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
        echo "OpenCrux autoresearch benchmark requires a working Python interpreter. Set PYTHON_BIN or create .venv/." >&2
        exit 1
    fi
elif ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "OpenCrux autoresearch benchmark requires a working Python interpreter on PATH. Set PYTHON_BIN if needed." >&2
    exit 1
fi

export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

run_tag="${OPENCRUX_AUTORESEARCH_RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_dir="$repo_root/data/evals/runs/$run_tag"
summary_dir="$run_dir/manifest-results"
report_path="$run_dir/benchmark-report.json"

mkdir -p "$summary_dir"

echo "Running OpenCrux benchmark manifest into $summary_dir"
cli_exit=0
if ! "$python_bin" -m opencrux.cli --manifest "$repo_root/data/samples/manifest.json" --output "$summary_dir"; then
    cli_exit=$?
    if [[ ! -f "$summary_dir/summary.json" ]]; then
        echo "Benchmark manifest run exited with code $cli_exit before producing summary.json." >&2
        exit "$cli_exit"
    fi
    echo "Manifest run exited with code $cli_exit because benchmark cohorts include expected failures. Continuing with scorer."
fi

echo "Scoring benchmark results into $report_path"
"$python_bin" "$repo_root/scripts/evaluate_heuristic_benchmark.py" \
    "$summary_dir/summary.json" \
    --manifest "$repo_root/evals/milestone1/benchmark-manifest-v1.json" \
    --expectations "$repo_root/evals/milestone1/benchmark-expectations-v1.json" \
    --baseline "$repo_root/evals/milestone1/baseline-score-v1.json" \
    --output "$report_path"

echo "Benchmark run complete"
echo "Run directory: $run_dir"
echo "Report: $report_path"