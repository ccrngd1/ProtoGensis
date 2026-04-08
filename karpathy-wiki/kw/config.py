"""Configuration management for karpathy-wiki."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml


DEFAULT_CONFIG = {
    "llm": {
        "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "region": "us-east-1",
        "max_tokens": 4096,
        "temperature": 1.0,
    },
    "paths": {
        "raw": "raw",
        "wiki": "wiki",
        "db": "kb.db",
    },
    "compile": {
        "auto_index_update": True,
        "max_articles_per_source": 5,
    },
}


class Config:
    """Knowledge base configuration."""

    def __init__(self, kb_root: Path):
        """Initialize configuration.

        Args:
            kb_root: Root path of the knowledge base
        """
        self.kb_root = Path(kb_root)
        self.config_path = self.kb_root / "kb.toml"
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from kb.toml or use defaults."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                user_config = yaml.safe_load(f) or {}
            # Merge with defaults
            config = DEFAULT_CONFIG.copy()
            for section, values in user_config.items():
                if section in config:
                    config[section].update(values)
                else:
                    config[section] = values
            return config
        return DEFAULT_CONFIG.copy()

    def save(self):
        """Save current configuration to kb.toml."""
        with open(self.config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    @property
    def raw_dir(self) -> Path:
        """Path to raw/ directory."""
        return self.kb_root / self._config["paths"]["raw"]

    @property
    def wiki_dir(self) -> Path:
        """Path to wiki/ directory."""
        return self.kb_root / self._config["paths"]["wiki"]

    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.kb_root / self._config["paths"]["db"]

    @property
    def index_path(self) -> Path:
        """Path to wiki index."""
        return self.wiki_dir / "index.md"

    @property
    def llm_model(self) -> str:
        """LLM model identifier."""
        return self._config["llm"]["model"]

    @property
    def llm_region(self) -> str:
        """AWS region for Bedrock."""
        return self._config["llm"]["region"]

    @property
    def llm_max_tokens(self) -> int:
        """Maximum tokens for LLM responses."""
        return self._config["llm"]["max_tokens"]

    @property
    def llm_temperature(self) -> float:
        """Temperature for LLM responses."""
        return self._config["llm"]["temperature"]

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key."""
        parts = key.split(".")
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set configuration value by dot-notation key."""
        parts = key.split(".")
        config = self._config
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value


def find_kb_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find knowledge base root by looking for kb.db.

    Args:
        start_path: Path to start searching from (defaults to cwd)

    Returns:
        Path to knowledge base root, or None if not found
    """
    current = start_path or Path.cwd()

    # Check current directory and parents
    for path in [current] + list(current.parents):
        if (path / "kb.db").exists():
            return path

    return None
