#!/usr/bin/env bash
# One command: make .venv, install the project with dev tools, lint, check links and run every test offline.
set -euo pipefail
cd "$(dirname "$0")"
if command -v uv >/dev/null 2>&1; then
  [ -d .venv ] || uv venv -q --python 3.11 .venv 2>/dev/null || uv venv -q .venv
  uv pip install -q --python .venv/bin/python -e ".[dev]"
else
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/python -m pip install -q -e ".[dev]"
fi
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python scripts/check_links.py
.venv/bin/python -m pytest
echo "init.sh: all checks passed"
