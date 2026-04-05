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
