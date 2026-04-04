# Phase 1.3 CI Wiring Log

## Discovery

This slice executed the bounded Phase 1.3 plan in [phase-1-3-ci-wiring-plan.md](phase-1-3-ci-wiring-plan.md).

Initial findings:

- the repo had no [.github/workflows](../.github/workflows) directory, so the targeted verification wrapper was still local-only
- the standardized verification entry point was already stable and documented as [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh)
- a rerun of the browser smoke suite reproduced the previously noted stale-element failure during history refresh in [tests/test_browser_smoke.py](../tests/test_browser_smoke.py), so the CI pass needed a small harness hardening change before the workflow could be trusted

## Implementation

- added [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml) as the minimal always-on CI surface for targeted verification on push and pull request
- kept the local and CI verification commands aligned by invoking only [scripts/run_targeted_verification.sh](../scripts/run_targeted_verification.sh) from the workflow
- made browser provisioning explicit in CI by installing browser binaries with `browser-actions/setup-chrome` and exposing `google-chrome` and `chromedriver` on `PATH` before the wrapper runs
- hardened the history-selection step in [tests/test_browser_smoke.py](../tests/test_browser_smoke.py) so the protected lifecycle path re-queries refreshed history items instead of clicking a stale Selenium handle after history refresh
- updated [README.md](../README.md) and [manual-verification.md](manual-verification.md) so the documented CI path points to the same wrapper instead of implying a separate command surface

## Verification

Local verification completed with the standardized wrapper:

- `./scripts/run_targeted_verification.sh`
- `./scripts/run_targeted_verification.sh -k protected_lifecycle --maxfail=1`

Verification result for this session:

- the full targeted surface passed locally through the repo-standard task and wrapper command surface with 15 tests
- the previously flaky protected lifecycle test passed on a focused wrapper-driven rerun after the history-click hardening change
- the CI workflow calls the same wrapper as local use and does not introduce a divergent pytest command

## Review

Findings:

- no UI, API, or heuristic behavior changed for this slice
- the only code change outside documentation is test-harness hardening for a known browser-smoke flake that would otherwise make CI noisy
- browser provisioning is explicit in automation rather than assumed from the hosted runner image

Residual risk:

- the new workflow is defined locally but cannot be executed from this workspace alone, so the first remote GitHub Actions run is still the real proof of hosted-runner behavior
- launch hygiene remains open beyond targeted verification wiring

## Next Step

Recommended next bounded slice:

1. observe the first remote run of [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml)
2. if the browser smoke path stays green, move to the next launch-hygiene slice instead of expanding CI scope prematurely
3. if hosted CI exposes a new browser-specific failure mode, keep the follow-up bounded to failure artifact capture or smoke-test stabilization rather than product behavior changes