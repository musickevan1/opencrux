from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WarningSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ProcessingWarning(BaseModel):
    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.WARNING


class HesitationMarker(BaseModel):
    timestamp_seconds: float
    duration_seconds: float


class AttemptSummary(BaseModel):
    index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    vertical_progress_ratio: float
    lateral_span_ratio: float
    hesitation_markers: list[HesitationMarker] = Field(default_factory=list)


class SessionMetrics(BaseModel):
    attempt_count: int
    estimated_time_on_wall_seconds: float
    average_rest_seconds: float
    total_rest_seconds: float
    lateral_span_ratio: float
    vertical_progress_ratio: float
    hesitation_marker_count: int
    mean_pose_visibility: float


class PreviewFrame(BaseModel):
    processed_frame_count: int
    timestamp_seconds: float
    detected_pose_count: int
    visible_landmark_count: int
    preview_image_base64: str


class PreviewAttemptWindow(BaseModel):
    index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float


class AnalysisPreview(BaseModel):
    progress_ratio: float = 0.0
    processed_frame_count: int = 0
    total_frame_count: int = 0
    current_timestamp_seconds: float = 0.0
    detected_pose_count: int = 0
    visible_landmark_count: int = 0
    multi_pose_ratio: float = 0.0
    coverage_ratio: float = 0.0
    mean_pose_visibility: float = 0.0
    provisional_attempt_count: int = 0
    provisional_vertical_progress_ratio: float = 0.0
    provisional_lateral_span_ratio: float = 0.0
    stage: str = "Queued for analysis."
    last_update_message: str | None = None
    preview_image_base64: str | None = None
    frames: list[PreviewFrame] = Field(default_factory=list)
    provisional_attempts: list[PreviewAttemptWindow] = Field(default_factory=list)
    active_warnings: list[ProcessingWarning] = Field(default_factory=list)


class SessionAnalysis(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    created_at: datetime = Field(default_factory=utc_now)
    status: SessionStatus
    original_filename: str
    stored_video_path: str | None = None
    route_name: str | None = None
    gym_name: str | None = None
    error_message: str | None = None
    processed_frame_count: int = 0
    sampled_fps: float = 0.0
    source_duration_seconds: float = 0.0
    warnings: list[ProcessingWarning] = Field(default_factory=list)
    attempts: list[AttemptSummary] = Field(default_factory=list)
    metrics: SessionMetrics | None = None
    llm_insights: LLMInsights | None = None


class TechniqueScore(BaseModel):
    """Technique scores derived from Gemma 4 vision analysis."""

    footwork: float = Field(
        ge=0.0, le=5.0, description="Foot placement precision and efficiency (0-5)"
    )
    body_tension: float = Field(
        ge=0.0, le=5.0, description="Core engagement and body control (0-5)"
    )
    route_reading: float = Field(
        ge=0.0, le=5.0, description="Ability to read and follow the route (0-5)"
    )
    efficiency: float = Field(
        ge=0.0, le=5.0, description="Movement economy and energy conservation (0-5)"
    )

    @property
    def overall(self) -> float:
        """Average of all technique scores."""
        return round(
            (self.footwork + self.body_tension + self.route_reading + self.efficiency)
            / 4,
            1,
        )


class AttemptInsight(BaseModel):
    """LLM-derived insights for a single climbing attempt."""

    attempt_index: int
    movement_description: str = ""
    technique_scores: TechniqueScore | None = None
    coaching_tips: list[str] = Field(default_factory=list)
    difficulty_estimate: str | None = None
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Model confidence in this analysis (0-1)",
    )


class LLMInsights(BaseModel):
    """Collection of Gemma 4 derived insights for a climbing session."""

    model_variant: str
    analysis_timestamp: datetime = Field(default_factory=utc_now)
    attempt_insights: list[AttemptInsight] = Field(default_factory=list)
    session_summary: str = ""
    overall_recommendations: list[str] = Field(default_factory=list)


class AnalysisJob(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    status: AnalysisJobStatus
    original_filename: str
    route_name: str | None = None
    gym_name: str | None = None
    error_message: str | None = None
    preview: AnalysisPreview = Field(default_factory=AnalysisPreview)
    result: SessionAnalysis | None = None
