from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def get_db_path() -> Path:
    configured = os.getenv("AGENT_OS_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return BASE_DIR / "data" / "agent_os.db"


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ai_company_runs (
    run_id TEXT PRIMARY KEY,
    spec_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    overall_status TEXT NOT NULL,
    started_at TEXT,
    goal TEXT NOT NULL,
    decision_summary TEXT NOT NULL,
    meeting_status TEXT NOT NULL,
    artifact_score REAL,
    active_agent_count INTEGER NOT NULL DEFAULT 0,
    alerts_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL,
    synced_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()


@contextmanager
def get_db():
    connection = _connect()
    try:
        yield connection
    finally:
        connection.close()
