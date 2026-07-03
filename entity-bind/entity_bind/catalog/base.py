"""
Entity Catalog Base Interface

Defines the Catalog interface and provides static (JSON/SQLite) and
dynamic (function-based with TTL cache) implementations.
"""

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .schema import Entity, EntityType, ToolSpec


# ============================================================================
# Catalog Interface
# ============================================================================


class Catalog(ABC):
    """
    Base interface for entity catalogs.

    Catalogs provide entity lookup by ID and type-filtered retrieval
    for candidate generation. Implementations can be static (JSON, SQLite)
    or dynamic (live API calls with caching).
    """

    @abstractmethod
    def get(self, entity_id: str) -> Optional[Entity]:
        """Get entity by canonical ID."""
        pass

    @abstractmethod
    def find_by_type(self, entity_type: Union[EntityType, str]) -> List[Entity]:
        """Find all entities of a given type."""
        pass

    @abstractmethod
    def all(self) -> List[Entity]:
        """Get all entities in the catalog."""
        pass

    def get_many(self, entity_ids: List[str]) -> List[Entity]:
        """Get multiple entities by ID (default implementation)."""
        entities = []
        for eid in entity_ids:
            entity = self.get(eid)
            if entity:
                entities.append(entity)
        return entities


# ============================================================================
# Static Catalog (JSON)
# ============================================================================


class StaticCatalog(Catalog):
    """
    Static catalog loaded from JSON or a list of entity dicts.

    Fast, deterministic, ideal for demos and benchmarks.
    No network calls, no staleness - but requires manual updates.
    """

    def __init__(
        self,
        entities: Optional[Union[List[Dict[str, Any]], List[Entity]]] = None,
        json_path: Optional[Union[str, Path]] = None
    ):
        """
        Initialize from entities list or JSON file.

        Args:
            entities: List of entity dicts or Entity objects
            json_path: Path to JSON file containing entity list
        """
        self._entities: Dict[str, Entity] = {}
        self._type_index: Dict[str, List[str]] = {}

        if json_path:
            self._load_from_json(json_path)
        elif entities:
            self._load_from_list(entities)

    def _load_from_json(self, json_path: Union[str, Path]) -> None:
        """Load entities from JSON file."""
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Catalog JSON not found: {json_path}")

        with open(path, 'r') as f:
            data = json.load(f)

        # Support both {"entities": [...]} and plain [...]
        if isinstance(data, dict) and 'entities' in data:
            entities_data = data['entities']
        elif isinstance(data, list):
            entities_data = data
        else:
            raise ValueError(f"Invalid JSON format in {json_path}")

        self._load_from_list(entities_data)

    def _load_from_list(self, entities: List[Union[Dict[str, Any], Entity]]) -> None:
        """Load entities from list of dicts or Entity objects."""
        for item in entities:
            if isinstance(item, Entity):
                entity = item
            else:
                entity = Entity(**item)

            self._entities[entity.id] = entity

            # Build type index
            entity_type = str(entity.type)
            if entity_type not in self._type_index:
                self._type_index[entity_type] = []
            self._type_index[entity_type].append(entity.id)

    def get(self, entity_id: str) -> Optional[Entity]:
        """Get entity by canonical ID."""
        return self._entities.get(entity_id)

    def find_by_type(self, entity_type: Union[EntityType, str]) -> List[Entity]:
        """Find all entities of a given type."""
        entity_type_str = str(entity_type).lower()
        entity_ids = self._type_index.get(entity_type_str, [])
        return [self._entities[eid] for eid in entity_ids]

    def all(self) -> List[Entity]:
        """Get all entities in the catalog."""
        return list(self._entities.values())

    def add(self, entity: Entity) -> None:
        """Add or update an entity."""
        self._entities[entity.id] = entity

        entity_type = str(entity.type)
        if entity_type not in self._type_index:
            self._type_index[entity_type] = []
        if entity.id not in self._type_index[entity_type]:
            self._type_index[entity_type].append(entity.id)

    def remove(self, entity_id: str) -> bool:
        """Remove an entity. Returns True if found and removed."""
        if entity_id not in self._entities:
            return False

        entity = self._entities.pop(entity_id)
        entity_type = str(entity.type)
        if entity_type in self._type_index:
            try:
                self._type_index[entity_type].remove(entity_id)
            except ValueError:
                pass

        return True

    def save_to_json(self, json_path: Union[str, Path]) -> None:
        """Save catalog to JSON file."""
        entities_data = [
            entity.model_dump(exclude_none=True)
            for entity in self._entities.values()
        ]

        with open(json_path, 'w') as f:
            json.dump({"entities": entities_data}, f, indent=2)

    def __len__(self) -> int:
        return len(self._entities)


# ============================================================================
# SQLite Catalog
# ============================================================================


class SQLiteCatalog(Catalog):
    """
    Static catalog backed by SQLite.

    Provides indexed lookups for large catalogs (thousands of entities).
    Useful for production static catalogs that exceed memory constraints.
    """

    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize SQLite catalog.

        Args:
            db_path: Path to SQLite database file (created if missing)
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create entities table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_type ON entities(type)
        """)
        self.conn.commit()

    def get(self, entity_id: str) -> Optional[Entity]:
        """Get entity by canonical ID."""
        cursor = self.conn.execute(
            "SELECT data FROM entities WHERE id = ?",
            (entity_id,)
        )
        row = cursor.fetchone()
        if row:
            return Entity(**json.loads(row['data']))
        return None

    def find_by_type(self, entity_type: Union[EntityType, str]) -> List[Entity]:
        """Find all entities of a given type."""
        entity_type_str = str(entity_type).lower()
        cursor = self.conn.execute(
            "SELECT data FROM entities WHERE type = ?",
            (entity_type_str,)
        )
        return [Entity(**json.loads(row['data'])) for row in cursor.fetchall()]

    def all(self) -> List[Entity]:
        """Get all entities in the catalog."""
        cursor = self.conn.execute("SELECT data FROM entities")
        return [Entity(**json.loads(row['data'])) for row in cursor.fetchall()]

    def add(self, entity: Entity) -> None:
        """Add or update an entity."""
        data = json.dumps(entity.model_dump(exclude_none=True))
        self.conn.execute(
            "INSERT OR REPLACE INTO entities (id, type, data) VALUES (?, ?, ?)",
            (entity.id, str(entity.type), data)
        )
        self.conn.commit()

    def add_many(self, entities: List[Entity]) -> None:
        """Bulk insert entities."""
        data = [
            (e.id, str(e.type), json.dumps(e.model_dump(exclude_none=True)))
            for e in entities
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO entities (id, type, data) VALUES (?, ?, ?)",
            data
        )
        self.conn.commit()

    def remove(self, entity_id: str) -> bool:
        """Remove an entity. Returns True if found and removed."""
        cursor = self.conn.execute(
            "DELETE FROM entities WHERE id = ?",
            (entity_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __len__(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM entities")
        return cursor.fetchone()['count']

    def __del__(self):
        """Ensure connection is closed."""
        if hasattr(self, 'conn'):
            self.conn.close()


# ============================================================================
# Dynamic Catalog with TTL Cache
# ============================================================================


class DynamicCatalog(Catalog):
    """
    Dynamic catalog that queries a live backend with TTL caching.

    Useful for production where entities come from live APIs
    (Slack directory, filesystem, database). Caches lookups to avoid
    repeated API hits while allowing stale data to refresh.
    """

    def __init__(
        self,
        fetch_fn: Callable[[Optional[str]], List[Entity]],
        ttl_seconds: int = 300
    ):
        """
        Initialize dynamic catalog.

        Args:
            fetch_fn: Function that fetches entities from live backend.
                      Signature: (entity_type: Optional[str]) -> List[Entity]
                      If entity_type is None, fetch all entities.
            ttl_seconds: Cache TTL in seconds (default 5 minutes)
        """
        self.fetch_fn = fetch_fn
        self.ttl_seconds = ttl_seconds

        # Cache: {cache_key: (entities, expiry_time)}
        self._cache: Dict[str, tuple[List[Entity], float]] = {}

    def _get_cache_key(self, entity_type: Optional[str] = None) -> str:
        """Generate cache key."""
        return entity_type or "__all__"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache:
            return False
        _, expiry = self._cache[cache_key]
        return time.time() < expiry

    def _set_cache(self, cache_key: str, entities: List[Entity]) -> None:
        """Store entities in cache."""
        expiry = time.time() + self.ttl_seconds
        self._cache[cache_key] = (entities, expiry)

    def _fetch_with_cache(self, entity_type: Optional[str] = None) -> List[Entity]:
        """Fetch entities with caching."""
        cache_key = self._get_cache_key(entity_type)

        if self._is_cache_valid(cache_key):
            entities, _ = self._cache[cache_key]
            return entities

        # Cache miss - fetch from backend
        entities = self.fetch_fn(entity_type)
        self._set_cache(cache_key, entities)
        return entities

    def get(self, entity_id: str) -> Optional[Entity]:
        """Get entity by canonical ID."""
        # Try all cached types first
        for entities, _ in self._cache.values():
            for entity in entities:
                if entity.id == entity_id:
                    return entity

        # Cache miss - fetch all and search
        all_entities = self._fetch_with_cache(None)
        for entity in all_entities:
            if entity.id == entity_id:
                return entity

        return None

    def find_by_type(self, entity_type: Union[EntityType, str]) -> List[Entity]:
        """Find all entities of a given type."""
        entity_type_str = str(entity_type).lower()
        return self._fetch_with_cache(entity_type_str)

    def all(self) -> List[Entity]:
        """Get all entities in the catalog."""
        return self._fetch_with_cache(None)

    def clear_cache(self) -> None:
        """Clear all cached entities."""
        self._cache.clear()


# ============================================================================
# Catalog Factory
# ============================================================================


def create_catalog(
    source: Union[str, Path, List[Dict], List[Entity], Callable],
    catalog_type: str = "auto",
    **kwargs
) -> Catalog:
    """
    Factory function to create a catalog from various sources.

    Args:
        source: JSON path, SQLite path, entity list, or fetch function
        catalog_type: "auto", "json", "sqlite", or "dynamic"
        **kwargs: Additional arguments for catalog constructor

    Returns:
        Catalog instance
    """
    if catalog_type == "auto":
        if callable(source):
            catalog_type = "dynamic"
        elif isinstance(source, (str, Path)):
            path = Path(source)
            if path.suffix == '.db':
                catalog_type = "sqlite"
            else:
                catalog_type = "json"
        elif isinstance(source, list):
            catalog_type = "json"
        else:
            raise ValueError(f"Cannot infer catalog type from source: {type(source)}")

    if catalog_type == "json":
        if isinstance(source, (str, Path)):
            return StaticCatalog(json_path=source, **kwargs)
        elif isinstance(source, list):
            return StaticCatalog(entities=source, **kwargs)
        else:
            raise ValueError(f"Invalid source for JSON catalog: {type(source)}")

    elif catalog_type == "sqlite":
        if not isinstance(source, (str, Path)):
            raise ValueError(f"SQLite catalog requires path, got {type(source)}")
        return SQLiteCatalog(db_path=source, **kwargs)

    elif catalog_type == "dynamic":
        if not callable(source):
            raise ValueError(f"Dynamic catalog requires callable, got {type(source)}")
        return DynamicCatalog(fetch_fn=source, **kwargs)

    else:
        raise ValueError(f"Unknown catalog type: {catalog_type}")
