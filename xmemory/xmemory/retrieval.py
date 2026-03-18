"""
Top-down retrieval: theme match → semantic select → uncertainty-gated expansion.

Retrieval proceeds in stages:
  1. Theme matching  — Sonnet scores all themes against the query, picks top-k
  2. Semantic select — Within matched themes, Sonnet selects diverse semantics
  3. Uncertainty gate — If confidence is low, expand to episodes then messages

This implements a simplified version of the two-stage retrieval from the
xMemory paper (arXiv:2602.02007), using LLM reranking rather than the full
submodular selection formulation.
"""

from __future__ import annotations

import json
from typing import List, Optional

from xmemory._llm import SONNET_MODEL, call_llm
from xmemory.models import Episode, Message, RetrievalResult, SemanticNode, Theme
from xmemory.store import MemoryStore

# How many themes to consider in stage 1
DEFAULT_TOP_THEMES = 3
# How many semantic nodes to return per theme
DEFAULT_SEMANTICS_PER_THEME = 4
# Confidence threshold below which we expand to episodes/messages
UNCERTAINTY_THRESHOLD = 0.4


def _theme_match_prompt(query: str, themes: List[Theme]) -> str:
    theme_list = "\n".join(
        f"{i+1}. [{t.id}] {t.label} ({len(t.semantic_ids)} facts)"
        for i, t in enumerate(themes)
    )
    return (
        "You are a memory retrieval system. Given a query, rank the themes by relevance.\n\n"
        f"Query: {query}\n\n"
        f"Available themes:\n{theme_list}\n\n"
        "Return JSON: {\"ranked_theme_ids\": [id1, id2, ...], \"confidence\": 0.0-1.0}\n"
        "Include only relevant themes (skip irrelevant ones). Confidence = how well "
        "the themes cover the query.\n\n"
        "Response:"
    )


def _semantic_select_prompt(
    query: str,
    semantics: List[SemanticNode],
    max_select: int,
) -> str:
    facts_list = "\n".join(
        f"{i+1}. [{s.id}] {s.fact}"
        for i, s in enumerate(semantics)
    )
    return (
        "You are selecting the most relevant and diverse facts to answer a query.\n\n"
        f"Query: {query}\n\n"
        f"Available facts:\n{facts_list}\n\n"
        f"Select up to {max_select} facts that are:\n"
        "- Directly relevant to the query\n"
        "- Diverse (not redundant with each other)\n\n"
        "Return JSON: {\"selected_ids\": [id1, id2, ...], \"confidence\": 0.0-1.0}\n"
        "Confidence = how confident you are these facts fully answer the query.\n\n"
        "Response:"
    )


def _uncertainty_prompt(
    query: str,
    current_context: str,
) -> str:
    return (
        "You are evaluating whether the current context is sufficient to answer a query.\n\n"
        f"Query: {query}\n\n"
        f"Current context:\n{current_context}\n\n"
        "Is this context sufficient to answer the query, or do you need more detail?\n"
        "Return JSON: {\"sufficient\": true/false, \"confidence\": 0.0-1.0, "
        "\"reason\": \"brief explanation\"}\n\n"
        "Response:"
    )


def _parse_json_response(response: str) -> dict:
    """Parse a JSON response, stripping markdown fences if present."""
    text = response.strip()
    if "```" in text:
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```"))
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


def match_themes(
    query: str,
    themes: List[Theme],
    top_k: int = DEFAULT_TOP_THEMES,
    model: str = SONNET_MODEL,
    client=None,
) -> tuple[List[Theme], float]:
    """
    Use Sonnet to rank and select top-k relevant themes.

    Returns:
        (selected_themes, confidence_score)
    """
    if not themes:
        return [], 0.0

    prompt = _theme_match_prompt(query, themes)
    response = call_llm(prompt, model=model, max_tokens=256, client=client)
    data = _parse_json_response(response)

    # Check if parsing succeeded
    if not data or "ranked_theme_ids" not in data:
        # Parse failure → fallback to first top_k themes
        return themes[:top_k], 0.5

    ranked_ids = data.get("ranked_theme_ids", [])
    confidence = float(data.get("confidence", 0.5))

    # Map IDs back to Theme objects
    theme_by_id = {t.id: t for t in themes}
    selected = [theme_by_id[tid] for tid in ranked_ids if tid in theme_by_id]

    # If LLM returned empty list (no relevant themes), respect that decision
    # Don't fallback - return empty list
    return selected[:top_k], confidence


def select_semantics(
    query: str,
    semantics: List[SemanticNode],
    max_select: int = DEFAULT_SEMANTICS_PER_THEME,
    model: str = SONNET_MODEL,
    client=None,
) -> tuple[List[SemanticNode], float]:
    """
    Use Sonnet to select diverse, relevant semantic nodes.

    Returns:
        (selected_semantics, confidence_score)
    """
    if not semantics:
        return [], 0.0

    prompt = _semantic_select_prompt(query, semantics, max_select)
    response = call_llm(prompt, model=model, max_tokens=256, client=client)
    data = _parse_json_response(response)

    selected_ids = data.get("selected_ids", [])
    confidence = float(data.get("confidence", 0.5))

    sem_by_id = {s.id: s for s in semantics}
    selected = [sem_by_id[sid] for sid in selected_ids if sid in sem_by_id]

    # Fallback
    if not selected:
        selected = semantics[:max_select]

    return selected[:max_select], confidence


def check_uncertainty(
    query: str,
    current_context: str,
    model: str = SONNET_MODEL,
    client=None,
) -> tuple[bool, float]:
    """
    Ask Sonnet whether the current context is sufficient.

    Returns:
        (is_sufficient, confidence)
    """
    prompt = _uncertainty_prompt(query, current_context)
    response = call_llm(prompt, model=model, max_tokens=128, client=client)
    data = _parse_json_response(response)
    sufficient = bool(data.get("sufficient", True))
    confidence = float(data.get("confidence", 0.5))
    return sufficient, confidence


class MemoryRetriever:
    """
    Top-down retrieval from the xMemory hierarchy.

    Stage 1: Select relevant themes via Sonnet reranking
    Stage 2: Select diverse semantics from matched themes
    Stage 3: Optionally expand to episodes/messages if uncertain
    """

    def __init__(
        self,
        store: MemoryStore,
        model: str = SONNET_MODEL,
        client=None,
        top_themes: int = DEFAULT_TOP_THEMES,
        semantics_per_theme: int = DEFAULT_SEMANTICS_PER_THEME,
        expand_on_uncertainty: bool = True,
        uncertainty_threshold: float = UNCERTAINTY_THRESHOLD,
    ) -> None:
        self.store = store
        self.model = model
        self.client = client
        self.top_themes = top_themes
        self.semantics_per_theme = semantics_per_theme
        self.expand_on_uncertainty = expand_on_uncertainty
        self.uncertainty_threshold = uncertainty_threshold

    def retrieve(self, query: str) -> RetrievalResult:
        """
        Execute top-down retrieval for the given query.

        Returns a RetrievalResult with themes, semantics, and optionally
        episodes/messages if uncertainty gating triggers expansion.
        """
        result = RetrievalResult(query=query)
        all_themes = self.store.get_all_themes()

        if not all_themes:
            # No themes built yet — fall back to episodes or messages
            all_episodes = self.store.get_all_episodes()
            if all_episodes:
                # Use existing episodes
                result.episodes = all_episodes[:20]
                result.retrieval_level = "episode"
            else:
                # Fall back to all messages (not just unprocessed)
                unprocessed = self.store.get_unprocessed_messages()
                if unprocessed:
                    result.messages = self.store.get_messages_by_ids(
                        [m.id for m in unprocessed[:20] if m.id is not None]
                    )
                else:
                    # If no unprocessed messages, get all recent messages
                    # This handles the case where messages are episodized but not themed
                    all_msg_ids = []
                    for ep in self.store.get_all_episodes()[:20]:
                        all_msg_ids.extend(ep.message_ids)
                    if all_msg_ids:
                        result.messages = self.store.get_messages_by_ids(all_msg_ids[:20])
                result.retrieval_level = "message"
            self._log(result)
            return result

        # Stage 1: Theme matching
        matched_themes, theme_confidence = match_themes(
            query,
            all_themes,
            top_k=self.top_themes,
            model=self.model,
            client=self.client,
        )
        result.themes = matched_themes
        result.retrieval_level = "theme"

        if not matched_themes:
            self._log(result)
            return result

        # Stage 2: Semantic selection across matched themes
        all_sem_ids = [
            sid for theme in matched_themes for sid in theme.semantic_ids
        ]
        candidate_semantics = self.store.get_semantics_by_ids(all_sem_ids)
        selected_sems, sem_confidence = select_semantics(
            query,
            candidate_semantics,
            max_select=self.semantics_per_theme * len(matched_themes),
            model=self.model,
            client=self.client,
        )
        result.semantics = selected_sems
        result.retrieval_level = "semantic"

        if not self.expand_on_uncertainty:
            self._log(result)
            return result

        # Stage 3: Uncertainty-gated expansion
        if sem_confidence < self.uncertainty_threshold:
            result = self._expand_to_episodes(query, result)

        self._log(result)
        return result

    def _expand_to_episodes(self, query: str, result: RetrievalResult) -> RetrievalResult:
        """Expand retrieval to include episode summaries."""
        episode_ids = set()
        for sem in result.semantics:
            for eid in sem.source_episode_ids:
                episode_ids.add(eid)

        if episode_ids:
            result.episodes = self.store.get_episodes_by_ids(list(episode_ids))
            result.retrieval_level = "episode"

            # Check again if we need raw messages
            context = result.to_context_string()
            sufficient, _ = check_uncertainty(
                query, context, model=self.model, client=self.client
            )
            if not sufficient:
                result = self._expand_to_messages(result)

        return result

    def _expand_to_messages(self, result: RetrievalResult) -> RetrievalResult:
        """Expand retrieval to include raw messages from source episodes."""
        msg_ids = set()
        for episode in result.episodes:
            for mid in episode.message_ids:
                msg_ids.add(mid)

        if msg_ids:
            result.messages = self.store.get_messages_by_ids(list(msg_ids))
            result.retrieval_level = "message"

        return result

    def _log(self, result: RetrievalResult) -> None:
        """Log the retrieval to the audit table."""
        all_ids = (
            [t.id for t in result.themes if t.id]
            + [s.id for s in result.semantics if s.id]
            + [e.id for e in result.episodes if e.id]
            + [m.id for m in result.messages if m.id]
        )
        self.store.log_retrieval(result.query, all_ids, result.retrieval_level)
        result.total_tokens = result.token_estimate()
