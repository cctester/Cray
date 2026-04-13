"""Tests for Web API."""

import pytest
from fastapi.testclient import TestClient

from cray.web import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app(workflow_dir="./test_workflows")
    return TestClient(app)


class TestWebAPI:
    """Test Web API endpoints."""
    
    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Cray API" in response.json()["name"]
    
    def test_list_plugins(self, client):
        """Test listing plugins."""
        response = client.get("/plugins")
        assert response.status_code == 200
        plugins = response.json()
        assert "shell" in plugins
        assert "http" in plugins
        assert "file" in plugins
    
    def test_create_and_get_workflow(self, client):
        """Test creating and retrieving a workflow."""
        # Create workflow
        create_response = client.post(
            "/workflows",
            json={
                "name": "test-workflow",
                "description": "Test workflow",
                "steps": [
                    {
                        "name": "hello",
                        "plugin": "shell",
                        "action": "exec",
                        "params": {"command": "echo hello"}
                    }
                ]
            }
        )
        assert create_response.status_code == 201
        
        # Get workflow
        get_response = client.get("/workflows/test-workflow")
        assert get_response.status_code == 200
        
        workflow = get_response.json()
        assert workflow["name"] == "test-workflow"
        assert len(workflow["steps"]) == 1
    
    def test_list_workflows(self, client):
        """Test listing workflows."""
        response = client.get("/workflows")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_delete_workflow(self, client):
        """Test deleting a workflow."""
        # Create workflow
        client.post(
            "/workflows",
            json={
                "name": "to-delete",
                "description": "Will be deleted",
                "steps": []
            }
        )
        
        # Delete workflow
        response = client.delete("/workflows/to-delete")
        assert response.status_code == 200
        
        # Verify deleted
        get_response = client.get("/workflows/to-delete")
        assert get_response.status_code == 404
    
    def test_run_workflow(self, client):
        """Test running a workflow."""
        # Create workflow
        client.post(
            "/workflows",
            json={
                "name": "run-test",
                "description": "Test run",
                "steps": [
                    {
                        "name": "echo",
                        "plugin": "shell",
                        "action": "exec",
                        "params": {"command": "echo test"}
                    }
                ]
            }
        )
        
        # Run workflow
        response = client.post(
            "/workflows/run-test/run",
            json={"input_data": {}}
        )
        assert response.status_code == 200
        
        task = response.json()
        assert task["workflow_name"] == "run-test"
        assert task["status"] in ["pending", "running", "success"]
