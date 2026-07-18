#!/usr/bin/env python3
# DEEPWALK-CELL: * D7
"""
validate_sast_owasp_complete.py - Arc R (S-lens, OWASP A09 meta): the SAST posture map must
cover the FULL OWASP Top-10, and every mapped scanner must exist.
=========================================================================================
Meta-finding #1 (Arc R): sast_scan.py printed "every OWASP Top-10 category has an automated
scanner / 7/7" while its map enumerated only 7 of the 10 categories - A07 (Auth Failures),
A09 (Logging/Monitoring), A10 (SSRF) were ABSENT from the map entirely, so the green was a
false sense of coverage (a metric measured against a truncated denominator - the exact
anti-pattern Arc Q taught). This gate makes that un-fakeable: it reads sast_scan.OWASP and
FAILS unless all of A01..A10 are present AND each category resolves at least one existing
scanner (at ROOT or tools/).

Self-test (--self-test): proves teeth - a map missing A10 FAILs; the full map passes.

Exit 0 = full Top-10 mapped + every scanner resolvable. Exit 1 = a gap (or self-test fail).
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_sast_owasp_complete"]
REQUIRED = [f"A{n:02d}" for n in range(1, 11)]  # A01..A10


def _resolve(v: str):
    for cand in (ROOT / v, ROOT / "tools" / v):
        if cand.exists():
            return cand
    return None


def _check(owasp: dict) -> list[str]:
    fails = []
    present_codes = {k.split()[0].split(":")[0] for k in owasp}  # "A01:2025 Broken..." -> "A01" (OWASP 2025 relabel); also handles "A01 x"
    for code in REQUIRED:
        if code not in present_codes:
            fails.append(f"OWASP {code} is ABSENT from the SAST map")
    for cat, scanners in owasp.items():
        if not any(_resolve(s) for s in scanners):
            fails.append(f"{cat}: no resolvable scanner ({scanners})")
    return fails


def self_test() -> bool:
    ok = True
    full = {f"A{n:02d} x": ["validate_xss.py"] for n in range(1, 11)}
    if _check(full):
        # validate_xss.py exists at ROOT so each resolves; only completeness matters here
        print(f"{R}self-test FAIL: full map flagged.{X}"); ok = False
    missing = {f"A{n:02d} x": ["validate_xss.py"] for n in range(1, 10)}  # no A10
    if not any("A10" in f for f in _check(missing)):
        print(f"{R}self-test FAIL: did not catch missing A10.{X}"); ok = False
    print((G + "self-test PASS - completeness gate has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1
    try:
        import sast_scan  # noqa
        owasp = sast_scan.OWASP
    except Exception as e:
        print(f"{R}FAIL: cannot import sast_scan.OWASP ({e}){X}")
        return 1

    fails = _check(owasp)
    print(f"{B}SAST OWASP-completeness gate (Arc R / S-lens){X}")
    print(f"  categories mapped: {len(owasp)}  ·  required: 10")
    for f in fails:
        print(f"  {R}FAIL{X} {f}")
    if fails:
        print(f"{R}FAIL: SAST map does not cover the full OWASP Top-10.{X}")
        return 1
    print(f"{G}PASS - SAST map covers all 10 OWASP categories, every scanner resolvable.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
