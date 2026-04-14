"""
Tests for the dependency chain functionality.
"""

import pytest
from cray.core.dependency import (
    DependencyGraph,
    DependencyNode,
    WorkflowChain,
    build_step_dependency_graph,
    build_workflow_dependency_graph,
)


class TestDependencyGraph:
    """Tests for DependencyGraph class."""

    def test_add_node(self):
        """Test adding nodes to the graph."""
        graph = DependencyGraph()
        graph.add_node("step1")
        graph.add_node("step2", depends_on=["step1"])

        assert "step1" in graph.nodes
        assert "step2" in graph.nodes
        assert graph.nodes["step2"].depends_on == ["step1"]

    def test_validate_empty_graph(self):
        """Test validation of empty graph."""
        graph = DependencyGraph()
        errors = graph.validate()
        assert errors == []

    def test_validate_missing_dependency(self):
        """Test validation catches missing dependencies."""
        graph = DependencyGraph()
        graph.add_node("step1", depends_on=["missing_step"])

        errors = graph.validate()
        assert len(errors) == 1
        assert "missing_step" in errors[0]

    def test_validate_cycle_detection(self):
        """Test validation catches cycles."""
        graph = DependencyGraph()
        graph.add_node("a", depends_on=["c"])
        graph.add_node("b", depends_on=["a"])
        graph.add_node("c", depends_on=["b"])

        errors = graph.validate()
        assert len(errors) == 1
        assert "cycle" in errors[0].lower()

    def test_execution_order_simple(self):
        """Test execution order with simple dependencies."""
        graph = DependencyGraph()
        graph.add_node("step1")
        graph.add_node("step2", depends_on=["step1"])
        graph.add_node("step3", depends_on=["step2"])

        order = graph.get_execution_order()
        assert order.index("step1") < order.index("step2")
        assert order.index("step2") < order.index("step3")

    def test_execution_order_parallel(self):
        """Test execution order with parallel steps."""
        graph = DependencyGraph()
        graph.add_node("step1")
        graph.add_node("step2", depends_on=["step1"])
        graph.add_node("step3", depends_on=["step1"])

        order = graph.get_execution_order()
        assert order.index("step1") < order.index("step2")
        assert order.index("step1") < order.index("step3")

    def test_parallel_groups(self):
        """Test getting parallel execution groups."""
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c", depends_on=["a", "b"])
        graph.add_node("d", depends_on=["c"])

        groups = graph.get_parallel_groups()
        
        # First group: a and b (no dependencies)
        assert "a" in groups[0]
        assert "b" in groups[0]
        
        # Second group: c (depends on a and b)
        assert groups[1] == ["c"]
        
        # Third group: d (depends on c)
        assert groups[2] == ["d"]

    def test_get_ready_nodes(self):
        """Test getting nodes ready to execute."""
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b", depends_on=["a"])
        graph.add_node("c", depends_on=["a"])

        # Initially only 'a' is ready
        ready = graph.get_ready_nodes(set())
        assert ready == ["a"]

        # After 'a' completes, 'b' and 'c' are ready
        ready = graph.get_ready_nodes({"a"})
        assert sorted(ready) == ["b", "c"]

    def test_mark_status(self):
        """Test marking node status."""
        graph = DependencyGraph()
        graph.add_node("step1")

        graph.mark_running("step1")
        assert graph.nodes["step1"].status == "running"

        graph.mark_success("step1", {"result": "ok"})
        assert graph.nodes["step1"].status == "success"
        assert graph.nodes["step1"].output == {"result": "ok"}

        graph.mark_failed("step2", "error message")
        # step2 doesn't exist, should not crash

    def test_get_dependents(self):
        """Test getting dependents of a node."""
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b", depends_on=["a"])
        graph.add_node("c", depends_on=["a"])

        dependents = graph.get_dependents("a")
        assert sorted(dependents) == ["b", "c"]

    def test_to_dict(self):
        """Test exporting graph to dictionary."""
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b", depends_on=["a"])

        data = graph.to_dict()
        assert "nodes" in data
        assert "execution_order" in data
        assert "parallel_groups" in data


class TestBuildStepDependencyGraph:
    """Tests for build_step_dependency_graph function."""

    def test_build_from_steps(self):
        """Test building graph from step objects."""
        from dataclasses import dataclass

        @dataclass
        class MockStep:
            name: str
            depends_on: list = None

        steps = [
            MockStep(name="step1"),
            MockStep(name="step2", depends_on=["step1"]),
            MockStep(name="step3", depends_on=["step1", "step2"]),
        ]

        graph = build_step_dependency_graph(steps)
        
        assert len(graph.nodes) == 3
        assert graph.nodes["step2"].depends_on == ["step1"]
        assert graph.nodes["step3"].depends_on == ["step1", "step2"]

    def test_build_with_string_depends_on(self):
        """Test building graph when depends_on is a string."""
        from dataclasses import dataclass

        @dataclass
        class MockStep:
            name: str
            depends_on: str = ""

        steps = [
            MockStep(name="step1", depends_on=""),
            MockStep(name="step2", depends_on="step1"),
        ]

        graph = build_step_dependency_graph(steps)
        # String should be converted to list
        assert graph.nodes["step2"].depends_on == ["step1"]


class TestWorkflowChain:
    """Tests for WorkflowChain class."""

    def test_add_workflow(self):
        """Test adding workflows to chain."""
        chain = WorkflowChain()
        chain.add_workflow("fetch-data")
        chain.add_workflow("process-data", depends_on=["fetch-data"])

        assert len(chain.graph.nodes) == 2

    def test_validate_chain(self):
        """Test validating workflow chain."""
        chain = WorkflowChain()
        chain.add_workflow("a", depends_on=["missing"])

        errors = chain.validate()
        assert len(errors) == 1

    def test_get_execution_order(self):
        """Test getting workflow execution order."""
        chain = WorkflowChain()
        chain.add_workflow("fetch")
        chain.add_workflow("process", depends_on=["fetch"])
        chain.add_workflow("report", depends_on=["process"])

        order = chain.get_execution_order()
        assert order == ["fetch", "process", "report"]

    def test_to_dict(self):
        """Test exporting chain to dictionary."""
        chain = WorkflowChain()
        chain.add_workflow("a")
        chain.add_workflow("b", depends_on=["a"])

        data = chain.to_dict()
        assert "graph" in data
        assert "results" in data


class TestDependencyGraphIntegration:
    """Integration tests for dependency graph with complex scenarios."""

    def test_diamond_dependency(self):
        """Test diamond-shaped dependency graph."""
        #     A
        #    / \
        #   B   C
        #    \ /
        #     D
        graph = DependencyGraph()
        graph.add_node("A")
        graph.add_node("B", depends_on=["A"])
        graph.add_node("C", depends_on=["A"])
        graph.add_node("D", depends_on=["B", "C"])

        order = graph.get_execution_order()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

        groups = graph.get_parallel_groups()
        assert "A" in groups[0]
        assert "B" in groups[1] or "C" in groups[1]
        assert "D" in groups[2]

    def test_multiple_independent_chains(self):
        """Test multiple independent dependency chains."""
        graph = DependencyGraph()
        # Chain 1
        graph.add_node("a1")
        graph.add_node("a2", depends_on=["a1"])
        # Chain 2
        graph.add_node("b1")
        graph.add_node("b2", depends_on=["b1"])

        groups = graph.get_parallel_groups()
        # First group should have a1 and b1
        assert "a1" in groups[0]
        assert "b1" in groups[0]
        # Second group should have a2 and b2
        assert "a2" in groups[1]
        assert "b2" in groups[1]

    def test_long_chain(self):
        """Test a long dependency chain."""
        graph = DependencyGraph()
        for i in range(10):
            deps = [f"step{i-1}"] if i > 0 else []
            graph.add_node(f"step{i}", depends_on=deps)

        order = graph.get_execution_order()
        assert order == [f"step{i}" for i in range(10)]
