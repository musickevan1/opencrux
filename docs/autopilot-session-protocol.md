# Autopilot Session Protocol

## Purpose

OpenCrux should not be driven by an unbounded prompt like "keep improving until launch".

That loses context, expands scope, and encourages inconsistent product decisions across sessions.

Use a bounded conductor loop instead:

1. load the canonical artifacts
2. select one milestone-sized slice
3. plan it
4. implement it
5. verify it
6. review it
7. leave a clean checkpoint for the next session

## Canonical Context Order

Every new session should read these in order before doing substantial work:

1. [README.md](../README.md)
2. [docs/milestone-1.md](milestone-1.md)
3. [docs/manual-verification.md](manual-verification.md)
4. [docs/prd-status.md](prd-status.md)
5. [docs/milestone-operations.md](milestone-operations.md)
6. [docs/ui-revamp-plan.md](ui-revamp-plan.md)
7. [docs/ui-revamp-phase-1-handoff.md](ui-revamp-phase-1-handoff.md)
8. [docs/ui-phase-1-verification-log.md](ui-phase-1-verification-log.md)
9. [docs/phase-1-1-hardening-log.md](phase-1-1-hardening-log.md)
10. [docs/phase-1-2-verification-operationalization-log.md](phase-1-2-verification-operationalization-log.md)
11. [docs/next-session-handover.md](next-session-handover.md)

If the task touches analysis heuristics, also read:

11. [src/opencrux/analysis.py](../src/opencrux/analysis.py)
12. [tests/test_analysis.py](../tests/test_analysis.py)

If the task touches the web app, also read:

11. [src/opencrux/templates/index.html](../src/opencrux/templates/index.html)
12. [src/opencrux/static/app.css](../src/opencrux/static/app.css)
13. [src/opencrux/static/app.js](../src/opencrux/static/app.js)
14. [tests/test_app.py](../tests/test_app.py)
15. [tests/test_browser_smoke.py](../tests/test_browser_smoke.py)
16. [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)

## Continuity Rules

1. Never restart from an open-ended product mandate. Restart from the latest milestone handoff.
2. One session should own one bounded slice unless verification shows the slice is incomplete.
3. Every session ends with an updated checkpoint artifact or milestone artifact, not just chat text.
4. When heuristics change, update tests and the milestone document together.
5. When UI behavior changes, update manual verification guidance if user-visible states changed.
6. Use repo memory for stable repo facts and current milestone posture.
7. Use session memory only for temporary working state within the current conversation.
8. Prefer the repo-local milestone structure in [milestone-operations.md](milestone-operations.md) over creating a second project-management system unless milestone scale proves it necessary.

## Bounded Conductor Loop

### Step 1: Load State

- read the canonical artifacts
- inspect changed files
- check existing tests relevant to the current slice
- identify the highest-value unresolved gap

### Step 2: Choose One Slice

Acceptable slices:

- one UI milestone such as the current Phase 1 workspace revamp
- one heuristic improvement with corresponding tests and verification
- one release-readiness gap such as failure handling, verification evidence, or documentation quality

Reject as too broad:

- "launch the whole product"
- "improve ML model and UI and testing in parallel"
- "keep iterating forever"

### Step 3: Spawn Roles In Order

Use the repo workflow boundary:

1. `Researcher` or `Planner` for discovery and implementation framing
2. `Implementer` for code changes
3. `Verifier` for automated and manual validation
4. `Reviewer` for residual risk and release readiness

Parallelize only the read-only stages when they do not depend on each other.

### Step 4: Execute The Slice

- keep changes narrow
- preserve local-first and deterministic behavior
- prefer explainable heuristics over opaque model work
- avoid introducing a frontend toolchain unless the static UI is the actual blocker

### Subordinate Autoresearch Loop

When the chosen slice is deterministic heuristic tuning, use the bounded autoresearch path instead of an open-ended iteration loop.

- mutable surface: [src/opencrux/heuristics.py](../src/opencrux/heuristics.py)
- benchmark contract: [docs/autoresearch-benchmark-v1.md](autoresearch-benchmark-v1.md)
- workflow rules: [docs/autoresearch-heuristic-protocol.md](autoresearch-heuristic-protocol.md)

Required sequence:

1. lock benchmark expectations
2. make one bounded heuristic hypothesis
3. run [scripts/run_autoresearch_benchmark.sh](../scripts/run_autoresearch_benchmark.sh)
4. reject immediately on hard-gate failure
5. run [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh) only for candidates worth promoting
6. update checkpoint docs if anything is kept

### Step 5: Leave A Checkpoint

At the end of the slice, update one or more of:

- [docs/milestone-1.md](milestone-1.md)
- [docs/ui-revamp-phase-1-handoff.md](ui-revamp-phase-1-handoff.md)
- [docs/manual-verification.md](manual-verification.md)
- a new bounded handoff document if the next slice needs one

The checkpoint must capture:

- what changed
- what was verified
- what remains open
- what the next session should do first

Recommended section shape:

- Discovery
- Implementation
- Verification
- Review
- Next Step

## Current Default Next Slice

Unless the user explicitly reprioritizes, the next implementation slice is:

- run a Phase 1.3 CI wiring pass after the completed Phase 1.2 verification operationalization slice

Why this is the default:

- the UI revamp, hardening pass, and verification operationalization pass are implemented and verified
- the next highest-value gap is making the standardized verification surface less operator-dependent
- the remaining risk is bounded and does not require heuristic expansion or frontend stack changes

## Launch Readiness Should Mean

OpenCrux is only ready to launch this first slice when all of the following are true:

- supported clips complete with explainable results
- unsupported clips fail clearly
- warning-heavy clips do not read as trustworthy
- the UI makes reliability obvious before metrics
- automated tests cover the key API and heuristic contracts
- manual verification evidence exists for known-good, known-bad, and known-unsupported footage
- the repo has a clear milestone state and next-step documentation

## Refined Reusable Prompt

Use this prompt for new sessions instead of an open-ended autopilot request:

```text
Act as the OpenCrux agent conductor for one bounded milestone slice.

Start by reading, in order:
- README.md
- docs/milestone-1.md
- docs/manual-verification.md
- docs/prd-status.md
- docs/ui-revamp-plan.md
- docs/ui-revamp-phase-1-handoff.md
- docs/ui-phase-1-verification-log.md
- docs/phase-1-1-hardening-log.md
- docs/phase-1-2-verification-operationalization-log.md
- docs/next-session-handover.md
- docs/autopilot-session-protocol.md

Then inspect current changed files and relevant tests.

Choose the highest-value unresolved slice that can be completed within the existing workflow boundary of discovery, implementation, verification, and review.

If a slice is already planned and handed off, do not re-plan the whole product. Execute that slice.

Use subagents only for bounded roles:
- Planner or Researcher for read-only framing
- Implementer for code
- Verifier for validation
- Reviewer for final risk assessment

Parallelize only read-only stages when appropriate.

Constraints:
- keep the first slice local-first and deterministic
- prefer explainable heuristics over opaque scoring models
- treat unsupported footage as a first-class outcome
- avoid introducing a separate frontend toolchain unless the current static UI is the clear blocker
- when changing analysis heuristics, update tests and milestone docs together

At the end of the session, leave a durable checkpoint in repo docs summarizing:
- what changed
- what was verified
- open risks
- the exact next recommended slice
```

## Anti-Drift Rules

Do not let future sessions drift into these without explicit approval:

- general "ML improvement" with no metric or footage constraint
- multi-climber support
- route difficulty inference
- technique scoring claims that cannot be explained from timestamps or visible motion
- frontend stack migration for aesthetic reasons alone

## Recommendation

Use this protocol as the first read for any new multi-agent OpenCrux session that aims to make milestone progress without losing context.

## Context Rollover Guidance

The assistant cannot see exact context-window token usage and cannot open a brand-new chat session by itself.

Use heuristic rollover instead:

- if a bounded slice is complete and the next step is a new slice, prefer a fresh session
- if the conversation now contains planning, implementation, verification, and review state for multiple slices, prefer a fresh session
- before rollover, update the durable checkpoint docs and provide an exact next-session handoff prompt

User-level customizations now exist for this:

- `/home/evan/.config/Code/User/prompts/opencrux-context-rollover.instructions.md`
- `/home/evan/.config/Code/User/prompts/opencrux-fresh-session-handoff.prompt.md`

Current manual-development handoff artifact:

- [next-session-handover.md](next-session-handover.md)