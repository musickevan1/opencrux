# Manual Verification Workflow

Use this workflow whenever OpenCrux heuristics change or when you want evidence from real climbing footage instead of synthetic tests.

## Allowed Footage Sources

- Your own climbing recordings
- Team-provided recordings with explicit permission to use them for development
- Openly licensed clips whose license clearly permits reuse and modification

Do not add arbitrary copyrighted videos from the internet to this repository.

## Clip Matrix

Stage at least three local clips under `data/samples/`:

1. `known-good.*`
   - Single climber
   - Stable framing
   - Bouldering or board session
   - Clear body visibility for most of the climb
2. `known-bad-occlusion.*`
   - Heavy occlusion, poor framing, or very short duration
3. `known-unsupported.*`
   - Multiple visible people, non-climbing footage, or otherwise unsupported conditions

Record clip notes in `data/samples/manifest.json` using the template in `data/samples/README.md`.

## Verification Steps

1. Run the CLI against each sample clip.

```bash
PYTHONPATH=src python -m opencrux.cli data/samples/known-good.mp4 --output data/samples/results/known-good.json
```

Or run the whole staged manifest at once:

```bash
PYTHONPATH=src python -m opencrux.cli --manifest data/samples/manifest.json --output data/samples/results
```

2. Confirm the known-good clip:
   - completes successfully
   - returns at least one attempt
   - returns metrics that are directionally plausible
   - surfaces no severe warning that contradicts the clip quality
3. Confirm the occlusion clip:
   - either completes with warning-heavy output or fails clearly
   - does not silently produce overconfident metrics
4. Confirm the unsupported clip:
   - fails clearly when multi-person footage dominates the clip
   - does not present itself as a supported success path
5. If the heuristics changed, rerun `PYTHONPATH=src pytest`.

## Autoresearch Promotion Gate

When a heuristic change comes from the bounded autoresearch workflow, run the benchmark gate before manual promotion review:

```bash
./scripts/run_autoresearch_benchmark.sh
```

Treat the benchmark as a contract guard, not as a replacement for the clip review in this document.

## UI State Checks

For the current web workspace, record these checks during manual verification:

1. Idle state:
   - the upload rail is the first obvious action
   - the frame stage is mounted even before analysis starts
   - history reads as secondary to the active workspace
2. Known-good clip:
   - the workspace moves from analyzing to a ready verdict
   - the frame stage, progress area, and scrubber stay in the same region during and after processing
   - headline metrics remain compact and warnings do not dominate
3. Known-bad-occlusion clip:
   - the workspace resolves to a caution posture or fails clearly
   - reliability notes appear before attempt cards and metrics
4. Known-unsupported clip:
   - the workspace resolves to a negative posture
   - the outcome does not read like a normal successful session
5. History reload:
   - recent sessions still refresh after a completed run
   - loading a stored session reuses the same workspace
   - the frame stage shows an honest placeholder when stored preview frames are unavailable
6. Mobile layout:
   - the order remains intake, status and verdict, frame stage, summary, evidence, then history

## Repeatable Browser Smoke

Run this repo-standard verification surface when the work touches intake locking, history lockout, or mobile ordering:

```bash
./scripts/run_targeted_verification.sh
```

This wrapper runs [tests/test_app.py](../tests/test_app.py) and [tests/test_browser_smoke.py](../tests/test_browser_smoke.py) together so the browser harness stays paired with the targeted app checks.

Prerequisites: local `chromium`, `chromium-browser`, or `google-chrome`, plus `chromedriver`, must be installed and available on `PATH`.

The same wrapper now runs in GitHub Actions through [.github/workflows/targeted-verification.yml](../.github/workflows/targeted-verification.yml), with browser binaries provisioned explicitly before the script executes.

This suite uses fake analyzers and a temporary local app instance to verify:

- submit, history refresh, and history selection lock from click through job resolution
- ready, caution, and negative verdict transitions
- history reload into the same workspace region
- mobile section ordering

This smoke pass complements real clip verification. It does not replace the known-good, known-bad, and known-unsupported footage checks.

## What To Record

- Clip id and local filename
- Whether the run completed or failed
- Warning codes returned
- Attempt count
- Notes on whether the metrics felt directionally correct
- Follow-up actions, if any

The batch manifest runner writes one JSON file per clip plus `summary.json` under the output directory.

## Review Gate

The first slice is behaving acceptably only when all of the following are true:

- One known-good clip completes successfully.
- One known-bad clip either fails clearly or returns warning-heavy output.
- One known-unsupported clip does not pass as a clean success.
- The result remains explainable from timestamps and visible motion.
- Autoresearch-driven heuristic changes pass benchmark v1 before promotion.
