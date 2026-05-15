"""Tests for workflow versioning system, including migration (#17)."""

import json
import hashlib
import tempfile
from pathlib import Path

import pytest

from cray.core.versioning import (
    WorkflowVersionManager,
    WorkflowVersion,
    SCHEMA_VERSION,
    MIGRATIONS,
    _MIGRATION_MAP,
)


class TestWorkflowVersion:
    """Tests for WorkflowVersion dataclass."""

    def test_to_dict_includes_checksum(self):
        v = WorkflowVersion(
            version_id="v1.0.0",
            workflow_name="test",
            content="hello",
            content_hash="abc",
            created_at="2026-01-01",
        )
        d = v.to_dict()
        assert d["content_checksum"] != ""
        # Should be sha256 of "hello"[:16]
        expected = hashlib.sha256(b"hello").hexdigest()[:16]
        assert d["content_checksum"] == expected

    def test_verify_checksum_valid(self):
        content = "my workflow"
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        v = WorkflowVersion(
            version_id="v1.0.0",
            workflow_name="test",
            content=content,
            content_hash="abc",
            created_at="2026-01-01",
            content_checksum=checksum,
        )
        assert v.verify_checksum() is True

    def test_verify_checksum_invalid(self):
        v = WorkflowVersion(
            version_id="v1.0.0",
            workflow_name="test",
            content="my workflow",
            content_hash="abc",
            created_at="2026-01-01",
            content_checksum="wrong_checksum",
        )
        assert v.verify_checksum() is False

    def test_verify_checksum_legacy_no_field(self):
        """Legacy versions without content_checksum should pass verification."""
        v = WorkflowVersion(
            version_id="v1.0.0",
            workflow_name="test",
            content="my workflow",
            content_hash="abc",
            created_at="2026-01-01",
            content_checksum="",
        )
        assert v.verify_checksum() is True

    def test_from_dict_ignores_unknown_keys(self):
        data = {
            "version_id": "v1.0.0",
            "workflow_name": "test",
            "content": "hello",
            "content_hash": "abc",
            "created_at": "2026-01-01",
            "unknown_future_field": "value",
        }
        v = WorkflowVersion.from_dict(data)
        assert v.version_id == "v1.0.0"
        assert not hasattr(v, "unknown_future_field")


class TestMigration:
    """Tests for schema migration system (#17)."""

    def _create_v1_workflow(self, storage_dir: Path, wf_name: str) -> Path:
        """Create a v1 (legacy) workflow directory with no schema_version."""
        wf_dir = storage_dir / wf_name
        wf_dir.mkdir(parents=True)

        # v1 index — no schema_version field
        index = {"versions": ["v1.0.0"], "current": "v1.0.0"}
        (wf_dir / "index.json").write_text(json.dumps(index))

        # v1 version file — no schema_version or content_checksum
        version_data = {
            "version_id": "v1.0.0",
            "workflow_name": wf_name,
            "content": "steps:\n  - name: hello\n    action: echo",
            "content_hash": "abc123",
            "created_at": "2025-01-01T00:00:00",
            "author": "test",
            "message": "initial",
            "tags": [],
            "parent_version": None,
        }
        (wf_dir / "v1.0.0.json").write_text(json.dumps(version_data))
        return wf_dir

    def test_migration_adds_schema_version_to_index(self):
        """Migration should add schema_version to index.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            # Initializing the manager triggers migration
            vm = WorkflowVersionManager(storage_path=str(storage))

            index = json.loads((storage / "my-wf" / "index.json").read_text())
            assert index["schema_version"] == SCHEMA_VERSION

    def test_migration_adds_schema_version_to_version_file(self):
        """Migration should add schema_version to version JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            vm = WorkflowVersionManager(storage_path=str(storage))

            vdata = json.loads(
                (storage / "my-wf" / "v1.0.0.json").read_text()
            )
            assert vdata["schema_version"] == SCHEMA_VERSION

    def test_migration_adds_content_checksum(self):
        """Migration v1→v2 should add content_checksum."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            vm = WorkflowVersionManager(storage_path=str(storage))

            vdata = json.loads(
                (storage / "my-wf" / "v1.0.0.json").read_text()
            )
            assert "content_checksum" in vdata
            # Verify the checksum is correct
            content = "steps:\n  - name: hello\n    action: echo"
            expected = hashlib.sha256(content.encode()).hexdigest()[:16]
            assert vdata["content_checksum"] == expected

    def test_migration_creates_backup(self):
        """Migration should create backup files before modifying data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            vm = WorkflowVersionManager(storage_path=str(storage))

            wf_dir = storage / "my-wf"
            # Should have backup files for v2 migration
            backup_index = wf_dir / "index.json.migration_backup_v2"
            assert backup_index.exists()

            backup_version = wf_dir / "v1.0.0.json.migration_backup_v2"
            assert backup_version.exists()

            # Backup should still have original data (no schema_version)
            orig_index = json.loads(backup_index.read_text())
            assert "schema_version" not in orig_index

    def test_migration_idempotent(self):
        """Re-initializing manager on already-migrated data should be a no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            # First migration
            vm1 = WorkflowVersionManager(storage_path=str(storage))
            vdata1 = json.loads(
                (storage / "my-wf" / "v1.0.0.json").read_text()
            )

            # Second initialization — should not re-migrate
            vm2 = WorkflowVersionManager(storage_path=str(storage))
            vdata2 = json.loads(
                (storage / "my-wf" / "v1.0.0.json").read_text()
            )

            assert vdata1 == vdata2

    def test_migration_preserves_content(self):
        """Migration must not alter workflow content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            original_content = "steps:\n  - name: hello\n    action: echo"

            vm = WorkflowVersionManager(storage_path=str(storage))

            vdata = json.loads(
                (storage / "my-wf" / "v1.0.0.json").read_text()
            )
            assert vdata["content"] == original_content

    def test_new_save_includes_schema_version(self):
        """Newly saved versions should include schema_version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = WorkflowVersionManager(storage_path=str(tmpdir))
            vm.save_version("test-wf", "content: hello", message="init")

            wf_dir = Path(tmpdir) / "test-wf"
            index = json.loads((wf_dir / "index.json").read_text())
            assert index["schema_version"] == SCHEMA_VERSION

            # Find the version file
            version_files = list(wf_dir.glob("v*.json"))
            assert len(version_files) == 1
            vdata = json.loads(version_files[0].read_text())
            assert vdata["schema_version"] == SCHEMA_VERSION

    def test_get_version_verifies_checksum(self):
        """get_version should warn on checksum mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "my-wf")

            vm = WorkflowVersionManager(storage_path=str(storage))

            # Tamper with content after migration
            vdata = json.loads(
                (storage / "my-wf" / "v1.0.0.json").read_text()
            )
            vdata["content"] = "TAMPERED CONTENT"
            (storage / "my-wf" / "v1.0.0.json").write_text(
                json.dumps(vdata)
            )

            # get_version should still return the version but log a warning
            # (we can't easily test the log, but we can test verify_checksum)
            version = vm.get_version("my-wf", "v1.0.0")
            assert version is not None
            assert version.verify_checksum() is False

    def test_multiple_workflows_migrated(self):
        """All workflows in storage should be migrated on init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            self._create_v1_workflow(storage, "wf-alpha")
            self._create_v1_workflow(storage, "wf-beta")

            vm = WorkflowVersionManager(storage_path=str(storage))

            for wf_name in ["wf-alpha", "wf-beta"]:
                index = json.loads(
                    (storage / wf_name / "index.json").read_text()
                )
                assert index["schema_version"] == SCHEMA_VERSION

    def test_migration_chain_completeness(self):
        """Verify migration chain covers all versions from 1 to SCHEMA_VERSION."""
        # We should be able to reach SCHEMA_VERSION from version 1
        current = 1
        visited = set()
        while current < SCHEMA_VERSION:
            assert current not in visited, f"Circular migration at v{current}"
            visited.add(current)
            migration = _MIGRATION_MAP.get(current)
            assert migration is not None, (
                f"No migration from v{current} to v{current + 1}"
            )
            assert migration.to_version > current
            current = migration.to_version
        assert current == SCHEMA_VERSION


class TestVersionManagerBasic:
    """Basic version manager operations still work after migration changes."""

    def test_save_and_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = WorkflowVersionManager(storage_path=str(tmpdir))
            vm.save_version("wf", "content: v1", message="first")
            vm.save_version("wf", "content: v2", message="second")

            versions = vm.list_versions("wf")
            assert len(versions) == 2
            assert versions[0].version_id == "v1.0.1"
            assert versions[1].version_id == "v1.0.0"

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = WorkflowVersionManager(storage_path=str(tmpdir))
            vm.save_version("wf", "content: v1", message="first")
            vm.save_version("wf", "content: v2", message="second")

            result = vm.rollback("wf", "v1.0.0", workflows_dir=tmpdir)
            assert result is True

    def test_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = WorkflowVersionManager(storage_path=str(tmpdir))
            vm.save_version("wf", "line1\nline2", message="first")
            vm.save_version("wf", "line1\nline3", message="second")

            diff = vm.diff("wf", "v1.0.0", "v1.0.1")
            assert diff is not None
            assert diff.deletions > 0 or diff.additions > 0

    def test_tag_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = WorkflowVersionManager(storage_path=str(tmpdir))
            vm.save_version("wf", "content", message="first")

            result = vm.tag_version("wf", "v1.0.0", "release")
            assert result is True

            version = vm.get_version("wf", "v1.0.0")
            assert "release" in version.tags

    def test_delete_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = WorkflowVersionManager(storage_path=str(tmpdir))
            vm.save_version("wf", "content: v1", message="first")
            vm.save_version("wf", "content: v2", message="second")

            result = vm.delete_version("wf", "v1.0.1")
            assert result is True

            versions = vm.list_versions("wf")
            assert len(versions) == 1
