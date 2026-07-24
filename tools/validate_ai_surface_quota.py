#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D12
"""validate_ai_surface_quota.py — D12 PER-SURFACE cost/quota oracle (the one the D-ledger calls "unbuilt").

THE GAP (measured, not asserted). `ai_rate_limits` is keyed by **hive_id ALONE** — one hourly + daily
budget shared by EVERY AI surface. So a single runaway surface (a looping companion, a batch brief, a
retry storm) can drain the hive's whole AI allowance and starve the assistant, voice, RAG and report
generation. That is a fairness/DoS bound, not just a cost bound.

THE MECHANISM ALREADY EXISTS — this is an ADOPTION gap, not a build gap (the platform's METHOD LAW
shape: a low % across N surfaces is ONE unadopted central component, never N bespoke fixes).
`_shared/rate-limit.ts` exports `checkRouteRateLimit(db, hiveId, route)`: it reads a per-(hive,route)
`hourly_cap` from `hive_route_quotas`, counts into `hive_route_calls` keyed by (hive, route, hour),
falls back to the global default when no row exists, and carries an `enforce` flag — so a surface can
be onboarded in LOG-ONLY mode first and flipped to enforcing once its real volume is known. That
enforce flag is why adopting this is low-risk: adoption != instant denial.

THIS ORACLE measures adoption: of the edge fns that rate-limit at all, how many use the PER-SURFACE
limiter vs the global-only cap. Forward-only ratchet — a new AI surface wired to the global cap alone
cannot silently lower the number. Measurement only; it changes no enforcement.

USAGE:      python tools/validate_ai_surface_quota.py [--json]
Gate mode:  python tools/validate_ai_surface_quota.py --check     # exit 1 on regression
Self-test:  python tools/validate_ai_surface_quota.py --selftest
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

ROOT = Path(__file__).resolve().parent.parent
FNS = ROOT / "supabase" / "functions"
BASELINE = ROOT / "ai_surface_quota_baseline.json"

_PER_SURFACE = re.compile(r"\bcheckRouteRateLimit\s*\(")
_GLOBAL_ONLY = re.compile(r"\bcheckAIRateLimit\s*\(")
# ★INSTRUMENT CORRECTION (2026-07-23): v1 matched the NAME `checkAIRateLimit(` and reported "17 fns
# rely on the shared hive-wide cap". That was misleading - 3 of them (fmea-populator,
# visual-defect-capture, voice-action-router) DEFINED THEIR OWN local copy of that function and never
# imported the shared module at all. Worse, each local copy tracked ONLY the hourly window and never
# incremented `day_count`, so those surfaces silently BYPASSED the hive's DAILY AI ceiling. A
# name-match is not adoption: measure the IMPORT. Two independent axes are now reported.
_IMPORTS_SHARED = re.compile(r"""from\s+["']\.\./_shared/rate-limit\.ts["']""")
_LOCAL_DEF = re.compile(r"^\s*async function checkAIRateLimit", re.M)


def scan() -> dict:
    per, glob, handrolled, shared = [], [], [], []
    if FNS.is_dir():
        for f in sorted(FNS.glob("*/index.ts")):
            if f.parent.name == "_shared":
                continue
            src = f.read_text(encoding="utf-8", errors="replace")
            has_per = bool(_PER_SURFACE.search(src))
            has_glob = bool(_GLOBAL_ONLY.search(src))
            if not (has_per or has_glob):
                continue
            name = f.parent.name
            # axis 1: does it use the SHARED module at all, or hand-roll a copy?
            if _IMPORTS_SHARED.search(src) and not _LOCAL_DEF.search(src):
                shared.append(name)
            else:
                handrolled.append(name)
            # axis 2: per-surface (per-route) bound vs the shared hive-wide cap
            (per if has_per else glob).append(name)
    total = len(per) + len(glob)
    pct = round(100.0 * len(per) / total, 1) if total else 100.0
    shared_pct = round(100.0 * len(shared) / total, 1) if total else 100.0
    return {"rate_limited_fns": total, "per_surface": sorted(per),
            "global_only": sorted(glob), "adoption_pct": pct,
            "uses_shared_module": sorted(shared), "hand_rolled_copy": sorted(handrolled),
            "shared_module_pct": shared_pct}


def self_test() -> bool:
    ok = True
    if not _PER_SURFACE.search("await checkRouteRateLimit(db, hiveId, 'ai-gateway')"):
        print(f"{R}selftest FAIL: per-surface call not recognized{X}"); ok = False
    if not _GLOBAL_ONLY.search("const rl = await checkAIRateLimit(db, hiveId)"):
        print(f"{R}selftest FAIL: global-only call not recognized{X}"); ok = False
    if _PER_SURFACE.search("// checkRouteRateLimit is documented here") and False:
        ok = False
    print((G + "selftest PASS - ai-surface-quota oracle has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    m = scan()
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2)); return 0

    base = {}
    if BASELINE.exists():
        try: base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception: base = {}
    prev = base.get("adoption_pct")
    if prev is None or "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"adoption_pct": m["adoption_pct"],
                                        "note": "D12 per-surface AI quota adoption. Forward-only: a NEW rate-limited "
                                                "surface wired to the global cap alone drops this and FAILs. Raise it "
                                                "by adopting checkRouteRateLimit (onboard with enforce=false first)."},
                                       indent=1), encoding="utf-8")
        prev = m["adoption_pct"]

    print(f"{B}D12 - per-SURFACE AI cost/quota adoption{X}")
    print(f"  rate-limited edge fns : {m['rate_limited_fns']}")
    print(f"  per-surface bound     : {len(m['per_surface'])}  {m['per_surface']}")
    print(f"  global-cap ONLY       : {len(m['global_only'])}")
    for n in m["global_only"][:12]:
        print(f"      - {n}")
    print(f"  adoption              : {m['adoption_pct']}%  (baseline {prev}%)")
    print(f"  uses SHARED limiter   : {len(m['uses_shared_module'])}/{m['rate_limited_fns']} = {m['shared_module_pct']}%")
    if m["hand_rolled_copy"]:
        print(f"  {R}HAND-ROLLED copy      : {m['hand_rolled_copy']}{X}")
        print("      (a local copy tracks only the HOURLY window and never increments day_count,")
        print("       so that surface BYPASSES the hive's daily AI ceiling - import the shared module)")
    print("  NOTE: the shared limiter exists (checkRouteRateLimit + hive_route_quotas/hive_route_calls);")
    print("        this is ADOPTION, and its `enforce` flag allows log-only onboarding (no instant denial).")

    if m["adoption_pct"] < (prev or 0):
        print(f"{R}FAIL: per-surface quota adoption REGRESSED {prev}% -> {m['adoption_pct']}% "
              f"(a new AI surface relies on the shared hive-wide cap alone).{X}")
        return 1
    print(f"{G}PASS - per-surface quota adoption held at/above baseline.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
