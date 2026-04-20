"""Task loader for test prompts."""

import os
from dataclasses import dataclass
from typing import List, Optional
import yaml


@dataclass
class Task:
    """Represents a single test task."""

    name: str
    category: str
    prompt: str
    description: Optional[str] = None

    def get_prompt(self) -> str:
        """Get the task prompt."""
        return self.prompt


class TaskLoader:
    """Loader for test task definitions."""

    def __init__(self, tasks_file: Optional[str] = None):
        """Initialize task loader.

        Args:
            tasks_file: Path to tasks YAML file.
                       Defaults to built-in tasks.yaml
        """
        if tasks_file is None:
            # Use built-in tasks
            current_dir = os.path.dirname(__file__)
            tasks_file = os.path.join(current_dir, "tasks.yaml")

        self.tasks_file = tasks_file
        self.tasks: List[Task] = []
        self._load_tasks()

    def _load_tasks(self):
        """Load tasks from YAML file."""
        with open(self.tasks_file, "r") as f:
            data = yaml.safe_load(f)

        for category, task_list in data.get("tasks", {}).items():
            for task_data in task_list:
                task = Task(
                    name=task_data["name"],
                    category=category,
                    prompt=task_data["prompt"],
                    description=task_data.get("description"),
                )
                self.tasks.append(task)

    def get_tasks(self, category: Optional[str] = None) -> List[Task]:
        """Get tasks, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of tasks
        """
        if category is None:
            return self.tasks

        return [t for t in self.tasks if t.category == category]

    def get_task(self, name: str) -> Optional[Task]:
        """Get task by name.

        Args:
            name: Task name

        Returns:
            Task object or None if not found
        """
        for task in self.tasks:
            if task.name == name:
                return task
        return None

    def get_categories(self) -> List[str]:
        """Get list of all task categories.

        Returns:
            List of unique category names
        """
        return list(set(t.category for t in self.tasks))
