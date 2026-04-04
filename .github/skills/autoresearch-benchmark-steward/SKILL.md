---
name: autoresearch-benchmark-steward
description: "Use when locking or reviewing the OpenCrux autoresearch benchmark, benchmark expectations, baseline score files, or cohort guardrails for heuristic tuning."
---
# Autoresearch Benchmark Steward

Use this skill when the task is to define or review the fixed benchmark surface for OpenCrux heuristic tuning.

## Read First

1. [docs/autoresearch-heuristic-protocol.md](../../../docs/autoresearch-heuristic-protocol.md)
2. [docs/autoresearch-benchmark-v1.md](../../../docs/autoresearch-benchmark-v1.md)
3. [docs/manual-verification.md](../../../docs/manual-verification.md)
4. [evals/milestone1/benchmark-manifest-v1.json](../../../evals/milestone1/benchmark-manifest-v1.json)
5. [evals/milestone1/benchmark-expectations-v1.json](../../../evals/milestone1/benchmark-expectations-v1.json)
6. [evals/milestone1/baseline-score-v1.json](../../../evals/milestone1/baseline-score-v1.json)

## Responsibilities

- preserve the supported, caution, and unsupported cohort contract
- keep unsupported multi-climber failure as a hard gate
- keep warning honesty ahead of metric optimization
- separate clip inventory from benchmark expectations

## Do Not

- edit [src/opencrux/heuristics.py](../../../src/opencrux/heuristics.py)
- soften benchmark expectations in the same change that introduces a heuristic mutation
- treat the soft penalty as more important than the hard gates

## Output

- updated benchmark manifest or expectations when required
- a brief rationale for any benchmark version change