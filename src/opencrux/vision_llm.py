"""Gemma 4 vision-language model integration for climbing analysis.

This module provides a lazy-loading wrapper around Gemma 4 models
for post-analysis reasoning on climbing footage. It supports both
the edge-optimized E2B variant (CPU-friendly) and the E4B variant
(GPU-accelerated).

Usage:
    from opencrux.config import get_settings
    from opencrux.vision_llm import VisionLLM

    settings = get_settings()
    llm = VisionLLM(settings)

    # Analyze a single attempt with frame images
    insight = llm.analyze_attempt(
        attempt_index=1,
        frame_images=[frame1_bytes, frame2_bytes, frame3_bytes],
        metrics={"vertical_progress": 0.45, "lateral_span": 0.32},
    )
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .models import AttemptInsight, LLMInsights, TechniqueScore

logger = logging.getLogger(__name__)

# Prompt template for analyzing a single climbing attempt
ATTEMPT_ANALYSIS_PROMPT = """You are an expert climbing analyst. Analyze the provided climbing footage frames and metrics to produce a structured assessment.

## Context
- Attempt #{attempt_index}
- Vertical progress ratio: {vertical_progress:.2%}
- Lateral span ratio: {lateral_span:.2%}
- Attempt duration: {duration:.1f} seconds
- Hesitation markers: {hesitation_count}

## Task
Analyze the climber's movement in these frames and provide:
1. A concise movement description (2-3 sentences)
2. Technique scores (0-5) for: footwork, body_tension, route_reading, efficiency
3. 2-3 specific coaching tips
4. An estimated difficulty grade (e.g., V0-V10, 5.9-5.14)
5. Your confidence in this analysis (0.0-1.0)

## Output Format
Respond ONLY with valid JSON matching this exact schema:
{{
  "movement_description": "string",
  "technique_scores": {{
    "footwork": float,
    "body_tension": float,
    "route_reading": float,
    "efficiency": float
  }},
  "coaching_tips": ["string", "string", "string"],
  "difficulty_estimate": "string or null",
  "confidence": float
}}

Be specific and actionable. Focus on observable technique, not vague encouragement."""

SESSION_SUMMARY_PROMPT = """You are an expert climbing analyst. Based on the following session data, provide a brief overall summary and 2-3 key recommendations.

## Session Data
- Total attempts: {attempt_count}
- Total time on wall: {time_on_wall:.1f} seconds
- Average rest between attempts: {avg_rest:.1f} seconds
- Overall vertical progress: {vertical_progress:.2%}
- Overall lateral span: {lateral_span:.2%}
- Total hesitation markers: {hesitation_count}
- Mean pose visibility: {pose_visibility:.1%}

## Attempt Summaries
{attempt_summaries}

## Output Format
Respond ONLY with valid JSON:
{{
  "session_summary": "string (2-3 sentences)",
  "overall_recommendations": ["string", "string", "string"]
}}"""


@dataclass
class FrameSample:
    """A sampled frame with its context."""

    index: int
    timestamp_seconds: float
    image_path: Path | None = None
    image_bytes: bytes | None = None


class VisionLLM:
    """Gemma 4 vision-language model for climbing analysis.

    Lazily loads the model on first use to avoid startup overhead.
    Falls back gracefully if the model cannot be loaded.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._processor = None
        self._available = False
        self._load_error: str | None = None

    @property
    def is_available(self) -> bool:
        """Whether the LLM model is loaded and ready."""
        return self._available

    @property
    def load_error(self) -> str | None:
        """Error message if model failed to load, None otherwise."""
        return self._load_error

    def _ensure_loaded(self) -> bool:
        """Lazy-load the model. Returns True if successful."""
        if self._available:
            return True

        if self._load_error is not None:
            return False

        if not self.settings.gemma_enabled:
            self._load_error = "Gemma LLM is disabled (set OPENCRUX_GEMMA_ENABLED=true)"
            logger.info("Gemma LLM is disabled")
            return False

        try:
            self._load_model()
            self._available = True
            return True
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("Failed to load Gemma model: %s", exc)
            return False

    def _load_model(self) -> None:
        """Load the Gemma 4 model and processor."""
        try:
            import torch
            from transformers import AutoProcessor, Gemma3ForConditionalGeneration
        except ImportError:
            raise RuntimeError(
                "Gemma LLM requires the 'llm' extra. Install with: pip install -e '.[llm]'"
            )

        model_name = self.settings.gemma_model_variant
        logger.info("Loading Gemma model: %s", model_name)

        # Determine device
        if torch.cuda.is_available():
            device = "cuda"
            torch_dtype = torch.bfloat16
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            torch_dtype = torch.float16
        else:
            device = "cpu"
            torch_dtype = torch.float32

        self._processor = AutoProcessor.from_pretrained(model_name)
        self._model = Gemma3ForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map="auto" if device != "cpu" else None,
        )
        if device == "cpu":
            self._model = self._model.to(device)
        self._model.eval()

        logger.info("Gemma model loaded on %s", device)

    def _generate(self, messages: list[dict], max_new_tokens: int | None = None) -> str:
        """Generate text from the model using chat messages."""
        if self._model is None or self._processor is None:
            raise RuntimeError("Model not loaded")

        inputs = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )

        if hasattr(self._model, "device"):
            inputs = inputs.to(self._model.device)

        input_len = inputs["input_ids"].shape[-1]

        generation = self._model.generate(
            **inputs,
            max_new_tokens=max_new_tokens or self.settings.gemma_max_new_tokens,
            temperature=self.settings.gemma_temperature,
            do_sample=self.settings.gemma_temperature > 0,
        )
        generated = generation[0][input_len:]
        return self._processor.decode(generated, skip_special_tokens=True)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from model output, handling markdown code blocks."""
        text = text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return json.loads(text)

    def analyze_attempt(
        self,
        attempt_index: int,
        frame_images: Sequence[bytes | Path],
        metrics: dict[str, float],
    ) -> AttemptInsight | None:
        """Analyze a single climbing attempt using Gemma 4.

        Args:
            attempt_index: 1-based attempt index
            frame_images: List of frame images as bytes or file paths
            metrics: Dict with vertical_progress, lateral_span, duration, hesitation_count

        Returns:
            AttemptInsight or None if analysis failed
        """
        if not self._ensure_loaded():
            return None

        try:
            vertical_progress = metrics.get("vertical_progress", 0.0)
            lateral_span = metrics.get("lateral_span", 0.0)
            duration = metrics.get("duration", 0.0)
            hesitation_count = metrics.get("hesitation_count", 0)

            prompt = ATTEMPT_ANALYSIS_PROMPT.format(
                attempt_index=attempt_index,
                vertical_progress=vertical_progress,
                lateral_span=lateral_span,
                duration=duration,
                hesitation_count=hesitation_count,
            )

            # Build message content with images
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for img in frame_images[:5]:  # Limit to 5 frames per attempt
                if isinstance(img, Path):
                    content.append({"type": "image", "url": str(img)})
                elif isinstance(img, bytes):
                    content.append({"type": "image", "image_bytes": img})

            messages = [{"role": "user", "content": content}]
            response_text = self._generate(messages)
            result = self._extract_json(response_text)

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
                ),
                coaching_tips=result.get("coaching_tips", []),
                difficulty_estimate=result.get("difficulty_estimate"),
                confidence=result.get("confidence", 0.5),
            )
        except Exception as exc:
            logger.warning("Failed to analyze attempt %d: %s", attempt_index, exc)
            return None

    def generate_session_summary(
        self,
        attempt_summaries: list[dict[str, Any]],
        metrics: dict[str, float],
    ) -> tuple[str, list[str]] | None:
        """Generate an overall session summary using Gemma 4.

        Args:
            attempt_summaries: List of attempt summary dicts
            metrics: Session-level metrics dict

        Returns:
            Tuple of (summary_text, recommendations) or None if failed
        """
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

            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            response_text = self._generate(messages, max_new_tokens=256)
            result = self._extract_json(response_text)

            return (
                result.get("session_summary", ""),
                result.get("overall_recommendations", []),
            )
        except Exception as exc:
            logger.warning("Failed to generate session summary: %s", exc)
            return None

    def analyze_session(
        self,
        attempts_data: list[dict[str, Any]],
        frame_images_by_attempt: dict[int, list[bytes]],
        session_metrics: dict[str, float],
    ) -> LLMInsights | None:
        """Run full session analysis with per-attempt insights and summary.

        Args:
            attempts_data: List of attempt summary dicts from heuristics
            frame_images_by_attempt: Dict mapping attempt_index (1-based) to frame images
            session_metrics: Session-level metrics dict

        Returns:
            LLMInsights or None if analysis failed entirely
        """
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
            insight = self.analyze_attempt(idx, frames, metrics)
            if insight is not None:
                attempt_insights.append(insight)

        # Generate session summary
        summary_result = self.generate_session_summary(attempts_data, session_metrics)
        session_summary = ""
        recommendations: list[str] = []
        if summary_result is not None:
            session_summary, recommendations = summary_result

        return LLMInsights(
            model_variant=self.settings.gemma_model_variant,
            attempt_insights=attempt_insights,
            session_summary=session_summary,
            overall_recommendations=recommendations,
        )
