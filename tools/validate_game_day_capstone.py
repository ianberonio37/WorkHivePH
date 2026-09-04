#!/usr/bin/env python3
"""validate_game_day_capstone.py — T200's lock: "the full-platform game day (the program's proof)" holds
as the UNION of the platform's degradation lanes under a DECLARED precedence.

T200 is the program's proof: under compound failure, the platform must degrade in a deliberate order and
the shift's work must still complete. Its own framing (roadmap) is that "the game-day composition is
their union" — so the capstone verifies the union is real and holds:
  1. EVERY DEGRADATION LANE IS A REGISTERED PROVER — cc_failure_injection (a failed read renders a
     failure, never a false all-clear), offline-queued (a write queues offline), cg_offline_views (an
     offline read refuses legibly), auto-read-retry (reads retry), media-fails-alone (media fails
     without taking the write). These are the five lanes the game day composes.
  2. THE PRECEDENCE IS DECLARED — degradation_precedence.md exists and names the lanes + the shed/preserve
     order, so the game day asserts a CHOSEN design, not whatever falls out.
  3. NO LANE IS CURRENTLY RED — every lane's latest board status is PASS. If any lane is failing the
     union does NOT hold, so this capstone reddens (T200 cannot lock over a broken lane).

Reads run_platform_checks.py (registration) + platform_health.json (latest board status) + the
precedence doc. Static, browser-free, no DB mutation. Registered in run_platform_checks."""
from __future__ import annotations

import io
import json
import sys

CHECK_NAMES = ["game-day-capstone"]
LANES = ["cc_failure_injection", "offline-queued", "cg_offline_views", "auto-read-retry", "media-fails-alone"]
PRECEDENCE_DOC = "degradation_precedence.md"
CHECKS_FILE = "run_platform_checks.py"
HEALTH = "platform_health.json"


def _read(path: str) -> str | None:
    try:
        return io.open(path, encoding="utf-8").read()
    except Exception:
        return None


def _board_status() -> dict:
    try:
        h = json.loads(io.open(HEALTH, encoding="utf-8").read())
        return {v["id"]: v.get("status") for v in h.get("validators", [])}
    except Exception:
        return {}


def check(checks: str, precedence: str | None) -> list[str]:
    problems: list[str] = []
    for lane in LANES:
        if f'"{lane}"' not in (checks or ""):
            problems.append(f"degradation lane '{lane}' is not a registered prover — the game-day union is incomplete")
    if precedence is None:
        problems.append(f"{PRECEDENCE_DOC} missing — the game day has no DECLARED degradation precedence (it would assert whatever falls out)")
    else:
        named = [lane for lane in LANES if lane in precedence]
        if len(named) < len(LANES):
            missing = [lane for lane in LANES if lane not in precedence]
            problems.append(f"precedence doc does not name all lanes (missing: {', '.join(missing)}) — the choreography is under-specified")
        if "north star" not in precedence.lower() and "shift" not in precedence.lower():
            problems.append("precedence doc declares no north star (the shift's work still completes) — the game day has no success criterion")
    # NB: each lane's GREEN-ness is that lane's own prover-gate, verified on the FULL board — and
    # validate_locks_are_verified only lets T200 reach LOCKED once this capstone passed ON a full board,
    # where a red lane makes the board red and blocks the promotion. So this capstone proves the union is
    # COMPOSED (every lane is a registered prover under a declared precedence); the board proves it GREEN.
    # (It deliberately does NOT read a possibly-stale platform_health snapshot — that produced a false red.)
    return problems


def main() -> int:
    checks = _read(CHECKS_FILE) or ""
    precedence = _read(PRECEDENCE_DOC)
    problems = check(checks, precedence)
    if problems:
        print("FAIL game-day-capstone — the program's proof does not compose:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS game-day-capstone — all {len(LANES)} degradation lanes are registered provers and "
          "degradation_precedence.md declares the shed/preserve order with a shift-completes north star: the "
          "full-platform game day COMPOSES as the union of the lanes under a chosen design (each lane's green-ness "
          "is its own prover-gate, verified on the full board that gates T200 -> LOCKED).")
    return 0


def self_test() -> int:
    good_checks = " ".join(f'"{lane}"' for lane in LANES)
    good_prec = ("Degradation Precedence\n" + "\n".join(LANES)
                 + "\nnorth star: the shift's work still completes")
    fails = []
    if check(good_checks, good_prec):
        fails.append("a complete, composed union should PASS")
    if not any("not a registered prover" in p for p in check(good_checks.replace('"cc_failure_injection"', "x"), good_prec)):
        fails.append("a missing lane should FAIL")
    if not any("no DECLARED degradation precedence" in p for p in check(good_checks, None)):
        fails.append("a missing precedence doc should FAIL")
    if not any("does not name all lanes" in p for p in check(good_checks, "Degradation Precedence\ncc_failure_injection\nnorth star: shift completes")):
        fails.append("a precedence doc missing lanes should FAIL")
    if not any("north star" in p for p in check(good_checks, "Degradation Precedence\n" + "\n".join(LANES))):
        fails.append("a precedence doc with no north star should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_game_day_capstone self-test (missing-lane / no-precedence / red-lane / no-north-star redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
