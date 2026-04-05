"""Tests for SQLite database layer."""
from __future__ import annotations

from opencrux.db import Database


class TestDatabaseInit:
    def test_creates_tables_on_init(self, tmp_path):
        db = Database(tmp_path / "test.db")
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row[0] for row in tables}
        assert "sessions" in table_names
        assert "frames" in table_names
        assert "landmarks" in table_names
        assert "llm_outputs" in table_names
        assert "scores" in table_names
        db.close()

    def test_idempotent_init(self, tmp_path):
        db_path = tmp_path / "test.db"
        db1 = Database(db_path)
        db1.close()
        db2 = Database(db_path)
        tables = db2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert len([r for r in tables if r[0] == "sessions"]) == 1
        db2.close()


from opencrux.pose_store import PoseStore


def _insert_session(db: Database, session_id: str) -> None:
    """Helper: insert a minimal session row to satisfy FK constraints."""
    db.execute(
        """INSERT INTO sessions
           (id, created_at, original_filename, session_json)
           VALUES (?, ?, ?, ?)""",
        (session_id, "2026-01-01T00:00:00", "test.mp4", "{}"),
    )
    db.commit()


class TestPoseStore:
    def test_store_frame_with_landmarks(self, tmp_path):
        db = Database(tmp_path / "test.db")
        _insert_session(db, "test-session")
        store = PoseStore(db)

        landmarks = [
            {"index": i, "x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}
            for i in range(33)
        ]
        frame_id = store.store_frame(
            session_id="test-session",
            frame_index=0,
            timestamp_seconds=0.0,
            centroid_x=0.5,
            centroid_y=0.5,
            visibility_ratio=0.85,
            visible_landmark_count=28,
            speed=0.02,
            detected_pose_count=1,
            landmarks=landmarks,
        )
        assert frame_id > 0

        stored = store.get_frame_landmarks(frame_id)
        assert len(stored) == 33
        assert stored[0]["x"] == 0.5
        db.close()

    def test_get_session_frames(self, tmp_path):
        db = Database(tmp_path / "test.db")
        _insert_session(db, "sess1")
        store = PoseStore(db)

        for i in range(5):
            store.store_frame(
                session_id="sess1",
                frame_index=i,
                timestamp_seconds=i * 0.16,
                centroid_x=0.5,
                centroid_y=0.5 - i * 0.05,
                visibility_ratio=0.85,
                visible_landmark_count=28,
                speed=0.02,
                detected_pose_count=1,
                landmarks=[
                    {"index": j, "x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}
                    for j in range(33)
                ],
            )

        frames = store.get_session_frames("sess1")
        assert len(frames) == 5
        assert frames[0]["frame_index"] == 0
        assert frames[4]["frame_index"] == 4
        db.close()

    def test_get_session_landmarks(self, tmp_path):
        db = Database(tmp_path / "test.db")
        _insert_session(db, "sess1")
        store = PoseStore(db)

        store.store_frame(
            session_id="sess1",
            frame_index=0,
            timestamp_seconds=0.0,
            centroid_x=0.5,
            centroid_y=0.5,
            visibility_ratio=0.85,
            visible_landmark_count=28,
            speed=0.02,
            detected_pose_count=1,
            landmarks=[
                {"index": j, "x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}
                for j in range(33)
            ],
        )

        all_landmarks = store.get_session_landmarks("sess1")
        assert len(all_landmarks) == 33
        assert all_landmarks[0]["landmark_index"] == 0
        db.close()


class TestLLMOutputStore:
    def test_store_llm_output(self, tmp_path):
        db = Database(tmp_path / "test.db")
        _insert_session(db, "test-session")
        store = PoseStore(db)

        row_id = store.store_llm_output(
            session_id="test-session",
            model_variant="gemma4:e4b",
            prompt_text="Analyze this climbing attempt...",
            response_text='{"movement_description": "Good footwork"}',
            attempt_index=1,
            output_type="attempt_analysis",
        )
        assert row_id > 0

        outputs = store.get_session_llm_outputs("test-session")
        assert len(outputs) == 1
        assert outputs[0]["model_variant"] == "gemma4:e4b"
        assert outputs[0]["attempt_index"] == 1
        db.close()


class TestScoreStore:
    def test_store_score(self, tmp_path):
        db = Database(tmp_path / "test.db")
        _insert_session(db, "test-session")
        store = PoseStore(db)

        row_id = store.store_score(
            session_id="test-session",
            overall_score=3.8,
            footwork=4.0,
            body_tension=3.5,
            route_reading=4.0,
            efficiency=3.5,
            difficulty_estimate="V3",
            route_name="White Heat",
            gym_name="Home Wall",
        )
        assert row_id > 0
        db.close()
