"""Tests for task loader."""

import pytest
from constraintbreak.tasks import TaskLoader, Task


class TestTaskLoader:
    """Test TaskLoader."""

    def test_load_tasks(self):
        """Test loading built-in tasks."""
        loader = TaskLoader()
        tasks = loader.get_tasks()

        assert len(tasks) > 0
        assert all(isinstance(t, Task) for t in tasks)

    def test_task_categories(self):
        """Test task categories."""
        loader = TaskLoader()
        categories = loader.get_categories()

        assert "writing" in categories
        assert "coding" in categories
        assert "analysis" in categories
        assert "reasoning" in categories

    def test_filter_by_category(self):
        """Test filtering tasks by category."""
        loader = TaskLoader()

        writing_tasks = loader.get_tasks("writing")
        assert len(writing_tasks) > 0
        assert all(t.category == "writing" for t in writing_tasks)

    def test_get_task_by_name(self):
        """Test getting task by name."""
        loader = TaskLoader()

        task = loader.get_task("essay_climate")
        assert task is not None
        assert task.name == "essay_climate"
        assert task.category == "writing"
        assert task.prompt

    def test_task_has_prompt(self):
        """Test that tasks have prompts."""
        loader = TaskLoader()
        tasks = loader.get_tasks()

        for task in tasks:
            assert task.get_prompt()
            assert len(task.get_prompt()) > 10

    def test_all_categories_have_tasks(self):
        """Test that all categories have tasks."""
        loader = TaskLoader()
        categories = loader.get_categories()

        for category in categories:
            tasks = loader.get_tasks(category)
            assert len(tasks) >= 3  # Each category should have at least 3 tasks
