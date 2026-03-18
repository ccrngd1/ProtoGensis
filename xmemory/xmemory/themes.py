"""
Theme clustering: group semantic nodes by topic using Haiku.

Semantics are presented to Haiku in batches. Haiku assigns each fact to a
theme label. Facts sharing the same label are grouped into a Theme. If a
matching theme already exists (by label, case-insensitive), new semantics are
merged into it rather than creating a duplicate.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from xmemory._llm import HAIKU_MODEL, call_llm
from xmemory.models import SemanticNode, Theme
from xmemory.store import MemoryStore

# Maximum semantics to cluster in a single LLM call
CLUSTER_BATCH = 40


def _cluster_prompt(facts: List[str]) -> str:
    numbered = "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))
    return (
        "You are clustering facts for a memory system. Group the following facts into "
        "thematic categories.\n\n"
        "Rules:\n"
        "- Use 3-8 themes maximum\n"
        "- Theme labels should be 2-5 words, descriptive\n"
        "- Every fact must be assigned to exactly one theme\n"
        "- Return ONLY valid JSON: {\"assignments\": [[fact_index, \"Theme Label\"], ...]}\n"
        "  where fact_index is 1-based\n\n"
        f"Facts:\n{numbered}\n\n"
        "Assignments (JSON):"
    )


def cluster_semantics_batch(
    nodes: List[SemanticNode],
    model: str = HAIKU_MODEL,
    client=None,
) -> Dict[str, List[int]]:
    """
    Ask Haiku to cluster a batch of semantic nodes into themes.

    Returns:
        Dict mapping theme label → list of semantic node IDs.
    """
    facts = [n.fact for n in nodes]
    prompt = _cluster_prompt(facts)
    response = call_llm(prompt, model=model, max_tokens=1024, client=client).strip()

    # Parse JSON
    try:
        text = response
        if "```" in text:
            lines = text.split("\n")
            text = "\n".join(l for l in lines if not l.strip().startswith("```"))
        data = json.loads(text)
        assignments = data.get("assignments", [])
    except (json.JSONDecodeError, ValueError):
        # Fallback: everything goes into one theme
        return {"General": [n.id for n in nodes if n.id is not None]}

    theme_map: Dict[str, List[int]] = {}
    for item in assignments:
        if len(item) < 2:
            continue
        idx = int(item[0]) - 1  # convert to 0-based
        label = str(item[1]).strip()
        if 0 <= idx < len(nodes) and nodes[idx].id is not None:
            theme_map.setdefault(label, []).append(nodes[idx].id)  # type: ignore[arg-type]

    # Catch any nodes that weren't assigned
    assigned_ids = {nid for ids in theme_map.values() for nid in ids}
    for node in nodes:
        if node.id not in assigned_ids:
            theme_map.setdefault("Miscellaneous", []).append(node.id)  # type: ignore[arg-type]

    return theme_map


def cluster_themes(
    store: MemoryStore,
    nodes: Optional[List[SemanticNode]] = None,
    model: str = HAIKU_MODEL,
    client=None,
) -> List[Theme]:
    """
    Group unthemed semantic nodes into themes and persist them.

    New nodes are merged into existing themes when the label matches
    (case-insensitive), otherwise a new Theme row is created.

    Args:
        store:  MemoryStore instance.
        nodes:  Specific semantic nodes to cluster (default: all unthemed).
        model:  LLM model for clustering.
        client: Optional pre-built boto3 client.

    Returns:
        All Theme objects that were created or updated.
    """
    if nodes is None:
        nodes = store.get_unthemed_semantics()

    if not nodes:
        return []

    # Load existing themes for merging
    existing_themes = store.get_all_themes()
    theme_by_label: Dict[str, Theme] = {
        t.label.lower(): t for t in existing_themes
    }

    touched: List[Theme] = []

    # Process in batches
    for start in range(0, len(nodes), CLUSTER_BATCH):
        batch = nodes[start : start + CLUSTER_BATCH]
        assignments = cluster_semantics_batch(batch, model=model, client=client)

        for label, sem_ids in assignments.items():
            key = label.lower()
            if key in theme_by_label:
                # Merge into existing theme
                theme = theme_by_label[key]
                for sid in sem_ids:
                    if sid not in theme.semantic_ids:
                        theme.semantic_ids.append(sid)
                theme = store.update_theme(theme)
            else:
                # Create new theme
                theme = Theme(label=label, semantic_ids=sem_ids)
                theme = store.add_theme(theme)
                theme_by_label[key] = theme

            if theme not in touched:
                touched.append(theme)

    return touched
