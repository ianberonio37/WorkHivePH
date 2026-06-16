"""
Health-Surface Discovery (Maturity Phase 1, 2026-06-16).
=========================================================
Closes the (AV, G-1) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — the
readiness auto-discovery gate for the Availability layer.

validate_health_endpoint.py (G0) enforces /health on a CURATED load-bearing
set. This gate is the complement: a forward-only ratchet over the count of ALL
edge fns WITHOUT a /health probe. When a new fn ships without /health the count
rises above baseline and this FAILs — forcing a conscious decision (add the
probe, or re-baseline after confirming the fn is genuinely not load-bearing).
That is the "a new readiness surface appeared and we forgot to wire it" catch.

Reads health_surface_report.json (auto-runs mine_health_surface.py if absent).

Output:  health_surface_discovery_report.json
Baseline: health_surface_baseline.json   (without_health count; only descends)

Exit code:
  0  PASS (no new health-less fn beyond baseline)
  1  FAIL (without_health count regressed up)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SURFACE = ROOT / "health_surface_report.json"
MINER   = ROOT / "tools" / "mine_health_surface.py"
REPORT   = ROOT / "health_surface_discovery_report.json"
BASELINE = ROOT / "health_surface_baseline.json"

CHECK_NAMES = ["health_surface_discovery"]
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _surface() -> dict:
    if not SURFACE.exists() and MINER.exists():
        subprocess.run([sys.executable, str(MINER)], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    return _load(SURFACE) or {}


def main() -> int:
    surf = _surface()
    without = sorted(surf.get("without_health_fns", []))
    cur = len(without)

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = {"without_health": cur, "fns": without}
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
    baseline_n = int(base.get("without_health", cur))
    new_fns = [f for f in without if f not in set(base.get("fns", []))]

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "without_health": cur, "baseline": baseline_n,
        "new_healthless_fns": new_fns, "first_lock": first_lock,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Health-Surface Discovery (AV, G-1){RESET}")
    print(f"  edge fns without /health: {cur}  (baseline {baseline_n})")
    if first_lock:
        print(f"{YEL}  baseline locked at {cur} (first run).{RESET}")
    if cur > baseline_n:
        print(f"{RED}FAIL: regressed +{cur - baseline_n} above baseline — a new fn shipped without /health:{RESET}")
        for f in new_fns:
            print(f"  - {f}  (add /health, or re-baseline if genuinely not load-bearing)")
        return 1
    if cur < baseline_n:
        base["without_health"] = cur; base["fns"] = without
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
        print(f"{GREEN}PASS: readiness tightened {baseline_n} → {cur}.{RESET}")
        return 0
    print(f"{GREEN}PASS — no new health-less surface.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
