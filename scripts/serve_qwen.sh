#!/usr/bin/env bash
# Foreground isolated server; the shared installation on port 11434 is untouched.
set -eu
task_runtime="${OLLAMA_QWEN_DIR:-/data/5pourghe/ollama-qwen}"
export OLLAMA_HOST=127.0.0.1:11435
export OLLAMA_MODELS="$task_runtime/models"
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_NO_CLOUD=true
exec "$task_runtime/0.40.15/bin/ollama" serve
