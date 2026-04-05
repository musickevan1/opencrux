from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .heuristics import DEFAULT_HEURISTIC_PROFILE


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENCRUX_", env_file=".env", extra="ignore"
    )

    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    models_dir: Path = Field(default=PROJECT_ROOT / "data" / "models")
    upload_dir: Path = Field(default=PROJECT_ROOT / "data" / "uploads")
    session_dir: Path = Field(default=PROJECT_ROOT / "data" / "sessions")
    pose_model_path: Path = Field(
        default=PROJECT_ROOT / "data" / "models" / "pose_landmarker_full.task"
    )
    pose_model_url: str = Field(
        default=(
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
        )
    )
    analysis_sample_fps: float = DEFAULT_HEURISTIC_PROFILE.analysis_sample_fps
    min_pose_visibility: float = DEFAULT_HEURISTIC_PROFILE.min_pose_visibility
    min_visible_landmarks: int = DEFAULT_HEURISTIC_PROFILE.min_visible_landmarks
    max_attempt_gap_seconds: float = DEFAULT_HEURISTIC_PROFILE.max_attempt_gap_seconds
    min_attempt_duration_seconds: float = (
        DEFAULT_HEURISTIC_PROFILE.min_attempt_duration_seconds
    )
    hesitation_speed_threshold: float = (
        DEFAULT_HEURISTIC_PROFILE.hesitation_speed_threshold
    )
    hesitation_min_duration_seconds: float = (
        DEFAULT_HEURISTIC_PROFILE.hesitation_min_duration_seconds
    )
    multi_pose_warning_ratio: float = DEFAULT_HEURISTIC_PROFILE.multi_pose_warning_ratio
    multi_pose_failure_ratio: float = DEFAULT_HEURISTIC_PROFILE.multi_pose_failure_ratio
    preview_frame_stride: int = 3
    preview_jpeg_quality: int = 72
    preview_max_width: int = 960
    preview_history_limit: int = 10

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.session_dir.mkdir(parents=True, exist_ok=True)
    return settings
