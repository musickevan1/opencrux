# PRD Status

## Product

OpenCrux

## Product Goal

Deliver a local-first climbing analytics slice for recorded single-climber bouldering or board footage that produces explainable, timestamp-linked outputs and fails clearly on unsupported conditions.

## Current Phase

Milestone 2 — Gemma 4 vision-language coaching insights

Status:

- implemented
- tests passing (30 LLM backend tests + all M1 tests green)

Supporting records:

- [milestone-2.md](milestone-2.md)
- [milestone-2-gemma4-plan.md](milestone-2-gemma4-plan.md)
- [milestone-operations.md](milestone-operations.md)

Previous milestone:

- Milestone 1 vertical slice — verified, signed off
- [milestone-1.md](milestone-1.md)

## Operating Model

OpenCrux now uses a lightweight repo-local milestone structure instead of a separate project-management layer.

Management surfaces:

- [milestone-operations.md](milestone-operations.md) for status vocabulary, artifact rules, and slice shape
- [milestone-1.md](milestone-1.md) for current milestone scope and acceptance criteria
- [next-session-handover.md](next-session-handover.md) for the live checkpoint and exact next-step guidance

## What Is Done

Product behavior currently evidenced:

- supported recorded clips complete successfully
- unsupported multi-climber clips fail clearly
- warning-heavy footage does not present as a clean success path
- session persistence and reload work locally
- the UI presents a verdict-first workspace with live preview, scrubber, and secondary history
- intake and history interactions lock atomically from submit click through job resolution
- automated app and browser checks cover the main HTML, API wiring, and protected browser workflow surfaces for the current slice
- the targeted web verification path is available through [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh), the `verify: targeted web smoke` task in [.vscode/tasks.json](../.vscode/tasks.json), and [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml)

## What Is Not Done

Still outside the current slices:

- end-to-end manual verification of LLM insights with real climbing footage and a running Ollama instance
- prompt iteration and quality tuning for coaching output
- launch packaging and release process
- broader heuristic expansion beyond the narrow supported footage conditions
- license decision for public publication

## Current Scope Boundaries

In scope for the product right now:

- single dominant climber in frame
- recorded bouldering or board footage
- deterministic and explainable metrics
- conservative attempt segmentation
- local persistence and local web review

Explicitly not in scope right now:

- multi-climber analysis
- route difficulty inference
- technique scoring claims that are not explainable from visible motion
- frontend stack migration for cosmetic reasons alone

## Evidence Snapshot

Automated evidence:

- [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh) currently passes with 15 tests across [tests/test_app.py](../tests/test_app.py) and [tests/test_browser_smoke.py](../tests/test_browser_smoke.py)
- [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml) runs the same wrapper in CI with explicit browser provisioning

Real clip evidence:

- [summary.json](../data/samples/results/ui-phase1-verification/summary.json)

Browser evidence:

- [selenium-verification.json](../data/samples/results/ui-phase1-verification/selenium-verification.json)
- [selenium-ready-desktop.png](../data/samples/results/ui-phase1-verification/selenium-ready-desktop.png)
- [selenium-caution-desktop.png](../data/samples/results/ui-phase1-verification/selenium-caution-desktop.png)
- [selenium-negative-desktop.png](../data/samples/results/ui-phase1-verification/selenium-negative-desktop.png)
- [phase-1-1-hardening-log.md](phase-1-1-hardening-log.md)

## Residual Risk

Current non-blocking risks:

- the first hosted run of the new targeted verification workflow still needs observation because it cannot be executed from this local workspace alone
- launch hygiene remains open around packaging and publication decisions

## Recommended Next Product Slice

End-to-end LLM insights verification with real footage

Objective:

- run a real climbing clip through the pipeline with `OPENCRUX_GEMMA_ENABLED=true` and Ollama serving `gemma4:e4b`, verify the UI renders coaching insights correctly, and iterate on prompt quality if needed

Success looks like:

- `llm_insights` populated in the session JSON with technique scores, coaching tips, and session summary
- the UI renders all insight fields without layout issues
- prompt output is specific and actionable for climbing technique

## Launch Readiness Status

Not launch-ready as a public product yet.

Reason:

- the first milestone slice is working and now has always-on targeted verification wiring, but launch hygiene still needs follow-through around release process, publication decisions, and hosted-runner observation

## Decision Summary

Do not reopen discovery for the UI revamp.

Use the current verified slice as the product baseline and proceed with small, high-confidence operationalization work next.