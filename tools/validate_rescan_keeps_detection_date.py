#!/usr/bin/env python3
"""rescan-keeps-detection-date - a re-scan is not a new detection (2026-10-27).

failure-signature-scan upserted every signature on (hive_id, machine, rule_id) with detected_at = now, so a signature
standing for weeks read as found minutes ago and the alert hub's "20 newest" - ordered by detected_at - became a lottery
of whichever rows the last scan touched (20 of 39 in the hive it was measured on). The scan now reads the hive's
standing signatures first and keeps a current one's first detection date (and an acknowledgement it was given); a
resolved or expired one re-emerges dated now. Walked: two scans rewrote 33 of 34 rows (expires_at refreshed) and the
detection dates were byte-identical before and after.

ASSERTION: the signature row the scan upserts takes detected_at from what it found standing, never now() alone.

    python tools/validate_rescan_keeps_detection_date.py [--ref HEAD]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = "supabase/functions/failure-signature-scan/index.ts"


def _read(ref: str | None) -> str:
    if ref:
        return subprocess.run(["git", "show", f"{ref}:{FN}"], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8").stdout
    return (ROOT / FN).read_text(encoding="utf-8")


def check(src: str) -> list[str]:
    bad = []
    m = re.search(r"const row = \{([\s\S]*?)\};", src)
    if not m:
        return [f"{FN}: the upserted signature row could not be found - re-point this gate"]
    row = m.group(1)
    dm = re.search(r"detected_at:\s*([^\n]+)", row)
    if not dm:
        bad.append(f"{FN}: the upserted row sets no detected_at")
    elif re.fullmatch(r"\s*now\.toISOString\(\),?\s*", dm.group(1)):
        bad.append(f"{FN}: every re-scan stamps detected_at = now - a standing signature reads as just found")
    if "failure_signature_alerts" not in src or not re.search(r"\.select\(\"machine, rule_id, status, detected_at", src):
        bad.append(f"{FN}: the scan does not read the signatures already standing before it upserts")
    return bad


def main() -> int:
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    bad = check(_read(ref))
    print("rescan-keeps-detection-date - a re-scan keeps a standing signature's first detection date")
    for b in bad:
        print("  - " + b)
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
