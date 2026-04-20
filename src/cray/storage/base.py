"""
Base storage backend interface.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save_task(self, task_data: Dict[str, Any]) -> str:
        """Save a task, return task ID."""
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        pass

    @abstractmethod
    async def list_tasks(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering."""
        pass

    @abstractmethod
    async def save_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """Save a workflow, return workflow name."""
        pass

    @abstractmethod
    async def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow by name."""
        pass

    @abstractmethod
    async def list_workflows(self) -> List[str]:
        """List all workflow names."""
        pass

    @abstractmethod
    async def delete_workflow(self, name: str) -> bool:
        """Delete a workflow."""
        pass

    @abstractmethod
    async def save_run(self, run_data: Dict[str, Any]) -> str:
        """Save a run, return run ID."""
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID."""
        pass

    @abstractmethod
    async def list_runs(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List runs with optional filtering."""
        pass

    @abstractmethod
    async def delete_run(self, run_id: str) -> bool:
        """Delete a run."""
        pass
