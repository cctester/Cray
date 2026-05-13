""" File plugin - file operations.

Security notes:
- All paths are restricted to the configured workspace root by default.
- Set `workspace_root` in plugin config to define the allowed directory.
- Path traversal attempts (..) are rejected.
- Absolute paths outside workspace are rejected.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from cray.plugins import Plugin


class FilePlugin(Plugin):
    """Plugin for file operations.

    Config options:
        workspace_root: Root directory for file operations (default: current working directory).
            All paths are resolved relative to and restricted within this root.
        allow_absolute: If True, allow absolute paths within workspace_root (default: True).
    """

    name = "file"
    description = "File read, write, move, copy, delete operations"

    def __init__(self):
        super().__init__()
        self._workspace_root: Optional[Path] = None
        self._allow_absolute: bool = True

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the file plugin."""
        root = config.get("workspace_root")
        if root:
            self._workspace_root = Path(root).resolve()
            if not self._workspace_root.is_dir():
                raise ValueError(f"workspace_root is not a directory: {self._workspace_root}")
        self._allow_absolute = config.get("allow_absolute", True)

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve and validate a path is within the workspace root.

        Raises ValueError if the path attempts traversal outside the workspace.
        """
        path = Path(path_str)

        # Resolve to absolute path
        if self._workspace_root:
            if path.is_absolute():
                if not self._allow_absolute:
                    raise ValueError(f"Absolute paths not allowed: {path_str}")
                resolved = path.resolve()
            else:
                resolved = (self._workspace_root / path).resolve()

            # Ensure resolved path is within workspace root
            try:
                resolved.relative_to(self._workspace_root)
            except ValueError:
                raise ValueError(
                    f"Path escapes workspace root: {path_str} "
                    f"(resolved to {resolved}, root is {self._workspace_root})"
                )
        else:
            # No workspace root configured — still block obvious traversal
            resolved = path.resolve()
            # Block paths that go above CWD
            cwd = Path.cwd().resolve()
            try:
                resolved.relative_to(cwd)
            except ValueError:
                # Allow if it's an absolute path the user explicitly set
                if not path.is_absolute():
                    raise ValueError(
                        f"Path escapes current directory: {path_str} "
                        f"(resolved to {resolved})"
                    )

        # Reject paths with suspicious components
        parts = resolved.parts
        if ".." in parts:
            raise ValueError(f"Path contains '..' component: {path_str}")

        return resolved

    @property
    def actions(self):
        return {
            "read": {"description": "Read file content", "params": [
                {"name": "path", "type": "string", "required": True, "description": "File path"}
            ]},
            "write": {"description": "Write content to file", "params": [
                {"name": "path", "type": "string", "required": True, "description": "File path"},
                {"name": "content", "type": "string", "required": True, "description": "Content to write"}
            ]},
            "copy": {"description": "Copy file or directory", "params": [
                {"name": "src", "type": "string", "required": True, "description": "Source path"},
                {"name": "dst", "type": "string", "required": True, "description": "Destination path"}
            ]},
            "move": {"description": "Move file or directory", "params": [
                {"name": "src", "type": "string", "required": True, "description": "Source path"},
                {"name": "dst", "type": "string", "required": True, "description": "Destination path"}
            ]},
            "delete": {"description": "Delete file or directory", "params": [
                {"name": "path", "type": "string", "required": True, "description": "Path to delete"}
            ]},
            "list": {"description": "List files in directory", "params": [
                {"name": "path", "type": "string", "required": True, "description": "Directory path"},
                {"name": "pattern", "type": "string", "required": False, "description": "File pattern"}
            ]},
            "exists": {"description": "Check if file exists", "params": [
                {"name": "path", "type": "string", "required": True, "description": "Path to check"}
            ]},
            "mkdir": {"description": "Create directory", "params": [
                {"name": "path", "type": "string", "required": True, "description": "Directory path"}
            ]},
        }

    async def execute(
        self, action: str, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a file action."""
        actions = {
            "read": self._read,
            "write": self._write,
            "append": self._append,
            "copy": self._copy,
            "move": self._move,
            "delete": self._delete,
            "exists": self._exists,
            "list": self._list,
            "mkdir": self._mkdir,
        }
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        return await actions[action](params)

    async def _read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read file contents."""
        path = self._resolve_path(params.get("path", ""))

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        encoding = params.get("encoding", "utf-8")
        logger.debug(f"Reading file: {path}")

        content = path.read_text(encoding=encoding)

        # Try to parse as JSON if requested
        if params.get("parse_json"):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass

        return {
            "path": str(path),
            "content": content,
            "size": path.stat().st_size,
            "success": True
        }

    async def _write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Write content to file."""
        path = self._resolve_path(params.get("path", ""))
        content = params.get("content", "")
        encoding = params.get("encoding", "utf-8")

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Writing file: {path}")

        # Handle dict/list content
        if isinstance(content, (dict, list)):
            content = json.dumps(content, indent=2, ensure_ascii=False)

        path.write_text(str(content), encoding=encoding)

        return {
            "path": str(path),
            "size": path.stat().st_size,
            "success": True
        }

    async def _append(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append content to file."""
        path = self._resolve_path(params.get("path", ""))
        content = params.get("content", "")
        encoding = params.get("encoding", "utf-8")

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Appending to file: {path}")

        with open(path, "a", encoding=encoding) as f:
            f.write(str(content))

        return {
            "path": str(path),
            "size": path.stat().st_size,
            "success": True
        }

    async def _copy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Copy file or directory."""
        src = self._resolve_path(params.get("src", ""))
        dst = self._resolve_path(params.get("dst", ""))

        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")

        logger.debug(f"Copying: {src} -> {dst}")

        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        return {
            "src": str(src),
            "dst": str(dst),
            "success": True
        }

    async def _move(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Move file or directory."""
        src = self._resolve_path(params.get("src", ""))
        dst = self._resolve_path(params.get("dst", ""))

        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")

        logger.debug(f"Moving: {src} -> {dst}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        return {
            "src": str(src),
            "dst": str(dst),
            "success": True
        }

    async def _delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete file or directory."""
        path = self._resolve_path(params.get("path", ""))

        if not path.exists():
            # Not an error if missing_ok is True
            if params.get("missing_ok"):
                return {"path": str(path), "success": True}
            raise FileNotFoundError(f"Path not found: {path}")

        logger.debug(f"Deleting: {path}")

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

        return {
            "path": str(path),
            "success": True
        }

    async def _exists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if file or directory exists."""
        path = self._resolve_path(params.get("path", ""))

        return {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "is_dir": path.is_dir() if path.exists() else False,
            "success": True
        }

    async def _list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents."""
        path = self._resolve_path(params.get("path", "."))
        pattern = params.get("pattern", "*")
        recursive = params.get("recursive", False)

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        logger.debug(f"Listing directory: {path}")

        if recursive:
            items = list(path.rglob(pattern))
        else:
            items = list(path.glob(pattern))

        files = []
        for item in items:
            stat = item.stat()
            files.append({
                "name": item.name,
                "path": str(item),
                "is_file": item.is_file(),
                "is_dir": item.is_dir(),
                "size": stat.st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        return {
            "path": str(path),
            "files": files,
            "count": len(files),
            "success": True
        }

    async def _mkdir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create directory."""
        path = self._resolve_path(params.get("path", ""))
        parents = params.get("parents", True)

        logger.debug(f"Creating directory: {path}")

        path.mkdir(parents=parents, exist_ok=True)

        return {
            "path": str(path),
            "success": True
        }
