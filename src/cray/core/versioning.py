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
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
from loguru import logger


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowVersion":
        """Create from dictionary."""
        return cls(**data)


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
        self.storage_path.chmod(0o700)
    
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
            created_at=datetime.now().isoformat(),
            author=author,
            message=message,
            tags=tags or [],
            parent_version=parent
        )
        
        # Save version file
        version_file = wf_dir / f"{version_id}.json"
        version_file.write_text(json.dumps(version.to_dict(), indent=2))
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
            index = {"versions": [], "current": None}
        
        # Add to front of list (newest first)
        if version.version_id not in index["versions"]:
            index["versions"].insert(0, version.version_id)
        
        index["current"] = version.version_id
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
        return WorkflowVersion.from_dict(data)
    
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
        version = self.get_version(workflow_name, version_id)
        if not version:
            logger.error(f"Version {version_id} not found")
            return False
        
        # Write workflow file
        workflow_file = Path(workflows_dir) / f"{workflow_name}.yaml"
        workflow_file.write_text(version.content)
        
        # Save as new version (rollback)
        self.save_version(
            workflow_name,
            version.content,
            message=f"Rollback to {version_id}",
            tags=["rollback"]
        )
        
        logger.info(f"Rolled back '{workflow_name}' to {version_id}")
        return True
    
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
        
        # Find added and deleted lines
        set1 = set(lines1)
        set2 = set(lines2)
        
        for line in set2 - set1:
            additions += 1
            changes.append({"type": "add", "line": line})
        
        for line in set1 - set2:
            deletions += 1
            changes.append({"type": "delete", "line": line})
        
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


def get_version_manager() -> WorkflowVersionManager:
    """Get the global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = WorkflowVersionManager()
    return _version_manager
