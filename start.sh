#!/bin/bash
# Credit Nexus — macOS / Linux launcher.  Run:  bash start.sh
cd "$(dirname "$0")"
PY=""
for c in python3 python; do command -v $c >/dev/null 2>&1 && $c -c 'import sys;sys.exit(sys.version_info<(3,10))' && PY=$c && break; done
if [ -z "$PY" ]; then
  echo "Python 3.10+ not found."
  if command -v brew >/dev/null; then brew install python@3.12 && PY=python3
  else echo "Install it from https://python.org/downloads then run: bash start.sh"; exit 1; fi
fi
echo "Installing / checking packages..."
$PY -m pip install --quiet --disable-pip-version-check -r backend/requirements.txt 2>/dev/null \
 || $PY -m pip install --quiet --user -r backend/requirements.txt 2>/dev/null \
 || $PY -m pip install --quiet --break-system-packages -r backend/requirements.txt
echo "Data and scores show in seconds; AI commentary follows in about 30-90 s (free AI, no key: one request per company, one every 30 s)."
exec $PY run.py
