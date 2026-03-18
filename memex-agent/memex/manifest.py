"""
manifest.py — JSON index manifest for human-readable experience index.

Format:
    {
        "entries": {
            "[project:topic-slug]": {
                "summary": "...",
                "archived_at": "2026-03-09T14:30:00Z",
                "tokens_saved": 1847
            }
        }
    }
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional


class IndexManifest:
    """Human-readable JSON manifest that maps index keys to experience metadata."""

    def __init__(self, manifest_path: str = "memex_manifest.json"):
        self.manifest_path = manifest_path
        self._data: dict = {"entries": {}}
        self._load()

    def _load(self):
        """Load manifest from disk if it exists."""
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                try:
                    self._data = json.load(f)
                except json.JSONDecodeError:
                    self._data = {"entries": {}}
        if "entries" not in self._data:
            self._data["entries"] = {}

    def _save(self):
        """Persist manifest to disk."""
        os.makedirs(
            os.path.dirname(self.manifest_path) if os.path.dirname(self.manifest_path) else ".",
            exist_ok=True,
        )
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def add_entry(
        self,
        key: str,
        summary: str,
        tokens_saved: int = 0,
        archived_at: Optional[str] = None,
    ) -> None:
        """Add or update a manifest entry."""
        if archived_at is None:
            archived_at = datetime.now(timezone.utc).isoformat()
        self._data["entries"][key] = {
            "summary": summary,
            "archived_at": archived_at,
            "tokens_saved": tokens_saved,
        }
        self._save()

    def get_entry(self, key: str) -> Optional[dict]:
        """Return manifest entry for key, or None."""
        return self._data["entries"].get(key)

    def list_entries(self) -> dict:
        """Return all entries."""
        return dict(self._data["entries"])

    def remove_entry(self, key: str) -> bool:
        """Remove an entry from the manifest. Returns True if found."""
        if key in self._data["entries"]:
            del self._data["entries"][key]
            self._save()
            return True
        return False

    def summary_for(self, key: str) -> Optional[str]:
        """Convenience: return just the summary text for a key."""
        entry = self.get_entry(key)
        return entry["summary"] if entry else None

    def format_index_block(self, key: str) -> str:
        """
        Format an index entry as a compact block suitable for inclusion
        in an agent's working context.

        Example:
            [research:oauth-libs]
            Summary: Found 3 OAuth2 libraries. Selected requests-oauthlib for...
            Archived: 2026-03-09T14:30:00Z | Tokens saved: 1,847
        """
        entry = self.get_entry(key)
        if entry is None:
            return f"[{key}] — not found in manifest"
        return (
            f"{key}\n"
            f"Summary: {entry['summary']}\n"
            f"Archived: {entry['archived_at']} | Tokens saved: {entry.get('tokens_saved', 0):,}"
        )

    @property
    def total_tokens_saved(self) -> int:
        return sum(e.get("tokens_saved", 0) for e in self._data["entries"].values())

    def __len__(self) -> int:
        return len(self._data["entries"])

    def __repr__(self) -> str:
        return f"IndexManifest({self.manifest_path!r}, {len(self)} entries)"
