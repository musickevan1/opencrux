# Milestone 2 — Gemma 4 Vision-Language Coaching Insights

## Objective

Wire up working Gemma 4 vision-language coaching insights end-to-end: rewrite the LLM backend to use Ollama's local API (and Gemini API as fallback), deliver per-attempt technique scoring, coaching tips, difficulty estimates, and session-level summaries through the existing UI.

## Decisions

- M1 stays signed off. This is the first M2 slice.
- Primary backend: Ollama local API (`http://localhost:11434/api/chat`) with Gemma 4 models already downloaded.
- Fallback backend: Gemini API for machines without Ollama or GPU.
- Backend selector: `OPENCRUX_LLM_BACKEND=ollama|gemini` (default: `ollama`).
- Default Ollama model: `gemma4:e4b` (9.6 GB, 4B params — best local quality/cost tradeoff).
- No fine-tuning. Prompt engineering only.
- No UI changes needed — the LLM insights section in `app.js` and `app.css` is already fully built.

## Hardware Context

- GPU: NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM.
- Ollama v0.20.0 installed with models: `gemma4:e2b` (7.2 GB), `gemma4:e4b` (9.6 GB), `gemma4:26b` (17 GB), `gemma4:31b` (19 GB).
- Models are downloaded but need sufficient free VRAM to load. The E4B fits in 16 GB VRAM when nothing else is consuming it.

## Current State

What already works end-to-end:
- Video upload → MediaPipe pose extraction → heuristic metrics → session persistence → UI rendering.
- Frame sampling per attempt already implemented in `VisionAnalyzer._sample_attempt_frames()` — extracts JPEG bytes at evenly spaced timestamps.
- `_analyze_with_llm()` in `analysis.py` already calls `VisionLLM.analyze_session()` and feeds the result into `SessionAnalysis.llm_insights`.
- UI in `app.js` `renderLLMInsights()` already renders technique scores, coaching tips, movement descriptions, difficulty estimates, session summary, and recommendations. CSS classes are styled.
- Prompt templates `ATTEMPT_ANALYSIS_PROMPT` and `SESSION_SUMMARY_PROMPT` in `vision_llm.py` are well-structured and ready to use.

What is broken / needs rewriting:
- `VisionLLM._load_model()` imports `Gemma3ForConditionalGeneration` from HuggingFace transformers — wrong class, wrong backend entirely.
- `VisionLLM._generate()` calls `self._processor.apply_chat_template()` and `self._model.generate()` — HuggingFace in-process inference that should be replaced with Ollama HTTP calls.
- Image passing uses `{"type": "image", "image_bytes": img}` dict format — needs to be base64-encoded strings for Ollama's API.
- `pyproject.toml` `[llm]` extra depends on `transformers`, `torch`, `accelerate` — replace with lightweight HTTP dependency.
- `analysis.py` has unreachable dead code after `return frames_by_attempt` (lines 586–602) — leftover merge artifact, delete it.

---

## Implementation Checklist

### Phase 1: Rewrite VisionLLM for Ollama Backend

#### Task 1.1 — Rewrite `src/opencrux/vision_llm.py`

Replace the entire HuggingFace loading/inference path with Ollama HTTP API calls.

**Current state of `VisionLLM` (what to replace):**
- `_load_model()` (lines 150–185): imports torch + transformers, loads model weights into GPU. **Delete entirely.**
- `_generate()` (lines 187–215): calls `processor.apply_chat_template()` and `model.generate()`. **Replace with HTTP POST to `http://localhost:11434/api/chat`.**
- `_ensure_loaded()` (lines 130–148): lazy loads model. **Replace with Ollama health check** (GET `http://localhost:11434/api/tags` to verify model exists).
- Image handling in `analyze_attempt()` (lines 260–268): builds `{"type": "image", "image_bytes": img}` dicts. **Replace with base64-encoding JPEG bytes into the `images` field** of the Ollama message.

**Ollama `/api/chat` request format (non-streaming):**
```json
{
  "model": "gemma4:e4b",
  "messages": [
    {
      "role": "user",
      "content": "Analyze this climbing footage...",
      "images": ["<base64-encoded-jpeg>", "<base64-encoded-jpeg>"]
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.2,
    "num_predict": 512
  }
}
```

**Ollama `/api/chat` response format:**
```json
{
  "model": "gemma4:e4b",
  "message": {
    "role": "assistant",
    "content": "{ ... JSON response ... }"
  },
  "done": true
}
```

**Key implementation details:**
- Use `urllib.request` (stdlib) for HTTP calls — no new dependency needed. Or use `httpx` which is already a dev dependency.
- Base64-encode JPEG bytes: `import base64; base64.b64encode(jpeg_bytes).decode("ascii")`.
- Set `"stream": false` so we get the full response in one JSON blob.
- Map `settings.gemma_max_new_tokens` → Ollama's `"num_predict"` option.
- Map `settings.gemma_temperature` → Ollama's `"temperature"` option.
- Replace `self._model` / `self._processor` instance vars with `self._ollama_base_url: str` and `self._model_tag: str`.
- `_ensure_loaded()` should do a GET to `http://localhost:11434/api/tags`, parse the JSON response, and confirm the configured model tag appears in the list. Set `_available = True` if found.
- `_generate()` should POST to `{base_url}/api/chat` with the message payload and return `response["message"]["content"]`.
- Keep `_extract_json()` unchanged — it already handles markdown code blocks.
- Keep `analyze_attempt()`, `generate_session_summary()`, `analyze_session()` method signatures unchanged — only change the internal image formatting and call to `_generate()`.

**What to keep unchanged in `vision_llm.py`:**
- `ATTEMPT_ANALYSIS_PROMPT` and `SESSION_SUMMARY_PROMPT` templates (lines 38–95).
- `FrameSample` dataclass (lines 97–102).
- `_extract_json()` method.
- `analyze_attempt()` method signature and JSON parsing logic (just change image encoding).
- `generate_session_summary()` method (text-only, no image changes needed).
- `analyze_session()` method (orchestration, delegates to above methods).

#### Task 1.2 — Update `src/opencrux/config.py`

Replace HuggingFace-oriented settings with Ollama + backend settings.

**Replace these settings (lines 53–58):**
```python
# Gemma 4 LLM settings
gemma_enabled: bool = False
gemma_model_variant: str = "google/gemma-4-E2B-it"
gemma_max_new_tokens: int = 512
gemma_temperature: float = 0.2
gemma_sample_frames_per_attempt: int = 3
```

**With:**
```python
# LLM coaching settings
gemma_enabled: bool = False
llm_backend: str = "ollama"  # "ollama" or "gemini"
ollama_base_url: str = "http://localhost:11434"
ollama_model: str = "gemma4:e4b"
gemini_api_key: str = ""
gemini_model: str = "gemini-2.5-flash"
llm_max_tokens: int = 512
llm_temperature: float = 0.2
llm_sample_frames_per_attempt: int = 3
```

All exposed as `OPENCRUX_*` env vars via the existing `env_prefix="OPENCRUX_"`.

**Update all references** in `analysis.py` and `vision_llm.py` that use the old `settings.gemma_*` names (e.g., `settings.gemma_model_variant` → `settings.ollama_model`, `settings.gemma_max_new_tokens` → `settings.llm_max_tokens`, `settings.gemma_sample_frames_per_attempt` → `settings.llm_sample_frames_per_attempt`).

#### Task 1.3 — Update `pyproject.toml` dependencies

**Replace the `[llm]` extra (lines 28–32):**
```toml
llm = [
  "transformers>=4.49",
  "torch>=2.0",
  "accelerate",
  "Pillow",
]
```

**With:**
```toml
llm = [
  "httpx>=0.27",
]
api = [
  "google-genai>=1.0",
]
```

Note: `httpx` is already in `[dev]` deps. We add it to `[llm]` so production installs without dev deps still have it. Alternatively, use `urllib.request` (stdlib) for the Ollama calls and drop the `[llm]` extra entirely. Implementer's choice — but `httpx` is cleaner for timeout handling and async potential.

#### Task 1.4 — Delete dead code in `src/opencrux/analysis.py`

**Delete lines 586–602** — unreachable code after `return frames_by_attempt` in `_sample_attempt_frames()`:
```python
        return frames_by_attempt
        if failure_message is not None:           # ← unreachable, delete from here
            raise AnalysisError(failure_message)

        return SessionAnalysis(
            id=session_id or uuid4().hex,
            status=SessionStatus.COMPLETED,
            original_filename=original_filename,
            stored_video_path=str(video_path),
            route_name=route_name,
            gym_name=gym_name,
            processed_frame_count=sampled_frames,
            sampled_fps=sampled_fps,
            source_duration_seconds=source_duration_seconds
            or round(observations[-1].timestamp_seconds, 2),
            warnings=warnings,
            attempts=attempt_summaries,
            metrics=metrics,
        )                                         # ← delete through here
```

#### Task 1.5 — Update `analysis.py` `_analyze_with_llm()` for backend dispatch

**Current code (lines 468–472):**
```python
try:
    from .vision_llm import VisionLLM
except ImportError:
    logger.warning(
        "Gemma LLM module not available. Install with: pip install -e '.[llm]'"
    )
    return None

llm = VisionLLM(self.settings)
```

**Replace with backend dispatch:**
```python
if self.settings.llm_backend == "gemini":
    try:
        from .gemini_llm import GeminiVisionLLM
    except ImportError:
        logger.warning("Gemini LLM backend not available. Install with: pip install -e '.[api]'")
        return None
    llm = GeminiVisionLLM(self.settings)
else:
    from .vision_llm import VisionLLM
    llm = VisionLLM(self.settings)
```

Also update the `LLMInsights.model_variant` to reflect the actual model used — for Ollama this should be `settings.ollama_model` (e.g., `"gemma4:e4b"`), for Gemini it should be `settings.gemini_model`.

#### Task 1.6 — Update `analysis.py` setting references

All references to old `settings.gemma_*` names need updating:
- `settings.gemma_enabled` → stays as-is (keep the `gemma_enabled` name or rename to `llm_enabled` — implementer's choice, but keep backward compat with `OPENCRUX_GEMMA_ENABLED` env var)
- `settings.gemma_sample_frames_per_attempt` → `settings.llm_sample_frames_per_attempt`

Search for `gemma_` in `analysis.py` and update all references.

---

### Phase 2: Add Gemini API Backend

#### Task 2.1 — Create `src/opencrux/gemini_llm.py`

New file implementing the same interface as the rewritten `VisionLLM`.

**Required methods** (same signatures as `VisionLLM`):
- `__init__(self, settings: Settings)` — store settings, set `_available = False`.
- `is_available: bool` property.
- `load_error: str | None` property.
- `_ensure_loaded() -> bool` — verify API key is set and Gemini API is reachable.
- `analyze_attempt(attempt_index, frame_images, metrics) -> AttemptInsight | None`
- `generate_session_summary(attempt_summaries, metrics) -> tuple[str, list[str]] | None`
- `analyze_session(attempts_data, frame_images_by_attempt, session_metrics) -> LLMInsights | None`

**Gemini API specifics:**
- Use `google.genai` SDK (from `google-genai` package).
- Image format: pass JPEG bytes as `Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")` or use inline data.
- Reuse the same prompt templates (`ATTEMPT_ANALYSIS_PROMPT`, `SESSION_SUMMARY_PROMPT`) — import from `vision_llm.py`.
- Parse JSON from response text using the same `_extract_json()` logic — either import it or duplicate the small helper.
- Set `generation_config` with `temperature` and `max_output_tokens` from settings.
- Model name from `settings.gemini_model` (default `"gemini-2.5-flash"`).
- API key from `settings.gemini_api_key`.

**Fallback behavior:** If `gemini_api_key` is empty, `_ensure_loaded()` returns `False` with a clear error message.

---

### Phase 3: Tests

#### Task 3.1 — Update `tests/test_vision_llm.py`

**Changes needed:**

1. **`TestVisionLLMDisabled`** — should still pass. The `gemma_enabled=False` check hasn't changed.

2. **`TestVisionLLMLazyLoading`** — update:
   - `test_ensure_loaded_returns_false_without_model`: currently expects failure because transformers/torch aren't installed. Now it should fail because Ollama isn't reachable (or the model tag isn't found). The assertion `result is False` and `llm.load_error is not None` should still hold. Just ensure the test doesn't accidentally connect to a running Ollama instance — mock the HTTP call or set `ollama_base_url` to a non-existent host.

3. **`TestVisionLLMWithMockedModel`** — major update:
   - The `mock_llm` fixture currently sets `llm._model = MagicMock()` and `llm._processor = MagicMock()`. These attributes no longer exist.
   - Replace with mocking the HTTP call (mock `urllib.request.urlopen` or `httpx.post` or whatever the implementer chose).
   - The `test_analyze_attempt_success` test patches `_generate` — that should still work if `_generate()` still exists as the internal method.
   - All other tests that `patch.object(mock_llm, "_generate", ...)` should transfer directly.

4. **Add new test:**
   ```python
   def test_default_model_is_ollama_gemma4():
       settings = Settings()
       assert settings.ollama_model == "gemma4:e4b"
       assert settings.llm_backend == "ollama"
   ```

5. **JSON extraction tests** — no changes needed, `_extract_json()` is unchanged.

6. **`TestTechniqueScore` and `TestAttemptInsight`** — no changes needed, these test models not the LLM.

#### Task 3.2 — Add Gemini backend tests (`tests/test_gemini_llm.py` or extend `test_vision_llm.py`)

Mirror the mock pattern:
- `TestGeminiDisabled` — returns `None` when `gemini_api_key` is empty.
- `TestGeminiWithMockedAPI` — mock the `google.genai` client, verify `analyze_attempt()`, `generate_session_summary()`, `analyze_session()` produce correct outputs from mocked responses.
- `TestGeminiErrorRecovery` — API errors return `None`, don't crash.

#### Task 3.3 — Verify existing tests still pass

Run:
```bash
pytest tests/test_vision_llm.py tests/test_analysis.py tests/test_app.py -v
```

All M1 tests must remain green. The dead code deletion and setting renames must not break anything.

#### Task 3.4 — Run full targeted verification

```bash
./scripts/run_targeted_verification.sh
```

This must still pass — we haven't changed the core analysis pipeline, only the optional LLM post-processing layer.

---

### Phase 4: Documentation

#### Task 4.1 — Create `docs/milestone-2.md`

Follow the same structure as `docs/milestone-1.md`.

```markdown
# Milestone 2

## Objective

Add vision-language coaching insights to the analysis pipeline using Gemma 4 models via Ollama, with a Gemini API fallback for machines without local GPU inference.

## In Scope

- Ollama-backed Gemma 4 local inference (default)
- Gemini API fallback backend
- Per-attempt technique scoring (footwork, body tension, route reading, efficiency)
- Per-attempt coaching tips and difficulty estimates
- Session-level summary and recommendations
- Graceful degradation when LLM is unavailable

## Acceptance Criteria

- A supported video upload with `OPENCRUX_GEMMA_ENABLED=true` returns a completed analysis with `llm_insights` populated.
- The UI renders technique scores, coaching tips, movement descriptions, difficulty estimates, session summary, and recommendations in the "Gemma insights" section.
- When Ollama is not running or the model is unavailable, the pipeline completes normally without LLM insights and the UI section stays hidden.
- The Gemini API backend produces equivalent results when `OPENCRUX_LLM_BACKEND=gemini` and a valid API key is set.
- All M1 tests remain green.
- New tests cover Ollama and Gemini backend mock paths.

## Known Risks

- LLM inference time depends on model size and available VRAM. The E4B model on a 16 GB GPU should complete per-attempt analysis in 5–15 seconds.
- Technique scores from a general-purpose model are approximate. No fine-tuning has been done.
- Coaching tips are only as good as the model's climbing domain knowledge from pretraining.
- Ollama must be running as a separate service. The app does not start or manage Ollama.
```

#### Task 4.2 — Update `docs/prd-status.md`

- Add Milestone 2 references under "Current Phase".
- Update "What Is Not Done" to include M2 scope.
- Update "Recommended Next Product Slice" to reference M2.

#### Task 4.3 — Update `docs/milestone-operations.md`

Add Milestone 2 to the "Milestone Registry" section:
```markdown
### Milestone 2

Goal:

- add vision-language coaching insights to the analysis pipeline using Gemma 4 via Ollama with Gemini API fallback

Status:

- in progress
```

#### Task 4.4 — Update `docs/next-session-handover.md`

After implementation is complete, rewrite the handover to reflect M2 state, completed slices, and next steps.

---

## Verification Matrix

| Check | Command | Expected |
|---|---|---|
| Unit tests pass | `pytest tests/ -v` | All green |
| M1 targeted verification | `./scripts/run_targeted_verification.sh` | 15 tests pass |
| Ollama text-only | `OPENCRUX_GEMMA_ENABLED=true` + upload clip (Ollama running, no image) | `llm_insights` populated with session summary |
| Ollama with images | Same as above with E4B loaded | Per-attempt scores + tips rendered in UI |
| Gemini fallback | `OPENCRUX_LLM_BACKEND=gemini OPENCRUX_GEMINI_API_KEY=<key>` | Same insights via Gemini |
| Graceful degradation | `OPENCRUX_GEMMA_ENABLED=true` but Ollama not running | Pipeline completes, no insights, no error |
| Disabled path | `OPENCRUX_GEMMA_ENABLED=false` (default) | No LLM calls, section hidden |

## Scope Boundaries

**In scope:** Ollama Gemma 4 local inference, Gemini API fallback, config plumbing, dead code cleanup, M2 docs, tests.

**Out of scope:** Fine-tuning, custom model training, prompt iteration beyond existing templates, UI changes to insights section, expanding supported footage conditions, multi-climber analysis, starting/managing Ollama from within the app.

## Files Changed

| File | Nature of change |
|---|---|
| `src/opencrux/vision_llm.py` | Rewrite: HuggingFace → Ollama HTTP API |
| `src/opencrux/gemini_llm.py` | New file: Gemini API backend |
| `src/opencrux/config.py` | Update: replace `gemma_model_variant` etc. with `ollama_*` / `gemini_*` / `llm_*` settings |
| `src/opencrux/analysis.py` | Fix: delete dead code, add backend dispatch, update setting references |
| `pyproject.toml` | Update: replace torch/transformers with httpx in `[llm]`, add `[api]` extra |
| `tests/test_vision_llm.py` | Update: mock HTTP instead of model objects, add Gemma 4 default test |
| `tests/test_gemini_llm.py` | New file: Gemini backend mock tests |
| `docs/milestone-2.md` | New file: M2 scope and acceptance criteria |
| `docs/milestone-2-gemma4-plan.md` | This file (planning artifact) |
| `docs/prd-status.md` | Update: reference M2 |
| `docs/milestone-operations.md` | Update: add M2 to registry |
| `docs/next-session-handover.md` | Update: after completion |

No changes to:
- `src/opencrux/templates/index.html` — UI structure already has the LLM section
- `src/opencrux/static/app.js` — `renderLLMInsights()` already renders all fields
- `src/opencrux/static/app.css` — `.llm-*` styles already exist
- `src/opencrux/heuristics.py` — no heuristic changes
- `src/opencrux/models.py` — `LLMInsights`, `AttemptInsight`, `TechniqueScore` already defined
