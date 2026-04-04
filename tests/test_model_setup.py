from pathlib import Path

from opencrux.analysis import ensure_pose_model_file, get_multi_pose_ratio
from opencrux.config import Settings


def test_ensure_pose_model_file_uses_existing_file(tmp_path: Path) -> None:
    pose_model_path = tmp_path / "models" / "pose_landmarker_full.task"
    pose_model_path.parent.mkdir(parents=True, exist_ok=True)
    pose_model_path.write_bytes(b"existing-model")
    settings = Settings(
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        upload_dir=tmp_path / "uploads",
        session_dir=tmp_path / "sessions",
        pose_model_path=pose_model_path,
    )

    resolved = ensure_pose_model_file(settings)

    assert resolved == pose_model_path
    assert resolved.read_bytes() == b"existing-model"


def test_ensure_pose_model_file_downloads_when_missing(tmp_path: Path, monkeypatch) -> None:
    pose_model_path = tmp_path / "models" / "pose_landmarker_full.task"
    settings = Settings(
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        upload_dir=tmp_path / "uploads",
        session_dir=tmp_path / "sessions",
        pose_model_path=pose_model_path,
        pose_model_url="https://example.com/pose.task",
    )

    def fake_urlretrieve(url: str, destination: Path) -> tuple[str, object]:
        assert url == "https://example.com/pose.task"
        Path(destination).write_bytes(b"downloaded-model")
        return str(destination), None

    monkeypatch.setattr("opencrux.analysis.urlretrieve", fake_urlretrieve)

    resolved = ensure_pose_model_file(settings)

    assert resolved == pose_model_path
    assert pose_model_path.read_bytes() == b"downloaded-model"


def test_get_multi_pose_ratio_handles_zero_frames() -> None:
    assert get_multi_pose_ratio(4, 0) == 0.0


def test_get_multi_pose_ratio_computes_fraction() -> None:
    assert get_multi_pose_ratio(5, 50) == 0.1