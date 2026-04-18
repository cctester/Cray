"""
Plugin system for Cray.
"""

from typing import Dict, Any, Optional, Callable, Type
from loguru import logger
from abc import ABC, abstractmethod


class Plugin(ABC):
    """Base class for all plugins."""

    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    @abstractmethod
    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """
        Execute an action.

        Args:
            action: The action to execute
            params: Action parameters
            context: Execution context (step outputs, input, etc.)

        Returns:
            Action result
        """
        pass

    def setup(self, config: Dict[str, Any]) -> None:
        """Initialize plugin with configuration."""
        pass

    def teardown(self) -> None:
        """Cleanup plugin resources."""
        pass


class PluginManager:
    """Manages plugin registration and execution."""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._load_builtin_plugins()

    def _load_builtin_plugins(self) -> None:
        """Load built-in plugins."""
        from cray.plugins.builtin import (
            ShellPlugin, HttpPlugin, FilePlugin,
            EmailPlugin, JsonPlugin, NotifyPlugin,
            MathPlugin, TextPlugin, DatabasePlugin,
            GitPlugin, RedisPlugin, AWSPlugin,
        )

        self.register(ShellPlugin())
        self.register(HttpPlugin())
        self.register(FilePlugin())
        self.register(EmailPlugin())
        self.register(JsonPlugin())
        self.register(NotifyPlugin())
        self.register(MathPlugin())
        self.register(TextPlugin())
        self.register(DatabasePlugin())
        self.register(GitPlugin())
        self.register(RedisPlugin())
        self.register(AWSPlugin())

    def register(self, plugin: Plugin) -> None:
        """Register a plugin."""
        if not plugin.name:
            raise ValueError("Plugin must have a name")

        self._plugins[plugin.name] = plugin
        logger.debug(f"Registered plugin: {plugin.name}")

    def unregister(self, name: str) -> bool:
        """Unregister a plugin."""
        if name in self._plugins:
            self._plugins[name].teardown()
            del self._plugins[name]
            return True
        return False

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> Dict[str, str]:
        """List all registered plugins with descriptions."""
        return {
            name: plugin.description
            for name, plugin in self._plugins.items()
        }

    def has_plugin(self, name: str) -> bool:
        """Check if a plugin is registered."""
        return name in self._plugins


# Export marketplace classes
from cray.plugins.market import (
    PluginMarket,
    PluginRegistry,
    PluginInfo,
    PluginManifest,
)

__all__ = [
    "Plugin",
    "PluginManager",
    "PluginMarket",
    "PluginRegistry",
    "PluginInfo",
    "PluginManifest",
]
