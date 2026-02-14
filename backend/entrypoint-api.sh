#!/bin/sh
set -eu

echo "Starting RaceTime API..."

# IMPORTANT: bind to 0.0.0.0 so Docker port mapping works
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
