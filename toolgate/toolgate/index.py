"""Tool indexing with sentence-transformers and FAISS."""

import numpy as np
from typing import Dict, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
import faiss

from toolgate.config import IndexConfig
from toolgate.schemas import MCPTool, IndexedTool


class ToolIndex:
    """Semantic search index for tools using FAISS."""

    def __init__(self, config: IndexConfig):
        self.config = config
        self.model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.Index] = None
        self.tools: List[IndexedTool] = []
        self.tool_map: Dict[str, IndexedTool] = {}

    def _load_model(self) -> SentenceTransformer:
        """Load sentence transformer model."""
        if self.model is None:
            cache_dir = self.config.cache_dir
            self.model = SentenceTransformer(
                self.config.model_name,
                cache_folder=cache_dir
            )
        return self.model

    def _create_embedding(self, text: str) -> np.ndarray:
        """Create embedding vector for text."""
        model = self._load_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """Normalize vectors for cosine similarity."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)  # Avoid division by zero
        return vectors / norms

    def build_index(
        self,
        tools: List[MCPTool],
        server_names: List[str],
    ) -> None:
        """
        Build FAISS index from tools.

        Args:
            tools: List of MCPTool objects to index
            server_names: Corresponding server names for each tool
        """
        if len(tools) != len(server_names):
            raise ValueError("tools and server_names must have same length")

        if not tools:
            raise ValueError("Cannot build index with empty tool list")

        # Create embeddings
        texts = []
        indexed_tools = []

        for tool, server_name in zip(tools, server_names):
            # Combine name and description for embedding
            text = f"{tool.name}: {tool.description or ''}"
            texts.append(text)

        # Generate embeddings in batch
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True)

        # Create IndexedTool objects
        for tool, server_name, embedding in zip(tools, server_names, embeddings):
            indexed_tool = IndexedTool(
                name=tool.name,
                description=tool.description or "",
                embedding=embedding.tolist(),
                server_name=server_name,
                full_tool=tool,
            )
            indexed_tools.append(indexed_tool)

        self.tools = indexed_tools
        self.tool_map = {tool.name: tool for tool in indexed_tools}

        # Build FAISS index
        dimension = embeddings.shape[1]

        if self.config.similarity_metric == "cosine":
            # For cosine similarity, normalize vectors and use inner product
            embeddings = self._normalize_vectors(embeddings)
            self.index = faiss.IndexFlatIP(dimension)
        elif self.config.similarity_metric == "euclidean":
            self.index = faiss.IndexFlatL2(dimension)
        else:  # dot product
            self.index = faiss.IndexFlatIP(dimension)

        # Add vectors to index
        self.index.add(embeddings.astype(np.float32))

    def search(
        self,
        query: str,
        k: int = 10,
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        Search for relevant tools.

        Args:
            query: Search query text
            k: Number of results to return

        Returns:
            Tuple of (tool_names, scores_dict)
        """
        if self.index is None or len(self.tools) == 0:
            # No index built, return empty results
            return [], {}

        # Limit k to available tools
        k = min(k, len(self.tools))

        try:
            # Create query embedding
            query_embedding = self._create_embedding(query)

            # Normalize for cosine similarity
            if self.config.similarity_metric == "cosine":
                query_embedding = query_embedding / np.linalg.norm(query_embedding)

            # Search
            query_vector = query_embedding.astype(np.float32).reshape(1, -1)
            distances, indices = self.index.search(query_vector, k)

            # Extract results
            tool_names = []
            scores = {}

            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.tools):
                    tool = self.tools[idx]
                    tool_names.append(tool.name)

                    # Convert distance to similarity score [0, 1]
                    if self.config.similarity_metric == "cosine":
                        # Cosine similarity is already in [-1, 1], map to [0, 1]
                        score = (float(distance) + 1.0) / 2.0
                    elif self.config.similarity_metric == "euclidean":
                        # L2 distance: lower is better, convert to similarity
                        score = 1.0 / (1.0 + float(distance))
                    else:
                        # Dot product: use as-is
                        score = float(distance)

                    scores[tool.name] = score

            return tool_names, scores

        except Exception as e:
            # On error, return empty results (safe degradation)
            return [], {}

    def get_tool(self, name: str) -> Optional[IndexedTool]:
        """Get tool by name."""
        return self.tool_map.get(name)

    def get_all_tool_names(self) -> List[str]:
        """Get all indexed tool names."""
        return [tool.name for tool in self.tools]

    def get_all_tools(self) -> List[MCPTool]:
        """Get all indexed tools as MCPTool objects."""
        return [tool.full_tool for tool in self.tools]

    @property
    def size(self) -> int:
        """Get number of indexed tools."""
        return len(self.tools)
