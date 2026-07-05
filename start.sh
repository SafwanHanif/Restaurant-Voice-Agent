#!/usr/bin/env bash
# Render start script — or run locally with: bash start.sh
set -e
cd "$(dirname "$0")"
uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
