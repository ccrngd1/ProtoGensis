"""FastAPI application factory."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from agents.orchestrator import Orchestrator
from agents.watcher import FileWatcher
from api.routes import router

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(
            db_path=os.getenv("MEMORY_DB_PATH", "memory.db"),
            consolidation_interval=int(os.getenv("CONSOLIDATION_INTERVAL", "300")),
            min_memories_for_consolidation=int(os.getenv("MIN_MEMORIES_CONSOLIDATE", "5")),
            daily_consolidation_interval=int(os.getenv("DAILY_CONSOLIDATION_INTERVAL", "86400")),
            enable_startup_consolidation=os.getenv("ENABLE_STARTUP_CONSOLIDATION", "true").lower() in ("true", "1", "yes"),
            enable_daily_consolidation=os.getenv("ENABLE_DAILY_CONSOLIDATION", "true").lower() in ("true", "1", "yes"),
            max_memories_query=int(os.getenv("MAX_MEMORIES_QUERY", "400")),
        )
    return _orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    orc = get_orchestrator()
    orc.start_background_consolidation()
    app.state.orchestrator = orc

    # Start file watcher if enabled
    watcher = None
    if os.getenv("ENABLE_FILE_WATCHER", "false").lower() in ("true", "1", "yes"):
        watch_dir = Path(os.getenv("WATCH_DIR", "./inbox"))
        poll_interval = int(os.getenv("WATCH_POLL_INTERVAL", "60"))  # 1 min default
        change_detection_interval = int(os.getenv("WATCH_CHANGE_DETECTION_INTERVAL", "1800"))  # 30 min default
        recursive = os.getenv("WATCH_RECURSIVE", "false").lower() in ("true", "1", "yes")
        track_changes = os.getenv("WATCH_TRACK_CHANGES", "true").lower() in ("true", "1", "yes")

        # Parse ignore_dirs from comma-separated env var
        ignore_dirs_str = os.getenv("WATCH_IGNORE_DIRS", ".obsidian,.git,node_modules,.venv,__pycache__")
        ignore_dirs = set(d.strip() for d in ignore_dirs_str.split(",") if d.strip())

        watcher = FileWatcher(
            orc,
            watch_dir,
            poll_interval,
            recursive=recursive,
            track_changes=track_changes,
            change_detection_interval=change_detection_interval,
            ignore_dirs=ignore_dirs,
        )
        watcher.start()
        app.state.watcher = watcher

    yield

    # Cleanup
    if watcher:
        watcher.stop()
    orc.stop_background_consolidation()
    orc.store.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Memory Agent Bedrock",
        description="Persistent memory agent powered by Claude Haiku 4.5 on AWS Bedrock",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
