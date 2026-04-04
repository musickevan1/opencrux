from __future__ import annotations

from pathlib import Path

from .models import SessionAnalysis


class SessionStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_id: str) -> Path:
        return self.base_path / f"{session_id}.json"

    def save(self, session: SessionAnalysis) -> SessionAnalysis:
        self._path_for(session.id).write_text(session.model_dump_json(indent=2), encoding="utf-8")
        return session

    def get(self, session_id: str) -> SessionAnalysis | None:
        path = self._path_for(session_id)
        if not path.exists():
            return None
        return SessionAnalysis.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self, limit: int = 10) -> list[SessionAnalysis]:
        sessions: list[SessionAnalysis] = []
        for path in self.base_path.glob("*.json"):
            sessions.append(SessionAnalysis.model_validate_json(path.read_text(encoding="utf-8")))

        sessions.sort(key=lambda session: session.created_at, reverse=True)
        return sessions[:limit]
