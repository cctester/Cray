"""
File plugin - file operations.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger

from cray.plugins import Plugin


class FilePlugin(Plugin):
    """Plugin for file operations."""
    
    name = "file"
    description = "File read, write, move, copy, delete operations"
    
    @property
    def actions(self):
        return {
            "read": {"description": "Read file content", "params": [{"name": "path", "type": "string", "required": True, "description": "File path"}]},
            "write": {"description": "Write content to file", "params": [{"name": "path", "type": "string", "required": True, "description": "File path"}, {"name": "content", "type": "string", "required": True, "description": "Content to write"}]},
            "copy": {"description": "Copy file or directory", "params": [{"name": "src", "type": "string", "required": True, "description": "Source path"}, {"name": "dst", "type": "string", "required": True, "description": "Destination path"}]},
            "move": {"description": "Move file or directory", "params": [{"name": "src", "type": "string", "required": True, "description": "Source path"}, {"name": "dst", "type": "string", "required": True, "description": "Destination path"}]},
            "delete": {"description": "Delete file or directory", "params": [{"name": "path", "type": "string", "required": True, "description": "Path to delete"}]},
            "list": {"description": "List files in directory", "params": [{"name": "path", "type": "string", "required": True, "description": "Directory path"}, {"name": "pattern", "type": "string", "required": False, "description": "File pattern"}]},
            "exists": {"description": "Check if file exists", "params": [{"name": "path", "type": "string", "required": True, "description": "Path to check"}]},
            "mkdir": {"description": "Create directory", "params": [{"name": "path", "type": "string", "required": True, "description": "Directory path"}]},
        }
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
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
        path = Path(params.get("path", ""))
        
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
        path = Path(params.get("path", ""))
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
        path = Path(params.get("path", ""))
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
        src = Path(params.get("src", ""))
        dst = Path(params.get("dst", ""))
        
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
        src = Path(params.get("src", ""))
        dst = Path(params.get("dst", ""))
        
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
        path = Path(params.get("path", ""))
        
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
        path = Path(params.get("path", ""))
        
        return {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "is_dir": path.is_dir() if path.exists() else False,
            "success": True
        }
    
    async def _list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents."""
        path = Path(params.get("path", "."))
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
        path = Path(params.get("path", ""))
        parents = params.get("parents", True)
        
        logger.debug(f"Creating directory: {path}")
        
        path.mkdir(parents=parents, exist_ok=True)
        
        return {
            "path": str(path),
            "success": True
        }
