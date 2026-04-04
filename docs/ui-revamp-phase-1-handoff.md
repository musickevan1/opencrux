# UI Revamp Phase 1 Handoff

## Workflow Status

- Discovery: complete
- Phase 1 milestone scope: implemented
- Verification gate: satisfied
- Review gate: approved for sign-off

## Current Checkpoint

- Phase 1 code implementation is in place across the static UI, targeted tests, and milestone verification docs.
- Automated verification status on 2026-04-03: `tests/test_app.py` passed with 8 tests.
- Real clip verification evidence and browser captures are recorded in [ui-phase-1-verification-log.md](ui-phase-1-verification-log.md).
- Current recommendation: treat Phase 1 as review-complete and move next into a small hardening slice rather than more redesign work.

This document is the conductor packet for moving the UI revamp from discovery into milestone execution.

It resolves the open Phase 1 policy gaps left intentionally broad in [ui-revamp-plan.md](ui-revamp-plan.md) so implementation can proceed without inventing product behavior mid-stream.

For restart-safe multi-session orchestration, use [autopilot-session-protocol.md](autopilot-session-protocol.md) together with this handoff.

## Goal

Ship one milestone slice that recomposes the current FastAPI-served page into a single active-session workspace.

The slice must:

- preserve the current static HTML, CSS, and vanilla JS stack
- preserve polling-based live updates and the 12-item history model
- make unsupported or warning-heavy outcomes visually primary before metrics
- keep the annotated frame stage stable across idle, live, completed, caution, and negative states

## Scope

In scope:

- compact masthead and intake rail
- one dominant active analysis workspace
- verdict-first status model
- stable frame stage with existing scrubber and thumbnail behavior
- headline summary metrics
- evidence section with warnings before attempts
- secondary history shelf with compact posture chips
- narrow tests and documentation updates needed for this slice

## Non-Goals

- no frontend framework or separate frontend toolchain
- no backend schema changes for job or session payloads
- no history pagination, filters, or comparisons
- no saved preview frame persistence for history sessions
- no redesign of analysis heuristics or warning generation

## Entry Criteria

- The discovery brief exists in [ui-revamp-plan.md](ui-revamp-plan.md).
- Existing API smoke coverage is passing in [tests/test_app.py](../tests/test_app.py).
- The current milestone and footage workflow remain the source of truth in [milestone-1.md](milestone-1.md) and [manual-verification.md](manual-verification.md).

## Phase 1 Policy Decisions

### Verdict Mapping

Phase 1 will derive visual verdicts entirely client-side from existing job and session payloads.

Use this mapping:

| Verdict | Trigger | Notes |
| --- | --- | --- |
| `idle` | No active job and no selected history session | Neutral posture with upload as the clear next action |
| `analyzing` | Active job status is `queued` or `running` | Progress, stage, live warnings, and scrubber remain primary |
| `ready` | Completed session with no warning severity above `info` and no caution-class warning codes | Clean supported posture |
| `caution` | Completed session includes any warning with severity `warning` or warning code in the caution list | Output is usable but explicitly lower confidence |
| `negative` | Active job status is `failed`, or live preview contains an `error` severity warning | Strongest posture on the page |

Phase 1 caution-class warning codes:

- `low_pose_coverage`
- `low_visibility`
- `multiple_people_detected`
- `attempt_segmentation_ambiguous`

Phase 1 negative mapping:

- If `error_message` contains `multiple climbers`, `one dominant climber`, or `unsupported`, label the verdict as `Unsupported footage`.
- Otherwise label the verdict as `Analysis failed`.

History sessions are persisted only on completed analysis today, so history cards can show `ready` or `caution`, but not `negative` in Phase 1.

### Single-Active-Session Rule

Phase 1 enforces single-focus behavior in the UI without changing backend concurrency.

Rules:

- When a job is `queued` or `running`, the upload submit action is disabled after job creation until the job resolves.
- While a job is active, history item selection and history refresh are disabled.
- The backend may still support concurrent jobs from other clients or direct API calls, but this page presents only one active workspace at a time.
- No queue management UI is introduced in Phase 1.

### History Recall Rule

- Clicking a history item replaces the active workspace content in the same screen region.
- History never opens a separate results-only view.
- If the selected history session has no preview frame, the frame stage remains mounted and shows an explicit placeholder that the annotated preview is unavailable for stored sessions.

### Minimum Retained Evidence Set

Always visible in the main workspace after a completed run:

- verdict band
- current status or outcome message
- frame stage
- headline summary metrics:
  - attempts
  - time on wall
  - average rest
  - vertical progress
  - visibility
- warnings block
- attempts block

Supporting details may move below the fold or into lighter secondary treatment:

- lateral span
- hesitation marker count
- sampled FPS
- source duration
- live-only diagnostics such as visible points or multi-pose rate

## System Areas Affected

- [src/opencrux/templates/index.html](../src/opencrux/templates/index.html)
- [src/opencrux/static/app.css](../src/opencrux/static/app.css)
- [src/opencrux/static/app.js](../src/opencrux/static/app.js)
- [tests/test_app.py](../tests/test_app.py)
- [manual-verification.md](manual-verification.md)
- [milestone-1.md](milestone-1.md)

Contract surfaces assumed stable for Phase 1:

- [src/opencrux/main.py](../src/opencrux/main.py)
- [src/opencrux/models.py](../src/opencrux/models.py)
- [src/opencrux/analysis.py](../src/opencrux/analysis.py)

## Ordered Steps

1. Restructure [src/opencrux/templates/index.html](../src/opencrux/templates/index.html) into one active-session workspace with these regions: masthead, intake rail, workspace shell, verdict band, summary, evidence, and secondary history.
2. Rebuild [src/opencrux/static/app.css](../src/opencrux/static/app.css) as a tokenized layout system with distinct styles for workspace shell, verdict states, evidence cards, and history chips.
3. Refactor [src/opencrux/static/app.js](../src/opencrux/static/app.js) around one render path driven by `activeJob`, `activeSession`, `selectedPreviewFrameIndex`, and derived verdict state.
4. Preserve the current polling cadence, preview scrubber, thumbnail behavior, and history fetch limit of 12.
5. Enforce the single-active-session rule in the UI by disabling submit, history reload, and history session selection during active jobs.
6. Sort warnings by severity and render them before metrics in both live and completed views.
7. Keep the last in-memory preview frame visible when a job completes or fails.
8. Add narrow test coverage in [tests/test_app.py](../tests/test_app.py) for the new HTML anchors plus at least one failed-job polling path.
9. Update [manual-verification.md](manual-verification.md) and [milestone-1.md](milestone-1.md) to reflect the verdict-first UI acceptance and manual state checks.

## Verification Matrix

### Automated

Add or retain these checks in [tests/test_app.py](../tests/test_app.py):

- root route HTML smoke test for workspace shell, verdict section, analysis form, and history shelf anchors
- supported job preview-to-completion flow
- failed job polling flow with user-visible `error_message`
- session listing still capped by request limit behavior
- persisted session reload by id still works
- bad extension rejection still works

### Manual

Run the clip matrix from [manual-verification.md](manual-verification.md) and record:

1. idle state with no active session
2. analyzing state on known-good footage
3. ready state on known-good footage
4. caution state on known-bad-occlusion footage
5. negative state on known-unsupported footage
6. history reload behavior after completion and via manual refresh
7. mobile priority order

### Evidence Required Before Review

- passing targeted automated checks
- manual verification notes for the five UI states plus history reload
- screenshots or short captures of desktop and mobile layouts for ready, caution, and negative states

## Risks And Dependencies

- Verdict mapping depends on current warning codes and error messages remaining stable.
- The UI-only single-focus rule does not prevent concurrent jobs outside this page.
- Stored history sessions do not include preview frames, so the placeholder state must be explicit and honest.
- Without browser automation, visual confidence depends on disciplined manual verification.

## Rollback Notes

Rollback is front-end only for Phase 1.

Revert together if needed:

- [src/opencrux/templates/index.html](../src/opencrux/templates/index.html)
- [src/opencrux/static/app.css](../src/opencrux/static/app.css)
- [src/opencrux/static/app.js](../src/opencrux/static/app.js)
- [tests/test_app.py](../tests/test_app.py)
- [manual-verification.md](manual-verification.md)
- [milestone-1.md](milestone-1.md)

## Agent Handoffs

### To Implementer

Implement Phase 1 only.

Constraints:

- keep the current FastAPI-served static UI architecture
- do not add React or a separate frontend toolchain
- do not change backend API schemas unless a hard blocker is proven
- preserve polling, preview scrubber, thumbnail history, and 12-item recent history behavior

Success condition:

- the UI reads as one continuous verdict-first workspace and passes the verification matrix in this document

### To Verifier

Validate the completed Phase 1 implementation against:

- [milestone-1.md](milestone-1.md)
- [manual-verification.md](manual-verification.md)
- this handoff document

Focus on:

- five UI states
- history reload behavior
- warning prominence over metrics
- unsupported footage not reading as a successful session

### To Reviewer

Review the completed Phase 1 change for:

- regressions in polling, preview continuity, and history behavior
- consistency between the implemented verdict mapping and the policy in this document
- whether the redesign stayed within milestone scope without adding frontend architecture overhead

## Recommendation

Phase 1 is complete enough for sign-off. Use this handoff together with [ui-phase-1-verification-log.md](ui-phase-1-verification-log.md) as the closed execution record, then move to a narrow hardening slice rather than reopening the redesign itself.