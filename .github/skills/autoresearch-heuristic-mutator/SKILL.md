---
name: autoresearch-heuristic-mutator
description: "Use when running a bounded OpenCrux heuristic experiment inside the mutable autoresearch surface in src/opencrux/heuristics.py."
---
# Autoresearch Heuristic Mutator

Use this skill when the task is to try one deterministic heuristic change under the benchmark harness.

## Read First

1. [docs/autoresearch-heuristic-protocol.md](../../../docs/autoresearch-heuristic-protocol.md)
2. [docs/autoresearch-benchmark-v1.md](../../../docs/autoresearch-benchmark-v1.md)
3. [src/opencrux/heuristics.py](../../../src/opencrux/heuristics.py)
4. [tests/test_analysis.py](../../../tests/test_analysis.py)
5. [tests/test_heuristic_benchmark.py](../../../tests/test_heuristic_benchmark.py)

## Editable Surface

Primary mutable file:

- [src/opencrux/heuristics.py](../../../src/opencrux/heuristics.py)

Only touch other files when the bounded experiment clearly requires companion test or checkpoint updates.

## Guardrails

- keep behavior deterministic and explainable from timestamps and visible motion
- do not edit UI, API, storage, or benchmark expectation files during a heuristic experiment
- preserve unsupported multi-climber failure behavior
- prefer smaller, clearer diffs over sprawling changes

## Required Verification

1. [scripts/run_autoresearch_benchmark.sh](../../../scripts/run_autoresearch_benchmark.sh)
2. [tests/test_analysis.py](../../../tests/test_analysis.py)
3. [tests/test_heuristic_benchmark.py](../../../tests/test_heuristic_benchmark.py)

Only candidates that pass the benchmark should advance to [scripts/run_targeted_verification.sh](../../../scripts/run_targeted_verification.sh).