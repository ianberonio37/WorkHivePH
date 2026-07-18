#!/usr/bin/env python3
# DEEPWALK-CELL: * D3
"""
validate_reactivity_wiring.py  --  Phase D anti-rot for INTERACTIVE_LINEAGE_ROADMAP.

Phase D ("edit here -> see there") had two build layers verified only by hand + a
DOM walk. This gate makes them PROVABLE + forward-only, deterministically:

  D1 (cross-surface RECEIPTS): every WRITE surface whose fields fan out to another page
     must emit a post-save receipt naming the ripple -- OR be explicitly dispositioned
     receipt-free because it has ZERO cross-page fan-out. The write-surface set is read
     from field_blast_radius.json (Phase A ground truth), so a NEW write surface that
     gains cross-page fan-out without a receipt FAILs (anti-rot). Receipt presence is
     verified by an exact declared marker substring in the page (not fragile prose).

  D2 (pre-commit IMPACT PREVIEW): every high-blast surface in field_impact_preview.json
     must (a) include impact-preview.js, and (b) have its SURFACE_ANCHORS save-button
     selector actually present in the page. The anchor map is parsed FROM impact-preview.js
     so the JS config is the single source of truth -- a stale anchor FAILs.

Severity: WARN by default (exit 0), surfaces gaps for review. --strict exits 1 on any gap.
Run: python tools/validate_reactivity_wiring.py [--strict]
"""
import json
import os
import re
import sys

# Windows cp1252 consoles crash encoding the checkmark/arrow glyphs we print (a fail message
# echoes a receipt marker that contains a Unicode tick). Force UTF-8 with a safe fallback so
# the gate reports its verdict instead of dying with a UnicodeEncodeError (a false FAIL).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLAST = os.path.join(ROOT, "field_blast_radius.json")
IMPACT = os.path.join(ROOT, "field_impact_preview.json")
IMPACT_JS = os.path.join(ROOT, "impact-preview.js")

# D1 receipt CONTRACT: write-surface -> a verbatim substring of its cross-surface receipt
# toast (verified present in <surface>.html). Each names the downstream ripple in plain
# user-voice. Extend when a new write surface gains cross-page fan-out.
RECEIPT_PRESENT = {
    "logbook":         "✓ Logged: updated",                          # `✓ Logged: updated ${_fx...}` (colon, no em-dash per no-em-dash gate)
    "inventory":       "Alert Hub stock alert",                                # OUT OF STOCK / restock -> alert + analytics
    "pm-scheduler":    "PM compliance recomputed",                            # `✓ PM done → PM compliance recomputed...`
    "asset-hub":       "feeds this asset",                                    # FMEA + Weibull -> risk score -> predictive/alert-hub/analytics
    "integrations":    "new work orders in Logbook",                          # cmms-sync -> logbook/analytics/shift-brain
    "project-manager": "linkable to assets from Logbook",                     # projects -> logbook/pm-scheduler/project-report
    "marketplace":     "goes live to buyers in the Marketplace",             # listing -> seller dashboard / buyers on approval
}

# Write surfaces verified to have ZERO cross-page fan-out -> correctly receipt-free
# (a receipt would claim effects that do not fire). Asserted to truly have 0 fan-out below.
RECEIPT_FREE = set()

# D4 (no snapshot KPI silently stale): the OWNER surface of each batch-computed snapshot
# must expose a freshness affordance -- a "recompute now" control OR a realtime
# subscription -- so the number is never silently a-day-stale. Consumer surfaces that
# only READ a canonical v_*_truth view load fresh on navigation (e.g. index home reads
# v_risk_truth), so freshness is owned upstream, not duplicated onto every reader.
# surface -> a verbatim freshness marker (recompute control or realtime channel).
D4_FRESH_OWNERS = {
    "analytics":   "recompute",            # analytics_snapshots: re-run via analytics-orchestrator
    "hive":        "computeBenchmarkNow",  # hive_benchmarks / network_benchmarks: recompute
    # predictive.html removed 2026-07-06 (folded into asset-hub); its asset_risk_scores freshness
    # ownership survives on asset-hub below ("updated live"), so the KPI is not orphaned.
    "asset-hub":   "updated live",          # asset_risk_scores: realtime risk gauge "Risk score updated live"
    "alert-hub":   ".channel(",            # amc_briefings / anomaly_signals: realtime
}


def write_surfaces():
    """surface -> {'fanout': total display fan-out, 'casc': fields with a causal cascade}
    for every page that has persisted (writable) fields, from Phase A blast radius."""
    blast = json.load(open(BLAST, encoding="utf-8"))
    agg = {}
    for f in blast.get("fields", []):
        s = f["surface"]
        a = agg.setdefault(s, {"fanout": 0, "casc": 0, "fields": 0})
        a["fields"] += 1
        a["fanout"] += f.get("display_fanout", 0)
        if f.get("causal_cascades"):
            a["casc"] += 1
    return agg


def parse_surface_anchors():
    """Parse SURFACE_ANCHORS {'page': '#sel', ...} from impact-preview.js (single source)."""
    txt = open(IMPACT_JS, encoding="utf-8").read()
    m = re.search(r"SURFACE_ANCHORS\s*=\s*\{([^}]*)\}", txt, re.DOTALL)
    anchors = {}
    if m:
        for k, v in re.findall(r"['\"]([a-z0-9-]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)):
            anchors[k] = v
    return anchors


def page_text(surface):
    p = os.path.join(ROOT, surface + ".html")
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else None


def main():
    strict = "--strict" in sys.argv
    fails = []
    surfaces = write_surfaces()

    # ── D1: receipt coverage over every write surface ──────────────────────────
    d1_ok = 0
    for s, a in sorted(surfaces.items()):
        has_fanout = a["fanout"] > 0 or a["casc"] > 0
        txt = page_text(s)
        if txt is None:
            continue  # not a standalone page (e.g. component) -> skip
        if has_fanout:
            marker = RECEIPT_PRESENT.get(s)
            if marker is None:
                fails.append(f"D1: write surface '{s}' has cross-page fan-out "
                             f"(fanout={a['fanout']}, cascade fields={a['casc']}) but NO receipt "
                             f"disposition. Add a cross-surface receipt + register its marker.")
            elif marker not in txt:
                fails.append(f"D1: '{s}' receipt marker not found in page: {marker!r} "
                             f"(receipt removed/changed -> the ripple is now silent).")
            else:
                d1_ok += 1
        else:  # zero fan-out -> must be receipt-free (and stay that way)
            if s in RECEIPT_PRESENT:
                d1_ok += 1  # has one anyway, fine
            else:
                RECEIPT_FREE.add(s)

    # ── D2: impact-preview wiring on every high-blast surface ──────────────────
    impact = json.load(open(IMPACT, encoding="utf-8"))
    high_blast = sorted(impact.get("surfaces", {}).keys())
    anchors = parse_surface_anchors()
    d2_ok = 0
    for s in high_blast:
        txt = page_text(s)
        if txt is None:
            fails.append(f"D2: high-blast surface '{s}' has no {s}.html.")
            continue
        if "impact-preview.js" not in txt:
            fails.append(f"D2: '{s}' is high-blast but does not include impact-preview.js.")
            continue
        sel = anchors.get(s)
        if not sel:
            fails.append(f"D2: '{s}' has no SURFACE_ANCHORS entry in impact-preview.js.")
            continue
        anchor_id = sel.lstrip("#")
        if f'id="{anchor_id}"' not in txt and f"id='{anchor_id}'" not in txt:
            fails.append(f"D2: '{s}' anchor {sel} not found in page (save button moved/renamed).")
            continue
        d2_ok += 1

    # ── D4: every snapshot-KPI OWNER surface is recompute-or-realtime fresh ────
    d4_ok = 0
    for s, marker in sorted(D4_FRESH_OWNERS.items()):
        txt = page_text(s)
        if txt is None:
            fails.append(f"D4: snapshot owner '{s}' has no {s}.html.")
        elif marker not in txt:
            fails.append(f"D4: snapshot owner '{s}' lost its freshness affordance "
                         f"(marker {marker!r} gone -> its snapshot KPI can go silently stale).")
        else:
            d4_ok += 1

    print("[reactivity_wiring]")
    print(f"  D1 write surfaces:           {len(surfaces)} "
          f"({d1_ok} with verified receipt, {len(RECEIPT_FREE)} receipt-free/zero-fanout)")
    print(f"  D2 high-blast surfaces:      {len(high_blast)} ({d2_ok} fully wired)")
    print(f"  D4 snapshot-KPI owners:      {len(D4_FRESH_OWNERS)} ({d4_ok} recompute-or-realtime fresh)")
    if fails:
        for f in fails:
            print("   - " + f)
        if strict:
            print("  FAIL (--strict): reactivity wiring gap(s) above.")
            return 1
        print("  WARN: surfaced for review (re-run with --strict to enforce).")
    else:
        print("  PASS: every write surface has a cross-surface receipt (or is zero-fanout) [D1], "
              "every high-blast surface has impact-preview wired [D2], and every snapshot-KPI "
              "owner is recompute-or-realtime fresh [D4].")
    return 0


if __name__ == "__main__":
    sys.exit(main())
