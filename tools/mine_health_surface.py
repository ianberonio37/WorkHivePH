"""
Health-Surface Substrate Miner (Maturity Phase 1, 2026-06-16).
===============================================================
Closes the (AV, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

The Availability & Recovery layer's readiness depends on every load-bearing
edge fn exposing a /health probe (study §2: "no status page / untested
backups"). The G0 validator (validate_health_endpoint.py) enforces /health on
a CURATED load-bearing set; this miner reveals the SHAPE across ALL edge fns —
the readiness-coverage substrate that feeds the (AV, G-1) discovery ratchet.

Detection mirrors validate_health_endpoint.has_health() so the shape layer and
the G0 gate agree on what "/health present" means.

Inputs:
  supabase/functions/*/index.ts
  status.html, wh_health_status references

Output:
  health_surface_report.json

Exit code:
  0  always (informational miner — the SHAPE layer)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = ROOT / "supabase" / "functions"
STATUS_PAGE = ROOT / "status.html"
REPORT = ROOT / "health_surface_report.json"

CHECK_NAMES = ["health_surface"]


def has_health(text: str) -> bool:
    return (
        '"/health"' in text or "'/health'" in text
        or "../_shared/health.ts" in text
        or "endsWith('/health')" in text or 'endsWith("/health")' in text
    )


def main() -> int:
    fns: list[dict] = []
    if FN_DIR.exists():
        for entry in sorted(FN_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            index = entry / "index.ts"
            if not index.exists():
                continue
            text = index.read_text(encoding="utf-8", errors="replace")
            fns.append({
                "fn": entry.name,
                "has_health": has_health(text),
                "writes_health_status": "wh_health_status" in text,
            })

    total = len(fns)
    with_health = [f for f in fns if f["has_health"]]
    without = [f["fn"] for f in fns if not f["has_health"]]
    coverage = round(100 * len(with_health) / total, 1) if total else 0.0

    out = {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_fns": total,
        "with_health": len(with_health),
        "without_health": len(without),
        "coverage_pct": coverage,
        "status_page_present": STATUS_PAGE.exists(),
        "without_health_fns": sorted(without),
        "fns": sorted(fns, key=lambda x: x["fn"]),
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Health-surface miner: {total} edge fns scanned.")
    print(f"  /health coverage: {len(with_health)}/{total} ({coverage}%)")
    print(f"  status page present: {'yes' if STATUS_PAGE.exists() else 'NO'}")
    print(f"  without /health: {len(without)}")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
