"""
Workflow definition and management.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from enum import Enum
import yaml
from pydantic import BaseModel, Field


class Step(BaseModel):
    """A single step in a workflow."""
    
    name: str
    plugin: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None
    retry: int = 0
    timeout: int = 300
    
    class Config:
        extra = "allow"


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
    triggers: List[Trigger] = Field(default_factory=list)
    steps: List[Step] = Field(default_factory=list)
    on_success: List[Dict[str, Any]] = Field(default_factory=list)
    on_failure: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        extra = "allow"
    
    @classmethod
    def from_yaml(cls, path: str | Path) -> "Workflow":
        """Load workflow from YAML file."""
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Parse triggers
        triggers = []
        for trigger_data in data.get("triggers", []):
            if isinstance(trigger_data, dict):
                if "schedule" in trigger_data:
                    triggers.append(Trigger.schedule(trigger_data["schedule"]))
                elif trigger_data.get("manual"):
                    triggers.append(Trigger.manual())
            elif isinstance(trigger_data, str):
                if trigger_data == "manual":
                    triggers.append(Trigger.manual())
        
        # Parse steps
        steps = [Step(**step) for step in data.get("steps", [])]
        
        return cls(
            name=data.get("name", path.stem),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            triggers=triggers,
            steps=steps,
            on_success=data.get("on_success", []),
            on_failure=data.get("on_failure", []),
        )
    
    def to_yaml(self, path: str | Path) -> None:
        """Save workflow to YAML file."""
        path = Path(path)
        
        data = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "triggers": [
                {"schedule": t.config["cron"]} if t.type == TriggerType.SCHEDULE 
                else {"manual": True}
                for t in self.triggers
            ],
            "steps": [step.model_dump() for step in self.steps],
            "on_success": self.on_success,
            "on_failure": self.on_failure,
        }
        
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def validate_steps(self) -> List[str]:
        """Validate workflow steps, return list of errors."""
        errors = []
        
        if not self.steps:
            errors.append("Workflow has no steps defined")
        
        step_names = [s.name for s in self.steps]
        duplicates = [n for n in step_names if step_names.count(n) > 1]
        if duplicates:
            errors.append(f"Duplicate step names: {set(duplicates)}")
        
        return errors
