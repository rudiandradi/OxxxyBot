# src/app/storage.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Tuple

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "oxxxybot.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS favs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            text       TEXT    NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS favs_user_idx ON favs(user_id, created_at DESC);")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS favs_user_text_uniq ON favs(user_id, text);")
        conn.commit()

def add_fav(user_id: int, text: str) -> bool:
    """True — добавили новый; False — уже был."""
    with _connect() as conn:
        try:
            conn.execute("INSERT INTO favs (user_id, text) VALUES (?, ?)", (user_id, text))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def list_favs(user_id: int, limit: int = 50) -> list[str]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT text
            FROM favs
            WHERE user_id=?
            ORDER BY created_at DESC, id DESC
            LIMIT ?;
        """, (user_id, limit))
        return [row[0] for row in cur.fetchall()]

def list_fav_rows(user_id: int, limit: int = 1000000) -> List[Tuple[int, str]]:
    """Вернёт (id, text) — удобно для точечного удаления."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, text
            FROM favs
            WHERE user_id=?
            ORDER BY created_at DESC, id DESC
            LIMIT ?;
        """, (user_id, limit))
        return [(row[0], row[1]) for row in cur.fetchall()]

def delete_fav(user_id: int, fav_id: int) -> bool:
    """Удалит один элемент пользователя по id. True — если удалён."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM favs WHERE user_id=? AND id=?", (user_id, fav_id))
        conn.commit()
        return cur.rowcount > 0

def clear_favs(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM favs WHERE user_id=?", (user_id,))
        conn.commit()