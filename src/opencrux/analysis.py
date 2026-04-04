from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from statistics import mean
from typing import Callable
from urllib.error import URLError
from urllib.request import urlretrieve
from uuid import uuid4

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .config import Settings
from .heuristics import (
    FrameObservation,
    derive_final_warnings,
    derive_preview_attempts,
    derive_preview_warnings,
    derive_provisional_movement_metrics,
    derive_session_metrics,
    get_multi_pose_ratio,
    segment_attempts,
)
from .models import (
    AttemptSummary,
    LLMInsights,
    ProcessingWarning,
    PreviewAttemptWindow,
    SessionAnalysis,
    SessionStatus,
)

logger = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    pass


@dataclass(slots=True)
class AnalysisPreviewUpdate:
    progress_ratio: float
    processed_frame_count: int
    total_frame_count: int
    current_timestamp_seconds: float
    detected_pose_count: int
    visible_landmark_count: int
    multi_pose_ratio: float
    stage: str
    coverage_ratio: float = 0.0
    mean_pose_visibility: float = 0.0
    provisional_attempt_count: int = 0
    provisional_vertical_progress_ratio: float = 0.0
    provisional_lateral_span_ratio: float = 0.0
    last_update_message: str | None = None
    preview_image_base64: str | None = None
    provisional_attempts: list[PreviewAttemptWindow] = field(default_factory=list)
    active_warnings: list[ProcessingWarning] = field(default_factory=list)


POSE_CONNECTIONS = vision.PoseLandmarksConnections.POSE_LANDMARKS


def draw_pose_landmarks(
    frame: cv2.typing.MatLike, landmarks: list, *, color: tuple[int, int, int]
) -> None:
    height, width = frame.shape[:2]
    for connection in POSE_CONNECTIONS:
        start = landmarks[connection.start]
        end = landmarks[connection.end]
        if start.visibility < 0.2 or end.visibility < 0.2:
            continue

        start_point = (int(start.x * width), int(start.y * height))
        end_point = (int(end.x * width), int(end.y * height))
        cv2.line(frame, start_point, end_point, color, 2, cv2.LINE_AA)

    for landmark in landmarks:
        if landmark.visibility < 0.2:
            continue
        center = (int(landmark.x * width), int(landmark.y * height))
        cv2.circle(frame, center, 4, color, -1, cv2.LINE_AA)


def build_preview_image(
    frame: cv2.typing.MatLike,
    pose_landmarks: list[list],
    *,
    timestamp_seconds: float,
    processed_frame_count: int,
    total_frame_count: int,
    detected_pose_count: int,
    multi_pose_ratio: float,
    max_width: int,
    jpeg_quality: int,
) -> str | None:
    preview = frame.copy()

    if preview.shape[1] > max_width:
        scaled_height = int(preview.shape[0] * (max_width / preview.shape[1]))
        preview = cv2.resize(
            preview, (max_width, max(1, scaled_height)), interpolation=cv2.INTER_AREA
        )

    for index, landmarks in enumerate(pose_landmarks[:2]):
        color = (71, 107, 191) if index == 0 else (167, 132, 83)
        draw_pose_landmarks(preview, landmarks, color=color)

    cv2.rectangle(preview, (12, 12), (410, 110), (28, 24, 20), -1)
    overlay_lines = [
        f"t={timestamp_seconds:.2f}s frames={processed_frame_count}/{max(total_frame_count, processed_frame_count)}",
        f"poses={detected_pose_count} multi-pose-rate={multi_pose_ratio:.2%}",
        "blue=primary pose, bronze=additional pose",
    ]
    for index, line in enumerate(overlay_lines):
        cv2.putText(
            preview,
            line,
            (24, 38 + (index * 24)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (245, 238, 229),
            2,
            cv2.LINE_AA,
        )

    success, encoded = cv2.imencode(
        ".jpg",
        preview,
        [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
    )
    if not success:
        return None

    return base64.b64encode(encoded.tobytes()).decode("ascii")


def ensure_pose_model_file(settings: Settings) -> Path:
    if settings.pose_model_path.exists():
        return settings.pose_model_path

    settings.pose_model_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urlretrieve(settings.pose_model_url, settings.pose_model_path)
    except URLError as error:
        raise AnalysisError(
            "OpenCrux could not download the MediaPipe pose model. Check your network connection or set OPENCRUX_POSE_MODEL_PATH to a local task file."
        ) from error

    return settings.pose_model_path


class VisionAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze(
        self,
        video_path: Path,
        *,
        session_id: str | None = None,
        original_filename: str,
        route_name: str | None = None,
        gym_name: str | None = None,
        progress_callback: Callable[[AnalysisPreviewUpdate], None] | None = None,
    ) -> SessionAnalysis:
        model_path = ensure_pose_model_file(self.settings)
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise AnalysisError("OpenCrux could not open this video file.")

        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        source_duration_seconds = round(frame_count / fps, 2) if fps > 0 else 0.0
        sample_every = (
            max(1, round(fps / self.settings.analysis_sample_fps)) if fps > 0 else 5
        )
        total_sampled_frames = (
            ceil(frame_count / sample_every) if frame_count > 0 else 0
        )
        sampled_fps = (
            round(fps / sample_every, 2)
            if fps > 0
            else self.settings.analysis_sample_fps
        )

        observations: list[FrameObservation] = []
        warnings: list[ProcessingWarning] = []
        sampled_frames = 0
        frame_index = 0
        multi_pose_frames = 0

        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=2,
            min_pose_detection_confidence=self.settings.min_pose_visibility,
            min_pose_presence_confidence=self.settings.min_pose_visibility,
            min_tracking_confidence=self.settings.min_pose_visibility,
            output_segmentation_masks=False,
        )

        with vision.PoseLandmarker.create_from_options(options) as pose:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                if frame_index % sample_every != 0:
                    frame_index += 1
                    continue

                sampled_frames += 1
                timestamp_seconds = (
                    round(frame_index / fps, 3)
                    if fps > 0
                    else round(sampled_frames / sampled_fps, 3)
                )
                timestamp_ms = int(timestamp_seconds * 1000)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                results = pose.detect_for_video(mp_image, timestamp_ms)
                detected_pose_count = (
                    len(results.pose_landmarks) if results.pose_landmarks else 0
                )
                visible_landmark_count = 0

                if results.pose_landmarks:
                    if len(results.pose_landmarks) > 1:
                        multi_pose_frames += 1

                    landmarks = results.pose_landmarks[0]
                    visible_landmarks = [
                        item
                        for item in landmarks
                        if item.visibility >= self.settings.min_pose_visibility
                    ]
                    visible_landmark_count = len(visible_landmarks)
                    if len(visible_landmarks) >= self.settings.min_visible_landmarks:
                        centroid_x = mean(item.x for item in visible_landmarks)
                        centroid_y = mean(item.y for item in visible_landmarks)
                        visibility_ratio = len(visible_landmarks) / len(landmarks)
                        observation = FrameObservation(
                            timestamp_seconds=timestamp_seconds,
                            centroid_x=centroid_x,
                            centroid_y=centroid_y,
                            visibility_ratio=visibility_ratio,
                            visible_landmarks=len(visible_landmarks),
                        )
                        if observations:
                            previous = observations[-1]
                            delta_time = max(
                                observation.timestamp_seconds
                                - previous.timestamp_seconds,
                                1e-6,
                            )
                            delta_x = observation.centroid_x - previous.centroid_x
                            delta_y = observation.centroid_y - previous.centroid_y
                            observation.speed = (
                                (delta_x**2 + delta_y**2) ** 0.5
                            ) / delta_time
                        observations.append(observation)

                if progress_callback is not None:
                    coverage_ratio = (
                        len(observations) / sampled_frames if sampled_frames else 0.0
                    )
                    multi_pose_ratio = get_multi_pose_ratio(
                        multi_pose_frames, sampled_frames
                    )
                    (
                        vertical_progress_ratio,
                        lateral_span_ratio,
                        mean_pose_visibility,
                    ) = derive_provisional_movement_metrics(observations)
                    preview_attempts = derive_preview_attempts(
                        observations,
                        max_gap_seconds=self.settings.max_attempt_gap_seconds,
                        min_attempt_duration_seconds=self.settings.min_attempt_duration_seconds,
                    )
                    preview_warnings = derive_preview_warnings(
                        sampled_frames=sampled_frames,
                        coverage_ratio=coverage_ratio,
                        mean_pose_visibility=mean_pose_visibility,
                        multi_pose_ratio=multi_pose_ratio,
                        multi_pose_warning_ratio=self.settings.multi_pose_warning_ratio,
                        multi_pose_failure_ratio=self.settings.multi_pose_failure_ratio,
                    )
                    preview_image_base64 = None
                    if (
                        sampled_frames == 1
                        or sampled_frames % self.settings.preview_frame_stride == 0
                    ):
                        preview_image_base64 = build_preview_image(
                            frame,
                            results.pose_landmarks if results.pose_landmarks else [],
                            timestamp_seconds=timestamp_seconds,
                            processed_frame_count=sampled_frames,
                            total_frame_count=total_sampled_frames,
                            detected_pose_count=detected_pose_count,
                            multi_pose_ratio=multi_pose_ratio,
                            max_width=self.settings.preview_max_width,
                            jpeg_quality=self.settings.preview_jpeg_quality,
                        )

                    raw_progress_ratio = (
                        (sampled_frames / total_sampled_frames)
                        if total_sampled_frames
                        else 0.0
                    )
                    progress_callback(
                        AnalysisPreviewUpdate(
                            progress_ratio=min(raw_progress_ratio, 0.96),
                            processed_frame_count=sampled_frames,
                            total_frame_count=total_sampled_frames,
                            current_timestamp_seconds=timestamp_seconds,
                            detected_pose_count=detected_pose_count,
                            visible_landmark_count=visible_landmark_count,
                            multi_pose_ratio=multi_pose_ratio,
                            coverage_ratio=coverage_ratio,
                            mean_pose_visibility=mean_pose_visibility,
                            provisional_attempt_count=len(preview_attempts),
                            provisional_vertical_progress_ratio=vertical_progress_ratio,
                            provisional_lateral_span_ratio=lateral_span_ratio,
                            stage="Sampling frames and fitting pose landmarks.",
                            last_update_message=(
                                f"Frame {sampled_frames}/{max(total_sampled_frames, sampled_frames)} at {timestamp_seconds:.2f}s"
                            ),
                            preview_image_base64=preview_image_base64,
                            provisional_attempts=preview_attempts,
                            active_warnings=preview_warnings,
                        )
                    )

                frame_index += 1

        capture.release()

        if not observations:
            raise AnalysisError(
                "OpenCrux could not extract a reliable single-climber pose. Try a clip with one visible climber and a clearer camera angle."
            )

        attempts = segment_attempts(
            observations,
            max_gap_seconds=self.settings.max_attempt_gap_seconds,
            min_attempt_duration_seconds=self.settings.min_attempt_duration_seconds,
        )
        if not attempts:
            raise AnalysisError(
                "OpenCrux detected pose landmarks, but the clip did not contain a long enough active climbing segment for the current heuristic."
            )

        if progress_callback is not None:
            vertical_progress_ratio, lateral_span_ratio, mean_pose_visibility = (
                derive_provisional_movement_metrics(observations)
            )
            preview_attempts = derive_preview_attempts(
                observations,
                max_gap_seconds=self.settings.max_attempt_gap_seconds,
                min_attempt_duration_seconds=self.settings.min_attempt_duration_seconds,
            )
            coverage_ratio = (
                len(observations) / sampled_frames if sampled_frames else 0.0
            )
            multi_pose_ratio = get_multi_pose_ratio(multi_pose_frames, sampled_frames)
            progress_callback(
                AnalysisPreviewUpdate(
                    progress_ratio=0.98,
                    processed_frame_count=sampled_frames,
                    total_frame_count=total_sampled_frames,
                    current_timestamp_seconds=observations[-1].timestamp_seconds,
                    detected_pose_count=1,
                    visible_landmark_count=observations[-1].visible_landmarks,
                    multi_pose_ratio=multi_pose_ratio,
                    coverage_ratio=coverage_ratio,
                    mean_pose_visibility=mean_pose_visibility,
                    provisional_attempt_count=len(preview_attempts),
                    provisional_vertical_progress_ratio=vertical_progress_ratio,
                    provisional_lateral_span_ratio=lateral_span_ratio,
                    stage="Deriving attempts and explainable metrics.",
                    last_update_message="Finalizing attempt segmentation.",
                    provisional_attempts=preview_attempts,
                    active_warnings=derive_preview_warnings(
                        sampled_frames=sampled_frames,
                        coverage_ratio=coverage_ratio,
                        mean_pose_visibility=mean_pose_visibility,
                        multi_pose_ratio=multi_pose_ratio,
                        multi_pose_warning_ratio=self.settings.multi_pose_warning_ratio,
                        multi_pose_failure_ratio=self.settings.multi_pose_failure_ratio,
                    ),
                )
            )

        attempt_summaries, metrics = derive_session_metrics(
            attempts,
            speed_threshold=self.settings.hesitation_speed_threshold,
            hesitation_min_duration_seconds=self.settings.hesitation_min_duration_seconds,
        )

        coverage_ratio = len(observations) / sampled_frames if sampled_frames else 0.0
        multi_pose_ratio = get_multi_pose_ratio(multi_pose_frames, sampled_frames)
        warnings, failure_message = derive_final_warnings(
            sampled_frames=sampled_frames,
            coverage_ratio=coverage_ratio,
            metrics=metrics,
            multi_pose_ratio=multi_pose_ratio,
            source_duration_seconds=source_duration_seconds,
            attempt_summaries=attempt_summaries,
            multi_pose_warning_ratio=self.settings.multi_pose_warning_ratio,
            multi_pose_failure_ratio=self.settings.multi_pose_failure_ratio,
        )
        if failure_message is not None:
            raise AnalysisError(failure_message)

        # Run Gemma 4 LLM analysis if enabled
        llm_insights = self._analyze_with_llm(
            video_path=video_path,
            attempt_summaries=attempt_summaries,
            metrics=metrics,
            observations=observations,
            fps=fps,
            sample_every=sample_every,
        )

        return SessionAnalysis(
            id=session_id or uuid4().hex,
            status=SessionStatus.COMPLETED,
            original_filename=original_filename,
            stored_video_path=str(video_path),
            route_name=route_name,
            gym_name=gym_name,
            processed_frame_count=sampled_frames,
            sampled_fps=sampled_fps,
            source_duration_seconds=source_duration_seconds
            or round(observations[-1].timestamp_seconds, 2),
            warnings=warnings,
            attempts=attempt_summaries,
            metrics=metrics,
            llm_insights=llm_insights,
        )

    def _analyze_with_llm(
        self,
        video_path: Path,
        attempt_summaries: list[AttemptSummary],
        metrics,
        observations: list[FrameObservation],
        fps: float,
        sample_every: int,
    ) -> LLMInsights | None:
        """Run Gemma 4 LLM analysis on the session if enabled.

        Samples key frames per attempt and feeds them to the LLM
        for technique analysis and coaching insights.
        """
        if not self.settings.gemma_enabled:
            return None

        try:
            from .vision_llm import VisionLLM
        except ImportError:
            logger.warning(
                "Gemma LLM module not available. Install with: pip install -e '.[llm]'"
            )
            return None

        llm = VisionLLM(self.settings)
        if not llm.is_available:
            logger.info("Gemma LLM not available: %s", llm.load_error or "unknown")
            return None

        # Sample frames per attempt from the video
        frames_by_attempt = self._sample_attempt_frames(
            video_path=video_path,
            attempt_summaries=attempt_summaries,
            fps=fps,
            sample_every=sample_every,
        )

        # Build session metrics dict for the LLM
        session_metrics = {
            "attempt_count": metrics.attempt_count,
            "estimated_time_on_wall_seconds": metrics.estimated_time_on_wall_seconds,
            "average_rest_seconds": metrics.average_rest_seconds,
            "vertical_progress_ratio": metrics.vertical_progress_ratio,
            "lateral_span_ratio": metrics.lateral_span_ratio,
            "hesitation_marker_count": metrics.hesitation_marker_count,
            "mean_pose_visibility": metrics.mean_pose_visibility,
        }

        # Build attempt data dicts for the LLM
        attempts_data = [
            {
                "index": a.index,
                "duration_seconds": a.duration_seconds,
                "vertical_progress_ratio": a.vertical_progress_ratio,
                "lateral_span_ratio": a.lateral_span_ratio,
                "hesitation_markers": [
                    {"timestamp": h.timestamp_seconds, "duration": h.duration_seconds}
                    for h in a.hesitation_markers
                ],
            }
            for a in attempt_summaries
        ]

        logger.info("Running Gemma 4 LLM analysis on %d attempts", len(attempts_data))
        return llm.analyze_session(
            attempts_data, dict(frames_by_attempt), session_metrics
        )

    def _sample_attempt_frames(
        self,
        video_path: Path,
        attempt_summaries: list[AttemptSummary],
        fps: float,
        sample_every: int,
    ) -> dict[int, list[bytes]]:
        """Extract JPEG frame bytes for key moments in each attempt.

        Samples up to `gemma_sample_frames_per_attempt` frames per attempt
        at evenly spaced timestamps (start, middle, end).
        """
        frames_per_attempt = self.settings.gemma_sample_frames_per_attempt
        frames_by_attempt: dict[int, list[bytes]] = {}

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return frames_by_attempt

        for attempt in attempt_summaries:
            if fps <= 0:
                continue

            # Calculate frame indices to sample
            start_frame = int(attempt.start_seconds * fps)
            end_frame = int(attempt.end_seconds * fps)
            total_frames = max(end_frame - start_frame, 1)

            # Space samples evenly across the attempt
            sample_indices = []
            for i in range(frames_per_attempt):
                if frames_per_attempt == 1:
                    # Single sample: middle of attempt
                    sample_indices.append(start_frame + total_frames // 2)
                else:
                    # Evenly spaced samples
                    fraction = i / (frames_per_attempt - 1)
                    sample_indices.append(start_frame + int(total_frames * fraction))

            jpeg_frames: list[bytes] = []
            for frame_idx in sample_indices:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                success, frame = capture.read()
                if not success:
                    continue

                # Resize for LLM input (keep reasonable size)
                max_dim = 640
                if frame.shape[0] > max_dim or frame.shape[1] > max_dim:
                    scale = max_dim / max(frame.shape[0], frame.shape[1])
                    new_w = int(frame.shape[1] * scale)
                    new_h = int(frame.shape[0] * scale)
                    frame = cv2.resize(
                        frame, (new_w, new_h), interpolation=cv2.INTER_AREA
                    )

                # Encode as JPEG
                _, buffer = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                )
                jpeg_frames.append(buffer.tobytes())

            if jpeg_frames:
                frames_by_attempt[attempt.index] = jpeg_frames

        capture.release()
        return frames_by_attempt
        if failure_message is not None:
            raise AnalysisError(failure_message)

        return SessionAnalysis(
            id=session_id or uuid4().hex,
            status=SessionStatus.COMPLETED,
            original_filename=original_filename,
            stored_video_path=str(video_path),
            route_name=route_name,
            gym_name=gym_name,
            processed_frame_count=sampled_frames,
            sampled_fps=sampled_fps,
            source_duration_seconds=source_duration_seconds
            or round(observations[-1].timestamp_seconds, 2),
            warnings=warnings,
            attempts=attempt_summaries,
            metrics=metrics,
        )
