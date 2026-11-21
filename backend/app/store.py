"""SQLite history: daily scores, applied fixes, minutes saved, streak."""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from contextlib import closing

DB_PATH = os.environ.get("MP_DB", os.path.join(os.path.dirname(__file__), "..", "morning_pulse.db"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with closing(_conn()) as c, c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS checkups(
            id INTEGER PRIMARY KEY, ts TEXT NOT NULL, day TEXT NOT NULL,
            score INTEGER NOT NULL, results TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fixes(
            id INTEGER PRIMARY KEY, ts TEXT NOT NULL, check_id TEXT NOT NULL,
            fix_id TEXT NOT NULL, ok INTEGER NOT NULL, minutes_per_week REAL NOT NULL, message TEXT);
        """)


def save_checkup(score: int, results: list[dict]) -> None:
    now = dt.datetime.now()
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO checkups(ts, day, score, results) VALUES(?,?,?,?)",
                  (now.isoformat(timespec="seconds"), now.date().isoformat(), score, json.dumps(results)))


def save_fix(check_id: str, fix_id: str, ok: bool, minutes: float, message: str) -> None:
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO fixes(ts, check_id, fix_id, ok, minutes_per_week, message) VALUES(?,?,?,?,?,?)",
                  (dt.datetime.now().isoformat(timespec="seconds"), check_id, fix_id, int(ok), minutes, message))


def stats() -> dict:
    today = dt.date.today()
    week_start = (today - dt.timedelta(days=today.weekday())).isoformat()
    with closing(_conn()) as c:
        minutes_week = c.execute(
            "SELECT COALESCE(SUM(minutes_per_week),0) FROM fixes WHERE ok=1 AND ts>=?", (week_start,)
        ).fetchone()[0]
        minutes_total = c.execute("SELECT COALESCE(SUM(minutes_per_week),0) FROM fixes WHERE ok=1").fetchone()[0]
        days = {r[0] for r in c.execute("SELECT DISTINCT day FROM checkups")}
        history = [dict(r) for r in c.execute(
            "SELECT day, MAX(score) AS score FROM checkups GROUP BY day ORDER BY day DESC LIMIT 7")]
        prev = c.execute("SELECT score FROM checkups WHERE day<? ORDER BY ts DESC LIMIT 1",
                         (today.isoformat(),)).fetchone()

    streak, d = 0, today
    while d.isoformat() in days:
        streak += 1
        d -= dt.timedelta(days=1)

    return {
        "minutes_saved_week": round(minutes_week),
        "minutes_saved_total": round(minutes_total),
        "streak_days": streak,
        "yesterday_score": prev[0] if prev else None,
        "history": list(reversed(history)),
    }
