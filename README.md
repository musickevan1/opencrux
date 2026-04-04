# OpenCrux

OpenCrux is a local-first prototype for climbing analytics. The first slice stays narrow on purpose: upload a recorded single-climber bouldering or board session, extract pose data with MediaPipe and OpenCV, derive a small set of explainable metrics, persist the result, and review it in a lightweight web UI.

## Current Slice

- Recorded single-climber video analysis
- Explainable metrics only
- Local persistence for sessions and derived analysis
- Static web UI served directly by the Python app
- Live analysis preview with MediaPipe landmark overlays while a clip is processing
- Frame scrubber and provisional attempt or warning state during in-flight analysis
- **Optional Gemma 4 AI insights** — technique scoring, movement descriptions, and coaching tips

## Gemma 4 AI Insights (Optional)

OpenCrux can augment its MediaPipe analysis with **Gemma 4** edge models for climbing-specific reasoning. This adds technique scores, movement descriptions, difficulty estimates, and coaching tips — all processed locally.

### Setup

Install with the `llm` extra to enable Gemma 4 support:

```bash
python -m pip install -e ".[llm]"
```

### Configuration

Gemma 4 is **disabled by default**. Enable it via environment variables:

```bash
# Enable Gemma 4 analysis
export OPENCRUX_GEMMA_ENABLED=true

# Choose model variant (default: google/gemma-4-E2B-it)
# E2B: ~2B params, runs on CPU, <1.5GB RAM
# E4B: ~4B params, benefits from GPU, ~3GB RAM
export OPENCRUX_GEMMA_MODEL_VARIANT="google/gemma-4-E2B-it"

# Tuning parameters
export OPENCRUX_GEMMA_MAX_NEW_TOKENS=512
export OPENCRUX_GEMMA_TEMPERATURE=0.2
export OPENCRUX_GEMMA_SAMPLE_FRAMES_PER_ATTEMPT=3
```

### Hardware Recommendations

| Model | RAM | GPU | Best For |
|-------|-----|-----|----------|
| E2B (default) | ~1.5GB | CPU OK | Laptops, Raspberry Pi |
| E4B | ~3GB | Recommended | Desktop GPUs, Apple Silicon |

On Apple Silicon (M1/M2/M3), the model runs efficiently via PyTorch's MPS backend.

### What It Adds

When enabled, each climbing session gets an additional **"Gemma insights"** section in the UI showing:
- **Per-attempt analysis**: Movement descriptions, technique scores (footwork, body tension, route reading, efficiency), estimated difficulty grade, and coaching tips
- **Session summary**: Overall assessment and actionable recommendations
- **Confidence scores**: Model confidence for each analysis

The LLM analysis runs as a post-processing step after MediaPipe completes, so it never blocks the core pipeline.

## Scope Constraints

The current implementation is designed for fixed-camera or mostly stable-camera footage where a single climber is the dominant subject. Attempt segmentation is intentionally conservative and works best when attempts are separated by visible pauses or gaps.

## Commands

Install dependencies in your chosen Python environment:

```bash
python -m pip install -e .
```

Run the development server:

```bash
PYTHONPATH=src python -m uvicorn opencrux.main:app --reload --app-dir src
```

Run a local analysis from the command line:

```bash
PYTHONPATH=src python -m opencrux.cli path/to/clip.mp4 --route-name "White Heat" --gym-name "Home Wall"
```

On the first real analysis run, OpenCrux downloads the official MediaPipe pose task model into `data/models/` and reuses it on later runs.

Run a batch verification pass from a local manifest:

```bash
PYTHONPATH=src python -m opencrux.cli --manifest data/samples/manifest.json --output data/samples/results
```

Run tests:

```bash
PYTHONPATH=src pytest
```

Run the targeted web verification surface, including the browser smoke path:

```bash
./scripts/run_targeted_verification.sh
```

Prerequisites: `chromium`, `chromium-browser`, or `google-chrome`, plus `chromedriver`, must be available on `PATH` for the browser smoke portion.

GitHub Actions runs this same wrapper through `.github/workflows/targeted-verification.yml` after explicitly provisioning the browser binaries it expects on `PATH`.

## Project Shape

- `src/opencrux/main.py`: FastAPI app, upload API, and static UI wiring
- `src/opencrux/analysis.py`: MediaPipe/OpenCV analysis pipeline and heuristics
- `src/opencrux/cli.py`: Local verification entrypoint for real climbing clips
- `src/opencrux/store.py`: JSON-backed session persistence
- `docs/milestone-1.md`: Milestone scope, acceptance criteria, and risks
- `docs/manual-verification.md`: Repeatable workflow for validating real footage
- `data/samples/README.md`: Rules for staging user-owned or openly licensed clips
- `data/samples/manifest.template.json`: Template manifest for batch verification
- `.github/skills/`: Repo-local agent skills for discovery and verification

## Sample Footage

OpenCrux should only use clips you own or clips with a license that clearly permits reuse. Do not pull arbitrary climbing videos from the web into the repository.

Use [docs/manual-verification.md](docs/manual-verification.md) together with [data/samples/README.md](data/samples/README.md) to stage sample clips locally and record results against the milestone criteria.

## License

The repository license is intentionally not set yet. The earlier planning work left the code-license choice open between permissive and network-copyleft options. Resolve that before public publication.
