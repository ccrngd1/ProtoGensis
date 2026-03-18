#!/usr/bin/env bash
# run.sh — Set up venv and run the xmemory benchmark/demo
set -euo pipefail

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating venv and installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install -q -r requirements.txt

echo "Running xmemory benchmark..."
python benchmarks/run_benchmark.py
