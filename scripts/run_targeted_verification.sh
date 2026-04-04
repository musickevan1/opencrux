#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -n "${PYTHON_BIN:-}" ]]; then
    python_bin="$PYTHON_BIN"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
    python_bin="$repo_root/.venv/bin/python"
else
    python_bin="python3"
fi

if [[ "$python_bin" == */* ]]; then
    if [[ ! -x "$python_bin" ]]; then
        echo "OpenCrux targeted verification requires a working Python interpreter. Set PYTHON_BIN or create .venv/." >&2
        exit 1
    fi
elif ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "OpenCrux targeted verification requires a working Python interpreter on PATH. Set PYTHON_BIN if needed." >&2
    exit 1
fi

chromium_bin="$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)"
chromedriver_bin="$(command -v chromedriver || true)"

if [[ -z "$chromium_bin" ]]; then
    echo "OpenCrux browser smoke verification requires chromium, chromium-browser, or google-chrome on PATH." >&2
    exit 1
fi

if [[ -z "$chromedriver_bin" ]]; then
    echo "OpenCrux browser smoke verification requires chromedriver on PATH." >&2
    exit 1
fi

export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

echo "Running targeted app and browser smoke verification with $python_bin"
"$python_bin" -m pytest tests/test_app.py tests/test_browser_smoke.py -rA "$@"