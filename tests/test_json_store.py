"""Tests for JsonStore file locking and atomic writes."""

import asyncio
import json
import os
import tempfile
import threading
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cray.storage.json_store import JsonStore


def _make_store(tmp_dir: str) -> JsonStore:
    """Create a JsonStore pointing at a temp directory."""
    return JsonStore(data_dir=tmp_dir)


def test_atomic_write_creates_valid_json():
    """Atomic write should produce valid JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("test-wf")
        store._atomic_write_json(path, {"name": "test-wf", "steps": []})
        with open(path, "r") as f:
            data = json.load(f)
        assert data["name"] == "test-wf"
        assert data["steps"] == []
        print("  ✅ atomic_write_creates_valid_json")


def test_atomic_write_no_partial_on_error():
    """If serialization fails, no file should be created at target path."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("bad-wf")

        # Use a type that fails even with default=str
        # We'll monkey-patch json.dumps to raise for this test
        import json as _json
        original_dumps = _json.dumps
        def _failing_dumps(*args, **kwargs):
            raise TypeError("simulated serialization failure")
        _json.dumps = _failing_dumps
        try:
            store._atomic_write_json(path, {"name": "bad"})
        except TypeError:
            pass
        finally:
            _json.dumps = original_dumps

        # Target file should NOT exist (no partial write)
        assert not path.exists(), "Partial file should not exist after failed write"
        print("  ✅ atomic_write_no_partial_on_error")


def test_read_json_returns_none_for_missing():
    """Reading a non-existent file returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("nonexistent")
        result = store._read_json(path)
        assert result is None
        print("  ✅ read_json_returns_none_for_missing")


def test_read_json_returns_none_for_corrupted():
    """Reading a corrupted JSON file returns None (not exception)."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("corrupt")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write invalid JSON
        with open(path, "w") as f:
            f.write("{invalid json!!!")
        result = store._read_json(path)
        assert result is None
        print("  ✅ read_json_returns_none_for_corrupted")


def test_concurrent_writes_no_corruption():
    """Multiple threads writing to the same file should not corrupt it."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("concurrent-wf")
        path.parent.mkdir(parents=True, exist_ok=True)

        errors = []
        num_writers = 10
        barrier = threading.Barrier(num_writers)

        def writer(idx):
            try:
                barrier.wait(timeout=5)
                store._atomic_write_json(path, {"writer": idx, "data": "x" * 100})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Writer errors: {errors}"

        # File should be valid JSON
        with open(path, "r") as f:
            data = json.load(f)
        assert "writer" in data
        assert isinstance(data["writer"], int)
        print(f"  ✅ concurrent_writes_no_corruption (last writer: {data['writer']})")


def test_concurrent_read_write():
    """Readers should get consistent data even while writers are active."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("rw-wf")
        # Initial write
        store._atomic_write_json(path, {"version": 0})

        read_errors = []
        num_readers = 5
        num_writers = 5
        stop_event = threading.Event()

        def reader():
            while not stop_event.is_set():
                result = store._read_json(path)
                if result is not None:
                    # Must be valid JSON with a version key
                    if "version" not in result:
                        read_errors.append(f"Missing version key: {result}")
                time.sleep(0.01)

        def writer(idx):
            for v in range(10):
                store._atomic_write_json(path, {"version": idx * 10 + v})
            stop_event.set()

        threads = (
            [threading.Thread(target=reader) for _ in range(num_readers)]
            + [threading.Thread(target=writer, args=(i,)) for i in range(num_writers)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not read_errors, f"Read errors: {read_errors}"
        # Final file should be valid
        with open(path, "r") as f:
            data = json.load(f)
        assert "version" in data
        print(f"  ✅ concurrent_read_write (final version: {data['version']})")


def test_delete_file_with_lock():
    """Delete should work with locking."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("del-wf")
        store._atomic_write_json(path, {"name": "del-wf"})
        assert path.exists()

        result = store._delete_file(path)
        assert result is True
        assert not path.exists()

        # Deleting non-existent returns False
        result = store._delete_file(path)
        assert result is False
        print("  ✅ delete_file_with_lock")


def test_lock_file_cleanup():
    """Lock files should be released after operations."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        path = store._workflow_path("lock-wf")
        store._atomic_write_json(path, {"name": "lock-wf"})

        lock_path = store._lock_path_for(path)
        # Lock file may or may not exist on disk (we create on demand)
        # But we should be able to acquire it again (no stale lock)
        store._acquire_lock(lock_path)
        store._release_lock(lock_path)
        print("  ✅ lock_file_cleanup")


def test_async_save_and_get_task():
    """Async save_task / get_task should work end-to-end."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)

        async def _test():
            task_id = await store.save_task({"id": "t1", "status": "running"})
            assert task_id == "t1"

            task = await store.get_task("t1")
            assert task is not None
            assert task["id"] == "t1"
            assert task["status"] == "running"

            # Missing task
            missing = await store.get_task("nonexistent")
            assert missing is None

        asyncio.run(_test())
        print("  ✅ async_save_and_get_task")


def test_async_save_and_get_workflow():
    """Async save_workflow / get_workflow should work end-to-end."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)

        async def _test():
            name = await store.save_workflow({"name": "wf1", "steps": [{"name": "s1"}]})
            assert name == "wf1"

            wf = await store.get_workflow("wf1")
            assert wf is not None
            assert wf["name"] == "wf1"

            names = await store.list_workflows()
            assert "wf1" in names

            deleted = await store.delete_workflow("wf1")
            assert deleted is True

            deleted2 = await store.delete_workflow("wf1")
            assert deleted2 is False

        asyncio.run(_test())
        print("  ✅ async_save_and_get_workflow")


def test_async_save_and_get_run():
    """Async save_run / get_run should work end-to-end."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)

        async def _test():
            run_id = await store.save_run({"id": "r1", "status": "success"})
            assert run_id == "r1"

            run = await store.get_run("r1")
            assert run is not None
            assert run["id"] == "r1"

            deleted = await store.delete_run("r1")
            assert deleted is True

        asyncio.run(_test())
        print("  ✅ async_save_and_get_run")


def test_list_tasks_with_filter():
    """list_tasks should filter by workflow_name and status."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)

        async def _test():
            await store.save_task({"id": "t1", "workflow_name": "wf-a", "status": "success"})
            await store.save_task({"id": "t2", "workflow_name": "wf-a", "status": "failed"})
            await store.save_task({"id": "t3", "workflow_name": "wf-b", "status": "success"})

            # Filter by workflow
            tasks = await store.list_tasks(workflow_name="wf-a")
            assert len(tasks) == 2

            # Filter by status
            tasks = await store.list_tasks(status="success")
            assert len(tasks) == 2

            # Filter by both
            tasks = await store.list_tasks(workflow_name="wf-a", status="success")
            assert len(tasks) == 1
            assert tasks[0]["id"] == "t1"

        asyncio.run(_test())
        print("  ✅ list_tasks_with_filter")


def test_list_tasks_offset_and_limit():
    """list_tasks offset/limit should work correctly after filtering."""
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)

        async def _test():
            for i in range(5):
                await store.save_task({"id": f"t{i}", "workflow_name": "wf", "status": "success"})

            # Limit
            tasks = await store.list_tasks(workflow_name="wf", limit=2)
            assert len(tasks) == 2

            # Offset
            tasks = await store.list_tasks(workflow_name="wf", offset=3)
            assert len(tasks) == 2  # 5 total - 3 offset = 2

        asyncio.run(_test())
        print("  ✅ list_tasks_offset_and_limit")


if __name__ == "__main__":
    print("Running JsonStore file-locking tests...")
    test_atomic_write_creates_valid_json()
    test_atomic_write_no_partial_on_error()
    test_read_json_returns_none_for_missing()
    test_read_json_returns_none_for_corrupted()
    test_concurrent_writes_no_corruption()
    test_concurrent_read_write()
    test_delete_file_with_lock()
    test_lock_file_cleanup()
    test_async_save_and_get_task()
    test_async_save_and_get_workflow()
    test_async_save_and_get_run()
    test_list_tasks_with_filter()
    test_list_tasks_offset_and_limit()
    print("\n✅ All tests passed!")
