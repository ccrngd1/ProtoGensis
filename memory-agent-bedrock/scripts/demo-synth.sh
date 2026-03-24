#!/usr/bin/env bash
# demo.sh — Quick demo of multimodal memory agent
set -euo pipefail

echo "============================================"
echo "Memory Agent Multimodal Demo"
echo "============================================"
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/status > /dev/null 2>&1; then
    echo "❌ Server not running!"
    echo ""
    echo "Start the server first:" 
    echo "  ./run-with-watcher.sh"
    echo ""
    exit 1
fi

echo "✓ Server is running"
echo ""

# 1. Test text ingestion
echo "1. Testing text ingestion..."
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Claude Haiku 4.5 supports vision capabilities for analyzing images.", "source": "demo"}' \
  | python3 -m json.tool

echo ""
echo "✓ Text ingestion successful"
echo ""

# 2. Create test image if Pillow is available
echo "2. Creating test image..."
if python3 -c "import PIL" 2>/dev/null; then
    cd examples
    python3 create_test_image.py
    cd ..

    echo ""
    echo "3. Uploading test image..."
    curl -s -X POST http://localhost:8000/ingest/file \
      -F "file=@examples/test_image.png" \
      | python3 -m json.tool

    echo ""
    echo "✓ Image upload successful"
    echo ""
else
    echo "⚠️  Pillow not installed, skipping image creation"
    echo "   Install with: pip install Pillow"
    echo ""
fi

# 3. Check status
echo "4. Checking status..."
curl -s http://localhost:8000/status | python3 -m json.tool

echo ""
echo ""

# 4. Query memories
echo "5. Querying memories..."
curl -s "http://localhost:8000/query?q=What+have+you+learned" \
  | python3 -m json.tool

echo ""
echo ""
echo "============================================"
echo "Demo Complete!"
echo "============================================"
echo ""
echo "Try these next:"
echo ""
echo "  # Upload your own files:"
echo "  curl -X POST http://localhost:8000/ingest/file -F 'file=@/path/to/image.png'"
echo "  curl -X POST http://localhost:8000/ingest/file -F 'file=@/path/to/document.pdf'"
echo ""
echo "  # Query specific information:"
echo "  curl 'http://localhost:8000/query?q=YOUR+QUESTION'"
echo ""
echo "  # View API docs:"
echo "  open http://localhost:8000/docs"
echo ""
