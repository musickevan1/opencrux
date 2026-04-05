"""Gemini API backend for climbing analysis.

Provides the same interface as VisionLLM but uses Google's Gemini API
instead of a local Ollama instance. Intended as a fallback for machines
without local GPU inference.

Requires: pip install -e '.[api]'
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .config import Settings
from .models import AttemptInsight, LLMInsights, TechniqueScore
from .vision_llm import (
    ATTEMPT_ANALYSIS_PROMPT,
    ENHANCED_ATTEMPT_PROMPT,
    SESSION_SUMMARY_PROMPT,
    _format_biomechanics,
    extract_json,
)

logger = logging.getLogger(__name__)


class GeminiVisionLLM:
    """Gemini API backend for climbing analysis.

    Same interface as VisionLLM for seamless backend switching.
    """

    def __init__(self, settings: Settings, pose_store=None, session_id: str | None = None) -> None:
        self.settings = settings
        self._client = None
        self._available = False
        self._load_error: str | None = None
        self._pose_store = pose_store
        self._session_id = session_id

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _ensure_loaded(self) -> bool:
        if self._available:
            return True

        if self._load_error is not None:
            return False

        if not self.settings.gemma_enabled:
            self._load_error = "Gemma LLM is disabled (set OPENCRUX_GEMMA_ENABLED=true)"
            logger.info("Gemma LLM is disabled")
            return False

        if not self.settings.gemini_api_key:
            self._load_error = (
                "Gemini API key not set (set OPENCRUX_GEMINI_API_KEY)"
            )
            logger.warning("Gemini API key not configured")
            return False

        try:
            self._init_client()
            self._available = True
            return True
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("Failed to initialize Gemini client: %s", exc)
            return False

    def _init_client(self) -> None:
        from google import genai

        self._client = genai.Client(api_key=self.settings.gemini_api_key)

    def _generate(
        self, prompt: str, images: list[bytes] | None = None, max_tokens: int | None = None
    ) -> str:
        from google.genai import types

        contents: list[types.Part] = []
        for img_bytes in images or []:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
        contents.append(types.Part.from_text(text=prompt))

        response = self._client.models.generate_content(
            model=self.settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=self.settings.llm_temperature,
                max_output_tokens=max_tokens or max(self.settings.llm_max_tokens, 2048),
                response_mime_type="application/json",
            ),
        )
        return response.text

    def analyze_attempt(
        self,
        attempt_index: int,
        frame_images: Sequence[bytes | Path],
        metrics: dict[str, float],
        biomechanics: dict | None = None,
    ) -> AttemptInsight | None:
        if not self._ensure_loaded():
            return None

        try:
            vertical_progress = metrics.get("vertical_progress", 0.0)
            lateral_span = metrics.get("lateral_span", 0.0)
            duration = metrics.get("duration", 0.0)
            hesitation_count = metrics.get("hesitation_count", 0)

            if biomechanics is not None:
                prompt = ENHANCED_ATTEMPT_PROMPT.format(
                    attempt_index=attempt_index,
                    vertical_progress=vertical_progress,
                    lateral_span=lateral_span,
                    duration=duration,
                    hesitation_count=hesitation_count,
                    biomechanics_text=_format_biomechanics(biomechanics),
                )
            else:
                prompt = ATTEMPT_ANALYSIS_PROMPT.format(
                    attempt_index=attempt_index,
                    vertical_progress=vertical_progress,
                    lateral_span=lateral_span,
                    duration=duration,
                    hesitation_count=hesitation_count,
                )

            images: list[bytes] = []
            for img in frame_images[:5]:
                if isinstance(img, Path):
                    images.append(img.read_bytes())
                elif isinstance(img, bytes):
                    images.append(img)

            response_text = self._generate(prompt, images)

            if self._pose_store and self._session_id:
                self._pose_store.store_llm_output(
                    session_id=self._session_id,
                    model_variant=self.settings.gemini_model,
                    prompt_text=prompt,
                    response_text=response_text,
                    attempt_index=attempt_index,
                    output_type="attempt_analysis",
                )

            result = extract_json(response_text)

            return AttemptInsight(
                attempt_index=attempt_index,
                movement_description=result.get("movement_description", ""),
                technique_scores=TechniqueScore(
                    footwork=result.get("technique_scores", {}).get("footwork", 0.0),
                    body_tension=result.get("technique_scores", {}).get(
                        "body_tension", 0.0
                    ),
                    route_reading=result.get("technique_scores", {}).get(
                        "route_reading", 0.0
                    ),
                    efficiency=result.get("technique_scores", {}).get(
                        "efficiency", 0.0
                    ),
                    hip_positioning=result.get("technique_scores", {}).get(
                        "hip_positioning", 0.0
                    ),
                    grip_technique=result.get("technique_scores", {}).get(
                        "grip_technique", 0.0
                    ),
                ),
                coaching_tips=result.get("coaching_tips", []),
                technique_highlights=result.get("technique_highlights", []),
                frame_notes=result.get("frame_notes", []),
                difficulty_estimate=result.get("difficulty_estimate"),
                confidence=result.get("confidence", 0.5),
            )
        except Exception as exc:
            import sys
            print(f"GEMINI ERROR analyze_attempt {attempt_index}: {exc}\n{traceback.format_exc()}", file=sys.stderr, flush=True)
            return None

    def generate_session_summary(
        self,
        attempt_summaries: list[dict[str, Any]],
        metrics: dict[str, float],
    ) -> tuple[str, list[str]] | None:
        if not self._ensure_loaded():
            return None

        try:
            summaries_text = "\n".join(
                f"- Attempt {a.get('index', i + 1)}: "
                f"duration={a.get('duration_seconds', 0):.1f}s, "
                f"vertical={a.get('vertical_progress_ratio', 0):.2%}, "
                f"lateral={a.get('lateral_span_ratio', 0):.2%}, "
                f"hesitations={len(a.get('hesitation_markers', []))}"
                for i, a in enumerate(attempt_summaries)
            )

            prompt = SESSION_SUMMARY_PROMPT.format(
                attempt_count=metrics.get("attempt_count", 0),
                time_on_wall=metrics.get("estimated_time_on_wall_seconds", 0),
                avg_rest=metrics.get("average_rest_seconds", 0),
                vertical_progress=metrics.get("vertical_progress_ratio", 0),
                lateral_span=metrics.get("lateral_span_ratio", 0),
                hesitation_count=metrics.get("hesitation_marker_count", 0),
                pose_visibility=metrics.get("mean_pose_visibility", 0),
                attempt_summaries=summaries_text or "No attempt details available.",
            )

            response_text = self._generate(prompt, max_tokens=256)

            if self._pose_store and self._session_id:
                self._pose_store.store_llm_output(
                    session_id=self._session_id,
                    model_variant=self.settings.gemini_model,
                    prompt_text=prompt,
                    response_text=response_text,
                    output_type="session_summary",
                )

            result = extract_json(response_text)

            return (
                result.get("session_summary", ""),
                result.get("overall_recommendations", []),
            )
        except Exception as exc:
            import sys
            print(f"GEMINI ERROR session_summary: {exc}\n{traceback.format_exc()}", file=sys.stderr, flush=True)
            return None

    def analyze_session(
        self,
        attempts_data: list[dict[str, Any]],
        frame_images_by_attempt: dict[int, list[bytes]],
        session_metrics: dict[str, float],
    ) -> LLMInsights | None:
        if not self._ensure_loaded():
            return None

        attempt_insights: list[AttemptInsight] = []
        for attempt in attempts_data:
            idx = attempt.get("index", 0)
            frames = frame_images_by_attempt.get(idx, [])
            metrics = {
                "vertical_progress": attempt.get("vertical_progress_ratio", 0.0),
                "lateral_span": attempt.get("lateral_span_ratio", 0.0),
                "duration": attempt.get("duration_seconds", 0.0),
                "hesitation_count": len(attempt.get("hesitation_markers", [])),
            }
            biomechanics = attempt.get("biomechanics")
            insight = self.analyze_attempt(idx, frames, metrics, biomechanics=biomechanics)
            if insight is not None:
                attempt_insights.append(insight)

        summary_result = self.generate_session_summary(attempts_data, session_metrics)
        session_summary = ""
        recommendations: list[str] = []
        if summary_result is not None:
            session_summary, recommendations = summary_result

        return LLMInsights(
            model_variant=self.settings.gemini_model,
            attempt_insights=attempt_insights,
            session_summary=session_summary,
            overall_recommendations=recommendations,
        )
