#!/usr/bin/env python3
"""validate_dr_claims.py - Arc S (Resilience/DR) R-lens cell `dr_claims_backed` (the keystone).
================================================================================
The Arc-Q/R anti-pattern in DR form: RTO_RPO_DECLARATION.md DECLARED recovery
mechanisms ("daily logical dump", "S3/R2 versioned bucket", "daily export to cold
storage") that did NOT exist — a false-sense recovery posture that would fail an
ISO 27001 / SOC 2 audit and, worse, fail a real recovery.

This gate parses the per-data-class table and asserts EVERY "Backup mechanism" cell
is either BACKED by an implemented mechanism OR explicitly marked a PROD TARGET (⏳).
A mechanism stated as live with no backing implementation FAILS the build.

Backed = references one of: an implemented tool (data_backup.py / verify_backups /
cold_archive_exporter / dataloss_monitor), a wired feature (offline-queue), a managed
service (PITR), or an inherent property (Recomputable). Prod-target = carries "⏳" or
"prod target". Also requires the "Implementation status" section to be present.

Exit 0 = no unbacked recovery claim; 1 = a false-sense claim remains. Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DOC = ROOT / "RTO_RPO_DECLARATION.md"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# tokens that prove a mechanism is real (implemented / managed / property) or honestly deferred
BACKED = [
    "data_backup.py", "verify_backups", "cold_archive_exporter", "dataloss_monitor",
    "offline-queue", "pitr", "recomputable", "regenerable",
    "prod target", "⏳",  # ⏳
]


def main() -> int:
    print(f"{B}Arc S - DR claims backed (R-lens keystone, no false-sense doc){X}")
    print("=" * 64)
    if not DOC.exists():
        print(f"  {R}FAIL{X}  RTO_RPO_DECLARATION.md missing"); return 1
    text = DOC.read_text(encoding="utf-8", errors="replace")

    # The per-data-class rows look like: | **Class** | examples | RTO | RPO | mechanism |
    rows = re.findall(r"^\|\s*\*\*(.+?)\*\*\s*\|.*?\|.*?\|.*?\|(.+?)\|\s*$", text, re.MULTILINE)
    unbacked = []
    checked = 0
    for cls, mech in rows:
        m = mech.strip().lower()
        if not m:
            continue
        checked += 1
        if not any(tok in m for tok in BACKED):
            unbacked.append((cls.strip(), mech.strip()))

    print(f"  scanned {checked} data-class recovery mechanism(s)")
    for cls, mech in unbacked:
        print(f"  {R}UNBACKED{X}  {cls}: \"{mech[:70]}\" — no implementation + not marked a prod target")

    status_ok = "Implementation status" in text
    print(f"  {(G+'PASS'+X) if status_ok else (R+'FAIL'+X)}  Implementation-status section present")

    if not checked:
        print(f"  {Y}WARN{X}  no data-class rows parsed (doc format changed?) — treat as fail-safe")
        return 1
    if unbacked or not status_ok:
        print(f"\n{R}{B}  DR-CLAIMS: FAIL{X} - {len(unbacked)} unbacked recovery claim(s); fix the impl or mark ⏳ prod-target.")
        return 1
    print(f"\n{G}{B}  DR-CLAIMS: PASS{X} - every declared recovery mechanism is implemented or marked a prod target.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
