"""
FastAPI Web Application for Cray.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import asyncio

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cray.core.workflow import Workflow
from cray.core.runner import Runner
from cray.core.task import Task, TaskStatus
from cray.plugins import PluginManager


# Request/Response Models
class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: List[Dict[str, Any]]


class WorkflowRunRequest(BaseModel):
    input_data: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    id: str
    workflow_name: str
    status: str
    created_at: str
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    results: List[Dict[str, Any]] = []


class WorkflowResponse(BaseModel):
    name: str
    version: str
    description: str
    steps: List[Dict[str, Any]]
    triggers: List[Dict[str, Any]]


# Application State
class AppState:
    def __init__(self):
        self.runner = Runner()
        self.workflows: Dict[str, Workflow] = {}
        self.tasks: Dict[str, Task] = {}
        self.workflow_dir = Path("./workflows")


state = AppState()


def create_app(workflow_dir: str = "./workflows") -> FastAPI:
    """Create FastAPI application."""
    
    app = FastAPI(
        title="Cray API",
        description="Web API for Cray automation tool",
        version="0.1.0",
    )
    
    state.workflow_dir = Path(workflow_dir)
    state.workflow_dir.mkdir(parents=True, exist_ok=True)
    
    # Load existing workflows
    for wf_file in state.workflow_dir.glob("*.yaml"):
        try:
            wf = Workflow.from_yaml(wf_file)
            state.workflows[wf.name] = wf
        except Exception:
            pass
    
    @app.get("/")
    async def root():
        """API root."""
        return {
            "name": "Cray API",
            "version": "0.1.0",
            "endpoints": {
                "workflows": "/workflows",
                "tasks": "/tasks",
                "plugins": "/plugins",
                "docs": "/docs",
            }
        }
    
    # === Workflows ===
    
    @app.get("/workflows", response_model=List[str])
    async def list_workflows():
        """List all workflows."""
        return list(state.workflows.keys())
    
    @app.get("/workflows/{name}", response_model=WorkflowResponse)
    async def get_workflow(name: str):
        """Get workflow details."""
        if name not in state.workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        wf = state.workflows[name]
        return WorkflowResponse(
            name=wf.name,
            version=wf.version,
            description=wf.description,
            steps=[s.model_dump() for s in wf.steps],
            triggers=[t.model_dump() for t in wf.triggers],
        )
    
    @app.post("/workflows", status_code=201)
    async def create_workflow(workflow: WorkflowCreate):
        """Create a new workflow."""
        if workflow.name in state.workflows:
            raise HTTPException(status_code=400, detail="Workflow already exists")
        
        from cray.core.workflow import Step
        
        steps = [Step(**s) for s in workflow.steps]
        wf = Workflow(
            name=workflow.name,
            description=workflow.description,
            steps=steps,
        )
        
        # Save to file
        wf.to_yaml(state.workflow_dir / f"{workflow.name}.yaml")
        state.workflows[workflow.name] = wf
        
        return {"created": workflow.name}
    
    @app.post("/workflows/{name}/run", response_model=TaskResponse)
    async def run_workflow(name: str, request: WorkflowRunRequest, background_tasks: BackgroundTasks):
        """Run a workflow."""
        if name not in state.workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        wf = state.workflows[name]
        
        # Run in background
        task = await state.runner.run(wf, request.input_data)
        state.tasks[task.id] = task
        
        return TaskResponse(
            id=task.id,
            workflow_name=task.workflow_name,
            status=task.status.value,
            created_at=task.created_at.isoformat(),
            duration_seconds=task.duration_seconds,
            error=task.error,
            results=[r.model_dump() for r in task.results],
        )
    
    @app.delete("/workflows/{name}")
    async def delete_workflow(name: str):
        """Delete a workflow."""
        if name not in state.workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        del state.workflows[name]
        wf_file = state.workflow_dir / f"{name}.yaml"
        if wf_file.exists():
            wf_file.unlink()
        
        return {"deleted": name}
    
    # === Tasks ===
    
    @app.get("/tasks", response_model=List[TaskResponse])
    async def list_tasks(limit: int = 50):
        """List recent tasks."""
        tasks = list(state.tasks.values())[-limit:]
        return [
            TaskResponse(
                id=t.id,
                workflow_name=t.workflow_name,
                status=t.status.value,
                created_at=t.created_at.isoformat(),
                duration_seconds=t.duration_seconds,
                error=t.error,
                results=[r.model_dump() for r in t.results],
            )
            for t in tasks
        ]
    
    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(task_id: str):
        """Get task details."""
        if task_id not in state.tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        t = state.tasks[task_id]
        return TaskResponse(
            id=t.id,
            workflow_name=t.workflow_name,
            status=t.status.value,
            created_at=t.created_at.isoformat(),
            duration_seconds=t.duration_seconds,
            error=t.error,
            results=[r.model_dump() for r in t.results],
        )
    
    # === Plugins ===
    
    @app.get("/plugins")
    async def list_plugins():
        """List available plugins."""
        return state.runner.plugin_manager.list_plugins()
    
    @app.get("/plugins/{name}")
    async def get_plugin(name: str):
        """Get plugin details."""
        plugin = state.runner.plugin_manager.get_plugin(name)
        if not plugin:
            raise HTTPException(status_code=404, detail="Plugin not found")
        
        return {
            "name": plugin.name,
            "description": plugin.description,
            "version": plugin.version,
        }
    
    return app
