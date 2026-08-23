#!/usr/bin/env bash
# Make a fresh machine able to evaluate candidates. Run by every Devin mutation
# session before it scores its own candidate, and by the orchestrator host.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e '.[dev]'

# Chromium + the headless shell. The harness plays the real page, so this is not
# optional; it is the only heavy step and it is cached per machine.
.venv/bin/python -m playwright install --with-deps chromium

.venv/bin/python -m pytest -q
echo "ready: .venv/bin/python -m orbit.cli evaluate games/orbit/index.html"
