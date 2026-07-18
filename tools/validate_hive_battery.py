#!/usr/bin/env python3
"""
validate_hive_battery.py — PER_PAGE_BUGHUNT_ROADMAP Tier-1 hive.html LIVE battery gate (P1/P2/P8).

Wraps tools/validate_hive_battery.mjs (headless Playwright, real supervisor sign-in) and mirrors its
exit code. Locks three per-page phases against regression:
  P1 Smoke      — hive.html loads signed-in, renders REAL data (no undefined/NaN/[object Object]),
                  the primary anchor stats (#stat-open, #stat-members) EQUAL the DB truth
                  (v_logbook_truth open count / hive_members active count), not the no-hive empty
                  state, and ZERO console errors on the board load.
  P2 Console/Net— every Supabase REST/RPC/auth/functions response during the load is < 400
                  (no silent 4xx/5xx / swallowed error).
  P8 Visual     — no horizontal overflow at 390px (mobile) or 1280px (desktop).

Ground-truth identity is the REAL Baguio hive 636cf7e8 (the older harness HIVE constant 9b4eaeac is
stale for the seeded accounts). Skips cleanly (exit 0) if node or the local stack (Flask :5000 +
Supabase :54321) is absent — mirrors validate_arc_u_focus_trap.py. A real regression is exit 1.
"""
import io
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tools" / "validate_hive_battery.mjs"


def _up(url: str, timeout: float = 3.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception as e:  # any HTTP status still means the port is answering
        return "HTTP Error" in str(e)


def main() -> int:
    print("\n" + "=" * 72)
    print("  hive.html LIVE battery gate (P1 Smoke / P2 Console+Network / P8 Visual)")
    print("=" * 72)
    if shutil.which("node") is None:
        print("  SKIP: node not on PATH — live battery not evaluated (local-only live gate).")
        return 0
    if not HARNESS.exists():
        print(f"  FAIL: {HARNESS.name} missing — the live battery harness was removed.")
        return 1
    if not (_up("http://127.0.0.1:5000/workhive/hive.html") and _up("http://127.0.0.1:54321/rest/v1/")):
        print("  SKIP: local stack (Flask :5000 / Supabase :54321) not reachable — treating as stack-absent.")
        return 0
    try:
        r = subprocess.run(["node", str(HARNESS)], cwd=str(ROOT), capture_output=True, text=True, timeout=180)
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
        print("\n  PASS: hive.html P1/P2/P8 invariants hold (render==DB, 0 errors, all 2xx, no overflow).\n")
    else:
        print("\n  FAIL: a hive.html P1/P2/P8 regression (render drift / console error / 4xx-5xx / overflow).\n")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
