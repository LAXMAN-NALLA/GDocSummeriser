#!/bin/bash
PORT=${PORT:-8000}
CORES=$(nproc 2>/dev/null || echo 1)
WORKER_COUNT=$((2 * CORES + 1))
if [[ $WORKER_COUNT -gt 4 ]]; then
    WORKER_COUNT=3
fi

echo "Starting Gunicorn with $WORKER_COUNT workers on port $PORT"

exec gunicorn main:app \
    --workers $WORKER_COUNT \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --timeout 300
