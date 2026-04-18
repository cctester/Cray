"""
Cray REST API and WebSocket server.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from loguru import logger

from cray.core import Workflow, WorkflowRunner
from cray.plugins import PluginRegistry


# Models
class WorkflowCreate(BaseModel):
    name: str
    content: str


class WorkflowRunRequest(BaseModel):
    input: Optional[Dict[str, Any]] = None


class RunResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    duration: Optional[int] = None
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = []


# In-memory storage
workflows: Dict[str, Dict] = {}
runs: Dict[str, Dict] = {}
websocket_clients: List[WebSocket] = []


def create_app(workflows_dir: str = "./workflows") -> FastAPI:
    """Create FastAPI application."""
    
    app = FastAPI(title="Cray API", version="1.0.0")
    
    # Load workflows
    workflows_path = Path(workflows_dir)
    if workflows_path.exists():
        for file in workflows_path.glob("*.yaml"):
            try:
                wf = Workflow.from_yaml(str(file))
                workflows[wf.name] = {
                    "id": wf.name,
                    "name": wf.name,
                    "version": wf.version,
                    "description": wf.description,
                    "file_path": str(file),
                    "steps": [{"name": s.name, "plugin": s.plugin} for s in wf.steps],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"Failed to load workflow {file}: {e}")
    
    # REST API Routes
    
    @app.get("/api/workflows")
    async def list_workflows():
        """List all workflows."""
        return list(workflows.values())
    
    @app.get("/api/workflows/{workflow_id}")
    async def get_workflow(workflow_id: str):
        """Get workflow details."""
        if workflow_id not in workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return workflows[workflow_id]
    
    @app.post("/api/workflows/{workflow_id}/run")
    async def run_workflow(workflow_id: str, request: WorkflowRunRequest):
        """Run a workflow."""
        if workflow_id not in workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        wf_data = workflows[workflow_id]
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(runs)}"
        
        run_data = {
            "id": run_id,
            "workflow_id": workflow_id,
            "workflow_name": wf_data["name"],
            "status": "pending",
            "started_at": datetime.now().isoformat(),
            "input": request.input or {},
            "steps": [],
        }
        runs[run_id] = run_data
        
        # Broadcast run started
        await broadcast({"type": "run_started", "run": run_data})
        
        # Run workflow in background
        asyncio.create_task(run_workflow_task(run_id, wf_data["file_path"], request.input))
        
        return run_data
    
    @app.get("/api/runs")
    async def list_runs():
        """List all runs."""
        return list(runs.values())
    
    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str):
        """Get run details."""
        if run_id not in runs:
            raise HTTPException(status_code=404, detail="Run not found")
        return runs[run_id]
    
    @app.post("/api/runs/{run_id}/stop")
    async def stop_run(run_id: str):
        """Stop a running workflow."""
        if run_id not in runs:
            raise HTTPException(status_code=404, detail="Run not found")
        
        run_data = runs[run_id]
        if run_data["status"] != "running":
            raise HTTPException(status_code=400, detail="Run is not running")
        
        run_data["status"] = "stopped"
        run_data["completed_at"] = datetime.now().isoformat()
        
        await broadcast({"type": "run_updated", "run": run_data})
        
        return run_data
    
    @app.get("/api/plugins")
    async def list_plugins():
        """List available plugins."""
        registry = PluginRegistry()
        return [
            {
                "name": p.name,
                "description": p.description,
                "version": "1.0.0",
            }
            for p in registry._plugins.values()
        ]

    # Secrets Management API
    from cray.core.secrets import get_secrets_manager, SecretBackend

    @app.get("/api/secrets")
    async def list_secrets():
        """List all secrets (metadata only, no values)."""
        sm = get_secrets_manager()
        secrets = sm.list()
        return [
            {
                "name": s.name,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "backend": s.backend.value,
                "tags": s.tags
            }
            for s in secrets
        ]

    @app.post("/api/secrets/{name}")
    async def set_secret_value(name: str, data: dict):
        """Set a secret value."""
        sm = get_secrets_manager()
        value = data.get("value")
        tags = data.get("tags", [])

        if not value:
            raise HTTPException(status_code=400, detail="value required")

        sm.set(name, value, tags)
        return {"status": "ok", "name": name}

    @app.delete("/api/secrets/{name}")
    async def delete_secret(name: str):
        """Delete a secret."""
        sm = get_secrets_manager()
        if not sm.delete(name):
            raise HTTPException(status_code=404, detail="Secret not found")
        return {"status": "deleted", "name": name}

    # Versioning API
    from cray.core.versioning import get_version_manager

    @app.get("/api/workflows/{workflow_id}/versions")
    async def list_workflow_versions(workflow_id: str):
        """List all versions of a workflow."""
        vm = get_version_manager()
        versions = vm.list_versions(workflow_id)
        return [
            {
                "version_id": v.version_id,
                "created_at": v.created_at,
                "author": v.author,
                "message": v.message,
                "tags": v.tags
            }
            for v in versions
        ]

    @app.post("/api/workflows/{workflow_id}/versions")
    async def save_workflow_version(workflow_id: str, data: dict):
        """Save current workflow as a new version."""
        vm = get_version_manager()

        # Get workflow content
        if workflow_id not in workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        wf_data = workflows[workflow_id]
        wf_path = Path(wf_data["file_path"])

        if not wf_path.exists():
            raise HTTPException(status_code=404, detail="Workflow file not found")

        content = wf_path.read_text()

        version = vm.save_version(
            workflow_id,
            content,
            message=data.get("message", ""),
            author=data.get("author", ""),
            tags=data.get("tags", [])
        )

        return version.to_dict()

    @app.post("/api/workflows/{workflow_id}/rollback/{version_id}")
    async def rollback_workflow(workflow_id: str, version_id: str):
        """Rollback workflow to a previous version."""
        vm = get_version_manager()

        success = vm.rollback(workflow_id, version_id)
        if not success:
            raise HTTPException(status_code=400, detail="Rollback failed")

        # Reload workflow
        wf_data = workflows[workflow_id]
        wf = Workflow.from_yaml(wf_data["file_path"])
        workflows[workflow_id] = {
            "id": wf.name,
            "name": wf.name,
            "version": wf.version,
            "description": wf.description,
            "file_path": wf_data["file_path"],
            "steps": [{"name": s.name, "plugin": s.plugin} for s in wf.steps],
            "updated_at": datetime.now().isoformat(),
        }

        return {"status": "rolled_back", "version": version_id}

    @app.get("/api/workflows/{workflow_id}/diff/{from_version}/{to_version}")
    async def diff_workflow_versions(
        workflow_id: str,
        from_version: str,
        to_version: str
    ):
        """Compare two versions of a workflow."""
        vm = get_version_manager()
        diff = vm.diff(workflow_id, from_version, to_version)

        if not diff:
            raise HTTPException(status_code=404, detail="Version not found")

        return {
            "from": from_version,
            "to": to_version,
            "additions": diff.additions,
            "deletions": diff.deletions,
            "changes": diff.changes[:50]  # Limit changes
        }

    # WebSocket
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        websocket_clients.append(websocket)
        
        try:
            while True:
                data = await websocket.receive_text()
                # Handle incoming messages if needed
                logger.debug(f"WebSocket received: {data}")
        except WebSocketDisconnect:
            websocket_clients.remove(websocket)
    
    async def broadcast(message: dict):
        """Broadcast message to all WebSocket clients."""
        for client in websocket_clients:
            try:
                await client.send_json(message)
            except Exception:
                pass
    
    async def run_workflow_task(run_id: str, workflow_path: str, input_data: dict):
        """Run workflow in background."""
        try:
            runs[run_id]["status"] = "running"
            await broadcast({"type": "run_updated", "run": runs[run_id]})
            
            # Run workflow
            workflow = Workflow.from_yaml(workflow_path)
            runner = WorkflowRunner()
            result = await runner.run(workflow, input_data or {})
            
            # Update run
            runs[run_id]["status"] = "success"
            runs[run_id]["completed_at"] = datetime.now().isoformat()
            runs[run_id]["output"] = result
            runs[run_id]["duration"] = int(
                (datetime.fromisoformat(runs[run_id]["completed_at"]) -
                 datetime.fromisoformat(runs[run_id]["started_at"])).total_seconds() * 1000
            )
            
        except Exception as e:
            logger.error(f"Workflow run failed: {e}")
            runs[run_id]["status"] = "failed"
            runs[run_id]["error"] = str(e)
            runs[run_id]["completed_at"] = datetime.now().isoformat()
        
        await broadcast({"type": "run_completed", "run": runs[run_id]})
    
    # Serve dashboard
    dashboard_path = Path(__file__).parent.parent.parent / "dashboard" / "dist"
    if dashboard_path.exists():
        app.mount("/assets", StaticFiles(directory=dashboard_path / "assets"), name="assets")
        
        @app.get("/{path:path}")
        async def serve_dashboard(path: str):
            """Serve dashboard for all non-API routes."""
            return FileResponse(dashboard_path / "index.html")
    
    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, workflows_dir: str = "./workflows"):
    """Run the API server."""
    app = create_app(workflows_dir)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
