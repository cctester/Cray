"""Cray Web Application - FastAPI backend with WebSocket support."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Set, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from loguru import logger

from cray.core.runner import WorkflowRunner
from cray.core.workflow import WorkflowManager
from cray.plugins import PluginRegistry

# Import Any for type hints
from typing import Any


# Connection manager for WebSocket
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

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

# Initialize managers
workflow_manager = WorkflowManager()
runner = WorkflowRunner()
plugin_registry = PluginRegistry()


# Event broadcaster - hooks into runner events
class EventBroadcaster:
    """Broadcasts workflow events to WebSocket clients."""

    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager

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

    # Attach broadcaster to runner
    runner.set_event_handler(broadcaster)

    yield

    # Shutdown
    logger.info("Shutting down Cray Web Application")


# Create FastAPI app
app = FastAPI(title="Cray Dashboard", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
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


# API Routes
@app.get("/api/workflows")
async def list_workflows():
    """List all workflows."""
    return workflow_manager.list_workflows()


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a specific workflow."""
    return workflow_manager.get_workflow(workflow_id)


@app.post("/api/workflows")
async def create_workflow(workflow: dict):
    """Create a new workflow."""
    result = workflow_manager.save_workflow(workflow)
    await broadcaster.on_workflow_created(result)
    return result


@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow: dict):
    """Update a workflow."""
    workflow["id"] = workflow_id
    result = workflow_manager.save_workflow(workflow)
    await broadcaster.on_workflow_updated(result)
    return result


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow."""
    workflow_manager.delete_workflow(workflow_id)
    return {"status": "deleted"}


@app.get("/api/runs")
async def list_runs():
    """List all runs."""
    return runner.list_runs()


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get a specific run."""
    return runner.get_run(run_id)


@app.post("/api/runs")
async def create_run(request: dict):
    """Start a new run."""
    workflow_id = request.get("workflow_id")
    input_data = request.get("input", {})
    return await runner.run_workflow(workflow_id, input_data)


@app.post("/api/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """Stop a running workflow."""
    return await runner.stop_run(run_id)


@app.get("/api/plugins")
async def list_plugins():
    """List all available plugins."""
    return plugin_registry.list_plugins()


@app.get("/api/plugins/{plugin_name}")
async def get_plugin(plugin_name: str):
    """Get plugin details."""
    return plugin_registry.get_plugin(plugin_name)


# Run workflow from YAML
@app.post("/api/workflows/run")
async def run_workflow_yaml(request: dict):
    """Run a workflow from YAML."""
    yaml_content = request.get("yaml")
    return await runner.run_from_yaml(yaml_content)


# Serve frontend
app.mount("/assets", StaticFiles(directory="dashboard/dist/assets"), name="assets")


@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve the SPA."""
    return FileResponse("dashboard/dist/index.html")
