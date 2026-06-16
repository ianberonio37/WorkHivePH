"""
Connection-Surface Discovery (Maturity Phase 1, 2026-06-16).
=============================================================
Closes the (LB, G-1) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 —
the auto-discovery / "we forgot to budget this" gate for the scaling layer.

Every surface that opens a realtime channel is a held connection that counts
against the project ceiling (1000). When a new surface starts subscribing,
it must be *consciously registered* in the connection-surface baseline so its
load is accounted for in CAPACITY_PLAN. An unregistered new connection surface
is exactly the "we forgot to wire this in" failure the G-1 layer exists to catch.

Reads capacity_signals_report.json (auto-runs mine_capacity_signals.py if absent).

Output:  connection_surface_discovery_report.json
Baseline: connection_surface_baseline.json   (the registered surface set)

Exit code:
  0  PASS (no unregistered connection surface)
  1  FAIL (a new subscribing surface is not in the baseline)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SIGNALS = ROOT / "capacity_signals_report.json"
MINER   = ROOT / "tools" / "mine_capacity_signals.py"
REPORT   = ROOT / "connection_surface_discovery_report.json"
BASELINE = ROOT / "connection_surface_baseline.json"

CHECK_NAMES = ["connection_surface_discovery"]
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _signals() -> dict:
    if not SIGNALS.exists() and MINER.exists():
        subprocess.run([sys.executable, str(MINER)], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    return _load(SIGNALS) or {}


def main() -> int:
    sig = _signals()
    # a connection surface = a file that actually subscribes (holds a channel)
    current = sorted({s["file"] for s in sig.get("surfaces", []) if s.get("subscribes", 0) > 0})

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = {"surfaces": current}
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    registered = set(base.get("surfaces", []))
    unregistered = [f for f in current if f not in registered]
    removed = [f for f in registered if f not in set(current)]

    # prune removed surfaces from the baseline (descending is always fine)
    if removed and not first_lock:
        base["surfaces"] = sorted(registered - set(removed))
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current_surfaces": current, "registered": sorted(registered),
        "unregistered": unregistered, "removed": removed, "first_lock": first_lock,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Connection-Surface Discovery (LB, G-1){RESET}")
    print(f"  subscribing surfaces: {len(current)}  (registered {len(registered)})")
    if removed:
        print(f"{YEL}  pruned {len(removed)} removed surface(s) from baseline.{RESET}")
    if first_lock:
        print(f"{YEL}  baseline locked with {len(current)} surface(s) (first run).{RESET}")
    if unregistered:
        print(f"{RED}FAIL: {len(unregistered)} unregistered connection surface(s):{RESET}")
        for f in unregistered:
            print(f"  - {f}  (new subscriber — register in connection_surface_baseline.json after confirming CAPACITY_PLAN headroom)")
        return 1
    print(f"{GREEN}PASS — every subscribing surface is registered + budgeted.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
