"""
JSON file-based storage backend.
"""

import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from cray.storage.base import StorageBackend


class JsonStore(StorageBackend):
    """
    JSON file-based storage.
    
    Stores tasks and workflows in JSON files.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.tasks_dir = self.data_dir / "tasks"
        self.workflows_dir = self.data_dir / "workflows"
        
        # Create directories
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def _task_path(self, task_id: str) -> Path:
        """Get path for a task file."""
        # Use date-based subdirectories
        today = datetime.now().strftime("%Y-%m-%d")
        return self.tasks_dir / today / f"{task_id}.json"
    
    def _workflow_path(self, name: str) -> Path:
        """Get path for a workflow file."""
        return self.workflows_dir / f"{name}.json"
    
    async def save_task(self, task_data: Dict[str, Any]) -> str:
        """Save a task to JSON file."""
        task_id = task_data.get("id")
        if not task_id:
            raise ValueError("Task must have an id")
        
        path = self._task_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Run file write in executor
        def write_file():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(task_data, f, indent=2, default=str)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, write_file)
        
        logger.debug(f"Saved task: {task_id}")
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        # Search in date directories
        for date_dir in sorted(self.tasks_dir.iterdir(), reverse=True):
            if date_dir.is_dir():
                task_file = date_dir / f"{task_id}.json"
                if task_file.exists():
                    def read_file():
                        with open(task_file, "r", encoding="utf-8") as f:
                            return json.load(f)
                    
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, read_file)
        
        return None
    
    async def list_tasks(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering."""
        tasks = []
        
        # Collect all task files
        task_files = []
        for date_dir in sorted(self.tasks_dir.iterdir(), reverse=True):
            if date_dir.is_dir():
                task_files.extend(sorted(date_dir.glob("*.json"), reverse=True))
        
        # Load and filter tasks
        for task_file in task_files[offset:offset + limit]:
            def read_file():
                with open(task_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            
            loop = asyncio.get_event_loop()
            task = await loop.run_in_executor(None, read_file)
            
            # Apply filters
            if workflow_name and task.get("workflow_name") != workflow_name:
                continue
            if status and task.get("status") != status:
                continue
            
            tasks.append(task)
            
            if len(tasks) >= limit:
                break
        
        return tasks
    
    async def save_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """Save a workflow to JSON file."""
        name = workflow_data.get("name")
        if not name:
            raise ValueError("Workflow must have a name")
        
        path = self._workflow_path(name)
        
        def write_file():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(workflow_data, f, indent=2, default=str)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, write_file)
        
        logger.debug(f"Saved workflow: {name}")
        return name
    
    async def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow by name."""
        path = self._workflow_path(name)
        
        if not path.exists():
            return None
        
        def read_file():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, read_file)
    
    async def list_workflows(self) -> List[str]:
        """List all workflow names."""
        return [f.stem for f in self.workflows_dir.glob("*.json")]
    
    async def delete_workflow(self, name: str) -> bool:
        """Delete a workflow."""
        path = self._workflow_path(name)
        
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted workflow: {name}")
            return True
        
        return False
