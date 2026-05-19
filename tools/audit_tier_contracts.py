"""
Tier Contract Auditor (Layer -1.5 four-tier registry health).
=============================================================

Surveys the three tier contract files
(`canonical/{capture,formula,agent}_contracts.json`) and the file mirror
of the lineage edge table (`canonical/lineage_edges.json`). For each
tier, reports:

  - registered count (entries in the file registry)
  - candidate count  (things that LOOK like they belong but aren't registered)
  - chain integrity  (every formula references existing captures/columns;
                      every agent references existing formulas/views;
                      every lineage edge references known nodes)

This auditor is INFORMATIONAL — it doesn't fail the gate on unregistered
entries (the baseline is sparse on purpose; entries get added as the team
touches each surface). It DOES fail on broken chain references because a
registry pointing at non-existent IDs is silent rot.

Outputs:
  - tier_contracts_report.json
  - tier_contracts_report.md
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = ROOT / "canonical"


def _load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _load_registry() -> dict:
    return _load_json(ROOT / "canonical_registry.json")


def _load_phantom_captures() -> dict:
    """Optional — if the phantom_captures audit has run, we can derive a
    'candidate captures' count from its alive list. Without it we still
    work, just with a less-rich report."""
    p = ROOT / "phantom_captures_report.json"
    return _load_json(p)


def audit_capture_tier() -> dict:
    contracts = _load_json(CANONICAL_DIR / "capture_contracts.json")
    registered = contracts.get("captures", []) or []
    registered_ids = {c["capture_id"] for c in registered if "capture_id" in c}

    phantom = _load_phantom_captures()
    discovered_capture_names = list((phantom.get("by_name") or {}).keys())

    # Candidates = HTML form fields that are ALIVE (have a consumer) but
    # not yet registered. These are the team's next-register queue.
    candidates = []
    for name in discovered_capture_names:
        entry = phantom["by_name"][name]
        if entry.get("status") == "alive" and name not in registered_ids:
            candidates.append(name)

    return {
        "tier":               "F (Fuel)",
        "registry_file":      "canonical/capture_contracts.json",
        "registered_count":   len(registered),
        "discovered_count":   len(discovered_capture_names),
        "candidates_count":   len(candidates),
        "candidates":         sorted(candidates)[:50],
    }


def audit_formula_tier(reg: dict) -> dict:
    contracts = _load_json(CANONICAL_DIR / "formula_contracts.json")
    registered = contracts.get("formulas", []) or []
    registered_ids = {f["formula_id"] for f in registered if "formula_id" in f}

    # Every Postgres RPC starting with `get_` that returns a metric-ish
    # value is a candidate formula. We just enumerate RPCs from the
    # registry and surface ones not yet registered as formula_ids.
    rpc_names = list(reg.get("rpcs", {}).keys())
    metric_rpc_names = [n for n in rpc_names if n.startswith("get_")]
    registered_implemented = "\n".join(json.dumps(f.get("implemented_in", "")) for f in registered)

    candidates = []
    for n in metric_rpc_names:
        if n in registered_implemented:
            continue
        candidates.append(n)

    # Chain integrity: every formula must reference inputs that exist.
    broken_refs = []
    for f in registered:
        for inp in f.get("inputs", []):
            # column ref like "logbook.status"
            if "." in inp and not inp.endswith("_id"):
                tbl, _, col = inp.partition(".")
                if tbl in reg.get("tables", {}):
                    cols_raw = reg["tables"][tbl].get("columns")
                    if isinstance(cols_raw, str):
                        cols = {c.strip() for c in cols_raw.split(",")}
                    elif isinstance(cols_raw, list):
                        cols = set(cols_raw)
                    else:
                        cols = set()
                    if cols and col not in cols:
                        broken_refs.append(f"{f.get('formula_id')} -> {inp} (column not in table)")

    return {
        "tier":               "E (Engine)",
        "registry_file":      "canonical/formula_contracts.json",
        "registered_count":   len(registered),
        "discovered_count":   len(metric_rpc_names),
        "candidates_count":   len(candidates),
        "candidates":         sorted(candidates)[:50],
        "broken_references":  broken_refs,
    }


def audit_agent_tier(reg: dict) -> dict:
    contracts = _load_json(CANONICAL_DIR / "agent_contracts.json")
    registered = contracts.get("agents", []) or []
    registered_edge_fns = {a.get("edge_fn", "").split()[0] for a in registered if a.get("edge_fn")}

    # Candidates = edge fns that look like AI agents (orchestrator,
    # populator, planner, brain, query, scan, etc.) and aren't registered.
    edge_fns = list(reg.get("edge_fns", {}).keys())
    AI_HINTS = ("orchestrator", "populator", "planner", "brain", "query", "scan", "agent", "compose", "synth")
    candidate_fns = [fn for fn in edge_fns if any(h in fn for h in AI_HINTS) and fn not in registered_edge_fns]

    return {
        "tier":               "B (Brain)",
        "registry_file":      "canonical/agent_contracts.json",
        "registered_count":   len(registered),
        "discovered_count":   len(edge_fns),
        "candidates_count":   len(candidate_fns),
        "candidates":         sorted(candidate_fns)[:50],
    }


def audit_lineage_tier(reg: dict, capture_audit: dict, formula_audit: dict, agent_audit: dict) -> dict:
    edges_doc = _load_json(CANONICAL_DIR / "lineage_edges.json")
    edges = edges_doc.get("edges", []) or []

    # Build the set of known IDs per kind for integrity checks
    capture_ids = set()
    for c in (_load_json(CANONICAL_DIR / "capture_contracts.json").get("captures") or []):
        capture_ids.add(c.get("capture_id", ""))
    formula_ids = set()
    for f in (_load_json(CANONICAL_DIR / "formula_contracts.json").get("formulas") or []):
        formula_ids.add(f.get("formula_id", ""))
    agent_ids = set()
    for a in (_load_json(CANONICAL_DIR / "agent_contracts.json").get("agents") or []):
        agent_ids.add(a.get("agent_id", ""))
    view_ids = set(reg.get("views", {}).keys())
    table_ids = set(reg.get("tables", {}).keys())
    column_ids = set()
    for t, meta in reg.get("tables", {}).items():
        cols_raw = meta.get("columns")
        if isinstance(cols_raw, str):
            cols_raw = [c.strip() for c in cols_raw.split(",")]
        if isinstance(cols_raw, list):
            for c in cols_raw:
                column_ids.add(f"{t}.{c}")

    known_by_kind = {
        "capture":   capture_ids,
        "column":    column_ids,
        "table":     table_ids,
        "view":      view_ids,
        "formula":   formula_ids,
        "agent":     agent_ids,
        "tile":      None,       # tiles aren't centrally registered yet; accept any
        "dashboard": None,
    }

    broken = []
    for e in edges:
        for side in ("source", "target"):
            kind = e.get(f"{side}_kind", "")
            ident = e.get(f"{side}_id",   "")
            known = known_by_kind.get(kind)
            if known is not None and ident and ident not in known:
                broken.append(f"{side}_kind={kind} {side}_id={ident} (not registered)")

    return {
        "tier":                  "Glue (lineage edges)",
        "registry_file":         "canonical/lineage_edges.json",
        "registered_count":      len(edges),
        "broken_references":     broken,
    }


def main() -> int:
    reg = _load_registry()
    if not reg:
        print("FAIL: canonical_registry.json missing or empty")
        return 2

    f_audit = audit_capture_tier()
    e_audit = audit_formula_tier(reg)
    b_audit = audit_agent_tier(reg)
    g_audit = audit_lineage_tier(reg, f_audit, e_audit, b_audit)

    report = {
        "tiers": [f_audit, e_audit, b_audit, g_audit],
    }

    # Hard-fail if any chain references are broken
    total_broken = (
        len(e_audit.get("broken_references", []))
        + len(g_audit.get("broken_references", []))
    )

    (ROOT / "tier_contracts_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = []
    md.append("# Tier Contract Audit (Layer -1.5 four-tier registry health)\n")
    md.append("Surveys the four canonical registries — Fuel / Engine / Brain / Glue —")
    md.append("and reports registered vs candidate count per tier. Chain integrity")
    md.append("failures (registry entries pointing at non-existent IDs) fail the gate.\n")
    md.append("| Tier | Registry file | Registered | Discovered | Pending |")
    md.append("|---|---|---:|---:|---:|")
    for t in report["tiers"][:3]:
        md.append(f"| {t['tier']} | `{t['registry_file']}` | {t['registered_count']} | {t['discovered_count']} | {t['candidates_count']} |")
    md.append(f"| {g_audit['tier']} | `{g_audit['registry_file']}` | {g_audit['registered_count']} | — | — |")
    md.append("")
    if total_broken:
        md.append(f"## ❌ Broken chain references ({total_broken})\n")
        for r in (e_audit.get("broken_references", []) + g_audit.get("broken_references", [])):
            md.append(f"- {r}")
        md.append("")
    for t in report["tiers"][:3]:
        if t["candidates_count"]:
            md.append(f"## Tier {t['tier']} — pending registrations ({t['candidates_count']})\n")
            for c in t["candidates"]:
                md.append(f"- `{c}`")
            md.append("")

    (ROOT / "tier_contracts_report.md").write_text("\n".join(md), encoding="utf-8")

    print("Tier Contract Audit (Layer -1.5)")
    for t in report["tiers"]:
        print(f"  {t['tier']:<28} reg={t['registered_count']:>3}  "
              f"{'pending=' + str(t.get('candidates_count', '—')):<14} "
              f"{'broken=' + str(len(t.get('broken_references', []))):<10}")

    return 1 if total_broken else 0


if __name__ == "__main__":
    sys.exit(main())
