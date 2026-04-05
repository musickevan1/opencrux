"""SQLite database layer for structured climbing data storage."""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_video_path TEXT,
    route_name TEXT,
    gym_name TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    error_message TEXT,
    processed_frame_count INTEGER DEFAULT 0,
    sampled_fps REAL DEFAULT 0.0,
    source_duration_seconds REAL DEFAULT 0.0,
    session_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    frame_index INTEGER NOT NULL,
    timestamp_seconds REAL NOT NULL,
    centroid_x REAL NOT NULL,
    centroid_y REAL NOT NULL,
    visibility_ratio REAL NOT NULL,
    visible_landmark_count INTEGER NOT NULL,
    speed REAL DEFAULT 0.0,
    detected_pose_count INTEGER DEFAULT 1,
    attempt_index INTEGER,
    UNIQUE(session_id, frame_index)
);

CREATE TABLE IF NOT EXISTS landmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id INTEGER NOT NULL REFERENCES frames(id),
    landmark_index INTEGER NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    visibility REAL NOT NULL,
    UNIQUE(frame_id, landmark_index)
);

CREATE TABLE IF NOT EXISTS llm_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    model_variant TEXT NOT NULL,
    created_at TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    attempt_index INTEGER,
    output_type TEXT NOT NULL DEFAULT 'attempt_analysis'
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    created_at TEXT NOT NULL,
    overall_score REAL NOT NULL,
    footwork REAL,
    body_tension REAL,
    route_reading REAL,
    efficiency REAL,
    hip_positioning REAL,
    grip_technique REAL,
    difficulty_estimate TEXT,
    route_name TEXT,
    gym_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_frames_session ON frames(session_id);
CREATE INDEX IF NOT EXISTS idx_landmarks_frame ON landmarks(frame_id);
CREATE INDEX IF NOT EXISTS idx_llm_session ON llm_outputs(session_id);
CREATE INDEX IF NOT EXISTS idx_scores_created ON scores(created_at);
"""


class Database:
    """SQLite database for structured climbing analytics storage."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_seq) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params_seq)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
