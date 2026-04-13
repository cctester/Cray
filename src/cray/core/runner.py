"""
Workflow runner - executes workflows step by step.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

from cray.core.workflow import Workflow, Step
from cray.core.task import Task, TaskResult, TaskStatus
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
        
        # Context for step execution (stores step outputs)
        context: Dict[str, Any] = {"input": task.input, "steps": {}}
        
        try:
            for step in workflow.steps:
                result = await self._execute_step(step, context)
                task.add_result(result)
                context["steps"][step.name] = result.output or {}
                
                if not result.success:
                    # Step failed, check retry
                    if step.retry > 0:
                        for attempt in range(step.retry):
                            logger.warning(
                                f"Retrying step '{step.name}' "
                                f"({attempt + 1}/{step.retry})"
                            )
                            result = await self._execute_step(step, context)
                            task.results[-1] = result  # Update last result
                            
                            if result.success:
                                break
                    
                    if not result.success:
                        logger.error(f"Step '{step.name}' failed: {result.error}")
                        task.fail(f"Step '{step.name}' failed: {result.error}")
                        
                        # Execute on_failure handlers
                        await self._execute_callbacks(workflow.on_failure, context)
                        return task
            
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
            
            # Check condition if present
            if step.condition:
                if not self._evaluate_condition(step.condition, context):
                    logger.info(f"Step '{step.name}' skipped (condition not met)")
                    return TaskResult(
                        step_name=step.name,
                        success=True,
                        output={"skipped": True, "reason": "condition_not_met"}
                    )
            
            # Execute action with timeout
            output = await asyncio.wait_for(
                plugin.execute(step.action, step.params, context),
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
