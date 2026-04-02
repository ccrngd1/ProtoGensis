#!/bin/bash
# Deployment script for AEGIS Firewall
# Run this script with appropriate permissions to deploy from /tmp/aegis-firewall-build
# to /root/projects/protoGen/aegis-firewall

SOURCE="/tmp/aegis-firewall-build"
TARGET="/root/projects/protoGen/aegis-firewall"

echo "AEGIS Firewall Deployment Script"
echo "================================="
echo "Source: $SOURCE"
echo "Target: $TARGET"
echo ""

# Check if source exists
if [ ! -d "$SOURCE" ]; then
    echo "ERROR: Source directory does not exist: $SOURCE"
    exit 1
fi

# Check if we have write permission to target
if [ ! -w "$TARGET" ]; then
    echo "WARNING: No write permission to target directory"
    echo "Attempting to fix permissions..."

    # Try to change ownership
    chown -R $(whoami):$(whoami) "$TARGET" 2>/dev/null

    if [ $? -ne 0 ]; then
        echo "ERROR: Cannot change permissions. Please run with appropriate privileges."
        echo ""
        echo "Suggested command:"
        echo "  sudo chown -R builder:builder $TARGET"
        echo "  bash $0"
        exit 1
    fi
fi

# Copy files
echo "Copying files..."
cp -rv "$SOURCE"/* "$TARGET/" 2>&1 | tail -20

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Deployment successful!"
    echo ""
    echo "Files deployed to: $TARGET"
    echo ""
    echo "Next steps:"
    echo "1. cd $TARGET"
    echo "2. Install dependencies: pip install -r requirements.txt"
    echo "3. Run tests: python3 -m pytest tests/ -v"
    echo "4. Try demos: python3 demo/run_all_demos.py"
else
    echo ""
    echo "✗ Deployment failed. See errors above."
    exit 1
fi
