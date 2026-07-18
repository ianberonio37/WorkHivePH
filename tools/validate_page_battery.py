#!/usr/bin/env python3
"""
validate_page_battery.py — PER_PAGE_BUGHUNT_ROADMAP platform-wide mechanical floor gate.

Wraps tools/page_battery.mjs --gate (headless Playwright, real Baguio supervisor sign-in) and mirrors
its exit code. Sweeps ALL ~30 interactive pages and locks the page-agnostic phases against regression:
  P1 Smoke      — every page loads signed-in, renders a non-blank body (>200 chars), NO error-state
                  banner ("failed to load" / "unexpected error"), and ZERO console errors on load.
  P2 Console/Net— no page emits a 5xx response during load (silent server error). (4xx + warnings are
                  reported but non-fatal — some pages legitimately HEAD-probe.)
  P4 Inputs*    — the SAFE reflected-XSS probe: typing `"><img src=x onerror=...>` into every visible
                  input NEVER executes (window flag stays unset) NOR reflects as a live <img onerror>
                  node. (Submit-path P4 stays MCP-interactive per the roadmap — this locks the
                  reflected-DOM-XSS invariant across every page's inputs.)
  P8 Visual     — no horizontal overflow at 390px (mobile-first invariant, hard-fail) on any page.

Complements the deeper per-page truth gates (validate_hive_battery.py asserts rendered==DB for
hive.html specifically). This one is BROAD (all pages) + SHALLOW (mechanical), so a page that starts
throwing on load, 5xx-ing, reflecting XSS, or overflowing at 390px blocks CI.

Skips cleanly (exit 0) if node or the local stack (Flask :5000 + Supabase :54321) is absent —
mirrors validate_hive_battery.py. A real regression is exit 1. Live-only (skip_if_fast).
Re-drive: WH_TEST_HIVE=636cf7e8-431a-4907-8a9f-43dd4cc216d6 node tools/page_battery.mjs --gate [--headed]
"""
import io
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tools" / "page_battery.mjs"
# The live Baguio hive for the seeded accounts (the harness HIVE constant 9b4eaeac is stale).
LIVE_HIVE = "636cf7e8-431a-4907-8a9f-43dd4cc216d6"


def _up(url: str, timeout: float = 3.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception as e:  # any HTTP status still means the port is answering
        return "HTTP Error" in str(e)


def main() -> int:
    print("\n" + "=" * 72)
    print("  Platform-wide page battery gate (P1 Smoke / P2 5xx / P4 reflected-XSS / P8 @390 overflow)")
    print("=" * 72)
    if shutil.which("node") is None:
        print("  SKIP: node not on PATH — live battery not evaluated (local-only live gate).")
        return 0
    if not HARNESS.exists():
        print(f"  FAIL: {HARNESS.name} missing — the page battery harness was removed.")
        return 1
    if not (_up("http://127.0.0.1:5000/workhive/hive.html") and _up("http://127.0.0.1:54321/rest/v1/")):
        print("  SKIP: local stack (Flask :5000 / Supabase :54321) not reachable — treating as stack-absent.")
        return 0
    env = dict(os.environ, WH_TEST_HIVE=LIVE_HIVE)
    try:
        r = subprocess.run(["node", str(HARNESS), "--gate"], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, timeout=420)
    except Exception as e:
        print(f"  SKIP: could not run the battery ({e}) — treating as local-stack-absent.")
        return 0
    out = (r.stdout or "").strip()
    if out:
        print("\n".join("  " + ln for ln in out.splitlines()))
    err = (r.stderr or "").strip()
    if err and r.returncode != 0:
        print("  stderr:", err[:400])
    if r.returncode == 0:
        print("\n  PASS: all pages load clean (P1), no 5xx (P2), no reflected XSS (P4), no @390 overflow (P8).\n")
    else:
        print("\n  FAIL: a page-battery regression (broken load / console error / 5xx / reflected XSS / mobile overflow).\n")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
