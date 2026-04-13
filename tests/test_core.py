"""Tests for core workflow functionality."""

import pytest
from pathlib import Path

from cray.core.workflow import Workflow, Step, Trigger, TriggerType
from cray.core.task import Task, TaskStatus


class TestWorkflow:
    """Test Workflow class."""
    
    def test_create_workflow(self):
        """Test creating a workflow."""
        workflow = Workflow(
            name="test",
            steps=[
                Step(name="step1", plugin="shell", action="exec", params={"command": "echo test"})
            ]
        )
        
        assert workflow.name == "test"
        assert len(workflow.steps) == 1
        assert workflow.steps[0].name == "step1"
    
    def test_load_from_yaml(self, sample_workflow_yaml):
        """Test loading workflow from YAML file."""
        workflow = Workflow.from_yaml(sample_workflow_yaml)
        
        assert workflow.name == "test-workflow"
        assert len(workflow.steps) == 1
        assert workflow.steps[0].plugin == "shell"
    
    def test_validate_steps(self):
        """Test workflow validation."""
        # Empty workflow
        workflow = Workflow(name="empty")
        errors = workflow.validate_steps()
        assert len(errors) > 0
        
        # Valid workflow
        workflow = Workflow(
            name="valid",
            steps=[Step(name="step1", plugin="shell", action="exec")]
        )
        errors = workflow.validate_steps()
        assert len(errors) == 0
    
    def test_duplicate_step_names(self):
        """Test detection of duplicate step names."""
        workflow = Workflow(
            name="test",
            steps=[
                Step(name="step1", plugin="shell", action="exec"),
                Step(name="step1", plugin="shell", action="exec"),
            ]
        )
        errors = workflow.validate_steps()
        assert any("Duplicate" in e for e in errors)


class TestTrigger:
    """Test Trigger class."""
    
    def test_manual_trigger(self):
        """Test manual trigger creation."""
        trigger = Trigger.manual()
        assert trigger.type == TriggerType.MANUAL
    
    def test_schedule_trigger(self):
        """Test schedule trigger creation."""
        trigger = Trigger.schedule("0 9 * * *")
        assert trigger.type == TriggerType.SCHEDULE
        assert trigger.config["cron"] == "0 9 * * *"


class TestTask:
    """Test Task class."""
    
    def test_task_creation(self):
        """Test task creation."""
        task = Task(workflow_name="test")
        assert task.status == TaskStatus.PENDING
        assert task.workflow_name == "test"
    
    def test_task_lifecycle(self):
        """Test task status transitions."""
        task = Task(workflow_name="test")
        
        # Start
        task.start()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        
        # Succeed
        task.succeed()
        assert task.status == TaskStatus.SUCCESS
        assert task.finished_at is not None
        assert task.is_complete
    
    def test_task_failure(self):
        """Test task failure."""
        task = Task(workflow_name="test")
        task.start()
        task.fail("Something went wrong")
        
        assert task.status == TaskStatus.FAILED
        assert task.error == "Something went wrong"
        assert task.is_complete
