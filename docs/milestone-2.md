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

- LLM inference time depends on model size and available VRAM. The E4B model on a 16 GB GPU should complete per-attempt analysis in 5-15 seconds.
- Technique scores from a general-purpose model are approximate. No fine-tuning has been done.
- Coaching tips are only as good as the model's climbing domain knowledge from pretraining.
- Ollama must be running as a separate service. The app does not start or manage Ollama.
