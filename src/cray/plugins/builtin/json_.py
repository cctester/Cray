"""
JSON plugin - JSON data manipulation.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger

from cray.plugins import Plugin


class JsonPlugin(Plugin):
    """Plugin for JSON data manipulation."""
    
    name = "json"
    description = "Parse, transform, and query JSON data"
    
    @property
    def actions(self):
        return {
            "parse": {"description": "Parse JSON string", "params": [{"name": "data", "type": "string", "required": True, "description": "JSON string to parse"}]},
            "stringify": {"description": "Convert to JSON string", "params": [{"name": "data", "type": "object", "required": True, "description": "Data to stringify"}]},
            "query": {"description": "Query JSON data", "params": [{"name": "data", "type": "object", "required": True, "description": "JSON data"}, {"name": "query", "type": "string", "required": True, "description": "JSONPath query"}]},
            "merge": {"description": "Merge JSON objects", "params": [{"name": "sources", "type": "array", "required": True, "description": "Array of JSON objects to merge"}]},
            "transform": {"description": "Transform JSON data", "params": [{"name": "data", "type": "object", "required": True, "description": "Data to transform"}, {"name": "operations", "type": "array", "required": True, "description": "Transform operations"}]},
        }
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a JSON action."""
        
        actions = {
            "parse": self._parse,
            "stringify": self._stringify,
            "query": self._query,
            "merge": self._merge,
            "transform": self._transform,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _parse(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSON string to object."""
        data = params.get("data")
        
        if data is None:
            raise ValueError("Missing required parameter: data")
        
        try:
            if isinstance(data, str):
                result = json.loads(data)
            else:
                result = data
            
            return {
                "data": result,
                "success": True,
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {e}",
            }
    
    async def _stringify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert object to JSON string."""
        data = params.get("data")
        indent = params.get("indent", 2)
        
        try:
            result = json.dumps(data, indent=indent, ensure_ascii=False)
            return {
                "data": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query JSON data using JSONPath-like syntax."""
        data = params.get("data")
        path = params.get("path", "")
        
        if data is None:
            raise ValueError("Missing required parameter: data")
        
        try:
            # Simple path query: "key1.key2[0].key3"
            result = data
            parts = self._parse_path(path)
            
            for part in parts:
                if isinstance(result, dict):
                    result = result.get(part)
                elif isinstance(result, list):
                    if isinstance(part, int):
                        result = result[part]
                    else:
                        # Map over array
                        result = [item.get(part) for item in result if isinstance(item, dict)]
                else:
                    return {
                        "success": False,
                        "error": f"Cannot access '{part}' on non-dict/list value",
                    }
            
            return {
                "data": result,
                "path": path,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _merge(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple JSON objects."""
        objects = params.get("objects", [])
        deep = params.get("deep", False)
        
        if not objects:
            return {"data": {}, "success": True}
        
        try:
            if deep:
                result = self._deep_merge(*objects)
            else:
                result = {}
                for obj in objects:
                    result.update(obj)
            
            return {
                "data": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _transform(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform JSON data using mapping rules."""
        data = params.get("data", {})
        mapping = params.get("mapping", {})
        
        try:
            result = {}
            
            for new_key, source_path in mapping.items():
                # Get value from source path
                query_result = await self._query({"data": data, "path": source_path})
                if query_result["success"]:
                    result[new_key] = query_result["data"]
                else:
                    result[new_key] = None
            
            return {
                "data": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def _parse_path(self, path: str) -> List[str | int]:
        """Parse a path string into parts."""
        parts = []
        current = ""
        in_bracket = False
        
        for char in path:
            if char == "." and not in_bracket:
                if current:
                    parts.append(current)
                    current = ""
            elif char == "[":
                if current:
                    parts.append(current)
                    current = ""
                in_bracket = True
            elif char == "]":
                if current:
                    # Try to convert to int for array index
                    try:
                        parts.append(int(current))
                    except ValueError:
                        parts.append(current)
                    current = ""
                in_bracket = False
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts
    
    def _deep_merge(self, *dicts: Dict) -> Dict:
        """Deep merge multiple dictionaries."""
        result = {}
        
        for d in dicts:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(result[key], value)
                else:
                    result[key] = value
        
        return result
