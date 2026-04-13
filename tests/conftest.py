"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    dir_path = Path(tempfile.mkdtemp())
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def sample_workflow_yaml(temp_dir):
    """Create a sample workflow YAML file."""
    content = """
name: test-workflow
version: "1.0"
description: Test workflow

steps:
  - name: hello
    plugin: shell
    action: exec
    params:
      command: echo "Hello"
"""
    workflow_path = temp_dir / "test.yaml"
    workflow_path.write_text(content)
    return workflow_path
