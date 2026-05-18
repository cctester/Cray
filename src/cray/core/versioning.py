"""
Workflow versioning system for Cray.

Features:
- Track workflow changes over time
- Rollback to previous versions
- Compare versions (diff)
- Tag versions for releases
"""

import json
import shutil
import hashlib
import difflib
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from loguru import logger


# Current schema version — bump when introducing breaking format changes
SCHEMA_VERSION = 2


@dataclass
class Migration:
    """A single migration step from one schema version to the next."""
    from_version: int
    to_version: int
    description: str
    migrate_version_file: Callable[[Dict[str, Any]], Dict[str, Any]]
    migrate_index_file: Callable[[Dict[str, Any]], Dict[str, Any]]


# ── Migration definitions ────────────────────────────────────────────

def _v1_to_v2_version(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a version file from schema v1 to v2.

    v1 had no schema_version field and no checksum validation.
    v2 adds schema_version and content_checksum.
    """
    data["schema_version"] = 2
    # Recompute content_checksum from content if missing
    if "content_checksum" not in data and "content" in data:
        data["content_checksum"] = hashlib.sha256(
            data["content"].encode()
        ).hexdigest()[:16]
    return data


def _v1_to_v2_index(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate an index file from schema v1 to v2.

    v2 adds schema_version to the index.
    """
    data["schema_version"] = 2
    return data


MIGRATIONS: List[Migration] = [
    Migration(
        from_version=1,
        to_version=2,
        description="Add schema_version and content_checksum fields",
        migrate_version_file=_v1_to_v2_version,
        migrate_index_file=_v1_to_v2_index,
    ),
]


def _build_migration_chain() -> Dict[int, Migration]:
    """Build a lookup from -> migration for quick access."""
    return {m.from_version: m for m in MIGRATIONS}


_MIGRATION_MAP = _build_migration_chain()


@dataclass
class WorkflowVersion:
    """Represents a single version of a workflow."""
    version_id: str
    workflow_name: str
    content: str
    content_hash: str
    created_at: str
    author: str = ""
    message: str = ""
    tags: List[str] = field(default_factory=list)
    parent_version: Optional[str] = None
    schema_version: int = SCHEMA_VERSION
    content_checksum: str = ""  # SHA-256 checksum for integrity verification

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.version_id and not isinstance(self.version_id, str):
            raise ValueError(f"version_id must be a string, got {type(self.version_id).__name__}")
        if self.version_id and not self.version_id.strip():
            raise ValueError("version_id must not be empty or whitespace-only")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        # Ensure content_checksum is populated
        if not d.get("content_checksum") and d.get("content"):
            d["content_checksum"] = hashlib.sha256(
                d["content"].encode()
            ).hexdigest()[:16]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowVersion":
        """Create from dictionary. Ignores unknown keys for forward compatibility."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def verify_checksum(self) -> bool:
        """Verify that content_checksum matches the actual content.

        Returns True if checksum is valid or was not set (legacy data).
        """
        if not self.content_checksum:
            # Legacy version without checksum — can't verify but not invalid
            return True
        actual = hashlib.sha256(self.content.encode()).hexdigest()[:16]
        return actual == self.content_checksum


@dataclass
class VersionDiff:
    """Difference between two workflow versions."""
    from_version: str
    to_version: str
    additions: int
    deletions: int
    changes: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions


class WorkflowVersionManager:
    """
    Manages workflow version history.
    
    Usage:
        vm = WorkflowVersionManager()
        
        # Save a new version
        vm.save_version("my-workflow", yaml_content, message="Added new step")
        
        # List versions
        versions = vm.list_versions("my-workflow")
        
        # Rollback
        vm.rollback("my-workflow", "v1.2.0")
        
        # Compare versions
        diff = vm.diff("my-workflow", "v1.0.0", "v1.1.0")
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize version manager.

        Args:
            storage_path: Path to store version history
        """
        self.storage_path = Path(storage_path or "~/.cray/versions")
        self.storage_path = self.storage_path.expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._migrate_all_workflows()

    def _migrate_all_workflows(self) -> None:
        """Run pending migrations for all stored workflows."""
        if not self.storage_path.exists():
            return

        for wf_dir in self.storage_path.iterdir():
            if wf_dir.is_dir():
                try:
                    self._migrate_workflow(wf_dir)
                except Exception as e:
                    logger.error(
                        f"Migration failed for '{wf_dir.name}': {e}"
                    )

    def _migrate_workflow(self, wf_dir: Path) -> None:
        """Migrate a single workflow's data to the current schema version.

        Reads the schema_version from the index file (defaults to 1 for
        legacy data with no schema_version field), then applies migrations
        sequentially until the current SCHEMA_VERSION is reached.

        Each migration transforms version JSON files and the index file.
        A backup of the pre-migration state is saved as
        .migration_backup_<to_version>.json for each step.
        """
        index_file = wf_dir / "index.json"
        if not index_file.exists():
            # No index yet — will be created on first save_version
            return

        index_data = json.loads(index_file.read_text())
        current_sv = index_data.get("schema_version", 1)

        if current_sv >= SCHEMA_VERSION:
            return  # Already up to date

        logger.info(
            f"Migrating '{wf_dir.name}' from schema v{current_sv} "
            f"to v{SCHEMA_VERSION}"
        )

        while current_sv < SCHEMA_VERSION:
            migration = _MIGRATION_MAP.get(current_sv)
            if migration is None:
                logger.error(
                    f"No migration path from schema v{current_sv} "
                    f"for '{wf_dir.name}'. Stopping."
                )
                break

            # ── Backup before migration ──
            backup_suffix = f".migration_backup_v{migration.to_version}"
            # Backup index
            shutil.copy2(
                index_file,
                wf_dir / f"index.json{backup_suffix}",
            )

            # ── Migrate index ──
            index_data = migration.migrate_index_file(index_data)
            current_sv = migration.to_version
            index_data["schema_version"] = current_sv
            index_file.write_text(json.dumps(index_data, indent=2))

            # ── Migrate each version file ──
            for version_id in index_data.get("versions", []):
                version_file = wf_dir / f"{version_id}.json"
                if not version_file.exists():
                    continue
                # Backup version file
                shutil.copy2(
                    version_file,
                    wf_dir / f"{version_id}.json{backup_suffix}",
                )
                vdata = json.loads(version_file.read_text())
                vdata = migration.migrate_version_file(vdata)
                version_file.write_text(json.dumps(vdata, indent=2))

            logger.info(
                f"  Applied migration v{migration.from_version} → "
                f"v{migration.to_version}: {migration.description}"
            )

        logger.info(
            f"Migration complete for '{wf_dir.name}', "
            f"now at schema v{current_sv}"
        )
    
    def _get_workflow_dir(self, workflow_name: str) -> Path:
        """Get the version directory for a workflow."""
        wf_dir = self.storage_path / workflow_name
        wf_dir.mkdir(parents=True, exist_ok=True)
        return wf_dir
    
    def _compute_hash(self, content: str) -> str:
        """Compute content hash."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _generate_version_id(self, workflow_name: str) -> str:
        """Generate a new version ID."""
        versions = self.list_versions(workflow_name)
        if not versions:
            return "v1.0.0"
        
        # Increment patch version
        last_version = versions[0].version_id
        parts = last_version.lstrip("v").split(".")
        if len(parts) == 3:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return f"v{major}.{minor}.{patch + 1}"
        
        return f"v{len(versions) + 1}.0.0"
    
    def save_version(
        self,
        workflow_name: str,
        content: str,
        message: str = "",
        author: str = "",
        tags: Optional[List[str]] = None
    ) -> WorkflowVersion:
        """
        Save a new version of a workflow.
        
        Args:
            workflow_name: Name of the workflow
            content: Workflow YAML content
            message: Commit message
            author: Author name
            tags: Optional tags for this version
            
        Returns:
            The created version
        """
        wf_dir = self._get_workflow_dir(workflow_name)
        
        # Check if content changed
        content_hash = self._compute_hash(content)
        versions = self.list_versions(workflow_name)
        
        if versions and versions[0].content_hash == content_hash:
            logger.info(f"No changes detected for workflow '{workflow_name}'")
            return versions[0]
        
        # Create new version
        version_id = self._generate_version_id(workflow_name)
        parent = versions[0].version_id if versions else None
        
        version = WorkflowVersion(
            version_id=version_id,
            workflow_name=workflow_name,
            content=content,
            content_hash=content_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
            author=author,
            message=message,
            tags=tags or [],
            parent_version=parent
        )
        
        # Save version file
        version_file = wf_dir / f"{version_id}.json"
        version_dict = version.to_dict()
        version_dict["schema_version"] = SCHEMA_VERSION
        version_file.write_text(json.dumps(version_dict, indent=2))
        version_file.chmod(0o600)
        
        # Update index
        self._update_index(workflow_name, version)
        
        logger.info(f"Saved version {version_id} for workflow '{workflow_name}'")
        return version
    
    def _update_index(self, workflow_name: str, version: WorkflowVersion) -> None:
        """Update the version index for a workflow."""
        wf_dir = self._get_workflow_dir(workflow_name)
        index_file = wf_dir / "index.json"

        if index_file.exists():
            index = json.loads(index_file.read_text())
        else:
            index = {"versions": [], "current": None, "schema_version": SCHEMA_VERSION}

        # Add to front of list (newest first)
        if version.version_id not in index["versions"]:
            index["versions"].insert(0, version.version_id)

        index["current"] = version.version_id
        index["schema_version"] = SCHEMA_VERSION
        index_file.write_text(json.dumps(index, indent=2))
    
    def list_versions(self, workflow_name: str) -> List[WorkflowVersion]:
        """
        List all versions of a workflow.
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            List of versions, newest first
        """
        wf_dir = self._get_workflow_dir(workflow_name)
        index_file = wf_dir / "index.json"
        
        if not index_file.exists():
            return []
        
        index = json.loads(index_file.read_text())
        versions = []
        
        for version_id in index.get("versions", []):
            version_file = wf_dir / f"{version_id}.json"
            if version_file.exists():
                data = json.loads(version_file.read_text())
                versions.append(WorkflowVersion.from_dict(data))
        
        return versions
    
    def get_version(
        self,
        workflow_name: str,
        version_id: str
    ) -> Optional[WorkflowVersion]:
        """
        Get a specific version of a workflow.

        Args:
            workflow_name: Name of the workflow
            version_id: Version ID to get

        Returns:
            The version or None if not found
        """
        wf_dir = self._get_workflow_dir(workflow_name)
        version_file = wf_dir / f"{version_id}.json"

        if not version_file.exists():
            return None

        data = json.loads(version_file.read_text())
        version = WorkflowVersion.from_dict(data)

        # Verify checksum if available
        if not version.verify_checksum():
            logger.warning(
                f"Checksum mismatch for {workflow_name}/{version_id}. "
                f"Content may have been tampered with."
            )

        return version
    
    def get_current(self, workflow_name: str) -> Optional[WorkflowVersion]:
        """Get the current (latest) version of a workflow."""
        versions = self.list_versions(workflow_name)
        return versions[0] if versions else None
    
    def rollback(
        self,
        workflow_name: str,
        version_id: str,
        workflows_dir: str = "./workflows"
    ) -> bool:
        """
        Rollback a workflow to a previous version.
        
        Args:
            workflow_name: Name of the workflow
            version_id: Version to rollback to
            workflows_dir: Directory containing workflow files
            
        Returns:
            True if rollback successful
        """
        logger.info(f"Rollback called: {workflow_name} -> {version_id}")
        version = self.get_version(workflow_name, version_id)
        logger.info(f"Found version: {version}")
        if not version:
            logger.error(f"Version {version_id} not found")
            return False
        
        try:
            workflows_path = Path(workflows_dir or "./workflows")
            workflows_path.mkdir(parents=True, exist_ok=True)
            workflow_file = workflows_path / f"{workflow_name}.yaml"
            workflow_file.write_text(version.content)
            
            self.save_version(
                workflow_name,
                version.content,
                message=f"Rollback to {version_id}",
                tags=["rollback"]
            )
            
            logger.info(f"Rolled back '{workflow_name}' to {version_id}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def diff(
        self,
        workflow_name: str,
        from_version: str,
        to_version: str
    ) -> Optional[VersionDiff]:
        """
        Compare two versions of a workflow.
        
        Args:
            workflow_name: Name of the workflow
            from_version: Source version
            to_version: Target version
            
        Returns:
            VersionDiff or None if versions not found
        """
        v1 = self.get_version(workflow_name, from_version)
        v2 = self.get_version(workflow_name, to_version)
        
        if not v1 or not v2:
            return None
        
        # Simple line-by-line diff
        lines1 = v1.content.splitlines()
        lines2 = v2.content.splitlines()

        additions = 0
        deletions = 0
        changes = []

        # Use difflib for proper ordered diff
        diff = difflib.unified_diff(lines1, lines2, lineterm="")
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
                changes.append({"type": "add", "line": line[1:]})
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
                changes.append({"type": "delete", "line": line[1:]})
        
        return VersionDiff(
            from_version=from_version,
            to_version=to_version,
            additions=additions,
            deletions=deletions,
            changes=changes
        )
    
    def tag_version(
        self,
        workflow_name: str,
        version_id: str,
        tag: str
    ) -> bool:
        """
        Add a tag to a version.
        
        Args:
            workflow_name: Name of the workflow
            version_id: Version to tag
            tag: Tag to add
            
        Returns:
            True if successful
        """
        version = self.get_version(workflow_name, version_id)
        if not version:
            return False
        
        if tag not in version.tags:
            version.tags.append(tag)
            
            # Save updated version
            wf_dir = self._get_workflow_dir(workflow_name)
            version_file = wf_dir / f"{version_id}.json"
            version_file.write_text(json.dumps(version.to_dict(), indent=2))
            
            logger.info(f"Tagged {version_id} with '{tag}'")
        
        return True
    
    def delete_version(
        self,
        workflow_name: str,
        version_id: str
    ) -> bool:
        """
        Delete a version from history.

        Args:
            workflow_name: Name of the workflow
            version_id: Version to delete

        Returns:
            True if deleted
        """
        wf_dir = self._get_workflow_dir(workflow_name)
        version_file = wf_dir / f"{version_id}.json"

        if not version_file.exists():
            return False

        # Re-link children that point to this version
        deleted = self.get_version(workflow_name, version_id)
        new_parent = deleted.parent_version if deleted else None
        versions = self.list_versions(workflow_name)
        for v in versions:
            # Skip the version being deleted
            if v.version_id == version_id:
                continue
            if v.parent_version == version_id:
                v.parent_version = new_parent
                vf = wf_dir / f"{v.version_id}.json"
                vf.write_text(json.dumps(v.to_dict(), indent=2))

        version_file.unlink()

        # Update index
        index_file = wf_dir / "index.json"
        if index_file.exists():
            index = json.loads(index_file.read_text())
            if version_id in index["versions"]:
                index["versions"].remove(version_id)
            index_file.write_text(json.dumps(index, indent=2))

        logger.info(f"Deleted version {version_id}")
        return True


# Global version manager
_version_manager: Optional[WorkflowVersionManager] = None
_version_manager_lock = threading.Lock()


def get_version_manager() -> WorkflowVersionManager:
    """Get the global version manager instance (thread-safe)."""
    global _version_manager
    with _version_manager_lock:
        if _version_manager is None:
            _version_manager = WorkflowVersionManager()
    return _version_manager
