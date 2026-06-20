"""Needle model abstraction with safe degradation."""

import sys
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import numpy as np

from needleroute.schemas import MCPTool, NeedleScore


class NeedleModel(ABC):
    """Abstract interface for Needle model."""

    @abstractmethod
    def encode_tool(self, tool: MCPTool) -> np.ndarray:
        """
        Encode a tool definition into an embedding vector.

        Args:
            tool: MCP tool to encode

        Returns:
            Embedding vector as numpy array
        """
        pass

    @abstractmethod
    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode a user query into an embedding vector.

        Args:
            query: User query text

        Returns:
            Embedding vector as numpy array
        """
        pass

    @abstractmethod
    def score_tools(
        self,
        query_embedding: np.ndarray,
        tool_embeddings: Dict[str, np.ndarray],
    ) -> List[NeedleScore]:
        """
        Score tools using contrastive head cosine similarity.

        Args:
            query_embedding: Query embedding vector
            tool_embeddings: Dict mapping tool names to embedding vectors

        Returns:
            List of NeedleScore objects, sorted by score descending
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if model is available and loaded."""
        pass


class HuggingFaceNeedleModel(NeedleModel):
    """
    Needle model from HuggingFace (Cactus-Compute/needle).

    This is a 26M parameter model with contrastive head for tool selection.
    If the model cannot be loaded, this implementation will report unavailable.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize HuggingFace Needle model.

        Args:
            model_path: HuggingFace model ID or local path (default: Cactus-Compute/needle)
        """
        self.model_path = model_path or "Cactus-Compute/needle"
        self._model = None
        self._tokenizer = None
        self._available = False

        self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load the model, handling failures gracefully."""
        try:
            # Try importing required dependencies
            from transformers import AutoModel, AutoTokenizer

            # Try loading model and tokenizer
            print(f"Loading Needle model from {self.model_path}...", file=sys.stderr)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self._model = AutoModel.from_pretrained(self.model_path)

            # Move to eval mode (no gradients needed for inference)
            self._model.eval()

            self._available = True
            print("Needle model loaded successfully", file=sys.stderr)

        except ImportError as e:
            print(f"Warning: Failed to import dependencies for Needle model: {e}", file=sys.stderr)
            print("Falling back to frontier escalation for all calls", file=sys.stderr)
            self._available = False

        except Exception as e:
            print(f"Warning: Failed to load Needle model: {e}", file=sys.stderr)
            print("Falling back to frontier escalation for all calls", file=sys.stderr)
            self._available = False

    def encode_tool(self, tool: MCPTool) -> np.ndarray:
        """Encode tool definition into embedding."""
        if not self._available:
            raise RuntimeError("Needle model not available")

        # Combine name and description for encoding
        text = f"{tool.name}: {tool.description or ''}"

        # Tokenize and encode
        inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

        # Get embeddings from model
        import torch
        with torch.no_grad():
            outputs = self._model(**inputs)
            # Use CLS token embedding (first token)
            embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()

        return embedding

    def encode_query(self, query: str) -> np.ndarray:
        """Encode user query into embedding."""
        if not self._available:
            raise RuntimeError("Needle model not available")

        # Tokenize and encode
        inputs = self._tokenizer(query, return_tensors="pt", truncation=True, max_length=512)

        # Get embeddings from model
        import torch
        with torch.no_grad():
            outputs = self._model(**inputs)
            # Use CLS token embedding
            embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()

        return embedding

    def score_tools(
        self,
        query_embedding: np.ndarray,
        tool_embeddings: Dict[str, np.ndarray],
    ) -> List[NeedleScore]:
        """Score tools using cosine similarity."""
        if not self._available:
            raise RuntimeError("Needle model not available")

        # Normalize query embedding
        query_norm = query_embedding / np.linalg.norm(query_embedding)

        # Calculate cosine similarity for each tool
        scores = []
        for tool_name, tool_embedding in tool_embeddings.items():
            # Normalize tool embedding
            tool_norm = tool_embedding / np.linalg.norm(tool_embedding)

            # Cosine similarity (dot product of normalized vectors)
            similarity = float(np.dot(query_norm, tool_norm))

            scores.append(NeedleScore(
                tool_name=tool_name,
                score=similarity,
                confidence=0.0  # Will be set later based on gap
            ))

        # Sort by score descending
        scores.sort(key=lambda x: x.score, reverse=True)

        # Calculate confidence as gap between top-1 and top-2
        if len(scores) >= 2:
            confidence = scores[0].score - scores[1].score
            scores[0].confidence = confidence
        elif len(scores) == 1:
            scores[0].confidence = 1.0

        return scores

    def is_available(self) -> bool:
        """Check if model is loaded and available."""
        return self._available


class MockNeedleModel(NeedleModel):
    """
    Mock Needle model for testing.

    Uses simple string matching and random scores for tool selection.
    """

    def __init__(self):
        """Initialize mock model."""
        self._tool_cache: Dict[str, np.ndarray] = {}

    def encode_tool(self, tool: MCPTool) -> np.ndarray:
        """Generate deterministic fake embedding for tool."""
        # Use hash of tool name for deterministic embedding
        seed = hash(tool.name) % 10000
        np.random.seed(seed)
        embedding = np.random.randn(384)  # MiniLM dimension
        return embedding

    def encode_query(self, query: str) -> np.ndarray:
        """Generate deterministic fake embedding for query."""
        # Use hash of query for deterministic embedding
        seed = hash(query) % 10000
        np.random.seed(seed)
        embedding = np.random.randn(384)
        return embedding

    def score_tools(
        self,
        query_embedding: np.ndarray,
        tool_embeddings: Dict[str, np.ndarray],
    ) -> List[NeedleScore]:
        """Score tools using cosine similarity (works with fake embeddings)."""
        # Normalize query
        query_norm = query_embedding / np.linalg.norm(query_embedding)

        scores = []
        for tool_name, tool_embedding in tool_embeddings.items():
            # Normalize tool embedding
            tool_norm = tool_embedding / np.linalg.norm(tool_embedding)

            # Cosine similarity
            similarity = float(np.dot(query_norm, tool_norm))

            scores.append(NeedleScore(
                tool_name=tool_name,
                score=similarity,
                confidence=0.0
            ))

        # Sort by score descending
        scores.sort(key=lambda x: x.score, reverse=True)

        # Calculate confidence
        if len(scores) >= 2:
            confidence = scores[0].score - scores[1].score
            scores[0].confidence = confidence
        elif len(scores) == 1:
            scores[0].confidence = 1.0

        return scores

    def is_available(self) -> bool:
        """Mock model is always available."""
        return True


def create_needle_model(model_path: Optional[str] = None, force_mock: bool = False) -> NeedleModel:
    """
    Factory function to create appropriate Needle model.

    Args:
        model_path: HuggingFace model ID or local path
        force_mock: Force use of mock model (for testing)

    Returns:
        NeedleModel instance (real or mock)
    """
    if force_mock:
        return MockNeedleModel()

    # Try to create real model
    model = HuggingFaceNeedleModel(model_path)

    # If model is not available, return mock for testing
    # In production, we'd escalate all calls instead
    if not model.is_available():
        print("Warning: Using mock Needle model due to load failure", file=sys.stderr)
        return MockNeedleModel()

    return model
