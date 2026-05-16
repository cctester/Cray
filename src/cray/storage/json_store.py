"""
JSON file-based storage backend with file locking and atomic writes.
"""

import json
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from cray.storage.base import StorageBackend


# ── Cross-platform file locking ────────────────────────────────────

if sys.platform == "win32":
    import msvcrt

    def _flock_exclusive(fd: int) -> None:
        """Acquire exclusive lock (blocking)."""
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 2**31 - 1)
                return
            except OSError:
                time.sleep(0.01)

    def _flock_shared(fd: int) -> None:
        """Acquire shared lock (blocking)."""
        # LK_RLOCK is shared lock; it may not exist in older Python.
        # When in doubt, use LK_LOCK (also exclusive on Windows fallback).
        try:
            msvcrt.locking(fd, msvcrt.LK_RLOCK, 2**31 - 1)
        except AttributeError:
            _flock_exclusive(fd)

    def _funlock(fd: int) -> None:
        """Unlock."""
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 2**31 - 1)
        except OSError:
            pass

else:
    import fcntl

    def _flock_exclusive(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _flock_shared(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_SH)

    def _funlock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


class JsonStore(StorageBackend):
    """
    JSON file-based storage.

    Stores tasks, workflows, and runs in JSON files.
    Uses file locking (fcntl.flock) to prevent concurrent write corruption
    and atomic writes (write-to-temp + rename) to prevent partial writes.
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(os.path.expanduser(data_dir))
        self.tasks_dir = self.data_dir / "tasks"
        self.workflows_dir = self.data_dir / "workflows"
        self.runs_dir = self.data_dir / "runs"

        # Create directories
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[JsonStore] initialized at {self.data_dir}")

    # ── Locking & Atomic I/O helpers ──────────────────────────────────

    # Registry mapping lock-file paths to their open file descriptors.
    # Key = str(lock_path) so it works across different Path instances.
    _lock_registry: Dict[str, "io.IOBase"] = {}

    @classmethod
    def _acquire_lock(cls, lock_path: Path, exclusive: bool = True) -> None:
        """Block until a lock on lock_path is obtained."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = open(lock_path, "wb")
        if exclusive:
            _flock_exclusive(lock_fd.fileno())
        else:
            _flock_shared(lock_fd.fileno())
        cls._lock_registry[str(lock_path)] = lock_fd

    @classmethod
    def _release_lock(cls, lock_path: Path) -> None:
        """Release a previously acquired lock."""
        key = str(lock_path)
        lock_fd = cls._lock_registry.pop(key, None)
        if lock_fd is not None:
            try:
                _funlock(lock_fd.fileno())
            except OSError:
                pass
            lock_fd.close()

    def _lock_path_for(self, target_path: Path) -> Path:
        """Return the .lock file path corresponding to a data file."""
        return target_path.with_suffix(target_path.suffix + ".lock")

    def _atomic_write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """
        Write JSON data atomically.

        1. Serialize data to JSON first (fail fast if unserializable)
        2. Acquire an exclusive lock file
        3. Write to a temp file in the same directory
        4. os.replace (atomic rename) to the target
        5. Release the lock
        """
        # Serialize upfront so we fail before touching the filesystem
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")

        lock_path = self._lock_path_for(path)
        try:
            self._acquire_lock(lock_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write to temp file in same directory (same filesystem for atomic rename)
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=path.stem + "_",
                dir=path.parent,
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(json_bytes)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, str(path))
            except BaseException:
                # Clean up temp file on any error
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        finally:
            self._release_lock(lock_path)

    def _read_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """
        Read JSON data with a shared lock.

        Returns None if the file doesn't exist or is corrupted.
        """
        if not path.exists():
            return None
        lock_path = self._lock_path_for(path)
        try:
            self._acquire_lock(lock_path, exclusive=False)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[JsonStore] corrupted file {path}: {e}")
                return None
            finally:
                self._release_lock(lock_path)
        except OSError as e:
            logger.warning(f"[JsonStore] could not acquire read lock for {path}: {e}")
            # Fallback: read without lock rather than failing
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None

    def _delete_file(self, path: Path) -> bool:
        """Delete a file with exclusive lock."""
        if not path.exists():
            return False
        lock_path = self._lock_path_for(path)
        try:
            self._acquire_lock(lock_path)
            path.unlink()
            logger.debug(f"[JsonStore] deleted {path}")
            return True
        except OSError as e:
            logger.warning(f"[JsonStore] failed to delete {path}: {e}")
            return False
        finally:
            self._release_lock(lock_path)

    # ── Path helpers ──────────────────────────────────────────────────

    def _task_path(self, task_id: str) -> Path:
        """Get path for a task file."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.tasks_dir / today / f"{task_id}.json"

    def _workflow_path(self, name: str) -> Path:
        """Get path for a workflow file."""
        return self.workflows_dir / f"{name}.json"

    def _run_path(self, run_id: str) -> Path:
        """Get path for a run file."""
        return self.runs_dir / f"{run_id}.json"

    # ── Task operations ───────────────────────────────────────────────

    async def save_task(self, task_data: Dict[str, Any]) -> str:
        """Save a task to JSON file."""
        task_id = task_data.get("id")
        if not task_id:
            raise ValueError("Task must have an id")

        path = self._task_path(task_id)

        def _write():
            self._atomic_write_json(path, task_data)

        await asyncio.get_running_loop().run_in_executor(None, _write)
        logger.debug(f"Saved task: {task_id}")
        return task_id

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        # Search in date directories (newest first)
        def _read():
            for date_dir in sorted(self.tasks_dir.iterdir(), reverse=True):
                if date_dir.is_dir():
                    task_file = date_dir / f"{task_id}.json"
                    result = self._read_json(task_file)
                    if result is not None:
                        return result
            return None

        return await asyncio.get_running_loop().run_in_executor(None, _read)

    async def list_tasks(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering."""
        def _list():
            tasks: List[Dict[str, Any]] = []
            # Collect all task files (newest first)
            task_files = []
            for date_dir in sorted(self.tasks_dir.iterdir(), reverse=True):
                if date_dir.is_dir():
                    task_files.extend(
                        sorted(date_dir.glob("*.json"), reverse=True)
                    )

            # Load and filter — apply offset/limit AFTER filtering
            matched = 0
            skipped = 0
            for task_file in task_files:
                task = self._read_json(task_file)
                if task is None:
                    continue
                # Apply filters
                if workflow_name and task.get("workflow_name") != workflow_name:
                    continue
                if status and task.get("status") != status:
                    continue
                # Apply offset
                if skipped < offset:
                    skipped += 1
                    continue
                tasks.append(task)
                matched += 1
                if matched >= limit:
                    break
            return tasks

        return await asyncio.get_running_loop().run_in_executor(None, _list)

    # ── Workflow operations ───────────────────────────────────────────

    async def save_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """Save a workflow to JSON file."""
        name = workflow_data.get("name")
        if not name:
            raise ValueError("Workflow must have a name")

        path = self._workflow_path(name)

        def _write():
            self._atomic_write_json(path, workflow_data)

        await asyncio.get_running_loop().run_in_executor(None, _write)
        logger.debug(f"Saved workflow: {name}")
        return name

    async def get_workflow(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow by name."""
        path = self._workflow_path(name)

        def _read():
            return self._read_json(path)

        return await asyncio.get_running_loop().run_in_executor(None, _read)

    async def list_workflows(self) -> List[str]:
        """List all workflow names."""
        def _list():
            return [f.stem for f in self.workflows_dir.glob("*.json")]

        return await asyncio.get_running_loop().run_in_executor(None, _list)

    async def delete_workflow(self, name: str) -> bool:
        """Delete a workflow."""
        path = self._workflow_path(name)

        def _delete():
            return self._delete_file(path)

        return await asyncio.get_running_loop().run_in_executor(None, _delete)

    # ── Run operations ────────────────────────────────────────────────

    async def save_run(self, run_data: Dict[str, Any]) -> str:
        """Save a run to JSON file."""
        run_id = run_data.get("id")
        if not run_id:
            raise ValueError("Run must have an id")

        path = self._run_path(run_id)

        def _write():
            self._atomic_write_json(path, run_data)

        await asyncio.get_running_loop().run_in_executor(None, _write)
        logger.debug(f"Saved run: {run_id}")
        return run_id

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID."""
        path = self._run_path(run_id)

        def _read():
            return self._read_json(path)

        return await asyncio.get_running_loop().run_in_executor(None, _read)

    async def list_runs(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List runs with optional filtering."""
        def _list():
            runs: List[Dict[str, Any]] = []
            run_files = sorted(self.runs_dir.glob("*.json"), reverse=True)

            matched = 0
            skipped = 0
            for run_file in run_files:
                run = self._read_json(run_file)
                if run is None:
                    continue
                if workflow_id and run.get("workflow_id") != workflow_id:
                    continue
                if status and run.get("status") != status:
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                runs.append(run)
                matched += 1
                if matched >= limit:
                    break
            return runs

        return await asyncio.get_running_loop().run_in_executor(None, _list)

    async def delete_run(self, run_id: str) -> bool:
        """Delete a run."""
        path = self._run_path(run_id)

        def _delete():
            return self._delete_file(path)

        return await asyncio.get_running_loop().run_in_executor(None, _delete)
