"""
铁路票缓存服务：内存缓存 + SQLite 持久化，TTL=7天
内存缓存热路径，SQLite 保底持久化。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "train_cache.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CACHE_TTL = 7 * 24 * 3600  # 7天
_lock = threading.Lock()
_mem: dict[tuple, dict] = {}  # 内存缓存 (origin, dest, date) -> data


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS train_cache (
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                date TEXT NOT NULL,
                data TEXT NOT NULL,
                fetched_at INTEGER NOT NULL,
                PRIMARY KEY (origin, destination, date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fetched ON train_cache(fetched_at)")
        conn.commit()
        conn.close()
        # 启动时把 SQLite 数据预热进内存
        _warmup_from_db()


def _warmup_from_db():
    """启动时从 SQLite 加载有效缓存到内存"""
    try:
        conn = _get_conn()
        now = int(time.time())
        rows = conn.execute(
            "SELECT origin, destination, date, data, fetched_at FROM train_cache WHERE ? - fetched_at < ?",
            (now, CACHE_TTL)
        ).fetchall()
        conn.close()
        for row in rows:
            key = (row["origin"], row["destination"], row["date"])
            _mem[key] = json.loads(row["data"])
    except Exception:
        pass


def get_cached(origin: str, destination: str, date: str) -> Optional[dict]:
    key = (origin, destination, date)
    # 先查内存
    with _lock:
        if key in _mem:
            return _mem[key]
    # 内存未命中，查 SQLite
    with _lock:
        try:
            conn = _get_conn()
            row = conn.execute(
                "SELECT data, fetched_at FROM train_cache WHERE origin=? AND destination=? AND date=?",
                (origin, destination, date)
            ).fetchone()
            conn.close()
            if row:
                age = time.time() - row["fetched_at"]
                if age < CACHE_TTL:
                    data = json.loads(row["data"])
                    _mem[key] = data  # 回填内存
                    return data
                else:
                    with _lock:
                        conn2 = _get_conn()
                        conn2.execute(
                            "DELETE FROM train_cache WHERE origin=? AND destination=? AND date=?",
                            (origin, destination, date)
                        )
                        conn2.commit()
                        conn2.close()
        except Exception:
            pass
    return None


def set_cached(origin: str, destination: str, date: str, data: dict):
    key = (origin, destination, date)
    with _lock:
        _mem[key] = data  # 写内存
    # 写 SQLite
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO train_cache (origin, destination, date, data, fetched_at) VALUES (?, ?, ?, ?, ?)",
            (origin, destination, date, json.dumps(data, ensure_ascii=False), int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_stats() -> dict:
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM train_cache").fetchone()[0]
        now = int(time.time())
        expired = conn.execute(
            "SELECT COUNT(*) FROM train_cache WHERE ? - fetched_at > ?",
            (now, CACHE_TTL)
        ).fetchone()[0]
        oldest = conn.execute("SELECT MIN(fetched_at) FROM train_cache").fetchone()[0]
        conn.close()
        return {
            "total": total,
            "mem_keys": len(_mem),
            "expired": expired,
            "oldest_days_ago": round((time.time() - oldest) / 86400, 1) if oldest else 0,
            "ttl_days": 7,
            "db_path": str(DB_PATH),
        }
    except Exception:
        return {"error": "db not ready"}


# 启动时初始化
init_db()
