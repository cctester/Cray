"""
Workflow definition and management.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from enum import Enum
from datetime import datetime
import yaml
from pydantic import BaseModel, Field
from loguru import logger

# Valid step name: alphanumeric, underscores, hyphens (no spaces or special chars)
_STEP_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# ── YAML Schema Validation ───────────────────────────────────────────

# Known top-level keys in a workflow YAML file
_VALID_TOP_LEVEL_KEYS: Set[str] = {
    "name", "version", "description", "variables", "dependencies",
    "triggers", "steps", "on_success", "on_failure", "on_error",
    "parallel", "max_parallel",
}

# Required keys that must be present
_REQUIRED_KEYS: Set[str] = {"name", "steps"}

# Known step-level keys
_VALID_STEP_KEYS: Set[str] = {
    "name", "plugin", "action", "params", "depends_on", "condition",
    "retry", "retry_delay", "timeout", "on_error", "continue_on_error",
    "max_retries",
}

# Required step keys
_REQUIRED_STEP_KEYS: Set[str] = {"name", "plugin", "action"}


class YAMLValidationError(Exception):
    """Raised when YAML workflow data fails schema validation."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"YAML validation failed with {len(errors)} error(s): " +
                         "; ".join(errors))


def validate_workflow_yaml(data: Any) -> List[str]:
    """Validate raw YAML data against the workflow schema.

    Args:
        data: The parsed YAML data (result of yaml.safe_load).

    Returns:
        List of validation error strings. Empty list means valid.
    """
    errors: List[str] = []

    # ── Top-level type check ──
    if data is None:
        return ["YAML file is empty or contains only comments"]

    if not isinstance(data, dict):
        return [f"YAML root must be a mapping, got {type(data).__name__}"]

    # ── Required top-level keys ──
    for key in _REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: '{key}'")

    # ── Unknown top-level keys ──
    unknown_keys = set(data.keys()) - _VALID_TOP_LEVEL_KEYS
    if unknown_keys:
        errors.append(f"Unknown top-level key(s): {sorted(unknown_keys)}")

    # ── Type checks for top-level fields ──
    if "name" in data and not isinstance(data["name"], str):
        errors.append(f"'name' must be a string, got {type(data['name']).__name__}")

    if "version" in data and not isinstance(data["version"], (str, int, float)):
        errors.append(f"'version' must be a string or number, got {type(data['version']).__name__}")

    if "description" in data and not isinstance(data["description"], str):
        errors.append(f"'description' must be a string, got {type(data['description']).__name__}")

    if "variables" in data and not isinstance(data["variables"], dict):
        errors.append(f"'variables' must be a mapping, got {type(data['variables']).__name__}")

    if "dependencies" in data and not isinstance(data["dependencies"], list):
        errors.append(f"'dependencies' must be a list, got {type(data['dependencies']).__name__}")

    if "triggers" in data and not isinstance(data["triggers"], list):
        errors.append(f"'triggers' must be a list, got {type(data['triggers']).__name__}")

    if "parallel" in data and not isinstance(data["parallel"], bool):
        errors.append(f"'parallel' must be a boolean, got {type(data['parallel']).__name__}")

    if "max_parallel" in data and not isinstance(data["max_parallel"], int):
        errors.append(f"'max_parallel' must be an integer, got {type(data['max_parallel']).__name__}")

    if "on_success" in data and not isinstance(data["on_success"], list):
        errors.append(f"'on_success' must be a list, got {type(data['on_success']).__name__}")

    if "on_failure" in data and not isinstance(data["on_failure"], list):
        errors.append(f"'on_failure' must be a list, got {type(data['on_failure']).__name__}")

    if "on_error" in data and not isinstance(data["on_error"], list):
        errors.append(f"'on_error' must be a list, got {type(data['on_error']).__name__}")

    # ── Steps validation ──
    if "steps" in data:
        steps = data["steps"]

        if not isinstance(steps, list):
            errors.append(f"'steps' must be a list, got {type(steps).__name__}")
        elif len(steps) == 0:
            errors.append("'steps' list is empty — workflow must have at least one step")
        else:
            for i, step in enumerate(steps, 1):
                step_errors = _validate_step(step, index=i)
                errors.extend(step_errors)

    return errors


def _validate_step(step: Any, index: int) -> List[str]:
    """Validate a single step entry from YAML data."""
    errors: List[str] = []
    prefix = f"Step #{index}"

    if not isinstance(step, dict):
        errors.append(f"{prefix}: must be a mapping, got {type(step).__name__}")
        return errors

    # Required keys
    for key in _REQUIRED_STEP_KEYS:
        if key not in step:
            errors.append(f"{prefix}: missing required key '{key}'")

    # Unknown keys
    unknown_keys = set(step.keys()) - _VALID_STEP_KEYS
    if unknown_keys:
        errors.append(f"{prefix}: unknown key(s): {sorted(unknown_keys)}")

    # Type checks
    if "name" in step:
        if not isinstance(step["name"], str):
            errors.append(f"{prefix}: 'name' must be a string, got {type(step['name']).__name__}")
        elif not step["name"].strip():
            errors.append(f"{prefix}: 'name' must not be empty")

    if "plugin" in step and not isinstance(step["plugin"], str):
        errors.append(f"{prefix}: 'plugin' must be a string, got {type(step['plugin']).__name__}")

    if "action" in step and not isinstance(step["action"], str):
        errors.append(f"{prefix}: 'action' must be a string, got {type(step['action']).__name__}")

    if "params" in step and not isinstance(step["params"], dict):
        errors.append(f"{prefix}: 'params' must be a mapping, got {type(step['params']).__name__}")

    if "depends_on" in step:
        if not isinstance(step["depends_on"], list):
            errors.append(f"{prefix}: 'depends_on' must be a list, got {type(step['depends_on']).__name__}")
        elif not all(isinstance(d, str) for d in step["depends_on"]):
            errors.append(f"{prefix}: 'depends_on' items must all be strings")

    if "condition" in step and step["condition"] is not None and not isinstance(step["condition"], str):
        errors.append(f"{prefix}: 'condition' must be a string, got {type(step['condition']).__name__}")

    if "retry" in step and step["retry"] is not None and not isinstance(step["retry"], int):
        errors.append(f"{prefix}: 'retry' must be an integer, got {type(step['retry']).__name__}")

    if "retry_delay" in step and step["retry_delay"] is not None and not isinstance(step["retry_delay"], (int, float)):
        errors.append(f"{prefix}: 'retry_delay' must be a number, got {type(step['retry_delay']).__name__}")

    if "timeout" in step and step["timeout"] is not None and not isinstance(step["timeout"], (int, float)):
        errors.append(f"{prefix}: 'timeout' must be a number, got {type(step['timeout']).__name__}")

    if "continue_on_error" in step and step["continue_on_error"] is not None and not isinstance(step["continue_on_error"], bool):
        errors.append(f"{prefix}: 'continue_on_error' must be a boolean, got {type(step['continue_on_error']).__name__}")

    if "max_retries" in step and step["max_retries"] is not None and not isinstance(step["max_retries"], int):
        errors.append(f"{prefix}: 'max_retries' must be an integer, got {type(step['max_retries']).__name__}")

    return errors


class Step(BaseModel):
    """A single step in a workflow."""

    name: str
    plugin: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    condition: Optional[str] = None
    retry: int = 0
    retry_delay: int = 1  # seconds between retries
    timeout: int = 300
    on_error: Optional[Dict[str, Any]] = None  # error handler
    continue_on_error: bool = False  # continue workflow if step fails
    max_retries: Optional[int] = None  # alias for retry, for clarity

    class Config:
        extra = "allow"

    def get_retry_count(self) -> int:
        """Get effective retry count."""
        return self.max_retries if self.max_retries is not None else self.retry


class TriggerType(str, Enum):
    """Types of workflow triggers."""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"


class Trigger(BaseModel):
    """Workflow trigger configuration."""
    
    type: TriggerType
    config: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def manual(cls) -> "Trigger":
        return cls(type=TriggerType.MANUAL, config={"enabled": True})
    
    @classmethod
    def schedule(cls, cron: str) -> "Trigger":
        return cls(type=TriggerType.SCHEDULE, config={"cron": cron})


class Workflow(BaseModel):
    """Workflow definition."""

    name: str
    version: str = "1.0"
    description: str = ""
    variables: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    triggers: List[Trigger] = Field(default_factory=list)
    steps: List[Step] = Field(default_factory=list)
    on_success: List[Dict[str, Any]] = Field(default_factory=list)
    on_failure: List[Dict[str, Any]] = Field(default_factory=list)
    on_error: List[Dict[str, Any]] = Field(default_factory=list)  # global error handler
    parallel: bool = False  # enable parallel execution for independent steps
    max_parallel: int = 10  # max concurrent steps

    class Config:
        extra = "allow"

    @staticmethod
    def _parse_triggers(trigger_data_list: list) -> List[Trigger]:
        """Parse trigger data from YAML into Trigger objects."""
        triggers = []
        for trigger_data in trigger_data_list:
            if isinstance(trigger_data, dict):
                if "schedule" in trigger_data:
                    triggers.append(Trigger.schedule(trigger_data["schedule"]))
                elif trigger_data.get("manual"):
                    triggers.append(Trigger.manual())
            elif isinstance(trigger_data, str):
                if trigger_data == "manual":
                    triggers.append(Trigger.manual())
        return triggers

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Workflow":
        """Load workflow from YAML file.

        Raises YAMLValidationError if the YAML data fails schema validation.
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Schema validation before constructing the Workflow
        schema_errors = validate_workflow_yaml(data)
        if schema_errors:
            raise YAMLValidationError(schema_errors)

        triggers = cls._parse_triggers(data.get("triggers", []))
        steps = [Step(**step) for step in data.get("steps", [])]

        return cls(
            name=data.get("name", path.stem),
            version=data.get("version", "1.0"),
            description=data.get("description") or "",
            variables=data.get("variables", {}),
            dependencies=data.get("dependencies", []),
            triggers=triggers,
            steps=steps,
            on_success=data.get("on_success", []),
            on_failure=data.get("on_failure", []),
            on_error=data.get("on_error", []),
            parallel=data.get("parallel", False),
            max_parallel=data.get("max_parallel", 10),
        )
    
    def to_yaml(self, path: str | Path) -> None:
        """Save workflow to YAML file."""
        path = Path(path)

        data = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
        }

        if self.variables:
            data["variables"] = self.variables

        if self.dependencies:
            data["dependencies"] = self.dependencies

        data["triggers"] = [
            {"schedule": t.config.get("cron", "")} if t.type == TriggerType.SCHEDULE
            else {"manual": True}
            for t in self.triggers
        ]
        data["steps"] = [step.model_dump() for step in self.steps]

        if self.on_success:
            data["on_success"] = self.on_success
        if self.on_failure:
            data["on_failure"] = self.on_failure
        if self.on_error:
            data["on_error"] = self.on_error
        if self.parallel:
            data["parallel"] = self.parallel
        if self.max_parallel != 10:
            data["max_parallel"] = self.max_parallel

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def validate_steps(self) -> List[str]:
        """Validate workflow steps, return list of errors."""
        errors = []

        if not self.steps:
            errors.append("Workflow has no steps defined")
            return errors

        # Validate step name format
        for step in self.steps:
            if not step.name:
                errors.append(f"Step has empty name")
            elif not _STEP_NAME_PATTERN.match(step.name):
                errors.append(
                    f"Step name '{step.name}' is invalid: "
                    f"use only alphanumeric characters, underscores, and hyphens"
                )

        step_names = [s.name for s in self.steps]
        duplicates = [n for n in step_names if step_names.count(n) > 1]
        if duplicates:
            errors.append(f"Duplicate step names: {set(duplicates)}")

        # Validate depends_on references
        name_set = set(step_names)
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in name_set:
                    errors.append(f"Step '{step.name}' depends_on '{dep}' which does not exist")

        return errors

    @classmethod
    def from_yaml_string(cls, yaml_content: str) -> "Workflow":
        """Load workflow from YAML string.

        Raises YAMLValidationError if the YAML data fails schema validation.
        """
        data = yaml.safe_load(yaml_content)

        # Schema validation before constructing the Workflow
        schema_errors = validate_workflow_yaml(data)
        if schema_errors:
            raise YAMLValidationError(schema_errors)

        triggers = cls._parse_triggers(data.get("triggers", []))
        steps = [Step(**step) for step in data.get("steps", [])]

        return cls(
            name=data.get("name", "unnamed"),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            variables=data.get("variables", {}),
            dependencies=data.get("dependencies", []),
            triggers=triggers,
            steps=steps,
            on_success=data.get("on_success", []),
            on_failure=data.get("on_failure", []),
            on_error=data.get("on_error", []),
            parallel=data.get("parallel", False),
            max_parallel=data.get("max_parallel", 10),
        )


class WorkflowManager:
    """Manages workflow storage and retrieval."""

    def __init__(self, workflows_dir: str = "workflows"):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._load_workflows()

    def _load_workflows(self):
        """Load all workflows from the workflows directory."""
        for yaml_file in self.workflows_dir.glob("*.yaml"):
            try:
                workflow = Workflow.from_yaml(yaml_file)
                with open(yaml_file, "r", encoding="utf-8") as f:
                    content = f.read()
                mtime = datetime.fromtimestamp(yaml_file.stat().st_mtime).isoformat()
                self._workflows[workflow.name] = {
                    "id": workflow.name,
                    "name": workflow.name,
                    "version": workflow.version,
                    "description": workflow.description,
                    "file_path": str(yaml_file),
                    "content": content,
                    "updated_at": mtime,
                    "steps": [{"name": s.name, "plugin": s.plugin} for s in workflow.steps],
                }
            except YAMLValidationError as e:
                logger.warning(
                    f"Schema validation failed for {yaml_file}: "
                    f"{'; '.join(e.errors)}. Skipping."
                )
            except Exception as e:
                logger.warning(f"Failed to load workflow {yaml_file}: {e}")

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        return list(self._workflows.values())

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific workflow."""
        return self._workflows.get(workflow_id)

    def save_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a workflow.

        Validates YAML content against the workflow schema before saving.
        Raises YAMLValidationError if schema validation fails.
        """
        workflow_id = workflow_data.get("id") or workflow_data.get("name")
        workflow_path = self.workflows_dir / f"{workflow_id}.yaml"

        # Check if content field is provided (YAML from editor)
        now = datetime.utcnow().isoformat()
        if workflow_data.get("content"):
            # Validate YAML content before saving
            parsed = yaml.safe_load(workflow_data["content"])
            schema_errors = validate_workflow_yaml(parsed)
            if schema_errors:
                raise YAMLValidationError(schema_errors)

            with open(workflow_path, "w", encoding="utf-8") as f:
                f.write(workflow_data["content"])

            # Parse to get metadata for cache
            parsed = yaml.safe_load(workflow_data["content"])
            workflow_name = parsed.get("name", workflow_id)
            workflow_dict = {
                "id": workflow_name,
                "name": workflow_name,
                "version": parsed.get("version", "1.0"),
                "description": parsed.get("description", ""),
                "file_path": str(workflow_path),
                "content": workflow_data["content"],
                "updated_at": now,
                "steps": [{"name": s.get("name"), "plugin": s.get("plugin")} for s in parsed.get("steps", [])],
            }
        else:
            # Build workflow object from dict fields
            workflow_dict = {
                "name": workflow_id,
                "version": workflow_data.get("version", "1.0"),
                "description": workflow_data.get("description", ""),
                "steps": workflow_data.get("steps", []),
            }

            if workflow_data.get("variables"):
                workflow_dict["variables"] = workflow_data["variables"]
            if workflow_data.get("triggers"):
                workflow_dict["triggers"] = workflow_data["triggers"]

            # Save to file
            with open(workflow_path, "w", encoding="utf-8") as f:
                yaml.dump(workflow_dict, f, default_flow_style=False, allow_unicode=True)

            workflow_dict = {
                "id": workflow_id,
                "name": workflow_id,
                "version": workflow_data.get("version", "1.0"),
                "description": workflow_data.get("description", ""),
                "file_path": str(workflow_path),
                "content": workflow_data.get("content", ""),
                "updated_at": now,
                "steps": workflow_data.get("steps", []),
            }

        # Update cache - use workflow name from YAML as key
        cache_key = workflow_dict.get("name") or workflow_id
        self._workflows[cache_key] = workflow_dict

        return self._workflows[cache_key]

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow. Returns True if deleted, False if not found."""
        if workflow_id in self._workflows:
            workflow_path = Path(self._workflows[workflow_id]["file_path"])
            if workflow_path.exists():
                workflow_path.unlink()
            del self._workflows[workflow_id]
            return True
        return False
