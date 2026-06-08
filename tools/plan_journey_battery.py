"""
plan_journey_battery.py  —  ③ JOURNEY battery, the plan generator (Layer B).
================================================================================
Makes the Phase-3 persona findings EXECUTABLE. The journey battery (journey_
battery.js / window.__JOURNEY) asserts STATE + NUMBER continuity across the pages
of a job-to-be-done; this tool emits the concrete plan it runs — which pages, in
order, and which KPI to read at each step (as a real `[data-rag-tile=…] .sc-hero`
selector, validated against the Phase-1 inventory corpus) — plus the exact
Playwright-MCP `__JOURNEY.step()` calls. It NEVER drives a browser itself (that
is the live MCP step); it produces a deterministic, grounded test plan.

Each journey is anchored to a Phase-3 CONFUSING finding and the `sweep:ia:*`
candidate it corroborates, so a live continuity miss becomes EVIDENCE on an
existing queued proposal — closing the loop IA-Phase-1 → 2 → 3 → here.

KEY DOCTRINE point (same-NAMED ≠ same-DERIVATION): some journeys EXPECT a drift.
The approvals journey reads "Pending approval" on asset-hub (assets) and inventory
(parts) — a drift there CONFIRMS they are distinct subjects (the RELABEL finding),
it is not a bug. Each journey states its expected outcome so the live result is
interpreted correctly.

OUTPUT:
  - journey_battery_plan.md     — human plan + copy-paste MCP step() calls
  - journey_battery_plan.json   — machine plan (a live driver / spec consumes it)

USAGE:  python tools/plan_journey_battery.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "ia_inventory_corpus.json"

# ── journey registry — grounded in Phase-3 jobs-to-be-done + the tile inventory.
# Each step: (page, tile_key, kpi_name). The driver reads [data-rag-tile="key"]
# .sc-hero. `expect`: 'agree' (a real continuity assertion) | 'drift-confirms-
# distinct' (a drift is the EXPECTED proof the units are different subjects).
JOURNEYS = [
    {
        "id": "overdue-continuity",
        "name": "Find what maintenance is due/overdue (does the count agree across the pages a worker sees?)",
        "persona": "field/novice",
        "steps": [
            ("pm-scheduler.html", "pm-scheduler:overdue", "overdue"),
            ("dayplanner.html", "dayplanner:overdue_count", "overdue"),
        ],
        "expect": "agree",
        "tests": "Phase-3 'due/overdue' AMBIGUITY OF SOURCE — the overdue count is derived two ways "
                 "(per-asset v_pm_compliance_truth vs per-scope-item v_pm_scope_items_truth).",
        "candidates": ["sweep:ia:theme:late-overdue", "sweep:ia:theme:due-soon-upcoming"],
    },
    {
        "id": "risk-continuity",
        "name": "Find the highest-risk asset (do the risk lenses agree?)",
        "persona": "supervisor/novice",
        "steps": [
            ("predictive.html", "predictive:hot_assets", "at_risk"),
            ("asset-hub.html", "asset-hub:critical_assets", "at_risk"),
            ("alert-hub.html", "alert-hub:high_severity_alerts", "at_risk"),
        ],
        "expect": "agree",
        "tests": "Phase-3 'top risk' AMBIGUITY + CANONICAL UNREACHABLE (predictive is hidden). Risk is "
                 "shown as hot assets / critical assets / high-severity alerts — confirm whether these "
                 "are one number or three legitimately different lenses.",
        "candidates": ["sweep:ia:theme:risk-hot-critical"],
    },
    {
        "id": "approvals-distinct",
        "name": "See what's waiting for my approval (assets vs parts — SHOULD these differ?)",
        "persona": "supervisor/novice",
        "steps": [
            ("asset-hub.html", "asset-hub:pending_approval", "pending_approval"),
            ("inventory.html", "inventory:pending_approval", "pending_approval"),
        ],
        "expect": "drift-confirms-distinct",
        "tests": "Phase-2 RELABEL — same label 'Pending approval' on two pages with DIFFERENT subjects "
                 "(assets vs parts). A drift here is the EXPECTED proof they are distinct units (relabel, "
                 "don't consolidate); agreement would be a coincidence, not a contract.",
        "candidates": ["sweep:ia:relabel:pending-approval"],
    },
]

SELECTOR = '[data-rag-tile="{key}"] .sc-hero'


def slug(p: str) -> str:
    return p.replace(".html", "")


def main() -> int:
    if not CORPUS.exists():
        print(f"ERROR: {CORPUS.name} not found — run Phase 1 (survey_ia_redundancy.py) first.")
        return 1
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    # index every known tile so we can validate the journey steps are real.
    known = {}
    for page, e in corpus["corpus"].items():
        for u in e.get("infoUnits", []):
            if u.get("unitId"):
                known[u["unitId"]] = u.get("label")

    plans = []
    for j in JOURNEYS:
        steps = []
        for (page, key, kpi) in j["steps"]:
            ok = key in known
            steps.append({
                "page": page, "tile": key, "kpi": kpi,
                "selector": SELECTOR.format(key=key),
                "label": known.get(key), "exists": ok,
            })
        plans.append({**j, "steps": steps,
                      "all_tiles_exist": all(s["exists"] for s in steps)})

    (ROOT / "journey_battery_plan.json").write_text(json.dumps({
        "_doc": "③ Journey battery plan. Drive with journey_battery.js / window.__JOURNEY in Playwright MCP.",
        "journeys": plans,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # markdown
    L = []
    L.append("# Journey Battery Plan — ③ Journey altitude (executable continuity)\n")
    L.append("> Each journey drives a job-to-be-done across pages with `window.__JOURNEY`"
             " (journey_battery.js) and asserts **state + number continuity**. Anchored to a"
             " Phase-3 finding + the `sweep:ia:*` candidate it corroborates. SURFACE-only.\n")
    L.append("> **Install per page:** `browser_evaluate(fn = <journey_battery.js>)` then the step()"
             " call below. Run the page kernel (`__UFAI.run`) too — journey COMPOSES the page battery.\n")
    for p in plans:
        flag = "" if p["all_tiles_exist"] else "  ⚠️ (some tiles not in corpus — verify selectors)"
        L.append(f"## {p['name']}{flag}\n")
        L.append(f"- **Persona:** {p['persona']}  ·  **Expect:** `{p['expect']}`")
        L.append(f"- **Tests:** {p['tests']}")
        L.append(f"- **Corroborates:** {', '.join('`'+c+'`' for c in p['candidates'])}\n")
        L.append("```js")
        L.append('window.__JOURNEY.reset();')
        for s in p["steps"]:
            miss = "" if s["exists"] else "   // ⚠️ tile not found in corpus"
            L.append(f'// navigate → {s["page"]}, re-install journey_battery.js, then:')
            L.append(f'window.__JOURNEY.step("{slug(s["page"])}", {{ {s["kpi"]}: \'{s["selector"]}\' }});{miss}')
        L.append('window.__JOURNEY.verdict({ tol: 0.5 });')
        L.append("```")
        if p["expect"] == "drift-confirms-distinct":
            L.append("> **Interpretation:** a `journey-number-drift` here is EXPECTED and CONFIRMS the"
                     " two units are different subjects (relabel, do not consolidate). Agreement would be"
                     " coincidence.")
        else:
            L.append("> **Interpretation:** a `journey-number-drift` here is a real finding — the same"
                     " KPI disagrees across pages (verify same-derivation first, then it is a drift bug"
                     " that can show users a stale value). Feed the result onto the cited candidate.")
        L.append("")
    L.append("---")
    L.append("_State continuity (identity/role/hive constant) is asserted automatically by"
             " `verdict()` across all steps — no per-step config needed._")
    (ROOT / "journey_battery_plan.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    ok = sum(1 for p in plans if p["all_tiles_exist"])
    print(f"Journey battery plan -- {len(plans)} journeys ({ok} fully tile-validated)")
    for p in plans:
        mark = "ok" if p["all_tiles_exist"] else "CHECK"
        print(f"  [{mark}] {p['id']:22s} {len(p['steps'])} steps  expect={p['expect']}")
    print("  -> journey_battery_plan.md + .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
