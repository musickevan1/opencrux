# Autoresearch Heuristic Protocol

## Purpose

Use autoresearch in OpenCrux as a bounded heuristic-tuning subsystem.

Do not use it as the top-level product conductor.

The main repo workflow remains discovery, implementation, verification, and review. This protocol only applies when the task is to tune or guard deterministic analysis heuristics inside the current Milestone 1 slice.

## Mutable Surface

The initial mutable surface is [src/opencrux/heuristics.py](../src/opencrux/heuristics.py).

That file now holds:

- heuristic threshold defaults
- attempt segmentation logic
- hesitation detection logic
- preview warning logic
- final warning and unsupported-footage decision logic

The following are out of bounds for heuristic mutation unless the user explicitly broadens scope:

- [src/opencrux/main.py](../src/opencrux/main.py)
- [src/opencrux/store.py](../src/opencrux/store.py)
- [src/opencrux/static/app.js](../src/opencrux/static/app.js)
- [src/opencrux/static/app.css](../src/opencrux/static/app.css)
- benchmark expectation files under [evals/milestone1](../evals/milestone1)

## Fixed Evaluation Surface

The benchmark contract is defined by:

- [evals/milestone1/benchmark-manifest-v1.json](../evals/milestone1/benchmark-manifest-v1.json)
- [evals/milestone1/benchmark-expectations-v1.json](../evals/milestone1/benchmark-expectations-v1.json)
- [evals/milestone1/baseline-score-v1.json](../evals/milestone1/baseline-score-v1.json)

The local runner is:

- [scripts/run_autoresearch_benchmark.sh](../scripts/run_autoresearch_benchmark.sh)

## Swarm Roles

Run the workflow as a small sequential swarm.

1. `Benchmark Steward`
   Locks cohort expectations and baseline behavior.
2. `Harness Keeper`
   Keeps the scorer and run artifacts stable.
3. `Heuristic Mutator`
   Edits only [src/opencrux/heuristics.py](../src/opencrux/heuristics.py) unless a narrower explicit exception is approved.
4. `Evaluator`
   Runs the fixed benchmark and analysis tests.
5. `Gate Reviewer`
   Rejects regressions in unsupported-footage behavior, warning honesty, and schema stability.
6. `Checkpoint Recorder`
   Updates docs and handoff artifacts for promoted changes.

## Recommended Subagent Mapping

Use built-in subagents or equivalent read-only helpers in this sequence:

1. `Explore` for benchmark context and baseline artifact reads
2. `gsd-planner` or `gsd-phase-researcher` for a bounded experiment plan
3. main agent for the actual heuristic edit
4. `gsd-verifier` or main agent for benchmark and targeted verification interpretation
5. main agent for checkpoint docs

Do not run multiple writer agents against the mutable heuristic surface at the same time.

## Session Rules

1. Start from the current benchmark version and baseline report.
2. Make one bounded heuristic hypothesis at a time.
3. Run the benchmark after every candidate.
4. Reject immediately on hard-gate failure.
5. Only escalate to targeted web verification for candidates that pass the benchmark.
6. Update docs when a heuristic candidate is promoted.

## Commands

Baseline benchmark run:

```bash
./scripts/run_autoresearch_benchmark.sh
```

Targeted verification for a promoted candidate:

```bash
./scripts/run_targeted_verification.sh
```

## Reusable Prompt

```text
Run one bounded OpenCrux heuristic autoresearch session.

Start by reading:
- docs/autoresearch-heuristic-protocol.md
- docs/autoresearch-benchmark-v1.md
- evals/milestone1/benchmark-manifest-v1.json
- evals/milestone1/benchmark-expectations-v1.json
- evals/milestone1/baseline-score-v1.json
- src/opencrux/heuristics.py
- tests/test_analysis.py
- tests/test_heuristic_benchmark.py

Use a small subagent swarm:
- Benchmark Steward for benchmark context only
- Heuristic Mutator for one bounded hypothesis
- Gate Reviewer for promotion or rejection

Constraints:
- keep changes deterministic and explainable
- preserve unsupported multi-climber failure behavior as a hard gate
- do not edit UI, API, or storage surfaces
- do not relax benchmark expectations during the same experiment loop

After the candidate change:
- run the benchmark wrapper
- run the analysis tests
- if the benchmark passes, run targeted verification
- update the next-session handoff if anything is promoted
```