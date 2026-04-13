"""
Text plugin - text manipulation.
"""

import re
from typing import Dict, Any, List
from loguru import logger

from cray.plugins import Plugin


class TextPlugin(Plugin):
    """Plugin for text manipulation."""
    
    name = "text"
    description = "Text manipulation and formatting"
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a text action."""
        
        actions = {
            "format": self._format,
            "replace": self._replace,
            "regex": self._regex,
            "split": self._split,
            "join": self._join,
            "upper": self._upper,
            "lower": self._lower,
            "capitalize": self._capitalize,
            "trim": self._trim,
            "template": self._template,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Format text with variables."""
        template = params.get("template", "")
        variables = params.get("variables", {})
        
        try:
            result = template
            for key, value in variables.items():
                result = result.replace(f"{{{{{key}}}}}", str(value))
            
            return {
                "template": template,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _replace(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Replace text."""
        text = params.get("text", "")
        old = params.get("old", "")
        new = params.get("new", "")
        count = params.get("count", -1)  # -1 means replace all
        
        try:
            result = text.replace(old, new, count) if count > 0 else text.replace(old, new)
            
            return {
                "text": text,
                "result": result,
                "replacements": text.count(old) if count < 0 else min(text.count(old), count),
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _regex(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Regex operations."""
        text = params.get("text", "")
        pattern = params.get("pattern", "")
        operation = params.get("operation", "match")  # match, search, findall, sub
        
        try:
            if operation == "match":
                match = re.match(pattern, text)
                result = match.group(0) if match else None
                groups = match.groups() if match else []
            elif operation == "search":
                match = re.search(pattern, text)
                result = match.group(0) if match else None
                groups = match.groups() if match else []
            elif operation == "findall":
                result = re.findall(pattern, text)
                groups = []
            elif operation == "sub":
                replacement = params.get("replacement", "")
                result = re.sub(pattern, replacement, text)
                groups = []
            else:
                raise ValueError(f"Unknown regex operation: {operation}")
            
            return {
                "text": text,
                "pattern": pattern,
                "operation": operation,
                "result": result,
                "groups": groups,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _split(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Split text."""
        text = params.get("text", "")
        separator = params.get("separator", " ")
        max_splits = params.get("max_splits", -1)
        
        try:
            if max_splits > 0:
                result = text.split(separator, max_splits)
            else:
                result = text.split(separator)
            
            return {
                "text": text,
                "result": result,
                "count": len(result),
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _join(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Join text items."""
        items = params.get("items", [])
        separator = params.get("separator", "")
        
        try:
            result = separator.join(str(item) for item in items)
            
            return {
                "items": items,
                "separator": separator,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _upper(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert to uppercase."""
        text = params.get("text", "")
        
        return {
            "text": text,
            "result": text.upper(),
            "success": True,
        }
    
    async def _lower(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert to lowercase."""
        text = params.get("text", "")
        
        return {
            "text": text,
            "result": text.lower(),
            "success": True,
        }
    
    async def _capitalize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Capitalize text."""
        text = params.get("text", "")
        mode = params.get("mode", "first")  # first, words, sentence
        
        try:
            if mode == "first":
                result = text.capitalize()
            elif mode == "words":
                result = text.title()
            elif mode == "sentence":
                result = ". ".join(s.strip().capitalize() for s in text.split("."))
            else:
                result = text
            
            return {
                "text": text,
                "mode": mode,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _trim(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trim whitespace."""
        text = params.get("text", "")
        mode = params.get("mode", "both")  # both, start, end
        
        try:
            if mode == "both":
                result = text.strip()
            elif mode == "start":
                result = text.lstrip()
            elif mode == "end":
                result = text.rstrip()
            else:
                result = text
            
            return {
                "text": text,
                "mode": mode,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _template(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Render a template with context."""
        template = params.get("template", "")
        context_data = params.get("context", {})
        
        try:
            # Simple template rendering
            result = template
            
            # Replace {{ variable }} patterns
            pattern = r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}"
            
            def replace(match):
                key = match.group(1)
                keys = key.split(".")
                value = context_data
                
                for k in keys:
                    if isinstance(value, dict):
                        value = value.get(k, "")
                    else:
                        return ""
                
                return str(value)
            
            result = re.sub(pattern, replace, result)
            
            return {
                "template": template,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
