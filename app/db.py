"""SQLite 상태 저장. 세션(스레드) 하나 = 후보 목록 하나. 승인 이력으로 중복 추천 방지."""
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    root_post_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,           -- awaiting_approval | done | cancelled
    candidates_json TEXT NOT NULL,  -- 점수화된 후보 리스트 (그대로 JSON)
    chosen_handle TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_programs (
    handle TEXT PRIMARY KEY,
    last_status TEXT NOT NULL,      -- suggested | approved | skipped
    updated_at REAL NOT NULL
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)


def create_session(root_post_id: str, channel_id: str, user_id: str, candidates: list[dict]) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (root_post_id, channel_id, user_id, status, candidates_json, created_at) "
            "VALUES (?, ?, ?, 'awaiting_approval', ?, ?)",
            (root_post_id, channel_id, user_id, json.dumps(candidates), time.time()),
        )
        for c in candidates:
            conn.execute(
                "INSERT INTO seen_programs (handle, last_status, updated_at) VALUES (?, 'suggested', ?) "
                "ON CONFLICT(handle) DO UPDATE SET last_status='suggested', updated_at=excluded.updated_at",
                (c["handle"], time.time()),
            )


def get_session(root_post_id: str) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE root_post_id = ?", (root_post_id,)
        ).fetchone()


def close_session(root_post_id: str, status: str, chosen_handle: str | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET status = ?, chosen_handle = ? WHERE root_post_id = ?",
            (status, chosen_handle, root_post_id),
        )
        if chosen_handle:
            conn.execute(
                "UPDATE seen_programs SET last_status = 'approved', updated_at = ? WHERE handle = ?",
                (time.time(), chosen_handle),
            )


def get_seen_handles() -> set[str]:
    with _conn() as conn:
        rows = conn.execute("SELECT handle FROM seen_programs").fetchall()
        return {r["handle"] for r in rows}
