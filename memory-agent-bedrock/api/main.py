"""FastAPI application factory."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from agents.orchestrator import Orchestrator
from agents.watcher import FileWatcher
from api.routes import router

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
        poll_interval = int(os.getenv("WATCH_POLL_INTERVAL", "5"))
        watcher = FileWatcher(orc, watch_dir, poll_interval)
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
