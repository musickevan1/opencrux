"""Training data export in JSONL format for fine-tuning."""
from __future__ import annotations

import json
from pathlib import Path

from .db import Database
from .pose_store import PoseStore


def export_session_jsonl(db: Database, session_id: str, output_path: Path) -> None:
    """Export a single session as a JSONL record with all pose and LLM data."""
    store = PoseStore(db)

    session_row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session_row is None:
        raise ValueError(f"Session {session_id} not found")

    frames = store.get_session_frames(session_id)
    for frame in frames:
        frame["landmarks"] = store.get_frame_landmarks(frame["id"])

    llm_outputs = store.get_session_llm_outputs(session_id)

    record = {
        "session_id": session_id,
        "created_at": session_row["created_at"],
        "original_filename": session_row["original_filename"],
        "route_name": session_row["route_name"],
        "gym_name": session_row["gym_name"],
        "source_duration_seconds": session_row["source_duration_seconds"],
        "session_analysis": json.loads(session_row["session_json"]) if session_row["session_json"] else {},
        "frames": frames,
        "llm_outputs": llm_outputs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def export_all_sessions_jsonl(db: Database, output_path: Path) -> int:
    """Export all sessions to a single JSONL file. Returns count exported."""
    rows = db.execute("SELECT id FROM sessions ORDER BY created_at").fetchall()
    for row in rows:
        export_session_jsonl(db, row["id"], output_path)
    return len(rows)
