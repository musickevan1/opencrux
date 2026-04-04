# Phase 1.3 CI Wiring Plan

## Goal

- run the existing targeted verification wrapper in a minimal CI surface without changing OpenCrux product behavior or widening product scope

## Scope

In scope:

- add CI-ready wiring around [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)
- keep browser dependency setup explicit
- keep the local and CI command surfaces aligned
- preserve the existing targeted app and browser smoke coverage contract

Out of scope:

- UI redesign or frontend stack changes
- analysis heuristic tuning beyond the already checkpointed bounded autoresearch track
- payload schema changes unrelated to CI wiring
- launch packaging or release automation beyond this targeted verification path

## Discovery

- [prd-status.md](prd-status.md) already identifies Phase 1.3 CI wiring as the default next product slice
- [phase-1-2-verification-operationalization-log.md](phase-1-2-verification-operationalization-log.md) established the repo-standard wrapper and VS Code task
- [next-session-handover.md](next-session-handover.md) captures the current verification posture and the bounded autoresearch checkpoint
- the relevant command surface is already stable: [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)

Current constraints:

- keep the first slice local-first and deterministic
- do not change the verified verdict mapping or warning posture while adding automation wiring
- browser prerequisites must be explicit instead of assumed

## Implementation

Expected surfaces to change:

- CI definition files if the repo does not already have the needed workflow wiring
- docs that point to the new CI-ready verification path
- checkpoint docs that record the resulting automation status

Expected surfaces to stay untouched unless a real blocker appears:

- [src/opencrux/main.py](../src/opencrux/main.py)
- [src/opencrux/static/app.js](../src/opencrux/static/app.js)
- [src/opencrux/static/app.css](../src/opencrux/static/app.css)
- [src/opencrux/heuristics.py](../src/opencrux/heuristics.py)

## Verification

Automated checks:

- run [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)
- if CI wiring is added, confirm the workflow invokes the same wrapper rather than a divergent command path

Manual review:

- confirm browser dependencies are provisioned explicitly in the automation definition
- confirm docs do not describe a different verification command for CI than for local use

Promotion criteria:

- the standardized wrapper remains the single source of truth for targeted verification
- the current targeted checks still pass locally
- the CI wiring is minimal, explicit, and does not reopen unrelated product surfaces

## Review

Known residual risk at plan time:

- browser smoke has shown an intermittent stale-element failure on rerun in `test_browser_smoke_protected_lifecycle`, although a focused rerun passed afterward
- CI wiring should not mask that flake; it should only make the current verification surface repeatable

Decision summary:

- proceed with a narrow CI wiring slice rather than adding a broader project-management system or reopening product discovery

## Next Step

- inspect the repo for existing CI workflow files and wire the standardized wrapper into the minimal appropriate workflow surface
- first command next session: `ls .github && ls .github/workflows 2>/dev/null || true`