from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .models import (
    AttemptSummary,
    HesitationMarker,
    ProcessingWarning,
    PreviewAttemptWindow,
    SessionMetrics,
    WarningSeverity,
)


MULTI_CLIMBER_FAILURE_MESSAGE = (
    "OpenCrux detected multiple climbers for a substantial portion of this clip. "
    "The current slice only supports one dominant climber per video."
)


@dataclass(frozen=True, slots=True)
class HeuristicProfile:
    analysis_sample_fps: float = 6.0
    min_pose_visibility: float = 0.5
    min_visible_landmarks: int = 10
    max_attempt_gap_seconds: float = 2.5
    min_attempt_duration_seconds: float = 1.5
    hesitation_speed_threshold: float = 0.018
    hesitation_min_duration_seconds: float = 1.5
    multi_pose_warning_ratio: float = 0.04
    multi_pose_failure_ratio: float = 0.25


DEFAULT_HEURISTIC_PROFILE = HeuristicProfile()


@dataclass(slots=True)
class FrameObservation:
    timestamp_seconds: float
    centroid_x: float
    centroid_y: float
    visibility_ratio: float
    visible_landmarks: int
    speed: float = 0.0


def get_multi_pose_ratio(multi_pose_frames: int, sampled_frames: int) -> float:
    if sampled_frames <= 0:
        return 0.0
    return multi_pose_frames / sampled_frames


def segment_attempts(
    observations: list[FrameObservation],
    *,
    max_gap_seconds: float,
    min_attempt_duration_seconds: float,
) -> list[list[FrameObservation]]:
    if not observations:
        return []

    attempts: list[list[FrameObservation]] = []
    current: list[FrameObservation] = [observations[0]]

    for previous, current_observation in zip(observations, observations[1:]):
        if current_observation.timestamp_seconds - previous.timestamp_seconds > max_gap_seconds:
            if current[-1].timestamp_seconds - current[0].timestamp_seconds >= min_attempt_duration_seconds:
                attempts.append(current)
            current = [current_observation]
            continue

        current.append(current_observation)

    if current[-1].timestamp_seconds - current[0].timestamp_seconds >= min_attempt_duration_seconds:
        attempts.append(current)

    return attempts


def detect_hesitation_markers(
    observations: list[FrameObservation],
    *,
    speed_threshold: float,
    min_duration_seconds: float,
) -> list[HesitationMarker]:
    markers: list[HesitationMarker] = []
    pause_start: float | None = None

    for observation in observations:
        if observation.speed <= speed_threshold:
            pause_start = observation.timestamp_seconds if pause_start is None else pause_start
            continue

        if pause_start is not None:
            pause_duration = observation.timestamp_seconds - pause_start
            if pause_duration >= min_duration_seconds:
                markers.append(
                    HesitationMarker(
                        timestamp_seconds=round(pause_start, 2),
                        duration_seconds=round(pause_duration, 2),
                    )
                )
            pause_start = None

    if pause_start is not None:
        pause_duration = observations[-1].timestamp_seconds - pause_start
        if pause_duration >= min_duration_seconds:
            markers.append(
                HesitationMarker(
                    timestamp_seconds=round(pause_start, 2),
                    duration_seconds=round(pause_duration, 2),
                )
            )

    return markers


def derive_session_metrics(
    attempts: list[list[FrameObservation]],
    *,
    speed_threshold: float,
    hesitation_min_duration_seconds: float,
) -> tuple[list[AttemptSummary], SessionMetrics]:
    summaries: list[AttemptSummary] = []
    all_observations = [observation for attempt in attempts for observation in attempt]
    rest_gaps: list[float] = []

    for index, attempt in enumerate(attempts, start=1):
        start_seconds = attempt[0].timestamp_seconds
        end_seconds = attempt[-1].timestamp_seconds
        hesitation_markers = detect_hesitation_markers(
            attempt,
            speed_threshold=speed_threshold,
            min_duration_seconds=hesitation_min_duration_seconds,
        )
        summaries.append(
            AttemptSummary(
                index=index,
                start_seconds=round(start_seconds, 2),
                end_seconds=round(end_seconds, 2),
                duration_seconds=round(end_seconds - start_seconds, 2),
                vertical_progress_ratio=round(max(0.0, attempt[0].centroid_y - min(item.centroid_y for item in attempt)), 3),
                lateral_span_ratio=round(max(item.centroid_x for item in attempt) - min(item.centroid_x for item in attempt), 3),
                hesitation_markers=hesitation_markers,
            )
        )

    for current_attempt, next_attempt in zip(summaries, summaries[1:]):
        rest_gaps.append(next_attempt.start_seconds - current_attempt.end_seconds)

    metrics = SessionMetrics(
        attempt_count=len(summaries),
        estimated_time_on_wall_seconds=round(sum(item.duration_seconds for item in summaries), 2),
        average_rest_seconds=round(sum(rest_gaps) / len(rest_gaps), 2) if rest_gaps else 0.0,
        total_rest_seconds=round(sum(rest_gaps), 2),
        lateral_span_ratio=round(max(item.centroid_x for item in all_observations) - min(item.centroid_x for item in all_observations), 3),
        vertical_progress_ratio=round(max(0.0, all_observations[0].centroid_y - min(item.centroid_y for item in all_observations)), 3),
        hesitation_marker_count=sum(len(item.hesitation_markers) for item in summaries),
        mean_pose_visibility=round(mean(item.visibility_ratio for item in all_observations), 3),
    )
    return summaries, metrics


def derive_provisional_movement_metrics(observations: list[FrameObservation]) -> tuple[float, float, float]:
    if not observations:
        return 0.0, 0.0, 0.0

    vertical_progress_ratio = round(max(0.0, observations[0].centroid_y - min(item.centroid_y for item in observations)), 3)
    lateral_span_ratio = round(max(item.centroid_x for item in observations) - min(item.centroid_x for item in observations), 3)
    mean_pose_visibility = round(mean(item.visibility_ratio for item in observations), 3)
    return vertical_progress_ratio, lateral_span_ratio, mean_pose_visibility


def derive_preview_attempts(
    observations: list[FrameObservation],
    *,
    max_gap_seconds: float,
    min_attempt_duration_seconds: float,
) -> list[PreviewAttemptWindow]:
    provisional_attempts = segment_attempts(
        observations,
        max_gap_seconds=max_gap_seconds,
        min_attempt_duration_seconds=min_attempt_duration_seconds,
    )
    return [
        PreviewAttemptWindow(
            index=index,
            start_seconds=round(attempt[0].timestamp_seconds, 2),
            end_seconds=round(attempt[-1].timestamp_seconds, 2),
            duration_seconds=round(attempt[-1].timestamp_seconds - attempt[0].timestamp_seconds, 2),
        )
        for index, attempt in enumerate(provisional_attempts, start=1)
    ]


def derive_preview_warnings(
    *,
    sampled_frames: int,
    coverage_ratio: float,
    mean_pose_visibility: float,
    multi_pose_ratio: float,
    multi_pose_warning_ratio: float,
    multi_pose_failure_ratio: float,
) -> list[ProcessingWarning]:
    warnings: list[ProcessingWarning] = []

    if sampled_frames >= 12 and coverage_ratio < 0.4:
        warnings.append(
            ProcessingWarning(
                code="low_pose_coverage",
                message="Pose coverage is currently intermittent. Occlusion or framing may reduce reliability.",
            )
        )
    if mean_pose_visibility > 0 and mean_pose_visibility < 0.55:
        warnings.append(
            ProcessingWarning(
                code="low_visibility",
                message="Visible landmark quality is trending low in the sampled frames so far.",
            )
        )
    if multi_pose_ratio >= multi_pose_failure_ratio:
        warnings.append(
            ProcessingWarning(
                code="multiple_people_dominant",
                message="Multiple climbers are dominating sampled frames. This clip is likely unsupported for the current slice.",
                severity=WarningSeverity.ERROR,
            )
        )
    elif multi_pose_ratio >= multi_pose_warning_ratio:
        warnings.append(
            ProcessingWarning(
                code="multiple_people_detected",
                message="More than one pose is appearing in sampled frames. OpenCrux is still evaluating whether one climber remains dominant.",
            )
        )

    return warnings


def derive_final_warnings(
    *,
    sampled_frames: int,
    coverage_ratio: float,
    metrics: SessionMetrics,
    multi_pose_ratio: float,
    source_duration_seconds: float,
    attempt_summaries: list[AttemptSummary],
    multi_pose_warning_ratio: float,
    multi_pose_failure_ratio: float,
) -> tuple[list[ProcessingWarning], str | None]:
    warnings: list[ProcessingWarning] = []

    if sampled_frames < 12:
        warnings.append(
            ProcessingWarning(
                code="short_clip",
                message="This clip is short, so timing and hesitation markers may be less stable than usual.",
                severity=WarningSeverity.INFO,
            )
        )
    if coverage_ratio < 0.4:
        warnings.append(
            ProcessingWarning(
                code="low_pose_coverage",
                message="Pose coverage was intermittent. Occlusion or framing may have reduced reliability.",
            )
        )
    if metrics.mean_pose_visibility < 0.55:
        warnings.append(
            ProcessingWarning(
                code="low_visibility",
                message="Visible landmark quality was low for parts of this clip.",
            )
        )
    if multi_pose_ratio >= multi_pose_failure_ratio:
        return warnings, MULTI_CLIMBER_FAILURE_MESSAGE
    if multi_pose_ratio >= multi_pose_warning_ratio:
        warnings.append(
            ProcessingWarning(
                code="multiple_people_detected",
                message="Multiple poses were detected in part of this clip. OpenCrux currently targets one dominant climber per video.",
            )
        )
    if len(attempt_summaries) == 1 and source_duration_seconds >= 45:
        warnings.append(
            ProcessingWarning(
                code="attempt_segmentation_ambiguous",
                message="This long continuous clip was treated as a single attempt. Split attempts are only inferred when the pose signal clearly drops out between them.",
            )
        )

    return warnings, None