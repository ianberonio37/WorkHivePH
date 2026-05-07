"""
Claude Token Tracker
Wraps the Anthropic SDK. Every call is logged to SQLite with action type,
model, tokens, cost, and timing. Feed this data into claude_model_router.py.

Usage:
    from tools.claude_token_tracker import TrackedClient

    client = TrackedClient()

    # Auto-classifies action from the prompt text
    response = client.chat("Fix the null-pointer bug in inventory.py", action_type="debugging")

    # Or let it classify automatically
    response = client.chat("Explain how RLS works")
"""

import time
import sqlite3
from datetime import datetime, timezone

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".claude" / "workhive_tokens.db"

MODEL_PRICING = {
    "claude-opus-4-7":   {"input": 5.00,  "output": 25.00, "cache_read": 0.50,  "cache_write": 6.25},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00, "cache_read": 0.30,  "cache_write": 3.75},
    "claude-haiku-4-5":  {"input": 1.00,  "output": 5.00,  "cache_read": 0.10,  "cache_write": 1.25},
}

# Keyword → action type mapping (first match wins)
ACTION_KEYWORDS = {
    "validation":  ["validate", "verify", "assert", "check that", "confirm that", "does it pass"],
    "search":      ["find", "search", "where is", "which file", "locate", "grep", "list all"],
    "code_edit":   ["edit", "modify", "change", "update the code", "replace", "rename", "refactor"],
    "explanation": ["explain", "what is", "how does", "describe", "why does", "what does"],
    "planning":    ["plan", "design", "architect", "roadmap", "strategy", "how should"],
    "debugging":   ["fix", "bug", "error", "broken", "debug", "crash", "fail", "exception"],
    "review":      ["review", "audit", "check the", "look at", "assess", "evaluate"],
    "build":       ["build", "create", "implement", "add feature", "new page", "generate"],
}


def _classify(prompt: str) -> str:
    p = prompt.lower()
    for action, keywords in ACTION_KEYWORDS.items():
        if any(kw in p for kw in keywords):
            return action
    return "general"


def _cost(model: str, input_t: int, output_t: int, cache_read: int = 0, cache_write: int = 0) -> float:
    p = MODEL_PRICING.get(model, MODEL_PRICING["claude-opus-4-7"])
    return (
        input_t     * p["input"]        / 1_000_000 +
        output_t    * p["output"]       / 1_000_000 +
        cache_read  * p["cache_read"]   / 1_000_000 +
        cache_write * p["cache_write"]  / 1_000_000
    )


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            action_type     TEXT    NOT NULL,
            model           TEXT    NOT NULL,
            input_tokens    INTEGER NOT NULL,
            output_tokens   INTEGER NOT NULL,
            cache_read      INTEGER NOT NULL DEFAULT 0,
            cache_write     INTEGER NOT NULL DEFAULT 0,
            total_tokens    INTEGER NOT NULL,
            cost_usd        REAL    NOT NULL,
            duration_ms     INTEGER NOT NULL,
            prompt_preview  TEXT,
            success         INTEGER NOT NULL DEFAULT 1,
            notes           TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_action ON token_usage(action_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts    ON token_usage(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON token_usage(model)")
    conn.commit()
    return conn


class TrackedClient:
    """
    Drop-in Anthropic wrapper that logs every call.

    Args:
        api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
        default_model: Model to use when not specified. Defaults to Opus 4.7.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: str = "claude-opus-4-7"):
        if _anthropic is None:
            raise ImportError("pip install anthropic  to make live API calls")
        self._client = _anthropic.Anthropic(api_key=api_key) if api_key else _anthropic.Anthropic()
        self.default_model = default_model

    def chat(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        action_type: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: int = 8192,
        notes: Optional[str] = None,
        **kwargs,
    ) -> "object":  # anthropic.types.Message when anthropic is installed
        """
        Send a single-turn message and record usage.

        Args:
            prompt:      The user message.
            model:       Override model (defaults to self.default_model).
            action_type: Label for this call type. Auto-detected if not provided.
            system:      System prompt.
            max_tokens:  Max output tokens.
            notes:       Optional free-text to attach to the log row.
            **kwargs:    Passed to messages.create().
        """
        chosen_model = model or self.default_model
        action = action_type or _classify(prompt)

        messages = [{"role": "user", "content": prompt}]
        create_kwargs = dict(
            model=chosen_model,
            max_tokens=max_tokens,
            messages=messages,
            **kwargs,
        )
        if system:
            create_kwargs["system"] = system

        t0 = time.monotonic()
        try:
            response = self._client.messages.create(**create_kwargs)
            success = 1
        except Exception:
            success = 0
            raise
        finally:
            elapsed_ms = int((time.monotonic() - t0) * 1000)

        usage = response.usage
        inp   = usage.input_tokens
        out   = usage.output_tokens
        cr    = getattr(usage, "cache_read_input_tokens",    0) or 0
        cw    = getattr(usage, "cache_creation_input_tokens", 0) or 0
        total = inp + out
        cost  = _cost(chosen_model, inp, out, cr, cw)

        conn = _get_db()
        conn.execute(
            """
            INSERT INTO token_usage
                (timestamp, action_type, model, input_tokens, output_tokens,
                 cache_read, cache_write, total_tokens, cost_usd,
                 duration_ms, prompt_preview, success, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                action,
                chosen_model,
                inp, out, cr, cw, total,
                round(cost, 8),
                elapsed_ms,
                prompt[:200],
                success,
                notes,
            ),
        )
        conn.commit()
        conn.close()

        return response

    def log_raw(
        self,
        *,
        action_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
        duration_ms: int = 0,
        prompt_preview: str = "",
        success: int = 1,
        notes: Optional[str] = None,
    ) -> None:
        """
        Manually insert a usage record (for calls you made outside this wrapper,
        e.g. from edge functions that already completed).
        """
        total = input_tokens + output_tokens
        cost  = _cost(model, input_tokens, output_tokens, cache_read, cache_write)
        conn  = _get_db()
        conn.execute(
            """
            INSERT INTO token_usage
                (timestamp, action_type, model, input_tokens, output_tokens,
                 cache_read, cache_write, total_tokens, cost_usd,
                 duration_ms, prompt_preview, success, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                action_type, model,
                input_tokens, output_tokens, cache_read, cache_write,
                total, round(cost, 8), duration_ms,
                prompt_preview[:200], success, notes,
            ),
        )
        conn.commit()
        conn.close()


def get_all_stats() -> list[dict]:
    """Return per-action-type aggregated stats (used by router and dashboard)."""
    conn = _get_db()
    rows = conn.execute("""
        SELECT
            action_type,
            COUNT(*)                                    AS sample_count,
            ROUND(AVG(total_tokens), 0)                 AS avg_total_tokens,
            ROUND(AVG(input_tokens), 0)                 AS avg_input_tokens,
            ROUND(AVG(output_tokens), 0)                AS avg_output_tokens,
            MAX(total_tokens)                           AS max_total_tokens,
            ROUND(SUM(cost_usd), 6)                     AS total_cost_usd,
            ROUND(AVG(cost_usd) * 1000, 6)              AS avg_cost_per_1k_calls_usd,
            ROUND(AVG(duration_ms), 0)                  AS avg_duration_ms,
            model,
            ROUND(100.0 * SUM(success) / COUNT(*), 1)   AS success_rate_pct,
            MIN(timestamp)                              AS first_seen,
            MAX(timestamp)                              AS last_seen
        FROM token_usage
        GROUP BY action_type, model
        ORDER BY action_type, sample_count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_calls(limit: int = 50) -> list[dict]:
    conn = _get_db()
    rows = conn.execute(
        """SELECT * FROM token_usage ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
