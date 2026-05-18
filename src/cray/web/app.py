"""Cray Web Application - FastAPI backend with WebSocket support."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set, Any, Optional

import psutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from loguru import logger

# Configure logging - print to stdout for debug visibility
import sys
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="{time:HH:mm:ss} | {level: <8} | {message}")
logger.add(sys.stderr, level="WARNING", format="{time:HH:mm:ss} | {level: <8} | {message}")

from cray.core.runner import WorkflowRunner
from cray.core.workflow import WorkflowManager
from cray.core.versioning import WorkflowVersionManager, get_version_manager
from cray.plugins import PluginRegistry, PluginManager


# ── API Key Authentication ──────────────────────────────────────────

_API_KEY: Optional[str] = os.environ.get("CRAY_API_KEY")


async def verify_api_key(request: Request) -> None:
    """Dependency that verifies API key if CRAY_API_KEY is set.

    If CRAY_API_KEY env var is not set, all requests are allowed (dev mode).
    If set, requests must include `X-API-Key` header matching the value.
    """
    if _API_KEY is None:
        return  # No auth required in dev mode

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        api_key = request.query_params.get("api_key")

    if api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# Connection manager for WebSocket
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    MAX_CONNECTIONS = 100  # Limit concurrent WebSocket connections

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        async with self._lock:
            if len(self.active_connections) >= self.MAX_CONNECTIONS:
                await websocket.close(code=1013, reason="Too many connections")
                logger.warning("WebSocket connection rejected: max connections reached")
                return False
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
        return True

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        message_json = json.dumps(message)
        disconnected = set()

        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    self.active_connections.discard(conn)


# Global connection manager
manager = ConnectionManager()

# Initialize storage based on configuration
def get_storage(backend: str = "json", data_dir: str = "~/.cray/data", db_path: str = "~/.cray/cray.db"):
    """Create storage backend based on configuration."""
    if backend == "json":
        from cray.storage import JsonStore
        return JsonStore(data_dir)
    elif backend == "sqlite":
        from cray.storage import SqliteStore
        return SqliteStore(db_path)
    elif backend == "postgres":
        raise NotImplementedError("PostgreSQL backend not yet implemented")
    else:
        raise ValueError(f"Unknown storage backend: {backend}")


# Initialize from environment if set, otherwise use JSON default
storage_backend = os.environ.get("CRAY_STORAGE_BACKEND", "json")
data_dir = os.path.expanduser(os.environ.get("CRAY_DATA_DIR", "~/.cray/data"))
logger.info(f"STORAGE_INIT: backend={storage_backend}, data_dir={data_dir}")
storage = get_storage(
    backend=storage_backend,
    data_dir=data_dir,
    db_path=os.path.expanduser(os.environ.get("CRAY_DB_PATH", "~/.cray/cray.db"))
)

# Initialize managers
workflow_manager = WorkflowManager()
runner = WorkflowRunner(storage=storage)
plugin_manager = PluginManager()
plugin_registry = PluginRegistry()
version_manager = get_version_manager()


# Event broadcaster - hooks into runner events
class EventBroadcaster:
    """Broadcasts workflow events to WebSocket clients."""

    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager

    async def __call__(self, event_type: str, data: Dict[str, Any]):
        """Handle events from runner."""
        run = data.get("run", {})
        run_id = run.get("id")
        
        if event_type == "run_started":
            await self.on_run_started(run)
        elif event_type == "run_updated":
            await self.on_run_updated(run)
        elif event_type == "run_completed":
            await self.on_run_completed(run)

    async def on_run_started(self, run: dict):
        """Called when a run starts."""
        await self.manager.broadcast({
            "type": "run_started",
            "run": run,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def on_step_started(self, run_id: str, step_name: str):
        """Called when a step starts."""
        await self.manager.broadcast({
            "type": "step_started",
            "run_id": run_id,
            "step": step_name,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def on_step_completed(self, run_id: str, step_name: str, success: bool, output: Any = None):
        """Called when a step completes."""
        await self.manager.broadcast({
            "type": "step_completed",
            "run_id": run_id,
            "step": step_name,
            "success": success,
            "output": output,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def on_run_updated(self, run: dict):
        """Called when a run status updates."""
        await self.manager.broadcast({
            "type": "run_updated",
            "run": run,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def on_run_completed(self, run: dict):
        """Called when a run completes."""
        await self.manager.broadcast({
            "type": "run_completed",
            "run": run,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def on_workflow_created(self, workflow: dict):
        """Called when a workflow is created."""
        await self.manager.broadcast({
            "type": "workflow_created",
            "workflow": workflow,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def on_workflow_updated(self, workflow: dict):
        """Called when a workflow is updated."""
        await self.manager.broadcast({
            "type": "workflow_updated",
            "workflow": workflow,
            "timestamp": datetime.utcnow().isoformat()
        })


# Create broadcaster
broadcaster = EventBroadcaster(manager)


# Lifespan context manager
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Cray Web Application")
    logger.info(f"[Web] Storage initialized: {storage}")
    logger.info(f"[Web] Runner storage: {runner._storage}")

    # Attach broadcaster to runner
    runner.set_event_handler(broadcaster)

    # Load runs from storage
    logger.info("LIFESPAN: About to load runs...")
    await runner.load_runs()
    runs_list = runner.list_runs()
    logger.info(f"LIFESPAN: Loaded {len(runs_list)} runs")

    # Rebuild metrics from loaded runs
    for run in runs_list:
        wf_name = run.get("workflow_name", "unknown")
        status = run.get("status", "unknown")
        logger.info(f"METRIC_REBUILD: {wf_name}:{status}")

    logger.info(f"LIFESPAN DONE: Loaded {len(runs_list)} runs from storage")

    yield

    # Shutdown
    logger.info("Shutting down Cray Web Application")


# Create FastAPI app
app = FastAPI(title="Cray Dashboard", lifespan=lifespan)

# Add CORS middleware
_CORS_ORIGINS = os.environ.get("CRAY_CORS_ORIGINS", "").split(",")
_CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    connected = await manager.connect(websocket)
    if not connected:
        return  # Max connections reached, already closed
    try:
        while True:
            # Wait for any message from client (ping/pong or commands)
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                # Handle client commands if needed
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - return service status."""
    return {"status": "ok", "service": "Cray Workflow Engine"}


# API Routes (with /api prefix)
@app.get("/api/workflows")
async def list_workflows(_auth=Depends(verify_api_key)):
    """List all workflows."""
    return workflow_manager.list_workflows()


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, _auth=Depends(verify_api_key)):
    """Get a specific workflow."""
    result = workflow_manager.get_workflow(workflow_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return result


@app.post("/api/workflows")
async def create_workflow(workflow: dict, _auth=Depends(verify_api_key)):
    """Create a new workflow."""
    if not workflow.get("name") and not workflow.get("id"):
        raise HTTPException(status_code=400, detail="workflow name or id is required")
    result = workflow_manager.save_workflow(workflow)
    wf_id = workflow.get("name") or workflow.get("id")
    if wf_id and workflow.get("content"):
        version_manager.save_version(wf_id, workflow["content"], message="Initial version")
    await broadcaster.on_workflow_created(result)
    return result


@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow: dict, _auth=Depends(verify_api_key)):
    """Update a workflow."""
    workflow["id"] = workflow_id
    result = workflow_manager.save_workflow(workflow)
    if workflow.get("content"):
        version_manager.save_version(workflow_id, workflow["content"], message="Updated")
    await broadcaster.on_workflow_updated(result)
    return result


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, _auth=Depends(verify_api_key)):
    """Delete a workflow."""
    deleted = workflow_manager.delete_workflow(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return {"status": "deleted"}


# Workflow versioning
@app.get("/api/workflows/{workflow_id}/versions")
async def list_workflow_versions(workflow_id: str, _auth=Depends(verify_api_key)):
    """List versions of a workflow."""
    versions = version_manager.list_versions(workflow_id)
    return [v.to_dict() for v in versions]


@app.post("/api/workflows/{workflow_id}/versions")
async def save_workflow_version(workflow_id: str, request: dict, _auth=Depends(verify_api_key)):
    """Save a new version of a workflow."""
    content = request.get("content", "")
    message = request.get("message", "")
    version = version_manager.save_version(workflow_id, content, message=message)
    return version.to_dict()


@app.post("/api/workflows/{workflow_id}/rollback/{version_id}")
async def rollback_workflow(workflow_id: str, version_id: str, _auth=Depends(verify_api_key)):
    """Rollback workflow to a specific version."""
    logger.info(f"Rolling back {workflow_id} to version {version_id}")
    success = version_manager.rollback(workflow_id, version_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Rollback failed: version {version_id} not found for workflow {workflow_id}")
    logger.info(f"Rollback result: {success}")
    return {"success": success, "workflow_id": workflow_id, "version_id": version_id}


@app.get("/api/workflows/{workflow_id}/diff/{from_version}/{to_version}")
async def diff_workflow_versions(workflow_id: str, from_version: str, to_version: str, _auth=Depends(verify_api_key)):
    """Compare two versions of a workflow."""
    diff = version_manager.diff(workflow_id, from_version, to_version)
    if not diff:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    return {
        "from_version": diff.from_version,
        "to_version": diff.to_version,
        "additions": diff.additions,
        "deletions": diff.deletions,
        "changes": diff.changes
    }


@app.get("/api/runs")
async def list_runs(_auth=Depends(verify_api_key)):
    """List all runs."""
    return runner.list_runs()


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str, _auth=Depends(verify_api_key)):
    """Get a specific run."""
    result = runner.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return result


@app.post("/api/runs")
async def create_run(request: dict, _auth=Depends(verify_api_key)):
    """Start a new run."""
    workflow_id = request.get("workflow_id")
    if not workflow_id:
        raise HTTPException(status_code=400, detail="workflow_id is required")
    input_data = request.get("input", {})
    return await runner.run_workflow(workflow_id, input_data)


@app.post("/api/runs/{run_id}/stop")
async def stop_run(run_id: str, _auth=Depends(verify_api_key)):
    """Stop a running workflow."""
    return await runner.stop_run(run_id)


@app.get("/api/plugins")
async def list_plugins(_auth=Depends(verify_api_key)):
    """List all available plugins."""
    result = []
    for name in ["shell", "http", "file", "json", "database", "git", "redis", "aws", "email", "notify", "math", "text"]:
        plugin = plugin_manager.get_plugin(name)
        if plugin:
            result.append({
                "name": plugin.name,
                "description": plugin.description,
                "actions": list(plugin.actions.keys()) if hasattr(plugin, 'actions') else []
            })
    return result


@app.get("/api/plugins/{plugin_name}")
async def get_plugin(plugin_name: str, _auth=Depends(verify_api_key)):
    """Get plugin details."""
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
    return {
        "name": plugin.name,
        "description": plugin.description,
        "actions": list(plugin.actions.keys())
    }


@app.get("/api/metrics/summary")
async def get_metrics_summary(_auth=Depends(verify_api_key)):
    """Get metrics summary."""
    runs = runner.list_runs()
    total = len(runs)
    success = len([r for r in runs if r.get("status") == "success"])
    failed = len([r for r in runs if r.get("status") == "failed"])
    running = len([r for r in runs if r.get("status") == "running"])
    return {
        "total_runs": total,
        "success": success,
        "failed": failed,
        "running": running,
        "status": "ok"
    }


@app.get("/api/metrics/realtime")
async def get_realtime_metrics(_auth=Depends(verify_api_key)):
    """Get real-time metrics."""
    process = psutil.Process()

    runs = runner.list_runs()
    total = len(runs)
    running = len([r for r in runs if r.get("status") == "running"])
    success = len([r for r in runs if r.get("status") == "success"])
    failed = len([r for r in runs if r.get("status") == "failed"])

    return {
        "timestamp": time.time(),
        "workflows": {
            "total_runs": total,
            "running": running,
            "successful": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        },
        "system": {
            "uptime_seconds": time.time() - psutil.boot_time(),
            "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
            "cpu_percent": process.cpu_percent(interval=0.1),
        }
    }


# Run workflow from YAML
@app.post("/api/workflows/run")
async def run_workflow_yaml(request: dict, _auth=Depends(verify_api_key)):
    """Run a workflow from YAML."""
    yaml_content = request.get("yaml")
    if not yaml_content:
        raise HTTPException(status_code=400, detail="yaml content is required")
    return await runner.run_from_yaml(yaml_content)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cray-api", "timestamp": time.time()}


# Legacy routes (without /api prefix) for backward compatibility
# NOTE: Legacy routes do not enforce API key auth for backward compatibility
@app.get("/workflows")
async def list_workflows_legacy():
    """List all workflows (legacy)."""
    return workflow_manager.list_workflows()


@app.get("/workflows/{workflow_id}")
async def get_workflow_legacy(workflow_id: str):
    """Get a specific workflow (legacy)."""
    result = workflow_manager.get_workflow(workflow_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return result


@app.post("/workflows")
async def create_workflow_legacy(workflow: dict):
    """Create a new workflow (legacy)."""
    result = workflow_manager.save_workflow(workflow)
    await broadcaster.on_workflow_created(result)
    return result


@app.put("/workflows/{workflow_id}")
async def update_workflow_legacy(workflow_id: str, workflow: dict):
    """Update a workflow (legacy)."""
    workflow["id"] = workflow_id
    result = workflow_manager.save_workflow(workflow)
    await broadcaster.on_workflow_updated(result)
    return result


@app.delete("/workflows/{workflow_id}")
async def delete_workflow_legacy(workflow_id: str):
    """Delete a workflow (legacy)."""
    deleted = workflow_manager.delete_workflow(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return {"status": "deleted"}


@app.get("/plugins")
async def list_plugins_legacy():
    """List all available plugins (legacy)."""
    return plugin_manager.list_plugins()


@app.get("/plugins/{plugin_name}")
async def get_plugin_legacy(plugin_name: str):
    """Get plugin details (legacy)."""
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
    return plugin


@app.post("/workflows/{workflow_id}/run")
async def run_workflow_legacy(workflow_id: str, request: dict):
    """Run a workflow (legacy)."""
    input_data = request.get("input_data", {})
    return await runner.run_workflow(workflow_id, input_data)


def create_app(workflow_dir: str = "./workflows") -> FastAPI:
    """Create a new FastAPI app instance (for testing).

    Note: This returns the global app singleton. The workflow_dir parameter
    is currently ignored — workflow directory is configured via environment.
    """
    return app


# Serve frontend
assets_path = Path(__file__).resolve().parent.parent.parent.parent / "dashboard" / "dist" / "assets"
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
    logger.info(f"Serving frontend assets from {assets_path}")
else:
    logger.warning(f"Frontend assets not found at {assets_path}. Run 'npm run build' in the dashboard directory.")


# Secrets management
_secrets: Dict[str, str] = {}


@app.get("/api/secrets")
async def list_secrets(_auth=Depends(verify_api_key)):
    """List secret names."""
    return list(_secrets.keys())


@app.post("/api/secrets/{name}")
async def set_secret(name: str, request: dict, _auth=Depends(verify_api_key)):
    """Set a secret."""
    value = request.get("value", "")
    _secrets[name] = value
    return {"name": name, "status": "set"}


@app.delete("/api/secrets/{name}")
async def delete_secret(name: str, _auth=Depends(verify_api_key)):
    """Delete a secret."""
    if name not in _secrets:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    del _secrets[name]
    return {"name": name, "status": "deleted"}
