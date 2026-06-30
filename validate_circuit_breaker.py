#!/usr/bin/env python3
"""validate_circuit_breaker.py - Arc S (Resilience/DR) F-lens cell `external_circuit_breaker`.
================================================================================
The platform already has a production-grade circuit-breaker (_shared/provider-health.ts:
escalating cooldown + Retry-After) used by the AI chain. The LIVE external-API edge
functions (Resend email, CMMS sync) must REUSE it, so a sustained outage stops being
hammered (failing fast with a clear "temporarily unavailable") instead of 502-ing on
every attempt and burning quota/latency.

This gate asserts each live external-dependency fn imports provider-health and uses
the breaker (isSlotBlocked pre-check + recordSlotFailure/recordSlotSuccess). The
marketplace Stripe fns are EXCLUDED — they are vestigial (free-platform decision,
pending the REMOVE-vs-keep fork), so requiring a breaker there would gild dead code.

Exit 0 = live external deps circuit-broken; 1 = one hammers without backoff. Stdlib, $0.
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FUNCS = ROOT / "supabase" / "functions"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# live external-dependency fns that must circuit-break (slot label for the message)
LIVE_EXTERNAL_FNS = [
    ("send-report-email", "Resend"),
    ("cmms-sync",         "CMMS"),
]


def _read(fn: str) -> str:
    try:
        return (FUNCS / fn / "index.ts").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    print(f"{B}Arc S - external circuit-breaker (F-lens, no hammering){X}")
    print("=" * 60)
    issues = []
    for fn, label in LIVE_EXTERNAL_FNS:
        t = _read(fn)
        if not t:
            print(f"  {Y}SKIP{X}  {fn} (not found)")
            continue
        imports = "provider-health.ts" in t
        pre = "isSlotBlocked(" in t
        rec = "recordSlotFailure(" in t and "recordSlotSuccess(" in t
        ok = imports and pre and rec
        miss = []
        if not imports: miss.append("no provider-health import")
        if not pre:     miss.append("no isSlotBlocked pre-check")
        if not rec:     miss.append("no recordSlotFailure/Success")
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  {fn} ({label}) circuit-breaker {('· ' + '; '.join(miss)) if miss else 'wired'}")
        if not ok:
            issues.append(fn)

    if issues:
        print(f"\n{R}{B}  CIRCUIT-BREAKER: FAIL{X} - unprotected external dependency in: {', '.join(issues)}")
        return 1
    print(f"\n{G}{B}  CIRCUIT-BREAKER: PASS{X} - live external deps reuse provider-health (fail-fast on outage).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
