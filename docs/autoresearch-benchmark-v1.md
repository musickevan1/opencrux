# Autoresearch Benchmark V1

## Purpose

Benchmark V1 is the fixed evaluation surface for bounded OpenCrux heuristic tuning.

It protects the currently verified Milestone 1 posture instead of replacing product judgment with one opaque score.

## Files

- [evals/milestone1/benchmark-manifest-v1.json](../evals/milestone1/benchmark-manifest-v1.json)
- [evals/milestone1/benchmark-expectations-v1.json](../evals/milestone1/benchmark-expectations-v1.json)
- [evals/milestone1/baseline-score-v1.json](../evals/milestone1/baseline-score-v1.json)
- [scripts/evaluate_heuristic_benchmark.py](../scripts/evaluate_heuristic_benchmark.py)
- [scripts/run_autoresearch_benchmark.sh](../scripts/run_autoresearch_benchmark.sh)

## Cohorts

The benchmark locks three clip cohorts from the existing local sample matrix:

1. `supported`: known-good single-climber footage should complete cleanly.
2. `caution`: known-bad-occlusion footage should complete in a warning posture, not as a clean ready posture.
3. `unsupported`: known-unsupported multi-climber footage must fail clearly.

## Hard Gates

The scorer rejects a candidate immediately when any of the following regress:

1. A benchmark clip is missing or an unexpected clip appears.
2. The terminal status changes away from the expected cohort behavior.
3. Required warning codes disappear.
4. Forbidden warning codes appear.
5. Required error-message fragments for unsupported footage disappear.
6. Attempt count falls outside the allowed range for a committed benchmark clip.

## Soft Penalty

After the hard gates pass, the scorer computes a small penalty for drift outside the expected metric bands.

This is intentionally secondary. The benchmark prefers honest unsupported or caution behavior over superficially nicer metrics.

## Baseline

The committed baseline report in [evals/milestone1/baseline-score-v1.json](../evals/milestone1/baseline-score-v1.json) represents the current verified slice.

A candidate is only interesting when it:

1. passes all hard gates
2. preserves explainable output behavior
3. matches or improves on the baseline penalty

## Commands

Run the full local benchmark wrapper:

```bash
./scripts/run_autoresearch_benchmark.sh
```

The wrapper intentionally continues after a nonzero manifest-analysis exit when `summary.json` was still produced, because the benchmark includes an unsupported clip that is expected to fail.

Run the scorer directly against a summary file:

```bash
PYTHONPATH=src python scripts/evaluate_heuristic_benchmark.py \
  data/samples/results/summary.json \
  --manifest evals/milestone1/benchmark-manifest-v1.json \
  --expectations evals/milestone1/benchmark-expectations-v1.json \
  --baseline evals/milestone1/baseline-score-v1.json
```

## Promotion Rule

Benchmark V1 is a promotion gate for heuristic changes, not a substitute for review.

Any promoted heuristic candidate should still pass:

1. [tests/test_analysis.py](../tests/test_analysis.py)
2. [tests/test_heuristic_benchmark.py](../tests/test_heuristic_benchmark.py)
3. [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)
4. the manual clip review posture in [manual-verification.md](manual-verification.md)