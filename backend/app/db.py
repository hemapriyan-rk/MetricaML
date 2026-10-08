"""SQLite access. Plain sqlite3 is plenty for a single-instance deployment."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    n_rows INTEGER NOT NULL,
    n_cols INTEGER NOT NULL,
    profile_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dataset_id INTEGER REFERENCES datasets(id) ON DELETE SET NULL,
    dataset_name TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    algorithm_label TEXT NOT NULL,
    problem_type TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    stages_json TEXT NOT NULL DEFAULT '[]',
    config_json TEXT NOT NULL,
    primary_metric TEXT,
    primary_value REAL,
    error TEXT,
    host_json TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    duration_s REAL
);
CREATE INDEX IF NOT EXISTS idx_experiments_user ON experiments(user_id, id DESC);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    config.ensure_dirs()
    with db() as conn:
        conn.executescript(SCHEMA)


def row_to_experiment(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["stages"] = json.loads(d.pop("stages_json") or "[]")
    d["config"] = json.loads(d.pop("config_json") or "{}")
    d["host"] = json.loads(d.pop("host_json")) if d.get("host_json") else None
    d.pop("host_json", None)
    return d
