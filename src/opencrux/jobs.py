from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from uuid import uuid4

from .analysis import AnalysisPreviewUpdate
from .models import AnalysisJob, AnalysisJobStatus, AnalysisPreview, PreviewFrame, SessionAnalysis, utc_now


class AnalysisJobStore:
    def __init__(self, max_workers: int = 2, max_preview_frames: int = 10) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="opencrux-analysis")
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = Lock()
        self._max_preview_frames = max_preview_frames

    def create(self, *, original_filename: str, route_name: str | None, gym_name: str | None) -> AnalysisJob:
        job = AnalysisJob(
            id=uuid4().hex,
            status=AnalysisJobStatus.QUEUED,
            original_filename=original_filename,
            route_name=route_name,
            gym_name=gym_name,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> AnalysisJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def submit(self, fn, /, *args, **kwargs) -> Future:
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def mark_running(self, job_id: str, *, stage: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return

            preview = job.preview.model_copy(update={"stage": stage, "last_update_message": stage})
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": AnalysisJobStatus.RUNNING,
                    "updated_at": utc_now(),
                    "preview": preview,
                }
            )

    def update_preview(self, job_id: str, update: AnalysisPreviewUpdate) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return

            current_preview = job.preview
            frames = list(current_preview.frames)
            if update.preview_image_base64:
                next_frame = PreviewFrame(
                    processed_frame_count=update.processed_frame_count,
                    timestamp_seconds=update.current_timestamp_seconds,
                    detected_pose_count=update.detected_pose_count,
                    visible_landmark_count=update.visible_landmark_count,
                    preview_image_base64=update.preview_image_base64,
                )
                if frames and frames[-1].processed_frame_count == next_frame.processed_frame_count:
                    frames[-1] = next_frame
                else:
                    frames.append(next_frame)
                frames = frames[-self._max_preview_frames :]

            preview = current_preview.model_copy(
                update={
                    "progress_ratio": update.progress_ratio,
                    "processed_frame_count": update.processed_frame_count,
                    "total_frame_count": update.total_frame_count,
                    "current_timestamp_seconds": update.current_timestamp_seconds,
                    "detected_pose_count": update.detected_pose_count,
                    "visible_landmark_count": update.visible_landmark_count,
                    "multi_pose_ratio": update.multi_pose_ratio,
                    "coverage_ratio": update.coverage_ratio,
                    "mean_pose_visibility": update.mean_pose_visibility,
                    "provisional_attempt_count": update.provisional_attempt_count,
                    "provisional_vertical_progress_ratio": update.provisional_vertical_progress_ratio,
                    "provisional_lateral_span_ratio": update.provisional_lateral_span_ratio,
                    "stage": update.stage,
                    "last_update_message": update.last_update_message,
                    "preview_image_base64": update.preview_image_base64 or current_preview.preview_image_base64,
                    "frames": frames,
                    "provisional_attempts": update.provisional_attempts,
                    "active_warnings": update.active_warnings,
                }
            )
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": AnalysisJobStatus.RUNNING,
                    "updated_at": utc_now(),
                    "preview": preview,
                }
            )

    def complete(self, job_id: str, result: SessionAnalysis) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return

            preview = job.preview.model_copy(
                update={
                    "progress_ratio": 1.0,
                    "stage": "Analysis complete.",
                    "last_update_message": "Analysis complete.",
                }
            )
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": AnalysisJobStatus.COMPLETED,
                    "updated_at": utc_now(),
                    "preview": preview,
                    "result": result,
                }
            )

    def fail(self, job_id: str, error_message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return

            preview = job.preview.model_copy(
                update={
                    "stage": "Analysis failed.",
                    "last_update_message": error_message,
                }
            )
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": AnalysisJobStatus.FAILED,
                    "updated_at": utc_now(),
                    "error_message": error_message,
                    "preview": preview,
                }
            )