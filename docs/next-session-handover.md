# Next Session Handover

## Discovery

OpenCrux Milestone 2 has been implemented: Gemma 4 vision-language coaching insights via Ollama HTTP API with Gemini API fallback.

M1 is signed off. M2 rewired the LLM backend from HuggingFace in-process inference to Ollama's local HTTP API and added a Gemini API fallback for machines without GPU.

## Implementation

Completed M2 slices:

- rewrote `src/opencrux/vision_llm.py` from HuggingFace transformers to Ollama HTTP API (`/api/chat`, `/api/tags`)
- created `src/opencrux/gemini_llm.py` as a Gemini API fallback backend with the same interface
- updated `src/opencrux/config.py` with new settings: `llm_backend`, `ollama_base_url`, `ollama_model`, `gemini_api_key`, `gemini_model`, `llm_max_tokens`, `llm_temperature`, `llm_sample_frames_per_attempt`
- updated `src/opencrux/analysis.py`: deleted dead code (lines 586-603), added backend dispatch, updated setting references
- replaced `pyproject.toml` `[llm]` extra (transformers, torch, accelerate, Pillow) with `httpx>=0.27` and added `[api]` extra with `google-genai>=1.0`
- updated `tests/test_vision_llm.py` for Ollama HTTP mocking
- created `tests/test_gemini_llm.py` with disabled, mocked API, and error recovery test classes

Key files:

- [src/opencrux/vision_llm.py](../src/opencrux/vision_llm.py) — Ollama backend
- [src/opencrux/gemini_llm.py](../src/opencrux/gemini_llm.py) — Gemini API backend
- [src/opencrux/config.py](../src/opencrux/config.py) — LLM settings
- [src/opencrux/analysis.py](../src/opencrux/analysis.py) — backend dispatch in `_analyze_with_llm()`
- [tests/test_vision_llm.py](../tests/test_vision_llm.py) — 22 Ollama backend tests
- [tests/test_gemini_llm.py](../tests/test_gemini_llm.py) — 8 Gemini backend tests

## Verification

Test results:

- 30 LLM backend tests pass (22 Ollama + 8 Gemini)
- 57 of 58 total tests pass
- 1 pre-existing flaky browser smoke test (`test_browser_smoke_protected_lifecycle`) fails intermittently due to Selenium element click interception — unrelated to M2 changes

Not yet verified:

- end-to-end with real climbing footage and a running Ollama instance
- Gemini API integration with a real API key
- prompt quality and coaching output specificity

## Review

Primary checkpoint artifacts:

- [milestone-2.md](milestone-2.md)
- [milestone-2-gemma4-plan.md](milestone-2-gemma4-plan.md)
- [prd-status.md](prd-status.md)
- [milestone-operations.md](milestone-operations.md)

Residual risks:

- prompt templates have not been iterated against real model output — coaching tips may be generic
- the flaky `test_browser_smoke_protected_lifecycle` test should be investigated separately
- Ollama must be running externally; there is no in-app lifecycle management

## Next Step

First recommended action next session:

1. Start Ollama and verify `gemma4:e4b` is loaded: `ollama list`
2. Run the app with LLM enabled:
   ```bash
   OPENCRUX_GEMMA_ENABLED=true PYTHONPATH=src python -m uvicorn opencrux.main:app --app-dir src --port 8000
   ```
3. Upload a real climbing clip and verify `llm_insights` appears in the session JSON and renders in the UI
4. If coaching output is too generic, iterate on prompt templates in `vision_llm.py`

Alternative next steps:

- Fix the flaky browser smoke test
- Test Gemini fallback with a real API key: `OPENCRUX_LLM_BACKEND=gemini OPENCRUX_GEMINI_API_KEY=<key> OPENCRUX_GEMMA_ENABLED=true`
