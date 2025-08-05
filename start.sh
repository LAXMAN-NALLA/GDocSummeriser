#!/bin/bash
PORT=${PORT:-8000}

# Get the number of available CPU cores. Default to 1 if nproc is not available.
CORES=$(nproc 2>/dev/null || echo 1)

# Calculate the number of Gunicorn workers based on cores.
WORKER_COUNT=$((2 * CORES + 1))

echo "Starting Gunicorn with $WORKER_COUNT workers on port $PORT"

# Start Gunicorn with dynamic port
exec gunicorn main:app \
    --workers $WORKER_COUNT \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --timeout 300
