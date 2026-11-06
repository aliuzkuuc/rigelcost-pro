#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ -x ".venv/bin/python" ]]; then
  exec .venv/bin/python main.py
fi
if command -v python3.14 >/dev/null 2>&1; then
  exec python3.14 main.py
fi
exec python3 main.py
