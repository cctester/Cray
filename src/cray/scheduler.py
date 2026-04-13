"""
Scheduler for Cray - schedule workflows with APScheduler.
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime
from loguru import logger

from cray.core.workflow import Workflow, TriggerType
from cray.core.runner import Runner
from cray.core.task import Task


class Scheduler:
    """
    Schedule workflows to run at specific times or intervals.
    
    Uses APScheduler for scheduling.
    """
    
    def __init__(self, runner: Optional[Runner] = None):
        self.runner = runner or Runner()
        self._scheduler = None
        self._jobs: Dict[str, Any] = {}
    
    def _get_scheduler(self):
        """Lazy load APScheduler."""
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                self._scheduler = AsyncIOScheduler()
            except ImportError:
                raise ImportError(
                    "APScheduler is required for scheduling. "
                    "Install with: pip install cray[schedule]"
                )
        return self._scheduler
    
    def start(self) -> None:
        """Start the scheduler."""
        scheduler = self._get_scheduler()
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def schedule_workflow(
        self,
        workflow: Workflow,
        cron: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> str:
        """
        Schedule a workflow to run periodically.
        
        Args:
            workflow: Workflow to schedule
            cron: Cron expression (e.g., "0 9 * * *" for daily at 9am)
            interval_seconds: Run every N seconds
            job_id: Optional job ID (defaults to workflow name)
            
        Returns:
            Job ID
        """
        scheduler = self._get_scheduler()
        job_id = job_id or f"workflow_{workflow.name}"
        
        async def run_workflow():
            logger.info(f"Running scheduled workflow: {workflow.name}")
            try:
                task = await self.runner.run(workflow)
                if task.status.value == "success":
                    logger.success(f"Scheduled workflow '{workflow.name}' completed")
                else:
                    logger.error(f"Scheduled workflow '{workflow.name}' failed: {task.error}")
            except Exception as e:
                logger.exception(f"Scheduled workflow '{workflow.name}' error: {e}")
        
        # Remove existing job with same ID
        if job_id in self._jobs:
            self.unschedule(job_id)
        
        # Add new job
        if cron:
            job = scheduler.add_job(
                run_workflow,
                trigger="cron",
                **self._parse_cron(cron),
                id=job_id,
                name=workflow.name,
                replace_existing=True,
            )
        elif interval_seconds:
            job = scheduler.add_job(
                run_workflow,
                trigger="interval",
                seconds=interval_seconds,
                id=job_id,
                name=workflow.name,
                replace_existing=True,
            )
        else:
            raise ValueError("Either cron or interval_seconds must be provided")
        
        self._jobs[job_id] = {
            "job": job,
            "workflow": workflow.name,
            "cron": cron,
            "interval_seconds": interval_seconds,
        }
        
        logger.info(f"Scheduled workflow '{workflow.name}' (job_id: {job_id})")
        return job_id
    
    def _parse_cron(self, cron: str) -> Dict[str, int]:
        """Parse cron expression to APScheduler kwargs."""
        parts = cron.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron}")
        
        minute, hour, day, month, day_of_week = parts
        
        return {
            "minute": minute,
            "hour": hour,
            "day": day,
            "month": month,
            "day_of_week": day_of_week,
        }
    
    def unschedule(self, job_id: str) -> bool:
        """
        Remove a scheduled workflow.
        
        Args:
            job_id: Job ID to remove
            
        Returns:
            True if job was removed, False if not found
        """
        scheduler = self._get_scheduler()
        
        if job_id in self._jobs:
            scheduler.remove_job(job_id)
            del self._jobs[job_id]
            logger.info(f"Unscheduled job: {job_id}")
            return True
        
        return False
    
    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """List all scheduled jobs."""
        return {
            job_id: {
                "workflow": job_info["workflow"],
                "cron": job_info.get("cron"),
                "interval_seconds": job_info.get("interval_seconds"),
                "next_run": str(job_info["job"].next_run_time) if job_info["job"].next_run_time else None,
            }
            for job_id, job_info in self._jobs.items()
        }
    
    def schedule_from_workflow(self, workflow: Workflow) -> Optional[str]:
        """
        Schedule a workflow based on its trigger configuration.
        
        Args:
            workflow: Workflow with triggers defined
            
        Returns:
            Job ID if scheduled, None if no schedule trigger
        """
        for trigger in workflow.triggers:
            if trigger.type == TriggerType.SCHEDULE:
                cron = trigger.config.get("cron")
                if cron:
                    return self.schedule_workflow(workflow, cron=cron)
        
        return None
