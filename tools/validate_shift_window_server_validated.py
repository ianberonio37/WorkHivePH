#!/usr/bin/env python3
"""validate_shift_window_server_validated.py — T423's lock: a midnight-crossing shift is a SERVER-
validated first-class window, never derived from an untrusted client clock.

The failure T423 guards: a shift that runs 22:00-06:00 crosses midnight, and if "which shift is this"
were computed from the device clock, a phone in the wrong timezone (or with a lied-to clock) would
file the night shift's work under the wrong day. The platform avoids this by treating the shift
window as a SERVER-side enum: shift-planner-orchestrator declares VALID_WINDOWS = {06-14, 14-22,
22-06} and REJECTS any shift_window not in that set before doing anything with it. The 22-06 value
is a first-class member, so the midnight-crossing shift is a named, validated case — not an edge the
client has to reason about. Pairs feedback_two_clocks_in_one_file.

This gate holds three properties on shift-planner-orchestrator/index.ts:
  1. the enum exists and contains all three windows INCLUDING the midnight-crossing 22-06;
  2. the enum is a Set (membership-checked), and
  3. an incoming shift_window is validated against it (a `!VALID_WINDOWS.has(...)` reject path).

Static (source read), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import sys

CHECK_NAMES = ["shift-window-server-validated"]
SRC = "supabase/functions/shift-planner-orchestrator/index.ts"
WINDOWS = ["06-14", "14-22", "22-06"]


def _read() -> str | None:
    try:
        return io.open(SRC, encoding="utf-8").read()
    except Exception:
        return None


def check(src: str) -> list[str]:
    problems: list[str] = []
    m = re.search(r"VALID_WINDOWS\s*=\s*new\s+Set\(\s*\[([^\]]*)\]", src)
    if not m:
        problems.append("no `VALID_WINDOWS = new Set([...])` enum — the shift window is not a server-side allow-list")
        return problems
    listed = set(re.findall(r'"([^"]+)"', m.group(1)))
    for w in WINDOWS:
        if w not in listed:
            problems.append(f"VALID_WINDOWS is missing '{w}'" + (" (the MIDNIGHT-CROSSING window — the whole point of T423)" if w == "22-06" else ""))
    if not re.search(r"!\s*VALID_WINDOWS\.has\s*\(", src):
        problems.append("no `!VALID_WINDOWS.has(...)` reject path — an arbitrary/client-derived window is not rejected server-side")
    return problems


def main() -> int:
    src = _read()
    if src is None:
        print(f"FAIL shift-window-server-validated — {SRC} not found or unreadable."); return 1
    problems = check(src)
    if problems:
        print("FAIL shift-window-server-validated — the shift window is not a validated server-side enum:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS shift-window-server-validated — VALID_WINDOWS is a server-side Set of {06-14, 14-22, 22-06} "
          "(the midnight-crossing 22-06 first-class) and an incoming shift_window is rejected unless it is a member: "
          "the night shift is filed by the server's definition, never the device clock.")
    return 0


def self_test() -> int:
    good = 'const VALID_WINDOWS = new Set(["06-14", "14-22", "22-06"]);\n if (!VALID_WINDOWS.has(shift_window)) { return err(); }'
    fails = []
    if check(good):
        fails.append("a validated enum with 22-06 should PASS")
    if not any("22-06" in p for p in check(good.replace('"22-06"', '"x"'))):
        fails.append("missing the midnight-crossing window should FAIL")
    if not any("reject path" in p for p in check(good.replace("!VALID_WINDOWS.has(shift_window)", "true"))):
        fails.append("no reject path should FAIL")
    if not any("allow-list" in p for p in check("const X = 1;")):
        fails.append("no enum at all should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_shift_window_server_validated self-test (missing-window / no-reject / no-enum redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
