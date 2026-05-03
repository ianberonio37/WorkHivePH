"""Persist gate run history and streak data to .tmp/.

run_history.json — list of recent runs (oldest first), trimmed to MAX_HISTORY.
streak.json      — current streak, best streak, last green date/commit.

Both are gitignored (.tmp/) and per-machine.
"""
import json
from pathlib import Path

_TMP = Path(__file__).resolve().parent.parent / ".tmp"
_TMP.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = _TMP / "run_history.json"
STREAK_FILE  = _TMP / "streak.json"

MAX_HISTORY = 50  # keep the last N runs


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def append_run(run_record: dict):
    history = load_history()
    history.append(run_record)
    history = history[-MAX_HISTORY:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


def load_streak() -> dict:
    if not STREAK_FILE.exists():
        return {
            "current_streak": 0,
            "best_streak": 0,
            "last_green_date": None,
            "last_green_commit": None,
            "last_run_date": None,
            "last_run_verdict": None,
            "broken_at": None,
            "broken_after_days": None,
        }
    try:
        return json.loads(STREAK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"current_streak": 0, "best_streak": 0}


def save_streak(streak: dict):
    STREAK_FILE.write_text(json.dumps(streak, indent=2), encoding="utf-8")


def latest_run() -> dict | None:
    history = load_history()
    return history[-1] if history else None
