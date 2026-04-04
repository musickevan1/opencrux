# Phase 1.1 Hardening Log

## Scope

This log records the bounded Phase 1.1 hardening slice that followed the completed Milestone 1 UI revamp.

Source of truth for the slice:

- [prd-status.md](prd-status.md)
- [next-session-handover.md](next-session-handover.md)
- [manual-verification.md](manual-verification.md)

## Implemented Changes

- the web client now locks intake and history interactions immediately on submit, before the create-job response resolves
- the same interaction lock now protects submit, form fields, history refresh, and history session selection for the full active-job lifecycle, including degraded recovery when polling or create-job responses are interrupted
- structured API validation details are converted into readable status messages instead of leaking object-shaped errors into the UI
- a repeatable Selenium smoke test now drives the real page in Chromium against a temporary FastAPI app with fake analyzers and seeded history

## Automated Evidence

- Command: `PYTHONPATH=src python -m pytest tests/test_app.py tests/test_browser_smoke.py -rA`
- Result on 2026-04-03: 15 passing tests

Covered behaviors:

- root HTML workspace shell still renders
- analysis jobs still stream preview state and complete or fail cleanly
- bad extension rejection and session-list limit behavior still work
- submit, history refresh, and history selection lock immediately on click and stay locked until the job resolves
- ready, caution, and negative verdict flows remain reachable in the real browser
- interrupted create-job responses auto-recover from persisted history when possible and fail clear after bounded recovery when no completed session appears
- persistent poll failures auto-recover from persisted history when possible and fail clear after bounded recovery when no completed session appears
- structured validation detail arrays render as readable status copy instead of object-shaped errors
- history reload still reuses the same workspace region
- mobile ordering remains intake, status, verdict, frame stage, summary, evidence, then history

## Review Notes

Findings:

- no regression was found in the polling loop, stored-session placeholder honesty, or verdict mapping during the targeted verification pass
- transient or persistent poll failures now surface a readable retry message while the workspace stays locked, and the client auto-recovers from persisted history once the completed session is available

Operational readiness:

- the new browser smoke path is repeatable locally on machines with Chromium and chromedriver available
- the smoke suite is not wired into CI yet, so verification remains operator-invoked rather than always-on

Residual risk:

- browser smoke coverage is still local-only and depends on the local Chromium toolchain
- launch hygiene remains open around packaging, publication decisions, and broader release process work

## Recommended Next Slice

Move to one bounded operationalization slice:

1. promote the new browser smoke coverage into a standard CI-ready or task-driven verification path without changing product behavior
2. keep the current UI, API, and analysis contracts stable while reducing operator-only verification steps