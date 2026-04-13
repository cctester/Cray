"""
Cray - A lightweight automation tool with claws 🦞

Cray helps you automate tasks with simple YAML workflows.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from cray.core.workflow import Workflow, Step
from cray.core.task import Task, TaskStatus
from cray.core.runner import Runner
from cray.scheduler import Scheduler
from cray.storage import JsonStore

__all__ = [
    "Workflow",
    "Step", 
    "Task",
    "TaskStatus",
    "Runner",
    "Scheduler",
    "JsonStore",
]
