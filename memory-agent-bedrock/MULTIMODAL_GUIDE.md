# Adding Multimodal Support to memory-agent-bedrock

Yes, your Bedrock version can absolutely be expanded to support multimodal inputs! Claude Haiku 4.5 on Bedrock already supports vision, and AWS provides additional services for audio and document processing.

## What's Possible

| File Type | Support Level | Implementation |
|-----------|--------------|----------------|
| **Images** | ✅ Native | Claude Haiku vision (already available) |
| **PDFs** | ✅ Easy | PyPDF2 or AWS Textract |
| **Audio** | ✅ Moderate | AWS Transcribe or faster-whisper |
| **Video** | ⚠️ Complex | Frame extraction + transcription |

## Implementation Roadmap

### Phase 1: Images (Easiest)

Claude Haiku 4.5 already supports images. You just need to modify the message format.

#### 1. Update `bedrock_client.py`

```python
"""Shared boto3 Bedrock client helper with multimodal support."""
from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3

MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon-bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
)

_RAW_MODEL_ID = MODEL_ID.removeprefix("amazon-bedrock/")

_client: Optional[Any] = None
_client_lock = threading.Lock()


def get_client() -> Any:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
                _client = boto3.client("bedrock-runtime", region_name=region)
    return _client


def invoke(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    """Call Haiku 4.5 via bedrock-runtime and return the text response."""
    client = get_client()

    messages = [{"role": "user", "content": prompt}]
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        body["system"] = system

    response = client.invoke_model(
        modelId=_RAW_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def invoke_multimodal(
    content: List[Dict[str, Any]],
    system: str = "",
    max_tokens: int = 2048
) -> str:
    """Call Haiku 4.5 with multimodal content (text + images).

    Args:
        content: List of content blocks, e.g.:
            [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
            ]
        system: System prompt
        max_tokens: Max tokens to generate

    Returns:
        Text response from Claude
    """
    client = get_client()

    messages = [{"role": "user", "content": content}]
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        body["system"] = system

    response = client.invoke_model(
        modelId=_RAW_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def load_image_as_base64(file_path: Path) -> tuple[str, str]:
    """Load image file and return (base64_data, media_type)."""
    # Detect media type
    suffix = file_path.suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "image/png")

    # Read and encode
    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    return image_data, media_type
```

#### 2. Update `IngestAgent` to handle images

```python
"""Ingest Agent — converts raw text or images to structured Memory records."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from agents.bedrock_client import invoke, invoke_multimodal, load_image_as_base64
from agents.utils import parse_json
from memory.models import Memory
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

SYSTEM = """You are a memory extraction assistant. Given a piece of text or an image, extract structured information.
Always respond with a single JSON object (no markdown fences) containing:
- summary: string (1-3 sentence distillation of what you see/read)
- entities: list of strings (people, places, organizations, products, concepts, objects in images)
- topics: list of strings (broad thematic categories)
- importance: float between 0.0 and 1.0 (how significant/noteworthy is this information)
"""

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class IngestAgent:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def ingest(self, text: str, source: str = "") -> Memory:
        """Extract structured memory from text and persist it."""
        prompt = f"Extract structured memory from the following text:\n\n{text}"
        try:
            raw = invoke(prompt, system=SYSTEM, max_tokens=1024)
            data = parse_json(raw)
        except Exception as exc:
            logger.warning("LLM extraction failed (%s); using fallback.", exc)
            data = {}

        # Clamp importance to valid range [0.0, 1.0]
        try:
            importance = float(data.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
        except (ValueError, TypeError):
            importance = 0.5

        memory = Memory(
            summary=data.get("summary", text[:500]),
            entities=data.get("entities", []),
            topics=data.get("topics", []),
            importance=importance,
            source=source,
        )
        return self.store.add_memory(memory)

    def ingest_file(self, file_path: Path) -> Memory:
        """Extract structured memory from a file (text or image).

        Args:
            file_path: Path to file (text or image)

        Returns:
            Created Memory record
        """
        suffix = file_path.suffix.lower()

        # Handle images
        if suffix in IMAGE_EXTENSIONS:
            return self._ingest_image(file_path)

        # Handle text files
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return self.ingest(text, source=file_path.name)

    def _ingest_image(self, file_path: Path) -> Memory:
        """Extract structured memory from an image."""
        try:
            image_data, media_type = load_image_as_base64(file_path)

            # Build multimodal content
            content = [
                {"type": "text", "text": "Extract structured memory from this image. Describe what you see, identify any text, objects, people, or concepts."},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data
                    }
                }
            ]

            raw = invoke_multimodal(content, system=SYSTEM, max_tokens=1024)
            data = parse_json(raw)
        except Exception as exc:
            logger.warning("Image extraction failed (%s); using fallback.", exc)
            data = {"summary": f"Image: {file_path.name}"}

        # Clamp importance
        try:
            importance = float(data.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
        except (ValueError, TypeError):
            importance = 0.5

        memory = Memory(
            summary=data.get("summary", f"Image: {file_path.name}"),
            entities=data.get("entities", []),
            topics=data.get("topics", ["image"]),
            importance=importance,
            source=file_path.name,
        )
        return self.store.add_memory(memory)
```

#### 3. Add file upload endpoint

```python
# In api/routes.py, add:

from fastapi import File, UploadFile
import tempfile
from pathlib import Path

@router.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Ingest a file (text or image)."""
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        memory = orchestrator.ingest_agent.ingest_file(tmp_path)
        return {
            "id": str(memory.id),
            "summary": memory.summary,
            "entities": memory.entities,
            "topics": memory.topics,
            "importance": memory.importance,
            "source": memory.source,
        }
    finally:
        tmp_path.unlink()  # Clean up temp file
```

#### 4. Test it

```bash
# Upload an image
curl -X POST http://localhost:8000/ingest/file \
  -F "file=@screenshot.png"

# Or via Python
import requests

with open("photo.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/ingest/file",
        files={"file": f}
    )
print(response.json())
```

---

### Phase 2: PDFs

#### Option A: Simple text extraction (PyPDF2)

```python
# Add to requirements.txt:
# PyPDF2>=3.0.0

# In agents/ingest.py:
from PyPDF2 import PdfReader

def _ingest_pdf(self, file_path: Path) -> Memory:
    """Extract text from PDF."""
    reader = PdfReader(file_path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    return self.ingest(text[:10000], source=file_path.name)  # Truncate if too long
```

#### Option B: AWS Textract (better OCR, tables, forms)

```python
# Add to requirements.txt:
# boto3>=1.34.0  # (already have this)

import boto3

def _ingest_pdf_textract(self, file_path: Path) -> Memory:
    """Extract text from PDF using AWS Textract."""
    textract = boto3.client("textract")

    with open(file_path, "rb") as f:
        response = textract.detect_document_text(
            Document={"Bytes": f.read()}
        )

    # Extract all text blocks
    text = "\n".join(
        block["Text"]
        for block in response["Blocks"]
        if block["BlockType"] == "LINE"
    )

    return self.ingest(text[:10000], source=file_path.name)
```

---

### Phase 3: Audio (AWS Transcribe)

```python
# Add to requirements.txt:
# boto3>=1.34.0  # (already have this)

import boto3
import time
import uuid

def _ingest_audio(self, file_path: Path) -> Memory:
    """Transcribe audio using AWS Transcribe."""
    transcribe = boto3.client("transcribe")
    s3 = boto3.client("s3")

    # Upload to S3 (Transcribe requires S3 input)
    bucket = os.getenv("TRANSCRIBE_BUCKET", "my-transcribe-bucket")
    s3_key = f"audio/{uuid.uuid4()}{file_path.suffix}"
    s3.upload_file(str(file_path), bucket, s3_key)

    # Start transcription job
    job_name = f"memory-{uuid.uuid4()}"
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{bucket}/{s3_key}"},
        MediaFormat=file_path.suffix[1:],  # Remove leading dot
        LanguageCode="en-US"
    )

    # Wait for completion
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status["TranscriptionJob"]["TranscriptionJobStatus"] in ["COMPLETED", "FAILED"]:
            break
        time.sleep(5)

    # Get transcript
    if status["TranscriptionJob"]["TranscriptionJobStatus"] == "COMPLETED":
        transcript_uri = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        import requests
        transcript_data = requests.get(transcript_uri).json()
        text = transcript_data["results"]["transcripts"][0]["transcript"]
    else:
        text = f"Transcription failed for {file_path.name}"

    # Clean up S3
    s3.delete_object(Bucket=bucket, Key=s3_key)

    return self.ingest(text, source=file_path.name)
```

**Simpler alternative: faster-whisper (local transcription)**

```python
# Add to requirements.txt:
# faster-whisper>=1.0.0

from faster_whisper import WhisperModel

# Load model once (class-level)
_whisper_model = None

def _ingest_audio_whisper(self, file_path: Path) -> Memory:
    """Transcribe audio using faster-whisper (local)."""
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel("base", device="cpu")  # or "cuda"

    segments, info = _whisper_model.transcribe(str(file_path))
    text = " ".join(segment.text for segment in segments)

    return self.ingest(text, source=file_path.name)
```

---

### Phase 4: File Watcher (Like Google's Version)

```python
# Add to requirements.txt:
# watchdog>=3.0.0

# Create agents/watcher.py:

"""File watcher for automatic ingestion."""
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    # Text
    ".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    # Documents
    ".pdf",
    # Audio (if implemented)
    ".mp3", ".wav", ".m4a",
}


class InboxHandler(FileSystemEventHandler):
    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.processed = set()

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Skip if not supported or already processed
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        if str(file_path) in self.processed:
            return

        logger.info(f"📥 New file detected: {file_path.name}")

        try:
            memory = self.orchestrator.ingest_agent.ingest_file(file_path)
            logger.info(f"✅ Ingested: {memory.summary[:60]}...")
            self.processed.add(str(file_path))
        except Exception as e:
            logger.error(f"❌ Failed to ingest {file_path.name}: {e}")


def start_watcher(orchestrator: Orchestrator, watch_dir: Path = Path("./inbox")):
    """Start watching a directory for new files."""
    watch_dir.mkdir(parents=True, exist_ok=True)

    event_handler = InboxHandler(orchestrator)
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=False)
    observer.start()

    logger.info(f"👁️  Watching: {watch_dir}/ for new files")
    return observer
```

Add to `api/main.py`:

```python
from agents.watcher import start_watcher

@app.on_event("startup")
async def startup_event():
    # Existing consolidation timer...

    # Add file watcher
    if os.getenv("ENABLE_FILE_WATCHER", "false").lower() == "true":
        watch_dir = Path(os.getenv("WATCH_DIR", "./inbox"))
        start_watcher(app.state.orchestrator, watch_dir)
```

Usage:
```bash
# Enable file watcher
export ENABLE_FILE_WATCHER=true
export WATCH_DIR=./inbox

# Start server
uvicorn api.main:app --reload

# Drop files
cp image.png inbox/
cp notes.txt inbox/
cp recording.mp3 inbox/
# Files are automatically ingested
```

---

## Updated `ingest_file` Implementation

Here's a complete `ingest_file` method supporting text, images, PDFs, and audio:

```python
SUPPORTED_EXTENSIONS = {
    # Text
    ".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    # Documents
    ".pdf",
    # Audio (optional)
    ".mp3", ".wav", ".m4a",
}

def ingest_file(self, file_path: Path) -> Memory:
    """Extract structured memory from any supported file type."""
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    # Images
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return self._ingest_image(file_path)

    # PDFs
    if suffix == ".pdf":
        return self._ingest_pdf(file_path)

    # Audio
    if suffix in {".mp3", ".wav", ".m4a"}:
        return self._ingest_audio(file_path)

    # Text files
    text = file_path.read_text(encoding="utf-8", errors="replace")
    return self.ingest(text, source=file_path.name)
```

---

## Dependencies Summary

Add to `requirements.txt`:

```txt
# Existing
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.0.0
boto3>=1.34.0
httpx>=0.27.0
pytest>=8.0.0

# For multimodal support
PyPDF2>=3.0.0           # PDF text extraction
watchdog>=3.0.0         # File watcher (optional)
faster-whisper>=1.0.0   # Audio transcription (optional, alternative to AWS Transcribe)
python-multipart>=0.0.6 # For FastAPI file uploads
```

---

## Testing Multimodal

```python
# tests/test_multimodal.py

import tempfile
from pathlib import Path
from PIL import Image

def test_ingest_image(ingest_agent, mock_bedrock):
    """Test image ingestion."""
    # Create test image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        memory = ingest_agent.ingest_file(tmp_path)
        assert memory.id is not None
        assert memory.source == tmp_path.name
    finally:
        tmp_path.unlink()


def test_ingest_pdf(ingest_agent, mock_bedrock):
    """Test PDF ingestion."""
    # Would need a test PDF file or PyPDF2 mocking
    pass
```

---

## Cost Comparison

| Input Type | Method | Cost |
|------------|--------|------|
| **Text** | Direct to Claude | $0.80/M tokens |
| **Images** | Claude vision | $0.80/M tokens (input) + $4.80/M images* |
| **PDFs** | Textract | $1.50/1K pages (OCR) |
| **PDFs** | PyPDF2 | Free (local) |
| **Audio** | Transcribe | $0.024/minute |
| **Audio** | faster-whisper | Free (local) |

*Claude pricing: ~1.5K tokens per image

---

## Recommendation

**Start with Phase 1 (Images)** — it's the easiest and Claude already supports it natively via Bedrock. Then add:

1. **Phase 1: Images** ✅ (1-2 hours)
   - Modify `bedrock_client.py`
   - Add `ingest_file` method
   - Add `/ingest/file` endpoint

2. **Phase 2: PDFs** (1 hour)
   - Add PyPDF2 for simple text extraction
   - Or AWS Textract for better OCR

3. **Phase 3: Audio** (2-3 hours)
   - Use faster-whisper for local transcription (easier)
   - Or AWS Transcribe for cloud (better accuracy)

4. **Phase 4: File Watcher** (1 hour)
   - Add watchdog library
   - Auto-ingest dropped files

Total implementation time: **4-7 hours** to match Google's multimodal capabilities.

Your Bedrock version would then support:
- ✅ Text
- ✅ Images (Claude vision)
- ✅ PDFs (PyPDF2 or Textract)
- ✅ Audio (faster-whisper or Transcribe)
- ✅ File watcher (watchdog)

All while keeping the modular structure and test coverage that make your implementation production-ready.
