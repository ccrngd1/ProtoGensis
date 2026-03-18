"""Tests for the SQLite memory store."""
from __future__ import annotations

import tempfile
import os

import pytest

from memory.models import Consolidation, Memory
from memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = MemoryStore(db_path=db_path)
    yield s
    s.close()


def test_add_and_get_memory(store):
    m = Memory(summary="Test memory", entities=["Alice"], topics=["testing"], importance=0.8)
    store.add_memory(m)
    retrieved = store.get_memory(m.id)
    assert retrieved is not None
    assert retrieved.summary == "Test memory"
    assert retrieved.entities == ["Alice"]
    assert retrieved.topics == ["testing"]
    assert abs(retrieved.importance - 0.8) < 1e-6
    assert retrieved.consolidated is False


def test_list_memories(store):
    for i in range(3):
        store.add_memory(Memory(summary=f"Memory {i}", entities=[], topics=[]))
    memories = store.list_memories()
    assert len(memories) == 3


def test_get_unconsolidated(store):
    m1 = Memory(summary="unconsolidated", consolidated=False)
    m2 = Memory(summary="consolidated", consolidated=True)
    store.add_memory(m1)
    store.add_memory(m2)
    unconsolidated = store.get_unconsolidated()
    assert len(unconsolidated) == 1
    assert unconsolidated[0].id == m1.id


def test_mark_consolidated(store):
    m = Memory(summary="will be consolidated")
    store.add_memory(m)
    assert store.get_unconsolidated()[0].id == m.id
    store.mark_consolidated([m.id])
    assert len(store.get_unconsolidated()) == 0
    retrieved = store.get_memory(m.id)
    assert retrieved.consolidated is True


def test_add_and_list_consolidation(store):
    c = Consolidation(
        memory_ids=["id1", "id2"],
        connections="Both about Python",
        insights="User prefers Python for scripting",
    )
    store.add_consolidation(c)
    consolidations = store.list_consolidations()
    assert len(consolidations) == 1
    assert consolidations[0].connections == "Both about Python"
    assert consolidations[0].memory_ids == ["id1", "id2"]


def test_count_methods(store):
    assert store.count_memories() == 0
    assert store.count_consolidations() == 0
    store.add_memory(Memory(summary="m1"))
    store.add_memory(Memory(summary="m2"))
    assert store.count_memories() == 2
    store.add_consolidation(Consolidation(memory_ids=["x"], connections="c", insights="i"))
    assert store.count_consolidations() == 1
