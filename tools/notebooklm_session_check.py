"""Fast session validity check for the WorkHive launcher.

Exit codes:
    0  Session file exists AND a minimal API call succeeds (session valid).
    1  Session file missing (never logged in, or file deleted).
    2  Session file exists but is rejected by Google (expired/invalid).
    3  Library not installed or other import error.
    4  Session is VALID but the account is rate-limited / quota-exhausted.
       (Don't force re-login in this case — wait, not re-auth.)

Used by video_marketing.bat to decide whether to auto-launch the
notebooklm_login.bat flow before starting Flask, and by the dashboard's
session-check polling. Keep the work here minimal so launcher startup
stays under ~2 seconds when session is OK.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _stdout_utf8() -> None:
    # Windows cp1252 stdout will choke on the lib's status lines.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _session_path() -> Path:
    override = os.getenv("NOTEBOOKLM_STORAGE_STATE")
    if override:
        return Path(override)
    return Path.home() / ".notebooklm" / "profiles" / "default" / "storage_state.json"


async def _verify_with_api() -> int:
    """Try a minimal API call to confirm the session is still accepted by Google."""
    try:
        from notebooklm import NotebookLMClient
    except ImportError as exc:
        print(f"  [check] notebooklm library not installed: {exc}", file=sys.stderr)
        return 3

    sp = _session_path()
    if not sp.exists() or sp.stat().st_size == 0:
        print(f"  [check] no session file at {sp}", file=sys.stderr)
        return 1

    try:
        async with await NotebookLMClient.from_storage(path=str(sp)) as client:
            # Cheapest call we can make — list notebooks (1 round-trip).
            # Verified method name against notebooklm-py 0.4.1:
            # `client.notebooks.list()` (NOT `list_notebooks()`).
            await client.notebooks.list()
        return 0
    except Exception as exc:
        msg = str(exc).lower()
        # Genuine auth failure — re-login required.
        if any(t in msg for t in ("authentication expired", "redirected to", "signin/accountchooser", "session expired", "invalid auth")):
            print(f"  [check] session rejected by Google: {type(exc).__name__}", file=sys.stderr)
            return 2
        # Quota / rate-limit — session is fine, just throttled. Don't push
        # the user into a re-login they don't need; wait or change profile.
        if any(t in msg for t in ("rate limit", "quota exceeded", "too many", "429", "user_displayable_error")):
            print(f"  [check] session valid but rate-limited: {type(exc).__name__}", file=sys.stderr)
            return 4
        # Library/network issue — log it but don't classify as expired,
        # since wrongly nudging the user to re-login (which they JUST did)
        # is worse than leaving the original error visible. The campaign
        # path will surface a more specific error if needed.
        print(f"  [check] session validation raised: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5


def main() -> int:
    _stdout_utf8()
    return asyncio.run(_verify_with_api())


if __name__ == "__main__":
    sys.exit(main())
