#!/usr/bin/env bash
# Run OpenCrux locally with Ollama LLM backend
export OPENCRUX_GEMMA_ENABLED=true
export OPENCRUX_OLLAMA_BASE_URL=http://100.76.50.93:11434
export PYTHONPATH=src

cd "$(dirname "$0")/.."
exec .venv/bin/python -m uvicorn opencrux.main:app --host 0.0.0.0 --port 8000 --app-dir src
