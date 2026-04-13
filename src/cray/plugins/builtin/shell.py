"""
Shell plugin - execute shell commands.
"""

import asyncio
from typing import Dict, Any
from loguru import logger

from cray.plugins import Plugin


class ShellPlugin(Plugin):
    """Plugin for executing shell commands."""
    
    name = "shell"
    description = "Execute shell commands"
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a shell action."""
        
        if action == "exec":
            return await self._exec(params)
        elif action == "script":
            return await self._script(params)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _exec(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command."""
        command = params.get("command")
        
        if not command:
            raise ValueError("Missing required parameter: command")
        
        # Substitute context variables
        command = self._substitute(command, params.get("_context", {}))
        
        logger.debug(f"Executing command: {command}")
        
        # Run command
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )
        
        stdout, stderr = await proc.communicate()
        
        result = {
            "command": command,
            "return_code": proc.returncode,
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "success": proc.returncode == 0
        }
        
        if not result["success"]:
            logger.warning(f"Command failed with code {proc.returncode}: {stderr.decode()}")
        
        return result
    
    async def _script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a multi-line script."""
        script = params.get("script")
        
        if not script:
            raise ValueError("Missing required parameter: script")
        
        # Join script lines
        if isinstance(script, list):
            script = "\n".join(script)
        
        return await self._exec({"command": script})
    
    def _substitute(self, template: str, context: Dict[str, Any]) -> str:
        """Substitute context variables in template."""
        import re
        
        def replace(match):
            key = match.group(1)
            keys = key.split(".")
            value = context
            
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k, "")
                else:
                    value = ""
                    break
            
            return str(value)
        
        return re.sub(r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}", replace, template)
