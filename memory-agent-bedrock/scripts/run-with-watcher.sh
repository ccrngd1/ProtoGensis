#!/usr/bin/env bash
# run-with-watcher.sh — Start server with file watcher enabled
set -euo pipefail

VENV_DIR=".venv"
WATCH_DIR="${WATCH_DIR:-./inbox}"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating venv and installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install -q -r requirements.txt

# Create inbox directory if it doesn't exist
mkdir -p "$WATCH_DIR"

echo ""
echo "============================================"
echo "Starting Memory Agent with File Watcher"
echo "============================================"
echo "  API Server: http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  Watch Dir:  $WATCH_DIR"
echo ""
echo "Drop files in $WATCH_DIR for auto-ingestion:"
echo "  - Text: .txt, .md, .json, .csv, .log, .yaml, .yml"
echo "  - Images: .png, .jpg, .jpeg, .gif, .webp"
echo "  - PDFs: .pdf"
echo ""
echo "============================================"
echo ""

# Enable file watcher
export ENABLE_FILE_WATCHER=true
export WATCH_DIR="$WATCH_DIR"

# Start server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
