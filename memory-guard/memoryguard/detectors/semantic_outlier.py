"""Semantic outlier detection using embedding-based clustering."""

from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class SemanticOutlierDetector:
    """Detects memory entries that are semantically anomalous.

    A legitimate memory store is *topically diverse* by design: it mixes user
    facts, feedback, project notes and references, so any single entry is
    dissimilar from the store *average*. Averaging therefore flags everything.

    Instead we score each entry by its similarity to its *nearest* neighbours
    (the entries it is most like) and flag only those that are statistical
    outliers relative to the rest of the store, using a robust
    median/MAD-based adaptive threshold rather than a brittle fixed cutoff.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        # Number of nearest neighbours to average when scoring cohesion.
        self.n_neighbors = 3
        # How many robust standard deviations below the median counts as an
        # outlier. Higher = more conservative (fewer false positives).
        self.mad_multiplier = 3.0
        # Absolute floor: an entry whose nearest-neighbour similarity is at
        # least this high is never an outlier, regardless of the distribution
        # (guards against flagging in tight, low-variance clusters).
        self.min_neighbor_similarity = 0.30

    def detect(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect semantic outliers in memory entries.

        Returns list of detections with:
        - entry_id: identifier of suspicious entry
        - risk_score: 0-100
        - reason: explanation of detection
        """
        if len(entries) < 3:
            return []

        texts = [self._extract_text(e) for e in entries]
        embeddings = self.model.encode(texts)

        # Cohesion score per entry: mean similarity to its nearest neighbours.
        # An outlier is unlike even the entries it is *most* similar to.
        cohesion = np.empty(len(embeddings))
        for idx, embedding in enumerate(embeddings):
            other_embeddings = np.delete(embeddings, idx, axis=0)
            similarities = cosine_similarity([embedding], other_embeddings)[0]
            k = min(self.n_neighbors, len(similarities))
            top_k = np.sort(similarities)[-k:]
            cohesion[idx] = float(np.mean(top_k))

        # Robust adaptive threshold from the cohesion distribution. MAD scaled
        # by 1.4826 estimates the standard deviation for normal data but is not
        # skewed by the very outliers we are trying to find.
        median = float(np.median(cohesion))
        mad = float(np.median(np.abs(cohesion - median)))
        robust_std = 1.4826 * mad
        threshold = median - self.mad_multiplier * robust_std

        detections = []
        for idx, score in enumerate(cohesion):
            # Flag only entries that are both statistical outliers AND
            # genuinely dissimilar from everything (absolute floor).
            if score < threshold and score < self.min_neighbor_similarity:
                # Risk grows with how far below the threshold the entry sits.
                risk_score = int(min((1 - score) * 100, 100))
                detections.append({
                    "entry_id": entries[idx].get("name", f"entry_{idx}"),
                    "risk_score": risk_score,
                    "category": "semantic_outlier",
                    "reason": (
                        "Semantically isolated from all other memories "
                        f"(nearest-neighbor similarity: {score:.2f}, "
                        f"store threshold: {threshold:.2f})"
                    )
                })

        return detections

    def _extract_text(self, entry: Dict[str, Any]) -> str:
        """Extract text content from memory entry."""
        parts = []
        if "name" in entry:
            parts.append(entry["name"])
        if "description" in entry:
            parts.append(entry["description"])
        if "content" in entry:
            parts.append(entry["content"])
        return " ".join(parts)
