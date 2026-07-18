#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D12
"""validate_ai_daily_ceiling.py - FREE_TIER_QUOTA_ROADMAP Q4 (daily AI ceiling) ratchet.

The AI daily-window 429 decision, locked. The live edge-runtime HTTP proof is deno-gated, so
the DECISION is proven via a Node local-substitute (tools/verify_ai_daily_ceiling.js) that
extracts + drives the REAL checkAIRateLimit/checkSoloRateLimit bodies from _shared/rate-limit.ts.

  C1 columns    the day-window columns exist (migration adds day_count + day_window_start)
  C2 enforce    both limiters deny with scope='day' when day_count >= limitPerDay
  C3 decision   the Node decision test passes - REAL teeth (allow/deny/reset all correct)

USAGE:      python tools/validate_ai_daily_ceiling.py
Self-test:  python tools/validate_ai_daily_ceiling.py --self-test
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
RATE_LIMIT = ROOT / "supabase" / "functions" / "_shared" / "rate-limit.ts"
NODE_TEST = ROOT / "tools" / "verify_ai_daily_ceiling.js"
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(MIGRATIONS.glob("*.sql")))


def _node_passes() -> bool:
    if not NODE_TEST.exists():
        return False
    try:
        r = subprocess.run(["node", str(NODE_TEST)], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and "PASS" in (r.stdout or "")
    except Exception:
        return False


def evaluate(mig: str, rl: str, node_ok: bool) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    c1 = ("day_count" in mig) and ("day_window_start" in mig) and "ai_rate_limits" in mig
    checks.append(("C1 columns", c1, "day_count + day_window_start columns added"
                   if c1 else "day-window columns missing"))

    c2 = bool(re.search(r"dayCount\s*>=\s*limitPerDay", rl)) and rl.count('scope: "day"') >= 1
    checks.append(("C2 enforce", c2, "limiters deny scope='day' at the daily ceiling"
                   if c2 else "daily-window enforcement missing"))

    checks.append(("C3 decision", node_ok, "Node decision test passes (allow/deny/reset)"
                   if node_ok else "Node decision test FAILED/absent"))
    return checks


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    mig = _migrations_text()
    rl = RATE_LIMIT.read_text(encoding="utf-8", errors="replace") if RATE_LIMIT.exists() else ""
    node_ok = _node_passes()
    checks = evaluate(mig, rl, node_ok)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q4 - AI daily ceiling (429 decision, locally proven)")
    print("=" * 74)
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:12s} {detail}")
    print(f"\n  {passed}/{len(checks)} checks green")

    if self_test:
        empty_all_fail = all(not ok for _, ok, _ in evaluate("", "", False))
        no_enforce = rl.replace("dayCount >= limitPerDay", "false")
        c2_tooth = dict((n, ok) for n, ok, _ in evaluate(mig, no_enforce, node_ok)).get("C2 enforce") is False
        good = empty_all_fail and c2_tooth and node_ok
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] "
              f"empty=all-fail:{empty_all_fail}  no-enforce->C2-fail:{c2_tooth}  node-decision:{node_ok}")
        if not good:
            return 1

    print()
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}FAIL{RST} - {len(failed)} check(s) regressed: {', '.join(failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} - AI daily 429 ceiling decision is enforced + locally proven (deploy Ian-gated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
