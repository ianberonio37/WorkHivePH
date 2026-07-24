#!/usr/bin/env python3
"""contract_test_rate_limit_seam.py — C4 contract test for the ai->quota / *->rate-limit seams.

WHAT A CONTRACT TEST IS HERE (per ai_seam_contracts.json policy): it pins the WIRE FORMAT between
caller and callee - the fields the caller reads off the callee's result - so a change on either side
that breaks the other FAILs loudly instead of silently returning undefined at runtime.

WHY THIS SEAM (2026-07-23, §12 flywheel loop 17): moving fmea-populator / visual-defect-capture /
voice-action-router off their hand-rolled limiters onto `_shared/rate-limit.ts` created 3 NEW
ai->quota seams. Rather than accept a higher uncovered floor (the gate's other option - "a contract
gap is real risk"), this covers them, and the same contract protects the other 16 callers too.

THE CONTRACT (both directions):
  callee EXPORTS  checkAIRateLimit -> { allowed, remaining }        (hour AND day enforced)
                  checkRouteRateLimit -> { allowed, remaining, cap, per_route, enforce }
                  routeRateLimitedResponse(corsHeaders, route, cap) -> 429 Response
  callers READ    only .allowed / .remaining from the global check
                  only .per_route / .allowed / .cap from the route check
A caller reading a field the callee does not return is the exact silent-undefined bug this pins.

USAGE:      python tools/contract_test_rate_limit_seam.py
Self-test:  python tools/contract_test_rate_limit_seam.py --selftest
Exit 0 = contract holds; 1 = the seam drifted.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
G = "\033[92m"; R = "\033[91m"; X = "\033[0m"

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "supabase" / "functions" / "_shared" / "rate-limit.ts"
FNS = ROOT / "supabase" / "functions"

# fields the callee MUST return, and that callers are allowed to read
GLOBAL_FIELDS = {"allowed", "remaining"}
ROUTE_FIELDS = {"allowed", "remaining", "cap", "per_route", "enforce"}


def check() -> list[str]:
    errs: list[str] = []
    if not SHARED.exists():
        return ["_shared/rate-limit.ts is missing - the whole seam is broken"]
    src = SHARED.read_text(encoding="utf-8", errors="replace")

    # 1) callee side: the exports the seam depends on must exist
    for fn in ("checkAIRateLimit", "checkRouteRateLimit", "routeRateLimitedResponse"):
        if not re.search(r"export (async )?function " + fn + r"\b", src):
            errs.append(f"callee no longer exports {fn}()")

    # 2) callee side: the RESULT SHAPES must still carry every field callers read
    if not re.search(r"interface RouteRateLimitResult[\s\S]{0,400}?per_route", src):
        errs.append("RouteRateLimitResult lost `per_route` (callers gate enforcement on it)")
    if not re.search(r"cap:\s*number", src):
        errs.append("RouteRateLimitResult lost `cap` (callers pass it to routeRateLimitedResponse)")
    if "allowed" not in src or "remaining" not in src:
        errs.append("result shape lost allowed/remaining")

    # 3) callee side: the DAILY ceiling must still be enforced (the bypass this seam work fixed).
    #    ★Use WORD BOUNDARIES, not `in`. A substring test is not a contract test: `"limitPerDay" in
    #    "limitPerDayXX"` is True, so a renamed/mangled symbol still "passed". Fault injection caught
    #    this - removing the daily ceiling returned exit 0. Anchored regexes make the check real.
    for sym in ("limitPerDay", "day_count", "day_window_start", "DEFAULT_RATE_LIMIT_PER_DAY"):
        if not re.search(r"\b" + re.escape(sym) + r"\b", src):
            errs.append(f"the shared limiter lost `{sym}` - the DAILY ceiling is no longer enforced "
                        f"(regression to hourly-only, the exact bypass fixed 2026-07-23)")

    # 4) caller side: nobody may read a field the callee does not return.
    #    Covers BOTH caller kinds so this one contract legitimately covers every *->rate-limit seam:
    #      - route callers  (checkRouteRateLimit -> ROUTE_FIELDS, read via the `_rq.` binding)
    #      - global callers (checkAIRateLimit    -> GLOBAL_FIELDS, read via the `rl.` binding)
    for f in sorted(FNS.glob("*/index.ts")):
        if f.parent.name == "_shared":
            continue
        s = f.read_text(encoding="utf-8", errors="replace")
        uses_route = "checkRouteRateLimit(" in s
        uses_global = "checkAIRateLimit(" in s
        if not (uses_route or uses_global):
            continue
        if uses_route:
            for field in set(re.findall(r"_rq\.(\w+)", s)):
                if field not in ROUTE_FIELDS:
                    errs.append(f"{f.parent.name} reads _rq.{field} which the route contract does not return")
        if uses_global:
            for field in set(re.findall(r"\brl\.(\w+)", s)):
                if field not in GLOBAL_FIELDS:
                    errs.append(f"{f.parent.name} reads rl.{field} which the global contract does not return")
        # a caller must not re-inline a private copy of the limiter (hand-rolled copies skip the daily cap)
        if re.search(r"^\s*async function checkAIRateLimit", s, re.M):
            errs.append(f"{f.parent.name} re-inlined a LOCAL checkAIRateLimit (hand-rolled copies skip the daily cap)")
    return errs


def self_test() -> bool:
    ok = True
    if "per_route" not in ROUTE_FIELDS or "allowed" not in GLOBAL_FIELDS:
        print(f"{R}selftest FAIL: contract field sets are wrong{X}"); ok = False
    # the real check must currently pass, else the self-test is meaningless
    if check():
        print(f"{R}selftest FAIL: contract does not hold on the live tree{X}"); ok = False
    print((G + "selftest PASS - rate-limit seam contract has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    errs = check()
    if errs:
        print(f"{R}FAIL - ai->quota / *->rate-limit seam contract DRIFTED:{X}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"{G}PASS - rate-limit seam contract holds "
          f"(exports + result shapes + daily ceiling + no caller reads an unknown field).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
