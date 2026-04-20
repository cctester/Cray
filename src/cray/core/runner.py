"""
Workflow runner - executes workflows step by step.
"""

import asyncio
import os
import uuid
from typing import Dict, Any, Optional, Set, List, Callable, Awaitable
from datetime import datetime
from pathlib import Path
from loguru import logger

from cray.core.workflow import Workflow, Step
from cray.core.task import Task, TaskResult, TaskStatus
from cray.core.template import render
from cray.core.dependency import DependencyGraph, build_step_dependency_graph
from cray.plugins import PluginManager


# Event handler type
EventHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]


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

            # Choose execution mode
            if workflow.parallel:
                await self._run_parallel(workflow, task, context, dep_graph)
            else:
                await self._run_sequential(workflow, task, context, dep_graph)

            # Check final status
            if task.status == TaskStatus.RUNNING:
                task.succeed()
                logger.success(f"Workflow '{workflow.name}' completed successfully")
                # Execute on_success handlers
                await self._execute_callbacks(workflow.on_success, context)

        except Exception as e:
            logger.exception(f"Workflow execution error: {e}")
            task.fail(str(e))
            # Execute on_failure handlers
            await self._execute_callbacks(workflow.on_failure, context)

        finally:
            self._running_tasks.pop(task.id, None)

        return task

    async def _run_sequential(
        self,
        workflow: Workflow,
        task: Task,
        context: Dict[str, Any],
        dep_graph: DependencyGraph
    ) -> None:
        """Execute steps sequentially based on dependency order."""
        execution_order = dep_graph.get_execution_order()
        step_map = {s.name: s for s in workflow.steps}
        completed: Set[str] = set()

        for step_name in execution_order:
            step = step_map.get(step_name)
            if not step:
                continue

            # Check if dependencies succeeded
            failed_deps = self._check_failed_dependencies(step, dep_graph)

            if failed_deps:
                await self._skip_step(step, step_name, task, context, dep_graph,
                                       f"dependencies_failed: {failed_deps}")
                continue

            result = await self._execute_step_with_retry(step, context, dep_graph)
            task.add_result(result)
            context["steps"][step_name] = result.output or {}

            if not result.success:
                # Execute step-level on_error handler
                if step.on_error:
                    await self._execute_step_error_handler(step, result, context)

                if not step.continue_on_error:
                    # Execute workflow-level on_error handlers
                    await self._execute_callbacks(workflow.on_error, context)
                    task.fail(f"Step '{step_name}' failed: {result.error}")
                    return

            completed.add(step_name)

    async def _run_parallel(
        self,
        workflow: Workflow,
        task: Task,
        context: Dict[str, Any],
        dep_graph: DependencyGraph
    ) -> None:
        """Execute steps in parallel where possible."""
        step_map = {s.name: s for s in workflow.steps}
        completed: Set[str] = set()
        failed_steps: Set[str] = set()
        semaphore = asyncio.Semaphore(workflow.max_parallel)

        async def run_step_with_semaphore(step_name: str) -> tuple:
            async with semaphore:
                step = step_map[step_name]
                result = await self._execute_step_with_retry(step, context, dep_graph)
                return step_name, result

        while len(completed) < len(workflow.steps):
            # Get all steps ready to run
            ready = dep_graph.get_ready_nodes(completed)
            ready = [s for s in ready if s not in failed_steps]

            if not ready:
                # Check if we're stuck (all remaining steps have failed deps)
                remaining = set(step_map.keys()) - completed
                if remaining and all(
                    any(d in failed_steps for d in dep_graph.get_dependencies(s))
                    for s in remaining
                ):
                    logger.warning("All remaining steps have failed dependencies")
                    break
                # Wait a bit for other steps to complete
                await asyncio.sleep(0.1)
                continue

            # Run ready steps in parallel
            tasks = [run_step_with_semaphore(name) for name in ready]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for item in results:
                if isinstance(item, Exception):
                    logger.error(f"Step execution error: {item}")
                    continue

                step_name, result = item
                task.add_result(result)
                context["steps"][step_name] = result.output or {}
                completed.add(step_name)

                if result.success:
                    dep_graph.mark_success(step_name, result.output)
                else:
                    dep_graph.mark_failed(step_name, result.error)
                    failed_steps.add(step_name)

                    # Execute step-level on_error handler
                    step = step_map[step_name]
                    if step.on_error:
                        await self._execute_step_error_handler(step, result, context)

                    if not step.continue_on_error:
                        # Execute workflow-level on_error handlers
                        await self._execute_callbacks(workflow.on_error, context)
                        task.fail(f"Step '{step_name}' failed: {result.error}")
                        return

    def _check_failed_dependencies(
        self,
        step: Step,
        dep_graph: DependencyGraph
    ) -> List[str]:
        """Check if any dependencies have failed."""
        failed_deps = []
        for dep in (step.depends_on or []):
            node = dep_graph.get_node(dep)
            if node and node.status not in ("success", "pending"):
                failed_deps.append(dep)
        return failed_deps

    async def _skip_step(
        self,
        step: Step,
        step_name: str,
        task: Task,
        context: Dict[str, Any],
        dep_graph: DependencyGraph,
        reason: str
    ) -> None:
        """Skip a step and record the reason."""
        logger.warning(f"Skipping step '{step_name}': {reason}")
        result = TaskResult(
            step_name=step_name,
            success=True,
            output={"skipped": True, "reason": reason}
        )
        task.add_result(result)
        context["steps"][step_name] = result.output or {}
        dep_graph.mark_skipped(step_name, reason)

    async def _execute_step_with_retry(
        self,
        step: Step,
        context: Dict[str, Any],
        dep_graph: DependencyGraph
    ) -> TaskResult:
        """Execute a step with retry logic."""
        dep_graph.mark_running(step.name)
        retry_count = step.get_retry_count()

        result = await self._execute_step(step, context)

        if not result.success and retry_count > 0:
            for attempt in range(retry_count):
                logger.warning(
                    f"Retrying step '{step.name}' "
                    f"({attempt + 1}/{retry_count})"
                )
                # Wait before retry
                if step.retry_delay > 0:
                    await asyncio.sleep(step.retry_delay)
                result = await self._execute_step(step, context)
                if result.success:
                    break

        if result.success:
            dep_graph.mark_success(step.name, result.output)
        else:
            dep_graph.mark_failed(step.name, result.error)

        return result

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
                        elif action == "shell":
                            # Execute shell command as callback
                            from cray.plugins.builtin.shell import ShellPlugin
                            shell = ShellPlugin()
                            await shell.execute("exec", {"command": params}, context)
            except Exception as e:
                logger.warning(f"Callback execution failed: {e}")

    async def _execute_step_error_handler(
        self,
        step: Step,
        result: TaskResult,
        context: Dict[str, Any]
    ) -> None:
        """Execute step-level error handler."""
        if not step.on_error:
            return

        error_context = {
            **context,
            "error": {
                "step": step.name,
                "message": result.error,
                "success": False
            }
        }

        logger.info(f"Executing error handler for step '{step.name}'")

        for action, params in step.on_error.items():
            try:
                if action == "log":
                    logger.error(f"Step error: {params.format(error=result.error, step=step.name)}")
                elif action == "notify":
                    logger.info(f"Error notification: {params}")
                elif action == "retry":
                    # Already handled by retry logic
                    pass
                elif action == "ignore":
                    # Just log and continue
                    logger.info(f"Ignoring error in step '{step.name}'")
            except Exception as e:
                logger.warning(f"Error handler execution failed: {e}")

    def run_sync(
        self,
        workflow: Workflow,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(workflow, input_data))


class WorkflowRunner:
    """High-level workflow runner with event support and run management."""

    def __init__(self, plugin_manager: Optional[PluginManager] = None):
        self.runner = Runner(plugin_manager)
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._event_handler: Optional[EventHandler] = None

    def set_event_handler(self, handler: EventHandler):
        """Set event handler for workflow events."""
        self._event_handler = handler

    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to the handler if set."""
        if self._event_handler:
            try:
                await self._event_handler(event_type, data)
            except Exception as e:
                logger.warning(f"Event handler error: {e}")

    async def run_workflow(
        self,
        workflow_id: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a workflow by ID and return run info."""
        run_id = str(uuid.uuid4())[:8]

        # Create run record
        run_info = {
            "id": run_id,
            "workflow_id": workflow_id,
            "status": "pending",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "input": input_data or {},
            "output": None,
            "error": None,
            "steps": []
        }
        self._runs[run_id] = run_info

        # Emit run started event
        await self._emit_event("run_started", {"run": run_info})

        try:
            # Load workflow (placeholder - actual implementation would load from storage)
            workflow_path = Path(f"workflows/{workflow_id}.yaml")
            if workflow_path.exists():
                workflow = Workflow.from_yaml(workflow_path)
            else:
                # Create a simple workflow for testing
                workflow = Workflow(
                    name=workflow_id,
                    version="1.0",
                    steps=[]
                )

            # Update status
            run_info["status"] = "running"
            await self._emit_event("run_updated", {"run": run_info})

            # Execute workflow
            task = await self.runner.run(workflow, input_data)

            # Update run info with results
            run_info["status"] = "success" if task.status == TaskStatus.SUCCESS else "failed"
            run_info["completed_at"] = datetime.utcnow().isoformat()
            run_info["output"] = task.results
            run_info["steps"] = [
                {
                    "name": r.step_name,
                    "success": r.success,
                    "output": r.output,
                    "error": r.error,
                    "duration_ms": r.duration_ms
                }
                for r in task.results
            ]

            if task.status == TaskStatus.FAILED:
                run_info["error"] = task.error

        except Exception as e:
            logger.exception(f"Workflow run failed: {e}")
            run_info["status"] = "failed"
            run_info["error"] = str(e)
            run_info["completed_at"] = datetime.utcnow().isoformat()

        # Emit completion event
        await self._emit_event("run_completed", {"run": run_info})

        return run_info

    async def run_from_yaml(self, yaml_content: str) -> Dict[str, Any]:
        """Run a workflow from YAML content."""
        workflow = Workflow.from_yaml_string(yaml_content)
        run_id = str(uuid.uuid4())[:8]

        run_info = {
            "id": run_id,
            "workflow_id": workflow.name,
            "status": "pending",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "input": {},
            "output": None,
            "error": None,
            "steps": []
        }
        self._runs[run_id] = run_info

        await self._emit_event("run_started", {"run": run_info})

        try:
            run_info["status"] = "running"
            await self._emit_event("run_updated", {"run": run_info})

            task = await self.runner.run(workflow)

            run_info["status"] = "success" if task.status == TaskStatus.SUCCESS else "failed"
            run_info["completed_at"] = datetime.utcnow().isoformat()
            run_info["output"] = task.results
            run_info["steps"] = [
                {
                    "name": r.step_name,
                    "success": r.success,
                    "output": r.output,
                    "error": r.error,
                    "duration_ms": r.duration_ms
                }
                for r in task.results
            ]

            if task.status == TaskStatus.FAILED:
                run_info["error"] = task.error

        except Exception as e:
            logger.exception(f"Workflow run failed: {e}")
            run_info["status"] = "failed"
            run_info["error"] = str(e)
            run_info["completed_at"] = datetime.utcnow().isoformat()

        await self._emit_event("run_completed", {"run": run_info})

        return run_info

    async def stop_run(self, run_id: str) -> Dict[str, Any]:
        """Stop a running workflow."""
        if run_id not in self._runs:
            return {"error": "Run not found"}

        run_info = self._runs[run_id]
        if run_info["status"] == "running":
            run_info["status"] = "stopped"
            run_info["completed_at"] = datetime.utcnow().isoformat()
            await self._emit_event("run_completed", {"run": run_info})

        return {"status": "stopped", "run_id": run_id}

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all runs."""
        return list(self._runs.values())

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific run."""
        return self._runs.get(run_id)
