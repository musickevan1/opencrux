"""Tests for training data export."""
from __future__ import annotations

import json
from pathlib import Path

from opencrux.db import Database
from opencrux.pose_store import PoseStore
from opencrux.export import export_session_jsonl, export_all_sessions_jsonl


def _insert_session(db, session_id="sess1", filename="test.mp4"):
    db.execute(
        "INSERT INTO sessions (id, created_at, original_filename, status, session_json) VALUES (?, ?, ?, ?, ?)",
        (session_id, "2026-04-05T00:00:00Z", filename, "completed", '{"test": true}'),
    )
    db.commit()


class TestExportSessionJSONL:
    def test_export_session_with_frames_and_landmarks(self, tmp_path):
        db = Database(tmp_path / "test.db")
        store = PoseStore(db)
        _insert_session(db)

        for i in range(3):
            store.store_frame(
                session_id="sess1", frame_index=i, timestamp_seconds=i * 0.16,
                centroid_x=0.5, centroid_y=0.5 - i * 0.05, visibility_ratio=0.85,
                visible_landmark_count=28, speed=0.02, detected_pose_count=1,
                landmarks=[{"index": j, "x": 0.5 + j * 0.01, "y": 0.5, "z": 0.0, "visibility": 0.9} for j in range(33)],
            )

        store.store_llm_output(
            session_id="sess1", model_variant="gemma4:e4b",
            prompt_text="Analyze...", response_text='{"movement_description": "Good"}',
            attempt_index=1, output_type="attempt_analysis",
        )

        output_path = tmp_path / "export.jsonl"
        export_session_jsonl(db, "sess1", output_path)

        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["session_id"] == "sess1"
        assert len(record["frames"]) == 3
        assert len(record["frames"][0]["landmarks"]) == 33
        assert len(record["llm_outputs"]) == 1
        assert record["session_analysis"] == {"test": True}
        db.close()

    def test_export_missing_session_raises(self, tmp_path):
        import pytest
        db = Database(tmp_path / "test.db")
        with pytest.raises(ValueError, match="not found"):
            export_session_jsonl(db, "nonexistent", tmp_path / "out.jsonl")
        db.close()


class TestExportAll:
    def test_export_multiple_sessions(self, tmp_path):
        db = Database(tmp_path / "test.db")
        _insert_session(db, "sess1", "clip1.mp4")
        _insert_session(db, "sess2", "clip2.mp4")

        output_path = tmp_path / "all.jsonl"
        count = export_all_sessions_jsonl(db, output_path)

        assert count == 2
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 2
        db.close()
