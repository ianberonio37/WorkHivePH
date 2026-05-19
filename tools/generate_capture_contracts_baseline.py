"""
Generate canonical/capture_contracts.json baseline from phantom_captures_report.

Reads the latest phantom captures audit and emits a skeleton entry for every
alive capture. Each skeleton has the discovered name + the page(s) it was
captured on; the team backfills `field_kind`, `written_to`, `contract`, and
`description` per surface as they're touched.

Preserves any HAND-WRITTEN entries already in capture_contracts.json
(matched on capture_id) so re-running won't clobber manual work — it only
APPENDS new skeletons for unregistered captures.

Run after every phantom_captures audit:
  python tools/audit_phantom_captures.py
  python tools/generate_capture_contracts_baseline.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_PATH = ROOT / "canonical" / "capture_contracts.json"
PHANTOM_PATH = ROOT / "phantom_captures_report.json"


def main() -> int:
    if not PHANTOM_PATH.exists():
        print(f"FAIL: {PHANTOM_PATH.name} missing — run audit_phantom_captures.py first")
        return 2

    phantom = json.loads(PHANTOM_PATH.read_text(encoding="utf-8"))
    if not CONTRACTS_PATH.exists():
        print(f"FAIL: {CONTRACTS_PATH.name} missing")
        return 2

    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    existing = contracts.get("captures") or []
    existing_ids = {c.get("capture_id") for c in existing}

    new_count = 0
    skipped_existing = 0
    for name, info in (phantom.get("by_name") or {}).items():
        if info.get("status") != "alive":
            continue
        if name in existing_ids:
            skipped_existing += 1
            continue
        # Build skeleton entry. Field kind heuristically inferred from the
        # capture name suffix when possible (-input, -select, -textarea).
        sites = sorted({s["file"] for s in info.get("capture_sites", [])})
        field_kind = "form"
        if "-input" in name.lower():
            field_kind = "form (input)"
        elif "-select" in name.lower() or name.lower().endswith("-status"):
            field_kind = "form (select)"
        elif "-textarea" in name.lower() or "-notes" in name.lower():
            field_kind = "form (textarea)"

        existing.append({
            "capture_id":  name,
            "surfaces":    sites,
            "field_kind":  field_kind,
            "written_to":  [],
            "contract":    {},
            "description": "(baseline skeleton — backfill description, written_to columns, and value contract)",
            "added_in":    "auto-generated baseline 2026-05-20"
        })
        new_count += 1

    contracts["captures"] = sorted(existing, key=lambda c: c.get("capture_id", ""))
    CONTRACTS_PATH.write_text(json.dumps(contracts, indent=2), encoding="utf-8")

    print(f"Capture-contracts baseline updated:")
    print(f"  existing entries (preserved): {skipped_existing}")
    print(f"  new skeletons added:          {new_count}")
    print(f"  total entries:                {len(existing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
