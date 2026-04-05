"""Tests for the Gemini API backend for climbing analysis."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from opencrux.config import Settings
from opencrux.models import AttemptInsight, LLMInsights


class TestGeminiDisabled:
    """Tests for behavior when Gemini backend is disabled or unconfigured."""

    def test_returns_none_when_llm_disabled(self):
        settings = Settings(gemma_enabled=False, llm_backend="gemini")
        from opencrux.gemini_llm import GeminiVisionLLM

        llm = GeminiVisionLLM(settings)
        assert llm.analyze_attempt(1, [], {"vertical_progress": 0.5}) is None
        assert "disabled" in llm.load_error.lower()

    def test_returns_none_when_api_key_empty(self):
        settings = Settings(
            gemma_enabled=True, llm_backend="gemini", gemini_api_key=""
        )
        from opencrux.gemini_llm import GeminiVisionLLM

        llm = GeminiVisionLLM(settings)
        result = llm.analyze_session([], {}, {})
        assert result is None
        assert "api key" in llm.load_error.lower()


class TestGeminiWithMockedAPI:
    """Tests for Gemini analysis with mocked _generate method."""

    @pytest.fixture
    def mock_llm(self):
        settings = Settings(
            gemma_enabled=True,
            llm_backend="gemini",
            gemini_api_key="test-key-123",
            gemini_model="gemini-2.5-flash",
        )
        from opencrux.gemini_llm import GeminiVisionLLM

        llm = GeminiVisionLLM(settings)
        llm._available = True
        llm._client = MagicMock()
        return llm

    def test_analyze_attempt_success(self, mock_llm):
        mock_response = json.dumps(
            {
                "movement_description": "Dynamic movement with good hip rotation.",
                "technique_scores": {
                    "footwork": 3.8,
                    "body_tension": 4.0,
                    "route_reading": 3.5,
                    "efficiency": 3.2,
                },
                "coaching_tips": [
                    "Flag more on overhangs.",
                    "Read sequences before starting.",
                ],
                "difficulty_estimate": "V3",
                "confidence": 0.75,
            }
        )

        with patch.object(mock_llm, "_generate", return_value=mock_response):
            result = mock_llm.analyze_attempt(
                attempt_index=1,
                frame_images=[b"fake_jpeg"],
                metrics={
                    "vertical_progress": 0.4,
                    "lateral_span": 0.3,
                    "duration": 10.0,
                    "hesitation_count": 1,
                },
            )

        assert result is not None
        assert isinstance(result, AttemptInsight)
        assert result.attempt_index == 1
        assert "Dynamic movement" in result.movement_description
        assert result.technique_scores.footwork == 3.8
        assert result.difficulty_estimate == "V3"

    def test_generate_session_summary_success(self, mock_llm):
        mock_response = json.dumps(
            {
                "session_summary": "Good session with improving technique.",
                "overall_recommendations": ["Work on footwork precision."],
            }
        )

        with patch.object(mock_llm, "_generate", return_value=mock_response):
            result = mock_llm.generate_session_summary(
                attempt_summaries=[
                    {
                        "index": 1,
                        "duration_seconds": 12.0,
                        "vertical_progress_ratio": 0.5,
                        "lateral_span_ratio": 0.3,
                        "hesitation_markers": [],
                    }
                ],
                metrics={
                    "attempt_count": 1,
                    "estimated_time_on_wall_seconds": 12.0,
                    "average_rest_seconds": 25.0,
                    "vertical_progress_ratio": 0.5,
                    "lateral_span_ratio": 0.3,
                    "hesitation_marker_count": 0,
                    "mean_pose_visibility": 0.9,
                },
            )

        assert result is not None
        summary, recs = result
        assert "Good session" in summary
        assert len(recs) == 1

    def test_analyze_session_aggregates_results(self, mock_llm):
        attempt_response = json.dumps(
            {
                "movement_description": "Steady climbing.",
                "technique_scores": {
                    "footwork": 3.5,
                    "body_tension": 3.5,
                    "route_reading": 3.5,
                    "efficiency": 3.5,
                },
                "coaching_tips": ["Keep momentum."],
                "difficulty_estimate": "V2",
                "confidence": 0.7,
            }
        )
        summary_response = json.dumps(
            {
                "session_summary": "Consistent session.",
                "overall_recommendations": ["Try harder routes."],
            }
        )

        responses = [attempt_response, summary_response]
        call_idx = 0

        def mock_generate(prompt, images=None, max_tokens=None):
            nonlocal call_idx
            result = responses[call_idx % len(responses)]
            call_idx += 1
            return result

        with patch.object(mock_llm, "_generate", side_effect=mock_generate):
            result = mock_llm.analyze_session(
                attempts_data=[
                    {
                        "index": 1,
                        "duration_seconds": 8.0,
                        "vertical_progress_ratio": 0.35,
                        "lateral_span_ratio": 0.25,
                        "hesitation_markers": [],
                    }
                ],
                frame_images_by_attempt={1: [b"frame1"]},
                session_metrics={
                    "attempt_count": 1,
                    "estimated_time_on_wall_seconds": 8.0,
                    "average_rest_seconds": 15.0,
                    "vertical_progress_ratio": 0.35,
                    "lateral_span_ratio": 0.25,
                    "hesitation_marker_count": 0,
                    "mean_pose_visibility": 0.85,
                },
            )

        assert result is not None
        assert isinstance(result, LLMInsights)
        assert result.model_variant == "gemini-2.5-flash"
        assert len(result.attempt_insights) == 1
        assert result.session_summary == "Consistent session."


class TestGeminiErrorRecovery:
    """Tests that Gemini errors return None instead of crashing."""

    @pytest.fixture
    def mock_llm(self):
        settings = Settings(
            gemma_enabled=True,
            llm_backend="gemini",
            gemini_api_key="test-key",
        )
        from opencrux.gemini_llm import GeminiVisionLLM

        llm = GeminiVisionLLM(settings)
        llm._available = True
        llm._client = MagicMock()
        return llm

    def test_analyze_attempt_returns_none_on_api_error(self, mock_llm):
        with patch.object(
            mock_llm, "_generate", side_effect=RuntimeError("API quota exceeded")
        ):
            result = mock_llm.analyze_attempt(1, [b"img"], {"vertical_progress": 0.5})
        assert result is None

    def test_generate_session_summary_returns_none_on_api_error(self, mock_llm):
        with patch.object(
            mock_llm, "_generate", side_effect=ConnectionError("Network error")
        ):
            result = mock_llm.generate_session_summary([], {})
        assert result is None

    def test_analyze_session_returns_none_on_init_failure(self):
        settings = Settings(
            gemma_enabled=True,
            llm_backend="gemini",
            gemini_api_key="bad-key",
        )
        from opencrux.gemini_llm import GeminiVisionLLM

        llm = GeminiVisionLLM(settings)

        with patch.object(
            llm, "_init_client", side_effect=RuntimeError("Invalid API key")
        ):
            result = llm.analyze_session([], {}, {})

        assert result is None
        assert "Invalid API key" in llm.load_error
