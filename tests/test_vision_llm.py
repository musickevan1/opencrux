"""Tests for the Gemma 4 vision LLM integration module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencrux.config import Settings
from opencrux.models import AttemptInsight, LLMInsights, TechniqueScore


class TestVisionLLMDisabled:
    """Tests for behavior when Gemma LLM is disabled."""

    def test_not_available_when_disabled(self):
        settings = Settings(gemma_enabled=False)
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        assert llm.is_available is False
        # load_error is set lazily when _ensure_loaded is called
        llm._ensure_loaded()
        assert llm.load_error is not None
        assert "disabled" in llm.load_error.lower()

    def test_analyze_attempt_returns_none_when_disabled(self):
        settings = Settings(gemma_enabled=False)
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        result = llm.analyze_attempt(1, [], {"vertical_progress": 0.5})
        assert result is None

    def test_generate_session_summary_returns_none_when_disabled(self):
        settings = Settings(gemma_enabled=False)
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        result = llm.generate_session_summary([], {})
        assert result is None

    def test_analyze_session_returns_none_when_disabled(self):
        settings = Settings(gemma_enabled=False)
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        result = llm.analyze_session([], {}, {})
        assert result is None


class TestVisionLLMLazyLoading:
    """Tests for lazy model loading behavior."""

    def test_ensure_loaded_returns_false_without_model(self):
        settings = Settings(
            gemma_enabled=True, gemma_model_variant="google/gemma-4-E2B-it"
        )
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        # Without transformers/torch installed, should return False gracefully
        result = llm._ensure_loaded()
        assert result is False
        assert llm.load_error is not None

    def test_is_available_false_initially(self):
        settings = Settings(gemma_enabled=True)
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        assert llm.is_available is False


class TestVisionLLMWithMockedModel:
    """Tests for LLM analysis with mocked model responses."""

    @pytest.fixture
    def mock_llm(self):
        """Create a VisionLLM instance with mocked model."""
        settings = Settings(
            gemma_enabled=True, gemma_model_variant="google/gemma-4-E2B-it"
        )
        from opencrux.vision_llm import VisionLLM

        llm = VisionLLM(settings)
        llm._available = True
        llm._model = MagicMock()
        llm._processor = MagicMock()
        return llm

    def test_extract_json_plain(self, mock_llm):
        text = '{"movement_description": "Good footwork", "confidence": 0.85}'
        result = mock_llm._extract_json(text)
        assert result["movement_description"] == "Good footwork"
        assert result["confidence"] == 0.85

    def test_extract_json_markdown_block(self, mock_llm):
        text = '```json\n{"movement_description": "Good footwork", "confidence": 0.85}\n```'
        result = mock_llm._extract_json(text)
        assert result["movement_description"] == "Good footwork"
        assert result["confidence"] == 0.85

    def test_extract_json_code_block_no_lang(self, mock_llm):
        text = '```\n{"movement_description": "Good footwork", "confidence": 0.85}\n```'
        result = mock_llm._extract_json(text)
        assert result["movement_description"] == "Good footwork"

    def test_analyze_attempt_success(self, mock_llm):
        mock_response = json.dumps(
            {
                "movement_description": "Strong body tension with precise foot placements.",
                "technique_scores": {
                    "footwork": 4.2,
                    "body_tension": 3.8,
                    "route_reading": 4.0,
                    "efficiency": 3.5,
                },
                "coaching_tips": [
                    "Focus on silent feet for better precision.",
                    "Engage core earlier on the crux sequence.",
                ],
                "difficulty_estimate": "V4",
                "confidence": 0.82,
            }
        )

        mock_llm._processor.apply_chat_template.return_value = {
            "input_ids": MagicMock(shape=[1, 50])
        }
        mock_llm._processor.decode.return_value = mock_response
        mock_llm._model.generate.return_value = MagicMock()
        mock_llm._model.generate.return_value.__getitem__ = lambda self, idx: (
            MagicMock()
        )
        mock_llm._model.device = "cpu"

        with patch.object(mock_llm, "_generate", return_value=mock_response):
            result = mock_llm.analyze_attempt(
                attempt_index=1,
                frame_images=[b"fake_image_bytes"],
                metrics={
                    "vertical_progress": 0.45,
                    "lateral_span": 0.32,
                    "duration": 12.5,
                    "hesitation_count": 2,
                },
            )

        assert result is not None
        assert result.attempt_index == 1
        assert "Strong body tension" in result.movement_description
        assert result.technique_scores is not None
        assert result.technique_scores.footwork == 4.2
        assert result.technique_scores.body_tension == 3.8
        assert len(result.coaching_tips) == 2
        assert result.difficulty_estimate == "V4"
        assert result.confidence == 0.82

    def test_analyze_attempt_returns_none_on_error(self, mock_llm):
        with patch.object(
            mock_llm, "_generate", side_effect=RuntimeError("Model error")
        ):
            result = mock_llm.analyze_attempt(1, [b"fake"], {"vertical_progress": 0.5})
        assert result is None

    def test_generate_session_summary_success(self, mock_llm):
        mock_response = json.dumps(
            {
                "session_summary": "Solid session with consistent technique across attempts.",
                "overall_recommendations": [
                    "Work on dynamic moves to improve efficiency.",
                    "Practice rest positions to reduce pump.",
                ],
            }
        )

        with patch.object(mock_llm, "_generate", return_value=mock_response):
            result = mock_llm.generate_session_summary(
                attempt_summaries=[
                    {
                        "index": 1,
                        "duration_seconds": 15.0,
                        "vertical_progress_ratio": 0.45,
                        "lateral_span_ratio": 0.32,
                        "hesitation_markers": [],
                    }
                ],
                metrics={
                    "attempt_count": 1,
                    "estimated_time_on_wall_seconds": 15.0,
                    "average_rest_seconds": 30.0,
                    "vertical_progress_ratio": 0.45,
                    "lateral_span_ratio": 0.32,
                    "hesitation_marker_count": 0,
                    "mean_pose_visibility": 0.85,
                },
            )

        assert result is not None
        summary, recommendations = result
        assert "Solid session" in summary
        assert len(recommendations) == 2

    def test_generate_session_summary_returns_none_on_error(self, mock_llm):
        with patch.object(
            mock_llm, "_generate", side_effect=RuntimeError("Model error")
        ):
            result = mock_llm.generate_session_summary([], {})
        assert result is None

    def test_analyze_session_aggregates_results(self, mock_llm):
        attempt_response = json.dumps(
            {
                "movement_description": "Clean movement with good flow.",
                "technique_scores": {
                    "footwork": 4.0,
                    "body_tension": 3.5,
                    "route_reading": 4.2,
                    "efficiency": 3.8,
                },
                "coaching_tips": ["Keep hips closer to the wall."],
                "difficulty_estimate": "V3",
                "confidence": 0.78,
            }
        )
        summary_response = json.dumps(
            {
                "session_summary": "Good session overall.",
                "overall_recommendations": ["Practice more dynamic moves."],
            }
        )

        responses = [attempt_response, summary_response]
        response_idx = 0

        def mock_generate(messages, max_new_tokens=None):
            nonlocal response_idx
            result = responses[response_idx % len(responses)]
            response_idx += 1
            return result

        with patch.object(mock_llm, "_generate", side_effect=mock_generate):
            result = mock_llm.analyze_session(
                attempts_data=[
                    {
                        "index": 1,
                        "duration_seconds": 10.0,
                        "vertical_progress_ratio": 0.4,
                        "lateral_span_ratio": 0.3,
                        "hesitation_markers": [],
                    }
                ],
                frame_images_by_attempt={1: [b"frame1", b"frame2"]},
                session_metrics={
                    "attempt_count": 1,
                    "estimated_time_on_wall_seconds": 10.0,
                    "average_rest_seconds": 20.0,
                    "vertical_progress_ratio": 0.4,
                    "lateral_span_ratio": 0.3,
                    "hesitation_marker_count": 0,
                    "mean_pose_visibility": 0.8,
                },
            )

        assert result is not None
        assert isinstance(result, LLMInsights)
        assert len(result.attempt_insights) == 1
        assert result.attempt_insights[0].attempt_index == 1
        assert result.session_summary == "Good session overall."
        assert len(result.overall_recommendations) == 1


class TestTechniqueScore:
    """Tests for the TechniqueScore model."""

    def test_overall_calculation(self):
        score = TechniqueScore(
            footwork=4.0, body_tension=3.0, route_reading=5.0, efficiency=3.0
        )
        assert score.overall == 3.8

    def test_overall_rounds_to_one_decimal(self):
        score = TechniqueScore(
            footwork=3.33, body_tension=3.33, route_reading=3.33, efficiency=3.33
        )
        assert score.overall == 3.3


class TestAttemptInsight:
    """Tests for the AttemptInsight model."""

    def test_defaults(self):
        insight = AttemptInsight(attempt_index=1)
        assert insight.movement_description == ""
        assert insight.technique_scores is None
        assert insight.coaching_tips == []
        assert insight.difficulty_estimate is None
        assert insight.confidence == 0.5

    def test_with_scores(self):
        insight = AttemptInsight(
            attempt_index=1,
            movement_description="Good flow",
            technique_scores=TechniqueScore(
                footwork=4.0, body_tension=3.5, route_reading=4.0, efficiency=3.0
            ),
            coaching_tips=["Tip 1", "Tip 2"],
            difficulty_estimate="V4",
            confidence=0.85,
        )
        assert insight.technique_scores.overall == 3.6
        assert len(insight.coaching_tips) == 2


class TestLLMInsights:
    """Tests for the LLMInsights model."""

    def test_defaults(self):
        insights = LLMInsights(model_variant="google/gemma-4-E2B-it")
        assert insights.attempt_insights == []
        assert insights.session_summary == ""
        assert insights.overall_recommendations == []

    def test_with_data(self):
        insights = LLMInsights(
            model_variant="google/gemma-4-E4B-it",
            attempt_insights=[
                AttemptInsight(
                    attempt_index=1,
                    movement_description="Clean beta",
                    technique_scores=TechniqueScore(
                        footwork=4.0,
                        body_tension=4.0,
                        route_reading=4.0,
                        efficiency=4.0,
                    ),
                    coaching_tips=["Great job"],
                    confidence=0.9,
                )
            ],
            session_summary="Excellent session.",
            overall_recommendations=["Keep it up"],
        )
        assert len(insights.attempt_insights) == 1
        assert insights.session_summary == "Excellent session."
        assert len(insights.overall_recommendations) == 1
