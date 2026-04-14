"""
Workflow runner - executes workflows step by step.
"""

import asyncio
import os
from typing import Dict, Any, Optional, Set
from datetime import datetime
from loguru import logger

from cray.core.workflow import Workflow, Step
from cray.core.task import Task, TaskResult, TaskStatus
from cray.core.template import render
from cray.core.dependency import DependencyGraph, build_step_dependency_graph
from cray.plugins import PluginManager


class Runner:
    """Executes workflows and manages task execution."""

    def __init__(self, plugin_manager: Optional[PluginManager] = None):
        self.plugin_manager = plugin_manager or PluginManager()
        self._running_tasks: Dict[str, Task] = {}

    async def run(
        self,
        workflow: Workflow,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Execute a workflow.

        Args:
            workflow: The workflow to execute
            input_data: Optional input data for the workflow

        Returns:
            Task object with execution results
        """
        task = Task(
            workflow_name=workflow.name,
            input=input_data or {}
        )

        self._running_tasks[task.id] = task
        task.start()

        logger.info(f"Starting workflow '{workflow.name}' (task: {task.id})")

        # Build context with variables, input, and steps
        # Variables are merged with input (input takes precedence)
        context: Dict[str, Any] = {
            "variables": workflow.variables,
            "input": {**workflow.variables, **task.input},
            "steps": {}
        }

        try:
            # Build dependency graph for steps
            dep_graph = build_step_dependency_graph(workflow.steps)
            errors = dep_graph.validate()
            if errors:
                raise ValueError(f"Invalid step dependencies: {errors}")

            # Get execution order based on dependencies
            execution_order = dep_graph.get_execution_order()
            step_map = {s.name: s for s in workflow.steps}
            completed: Set[str] = set()

            for step_name in execution_order:
                step = step_map.get(step_name)
                if not step:
                    continue

                # Check if dependencies succeeded
                failed_deps = [
                    dep for dep in (step.depends_on or [])
                    if dep_graph.get_node(dep) and dep_graph.get_node(dep).status != "success"
                ]

                if failed_deps:
                    logger.warning(
                        f"Skipping step '{step_name}' due to failed dependencies: {failed_deps}"
                    )
                    result = TaskResult(
                        step_name=step_name,
                        success=True,
                        output={"skipped": True, "reason": f"dependencies_failed: {failed_deps}"}
                    )
                    task.add_result(result)
                    context["steps"][step_name] = result.output or {}
                    dep_graph.mark_skipped(step_name, f"dependencies_failed: {failed_deps}")
                    continue

                dep_graph.mark_running(step_name)
                result = await self._execute_step(step, context)
                task.add_result(result)
                context["steps"][step_name] = result.output or {}

                if result.success:
                    dep_graph.mark_success(step_name, result.output)
                else:
                    # Step failed, check retry
                    if step.retry > 0:
                        for attempt in range(step.retry):
                            logger.warning(
                                f"Retrying step '{step_name}' "
                                f"({attempt + 1}/{step.retry})"
                            )
                            result = await self._execute_step(step, context)
                            task.results[-1] = result  # Update last result

                            if result.success:
                                dep_graph.mark_success(step_name, result.output)
                                break

                    if not result.success:
                        dep_graph.mark_failed(step_name, result.error)
                        logger.error(f"Step '{step_name}' failed: {result.error}")
                        task.fail(f"Step '{step_name}' failed: {result.error}")

                        # Execute on_failure handlers
                        await self._execute_callbacks(workflow.on_failure, context)
                        return task

                completed.add(step_name)

            # All steps completed successfully
            task.succeed()
            logger.success(f"Workflow '{workflow.name}' completed successfully")

            # Execute on_success handlers
            await self._execute_callbacks(workflow.on_success, context)

        except Exception as e:
            logger.exception(f"Workflow execution error: {e}")
            task.fail(str(e))

        finally:
            self._running_tasks.pop(task.id, None)

        return task

    async def _execute_step(
        self,
        step: Step,
        context: Dict[str, Any]
    ) -> TaskResult:
        """Execute a single step."""
        start_time = datetime.now()

        logger.debug(f"Executing step '{step.name}' with plugin '{step.plugin}'")

        try:
            # Get plugin
            plugin = self.plugin_manager.get_plugin(step.plugin)

            if not plugin:
                return TaskResult(
                    step_name=step.name,
                    success=False,
                    error=f"Plugin '{step.plugin}' not found"
                )

            # Render templates in condition
            if step.condition:
                rendered_condition = render(step.condition, context, dict(os.environ))
                if not self._evaluate_condition(rendered_condition, context):
                    logger.info(f"Step '{step.name}' skipped (condition not met)")
                    return TaskResult(
                        step_name=step.name,
                        success=True,
                        output={"skipped": True, "reason": "condition_not_met"}
                    )

            # Render templates in params
            rendered_params = render(step.params, context, dict(os.environ))
            logger.debug(f"Rendered params for '{step.name}': {rendered_params}")

            # Execute action with timeout
            output = await asyncio.wait_for(
                plugin.execute(step.action, rendered_params, context),
                timeout=step.timeout
            )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return TaskResult(
                step_name=step.name,
                success=True,
                output=output,
                duration_ms=duration_ms
            )

        except asyncio.TimeoutError:
            return TaskResult(
                step_name=step.name,
                success=False,
                error=f"Step timed out after {step.timeout}s"
            )
        except Exception as e:
            return TaskResult(
                step_name=step.name,
                success=False,
                error=str(e)
            )

    def _evaluate_condition(
        self,
        condition: str,
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate a condition expression."""
        # Simple template evaluation
        # Supports: {{ steps.step_name.success }}, {{ steps.step_name.output.field }}

        try:
            # Replace template variables
            expr = condition.strip()

            # Handle common patterns
            if "{{ steps." in expr:
                import re
                pattern = r"\{\{\s*steps\.(\w+)\.(\w+)\s*\}\}"

                def replace(match):
                    step_name = match.group(1)
                    field = match.group(2)
                    step_result = context.get("steps", {}).get(step_name, {})
                    return str(step_result.get(field, False))

                expr = re.sub(pattern, replace, expr)

            # Evaluate as boolean
            return bool(eval(expr))

        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
            return False

    async def _execute_callbacks(
        self,
        callbacks: list,
        context: Dict[str, Any]
    ) -> None:
        """Execute callback actions."""
        for callback in callbacks:
            try:
                if isinstance(callback, dict):
                    # Execute callback action
                    for action, params in callback.items():
                        if action == "log":
                            logger.info(params)
                        elif action == "notify":
                            # TODO: Implement notification
                            logger.info(f"Notification: {params}")
            except Exception as e:
                logger.warning(f"Callback execution failed: {e}")

    def run_sync(
        self,
        workflow: Workflow,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(workflow, input_data))
