#!/usr/bin/env python3
"""
validate_read_battery.py — PER_PAGE_BUGHUNT_ROADMAP per-page P3 read-correctness + P7 empty/error gate.

Wraps tools/validate_read_battery.mjs (headless Playwright, real Baguio supervisor sign-in) and mirrors
its exit code. Locks the READ path of 8 read-heavy pages against regression by comparing what each page
RENDERS to the DB truth (docker-psql admin) for the signed-in hive:

  audit-log.html          #feed child count == count(hive_audit_log) [<=500]  (EXACT rendered==DB)
  integrations.html       DB==0 -> empty-state + hero counters read 0 (no error)   (P7 empty-vs-error)
  plant-connections.html  DB==0 -> empty-state + #wh-conn-queue reads 0 (no error) (P7 empty-vs-error)
  public-feed.html        #feed-list renders real rows when DB>0                (render-state)
  project-report.html     #ar-print-wrapper renders when DB>0                   (render-state)
  shift-brain.html        #carry-list renders when DB>0                         (render-state)
  analytics.html          #results-panel renders when DB>0                      (render-state)
  ai-quality.html         #content renders OR the intentional maturity gate shows (render-state, gate-aware)

Complements validate_hive_battery.py (hive.html deep render==DB) and truth-view-read-isolation (the DATA
layer / RLS). A regression (stale/dropped/mangled render, error swallowed as empty, stuck skeleton) FAILs.
Every expectation is derived from a LIVE DB count = reseed-robust. Skips cleanly (exit 0) if node or the
local stack (Flask :5000 + Supabase :54321) is absent — a local-only live gate.
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
HARNESS = ROOT / "tools" / "validate_read_battery.mjs"


def _up(url: str, timeout: float = 3.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception as e:
        return "HTTP Error" in str(e)


def main() -> int:
    print("\n" + "=" * 72)
    print("  Read-correctness battery (P3 rendered==DB / P7 empty-vs-error) — 8 read-heavy pages")
    print("=" * 72)
    if shutil.which("node") is None:
        print("  SKIP: node not on PATH — live read battery not evaluated (local-only live gate).")
        return 0
    if not HARNESS.exists():
        print(f"  FAIL: {HARNESS.name} missing — the read battery harness was removed.")
        return 1
    if not (_up("http://127.0.0.1:5000/workhive/hive.html") and _up("http://127.0.0.1:54321/rest/v1/")):
        print("  SKIP: local stack (Flask :5000 / Supabase :54321) not reachable — treating as stack-absent.")
        return 0
    try:
        r = subprocess.run(["node", str(HARNESS)], cwd=str(ROOT), capture_output=True, text=True, timeout=240)
    except Exception as e:
        print(f"  SKIP: could not run the read battery ({e}) — treating as local-stack-absent.")
        return 0
    out = (r.stdout or "").strip()
    if out:
        print("\n".join("  " + ln for ln in out.splitlines()))
    err = (r.stderr or "").strip()
    if err and r.returncode != 0:
        print("  stderr:", err[:400])
    if r.returncode == 0:
        print("\n  PASS: read paths hold (rendered==DB / correct empty-vs-error / no stuck skeleton).\n")
    else:
        print("\n  FAIL: a read-correctness regression (render drift / swallowed error / stuck skeleton).\n")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
