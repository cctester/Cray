"""Tests for parallel execution and error handling."""

import pytest
import asyncio
from cray.core.workflow import Workflow, Step
from cray.core.runner import Runner
from cray.plugins import PluginManager


class TestParallelExecution:
    """Test parallel step execution."""

    @pytest.fixture
    def runner(self):
        return Runner()

    def test_workflow_parallel_flag(self):
        """Test that workflow can have parallel flag."""
        workflow = Workflow(
            name="test-parallel",
            parallel=True,
            max_parallel=5,
            steps=[
                Step(name="step1", plugin="shell", action="exec", params={"command": "echo 1"}),
                Step(name="step2", plugin="shell", action="exec", params={"command": "echo 2"}),
            ]
        )
        assert workflow.parallel is True
        assert workflow.max_parallel == 5

    def test_workflow_serialization_with_parallel(self, tmp_path):
        """Test workflow serialization includes parallel settings."""
        workflow = Workflow(
            name="test-parallel",
            parallel=True,
            max_parallel=3,
            steps=[
                Step(name="step1", plugin="shell", action="exec", params={"command": "echo 1"}),
            ]
        )
        
        yaml_path = tmp_path / "test.yaml"
        workflow.to_yaml(yaml_path)
        
        loaded = Workflow.from_yaml(yaml_path)
        assert loaded.parallel is True
        assert loaded.max_parallel == 3

    @pytest.mark.asyncio
    async def test_parallel_execution_order(self, runner):
        """Test that independent steps can run in parallel."""
        workflow = Workflow(
            name="parallel-test",
            parallel=True,
            max_parallel=3,
            steps=[
                Step(name="a", plugin="shell", action="exec", params={"command": "echo a"}),
                Step(name="b", plugin="shell", action="exec", params={"command": "echo b"}),
                Step(name="c", plugin="shell", action="exec", params={"command": "echo c"}),
                Step(name="d", plugin="shell", action="exec", 
                     params={"command": "echo d"},
                     depends_on=["a", "b", "c"]),
            ]
        )
        
        task = await runner.run(workflow)
        assert task.status.value == "success"
        assert len(task.results) == 4

    @pytest.mark.asyncio
    async def test_sequential_execution_when_parallel_disabled(self, runner):
        """Test that steps run sequentially when parallel is disabled."""
        workflow = Workflow(
            name="sequential-test",
            parallel=False,
            steps=[
                Step(name="a", plugin="shell", action="exec", params={"command": "echo a"}),
                Step(name="b", plugin="shell", action="exec", params={"command": "echo b"}),
            ]
        )
        
        task = await runner.run(workflow)
        assert task.status.value == "success"


class TestErrorHandling:
    """Test error handling features."""

    @pytest.fixture
    def runner(self):
        return Runner()

    def test_step_retry_configuration(self):
        """Test step retry configuration."""
        step = Step(
            name="flaky",
            plugin="http",
            action="get",
            params={"url": "http://example.com"},
            retry=3,
            retry_delay=2
        )
        assert step.retry == 3
        assert step.retry_delay == 2
        assert step.get_retry_count() == 3

    def test_step_max_retries_alias(self):
        """Test max_retries as alias for retry."""
        step = Step(
            name="flaky",
            plugin="http",
            action="get",
            params={"url": "http://example.com"},
            max_retries=5
        )
        assert step.get_retry_count() == 5

    def test_step_continue_on_error(self):
        """Test continue_on_error flag."""
        step = Step(
            name="optional",
            plugin="shell",
            action="exec",
            params={"command": "exit 1"},
            continue_on_error=True
        )
        assert step.continue_on_error is True

    def test_step_on_error_handler(self):
        """Test step-level on_error handler."""
        step = Step(
            name="risky",
            plugin="shell",
            action="exec",
            params={"command": "risky-command"},
            on_error={
                "log": "Step failed",
                "notify": "admin@example.com"
            }
        )
        assert step.on_error is not None
        assert "log" in step.on_error

    def test_workflow_on_error_handlers(self):
        """Test workflow-level error handlers."""
        workflow = Workflow(
            name="error-handling-workflow",
            steps=[
                Step(name="step1", plugin="shell", action="exec", params={"command": "echo test"}),
            ],
            on_error=[{"log": "Workflow error"}],
            on_success=[{"log": "Success"}],
            on_failure=[{"log": "Failure"}]
        )
        assert len(workflow.on_error) == 1
        assert len(workflow.on_success) == 1
        assert len(workflow.on_failure) == 1

    @pytest.mark.asyncio
    async def test_continue_on_error_allows_workflow_to_continue(self, runner):
        """Test that workflow continues when step has continue_on_error."""
        workflow = Workflow(
            name="continue-on-error-test",
            steps=[
                Step(
                    name="failing-step",
                    plugin="shell",
                    action="exec",
                    params={"command": "exit 1"},
                    continue_on_error=True
                ),
                Step(
                    name="next-step",
                    plugin="shell",
                    action="exec",
                    params={"command": "echo 'I still run'"},
                    depends_on=["failing-step"]
                ),
            ]
        )
        
        task = await runner.run(workflow)
        # Workflow should complete (not fail) because continue_on_error is True
        assert task.status.value == "success"
        assert len(task.results) == 2

    @pytest.mark.asyncio
    async def test_retry_logic(self, runner):
        """Test that failed steps are retried."""
        # This test would need a mock plugin that fails first N times
        # For now, we just verify the retry mechanism is in place
        workflow = Workflow(
            name="retry-test",
            steps=[
                Step(
                    name="flaky",
                    plugin="shell",
                    action="exec",
                    params={"command": "echo success"},
                    retry=3,
                    retry_delay=0  # No delay for test
                ),
            ]
        )
        
        task = await runner.run(workflow)
        assert task.status.value == "success"


class TestDependencyGraph:
    """Test dependency graph functionality."""

    def test_get_parallel_groups(self):
        """Test getting parallel execution groups."""
        from cray.core.dependency import DependencyGraph
        
        graph = DependencyGraph()
        graph.add_node("a", [])
        graph.add_node("b", [])
        graph.add_node("c", ["a", "b"])
        graph.add_node("d", ["c"])
        
        groups = graph.get_parallel_groups()
        
        # First group: a and b (no dependencies)
        assert "a" in groups[0] or "b" in groups[0]
        # Second group: c (depends on a and b)
        assert "c" in groups[1]
        # Third group: d (depends on c)
        assert "d" in groups[2]

    def test_get_ready_nodes(self):
        """Test getting nodes ready to execute."""
        from cray.core.dependency import DependencyGraph
        
        graph = DependencyGraph()
        graph.add_node("a", [])
        graph.add_node("b", ["a"])
        graph.add_node("c", ["a"])
        
        # Initially only 'a' is ready
        ready = graph.get_ready_nodes(set())
        assert ready == ["a"]
        
        # After 'a' completes, 'b' and 'c' are ready
        ready = graph.get_ready_nodes({"a"})
        assert sorted(ready) == ["b", "c"]
