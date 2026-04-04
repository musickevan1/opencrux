import time
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from opencrux.analysis import AnalysisError, AnalysisPreviewUpdate
from opencrux.config import Settings
from opencrux.main import create_app
from opencrux.models import PreviewAttemptWindow, ProcessingWarning, SessionAnalysis, SessionMetrics, SessionStatus


class FakeAnalyzer:
    def __init__(self, stored_video_path: str) -> None:
        self.stored_video_path = stored_video_path

    def analyze(self, video_path: Path, **_: object) -> SessionAnalysis:
        return SessionAnalysis(
            id="session-123",
            status=SessionStatus.COMPLETED,
            original_filename="demo.mp4",
            stored_video_path=self.stored_video_path,
            source_duration_seconds=12.0,
            sampled_fps=6.0,
            metrics=SessionMetrics(
                attempt_count=1,
                estimated_time_on_wall_seconds=8.5,
                average_rest_seconds=0.0,
                total_rest_seconds=0.0,
                lateral_span_ratio=0.22,
                vertical_progress_ratio=0.31,
                hesitation_marker_count=0,
                mean_pose_visibility=0.8,
            ),
        )


class FakeStreamingAnalyzer:
    def analyze(self, video_path: Path, **kwargs: object) -> SessionAnalysis:
        progress_callback = kwargs.get("progress_callback")
        if callable(progress_callback):
            progress_callback(
                AnalysisPreviewUpdate(
                    progress_ratio=0.3,
                    processed_frame_count=3,
                    total_frame_count=10,
                    current_timestamp_seconds=0.48,
                    detected_pose_count=1,
                    visible_landmark_count=18,
                    multi_pose_ratio=0.0,
                    coverage_ratio=0.67,
                    mean_pose_visibility=0.82,
                    provisional_attempt_count=1,
                    provisional_vertical_progress_ratio=0.21,
                    provisional_lateral_span_ratio=0.08,
                    stage="Sampling frames and fitting pose landmarks.",
                    last_update_message="Frame 3/10 at 0.48s",
                    preview_image_base64="ZmFrZS1wcmV2aWV3",
                    provisional_attempts=[
                        PreviewAttemptWindow(index=1, start_seconds=0.0, end_seconds=0.48, duration_seconds=0.48)
                    ],
                    active_warnings=[
                        ProcessingWarning(
                            code="low_pose_coverage",
                            message="Pose coverage is currently intermittent.",
                        )
                    ],
                )
            )
            time.sleep(0.02)

        return SessionAnalysis(
            id="session-stream-123",
            status=SessionStatus.COMPLETED,
            original_filename=video_path.name,
            stored_video_path=str(video_path),
            source_duration_seconds=9.5,
            sampled_fps=6.0,
            metrics=SessionMetrics(
                attempt_count=1,
                estimated_time_on_wall_seconds=8.2,
                average_rest_seconds=0.0,
                total_rest_seconds=0.0,
                lateral_span_ratio=0.19,
                vertical_progress_ratio=0.27,
                hesitation_marker_count=0,
                mean_pose_visibility=0.81,
            ),
        )


class FakeFailingAnalyzer:
    def analyze(self, video_path: Path, **kwargs: object) -> SessionAnalysis:
        progress_callback = kwargs.get("progress_callback")
        if callable(progress_callback):
            progress_callback(
                AnalysisPreviewUpdate(
                    progress_ratio=0.55,
                    processed_frame_count=6,
                    total_frame_count=10,
                    current_timestamp_seconds=1.1,
                    detected_pose_count=2,
                    visible_landmark_count=15,
                    multi_pose_ratio=0.6,
                    coverage_ratio=0.48,
                    mean_pose_visibility=0.58,
                    provisional_attempt_count=1,
                    provisional_vertical_progress_ratio=0.2,
                    provisional_lateral_span_ratio=0.11,
                    stage="Sampling frames and fitting pose landmarks.",
                    last_update_message="Frame 6/10 at 1.10s",
                    preview_image_base64="ZmFrZS1wcmV2aWV3LWZhaWw=",
                    active_warnings=[
                        ProcessingWarning(
                            code="multiple_people_dominant",
                            message="Multiple climbers are dominating sampled frames. This clip is likely unsupported for the current slice.",
                            severity="error",
                        )
                    ],
                )
            )

        raise AnalysisError(
            "OpenCrux detected multiple climbers for a substantial portion of this clip. The current slice only supports one dominant climber per video."
        )


class FakeLimitAnalyzer:
    def analyze(self, video_path: Path, **kwargs: object) -> SessionAnalysis:
        session_id = str(kwargs.get("session_id") or video_path.stem)
        return SessionAnalysis(
            id=session_id,
            status=SessionStatus.COMPLETED,
            original_filename=video_path.name,
            stored_video_path=str(video_path),
            source_duration_seconds=10.0,
            sampled_fps=6.0,
            metrics=SessionMetrics(
                attempt_count=1,
                estimated_time_on_wall_seconds=6.0,
                average_rest_seconds=0.0,
                total_rest_seconds=0.0,
                lateral_span_ratio=0.12,
                vertical_progress_ratio=0.33,
                hesitation_marker_count=0,
                mean_pose_visibility=0.79,
            ),
        )


def test_index_route_exposes_workspace_shell() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        body = response.text
        assert 'id="analysis-workspace"' in body
        assert 'id="verdict-band"' in body
        assert 'id="analysis-form"' in body
        assert 'id="history-shelf"' in body


def test_health_endpoint() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        client = TestClient(app)

        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_analyze_endpoint_persists_session() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        app.state.analyzer = FakeAnalyzer(stored_video_path="data/uploads/demo.mp4")
        client = TestClient(app)

        response = client.post(
            "/api/sessions/analyze",
            files={"file": ("demo.mp4", b"video-bytes", "video/mp4")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == "session-123"

        stored = client.get("/api/sessions/session-123")
        assert stored.status_code == 200
        assert stored.json()["metrics"]["attempt_count"] == 1


def test_analyze_endpoint_rejects_bad_extension() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        client = TestClient(app)

        response = client.post(
            "/api/sessions/analyze",
            files={"file": ("demo.txt", b"not-a-video", "text/plain")},
        )

        assert response.status_code == 400


def test_list_sessions_returns_saved_results() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        app.state.analyzer = FakeAnalyzer(stored_video_path="data/uploads/demo.mp4")
        client = TestClient(app)

        client.post(
            "/api/sessions/analyze",
            files={"file": ("demo.mp4", b"video-bytes", "video/mp4")},
        )

        response = client.get("/api/sessions?limit=5")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == "session-123"


def test_list_sessions_honors_requested_limit() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        app.state.analyzer = FakeLimitAnalyzer()
        client = TestClient(app)

        for index in range(3):
            client.post(
                "/api/sessions/analyze",
                files={"file": (f"demo-{index}.mp4", b"video-bytes", "video/mp4")},
            )

        response = client.get("/api/sessions?limit=2")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2


def test_analysis_job_endpoint_streams_preview_and_completes() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        app.state.analyzer = FakeStreamingAnalyzer()
        client = TestClient(app)

        create_response = client.post(
            "/api/analysis-jobs",
            files={"file": ("demo.mp4", b"video-bytes", "video/mp4")},
        )

        assert create_response.status_code == 202
        job_id = create_response.json()["id"]

        deadline = time.monotonic() + 2.0
        payload = None
        while time.monotonic() < deadline:
            response = client.get(f"/api/analysis-jobs/{job_id}")
            assert response.status_code == 200
            payload = response.json()
            if payload["status"] == "completed":
                break
            time.sleep(0.02)

        assert payload is not None
        assert payload["status"] == "completed"
        assert payload["preview"]["preview_image_base64"] == "ZmFrZS1wcmV2aWV3"
        assert payload["preview"]["frames"][0]["preview_image_base64"] == "ZmFrZS1wcmV2aWV3"
        assert payload["preview"]["provisional_attempt_count"] == 1
        assert payload["preview"]["active_warnings"][0]["code"] == "low_pose_coverage"
        assert payload["result"]["id"] == "session-stream-123"


def test_analysis_job_endpoint_exposes_failed_job_state() -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            data_dir=Path(directory),
            upload_dir=Path(directory) / "uploads",
            session_dir=Path(directory) / "sessions",
        )
        app = create_app(settings)
        app.state.analyzer = FakeFailingAnalyzer()
        client = TestClient(app)

        create_response = client.post(
            "/api/analysis-jobs",
            files={"file": ("demo.mp4", b"video-bytes", "video/mp4")},
        )

        assert create_response.status_code == 202
        job_id = create_response.json()["id"]

        deadline = time.monotonic() + 2.0
        payload = None
        while time.monotonic() < deadline:
            response = client.get(f"/api/analysis-jobs/{job_id}")
            assert response.status_code == 200
            payload = response.json()
            if payload["status"] == "failed":
                break
            time.sleep(0.02)

        assert payload is not None
        assert payload["status"] == "failed"
        assert payload["preview"]["frames"][0]["preview_image_base64"] == "ZmFrZS1wcmV2aWV3LWZhaWw="
        assert payload["preview"]["active_warnings"][0]["severity"] == "error"
        assert "one dominant climber" in payload["error_message"]

