"""
Project Manager — Prescriptive Phase
Critical path (CPM via networkx), slack analysis, fast-track candidates.

Standards:
    PMBOK 7th ed. §6.5.2.2 — Critical Path Method
    AACE 24R-03 — Forensic Schedule Analysis
    networkx documentation — DAG longest path, topological sort

CPM mechanics (forward + backward pass via networkx):
    - Build a DiGraph of items where edges = predecessors.
    - For each item, duration = days(planned_end - planned_start) or
      ceil(estimated_hours / 8) if dates missing, defaulting to 1 day.
    - networkx.dag_longest_path() returns the critical path (longest chain).
    - Forward pass: ES, EF for each node.
    - Backward pass: LF, LS for each node.
    - Slack = LS - ES; critical = slack == 0.

Cycles in predecessor graph would silently miscompute under the old TS
hand-rolled implementation. networkx.find_cycle() raises a clean error
that the API surfaces as `cycle_warning` so the user can fix it.
"""

from datetime import datetime
from math import ceil


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _duration(it):
    """Duration in working days. Falls back to estimated_hours / 8 if no dates."""
    ds, de = _parse_date(it.get("planned_start")), _parse_date(it.get("planned_end"))
    if ds and de:
        days = max(1, int((de - ds).total_seconds() // 86400) + 1)
        return days
    if it.get("estimated_hours"):
        return max(1, ceil(float(it["estimated_hours"]) / 8))
    return 1


def calculate(inputs: dict) -> dict:
    items = inputs.get("items") or []
    if not items:
        return {
            "critical_path": {"item_ids": [], "total_days": 0, "slack_per_item": {}},
            "fast_track_candidates": [],
            "blockers": [],
            "cycle_warning": None,
        }

    try:
        import networkx as nx
    except ImportError:
        # Graceful fallback: no critical path, no slack analysis
        return {
            "critical_path": {"item_ids": [], "total_days": 0, "slack_per_item": {}},
            "fast_track_candidates": [],
            "blockers": [],
            "cycle_warning": "networkx not installed — install via pip",
        }

    # ── Build the DAG ────────────────────────────────────────────────────
    G = nx.DiGraph()
    by_id = {}
    for it in items:
        iid = it.get("id")
        if not iid:
            continue
        G.add_node(iid, duration=_duration(it), title=it.get("title", ""), status=it.get("status", "pending"))
        by_id[iid] = it

    for it in items:
        iid = it.get("id")
        if not iid or iid not in G:
            continue
        for pred in (it.get("predecessors") or []):
            if pred in by_id:
                G.add_edge(pred, iid)

    cycle_warning = None
    try:
        cycle = nx.find_cycle(G)
        cycle_warning = {
            "edges": [[u, v] for u, v in cycle],
            "message": "Predecessor graph has a cycle — fix it or critical path will not converge.",
        }
    except nx.NetworkXNoCycle:
        pass

    # ── Forward / backward pass ──────────────────────────────────────────
    if cycle_warning:
        # Skip CPM math when there's a cycle
        return {
            "critical_path": {"item_ids": [], "total_days": 0, "slack_per_item": {}},
            "fast_track_candidates": [],
            "blockers": _blockers(items),
            "cycle_warning": cycle_warning,
        }

    try:
        topo = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        return {
            "critical_path": {"item_ids": [], "total_days": 0, "slack_per_item": {}},
            "fast_track_candidates": [],
            "blockers": _blockers(items),
            "cycle_warning": {"message": "Topological sort failed — non-DAG structure"},
        }

    ES, EF = {}, {}
    for n in topo:
        preds = list(G.predecessors(n))
        ES[n] = max((EF[p] for p in preds), default=0)
        EF[n] = ES[n] + G.nodes[n]["duration"]

    project_finish = max(EF.values()) if EF else 0
    LF, LS = {}, {}
    for n in reversed(topo):
        succs = list(G.successors(n))
        LF[n] = min((LS[s] for s in succs), default=project_finish)
        LS[n] = LF[n] - G.nodes[n]["duration"]

    slack = {n: LS[n] - ES[n] for n in topo}
    critical_ids = sorted(
        [n for n in topo if slack[n] == 0],
        key=lambda n: ES[n],
    )

    # ── Fast-track candidates: items with the most slack are safest to fast-track ──
    sorted_by_slack = sorted(
        [(n, slack[n], by_id[n].get("title", "")) for n in topo if by_id[n].get("status") not in ("done", "skipped")],
        key=lambda t: -t[1],
    )
    fast_track = [
        {"id": n, "title": title, "slack_days": s}
        for n, s, title in sorted_by_slack[:5]
        if s > 0
    ]

    return {
        "critical_path": {
            "item_ids":        critical_ids,
            "total_days":      project_finish,
            "slack_per_item":  slack,
        },
        "fast_track_candidates": fast_track,
        "blockers":              _blockers(items),
        "cycle_warning":         cycle_warning,
    }


def _blockers(items):
    """Items currently blocked — surface the title + owner so the supervisor sees who's stuck."""
    return [
        {"id": it.get("id"), "title": it.get("title"), "owner": it.get("owner_name")}
        for it in items
        if it.get("status") == "blocked"
    ]
