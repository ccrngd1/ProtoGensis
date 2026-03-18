"""
Semantic extraction: extract reusable facts from episodes, deduplicate.

Each episode is processed by Haiku to yield a list of atomic facts. Facts
that are semantically equivalent to existing ones (determined by an LLM
deduplication pass) are merged rather than duplicated.
"""

from __future__ import annotations

import json
from typing import List, Optional

from xmemory._llm import HAIKU_MODEL, call_llm
from xmemory.models import Episode, SemanticNode
from xmemory.store import MemoryStore


def _extract_facts_prompt(episode_summary: str) -> str:
    return (
        "You are extracting atomic, reusable facts from an episode summary for a memory system.\n\n"
        "Rules:\n"
        "- Each fact must be self-contained and meaningful without context\n"
        "- Focus on concrete decisions, preferences, relationships, and named entities\n"
        "- Avoid vague or generic statements\n"
        "- Return ONLY a JSON array of strings, one fact per element\n"
        "- Maximum 8 facts per episode\n\n"
        f"Episode summary:\n{episode_summary}\n\n"
        'Facts (JSON array):'
    )


def _dedup_prompt(new_fact: str, existing_facts: List[str]) -> str:
    existing_text = "\n".join(f"- {f}" for f in existing_facts)
    return (
        "You are checking whether a new fact is already captured by existing facts in a memory system.\n\n"
        f"New fact: {new_fact}\n\n"
        f"Existing facts:\n{existing_text}\n\n"
        "Is the new fact already captured (semantically equivalent or subsumed) by any existing fact?\n"
        "Answer with JSON: {\"duplicate\": true/false, \"reason\": \"brief explanation\"}"
    )


def extract_facts_from_episode(
    episode: Episode,
    model: str = HAIKU_MODEL,
    client=None,
) -> List[str]:
    """Use Haiku to extract atomic facts from an episode summary."""
    prompt = _extract_facts_prompt(episode.summary)
    response = call_llm(prompt, model=model, max_tokens=512, client=client).strip()

    # Parse JSON array
    try:
        # Strip markdown code fences if present
        text = response
        if "```" in text:
            lines = text.split("\n")
            text = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            )
        facts = json.loads(text)
        if isinstance(facts, list):
            return [str(f).strip() for f in facts if f]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: split by newlines, strip bullet chars
    lines = [l.strip().lstrip("-• ").strip() for l in response.split("\n")]
    return [l for l in lines if len(l) > 10]


def is_duplicate(
    new_fact: str,
    existing_facts: List[str],
    model: str = HAIKU_MODEL,
    client=None,
) -> tuple[bool, Optional[str]]:
    """
    Return (True, matching_fact) if new_fact is semantically captured by any existing fact.
    Returns (False, None) if it's a new fact.
    """
    if not existing_facts:
        return False, None
    # Only check against a window of recent facts to keep costs low
    window = existing_facts[-50:] if len(existing_facts) > 50 else existing_facts
    prompt = _dedup_prompt(new_fact, window)
    response = call_llm(prompt, model=model, max_tokens=128, client=client).strip()
    try:
        text = response
        if "```" in text:
            lines = text.split("\n")
            text = "\n".join(l for l in lines if not l.strip().startswith("```"))
        result = json.loads(text)
        is_dup = bool(result.get("duplicate", False))
        if is_dup:
            # Try to extract which existing fact it matched (use reason field or first match)
            # For now, we'll search through the window to find the best match
            # This is a simplified approach - in production you'd want the LLM to tell you which one
            for existing_fact in window:
                if existing_fact.lower() in result.get("reason", "").lower() or \
                   new_fact.lower() in existing_fact.lower() or \
                   existing_fact.lower() in new_fact.lower():
                    return True, existing_fact
            # If we can't identify the specific match, return the first fact as a fallback
            return True, window[0] if window else None
        return False, None
    except (json.JSONDecodeError, ValueError):
        return False, None


def extract_semantics(
    store: MemoryStore,
    episodes: Optional[List[Episode]] = None,
    model: str = HAIKU_MODEL,
    client=None,
    deduplicate: bool = True,
) -> List[SemanticNode]:
    """
    Extract semantic nodes from unprocessed episodes and persist them.

    Args:
        store:       MemoryStore instance.
        episodes:    Specific episodes to process (default: all unprocessed).
        model:       LLM model for extraction and dedup.
        client:      Optional pre-built boto3 client.
        deduplicate: Whether to skip duplicate facts.

    Returns:
        Newly created SemanticNode objects.
    """
    if episodes is None:
        episodes = store.get_unprocessed_episodes()

    if not episodes:
        return []

    existing_semantics = store.get_all_semantics()
    existing_facts = [s.fact for s in existing_semantics]

    created: List[SemanticNode] = []
    for episode in episodes:
        raw_facts = extract_facts_from_episode(episode, model=model, client=client)
        for fact in raw_facts:
            is_dup, matching_fact = is_duplicate(fact, existing_facts, model=model, client=client)
            if deduplicate and is_dup and matching_fact:
                # Merge: update source_episode_ids on the matching existing node
                # Find the node by the fact string returned by the LLM
                for node in existing_semantics:
                    if node.fact.lower() == matching_fact.lower():
                        if episode.id not in node.source_episode_ids:
                            node.source_episode_ids.append(episode.id)  # type: ignore[arg-type]
                            # Persist the update to the database
                            store.update_semantic(node)
                        break
                continue

            node = SemanticNode(
                fact=fact,
                source_episode_ids=[episode.id] if episode.id else [],
            )
            node = store.add_semantic(node)
            existing_facts.append(fact)
            existing_semantics.append(node)
            created.append(node)

    return created
