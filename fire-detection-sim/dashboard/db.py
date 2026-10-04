"""Tiny SQLite storage = the 'Database' box in the container diagram."""
import sqlite3
import threading
import time
from contextlib import contextmanager

import config

_lock = threading.Lock()


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(config.DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init():
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS readings(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts REAL, recv_ts REAL, seq INTEGER,
              smoke INTEGER, flame INTEGER,
              fire INTEGER, siren INTEGER, pump INTEGER, buffered INTEGER);
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts REAL, kind TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            """
        )


def set_meta(key, value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, str(value)))


def get_meta(key, default=None):
    with conn() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def add_reading(ts, seq, smoke, flame, fire, siren, pump, buffered):
    with conn() as c:
        c.execute(
            "INSERT INTO readings(ts,recv_ts,seq,smoke,flame,fire,siren,pump,buffered)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (ts, time.time(), seq, smoke, flame, fire, siren, pump, buffered),
        )


def add_event(kind, detail="", ts=None):
    with conn() as c:
        c.execute(
            "INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
            (ts or time.time(), kind, detail),
        )


def latest():
    """Most recently RECEIVED reading."""
    with conn() as c:
        r = c.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def recent(n=300):
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM readings ORDER BY ts DESC, id DESC LIMIT ?", (n,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def events(n=50):
    with conn() as c:
        rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [dict(r) for r in rows]


def last_event_id(kind):
    with conn() as c:
        r = c.execute("SELECT MAX(id) AS m FROM events WHERE kind=?", (kind,)).fetchone()
    return r["m"] or 0


def clear():
    with conn() as c:
        c.executescript("DELETE FROM readings; DELETE FROM events; DELETE FROM meta;")
