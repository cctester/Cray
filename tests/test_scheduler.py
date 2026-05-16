"""Tests for Scheduler persistence (#12)."""

import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cray.core.workflow import Workflow, Step
from cray.scheduler import Scheduler


class TestSchedulerPersistence:
    """Tests for scheduler job persistence across restarts."""

    @pytest.fixture
    def persist_dir(self, tmp_path):
        """Create a temp directory for persist file."""
        return tmp_path / "scheduler_jobs.json"

    @pytest.fixture
    def scheduler(self, persist_dir):
        """Create scheduler with temp persist path."""
        return Scheduler(persist_path=str(persist_dir))

    @pytest.fixture
    def sample_workflow(self):
        """Create a sample workflow."""
        return Workflow(
            name="test-workflow",
            steps=[
                Step(
                    name="echo",
                    plugin="shell",
                    action="exec",
                    params={"command": "echo test"},
                )
            ],
        )

    @pytest.fixture
    def workflow_file(self, tmp_path, sample_workflow):
        """Write a sample workflow YAML file."""
        wf_path = tmp_path / "test-workflow.yaml"
        wf_path.write_text(
            "name: test-workflow\n"
            "steps:\n"
            "  - name: echo\n"
            "    plugin: shell\n"
            "    action: exec\n"
            "    params:\n"
            "      command: echo test\n"
        )
        return str(wf_path)

    @pytest.fixture
    def running_scheduler(self, scheduler):
        """Start the scheduler with an event loop, yield, then stop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scheduler._get_scheduler().start(paused=False)
            yield scheduler
        finally:
            scheduler.stop()
            loop.close()

    def test_save_jobs_creates_file(self, scheduler, persist_dir):
        """_save_jobs should create a persist file."""
        scheduler._jobs = {
            "job_1": {
                "workflow": "my-wf",
                "cron": "0 9 * * *",
                "interval_seconds": None,
                "workflow_file": "/tmp/my-wf.yaml",
                "created_at": "2026-01-01T00:00:00",
            }
        }
        scheduler._save_jobs()
        assert Path(persist_dir).exists()

    def test_save_jobs_writes_valid_json(self, scheduler, persist_dir):
        """Persist file should contain valid JSON."""
        scheduler._jobs = {
            "job_1": {
                "workflow": "my-wf",
                "cron": "0 9 * * *",
                "interval_seconds": None,
                "workflow_file": "/tmp/my-wf.yaml",
                "created_at": "2026-01-01T00:00:00",
            }
        }
        scheduler._save_jobs()
        data = json.loads(Path(persist_dir).read_text())
        assert "job_1" in data
        assert data["job_1"]["workflow"] == "my-wf"
        assert data["job_1"]["cron"] == "0 9 * * *"

    def test_save_jobs_excludes_non_serializable(self, scheduler, persist_dir):
        """Persist file should not include the live APScheduler job object."""
        scheduler._jobs = {
            "job_1": {
                "job": MagicMock(),
                "workflow": "my-wf",
                "cron": None,
                "interval_seconds": 60,
                "workflow_file": "/tmp/my-wf.yaml",
                "created_at": "2026-01-01T00:00:00",
            }
        }
        scheduler._save_jobs()
        data = json.loads(Path(persist_dir).read_text())
        assert "job" not in data["job_1"]
        assert data["job_1"]["interval_seconds"] == 60

    def test_load_jobs_empty_file(self, scheduler, persist_dir):
        """_load_jobs should return empty dict if no persist file."""
        result = scheduler._load_jobs()
        assert result == {}

    def test_load_jobs_valid_file(self, scheduler, persist_dir):
        """_load_jobs should read valid JSON from persist file."""
        data = {
            "job_1": {
                "workflow": "my-wf",
                "cron": "0 9 * * *",
                "interval_seconds": None,
                "workflow_file": "/tmp/my-wf.yaml",
                "created_at": "2026-01-01T00:00:00",
            }
        }
        Path(persist_dir).write_text(json.dumps(data))
        result = scheduler._load_jobs()
        assert "job_1" in result
        assert result["job_1"]["workflow"] == "my-wf"

    def test_load_jobs_corrupt_file(self, scheduler, persist_dir):
        """_load_jobs should return empty dict for corrupt JSON."""
        Path(persist_dir).write_text("NOT VALID JSON {{{")
        result = scheduler._load_jobs()
        assert result == {}

    def test_load_jobs_non_dict_file(self, scheduler, persist_dir):
        """_load_jobs should return empty dict if JSON root is not a dict."""
        Path(persist_dir).write_text(json.dumps([1, 2, 3]))
        result = scheduler._load_jobs()
        assert result == {}

    def test_schedule_workflow_persists(
        self, running_scheduler, sample_workflow, workflow_file, persist_dir
    ):
        """schedule_workflow should auto-persist after adding a job."""
        running_scheduler.schedule_workflow(
            sample_workflow,
            cron="0 9 * * *",
            workflow_file=workflow_file,
        )
        assert Path(persist_dir).exists()
        data = json.loads(Path(persist_dir).read_text())
        assert len(data) == 1

    def test_unschedule_persists(
        self, running_scheduler, sample_workflow, workflow_file, persist_dir
    ):
        """unschedule should update persist file after removal."""
        job_id = running_scheduler.schedule_workflow(
            sample_workflow,
            cron="0 9 * * *",
            workflow_file=workflow_file,
        )
        assert len(json.loads(Path(persist_dir).read_text())) == 1

        running_scheduler.unschedule(job_id)
        data = json.loads(Path(persist_dir).read_text())
        assert len(data) == 0

    def test_restore_jobs_on_start(self, persist_dir, workflow_file):
        """Jobs should be restored when a new Scheduler starts."""
        loop1 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop1)
        s1 = Scheduler(persist_path=str(persist_dir))
        try:
            s1.start()
            s1.schedule_workflow(
                Workflow(
                    name="test-workflow",
                    steps=[
                        Step(
                            name="echo",
                            plugin="shell",
                            action="exec",
                            params={"command": "echo test"},
                        )
                    ],
                ),
                cron="0 9 * * *",
                workflow_file=workflow_file,
            )
            assert len(s1._jobs) == 1
        finally:
            s1.stop()
            loop1.close()

        # Second scheduler: should restore the job
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        s2 = Scheduler(persist_path=str(persist_dir))
        try:
            s2.start()
            assert len(s2._jobs) == 1
            job_info = list(s2._jobs.values())[0]
            assert job_info["workflow"] == "test-workflow"
            assert job_info["cron"] == "0 9 * * *"
        finally:
            s2.stop()
            loop2.close()

    def test_restore_skips_missing_workflow_file(self, persist_dir):
        """Restore should skip jobs whose workflow file doesn't exist."""
        data = {
            "job_ghost": {
                "workflow": "ghost-wf",
                "cron": "0 9 * * *",
                "interval_seconds": None,
                "workflow_file": "/nonexistent/ghost.yaml",
                "created_at": "2026-01-01T00:00:00",
            }
        }
        Path(persist_dir).write_text(json.dumps(data))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        s = Scheduler(persist_path=str(persist_dir))
        try:
            s.start()
            assert len(s._jobs) == 0
        finally:
            s.stop()
            loop.close()

    def test_restore_skips_job_without_workflow_file(self, persist_dir):
        """Restore should skip jobs with no workflow_file recorded."""
        data = {
            "job_no_file": {
                "workflow": "no-file-wf",
                "cron": "0 9 * * *",
                "interval_seconds": None,
                "workflow_file": None,
                "created_at": "2026-01-01T00:00:00",
            }
        }
        Path(persist_dir).write_text(json.dumps(data))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        s = Scheduler(persist_path=str(persist_dir))
        try:
            s.start()
            assert len(s._jobs) == 0
        finally:
            s.stop()
            loop.close()

    def test_persist_path_created_on_init(self, tmp_path):
        """Scheduler init should create parent directory for persist file."""
        persist = tmp_path / "deep" / "nested" / "jobs.json"
        s = Scheduler(persist_path=str(persist))
        assert persist.parent.exists()

    def test_list_jobs_includes_persist_fields(
        self, running_scheduler, sample_workflow, workflow_file
    ):
        """list_jobs should include workflow_file and created_at."""
        job_id = running_scheduler.schedule_workflow(
            sample_workflow,
            cron="0 9 * * *",
            workflow_file=workflow_file,
        )
        jobs = running_scheduler.list_jobs()
        assert jobs[job_id]["workflow_file"] == workflow_file
        assert jobs[job_id]["created_at"] is not None

    def test_schedule_interval_persists(
        self, running_scheduler, sample_workflow, workflow_file, persist_dir
    ):
        """Interval-based jobs should also be persisted correctly."""
        running_scheduler.schedule_workflow(
            sample_workflow,
            interval_seconds=3600,
            workflow_file=workflow_file,
        )
        data = json.loads(Path(persist_dir).read_text())
        job_data = list(data.values())[0]
        assert job_data["interval_seconds"] == 3600
        assert job_data["cron"] is None

    def test_replace_existing_job_persists(
        self, running_scheduler, sample_workflow, workflow_file, persist_dir
    ):
        """Re-scheduling same job_id should update persist file."""
        running_scheduler.schedule_workflow(
            sample_workflow,
            cron="0 9 * * *",
            job_id="my-job",
            workflow_file=workflow_file,
        )
        running_scheduler.schedule_workflow(
            sample_workflow,
            cron="0 12 * * *",
            job_id="my-job",
            workflow_file=workflow_file,
        )
        data = json.loads(Path(persist_dir).read_text())
        assert len(data) == 1
        assert data["my-job"]["cron"] == "0 12 * * *"


class TestSchedulerBasic:
    """Basic scheduler operations still work after persistence changes."""

    def test_scheduler_creation(self):
        scheduler = Scheduler()
        assert scheduler is not None
        assert scheduler._scheduler is None

    def test_list_jobs_empty(self):
        scheduler = Scheduler()
        jobs = scheduler.list_jobs()
        assert jobs == {}

    def test_parse_cron_valid(self):
        scheduler = Scheduler()
        result = scheduler._parse_cron("0 9 * * *")
        assert result == {
            "minute": "0",
            "hour": "9",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_parse_cron_invalid(self):
        scheduler = Scheduler()
        with pytest.raises(ValueError, match="Invalid cron"):
            scheduler._parse_cron("0 9 * *")
