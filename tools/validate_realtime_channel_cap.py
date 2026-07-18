#!/usr/bin/env python3
"""validate_realtime_channel_cap.py - FREE_TIER_QUOTA_ROADMAP Q5 (realtime) ratchet.

GROUNDED (Step 0, VERIFIED): Supabase FREE tier = 200 concurrent realtime connections
PLATFORM-WIDE (shared across ALL users, like the LLM org-pool) - far tighter than the ~10K
the old whPoll note assumed. `whRealtimeSubscribe` bounds channels PER CLIENT and gracefully
degrades overflow + offline to whPoll (surface always updates: live when there's headroom,
polled when there isn't). This gate proves the cap + degrade + cleanup exist and behave.

  C1 primitive   whRealtimeSubscribe defined + exported on window
  C2 per-cap     a per-client channel cap (WH_MAX_CLIENT_CHANNELS) that degrades at the cap
  C3 degrade     graceful whPoll fallback on cap / offline / subscribe-error
  C4 cleanup     stop() frees the registry slot (reg.delete) - no leak toward the 200 wall
  C5 behaviour   the Node behavioural test (tools/verify_realtime_cap.js) passes - REAL teeth

USAGE:      python tools/validate_realtime_channel_cap.py
Self-test:  python tools/validate_realtime_channel_cap.py --self-test
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
UTILS = ROOT / "utils.js"
NODE_TEST = ROOT / "tools" / "verify_realtime_cap.js"
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"


GRACE_429_TEST = ROOT / "tools" / "verify_graceful_429.js"


def _node_passes(script: Path) -> bool:
    """Run a Node behavioural test (node works; only npx breaks on the '&' path)."""
    if not script.exists():
        return False
    try:
        r = subprocess.run(["node", str(script)], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and "PASS" in (r.stdout or "")
    except Exception:
        return False


def evaluate(js: str, node_ok: bool, grace_ok: bool = True) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    fn = ""
    m = re.search(r"function whRealtimeSubscribe\b", js)
    if m:
        # brace-match the body for the property checks
        i = js.index("{", m.start()); depth = 0
        for j in range(i, len(js)):
            if js[j] == "{": depth += 1
            elif js[j] == "}":
                depth -= 1
                if depth == 0:
                    fn = js[m.start():j + 1]; break

    c1 = bool(fn) and "window.whRealtimeSubscribe" in js
    checks.append(("C1 primitive", c1, "whRealtimeSubscribe defined + exported"
                   if c1 else "primitive missing/not exported"))

    c2 = ("WH_MAX_CLIENT_CHANNELS" in js) and bool(re.search(r"reg\.size\s*>=\s*max", fn))
    checks.append(("C2 per-cap", c2, "per-client channel cap degrades at the cap"
                   if c2 else "no per-client cap"))

    c3 = ("degradeToPoll" in fn) and ("whPoll(" in fn) and ("'cap'" in fn) and ("'offline'" in fn)
    checks.append(("C3 degrade", c3, "graceful whPoll fallback on cap/offline/error"
                   if c3 else "missing graceful degrade"))

    c4 = bool(re.search(r"reg\.delete\(channel\)", fn))
    checks.append(("C4 cleanup", c4, "stop() frees the registry slot"
                   if c4 else "no registry cleanup (channel leak)"))

    checks.append(("C5 behaviour", node_ok, "Node channel-cap behavioural test passes"
                   if node_ok else "Node behavioural test FAILED/absent"))

    checks.append(("C6 graceful-429", grace_ok, "scope-aware 429 UX maps each gateway body to the right hint"
                   if grace_ok else "graceful-429 classification test FAILED/absent"))
    return checks


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    js = UTILS.read_text(encoding="utf-8", errors="replace") if UTILS.exists() else ""
    node_ok = _node_passes(NODE_TEST)
    grace_ok = _node_passes(GRACE_429_TEST)
    checks = evaluate(js, node_ok, grace_ok)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q5 - realtime per-client channel cap + graceful degrade")
    print("=" * 74)
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:14s} {detail}")
    print(f"\n  {passed}/{len(checks)} checks green")

    if self_test:
        empty_all_fail = all(not ok for _, ok, _ in evaluate("", False, False))
        # a utils.js without the cap guard -> C2 fails
        no_cap = js.replace("reg.size >= max", "false")
        c2_tooth = dict((n, ok) for n, ok, _ in evaluate(no_cap, node_ok, grace_ok)).get("C2 per-cap") is False
        good = empty_all_fail and c2_tooth and node_ok and grace_ok  # node tests are the behavioural teeth
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] "
              f"empty=all-fail:{empty_all_fail}  no-cap->C2-fail:{c2_tooth}  channel-cap:{node_ok}  graceful-429:{grace_ok}")
        if not good:
            return 1

    print()
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}FAIL{RST} - {len(failed)} check(s) regressed: {', '.join(failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} - realtime channels are per-client capped + gracefully degrade to polling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
