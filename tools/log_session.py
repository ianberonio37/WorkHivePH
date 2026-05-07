"""
Claude Code Stop hook — logs each session to the token DB.
Called automatically by Claude Code when a session ends.
Receives session JSON via stdin.

Registered in: C:\Users\ILBeronio\.claude\settings.json
"""
import sys
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "workhive_tokens.db"


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    session_id  = data.get("session_id", "unknown")
    model       = data.get("model", "unknown")
    timestamp   = datetime.now(timezone.utc).isoformat()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            session_id  TEXT,
            model       TEXT,
            raw_event   TEXT
        )
    """)
    conn.execute(
        "INSERT INTO sessions (timestamp, session_id, model, raw_event) VALUES (?,?,?,?)",
        (timestamp, session_id, model, raw[:2000] if (raw := json.dumps(data)) else ""),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
