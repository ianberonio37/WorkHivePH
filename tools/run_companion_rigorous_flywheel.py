#!/usr/bin/env python3
"""
run_companion_rigorous_flywheel.py
==================================

Drives the REAL companion flywheel: per turn, invokes the Playwright spec
(companion-rigorous-flywheel.spec.ts) against the LIVE ai-gateway, then
calls the INDEPENDENT grader to assess the artifacts.

Replaces the fake simulators (run_companion_100turn_flywheel.py et al).

Honest scope:
  - This script COLLECTS evidence per turn. It does NOT auto-patch code
    between turns. Code fixes happen with Claude-in-the-loop in a later
    session, informed by the per-turn drift.json reports.
  - Rate-limit aware: backs off when consecutive turns see >50% 429s.
  - Checkpoints to .tmp/flywheel-state.json so you can resume after a
    crash or rate-limit exhaustion.
  - Persona + hive rotate per turn for cross-context coverage.

Usage:
  python tools/run_companion_rigorous_flywheel.py --turns 100 --start-from 1
  python tools/run_companion_rigorous_flywheel.py --turns 1 --start-from 1   # turn 1 only
  python tools/run_companion_rigorous_flywheel.py --turns 100 --rest-seconds 60
"""
from __future__ import annotations
import argparse
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / ".tmp" / "flywheel-state.json"
TURN_LOG_PATH = ROOT / ".tmp" / "flywheel-turn-log.jsonl"

PERSONAS = ["zaniah", "hezekiah"]
HIVES    = ["manila", "baguio", "cebu"]


def rotate_for_turn(turn: int) -> tuple[str, str]:
    persona = PERSONAS[(turn - 1) % len(PERSONAS)]
    hive    = HIVES[(turn - 1) % len(HIVES)]
    return persona, hive


# Local-eval rate-limit reset (added 2026-06-07 after a 3-run thrash on turn 18).
# The 58-probe bank exceeds BOTH default caps in `_shared/rate-limit.ts` — per-hive
# `checkAIRateLimit` (table `ai_rate_limits`, cap 50) AND per-user `checkUserRateLimit`
# (table `ai_user_rate_limits`, cap 25) — and `supabase start` does NOT load
# `supabase/functions/.env`, so `WH_*_RATE_LIMIT_OVERRIDE` never reaches the runtime.
# Un-relaxed, a >25-probe turn gets starved: the LATE probes (always the adversarial /
# safety tail) 429, grade as fails, and bake a FALSE-low safety floor into the baseline.
# We seed BOTH counters far-negative with a fresh window before each turn so the whole
# bank runs un-throttled. LOCAL ONLY: mutates infra counters on the local Supabase
# docker DB (not real data; self-heals after 1h when the window goes stale). Best-effort
# — never blocks the run. Opt out with WH_FLYWHEEL_NO_RESET=1. NOTE: resets EXISTING
# rows; a brand-new DB with no counter row yet may still throttle on turn 1 (rows are
# upserted by the gateway, then reset cleanly from turn 2 on).
DB_CONTAINER = os.environ.get("WH_LOCAL_DB_CONTAINER", "supabase_db_workhive")


def reset_rate_limit_counters() -> None:
    """Relax the per-hive + per-user AI rate-limit counters so the full probe bank
    runs without 429 starvation. See module note above. Best-effort + local-only."""
    if os.environ.get("WH_FLYWHEEL_NO_RESET"):
        return
    sql = (
        "UPDATE ai_rate_limits SET call_count=-100000, window_start=now();"
        "UPDATE ai_user_rate_limits SET call_count=-100000, window_start=now();"
    )
    try:
        proc = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode == 0:
            print("[orch] rate-limit counters relaxed (hive+user) — full bank runs un-throttled.", flush=True)
        else:
            print(f"[orch] rate-limit reset SKIPPED (psql rc={proc.returncode}): "
                  f"{(proc.stderr or '').strip()[:140]} — a >25-probe turn may see 429s.", flush=True)
    except Exception as e:
        print(f"[orch] rate-limit reset SKIPPED ({type(e).__name__}: {e}) — "
              f"a >25-probe turn may see 429s. Set WH_FLYWHEEL_NO_RESET=1 to silence.", flush=True)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_completed_turn": 0, "turns": []}


def append_turn_log(entry: dict) -> None:
    TURN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TURN_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def stack_alive() -> bool:
    """Quick check that local Supabase + Flask seeder are up."""
    import urllib.request
    import urllib.error
    for url in (
        "http://127.0.0.1:54321/rest/v1/",
        "http://127.0.0.1:5000/",
    ):
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as e:
            if e.code in (200, 401, 404, 405):
                continue
        except Exception:
            return False
    return True


def run_playwright_for_turn(turn: int, persona: str, hive: str) -> tuple[bool, str]:
    """Invoke the Playwright spec for one turn. Returns (success, log_excerpt)."""
    env = os.environ.copy()
    env["FLYWHEEL_TURN"] = str(turn)
    env["FLYWHEEL_PERSONA"] = persona
    env["FLYWHEEL_HIVE_LABEL"] = hive

    # Direct node invocation avoids the `&` in the project path breaking
    # the npx subprocess shell expansion ("Build & Sell with Claude Code").
    playwright_cli = str(ROOT / "node_modules" / "@playwright" / "test" / "cli.js")
    cmd = [
        "node", playwright_cli, "test",
        "tests/companion-rigorous-flywheel.spec.ts",
        "--reporter=list",
        "--workers=1",
    ]
    print(f"[orch] turn {turn} — launching Playwright ({persona}/{hive})…", flush=True)
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), env=env,
            capture_output=True, text=True,
            timeout=60 * 60,   # 1 hour per turn ceiling
        )
        dur = time.time() - t0
        ok = proc.returncode == 0
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        tail = log[-3000:] if len(log) > 3000 else log
        print(f"[orch] turn {turn} — Playwright exit={proc.returncode} in {dur:.1f}s", flush=True)
        return ok, tail
    except subprocess.TimeoutExpired:
        print(f"[orch] turn {turn} — Playwright TIMED OUT after 1h", flush=True)
        return False, "TIMEOUT after 1h"
    except FileNotFoundError as e:
        print(f"[orch] turn {turn} — npx not found: {e}", flush=True)
        return False, f"npx not found: {e}"


def run_grader_for_turn(turn: int) -> dict:
    """Invoke the independent grader. Returns the parsed report.json."""
    cmd = [sys.executable, str(ROOT / "tools" / "companion_rigorous_grader.py"),
           "--turn", str(turn)]
    print(f"[orch] turn {turn} — grading…", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    if proc.stdout:
        print(proc.stdout, flush=True)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, flush=True)
    report_path = ROOT / ".tmp" / f"flywheel-turn-{turn}" / "report.json"
    if report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return {"turn": turn, "error": "no report.json produced", "metrics": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rigorous companion flywheel — REAL probes, REAL ai-gateway.")
    parser.add_argument("--turns",       type=int, default=100, help="Total turns to run")
    parser.add_argument("--start-from",  type=int, default=1,   help="Turn number to start at (resume-friendly)")
    parser.add_argument("--rest-seconds", type=int, default=30, help="Seconds between turns (cooldown)")
    parser.add_argument("--abort-on-stack-down", action="store_true",
                        help="Abort if local stack becomes unreachable")
    args = parser.parse_args()

    if not stack_alive():
        print("[orch] ERROR: local stack appears down (Supabase 54321 or Flask 5000).", file=sys.stderr)
        if args.abort_on_stack_down:
            return 3
        print("[orch] Proceeding anyway — turn 1 will surface the real failure mode.", flush=True)

    state = load_state()
    print(f"[orch] starting turn {args.start_from} → {args.start_from + args.turns - 1}", flush=True)
    print(f"[orch] state file: {STATE_PATH}", flush=True)
    print(f"[orch] turn log:   {TURN_LOG_PATH}", flush=True)

    consecutive_rate_limited_turns = 0

    for turn in range(args.start_from, args.start_from + args.turns):
        persona, hive = rotate_for_turn(turn)
        turn_started = datetime.now().isoformat()

        reset_rate_limit_counters()  # local-only; keeps the full bank off the 429 tail
        ok, log_tail = run_playwright_for_turn(turn, persona, hive)
        if not ok:
            entry = {
                "turn": turn, "ts": turn_started,
                "status": "PLAYWRIGHT_FAIL",
                "persona": persona, "hive": hive,
                "log_tail": log_tail[-1500:],
            }
            append_turn_log(entry)
            state.setdefault("turns", []).append(entry)
            save_state(state)
            print(f"[orch] turn {turn} — playwright failed, continuing to next turn", flush=True)
            continue

        report = run_grader_for_turn(turn)
        metrics = report.get("metrics", {})
        drift = report.get("drift", {})

        entry = {
            "turn":      turn,
            "ts":        turn_started,
            "status":    "OK",
            "persona":   persona,
            "hive":      hive,
            "metrics":   metrics,
            "drift_summary": {
                "fail_count": drift.get("fail_count"),
                "leak_count": drift.get("leak_count"),
                "rate_limited": drift.get("rate_limited"),
                "top_fails":  list(drift.get("fails_by_category", {}).items())[:3],
            },
        }
        append_turn_log(entry)
        state["last_completed_turn"] = turn
        state.setdefault("turns", []).append(entry)
        save_state(state)

        # Rate-limit backoff: if >50% of probes were 429, treat as throttled
        probe_total = metrics.get("total", 0) or 1
        if drift.get("rate_limited", 0) / probe_total > 0.5:
            consecutive_rate_limited_turns += 1
            backoff = min(600, 60 * (2 ** consecutive_rate_limited_turns))
            print(f"[orch] turn {turn} — {drift['rate_limited']}/{probe_total} rate-limited; backing off {backoff}s", flush=True)
            time.sleep(backoff)
        else:
            consecutive_rate_limited_turns = 0
            if turn < args.start_from + args.turns - 1:
                time.sleep(args.rest_seconds)

    print(f"\n[orch] Done. {state['last_completed_turn']} turn(s) completed. State at {STATE_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
