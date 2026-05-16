"""Scheduler for Cray - schedule workflows with APScheduler and persistence."""

import json
import asyncio
import fcntl
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
from loguru import logger

from cray.core.workflow import Workflow, TriggerType
from cray.core.runner import Runner
from cray.core.task import Task

# Default persistence file location
_DEFAULT_PERSIST_PATH = "~/.cray/scheduler_jobs.json"


class Scheduler:
    """Schedule workflows to run at specific times or intervals.

    Uses APScheduler for scheduling. Job definitions are persisted to a
    JSON file so they survive process restarts. On start(), previously
    saved jobs are automatically reloaded and re-scheduled.
    """

    def __init__(
        self,
        runner: Optional[Runner] = None,
        persist_path: Optional[str] = None,
    ):
        self.runner = runner or Runner()
        self._scheduler = None
        self._jobs: Dict[str, Any] = {}
        self._persist_path = Path(
            persist_path or _DEFAULT_PERSIST_PATH
        ).expanduser()
        # Ensure parent directory exists
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Persistence ─────────────────────────────────────────────────

    def _save_jobs(self) -> None:
        """Persist current job definitions to JSON file.

        Uses file locking to prevent concurrent writes from corrupting
        the data. Only serializable metadata is saved (not the live
        APScheduler job object).
        """
        serializable: Dict[str, Any] = {}
        for job_id, info in self._jobs.items():
            serializable[job_id] = {
                "workflow": info["workflow"],
                "cron": info.get("cron"),
                "interval_seconds": info.get("interval_seconds"),
                "workflow_file": info.get("workflow_file"),
                "created_at": info.get("created_at"),
            }

        try:
            with open(self._persist_path, "w", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    json.dump(serializable, f, indent=2)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Failed to persist scheduler jobs: {e}")

    def _load_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Load persisted job definitions from JSON file.

        Returns:
            Dict of job_id -> job metadata, or empty dict if file
            doesn't exist or is corrupt.
        """
        if not self._persist_path.exists():
            return {}

        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            if not isinstance(data, dict):
                logger.warning(
                    f"Scheduler persist file has invalid format, ignoring"
                )
                return {}

            return data
        except json.JSONDecodeError as e:
            logger.warning(
                f"Scheduler persist file is corrupt, ignoring: {e}"
            )
            return {}
        except Exception as e:
            logger.warning(f"Failed to load scheduler jobs: {e}")
            return {}

    def _restore_jobs(self) -> None:
        """Restore previously persisted jobs on scheduler start.

        Reads the persist file and re-schedules each job. If a workflow
        file is recorded, the workflow is re-loaded from disk. Jobs whose
        workflow files are missing are skipped with a warning.
        """
        saved = self._load_jobs()
        if not saved:
            return

        restored = 0
        for job_id, info in saved.items():
            workflow_file = info.get("workflow_file")
            if not workflow_file:
                logger.warning(
                    f"Skipping job '{job_id}': no workflow_file recorded"
                )
                continue

            wf_path = Path(workflow_file)
            if not wf_path.exists():
                logger.warning(
                    f"Skipping job '{job_id}': workflow file "
                    f"'{workflow_file}' not found"
                )
                continue

            try:
                workflow = Workflow.from_yaml(wf_path)
                cron = info.get("cron")
                interval_seconds = info.get("interval_seconds")

                self.schedule_workflow(
                    workflow,
                    cron=cron,
                    interval_seconds=interval_seconds,
                    job_id=job_id,
                    workflow_file=workflow_file,
                    created_at=info.get("created_at"),
                    skip_persist=True,  # Don't re-save during restore
                )
                restored += 1
            except Exception as e:
                logger.warning(
                    f"Failed to restore job '{job_id}': {e}"
                )

        if restored:
            logger.info(f"Restored {restored} scheduled job(s)")
        if len(saved) > restored:
            skipped = len(saved) - restored
            logger.warning(
                f"Skipped {skipped} job(s) that could not be restored"
            )

    # ── Scheduler lifecycle ─────────────────────────────────────────

    def _get_scheduler(self):
        """Lazy load APScheduler."""
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler

                # Try to attach to an existing event loop so APScheduler
                # can start even when called from a non-async context
                # (e.g., CLI commands, tests)
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                self._scheduler = AsyncIOScheduler(event_loop=loop)
            except ImportError:
                raise ImportError(
                    "APScheduler is required for scheduling. "
                    "Install with: pip install cray[schedule]"
                )
        return self._scheduler

    def start(self) -> None:
        """Start the scheduler and restore persisted jobs."""
        scheduler = self._get_scheduler()
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started")

        # Restore persisted jobs after scheduler is running
        self._restore_jobs()

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")

    # ── Job management ──────────────────────────────────────────────

    def schedule_workflow(
        self,
        workflow: Workflow,
        cron: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        job_id: Optional[str] = None,
        workflow_file: Optional[str] = None,
        created_at: Optional[str] = None,
        skip_persist: bool = False,
    ) -> str:
        """Schedule a workflow to run periodically.

        Args:
            workflow: Workflow to schedule
            cron: Cron expression (e.g., "0 9 * * *" for daily at 9am)
            interval_seconds: Run every N seconds
            job_id: Optional job ID (defaults to workflow name)
            workflow_file: Path to the workflow YAML file (for persistence)
            created_at: ISO timestamp when job was first created
            skip_persist: If True, don't write to persist file (used
                during restore to avoid redundant writes)

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
                    logger.success(
                        f"Scheduled workflow '{workflow.name}' completed"
                    )
                else:
                    logger.error(
                        f"Scheduled workflow '{workflow.name}' failed: "
                        f"{task.error}"
                    )
            except Exception as e:
                logger.exception(
                    f"Scheduled workflow '{workflow.name}' error: {e}"
                )

        # Remove existing job with same ID
        if job_id in self._jobs:
            self.unschedule(job_id, skip_persist=True)

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
            raise ValueError(
                "Either cron or interval_seconds must be provided"
            )

        self._jobs[job_id] = {
            "job": job,
            "workflow": workflow.name,
            "cron": cron,
            "interval_seconds": interval_seconds,
            "workflow_file": workflow_file,
            "created_at": created_at or datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Scheduled workflow '{workflow.name}' (job_id: {job_id})"
        )

        if not skip_persist:
            self._save_jobs()

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

    def unschedule(
        self, job_id: str, skip_persist: bool = False
    ) -> bool:
        """Remove a scheduled workflow.

        Args:
            job_id: Job ID to remove
            skip_persist: If True, don't update persist file (used
                internally during re-schedule)

        Returns:
            True if job was removed, False if not found
        """
        scheduler = self._get_scheduler()
        if job_id in self._jobs:
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass  # Job may already be removed from APScheduler
            del self._jobs[job_id]
            logger.info(f"Unscheduled job: {job_id}")

            if not skip_persist:
                self._save_jobs()

            return True
        return False

    def list_jobs(self) -> Dict[str, Dict[str, Any]]:
        """List all scheduled jobs."""
        return {
            job_id: {
                "workflow": job_info["workflow"],
                "cron": job_info.get("cron"),
                "interval_seconds": job_info.get("interval_seconds"),
                "workflow_file": job_info.get("workflow_file"),
                "created_at": job_info.get("created_at"),
                "next_run": (
                    str(job_info["job"].next_run_time)
                    if job_info["job"].next_run_time
                    else None
                ),
            }
            for job_id, job_info in self._jobs.items()
        }

    def schedule_from_workflow(self, workflow: Workflow) -> Optional[str]:
        """Schedule a workflow based on its trigger configuration.

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
