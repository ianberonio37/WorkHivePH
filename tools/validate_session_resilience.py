#!/usr/bin/env python3
# DEEPWALK-CELL: * D19
r"""validate_session_resilience.py — D19 idle-session robustness (token-refresh, no stale 401).

THE CLASS (utils.js Finding #6, 2026-07-06): a tab left idle for hours has its scheduled
Supabase token-refresh timer suspended while backgrounded, so its first authed read on wake
fires on a STALE access token and silently 401s — leaving a broken "signed-in" dashboard that
looks logged in but every query fails. The fix is a SHARED mechanism carried by the singleton
Supabase client (`getSupabaseClient` / `window._whSupabaseClient` in utils.js), so EVERY page
that uses the singleton inherits it — which `validate_client_singleton.py` already enforces
platform-wide. Hence the `* D19` wildcard: the guarantee is one shared client, used everywhere.

THREE deterministic layers ($0, no browser/DB/model) over utils.js:
  1. REFRESH CONTRACT — the shared client is created with auth.autoRefreshToken:true AND
     persistSession:true (keeps the token fresh + restores it on reload).
  2. WAKE REFRESH — a `visibilitychange` handler proactively calls `getSession()` when the tab
     returns to the foreground (covers the "background timer never fired" case before the user's
     next action). Without it, autoRefreshToken alone still leaves the first-read-after-wake race.
  3. NO ROGUE CLIENT — no page/JS creates an ad-hoc `createClient(...)` with
     `autoRefreshToken: false` (an opt-out that would re-introduce the stale-401 for that surface).

Exit 0 = PASS, 1 = FAIL. No file is edited.
"""
from __future__ import annotations
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"
GRN, RED, YEL, BLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"


def main() -> int:
    fails: list[str] = []
    print(f"{BLD}SESSION RESILIENCE (D19) — idle/expired-session token-refresh is wired platform-wide{RST}")
    print("=" * 80)

    if not UTILS.is_file():
        print(f"{RED}FAIL{RST}: utils.js not found")
        return 1
    src = UTILS.read_text(encoding="utf-8", errors="replace")

    # 1. REFRESH CONTRACT — the shared singleton client opts INTO auto-refresh + persistence.
    #    Match the `auth: { ... }` option block of the singleton createClient call.
    auth_block = re.search(r"auth:\s*\{([^}]*)\}", src)
    ab = auth_block.group(1) if auth_block else ""
    if not re.search(r"autoRefreshToken:\s*true", ab):
        fails.append("shared Supabase client missing `auth.autoRefreshToken: true` "
                     "(idle tab's access token would go stale → silent 401)")
    if not re.search(r"persistSession:\s*true", ab):
        fails.append("shared Supabase client missing `auth.persistSession: true` "
                     "(session not restored on reload)")

    # 2. WAKE REFRESH — a visibilitychange handler that refreshes the session on foreground.
    vis = re.search(r"visibilitychange", src)
    wake_refresh = bool(vis) and bool(
        re.search(r"visibilitychange[\s\S]{0,400}?(?:getSession|refreshSession)\s*\(", src))
    if not wake_refresh:
        fails.append("no visibilitychange→getSession()/refreshSession() wake handler "
                     "(the background-timer-never-fired race after hours idle is unguarded)")

    # 3. NO ROGUE CLIENT — no createClient anywhere opts OUT of auto-refresh.
    rogue = []
    for path in sorted(ROOT.glob("*.js")):
        try:
            js = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"createClient\s*\([^;]*?autoRefreshToken:\s*false", js, re.S):
            rogue.append(path.name)
            break
    for name in rogue:
        fails.append(f"{name}: creates a Supabase client with autoRefreshToken:false "
                     f"(re-introduces the stale-session 401 for that surface)")

    print(f"  refresh contract: autoRefreshToken={'✓' if 'autoRefreshToken' not in ''.join(fails) else '✗'} · "
          f"wake-refresh handler: {'✓' if wake_refresh else '✗'} · rogue no-refresh clients: {len(rogue)}")

    if fails:
        print(f"\n{RED}FAIL{RST}: {len(fails)} D19 session-resilience breach(es):")
        for f in fails:
            print(f"  {RED}✗{RST} {f}")
        return 1
    print(f"\n{GRN}PASS{RST}: the shared singleton client auto-refreshes + persists the session and "
          f"refreshes on tab-wake; no surface opts out → every page inherits idle-session robustness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
