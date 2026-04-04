# UI Phase 1 Verification Log

## Scope

This log records the verification and readiness evidence for the Phase 1 UI revamp.

Source of truth for the slice:

- [milestone-1.md](milestone-1.md)
- [manual-verification.md](manual-verification.md)
- [ui-revamp-phase-1-handoff.md](ui-revamp-phase-1-handoff.md)

## Automated Evidence

- Targeted app verification passed on 2026-04-03.
- Command: `PYTHONPATH=src /home/evan/Projects/opencrux/.venv/bin/python -m pytest tests/test_app.py -rA`
- Result: 8 passing tests in [tests/test_app.py](../tests/test_app.py)

Covered behaviors:

- root HTML workspace shell is present
- health endpoint responds
- successful session analysis persists
- bad extension rejection works
- session listing works and honors requested limit
- streaming analysis jobs complete
- failed analysis jobs expose a pollable negative path

## Real Clip Matrix Evidence

Batch output directory:

- [data/samples/results/ui-phase1-verification](../data/samples/results/ui-phase1-verification)

Result summary:

- [summary.json](../data/samples/results/ui-phase1-verification/summary.json)

Clip outcomes:

1. Known-good:
   - [known-good.json](../data/samples/results/ui-phase1-verification/known-good.json)
   - completed successfully
   - warning count: 0
   - attempts: 1
   - metrics remained directionally plausible for the supported slice
2. Known-bad-occlusion:
   - [known-bad-occlusion.json](../data/samples/results/ui-phase1-verification/known-bad-occlusion.json)
   - completed with warning posture
   - warning code: `multiple_people_detected`
   - attempts: 1
   - did not present as a clean warning-free success
3. Known-unsupported:
   - [known-unsupported.json](../data/samples/results/ui-phase1-verification/known-unsupported.json)
   - failed clearly
   - error message explicitly states that the current slice supports one dominant climber per video

## Browser Evidence

Idle workspace evidence:

- [idle-dom.html](../data/samples/results/ui-phase1-verification/idle-dom.html)
- [selenium-idle-desktop.png](../data/samples/results/ui-phase1-verification/selenium-idle-desktop.png)
- [selenium-idle-mobile.png](../data/samples/results/ui-phase1-verification/selenium-idle-mobile.png)

Desktop state captures:

- [selenium-ready-desktop.png](../data/samples/results/ui-phase1-verification/selenium-ready-desktop.png)
- [selenium-caution-desktop.png](../data/samples/results/ui-phase1-verification/selenium-caution-desktop.png)
- [selenium-analyzing-desktop.png](../data/samples/results/ui-phase1-verification/selenium-analyzing-desktop.png)
- [selenium-negative-desktop.png](../data/samples/results/ui-phase1-verification/selenium-negative-desktop.png)

Mobile state captures:

- [selenium-ready-mobile.png](../data/samples/results/ui-phase1-verification/selenium-ready-mobile.png)
- [selenium-caution-mobile.png](../data/samples/results/ui-phase1-verification/selenium-caution-mobile.png)
- [selenium-negative-mobile.png](../data/samples/results/ui-phase1-verification/selenium-negative-mobile.png)

Structured Selenium notes:

- [selenium-verification.json](../data/samples/results/ui-phase1-verification/selenium-verification.json)

Verified UI behaviors from browser automation:

- idle desktop status reads `Idle`
- history reload preserved the active stored session title `known-good.mp4`
- history refresh still returned 4 items during the recorded pass
- stored session placeholder copy is explicit about missing persisted preview frames
- negative verdict title reads `Unsupported footage likely`
- negative verdict message explicitly calls out unsupported multi-climber footage
- mobile ordering satisfies:
  - intake
  - status
  - verdict
  - frame stage
  - summary
  - evidence
  - history

## Manual-State Equivalence Notes

The original handoff asked for manual UI state notes. In this session, those checks were executed through scripted browser interaction against the live app plus screenshot inspection.

Covered state set:

- idle
- analyzing
- ready
- caution
- negative
- history reload
- mobile ordering

This is sufficient for Phase 1 sign-off within the available tool surface.

## Readiness Judgment

Phase 1 is review-complete and ready for sign-off.

Why:

- automated tests are passing
- supported, caution, and unsupported pipeline outcomes are evidenced on real clips
- desktop and mobile UI captures exist for ready, caution, and negative states
- history reload and stored-session placeholder behavior are evidenced
- the final readiness review found no significant blockers

## Residual Risk

One small hardening risk remains:

- the intake lock is strongest after the job state becomes active, but a very small duplicate-submit window may exist before the create-job response resolves

This is not a Phase 1 blocker.

## Recommended Next Slice

Move to a narrow Phase 1.1 hardening pass:

1. make the single-focus lock atomic from submit click through job creation
2. keep history and intake lockout atomic for the entire active-job lifecycle
3. preserve the existing UI and analysis contracts while making the browser evidence workflow more repeatable