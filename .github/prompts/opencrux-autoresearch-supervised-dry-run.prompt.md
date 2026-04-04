---
mode: ask
description: "Start a fresh OpenCrux session for one bounded supervised autoresearch heuristic experiment using the benchmark harness and subagent workflow."
---

Act as the OpenCrux agent conductor for one bounded supervised autoresearch slice.

This is not a general product iteration session.

The goal is to run exactly one heuristic experiment inside the bounded autoresearch framework that is now set up in this repo.

Start by reading, in order:

- README.md
- docs/milestone-1.md
- docs/manual-verification.md
- docs/prd-status.md
- docs/autopilot-session-protocol.md
- docs/autoresearch-heuristic-protocol.md
- docs/autoresearch-benchmark-v1.md
- docs/next-session-handover.md
- src/opencrux/heuristics.py
- evals/milestone1/benchmark-manifest-v1.json
- evals/milestone1/benchmark-expectations-v1.json
- evals/milestone1/baseline-score-v1.json
- tests/test_analysis.py
- tests/test_heuristic_benchmark.py

Then inspect the most recent benchmark run artifacts under:

- data/evals/runs/

Use a small sequential swarm with bounded roles:

1. Benchmark Steward
   Use the autoresearch-benchmark-steward skill to restate the locked benchmark contract and hard gates.
2. Heuristic Mutator
   Use the autoresearch-heuristic-mutator skill to propose one small threshold-only hypothesis in src/opencrux/heuristics.py.
3. Gate Reviewer
   Use the autoresearch-gate-review skill to evaluate whether the candidate should be rejected or promoted.

Constraints:

- keep the experiment local-first and deterministic
- keep the mutable surface limited to src/opencrux/heuristics.py unless a companion test update is strictly required
- do not change UI, API, persistence, or benchmark expectation files during the same experiment
- preserve unsupported multi-climber failure behavior as a hard gate
- do not run an unbounded loop or multiple experiments in one session

Execution steps:

1. summarize the benchmark contract and identify one plausible threshold-only hypothesis
2. edit the heuristic surface for that single hypothesis
3. run focused heuristic tests
4. run ./scripts/run_autoresearch_benchmark.sh
5. if the benchmark passes and the candidate looks worth keeping, run ./scripts/run_targeted_verification.sh
6. update docs/next-session-handover.md with the result and recommended next step

Deliverables by end of session:

- one bounded heuristic experiment completed
- benchmark result interpreted
- targeted verification result recorded if promotion was attempted
- durable checkpoint written for the next session