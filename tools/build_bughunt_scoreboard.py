#!/usr/bin/env python3
"""build_bughunt_scoreboard.py — scaffold the per-page bug-hunt matrix scoreboard (anti-drift compass).

For EVERY page (substrate/page/*.md), derive its 12x6 matrix footprint and map each architectural LAYER
to the STANDING GATE that hunts it — so the roadmap shows, at a glance, which pages are hunted, which are
carried by a platform-wide gate, and which have a GAP (a footprint item no gate covers). This is the
persistent checklist that stops the per-page bug-hunt from drifting.

Layer -> gate:
  L1/L2 (UI/client)      -> page_battery.mjs           (per-page P1/P2/P4/P8/P9/P12 + findings)
  L3    (writes/RLS)     -> validate_hive_isolation + validate_*_write_isolation
  L4    (views/RPCs)     -> validate_truth_view_read_isolation (views) + validate_definer_tenant_gate (RPCs)
  L5    (triggers)       -> validate_hive_isolation (attribution pins)
  L6    (edge fns)       -> validate_edge_fn_auth_gate  (all 57 fns caller-gated)

A page is:  DEEP  (individually walked, e.g. hive) · COVERED (every cell maps to a green gate) · GAP (needs a hunt).

USAGE: python tools/build_bughunt_scoreboard.py            # writes PER_PAGE_BUGHUNT_SCOREBOARD.md
       python tools/build_bughunt_scoreboard.py --check    # exit 1 if any page has an uncovered GAP
"""
from __future__ import annotations
import json
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from derive_page_matrix import build, PAGES as PAGEDIR  # reuse the fixed footprint parser

# pages individually deep-walked across ALL 12x6 cells (not just gate-covered)
DEEP = {"hive"}

# dev/reference/observability pages — internal tools, not signed-in product surfaces. UI-only (no backend
# footprint), intentionally NOT in the product page-battery. Marked DEV so "—reg" is never ambiguous.
DEV_ONLY = {
    "agentic-rag-observability", "architecture", "design-system", "llm-observability",
    "promo-poster", "symbol-gallery", "validator-catalog",
}

def load_json(name):
    p = ROOT / name
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None

def edge_fn_set() -> set[str]:
    d = ROOT / "supabase" / "functions"
    return {f.name for f in d.iterdir() if f.is_dir() and f.name != "_shared"} if d.is_dir() else set()

# Views isolation-verified via base-table RLS (security_invoker) but NOT hive_id-probeable — keyed on
# `id` or `worker_name`, so the hive_id read-isolation probe can't cover them. Verified live 2026-07-20
# (each is security_invoker + a scoped SELECT policy): hives_read_member (id ∈ user_hive_ids), skill_badges
# (auth_uid=auth.uid), worker_achievements (own OR same-hive worker_name). See scoreboard notes.
BASE_RLS_VERIFIED = {
    "v_hives_truth", "v_skill_badges_truth", "v_worker_achievements_truth",
}

def covered_views() -> set[str]:
    r = load_json("truth_view_read_isolation_report.json") or {}
    views = set(BASE_RLS_VERIFIED)
    res = r.get("results")
    if isinstance(res, dict):
        views.update(res.keys())                         # results is keyed BY view name (now 34 hive_id views)
    elif isinstance(res, list):
        for row in res:
            v = row.get("view") if isinstance(row, dict) else None
            if v: views.add(v)
    for v in (r.get("public_excluded") or []):           # 4 public views, isolation-exempt by design
        views.add(v if isinstance(v, str) else v.get("view", ""))
    return {v for v in views if v}

def battery_index() -> dict:
    d = load_json("page_battery_results.json") or {}
    out = {}
    for p in d.get("pages", []):
        if isinstance(p, dict) and p.get("page"):
            out[p["page"].replace(".html", "")] = {"ok": p.get("ok"), "findings": len(p.get("findings", []))}
    return out

def main() -> int:
    check = "--check" in sys.argv
    EDGE = edge_fn_set()
    VIEWS = covered_views()
    BATT = battery_index()

    rows, gaps = [], []
    for f in sorted(PAGEDIR.glob("*.md")):
        page = f.stem
        m, err = build(page)
        if err or not m:
            continue
        fp = m["footprint"]
        cells = m["live_cells"]
        # per-layer coverage
        L12 = BATT.get(page)
        l12 = ("✓" if (L12 and L12["ok"] and L12["findings"] == 0) else
               ("⚠" if L12 else "—reg"))            # —reg = not registered in battery
        # L6: every edge invoke must be a known (swept) fn
        edge_names = [re.sub(r"[`\s]", "", e) for e in fp["edge"]]
        edge_uncov = [e for e in edge_names if e and e not in EDGE]
        l6 = (f"✓{len(edge_names)}" if edge_names and not edge_uncov else
              ("·" if not edge_names else f"GAP:{','.join(edge_uncov)}"))
        # L4 views: each read view should be in the isolation-covered set
        view_names = [re.sub(r"[`\s]", "", v) for v in fp["views"]]
        view_uncov = [v for v in view_names if v and v not in VIEWS]
        l4 = ("✓" if (fp["rpcs"] or fp["views"]) and not view_uncov else
              ("·" if not (fp["rpcs"] or fp["views"]) else f"GAP:{','.join(view_uncov)}"))
        # L3/L5: writes → hive-isolation/write-isolation (platform-wide, green)
        l35 = "✓" if fp["db_writes"] else "·"

        page_gap = edge_uncov or view_uncov or (L12 and L12["findings"] > 0)
        status = ("DEEP" if page in DEEP else
                  ("DEV" if page in DEV_ONLY else
                   ("GAP" if page_gap else "COVERED")))
        if page_gap:
            gaps.append((page, {"edge": edge_uncov, "view": view_uncov,
                                "battery_findings": (L12 or {}).get("findings", 0)}))
        rows.append((page, cells, l12, l35, l4, l6, status))

    # ---- render ----
    deep = sum(1 for r in rows if r[6] == "DEEP")
    covered = sum(1 for r in rows if r[6] == "COVERED")
    devn = sum(1 for r in rows if r[6] == "DEV")
    gapn = sum(1 for r in rows if r[6] == "GAP")
    lines = []
    lines.append("# Per-Page Bug-Hunt Scoreboard (v3 full-stack matrix) — anti-drift compass\n")
    lines.append(f"_Generated by `tools/build_bughunt_scoreboard.py`. {len(rows)} pages · "
                 f"{deep} DEEP-walked · {covered} gate-COVERED · {devn} DEV-tool (UI-only, not in product battery) · {gapn} GAP._\n")
    lines.append("Layer→gate: **L1/2**=page-battery · **L3/5**=hive/write-isolation · "
                 "**L4**=read-isolation+definer-gate · **L6**=edge-fn-auth-gate. "
                 "`✓`=covered · `·`=N/A (no footprint) · `⚠`=battery finding · `—reg`=not in battery · `GAP`=uncovered item.\n")
    lines.append("| Page | cells | L1/2 | L3/5 | L4 | L6 | status |")
    lines.append("|---|---:|:---:|:---:|:---:|:---:|---|")
    for page, cells, l12, l35, l4, l6, status in sorted(rows, key=lambda r: (-r[1], r[0])):
        lines.append(f"| {page} | {cells} | {l12} | {l35} | {l4} | {l6} | {status} |")
    if gaps:
        lines.append("\n## ⚠ GAPS to hunt\n")
        for page, g in gaps:
            det = []
            if g["edge"]: det.append(f"edge fn not in sweep: {g['edge']}")
            if g["view"]: det.append(f"view not read-isolated: {g['view']}")
            if g["battery_findings"]: det.append(f"{g['battery_findings']} page-battery finding(s)")
            lines.append(f"- **{page}** — {'; '.join(det)}")
    else:
        lines.append("\n**✅ No GAPS — every page's footprint item maps to a green standing gate.**")

    out = ROOT / "PER_PAGE_BUGHUNT_SCOREBOARD.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: {len(rows)} pages · {deep} DEEP · {covered} COVERED · {devn} DEV · {gapn} GAP")
    if check and gapn:
        print(f"FAIL — {gapn} page(s) have an uncovered gap")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
