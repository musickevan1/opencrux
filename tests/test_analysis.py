from opencrux.analysis import (
    FrameObservation,
    derive_final_warnings,
    derive_preview_attempts,
    derive_provisional_movement_metrics,
    derive_preview_warnings,
    derive_session_metrics,
    segment_attempts,
)
from opencrux.heuristics import DEFAULT_HEURISTIC_PROFILE
from opencrux.models import SessionMetrics


def test_segment_attempts_splits_on_large_gap() -> None:
    observations = [
        FrameObservation(timestamp_seconds=0.0, centroid_x=0.4, centroid_y=0.9, visibility_ratio=0.8, visible_landmarks=20),
        FrameObservation(timestamp_seconds=1.0, centroid_x=0.42, centroid_y=0.8, visibility_ratio=0.8, visible_landmarks=20),
        FrameObservation(timestamp_seconds=4.5, centroid_x=0.51, centroid_y=0.88, visibility_ratio=0.82, visible_landmarks=21),
        FrameObservation(timestamp_seconds=5.6, centroid_x=0.53, centroid_y=0.74, visibility_ratio=0.82, visible_landmarks=21),
    ]

    attempts = segment_attempts(
        observations,
        max_gap_seconds=2.0,
        min_attempt_duration_seconds=0.5,
    )

    assert len(attempts) == 2
    assert attempts[0][0].timestamp_seconds == 0.0
    assert attempts[1][0].timestamp_seconds == 4.5


def test_derive_session_metrics_counts_rest_and_hesitation() -> None:
    attempts = [
        [
            FrameObservation(timestamp_seconds=0.0, centroid_x=0.4, centroid_y=0.92, visibility_ratio=0.8, visible_landmarks=20, speed=0.0),
            FrameObservation(timestamp_seconds=1.0, centroid_x=0.41, centroid_y=0.86, visibility_ratio=0.8, visible_landmarks=20, speed=0.01),
            FrameObservation(timestamp_seconds=2.0, centroid_x=0.46, centroid_y=0.72, visibility_ratio=0.8, visible_landmarks=20, speed=0.09),
        ],
        [
            FrameObservation(timestamp_seconds=5.0, centroid_x=0.48, centroid_y=0.88, visibility_ratio=0.76, visible_landmarks=18, speed=0.0),
            FrameObservation(timestamp_seconds=6.0, centroid_x=0.5, centroid_y=0.79, visibility_ratio=0.76, visible_landmarks=18, speed=0.03),
            FrameObservation(timestamp_seconds=7.0, centroid_x=0.56, centroid_y=0.7, visibility_ratio=0.76, visible_landmarks=18, speed=0.08),
        ],
    ]

    summaries, metrics = derive_session_metrics(
        attempts,
        speed_threshold=0.02,
        hesitation_min_duration_seconds=0.9,
    )

    assert metrics.attempt_count == 2
    assert metrics.average_rest_seconds == 3.0
    assert metrics.hesitation_marker_count == 2
    assert summaries[0].vertical_progress_ratio > 0
    assert summaries[1].lateral_span_ratio > 0


def test_preview_helpers_surface_attempts_and_warning_state() -> None:
    observations = [
        FrameObservation(timestamp_seconds=0.0, centroid_x=0.4, centroid_y=0.92, visibility_ratio=0.52, visible_landmarks=20, speed=0.0),
        FrameObservation(timestamp_seconds=1.0, centroid_x=0.44, centroid_y=0.81, visibility_ratio=0.5, visible_landmarks=19, speed=0.02),
        FrameObservation(timestamp_seconds=2.0, centroid_x=0.46, centroid_y=0.7, visibility_ratio=0.48, visible_landmarks=18, speed=0.06),
    ]

    preview_attempts = derive_preview_attempts(
        observations,
        max_gap_seconds=2.0,
        min_attempt_duration_seconds=1.5,
    )
    vertical_progress_ratio, lateral_span_ratio, mean_pose_visibility = derive_provisional_movement_metrics(observations)
    warnings = derive_preview_warnings(
        sampled_frames=15,
        coverage_ratio=0.2,
        mean_pose_visibility=mean_pose_visibility,
        multi_pose_ratio=0.3,
        multi_pose_warning_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_warning_ratio,
        multi_pose_failure_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_failure_ratio,
    )

    assert len(preview_attempts) == 1
    assert preview_attempts[0].duration_seconds == 2.0
    assert vertical_progress_ratio > 0
    assert lateral_span_ratio > 0
    assert any(item.code == "low_pose_coverage" for item in warnings)
    assert any(item.code == "multiple_people_dominant" for item in warnings)


def test_multi_pose_warning_threshold_is_conservative_without_crossing_failure_gate() -> None:
    preview_warnings = derive_preview_warnings(
        sampled_frames=20,
        coverage_ratio=0.7,
        mean_pose_visibility=0.82,
        multi_pose_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_warning_ratio,
        multi_pose_warning_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_warning_ratio,
        multi_pose_failure_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_failure_ratio,
    )

    assert any(item.code == "multiple_people_detected" for item in preview_warnings)
    assert all(item.code != "multiple_people_dominant" for item in preview_warnings)

    final_warnings, failure_message = derive_final_warnings(
        sampled_frames=20,
        coverage_ratio=0.7,
        metrics=SessionMetrics(
            attempt_count=1,
            estimated_time_on_wall_seconds=8.5,
            average_rest_seconds=0.0,
            total_rest_seconds=0.0,
            lateral_span_ratio=0.1,
            vertical_progress_ratio=0.22,
            hesitation_marker_count=0,
            mean_pose_visibility=0.82,
        ),
        multi_pose_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_warning_ratio,
        source_duration_seconds=8.5,
        attempt_summaries=[],
        multi_pose_warning_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_warning_ratio,
        multi_pose_failure_ratio=DEFAULT_HEURISTIC_PROFILE.multi_pose_failure_ratio,
    )

    assert failure_message is None
    assert any(item.code == "multiple_people_detected" for item in final_warnings)
    assert all(item.code != "multiple_people_dominant" for item in final_warnings)
