"""FastAPI application factory."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agents.orchestrator import Orchestrator
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
    yield
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
