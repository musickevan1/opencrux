# Next Session Handover

## Discovery

OpenCrux has completed the Phase 1 UI revamp slice, the follow-on Phase 1.1 hardening slice, the Phase 1.2 verification operationalization slice, and the bounded Phase 1.3 CI wiring slice for Milestone 1.

The repo now has a lightweight milestone operating model in [milestone-operations.md](milestone-operations.md), a Phase 1.3 plan artifact in [phase-1-3-ci-wiring-plan.md](phase-1-3-ci-wiring-plan.md), and an implementation record in [phase-1-3-ci-wiring-log.md](phase-1-3-ci-wiring-log.md).

Autoresearch checkpoint:

- supervised dry run completed with one threshold-only heuristic experiment
- candidate change: lowered `multi_pose_warning_ratio` from `0.05` to `0.04` in [src/opencrux/heuristics.py](../src/opencrux/heuristics.py) to keep multi-pose caution warnings slightly more conservative without moving the unsupported failure gate
- companion analysis test coverage now pins the warning threshold boundary
- focused heuristic tests passed: `tests/test_analysis.py` and `tests/test_heuristic_benchmark.py`
- benchmark v1 passed with zero hard failures and zero soft-penalty delta in [data/evals/runs/20260404T045717Z/benchmark-report.json](../data/evals/runs/20260404T045717Z/benchmark-report.json)
- Phase 1.3 hardened the stale history-click path in [tests/test_browser_smoke.py](../tests/test_browser_smoke.py) and added [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml) so the standardized wrapper now has an always-on CI surface
- the full targeted verification wrapper passed locally after the hardening change, and `test_browser_smoke_protected_lifecycle` passed on a focused wrapper-driven rerun
- the candidate is provisionally worth keeping because the benchmark and the first targeted verification pass stayed aligned with baseline behavior

Verified status:

- the verdict-first workspace is implemented
- targeted app coverage is passing
- real clip verification exists for supported, caution, and unsupported conditions
- browser evidence exists for idle, analyzing, ready, caution, negative, history reload, and mobile ordering
- intake and history interactions now lock atomically from submit click through job resolution
- repeatable browser smoke coverage exists for ready, caution, negative, history reload, and mobile ordering
- a repo-standard targeted verification surface now exists via [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh), [.vscode/tasks.json](../.vscode/tasks.json), and [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml)

Primary checkpoint artifacts:

- [milestone-operations.md](milestone-operations.md)
- [phase-1-3-ci-wiring-plan.md](phase-1-3-ci-wiring-plan.md)
- [phase-1-3-ci-wiring-log.md](phase-1-3-ci-wiring-log.md)
- [ui-revamp-phase-1-handoff.md](ui-revamp-phase-1-handoff.md)
- [ui-phase-1-verification-log.md](ui-phase-1-verification-log.md)
- [phase-1-1-hardening-log.md](phase-1-1-hardening-log.md)
- [phase-1-2-verification-operationalization-log.md](phase-1-2-verification-operationalization-log.md)
- [autopilot-session-protocol.md](autopilot-session-protocol.md)
- [autoresearch-heuristic-protocol.md](autoresearch-heuristic-protocol.md)
- [autoresearch-benchmark-v1.md](autoresearch-benchmark-v1.md)
- [milestone-1.md](milestone-1.md)

## Implementation

Most recent completed product slice:

- execute the bounded Phase 1.3 CI wiring plan recorded in [phase-1-3-ci-wiring-log.md](phase-1-3-ci-wiring-log.md)

Goal:

- run the existing standardized verification wrapper in CI without changing the current UI, API, or analysis contracts

In scope:

- add a minimal CI job around [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)
- keep browser and chromedriver provisioning explicit wherever the CI path is defined
- preserve the current verdict mapping and warning posture behavior intact

Out of scope:

- redesigning the UI again
- changing heuristic thresholds or warning taxonomy
- adding a frontend framework
- expanding to multi-climber support or new climbing modes

Default next product slice:

- observe the first hosted run of [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml) and keep any follow-up bounded to CI stabilization or launch hygiene

## Verification

Read in order:

1. [README.md](../README.md)
2. [milestone-1.md](milestone-1.md)
3. [manual-verification.md](manual-verification.md)
4. [prd-status.md](prd-status.md)
5. [milestone-operations.md](milestone-operations.md)
6. [phase-1-3-ci-wiring-plan.md](phase-1-3-ci-wiring-plan.md)
7. [ui-revamp-phase-1-handoff.md](ui-revamp-phase-1-handoff.md)
8. [ui-phase-1-verification-log.md](ui-phase-1-verification-log.md)
9. [phase-1-1-hardening-log.md](phase-1-1-hardening-log.md)
10. [phase-1-2-verification-operationalization-log.md](phase-1-2-verification-operationalization-log.md)
11. [autopilot-session-protocol.md](autopilot-session-protocol.md)
12. [autoresearch-heuristic-protocol.md](autoresearch-heuristic-protocol.md)
13. [autoresearch-benchmark-v1.md](autoresearch-benchmark-v1.md)

If the slice touches the web app, also read:

14. [src/opencrux/templates/index.html](../src/opencrux/templates/index.html)
15. [src/opencrux/static/app.css](../src/opencrux/static/app.css)
16. [src/opencrux/static/app.js](../src/opencrux/static/app.js)
17. [tests/test_app.py](../tests/test_app.py)
18. [tests/test_browser_smoke.py](../tests/test_browser_smoke.py)

If the slice is heuristic tuning, also read:

14. [src/opencrux/heuristics.py](../src/opencrux/heuristics.py)
15. [evals/milestone1/benchmark-manifest-v1.json](../evals/milestone1/benchmark-manifest-v1.json)
16. [evals/milestone1/benchmark-expectations-v1.json](../evals/milestone1/benchmark-expectations-v1.json)
17. [evals/milestone1/baseline-score-v1.json](../evals/milestone1/baseline-score-v1.json)
18. [tests/test_heuristic_benchmark.py](../tests/test_heuristic_benchmark.py)

Local validation surface for the default next slice:

- [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)
- [tests/test_app.py](../tests/test_app.py)
- [tests/test_browser_smoke.py](../tests/test_browser_smoke.py)
- [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml)

## Review

The repo now also has a bounded heuristic autoresearch harness for supervised experiments.

Key surfaces:

- [src/opencrux/heuristics.py](../src/opencrux/heuristics.py)
- [scripts/run_autoresearch_benchmark.sh](../scripts/run_autoresearch_benchmark.sh)
- [evals/milestone1/benchmark-manifest-v1.json](../evals/milestone1/benchmark-manifest-v1.json)
- [evals/milestone1/benchmark-expectations-v1.json](../evals/milestone1/benchmark-expectations-v1.json)
- [evals/milestone1/baseline-score-v1.json](../evals/milestone1/baseline-score-v1.json)

If continuing the autoresearch track, the next bounded slice is:

1. inspect the latest promoted dry-run artifacts under [data/evals/runs](../data/evals/runs)
2. confirm whether the `multi_pose_warning_ratio=0.04` candidate should remain promoted based on [data/evals/runs/20260404T045717Z/benchmark-report.json](../data/evals/runs/20260404T045717Z/benchmark-report.json) and one more clean rerun of [tests/test_browser_smoke.py](../tests/test_browser_smoke.py)
3. if a new experiment is needed, make one new threshold-only hypothesis in [src/opencrux/heuristics.py](../src/opencrux/heuristics.py)
4. benchmark it before considering any further promotion

Keep this separate from the default product-roadmap slice. Do not turn it into an unbounded forever loop.

Residual risks to watch:

- avoid accidental regressions in the current live preview poll loop
- do not weaken the stored-session placeholder honesty for missing preview frames
- do not change backend payload schemas unless a real blocker is proven
- watch the first hosted GitHub Actions run to confirm the explicit browser provisioning behaves as expected on the remote runner

## Next Step

First recommended action next session:

- inspect the first hosted run of [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml) and decide whether any follow-up is needed

Suggested commands:

Targeted verification:

```bash
./scripts/run_targeted_verification.sh
```

Hosted CI definition:

```bash
sed -n '1,220p' .github/workflows/targeted-verification.yml
```

Prerequisites: local `chromium`, `chromium-browser`, or `google-chrome`, plus `chromedriver`, must be installed and available on `PATH` for the browser smoke portion.

Run the app:

```bash
PYTHONPATH=src python -m uvicorn opencrux.main:app --app-dir src --port 8000
```

Real clip verification artifacts already exist under:

- [data/samples/results/ui-phase1-verification](../data/samples/results/ui-phase1-verification)

## Ready-To-Use Fresh Session Prompt

Preferred prompt file:

- `/home/evan/.config/Code/User/prompts/opencrux-start-from-handoffs.prompt.md`

Workspace prompt for the supervised autoresearch track:

- [opencrux-autoresearch-supervised-dry-run.prompt.md](../.github/prompts/opencrux-autoresearch-supervised-dry-run.prompt.md)

```text
Act as the OpenCrux agent conductor for the next bounded slice.

Start by reading:
- README.md
- docs/milestone-1.md
- docs/manual-verification.md
- docs/prd-status.md
- docs/milestone-operations.md
- docs/phase-1-3-ci-wiring-plan.md
- docs/phase-1-3-ci-wiring-log.md
- docs/ui-revamp-phase-1-handoff.md
- docs/ui-phase-1-verification-log.md
- docs/phase-1-1-hardening-log.md
- docs/phase-1-2-verification-operationalization-log.md
- docs/autopilot-session-protocol.md
- docs/next-session-handover.md

Then inspect the first hosted CI run and the current targeted verification surface.

Execute the default next slice: observe the Phase 1.3 workflow result and keep any follow-up bounded to CI stabilization or launch hygiene.

Do not reopen UI redesign discovery. Keep the work bounded to implementation, verification, review, and a durable checkpoint.
```

Autoresearch fresh-session prompt:

```text
Use the workspace prompt at .github/prompts/opencrux-autoresearch-supervised-dry-run.prompt.md.

This should run one supervised heuristic experiment only.

Do not reopen product discovery and do not start an unbounded loop.
```