#!/bin/bash
# Run the League Image Generator MCP server via uv.
# Self-locating: cd to the project root relative to this script, so it works
# regardless of where the project lives or what the caller's cwd is.
# `uv run` syncs the project's virtual environment (.venv) from pyproject.toml /
# uv.lock before launching, so no manual venv setup is needed.
#
# Requires: uv (https://docs.astral.sh/uv/) and OPENROUTER_API_KEY (read from .env).
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run mcp-server/server.py
