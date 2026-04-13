"""Tests for Scheduler."""

import pytest
import asyncio

from cray.core.workflow import Workflow, Step, Trigger
from cray.scheduler import Scheduler


class TestScheduler:
    """Test Scheduler class."""
    
    @pytest.fixture
    def scheduler(self):
        """Create scheduler instance."""
        return Scheduler()
    
    @pytest.fixture
    def sample_workflow(self):
        """Create a sample workflow."""
        return Workflow(
            name="test-workflow",
            steps=[
                Step(name="echo", plugin="shell", action="exec", params={"command": "echo test"})
            ]
        )
    
    def test_scheduler_creation(self, scheduler):
        """Test scheduler can be created."""
        assert scheduler is not None
        assert scheduler._scheduler is None  # Lazy loaded
    
    def test_list_jobs_empty(self, scheduler):
        """Test listing jobs when empty."""
        jobs = scheduler.list_jobs()
        assert jobs == {}
    
    @pytest.mark.asyncio
    async def test_schedule_with_interval(self, scheduler, sample_workflow):
        """Test scheduling with interval."""
        try:
            scheduler.start()
            
            job_id = scheduler.schedule_workflow(
                sample_workflow,
                interval_seconds=3600  # Every hour
            )
            
            assert job_id is not None
            assert "test-workflow" in job_id
            
            jobs = scheduler.list_jobs()
            assert job_id in jobs
            assert jobs[job_id]["workflow"] == "test-workflow"
            
        finally:
            scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_schedule_with_cron(self, scheduler, sample_workflow):
        """Test scheduling with cron expression."""
        try:
            scheduler.start()
            
            job_id = scheduler.schedule_workflow(
                sample_workflow,
                cron="0 9 * * *"  # Daily at 9 AM
            )
            
            assert job_id is not None
            
            jobs = scheduler.list_jobs()
            assert job_id in jobs
            assert jobs[job_id]["cron"] == "0 9 * * *"
            
        finally:
            scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_unschedule(self, scheduler, sample_workflow):
        """Test unscheduling a workflow."""
        try:
            scheduler.start()
            
            job_id = scheduler.schedule_workflow(
                sample_workflow,
                interval_seconds=3600
            )
            
            # Verify scheduled
            assert job_id in scheduler.list_jobs()
            
            # Unschedule
            result = scheduler.unschedule(job_id)
            assert result is True
            
            # Verify removed
            assert job_id not in scheduler.list_jobs()
            
            # Try to unschedule again
            result = scheduler.unschedule(job_id)
            assert result is False
            
        finally:
            scheduler.stop()
