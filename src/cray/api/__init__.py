"""
Cray REST API and WebSocket server.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
import uvicorn
from loguru import logger

from cray.core import Workflow, Runner as WorkflowRunner
from cray.plugins import PluginManager


# Models
class WorkflowCreate(BaseModel):
    name: str
    content: str = ""


class WorkflowRunRequest(BaseModel):
    workflow_id: Optional[str] = None
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


def create_app(workflows_dir: str = None) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(title="Cray API", version="1.0.0")

    # Metrics
    from cray.core.metrics import get_metrics_collector
    metrics_collector = get_metrics_collector()

    @app.get("/api/metrics/summary")
    async def get_metrics_summary():
        """Get metrics summary."""
        collector = get_metrics_collector()
        return collector.get_summary()

    @app.get("/api/metrics/workflows")
    async def get_workflow_metrics(workflow_name: Optional[str] = None, limit: int = 100):
        """Get workflow execution metrics."""
        collector = get_metrics_collector()
        return collector.get_workflow_metrics(workflow_name, limit)

    @app.get("/metrics")
    async def get_metrics():
        """Get metrics summary (alias for /api/metrics/summary)."""
        collector = get_metrics_collector()
        return collector.get_summary()

    @app.get("/api/metrics/realtime")
    async def get_realtime_metrics():
        """Get real-time system metrics."""
        import time
        collector = get_metrics_collector()
        summary = collector.get_summary()
        return {
            "timestamp": time.time(),
            "workflows": {
                "total_runs": summary["total_runs"],
                "successful": summary["successful"],
                "failed": summary["failed"],
                "running": summary["running"],
                "success_rate": round(summary["success_rate"] * 100, 1),
                "avg_duration": round(summary["avg_duration_seconds"], 2)
            },
            "system": {
                "uptime_seconds": int(summary["uptime_seconds"])
            }
        }

    @app.get("/api/metrics/prometheus")
    async def get_prometheus_metrics():
        """Get Prometheus-compatible metrics."""
        collector = get_metrics_collector()
        summary = collector.get_summary()
        lines = [
            f'cray_total_runs {summary["total_runs"]}',
            f'cray_successful {summary["successful"]}',
            f'cray_failed {summary["failed"]}',
            f'cray_running {summary["running"]}',
            f'cray_success_rate {summary["success_rate"]}',
            f'cray_avg_duration_seconds {summary["avg_duration_seconds"]}',
        ]
        return Response(content="\n".join(lines), media_type="text/plain")

    # Default to project root workflows directory
    if workflows_dir is None:
        workflows_dir = str((Path(__file__).parent / ".." / ".." / ".." / "workflows").resolve())
    
    # Load workflows
    workflows_path = Path(workflows_dir)
    workflows_path.mkdir(parents=True, exist_ok=True)
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
"steps": [{"name": s.name, "plugin": s.plugin, "action": s.action, "params": s.params} for s in wf.steps],
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

    @app.post("/api/workflows")
    async def create_workflow(request: WorkflowCreate):
        """Create a new workflow."""
        if request.name in workflows:
            raise HTTPException(status_code=400, detail="Workflow already exists")

        # Use default template only if content is empty
        if not request.content:
            content = f"name: {request.name}\ndescription: New workflow\nsteps:\n  - name: step1\n    plugin: shell\n    action: exec\n    params:\n      command: echo 'Hello'\n"
        else:
            content = request.content

        # Validate YAML content
        import yaml
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="YAML must be a dictionary")

        yaml_name = data.get("name")
        if yaml_name != request.name:
            raise HTTPException(status_code=400, detail=f"Name in YAML ('{yaml_name}') does not match request name ('{request.name}')")

        # Validate workflow structure
        errors = []
        if "steps" not in data:
            errors.append("Missing 'steps' field")
        if not data.get("steps"):
            errors.append("Workflow must have at least one step")
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        file_path = workflows_path / f"{request.name}.yaml"
        file_path.write_text(content)

        workflows[request.name] = {
            "id": request.name,
            "name": data.get("name", request.name),
            "version": data.get("version", "1.0.0"),
            "description": data.get("description", ""),
            "file_path": str(file_path),
            "steps": data.get("steps", []),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        return {"id": request.name, "name": request.name, "file": str(file_path)}

    @app.get("/api/workflows/{workflow_id}")
    async def get_workflow(workflow_id: str):
        """Get workflow details."""
        if workflow_id not in workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        wf = workflows[workflow_id].copy()
        file_path = wf.get("file_path") or str(workflows_path / f"{workflow_id}.yaml")
        if Path(file_path).exists():
            try:
                wf_obj = Workflow.from_yaml(file_path)
                wf["steps"] = [{"name": s.name, "plugin": s.plugin, "action": s.action, "params": s.params} for s in wf_obj.steps]
            except Exception as e:
                logger.error(f"Failed to parse workflow {workflow_id}: {e}")
                wf["steps"] = wf.get("steps", [])
        return wf

    @app.put("/api/workflows/{workflow_id}")
    async def update_workflow(workflow_id: str, request: WorkflowCreate):
        """Update a workflow."""
        if workflow_id not in workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        file_path = workflows_path / f"{workflow_id}.yaml"

        # Use default template only if content is empty
        if not request.content:
            content = f"name: {workflow_id}\ndescription: Updated\nsteps:\n  - name: step1\n    plugin: shell\n    action: exec\n    params:\n      command: echo 'Updated'\n"
        else:
            content = request.content

        # Validate YAML content
        import yaml
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="YAML must be a dictionary")

        yaml_name = data.get("name")
        if yaml_name != workflow_id:
            raise HTTPException(status_code=400, detail=f"Name in YAML ('{yaml_name}') does not match workflow_id ('{workflow_id}')")

        # Validate workflow structure
        errors = []
        if "steps" not in data:
            errors.append("Missing 'steps' field")
        if not data.get("steps"):
            errors.append("Workflow must have at least one step")
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        file_path.write_text(content)

        # Reload workflow from file
        wf_obj = Workflow.from_yaml(str(file_path))
        workflows[workflow_id] = {
            "id": wf_obj.name,
            "name": wf_obj.name,
            "version": wf_obj.version,
            "description": wf_obj.description,
            "file_path": str(file_path),
            "steps": [{"name": s.name, "plugin": s.plugin, "action": s.action, "params": s.params} for s in wf_obj.steps],
            "created_at": workflows.get(workflow_id, {}).get("created_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
        }

        return {"id": workflow_id, "name": workflow_id}

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
        asyncio.create_task(run_workflow_task(run_id, wf_data["file_path"], request.input or {}, workflow_id))

        return run_data

    @app.get("/api/runs")
    async def list_runs():
        """List all runs."""
        return list(runs.values())

    @app.post("/api/runs")
    async def create_run(request: WorkflowRunRequest):
        """Run a workflow by name."""
        if not request.workflow_id:
            raise HTTPException(status_code=400, detail="workflow_id required")

        workflow_id = request.workflow_id
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

        await broadcast({"type": "run_started", "run": run_data})
        asyncio.create_task(run_workflow_task(run_id, wf_data["file_path"], request.input or {}, workflow_id))

        return run_data

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
        manager = PluginManager()
        plugins = []
        for name in manager.list_plugins():
            plugin = manager.get_plugin(name)
            actions = []
            if plugin and hasattr(plugin, 'actions'):
                for action_name, action_data in plugin.actions.items():
                    actions.append({
                        "name": action_name,
                        "description": action_data.get("description", ""),
                        "params": [
                            {"name": p["name"], "type": p.get("type", "string"), "required": p.get("required", False), "default": p.get("default"), "description": p.get("description", "")}
                            for p in action_data.get("params", [])
                        ] if action_data.get("params") else []
                    })
            plugins.append({
                "name": name,
                "description": getattr(plugin, "description", ""),
                "version": "1.0.0",
                "actions": actions
            })
        return plugins

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
    
    async def run_workflow_task(run_id: str, workflow_path: str, input_data: dict, workflow_name: str):
        """Run workflow in background."""
        start_time = time.time()
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

            # Record metrics
            metrics_collector._increment_counter(
                f"cray_workflow_total",
                labels={"workflow": workflow_name, "status": "success"}
            )
            metrics_collector._record_histogram(
                f"cray_workflow_duration_seconds",
                time.time() - start_time,
                labels={"workflow": workflow_name}
            )

        except Exception as e:
            logger.error(f"Workflow run failed: {e}")
            runs[run_id]["status"] = "failed"
            runs[run_id]["error"] = str(e)
            runs[run_id]["completed_at"] = datetime.now().isoformat()

            # Record metrics for failure
            metrics_collector._increment_counter(
                f"cray_workflow_total",
                labels={"workflow": workflow_name, "status": "failed"}
            )
            metrics_collector._record_histogram(
                f"cray_workflow_duration_seconds",
                time.time() - start_time,
                labels={"workflow": workflow_name}
            )

        await broadcast({"type": "run_completed", "run": runs[run_id]})

# Health check endpoint
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "cray-api"}

    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, workflows_dir: str = None):
    """Run the API server."""
    app = create_app(workflows_dir)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
