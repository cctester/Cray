"""Tests for plugins."""

import pytest
import asyncio

from cray.plugins import PluginManager
from cray.plugins.builtin import ShellPlugin, HttpPlugin, FilePlugin


class TestShellPlugin:
    """Test Shell plugin."""
    
    @pytest.fixture
    def plugin(self):
        return ShellPlugin()
    
    @pytest.mark.asyncio
    async def test_exec_command(self, plugin):
        """Test executing a command."""
        result = await plugin.execute("exec", {"command": "echo hello"}, {})
        
        assert result["success"]
        assert "hello" in result["stdout"]
    
    @pytest.mark.asyncio
    async def test_exec_failed_command(self, plugin):
        """Test failed command execution."""
        result = await plugin.execute(
            "exec", 
            {"command": "exit 1"}, 
            {}
        )
        
        assert not result["success"]
        assert result["return_code"] == 1


class TestFilePlugin:
    """Test File plugin."""
    
    @pytest.fixture
    def plugin(self):
        return FilePlugin()
    
    @pytest.mark.asyncio
    async def test_write_and_read(self, plugin, temp_dir):
        """Test writing and reading a file."""
        test_file = temp_dir / "test.txt"
        
        # Write
        await plugin.execute("write", {
            "path": str(test_file),
            "content": "Hello, Cray!"
        }, {})
        
        assert test_file.exists()
        
        # Read
        result = await plugin.execute("read", {"path": str(test_file)}, {})
        
        assert result["success"]
        assert result["content"] == "Hello, Cray!"
    
    @pytest.mark.asyncio
    async def test_exists(self, plugin, temp_dir):
        """Test file existence check."""
        test_file = temp_dir / "exists.txt"
        test_file.write_text("test")
        
        result = await plugin.execute("exists", {"path": str(test_file)}, {})
        
        assert result["exists"]
        assert result["is_file"]
    
    @pytest.mark.asyncio
    async def test_list_directory(self, plugin, temp_dir):
        """Test listing directory."""
        # Create some files
        (temp_dir / "file1.txt").write_text("a")
        (temp_dir / "file2.txt").write_text("b")
        
        result = await plugin.execute("list", {"path": str(temp_dir)}, {})
        
        assert result["success"]
        assert result["count"] == 2


class TestPluginManager:
    """Test Plugin Manager."""
    
    def test_register_plugin(self):
        """Test plugin registration."""
        manager = PluginManager()
        
        # Built-in plugins should be loaded
        assert manager.has_plugin("shell")
        assert manager.has_plugin("http")
        assert manager.has_plugin("file")
    
    def test_get_plugin(self):
        """Test getting a plugin."""
        manager = PluginManager()
        plugin = manager.get_plugin("shell")
        
        assert plugin is not None
        assert plugin.name == "shell"
    
    def test_list_plugins(self):
        """Test listing plugins."""
        manager = PluginManager()
        plugins = manager.list_plugins()
        
        assert "shell" in plugins
        assert "http" in plugins
        assert "file" in plugins
