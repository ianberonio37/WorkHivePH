"""validate_dayplanner.py - Phase 1.9 of STRATEGIC_ROADMAP.md.

Architectural contract gate for dayplanner.html. The Day Planner is the only
surface that holds the worker's personal-schedule contract; the user has
explicitly flagged it as 'already built' (memory: project_lifeplanner) so
this validator's job is to prevent regressions, not gate new features.

Layers:
  L1  dayplanner.html exists on disk
  L2  Four mode tabs: DILO, WILO, MILO, YILO (id + switchView wiring)
  L3  schedule_items reads/writes go through db.from('schedule_items')
  L4  dayplanner.html is referenced from nav-hub.js (TOOLS array)
  L5  worker-scoped reads use restoreIdentityFromSession (auth-aware)

Skills consulted:
  frontend (tab pattern, view-switching contract)
  multitenant-engineer (worker-scoped reads must filter by worker_name)
  qa-tester (regression catcher rather than new feature gate)
"""
from __future__ import annotations
import json, re, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent
PAGE = ROOT / "dayplanner.html"
NAV_HUB = ROOT / "nav-hub.js"

LAYERS = [
    {"layer": "L1", "label": "dayplanner.html exists on disk"},
    {"layer": "L2", "label": "Four mode tabs: DILO + WILO + MILO + YILO"},
    {"layer": "L3", "label": "schedule_items reads/writes present"},
    {"layer": "L4", "label": "dayplanner.html referenced from nav-hub.js"},
    {"layer": "L5", "label": "restoreIdentityFromSession used (auth-aware)"},
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def run() -> dict:
    issues: list[dict] = []

    if not PAGE.exists():
        issues.append({"check": "l1", "layer": "L1",
                       "reason": "dayplanner.html not found."})
        return {"validator": "dayplanner", "total_checks": len(LAYERS),
                "passed": 0, "failed": len(LAYERS), "warned": 0,
                "layers": LAYERS, "issues": issues, "warnings": []}

    src = _read(PAGE)

    # L2: tab ids + switchView wiring
    for mode in ("dilo", "wilo", "milo", "yilo"):
        if f"id=\"tab-{mode}\"" not in src and f"id='tab-{mode}'" not in src:
            issues.append({"check": f"l2_tab_{mode}", "layer": "L2",
                           "reason": f"tab-{mode} button missing. Mode "
                                     f"{mode.upper()} not reachable."})
        if f"switchView('{mode}')" not in src and f'switchView("{mode}")' not in src:
            issues.append({"check": f"l2_switch_{mode}", "layer": "L2",
                           "reason": f"switchView('{mode}') call missing. Mode "
                                     f"{mode.upper()} cannot be activated."})

    # L3: schedule_items
    if "schedule_items" not in src:
        issues.append({"check": "l3", "layer": "L3",
                       "reason": "schedule_items not referenced. Day planner "
                                 "cannot read/write tasks."})

    # L4: nav-hub linkage
    if NAV_HUB.exists():
        nav = _read(NAV_HUB)
        if "dayplanner.html" not in nav:
            issues.append({"check": "l4", "layer": "L4",
                           "reason": "dayplanner.html not in nav-hub.js TOOLS array. "
                                     "Worker cannot reach it from nav."})
    else:
        issues.append({"check": "l4_nav_missing", "layer": "L4",
                       "reason": "nav-hub.js not found."})

    # L5: restoreIdentityFromSession
    if "restoreIdentityFromSession" not in src:
        issues.append({"check": "l5", "layer": "L5",
                       "reason": "restoreIdentityFromSession not used. Falling back "
                                 "to raw localStorage breaks Supabase Auth-gated "
                                 "RLS on schedule_items."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "dayplanner", "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nDay Planner Validator ({len(out['layers'])}-layer)")
    print("=" * 55)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "dayplanner_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
