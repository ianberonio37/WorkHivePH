#!/usr/bin/env python3
"""
Validator: Engineering-Design silent-zero result fallbacks (deep-arc P7 / F-5), RATCHET.

Bug class: a report renderer resolves a load-bearing numeric result through an alias chain that
ends in `|| 0`, e.g. `Number(results.d_standard_mm || results.d_std_mm || results.d_used_mm || 0)`.
When the engine result is missing that key (a rename, a new mode, an aborted calc), the renderer
prints a SILENT ZERO — "0 mm" shaft diameter, "0 HP" motor, "0 kVA" genset — a dangerous
engineering spec that looks valid. A field-name test can't catch it (the field exists; it's the
VALUE that's a lie).

The correct fix is a per-field audit replacing the `|| 0` on PRIMARY result fields with an explicit
resolve-or-"unavailable" render — but distinguishing a dangerous primary field from a legitimately-
zero optional field is human judgment across ~123 sites, so a blanket refactor risks breaking the
intentional cases. This gate instead RATCHETS the class: it counts the alias-chain-ending-in-||0
pattern and FAILs if the count grows past the baseline, so the class can spread no further while the
per-field audit is worked. Lower the BASELINE as sites are genuinely fixed (that is the measured
progress signal).

Static + hermetic. Run: python tools/validate_engdesign_silent_zero.py   Self-test: --self-test
"""
import os
import re
import sys

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "engineering-design.js")

# Alias-chain ending in `|| 0` on a result/`r`-prefixed field: the dangerous silent-zero pattern.
PATTERN = re.compile(r"(?:results|_?r)\??\.\w+\s*\|\|[^;]{0,90}\|\|\s*0\b")

# Baseline captured 2026-07-08 at arc start (127). RATCHET: the count may not GROW. Lower this number
# as primary-field sites are genuinely converted to resolve-or-unavailable (measured F-5 progress).
# 2026-07-09: G1 per-field audit — 229 DANGEROUS display sites converted to _orNA (fan-out judged +
# adversarial/skeptic verified; 84 LEGIT keys + 11 skeptic-refuted plausible-real-zero keys left as-is).
# Alias-chain-||0 count dropped 127->77.
BASELINE = 77


def run():
    js = open(JS, encoding="utf-8").read()
    hits = PATTERN.findall(js)
    n = len(hits)
    print("=" * 62)
    print("Engineering-Design silent-zero ratchet (deep-arc P7 / F-5)")
    print("=" * 62)
    print(f"  alias-chain `... || 0` result fallbacks: {n}  (baseline {BASELINE})")
    if n > BASELINE:
        print(f"\nFAIL — the silent-zero class GREW ({n} > {BASELINE}). New `results.X || ... || 0`")
        print("       primary-field fallbacks render a dangerous 0 spec on a missing key. Use an")
        print("       explicit resolve-or-'unavailable' helper instead.")
        return 1
    if n < BASELINE:
        print(f"  note: count DROPPED {BASELINE}->{n} — lower BASELINE to {n} to lock the progress.")
    print("\nPASS — silent-zero class did not grow past the baseline.")
    return 0


def self_test():
    ok = True
    if not PATTERN.search("Number(results.torque_Nm || results.T_Nm || 0)"):
        print("self-test: pattern misses a real alias-chain"); ok = False
    if PATTERN.search("const x = a + b;"):
        print("self-test: pattern false-positive on plain code"); ok = False
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
