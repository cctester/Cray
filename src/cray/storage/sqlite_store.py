"""
SQLite-based storage backend.
"""

import sqlite3
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from loguru import logger

from cray.storage.base import StorageBackend


def dict_from_row(row: tuple, columns: List[str]) -> Dict[str, Any]:
    """Convert SQL row to dict."""
    return dict(zip(columns, row))


class SqliteStore(StorageBackend):
    """
    SQLite-based storage.

    Stores tasks, workflows, and runs in SQLite database.
    """

    def __init__(self, db_path: str = "~/.cray/cray.db"):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    workflow_name TEXT,
                    status TEXT,
                    data TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS workflows (
                    name TEXT PRIMARY KEY,
                    data TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT,
                    status TEXT,
                    data TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_workflow ON tasks(workflow_name);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_runs_workflow ON runs(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
            """)
            logger.info(f"Initialized database: {self.db_path}")

    async def save_task(self, task_data: Dict[str, Any]) -> str:
        """Save a task to database."""
        task_id = task_data.get("id")
        if not task_id:
            raise ValueError("Task must have an id")

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        import json
        data = json.dumps(task_data)

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tasks (id, workflow_name, status, data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM tasks WHERE id = ?), ?), ?)""",
                (task_id, task_data.get("workflow_name"), task_data.get("status"), data, task_id, now, now)
            )

        logger.debug(f"Saved task: {task_id}")
        return task_id

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        with self._conn() as conn:
            row = conn.execute("SELECT data FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                import json
                return json.loads(row[0])
        return None

    async def list_tasks(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering."""
        query = "SELECT data FROM tasks WHERE 1=1"
        params = []

        if workflow_name:
            query += " AND workflow_name = ?"
            params.append(workflow_name)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        import json
        tasks = []
        with self._conn() as conn:
            for row in conn.execute(query, params):
                tasks.append(json.loads(row[0]))
        return tasks

    async def save_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """Save a workflow to database."""
        name = workflow_data.get("name")
        if not name:
            raise ValueError("Workflow must have a name")

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        import json
        data = json.dumps(workflow_data)

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO workflows (name, data, created_at, updated_at)
                   VALUES (?, ?, COALESCE((SELECT created_at FROM workflows WHERE name = ?), ?), ?)""",
                (name, data, name, now, now)
            )

        logger.debug(f"Saved workflow: {name}")
        return name

    async def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow by name."""
        with self._conn() as conn:
            row = conn.execute("SELECT data FROM workflows WHERE name = ?", (name,)).fetchone()
            if row:
                import json
                return json.loads(row[0])
        return None

    async def list_workflows(self) -> List[str]:
        """List all workflow names."""
        with self._conn() as conn:
            return [row[0] for row in conn.execute("SELECT name FROM workflows ORDER BY name")]

    async def delete_workflow(self, name: str) -> bool:
        """Delete a workflow."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM workflows WHERE name = ?", (name,))
            return cursor.rowcount > 0

    async def save_run(self, run_data: Dict[str, Any]) -> str:
        """Save a run to database."""
        run_id = run_data.get("id")
        if not run_id:
            raise ValueError("Run must have an id")

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        import json
        data = json.dumps(run_data)

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs (id, workflow_id, status, data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM runs WHERE id = ?), ?), ?)""",
                (run_id, run_data.get("workflow_id"), run_data.get("status"), data, run_id, now, now)
            )

        logger.debug(f"Saved run: {run_id}")
        return run_id

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID."""
        with self._conn() as conn:
            row = conn.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row:
                import json
                return json.loads(row[0])
        return None

    async def list_runs(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List runs with optional filtering."""
        query = "SELECT data FROM runs WHERE 1=1"
        params = []

        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        import json
        runs = []
        with self._conn() as conn:
            for row in conn.execute(query, params):
                runs.append(json.loads(row[0]))
        return runs

    async def delete_run(self, run_id: str) -> bool:
        """Delete a run."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            return cursor.rowcount > 0