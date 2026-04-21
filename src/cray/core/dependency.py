"""
Workflow dependency chain management.

Supports:
- Workflow dependencies (workflow A depends on workflow B)
- Step dependencies (step A depends on step B)
- Parallel execution of independent steps
- Dependency graph validation
"""

from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from loguru import logger


class DependencyType(str, Enum):
    """Types of dependencies."""
    WORKFLOW = "workflow"
    STEP = "step"


@dataclass
class DependencyNode:
    """A node in the dependency graph."""
    name: str
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, failed, skipped
    output: Optional[Dict[str, Any]] = None


class DependencyGraph:
    """
    Manages a dependency graph for workflows or steps.
    
    Features:
    - Topological sorting for execution order
    - Cycle detection
    - Parallel execution groups
    - Status tracking
    """

    def __init__(self):
        self.nodes: Dict[str, DependencyNode] = {}
        self._execution_order: Optional[List[str]] = None

    def add_node(self, name: str, depends_on: List[str] = None) -> None:
        """Add a node to the graph."""
        self.nodes[name] = DependencyNode(
            name=name,
            depends_on=depends_on or []
        )
        self._execution_order = None  # Reset cached order

    def get_node(self, name: str) -> Optional[DependencyNode]:
        """Get a node by name."""
        return self.nodes.get(name)

    def validate(self) -> List[str]:
        """
        Validate the dependency graph.
        
        Returns:
            List of error messages, empty if valid
        """
        errors = []

        # Check for missing dependencies
        for node in self.nodes.values():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    errors.append(f"'{node.name}' depends on unknown '{dep}'")

        # Check for cycles
        if self._has_cycle():
            errors.append("Dependency graph contains a cycle")

        return errors

    def _has_cycle(self) -> bool:
        """Check if the graph has any cycles."""
        visited = set()
        rec_stack = set()

        def dfs(node_name: str) -> bool:
            visited.add(node_name)
            rec_stack.add(node_name)

            node = self.nodes.get(node_name)
            if node:
                for dep in node.depends_on:
                    if dep not in visited:
                        if dfs(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(node_name)
            return False

        for node_name in self.nodes:
            if node_name not in visited:
                if dfs(node_name):
                    return True

        return False

    def get_execution_order(self) -> List[str]:
        """
        Get topologically sorted execution order.
        
        Returns:
            List of node names in execution order
        """
        if self._execution_order:
            return self._execution_order

        # Kahn's algorithm for topological sort
        in_degree = {name: 0 for name in self.nodes}
        
        for node in self.nodes.values():
            for dep in node.depends_on:
                if dep in in_degree:
                    in_degree[node.name] += 1

        # Start with nodes that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort for deterministic order
            queue.sort()
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependent nodes
            for node in self.nodes.values():
                if current in node.depends_on:
                    in_degree[node.name] -= 1
                    if in_degree[node.name] == 0:
                        queue.append(node.name)

        self._execution_order = result
        return result

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get groups of nodes that can be executed in parallel.
        
        Returns:
            List of groups, each group can run in parallel
        """
        groups = []
        completed: Set[str] = set()
        remaining = set(self.nodes.keys())

        while remaining:
            # Find all nodes whose dependencies are satisfied
            ready = []
            for name in remaining:
                node = self.nodes[name]
                if all(dep in completed for dep in node.depends_on):
                    ready.append(name)

            if not ready:
                # This shouldn't happen if graph is valid
                break

            groups.append(sorted(ready))
            completed.update(ready)
            remaining -= set(ready)

        return groups

    def get_ready_nodes(self, completed: Set[str]) -> List[str]:
        """
        Get nodes that are ready to execute.
        
        Args:
            completed: Set of already completed node names
            
        Returns:
            List of node names ready to execute
        """
        ready = []
        for name, node in self.nodes.items():
            if name in completed:
                continue
            if node.status != "pending":
                continue
            if all(dep in completed for dep in node.depends_on):
                ready.append(name)
        return sorted(ready)

    def mark_running(self, name: str) -> None:
        """Mark a node as running."""
        if name in self.nodes:
            self.nodes[name].status = "running"

    def mark_success(self, name: str, output: Dict[str, Any] = None) -> None:
        """Mark a node as successfully completed."""
        if name in self.nodes:
            self.nodes[name].status = "success"
            self.nodes[name].output = output

    def mark_failed(self, name: str, error: str = None) -> None:
        """Mark a node as failed."""
        if name in self.nodes:
            self.nodes[name].status = "failed"
            if error:
                self.nodes[name].output = {"error": error}

    def mark_skipped(self, name: str, reason: str = None) -> None:
        """Mark a node as skipped."""
        if name in self.nodes:
            self.nodes[name].status = "skipped"
            if reason:
                self.nodes[name].output = {"reason": reason}

    def get_dependents(self, name: str) -> List[str]:
        """Get all nodes that depend on the given node."""
        dependents = []
        for node in self.nodes.values():
            if name in node.depends_on:
                dependents.append(node.name)
        return dependents

    def get_dependencies(self, name: str) -> List[str]:
        """Get all dependencies of a node."""
        node = self.nodes.get(name)
        return node.depends_on if node else []

    def to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary."""
        return {
            "nodes": {
                name: {
                    "name": node.name,
                    "depends_on": node.depends_on,
                    "status": node.status,
                    "output": node.output
                }
                for name, node in self.nodes.items()
            },
            "execution_order": self.get_execution_order(),
            "parallel_groups": self.get_parallel_groups()
        }


def build_step_dependency_graph(steps: List[Any]) -> DependencyGraph:
    """
    Build a dependency graph from workflow steps.
    
    Args:
        steps: List of Step objects with optional 'depends_on' field
        
    Returns:
        DependencyGraph for the steps
    """
    import re
    graph = DependencyGraph()

    for step in steps:
        depends_on = getattr(step, 'depends_on', []) or []
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        
        # Add implicit dependencies from condition references
        condition = getattr(step, 'condition', None)
        if condition:
            cond_pattern = r"\{\{\s*steps\.([\w\-]+)\.\w+\s*\}\}"
            cond_deps = re.findall(cond_pattern, condition)
            for dep in cond_deps:
                if dep not in depends_on:
                    depends_on.append(dep)
        
        graph.add_node(step.name, depends_on)

    return graph


def build_workflow_dependency_graph(
    workflow_refs: List[Dict[str, Any]]
) -> DependencyGraph:
    """
    Build a dependency graph from workflow references.
    
    Args:
        workflow_refs: List of dicts with 'name' and optional 'depends_on'
        
    Returns:
        DependencyGraph for the workflows
    """
    graph = DependencyGraph()

    for ref in workflow_refs:
        name = ref.get('name') or ref.get('workflow')
        depends_on = ref.get('depends_on', [])
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        if name:
            graph.add_node(name, depends_on)

    return graph


class WorkflowChain:
    """
    Manages a chain of dependent workflows.
    
    Example:
        chain = WorkflowChain()
        chain.add_workflow("fetch-data")
        chain.add_workflow("process-data", depends_on=["fetch-data"])
        chain.add_workflow("send-report", depends_on=["process-data"])
        
        # Execute in order
        await chain.execute()
    """

    def __init__(self, workflow_dir: Optional[Path] = None):
        self.graph = DependencyGraph()
        self.workflows: Dict[str, Any] = {}  # name -> Workflow
        self.workflow_dir = workflow_dir
        self._results: Dict[str, Any] = {}

    def add_workflow(
        self,
        name: str,
        depends_on: List[str] = None,
        workflow: Any = None
    ) -> None:
        """
        Add a workflow to the chain.
        
        Args:
            name: Workflow name or path
            depends_on: List of workflow names this depends on
            workflow: Optional Workflow object
        """
        self.graph.add_node(name, depends_on or [])
        if workflow:
            self.workflows[name] = workflow

    def validate(self) -> List[str]:
        """Validate the workflow chain."""
        return self.graph.validate()

    def get_execution_order(self) -> List[str]:
        """Get workflow execution order."""
        return self.graph.get_execution_order()

    async def execute(
        self,
        runner: Any,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute all workflows in dependency order.
        
        Args:
            runner: Runner instance to execute workflows
            input_data: Input data for the first workflow
            
        Returns:
            Dict mapping workflow names to their results
        """
        errors = self.validate()
        if errors:
            raise ValueError(f"Invalid workflow chain: {errors}")

        execution_order = self.get_execution_order()
        completed: Set[str] = set()

        for workflow_name in execution_order:
            workflow = self.workflows.get(workflow_name)
            if not workflow:
                logger.warning(f"Workflow '{workflow_name}' not found, skipping")
                self.graph.mark_skipped(workflow_name, "workflow_not_found")
                continue

            # Check if dependencies succeeded
            deps = self.graph.get_dependencies(workflow_name)
            failed_deps = [d for d in deps if self.graph.get_node(d).status != "success"]
            
            if failed_deps:
                logger.warning(
                    f"Skipping '{workflow_name}' due to failed dependencies: {failed_deps}"
                )
                self.graph.mark_skipped(workflow_name, f"dependencies_failed: {failed_deps}")
                continue

            # Execute workflow
            logger.info(f"Executing workflow '{workflow_name}'")
            self.graph.mark_running(workflow_name)

            try:
                # Merge input with outputs from dependencies
                workflow_input = input_data or {}
                for dep in deps:
                    dep_output = self._results.get(dep, {})
                    workflow_input = {**workflow_input, **dep_output}

                task = await runner.run(workflow, workflow_input)
                
                if task.status.value == "success":
                    self.graph.mark_success(workflow_name, task.results[-1].output if task.results else {})
                    self._results[workflow_name] = task.results[-1].output if task.results else {}
                else:
                    self.graph.mark_failed(workflow_name, task.error)

            except Exception as e:
                logger.error(f"Workflow '{workflow_name}' failed: {e}")
                self.graph.mark_failed(workflow_name, str(e))

            completed.add(workflow_name)

        return self._results

    def get_results(self) -> Dict[str, Any]:
        """Get all workflow results."""
        return self._results

    def to_dict(self) -> Dict[str, Any]:
        """Export chain state to dictionary."""
        return {
            "graph": self.graph.to_dict(),
            "results": self._results
        }
