---
name: autoresearch-gate-review
description: "Use when reviewing an OpenCrux heuristic experiment result for hard-gate regressions, benchmark pass or fail, and promotion readiness."
---
# Autoresearch Gate Review

Use this skill after a bounded heuristic candidate has been evaluated.

## Read First

1. [docs/autoresearch-heuristic-protocol.md](../../../docs/autoresearch-heuristic-protocol.md)
2. [docs/autoresearch-benchmark-v1.md](../../../docs/autoresearch-benchmark-v1.md)
3. [evals/milestone1/baseline-score-v1.json](../../../evals/milestone1/baseline-score-v1.json)
4. the candidate benchmark report under `data/evals/runs/<tag>/benchmark-report.json`

## Review Order

1. hard-failure count
2. unsupported-footage behavior
3. warning honesty on caution footage
4. supported-footage cleanliness
5. soft penalty delta versus baseline
6. need for targeted web verification

## Reject Conditions

- unsupported footage no longer fails clearly
- benchmark hard gates fail
- metric wins depend on relaxing warning honesty
- the candidate changed surfaces outside the bounded heuristic scope without approval

## Promotion Conditions

- benchmark passes
- analysis tests pass
- targeted verification passes if the candidate is worth keeping
- checkpoint docs are updated