import json
from pathlib import Path
from tempfile import TemporaryDirectory

from opencrux.cli import run_manifest


class FakeAnalyzer:
    def analyze(self, video_path: Path, **_: object):
        class _Result:
            def model_dump(self, mode: str = "json") -> dict[str, object]:
                return {
                    "id": f"result-{video_path.stem}",
                    "original_filename": video_path.name,
                    "status": "completed",
                    "attempts": [],
                    "metrics": {
                        "attempt_count": 1,
                        "estimated_time_on_wall_seconds": 4.2,
                        "average_rest_seconds": 0.0,
                        "total_rest_seconds": 0.0,
                        "lateral_span_ratio": 0.2,
                        "vertical_progress_ratio": 0.3,
                        "hesitation_marker_count": 0,
                        "mean_pose_visibility": 0.8,
                    },
                }

        return _Result()


def test_run_manifest_writes_summary_and_per_clip_results() -> None:
    with TemporaryDirectory() as directory:
        base_path = Path(directory)
        manifest_path = base_path / "manifest.json"
        output_dir = base_path / "results"
        clip_path = base_path / "known-good.mp4"
        clip_path.write_bytes(b"clip")
        manifest_path.write_text(
            json.dumps(
                [
                    {
                        "id": "known-good",
                        "filename": "known-good.mp4",
                        "source": "user-owned",
                        "notes": "single climber",
                    }
                ]
            ),
            encoding="utf-8",
        )

        summary = run_manifest(FakeAnalyzer(), manifest_path, output_dir)

        assert summary["result_count"] == 1
        assert summary["results"][0]["status"] == "completed"
        assert (output_dir / "known-good.json").exists()
        assert (output_dir / "summary.json").exists()


def test_run_manifest_marks_missing_videos() -> None:
    with TemporaryDirectory() as directory:
        base_path = Path(directory)
        manifest_path = base_path / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                [
                    {
                        "id": "missing-clip",
                        "filename": "missing.mp4",
                        "source": "user-owned",
                    }
                ]
            ),
            encoding="utf-8",
        )

        summary = run_manifest(FakeAnalyzer(), manifest_path, None)

        assert summary["results"][0]["status"] == "missing"