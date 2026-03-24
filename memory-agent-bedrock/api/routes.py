"""API routes: /ingest, /query, /status, /consolidate."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, File, UploadFile
from pydantic import BaseModel, Field

router = APIRouter()


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class IngestRequest(BaseModel):
    text: str = Field(..., max_length=100000)
    source: str = ""


class IngestResponse(BaseModel):
    id: str
    summary: str
    entities: list
    topics: list
    importance: float
    source: str


class QueryResponse(BaseModel):
    answer: str


class StatusResponse(BaseModel):
    memory_count: int
    consolidation_count: int
    unconsolidated_count: int
    background_consolidation_running: bool


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


def _get_orc(request: Request):
    orc = getattr(request.app.state, "orchestrator", None)
    if orc is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return orc


@router.post("/ingest", response_model=IngestResponse, summary="Ingest text into memory")
async def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    orc = _get_orc(request)
    memory = await asyncio.to_thread(orc.ingest, body.text, source=body.source)
    return IngestResponse(
        id=memory.id,
        summary=memory.summary,
        entities=memory.entities,
        topics=memory.topics,
        importance=memory.importance,
        source=memory.source,
    )


@router.get("/query", response_model=QueryResponse, summary="Query stored memories")
async def query(q: str, request: Request) -> QueryResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    orc = _get_orc(request)
    answer = await asyncio.to_thread(orc.query, q)
    return QueryResponse(answer=answer)


@router.get("/status", response_model=StatusResponse, summary="Agent status")
async def status(request: Request) -> StatusResponse:
    orc = _get_orc(request)
    s = orc.status()
    return StatusResponse(**s)


@router.post("/consolidate", summary="Trigger manual consolidation")
async def consolidate(request: Request):
    orc = _get_orc(request)
    result = await asyncio.to_thread(orc.consolidate)
    if result is None:
        return {"message": "Not enough unconsolidated memories to consolidate", "consolidated": False}
    return {
        "message": "Consolidation complete",
        "consolidated": True,
        "consolidation_id": result.id,
        "memory_count": len(result.memory_ids),
    }


@router.post("/ingest/file", response_model=IngestResponse, summary="Ingest a file (text, image, or PDF)")
async def ingest_file(file: UploadFile = File(...), request: Request = None) -> IngestResponse:
    """Upload and ingest a file.

    Supports: text files (.txt, .md, .json, etc.), images (.png, .jpg, etc.), and PDFs.
    """
    orc = _get_orc(request)

    # Check file extension
    file_path = Path(file.filename or "unknown")
    supported_extensions = {".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml",
                           ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}

    if file_path.suffix.lower() not in supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_path.suffix}. Supported: {', '.join(sorted(supported_extensions))}"
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_path.suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        memory = await asyncio.to_thread(orc.ingest_agent.ingest_file, tmp_path)
        return IngestResponse(
            id=memory.id,
            summary=memory.summary,
            entities=memory.entities,
            topics=memory.topics,
            importance=memory.importance,
            source=file.filename or "uploaded_file",
        )
    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)
