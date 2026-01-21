#!/bin/bash

# Script to run the backend server
# Usage: ./scripts/run_backend.sh

set -e

# Get the project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Virtual environment not activated. Activating..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "Error: Virtual environment not found. Please run ./scripts/setup_venv.sh first"
        exit 1
    fi
fi

# Install package in editable mode if not already installed
pip install -e . --no-build-isolation > /dev/null 2>&1 || true

# Run backend from project root
echo "Starting backend server..."
echo "Backend will be available at: http://localhost:8000"
echo "API docs will be available at: http://localhost:8000/docs"
echo ""
uvicorn backend.main:app --reload --port 8000 --host 0.0.0.0
