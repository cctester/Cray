""" Shell plugin - execute shell commands.

Security notes:
- Commands run via subprocess_shell with shell=True by default.
- Set `allowed_commands` in plugin config to restrict to an allowlist.
- Set `sandbox=True` to enable basic command validation (blocks dangerous patterns).
- Context variable substitution uses shlex.quote to prevent injection.
"""

import asyncio
import re
import shlex
from typing import Dict, Any, List, Optional
from loguru import logger

from cray.plugins import Plugin

# Patterns that are commonly dangerous in shell commands
_DANGEROUS_PATTERNS = [
    re.compile(r";\s*rm\s"),
    re.compile(r";\s*shutdown"),
    re.compile(r";\s*reboot"),
    re.compile(r";\s*mkfs"),
    re.compile(r";\s*dd\s"),
    re.compile(r">\s*/dev/"),
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bchmod\s+-R\s+777"),
    re.compile(r"\bcurl\s+.*\|\s*sh"),
    re.compile(r"\bwget\s+.*\|\s*sh"),
    re.compile(r"\beval\s+"),
]


class ShellPlugin(Plugin):
    """Plugin for executing shell commands.

    Config options:
        allowed_commands: List of allowed command prefixes (e.g. ["echo", "ls", "git"])
            If set, only commands starting with these prefixes are allowed.
        sandbox: If True, block commands matching dangerous patterns (default: True)
        timeout: Default command timeout in seconds (default: 300)
    """

    name = "shell"
    description = "Execute shell commands"

    def __init__(self):
        super().__init__()
        self._allowed_commands: Optional[List[str]] = None
        self._sandbox: bool = True
        self._timeout: int = 300

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the shell plugin."""
        self._allowed_commands = config.get("allowed_commands")
        self._sandbox = config.get("sandbox", True)
        self._timeout = config.get("timeout", 300)

    @property
    def actions(self):
        return {
            "exec": {
                "description": "Execute a shell command",
                "params": [
                    {"name": "command", "type": "string", "required": True,
                     "description": "Shell command to execute"},
                    {"name": "timeout", "type": "number", "required": False,
                     "description": "Timeout in seconds"},
                ],
            },
            "script": {
                "description": "Execute a shell script",
                "params": [
                    {"name": "script", "type": "string", "required": True,
                     "description": "Shell script to execute"},
                ],
            },
        }

    async def execute(
        self, action: str, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a shell action."""
        if action == "exec":
            return await self._exec(params)
        elif action == "script":
            return await self._script(params)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _validate_command(self, command: str) -> None:
        """Validate command against security rules.

        Raises ValueError if the command violates security policy.
        """
        # Check allowlist if configured
        if self._allowed_commands is not None:
            stripped = command.strip()
            if not any(stripped.startswith(prefix) for prefix in self._allowed_commands):
                raise ValueError(
                    f"Command not in allowed list: {stripped.split()[0]!r}. "
                    f"Allowed prefixes: {self._allowed_commands}"
                )

        # Check dangerous patterns if sandbox mode is on
        if self._sandbox:
            for pattern in _DANGEROUS_PATTERNS:
                if pattern.search(command):
                    raise ValueError(
                        f"Command blocked by sandbox security policy. "
                        f"Matched dangerous pattern. Set sandbox=False to disable."
                    )

    async def _exec(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command."""
        command = params.get("command")
        if not command:
            raise ValueError("Missing required parameter: command")

        # Substitute context variables
        command = self._substitute(command, params.get("_context", {}))

        # Validate command against security rules
        self._validate_command(command)

        timeout = params.get("timeout", self._timeout)

        logger.debug(f"Executing command: {command}")

        # Run command
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "command": command,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "success": False,
            }

        result = {
            "command": command,
            "return_code": proc.returncode,
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "success": proc.returncode == 0
        }

        if not result["success"]:
            logger.warning(
                f"Command failed with code {proc.returncode}: {stderr.decode()}"
            )

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
        """Substitute context variables in template.

        Uses shlex.quote to safely escape substituted values so they
        cannot inject shell commands through variable expansion.
        """
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
            # Quote the substituted value to prevent injection
            return shlex.quote(str(value))

        return re.sub(r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}", replace, template)
