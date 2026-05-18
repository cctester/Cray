"""
Task definition and status management.
"""

from __future__ import annotations
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    """Task execution status."""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class TaskResult(BaseModel):
    """Result of a single step execution."""
    
    step_name: str
    success: bool
    output: Optional[Union[Dict[str, Any], str, List[Any], Any]] = None
    error: Optional[str] = None
    duration_ms: int = 0


class Task(BaseModel):
    """Task instance - a single execution of a workflow."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    results: List[TaskResult] = Field(default_factory=list)
    
    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def succeed(self) -> None:
        """Mark task as succeeded."""
        self.status = TaskStatus.SUCCESS
        self.finished_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = datetime.now(timezone.utc)

    def skip(self) -> None:
        """Mark task as skipped."""
        self.status = TaskStatus.SKIPPED
        self.finished_at = datetime.now(timezone.utc)

    def retry(self) -> None:
        """Mark task as retrying."""
        self.status = TaskStatus.RETRYING

    def is_retrying(self) -> bool:
        """Check if task is currently retrying."""
        return self.status == TaskStatus.RETRYING
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if task is complete (success, failed, or skipped)."""
        return self.status in {
            TaskStatus.SUCCESS, 
            TaskStatus.FAILED, 
            TaskStatus.SKIPPED
        }
    
    def add_result(self, result: TaskResult) -> None:
        """Add a step result."""
        self.results.append(result)
        
        # Update output with step result
        if result.success and result.output is not None:
            self.output[result.step_name] = result.output
