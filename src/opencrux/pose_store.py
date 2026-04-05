"""Per-frame pose landmark storage and retrieval."""
from __future__ import annotations

from typing import Any

from .db import Database


class PoseStore:
    """Stores and retrieves per-frame pose landmark data."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def store_frame(
        self,
        *,
        session_id: str,
        frame_index: int,
        timestamp_seconds: float,
        centroid_x: float,
        centroid_y: float,
        visibility_ratio: float,
        visible_landmark_count: int,
        speed: float,
        detected_pose_count: int,
        landmarks: list[dict[str, Any]],
        attempt_index: int | None = None,
    ) -> int:
        """Store a frame observation with full landmark data. Returns frame row ID."""
        cursor = self._db.execute(
            """INSERT INTO frames
               (session_id, frame_index, timestamp_seconds, centroid_x, centroid_y,
                visibility_ratio, visible_landmark_count, speed, detected_pose_count, attempt_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, frame_index, timestamp_seconds, centroid_x, centroid_y,
             visibility_ratio, visible_landmark_count, speed, detected_pose_count, attempt_index),
        )
        frame_id = cursor.lastrowid

        if landmarks:
            self._db.executemany(
                """INSERT INTO landmarks (frame_id, landmark_index, x, y, z, visibility)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (frame_id, lm["index"], lm["x"], lm["y"], lm["z"], lm["visibility"])
                    for lm in landmarks
                ],
            )

        self._db.commit()
        return frame_id

    def get_frame_landmarks(self, frame_id: int) -> list[dict[str, Any]]:
        """Get all landmarks for a specific frame."""
        rows = self._db.execute(
            "SELECT landmark_index, x, y, z, visibility FROM landmarks WHERE frame_id = ? ORDER BY landmark_index",
            (frame_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_session_frames(self, session_id: str) -> list[dict[str, Any]]:
        """Get all frame observations for a session, ordered by frame index."""
        rows = self._db.execute(
            """SELECT id, frame_index, timestamp_seconds, centroid_x, centroid_y,
                      visibility_ratio, visible_landmark_count, speed, detected_pose_count, attempt_index
               FROM frames WHERE session_id = ? ORDER BY frame_index""",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_session_landmarks(self, session_id: str) -> list[dict[str, Any]]:
        """Get all landmarks for all frames in a session."""
        rows = self._db.execute(
            """SELECT f.frame_index, f.timestamp_seconds, l.landmark_index, l.x, l.y, l.z, l.visibility
               FROM landmarks l
               JOIN frames f ON l.frame_id = f.id
               WHERE f.session_id = ?
               ORDER BY f.frame_index, l.landmark_index""",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def store_llm_output(
        self,
        *,
        session_id: str,
        model_variant: str,
        prompt_text: str,
        response_text: str,
        attempt_index: int | None = None,
        output_type: str = "attempt_analysis",
    ) -> int:
        """Store an LLM prompt/response pair for training data."""
        from .models import utc_now
        cursor = self._db.execute(
            """INSERT INTO llm_outputs
               (session_id, model_variant, created_at, prompt_text, response_text, attempt_index, output_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, model_variant, utc_now().isoformat(), prompt_text, response_text, attempt_index, output_type),
        )
        self._db.commit()
        return cursor.lastrowid

    def get_session_llm_outputs(self, session_id: str) -> list[dict]:
        """Get all LLM outputs for a session."""
        rows = self._db.execute(
            """SELECT model_variant, created_at, prompt_text, response_text, attempt_index, output_type
               FROM llm_outputs WHERE session_id = ? ORDER BY id""",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def store_score(
        self,
        *,
        session_id: str,
        overall_score: float,
        footwork: float | None = None,
        body_tension: float | None = None,
        route_reading: float | None = None,
        efficiency: float | None = None,
        hip_positioning: float | None = None,
        grip_technique: float | None = None,
        difficulty_estimate: str | None = None,
        route_name: str | None = None,
        gym_name: str | None = None,
    ) -> int:
        """Store a score record for historical tracking."""
        from .models import utc_now
        cursor = self._db.execute(
            """INSERT INTO scores
               (session_id, created_at, overall_score, footwork, body_tension,
                route_reading, efficiency, hip_positioning, grip_technique,
                difficulty_estimate, route_name, gym_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, utc_now().isoformat(), overall_score, footwork, body_tension,
             route_reading, efficiency, hip_positioning, grip_technique,
             difficulty_estimate, route_name, gym_name),
        )
        self._db.commit()
        return cursor.lastrowid
