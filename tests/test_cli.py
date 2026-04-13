"""Tests for CLI."""

import pytest
from click.testing import CliRunner

from cray.cli import main


class TestCLI:
    """Test CLI commands."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_version(self, runner):
        """Test version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "cray" in result.output
    
    def test_create_workflow(self, runner, temp_dir):
        """Test creating a workflow."""
        import os
        os.chdir(temp_dir)
        
        result = runner.invoke(main, ["create", "test-workflow"])
        
        assert result.exit_code == 0
        assert "Created workflow" in result.output
    
    def test_list_plugins(self, runner):
        """Test listing plugins."""
        result = runner.invoke(main, ["list", "--plugins"])
        
        assert result.exit_code == 0
        assert "shell" in result.output
        assert "http" in result.output
        assert "file" in result.output
    
    def test_validate_workflow(self, runner, sample_workflow_yaml):
        """Test validating a workflow."""
        result = runner.invoke(main, ["validate", str(sample_workflow_yaml)])
        
        assert result.exit_code == 0
        assert "valid" in result.output.lower()
