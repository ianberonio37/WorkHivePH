"""
__JOURNEY_TRACE -- the generic differential data-lineage nerve-probe (§13 P1)
=============================================================================
The LIVE engine §13 adds on top of the STATIC lineage auditors. A static
auditor proves a consumer EXISTS in code; this proves the rendered/computed
VALUE is CORRECT at every downstream terminus when a real input changes.

THE METHOD (§13.3, differential -- robust to pre-existing data):
  1. read BASELINE at every consumer terminus
  2. seed a KNOWN delta (a marked input row with a known value)
  3. re-read every consumer
  4. ASSERT the delta propagated with the CORRECT VALUE everywhere it lands
  5. CLEAN UP (delete the marked row; restore derived views)

It is a GENERIC engine, not a per-page script: a NERVE supplies the recipe
(target picker, baseline reads, seed, propagate, expected-delta assertions,
cleanup); the orchestration is shared. Logbook->MTTR is proof #1, never the
scope -- the same engine drives every input surface in lineage_map.json.

GROUND TRUTH: reads the REAL edge DB via `docker exec supabase_db_workhive
psql` -- NOT the postgres MCP, which has been observed pointing at a stale/
empty DB ("verify the DB, not the toast"; memento gotcha 2026-06-15).

★A real nerve property this surfaces: v_kpi_truth is a MATERIALIZED view
(hourly pg_cron refresh) -- MTTR does NOT move on insert; it has a designed
<=1h propagation latency. The probe asserts the staleness BEFORE refresh and
the correct value AFTER refresh -- both are part of the honest nerve.

Output: .tmp/journey_trace_<nerve>.json + a console verdict. Exit 0 = every
terminus propagated the correct value; exit 1 = a dead/wrong nerve.

Skills consulted: analytics-engineer (v_kpi_truth MTTR formula = AVG(downtime_
hours) over corrective entries in window), predictive-analytics (MTBF/MTTR
window semantics), data-engineer (differential DB-verified write->read),
qa-tester (seed/verify/cleanup pattern reused from flows/logbook_crud.py).
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
DB_CONTAINER = "supabase_db_workhive"

# Markers so seeded rows are always identifiable + cleanable, even if a run aborts.
JT_WORKER = "__journey_trace__"


def psql(sql: str) -> list[list[str]]:
    """Run SQL against the real edge DB; return rows as lists of string cells."""
    out = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip() or out.stdout.strip()}")
    rows = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(line.split("|"))
    return rows


def scalar(sql: str):
    rows = psql(sql)
    return rows[0][0] if rows and rows[0] else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _close(a, b, tol=0.05) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def bool_pg(v):
    """Parse psql boolean output ('t'/'f') to a Python bool (None if unknown)."""
    if v in ("t", "true", "T"):
        return True
    if v in ("f", "false", "F"):
        return False
    return None


# ───────────────────────────────────────────────────────────────────────────
# NERVE #1 -- logbook.downtime_hours -> MTTR / total_downtime / failures
# (Ian's worked example; the highest-signal proof of both axes).
# ───────────────────────────────────────────────────────────────────────────
def probe_logbook_mttr(delta: float = 6.0) -> dict:
    HIVE_MACHINE_SQL = """
        SELECT hive_id, machine FROM v_kpi_truth
        WHERE failures_30d >= 2 AND mttr_30d IS NOT NULL AND hive_id IS NOT NULL
        ORDER BY failures_30d DESC, machine LIMIT 1;"""
    tgt = psql(HIVE_MACHINE_SQL)
    if not tgt:
        return {"nerve": "logbook_downtime__mttr", "error": "no target (hive,machine) with corrective baseline"}
    hive, machine = tgt[0][0], tgt[0][1]
    where = (f"hive_id='{hive}' AND machine='{machine}' "
             f"AND maintenance_type='Breakdown / Corrective' "
             f"AND created_at >= NOW() - INTERVAL '30 days'")

    # ---- 1. BASELINE (raw 30d corrective + the materialized KPI row) ----
    raw = psql(f"SELECT count(*), COALESCE(sum(downtime_hours),0) FROM logbook WHERE {where};")[0]
    base_count, base_sum = int(raw[0]), _f(raw[1])
    mvb = psql(f"SELECT failures_30d, mttr_30d, total_downtime_30d FROM v_kpi_truth "
               f"WHERE hive_id='{hive}' AND machine='{machine}';")[0]
    base_failures, base_mttr, base_total = int(mvb[0]), _f(mvb[1]), _f(mvb[2])
    base_vlt = int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{hive}' AND machine='{machine}';"))

    # Expected post-seed values (the exact formula -- ROUND(...,1) like the MV).
    # ★Anchor ALL three on the RAW baseline (base_count/base_sum), NEVER the MV's
    # own failures_30d: the MV is stale-by-design (<=1h refresh) and the 30-day
    # window is a MOVING boundary (created_at >= NOW()-30d) -- a real entry can
    # age out between the MV's last refresh and now, so the stale MV count can
    # exceed the live raw count. After refresh the MV recomputes from the raw
    # window, so the raw baseline + seed is the correct post-refresh expectation.
    exp_failures = base_count + 1
    exp_total = round(base_sum + delta, 1)
    exp_mttr = round((base_sum + delta) / (base_count + 1), 1)

    marker = f"__JT__{uuid.uuid4().hex[:10]}"
    row_id = f"__jt__{uuid.uuid4().hex[:12]}"
    termini = []

    try:
        # ---- 2. SEED a known delta (a marked corrective entry) ----
        psql(f"""INSERT INTO logbook
            (id, worker_name, date, created_at, machine, hive_id, maintenance_type,
             downtime_hours, status, closed_at, problem, action)
            VALUES ('{row_id}', '{JT_WORKER}', NOW(), NOW(), '{machine}', '{hive}',
             'Breakdown / Corrective', {delta}, 'Closed', NOW(), '{marker}',
             'journey-trace differential seed');""")

        # ---- T1. D-layer: the row landed with the correct value ----
        d_row = psql(f"SELECT downtime_hours, status, maintenance_type FROM logbook WHERE problem='{marker}';")
        ok_d = bool(d_row) and _close(_f(d_row[0][0]), delta) and d_row[0][1] == "Closed"
        termini.append({"terminus": "D · logbook row", "layer": "D",
                        "measured": d_row[0] if d_row else None,
                        "expected": [delta, "Closed", "Breakdown / Corrective"], "ok": ok_d})

        # ---- T2. canonical: v_logbook_truth exposes the row with the value ----
        vlt = psql(f"SELECT downtime_hours FROM v_logbook_truth WHERE problem='{marker}';")
        ok_vlt = bool(vlt) and _close(_f(vlt[0][0]), delta)
        termini.append({"terminus": "canonical · v_logbook_truth", "layer": "D/view",
                        "measured": (vlt[0][0] if vlt else None), "expected": delta, "ok": ok_vlt})

        # ---- T3. STALENESS NERVE: MV must NOT have moved yet (<=1h latency) ----
        pre = psql(f"SELECT failures_30d FROM v_kpi_truth WHERE hive_id='{hive}' AND machine='{machine}';")
        pre_failures = int(pre[0][0]) if pre else None
        ok_stale = (pre_failures == base_failures)   # unchanged before refresh = correct designed latency
        termini.append({"terminus": "KPI staleness · v_kpi_truth pre-refresh (materialized, <=1h)",
                        "layer": "CA/latency", "measured": pre_failures,
                        "expected": f"{base_failures} (unchanged until refresh)", "ok": ok_stale})

        # ---- 3. PROPAGATE (refresh the materialized view) ----
        psql("SELECT refresh_v_kpi_truth();")

        # ---- 4. RE-READ + ASSERT the computed termini ----
        mva = psql(f"SELECT failures_30d, mttr_30d, total_downtime_30d FROM v_kpi_truth "
                   f"WHERE hive_id='{hive}' AND machine='{machine}';")[0]
        a_failures, a_mttr, a_total = int(mva[0]), _f(mva[1]), _f(mva[2])
        termini.append({"terminus": "KPI · v_kpi_truth.failures_30d (COUNT)", "layer": "CA/compute",
                        "measured": a_failures, "expected": exp_failures, "ok": a_failures == exp_failures})
        termini.append({"terminus": "KPI · v_kpi_truth.total_downtime_30d (SUM)", "layer": "CA/compute",
                        "measured": a_total, "expected": exp_total, "ok": _close(a_total, exp_total, 0.11)})
        termini.append({"terminus": "KPI · v_kpi_truth.mttr_30d (AVG -- the MTTR nerve)", "layer": "CA/compute",
                        "measured": a_mttr, "expected": exp_mttr, "ok": _close(a_mttr, exp_mttr, 0.11)})

    finally:
        # ---- 5. CLEANUP (always) + restore the derived view ----
        psql(f"DELETE FROM logbook WHERE worker_name='{JT_WORKER}';")
        try:
            psql("SELECT refresh_v_kpi_truth();")
        except Exception:
            pass

    all_ok = all(t["ok"] for t in termini)
    return {
        "nerve": "logbook_downtime__mttr",
        "field": "logbook.downtime_hours",
        "input_surface": "logbook",
        "target": {"hive_id": hive, "machine": machine},
        "delta": delta,
        "baseline": {"raw_count_30d": base_count, "raw_sum_30d": base_sum,
                     "mv_failures_30d": base_failures, "mv_mttr_30d": base_mttr,
                     "mv_total_downtime_30d": base_total, "v_logbook_truth_count": base_vlt},
        "termini": termini,
        "termini_total": len(termini),
        "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all_ok,
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #2 -- inventory qty_on_hand -> is_low_stock -> low_stock count.
# Different surface AND different transform shape: v_inventory_items_truth is a
# REGULAR view (live, no refresh) -- proves the engine generalizes past the
# materialized KPI case. low_stock is a REGISTERED kpi_source_registry metric,
# so verifying it flips a STATIC map path true (vs logbook which added new ones).
# ───────────────────────────────────────────────────────────────────────────
def probe_inventory_low_stock() -> dict:
    # Target: an item just above its min, so a small consumption crosses the line.
    TGT_SQL = """
        SELECT id, hive_id, qty_on_hand, min_qty FROM v_inventory_items_truth
        WHERE qty_on_hand > min_qty AND min_qty > 0 AND hive_id IS NOT NULL
        ORDER BY (qty_on_hand - min_qty) ASC, id LIMIT 1;"""
    tgt = psql(TGT_SQL)
    if not tgt:
        return {"nerve": "inventory_qty__low_stock", "error": "no item above its min_qty"}
    item_id, hive, qty0, minq = tgt[0][0], tgt[0][1], _f(tgt[0][2]), _f(tgt[0][3])
    delta = qty0 - minq            # consume the margin -> qty == min -> is_low_stock crosses true
    qty_new = qty0 - delta         # == minq

    base_low = bool_pg(scalar(f"SELECT is_low_stock FROM v_inventory_items_truth WHERE id='{item_id}';"))
    base_count = int(scalar(f"SELECT count(*) FROM v_inventory_items_truth WHERE hive_id='{hive}' AND is_low_stock;"))
    termini = []
    try:
        # SEED: the input is a parts consumption -> qty_on_hand drops by delta.
        # (canonical column the view reads; the real-user path is a consumption txn = a V-axis journey.)
        psql(f"UPDATE inventory_items SET qty_on_hand = qty_on_hand - {delta} WHERE id='{item_id}';")

        # T1. D-layer: the column dropped to the known value.
        d_qty = _f(scalar(f"SELECT qty_on_hand FROM inventory_items WHERE id='{item_id}';"))
        termini.append({"terminus": "D · inventory_items.qty_on_hand", "layer": "D",
                        "measured": d_qty, "expected": qty_new, "ok": _close(d_qty, qty_new)})

        # T2. canonical: the truth view recomputes is_low_stock (false -> true).
        v = psql(f"SELECT qty_on_hand, is_low_stock FROM v_inventory_items_truth WHERE id='{item_id}';")[0]
        v_qty, v_low = _f(v[0]), bool_pg(v[1])
        ok_flag = (v_low is True and base_low is False) and _close(v_qty, qty_new)
        termini.append({"terminus": "canonical · v_inventory_items_truth.is_low_stock (qty<=min)", "layer": "D/view",
                        "measured": {"qty": v_qty, "is_low_stock": v_low},
                        "expected": {"qty": qty_new, "is_low_stock": True, "was": base_low}, "ok": ok_flag})

        # T3. KPI low_stock count for the hive: +1 (registered metric; index/alert-hub/inventory/hive).
        a_count = int(scalar(f"SELECT count(*) FROM v_inventory_items_truth WHERE hive_id='{hive}' AND is_low_stock;"))
        termini.append({"terminus": "KPI · low_stock count (hive)", "layer": "compute",
                        "measured": a_count, "expected": base_count + 1, "ok": a_count == base_count + 1})
    finally:
        # CLEANUP: restore the exact original quantity.
        psql(f"UPDATE inventory_items SET qty_on_hand = {qty0} WHERE id='{item_id}';")

    return {
        "nerve": "inventory_qty__low_stock",
        "field": "inventory_items.qty_on_hand",
        "input_surface": "inventory",
        "target": {"hive_id": hive, "item_id": item_id},
        "delta": -delta,
        "baseline": {"qty_on_hand": qty0, "min_qty": minq, "is_low_stock": base_low, "hive_low_stock_count": base_count},
        "termini": termini,
        "termini_total": len(termini),
        "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #3 -- pm_scope_items.anchor_date -> next_due_date -> is_overdue ->
# pm_overdue (distinct-pm_asset_id roll-up). 3rd surface, 3rd registered metric.
# ★is_overdue = next_due_date < CURRENT_DATE, next_due_date = COALESCE(
# last_completed_at, anchor_date, created_at) + frequency_days. So we pick an
# item with last_completed_at IS NULL (anchor drives it) whose ASSET has no
# other overdue item (clean +1 on the distinct roll-up), and push anchor_date
# into the past. The real-user analogue is the inverse (a PM completion moves
# next_due forward); this proves the same nerve from the schedule side.
# ───────────────────────────────────────────────────────────────────────────
def probe_pm_overdue() -> dict:
    TGT_SQL = """
        WITH overdue_assets AS (
          SELECT DISTINCT hive_id, pm_asset_id FROM v_pm_scope_items_truth WHERE is_overdue
        )
        SELECT t.scope_item_id, t.hive_id, t.pm_asset_id, t.frequency_days
        FROM v_pm_scope_items_truth t
        WHERE t.is_overdue = false AND t.hive_id IS NOT NULL
          AND t.frequency_days IS NOT NULL AND t.last_completed_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM overdue_assets oa
                          WHERE oa.hive_id=t.hive_id AND oa.pm_asset_id=t.pm_asset_id)
        ORDER BY t.next_due_date ASC, t.scope_item_id LIMIT 1;"""
    tgt = psql(TGT_SQL)
    if not tgt:
        return {"nerve": "pm_anchor__overdue", "error": "no clean not-overdue target (asset w/o other overdue, no completion)"}
    sid, hive, asset, freq = tgt[0][0], tgt[0][1], tgt[0][2], int(_f(tgt[0][3]))
    back = freq + 10   # next_due = anchor + freq = today - 10  ->  overdue

    orig_anchor = scalar(f"SELECT anchor_date FROM pm_scope_items WHERE id='{sid}';")
    base_overdue = bool_pg(scalar(f"SELECT is_overdue FROM v_pm_scope_items_truth WHERE scope_item_id='{sid}';"))
    base_count = int(scalar(
        f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{hive}' AND is_overdue;"))
    termini = []
    try:
        # SEED: push the schedule anchor into the past so next_due_date < today.
        psql(f"UPDATE pm_scope_items SET anchor_date = (CURRENT_DATE - INTERVAL '{back} days')::date WHERE id='{sid}';")

        # T1. D-layer: the anchor moved.
        d_anchor = scalar(f"SELECT anchor_date FROM pm_scope_items WHERE id='{sid}';")
        termini.append({"terminus": "D · pm_scope_items.anchor_date", "layer": "D",
                        "measured": d_anchor, "expected": "CURRENT_DATE - %dd" % back,
                        "ok": d_anchor is not None and d_anchor != orig_anchor})

        # T2. canonical: the truth view recomputes is_overdue (false -> true).
        v_over = bool_pg(scalar(f"SELECT is_overdue FROM v_pm_scope_items_truth WHERE scope_item_id='{sid}';"))
        termini.append({"terminus": "canonical · v_pm_scope_items_truth.is_overdue (next_due<today)", "layer": "D/view",
                        "measured": v_over, "expected": {"is_overdue": True, "was": base_overdue},
                        "ok": v_over is True and base_overdue is False})

        # T3. KPI pm_overdue distinct-asset roll-up: +1.
        a_count = int(scalar(
            f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{hive}' AND is_overdue;"))
        termini.append({"terminus": "KPI · pm_overdue (distinct pm_asset_id roll-up, hive)", "layer": "compute",
                        "measured": a_count, "expected": base_count + 1, "ok": a_count == base_count + 1})
    finally:
        # CLEANUP: restore the exact original anchor_date.
        if orig_anchor:
            psql(f"UPDATE pm_scope_items SET anchor_date = '{orig_anchor}' WHERE id='{sid}';")

    return {
        "nerve": "pm_anchor__overdue",
        "field": "pm_scope_items.anchor_date",
        "input_surface": "pm-scheduler",
        "target": {"hive_id": hive, "scope_item_id": sid, "pm_asset_id": asset},
        "delta": f"anchor -{back}d",
        "baseline": {"anchor_date": orig_anchor, "frequency_days": freq,
                     "is_overdue": base_overdue, "hive_pm_overdue_assets": base_count},
        "termini": termini,
        "termini_total": len(termini),
        "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #4 -- pm_scope_items.anchor_date -> next_due_date -> is_due_soon ->
# pm_due_soon (distinct roll-up). Same surface/base as #3 but the OTHER band:
# is_due_soon = next_due_date IN [today, today+14] AND not overdue. Push the
# anchor so next_due lands ~7 days out.
# ───────────────────────────────────────────────────────────────────────────
def probe_pm_due_soon() -> dict:
    TGT_SQL = """
        WITH ds AS (SELECT DISTINCT hive_id, pm_asset_id FROM v_pm_scope_items_truth WHERE is_due_soon)
        SELECT t.scope_item_id, t.hive_id, t.pm_asset_id, t.frequency_days
        FROM v_pm_scope_items_truth t
        WHERE t.is_due_soon=false AND t.is_overdue=false AND t.hive_id IS NOT NULL
          AND t.frequency_days IS NOT NULL AND t.last_completed_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM ds WHERE ds.hive_id=t.hive_id AND ds.pm_asset_id=t.pm_asset_id)
        ORDER BY t.scope_item_id LIMIT 1;"""
    tgt = psql(TGT_SQL)
    if not tgt:
        return {"nerve": "pm_anchor__due_soon", "error": "no clean not-due-soon target"}
    sid, hive, asset, freq = tgt[0][0], tgt[0][1], tgt[0][2], int(_f(tgt[0][3]))
    fwd = freq - 7   # next_due = anchor + freq = today + 7  ->  inside the 14-day due-soon band

    orig_anchor = scalar(f"SELECT anchor_date FROM pm_scope_items WHERE id='{sid}';")
    base_ds = bool_pg(scalar(f"SELECT is_due_soon FROM v_pm_scope_items_truth WHERE scope_item_id='{sid}';"))
    base_count = int(scalar(
        f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{hive}' AND is_due_soon;"))
    termini = []
    try:
        psql(f"UPDATE pm_scope_items SET anchor_date = (CURRENT_DATE - INTERVAL '{fwd} days')::date WHERE id='{sid}';")
        d_anchor = scalar(f"SELECT anchor_date FROM pm_scope_items WHERE id='{sid}';")
        termini.append({"terminus": "D · pm_scope_items.anchor_date", "layer": "D",
                        "measured": d_anchor, "expected": "next_due ≈ today+7",
                        "ok": d_anchor is not None and d_anchor != orig_anchor})
        vals = psql(f"SELECT is_due_soon, is_overdue FROM v_pm_scope_items_truth WHERE scope_item_id='{sid}';")[0]
        v_ds, v_over = bool_pg(vals[0]), bool_pg(vals[1])
        termini.append({"terminus": "canonical · v_pm_scope_items_truth.is_due_soon (today≤next_due≤+14)", "layer": "D/view",
                        "measured": {"is_due_soon": v_ds, "is_overdue": v_over},
                        "expected": {"is_due_soon": True, "is_overdue": False, "was": base_ds},
                        "ok": v_ds is True and v_over is False and base_ds is False})
        a_count = int(scalar(
            f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{hive}' AND is_due_soon;"))
        termini.append({"terminus": "KPI · pm_due_soon (distinct pm_asset_id roll-up, hive)", "layer": "compute",
                        "measured": a_count, "expected": base_count + 1, "ok": a_count == base_count + 1})
    finally:
        if orig_anchor:
            psql(f"UPDATE pm_scope_items SET anchor_date = '{orig_anchor}' WHERE id='{sid}';")

    return {
        "nerve": "pm_anchor__due_soon", "field": "pm_scope_items.anchor_date", "input_surface": "pm-scheduler",
        "target": {"hive_id": hive, "scope_item_id": sid, "pm_asset_id": asset}, "delta": f"anchor -> next_due≈+7d",
        "baseline": {"anchor_date": orig_anchor, "frequency_days": freq, "is_due_soon": base_ds, "hive_due_soon_assets": base_count},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #5 -- get_pm_compliance_smrp (RPC) -> pm_compliance %. A DIFFERENT
# MECHANISM: the terminus is an RPC returning jsonb {total_completed,
# total_scheduled, overall_pct, compliance_by_asset[]}, not a view. The RPC's
# completion-COUNTING is scheduled-matched (opaque to a raw insert), so rather
# than a fragile seed-differential we assert the RPC's VALUE is CORRECT three
# ways -- the §13 nerve is "the number is correct", and an RPC that
# mis-aggregates is exactly the bug this catches:
#   1. overall_pct == round(100 * total_completed / total_scheduled, 1)
#   2. every per-asset compliance_pct == round(100*completed/scheduled,1)
#   3. ROLLUP integrity: total_completed == Σ asset.completed AND
#      total_scheduled == Σ asset.scheduled (the overall matches its parts)
# (A full completion-seed differential needs the RPC's scheduled-matching
# semantics -> a deeper P4 journey; noted, not faked.)
# ───────────────────────────────────────────────────────────────────────────
def probe_pm_compliance() -> dict:
    import json as _json
    hive = scalar("""
        SELECT hive_id FROM v_pm_scope_items_truth WHERE hive_id IS NOT NULL
        GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1;""")
    if not hive:
        return {"nerve": "pm_rpc__compliance", "error": "no hive with PM scope items"}
    raw = scalar(f"SELECT get_pm_compliance_smrp('{hive}'::uuid, 90);")
    r = _json.loads(raw) if raw else {}
    done, sched, pct = r.get("total_completed"), r.get("total_scheduled"), r.get("overall_pct")
    by = r.get("compliance_by_asset", []) or []

    exp_pct = round(100 * done / sched, 1) if sched else None
    sum_done = sum(a.get("completed", 0) for a in by)
    sum_sched = sum(a.get("scheduled", 0) for a in by)
    asset_pct_ok = all(
        a.get("scheduled") and _close(a.get("compliance_pct"), round(100 * a["completed"] / a["scheduled"], 1), 0.11)
        for a in by) if by else False

    termini = [
        {"terminus": "RPC · overall_pct == completed/scheduled", "layer": "compute",
         "measured": pct, "expected": exp_pct, "ok": _close(pct, exp_pct, 0.11)},
        {"terminus": f"RPC · all {len(by)} per-asset compliance_pct correct", "layer": "compute",
         "measured": f"{len(by)} rows", "expected": "each == completed/scheduled", "ok": bool(asset_pct_ok)},
        {"terminus": "RPC · rollup integrity (overall == Σ per-asset)", "layer": "compute",
         "measured": {"done": done, "sched": sched}, "expected": {"Σdone": sum_done, "Σsched": sum_sched},
         "ok": done == sum_done and sched == sum_sched},
    ]
    return {
        "nerve": "pm_rpc__compliance", "field": "get_pm_compliance_smrp (RPC)", "input_surface": "pm-scheduler",
        "target": {"hive_id": hive, "period_days": 90}, "delta": "value-correctness (RPC mechanism)",
        "baseline": {"total_completed": done, "total_scheduled": sched, "overall_pct": pct, "assets": len(by)},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #6 -- skill_badges.level -> v_worker_skill_truth.current_level /
# badge_count. The 4th SURFACE (skillmatrix) -- and ★it directly advances the
# `live_discovery_pending` finding: skillmatrix exposes NO static capture markup
# (its inputs are a JS-rendered grid, invisible to the static auditor), yet its
# DB nerve is fully testable via psql WITHOUT the browser. current_level =
# max(skill_badges.level) per (worker, discipline); badge_count = count.
# ───────────────────────────────────────────────────────────────────────────
def probe_skillmatrix_level() -> dict:
    tgt = psql("""
        SELECT hive_id, worker_name, discipline, current_level, badge_count
        FROM v_worker_skill_truth
        WHERE current_level IS NOT NULL AND current_level < 5 AND hive_id IS NOT NULL
        ORDER BY worker_name, discipline LIMIT 1;""")
    if not tgt:
        return {"nerve": "skillmatrix_badge__level", "error": "no worker with current_level < 5"}
    hive, worker, disc, base_lvl, base_badges = tgt[0][0], tgt[0][1], tgt[0][2], int(tgt[0][3]), int(tgt[0][4])
    marker = f"__JT__{uuid.uuid4().hex[:10]}"
    new_level = 5
    termini = []
    try:
        psql(f"""INSERT INTO skill_badges (id, worker_name, discipline, level, exam_score, earned_at, badge_key)
                 VALUES (gen_random_uuid(), '{worker.replace("'", "''")}', '{disc.replace("'", "''")}',
                         {new_level}, 100, NOW(), '{marker}');""")

        d = psql(f"SELECT level FROM skill_badges WHERE badge_key='{marker}';")
        termini.append({"terminus": "D · skill_badges row (level)", "layer": "D",
                        "measured": d[0][0] if d else None, "expected": new_level,
                        "ok": bool(d) and int(d[0][0]) == new_level})

        v = psql(f"""SELECT current_level, badge_count FROM v_worker_skill_truth
                     WHERE hive_id='{hive}' AND worker_name='{worker.replace("'", "''")}'
                       AND discipline='{disc.replace("'", "''")}';""")
        v_lvl, v_badges = (int(v[0][0]), int(v[0][1])) if v else (None, None)
        termini.append({"terminus": "canonical · v_worker_skill_truth.current_level (= max badge level)", "layer": "D/view",
                        "measured": v_lvl, "expected": max(base_lvl, new_level),
                        "ok": v_lvl == max(base_lvl, new_level) and base_lvl < new_level})
        termini.append({"terminus": "canonical · v_worker_skill_truth.badge_count (+1)", "layer": "D/view",
                        "measured": v_badges, "expected": base_badges + 1, "ok": v_badges == base_badges + 1})
    finally:
        psql(f"DELETE FROM skill_badges WHERE badge_key='{marker}';")

    return {
        "nerve": "skillmatrix_badge__level", "field": "skill_badges.level", "input_surface": "skillmatrix",
        "target": {"hive_id": hive, "worker_name": worker, "discipline": disc}, "delta": f"+1 badge level={new_level}",
        "baseline": {"current_level": base_lvl, "badge_count": base_badges},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #7 -- asset-hub. TWO kinds in one surface: (a) a PASSTHROUGH input
# (asset_nodes.criticality -> v_asset_truth.criticality, the asset attribute
# that risk/analytics read) and (b) a CROSS-SURFACE rollup (a logbook entry
# linked by asset_node_id -> v_asset_truth.lifetime_logbook_entries +1) -- the
# 5th surface, and proof that an input on ONE page innervates a terminus on
# ANOTHER (the web, not just one screen).
# ───────────────────────────────────────────────────────────────────────────
def probe_assethub() -> dict:
    tgt = psql("""
        SELECT n.id, n.hive_id, n.criticality, t.lifetime_logbook_entries
        FROM asset_nodes n JOIN v_asset_truth t ON t.asset_id = n.id
        WHERE n.hive_id IS NOT NULL AND n.criticality IS NOT NULL
          AND lower(n.criticality) <> 'critical'
        ORDER BY n.id LIMIT 1;""")
    if not tgt:
        return {"nerve": "assethub__criticality_and_rollup", "error": "no asset_node with non-critical criticality"}
    aid, hive, base_crit, base_lle = tgt[0][0], tgt[0][1], tgt[0][2], int(tgt[0][3])
    marker = f"__JT__{uuid.uuid4().hex[:10]}"
    rid = f"__jt__{uuid.uuid4().hex[:12]}"
    termini = []
    try:
        # (a) PASSTHROUGH input: change the asset's criticality (enum: low/medium/high/critical).
        psql(f"UPDATE asset_nodes SET criticality='critical' WHERE id='{aid}';")
        v_crit = scalar(f"SELECT criticality FROM v_asset_truth WHERE asset_id='{aid}';")
        termini.append({"terminus": "canonical · v_asset_truth.criticality (passthrough)", "layer": "D/view",
                        "measured": v_crit, "expected": "critical", "ok": v_crit == "critical" and (base_crit or "").lower() != "critical"})

        # (b) CROSS-SURFACE rollup: a logbook entry linked to this asset -> lifetime +1.
        psql(f"""INSERT INTO logbook (id, worker_name, date, created_at, machine, hive_id,
                 maintenance_type, downtime_hours, status, problem, action, asset_node_id)
                 VALUES ('{rid}', '{JT_WORKER}', NOW(), NOW(), 'JT-ASSET', '{hive}',
                 'Breakdown / Corrective', 0, 'Open', '{marker}', 'asset rollup seed', '{aid}');""")
        a_lle = int(scalar(f"SELECT lifetime_logbook_entries FROM v_asset_truth WHERE asset_id='{aid}';"))
        termini.append({"terminus": "canonical · v_asset_truth.lifetime_logbook_entries (cross-surface: logbook→asset +1)",
                        "layer": "compute", "measured": a_lle, "expected": base_lle + 1, "ok": a_lle == base_lle + 1})
    finally:
        psql(f"UPDATE asset_nodes SET criticality='{(base_crit or '').replace(chr(39), chr(39)*2)}' WHERE id='{aid}';")
        psql(f"DELETE FROM logbook WHERE worker_name='{JT_WORKER}';")

    return {
        "nerve": "assethub__criticality_and_rollup", "field": "asset_nodes.criticality + logbook.asset_node_id",
        "input_surface": "asset-hub", "target": {"hive_id": hive, "asset_id": aid},
        "delta": "criticality->Critical · +1 linked logbook entry",
        "baseline": {"criticality": base_crit, "lifetime_logbook_entries": base_lle},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #8 -- project_items.status -> v_project_truth.items_done. The 6th
# surface (project-manager): completing a project task rolls up to the
# project's done-count. items_done = count(project_items WHERE status='done').
# ───────────────────────────────────────────────────────────────────────────
def probe_projectmgr() -> dict:
    tgt = psql("""
        SELECT i.id, i.project_id, i.status, t.hive_id, t.items_done
        FROM project_items i JOIN v_project_truth t ON t.project_id = i.project_id
        WHERE i.status <> 'done' AND t.hive_id IS NOT NULL
        ORDER BY t.project_id, i.id LIMIT 1;""")
    if not tgt:
        return {"nerve": "projectmgr_item__items_done", "error": "no non-done project_item"}
    iid, pid, orig_status, hive, base_done = tgt[0][0], tgt[0][1], tgt[0][2], tgt[0][3], int(tgt[0][4])
    termini = []
    try:
        psql(f"UPDATE project_items SET status='done' WHERE id='{iid}';")
        d = scalar(f"SELECT status FROM project_items WHERE id='{iid}';")
        termini.append({"terminus": "D · project_items.status", "layer": "D",
                        "measured": d, "expected": "done", "ok": d == "done"})
        a_done = int(scalar(f"SELECT items_done FROM v_project_truth WHERE project_id='{pid}';"))
        termini.append({"terminus": "canonical · v_project_truth.items_done (count status=done) +1", "layer": "compute",
                        "measured": a_done, "expected": base_done + 1, "ok": a_done == base_done + 1})
    finally:
        psql(f"UPDATE project_items SET status='{orig_status}' WHERE id='{iid}';")
    return {
        "nerve": "projectmgr_item__items_done", "field": "project_items.status", "input_surface": "project-manager",
        "target": {"hive_id": hive, "project_id": pid, "item_id": iid}, "delta": f"status {orig_status}->done",
        "baseline": {"items_done": base_done, "orig_status": orig_status},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #9 -- community_posts.deleted_at -> v_community_posts_truth.is_deleted.
# The 7th surface (community): soft-delete semantics -- a deleted post must
# correctly read is_deleted=true (so it disappears from the live feed).
# is_deleted = (deleted_at IS NOT NULL).
# ───────────────────────────────────────────────────────────────────────────
def probe_community() -> dict:
    tgt = psql("""SELECT id, hive_id, is_deleted FROM v_community_posts_truth
                  WHERE hive_id IS NOT NULL AND is_deleted=false ORDER BY id LIMIT 1;""")
    if not tgt:
        return {"nerve": "community_softdelete__is_deleted", "error": "no non-deleted post"}
    pid, hive, base_del = tgt[0][0], tgt[0][1], bool_pg(tgt[0][2])
    termini = []
    try:
        psql(f"UPDATE community_posts SET deleted_at = NOW() WHERE id='{pid}';")
        v = bool_pg(scalar(f"SELECT is_deleted FROM v_community_posts_truth WHERE id='{pid}';"))
        termini.append({"terminus": "canonical · v_community_posts_truth.is_deleted (deleted_at IS NOT NULL)",
                        "layer": "D/view", "measured": v, "expected": {"is_deleted": True, "was": base_del},
                        "ok": v is True and base_del is False})
    finally:
        psql(f"UPDATE community_posts SET deleted_at = NULL WHERE id='{pid}';")
    return {
        "nerve": "community_softdelete__is_deleted", "field": "community_posts.deleted_at",
        "input_surface": "community", "target": {"hive_id": hive, "post_id": pid}, "delta": "deleted_at -> NOW()",
        "baseline": {"is_deleted": base_del},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #10 -- marketplace_listings(published) -> v_marketplace_sellers_truth.
# active_listings_count. The 8th surface AND the standing regression-guard for
# the dead-nerve FIXED in migration 20260616000000 (was filtering 'active', now
# 'published'). Self-seeds a seller + a published listing (the seller table is
# empty in the local seed), proves the rollup +1, cleans up both.
# ───────────────────────────────────────────────────────────────────────────
def probe_marketplace() -> dict:
    hive = scalar("SELECT hive_id FROM marketplace_listings WHERE hive_id IS NOT NULL LIMIT 1;")
    if not hive:
        return {"nerve": "marketplace_listing__active_count", "error": "no marketplace_listings hive"}
    termini = []
    try:
        # seed a seller (none exist in the local seed)
        psql(f"""INSERT INTO marketplace_sellers
                 (id, worker_name, tier, kyb_verified, total_sales, rating_count, cert_verified, hive_id, created_at, updated_at)
                 VALUES (gen_random_uuid(), '{JT_WORKER}', 'bronze', false, 0, 0, false, '{hive}', NOW(), NOW());""")
        base = int(scalar(f"SELECT active_listings_count FROM v_marketplace_sellers_truth WHERE worker_name='{JT_WORKER}';"))

        # publish a listing for that seller -> the rollup must count it
        psql(f"""INSERT INTO marketplace_listings
                 (id, seller_name, seller_verified, completed_sales, section, title, status, view_count, hive_id, created_at, updated_at)
                 VALUES (gen_random_uuid(), '{JT_WORKER}', false, 0, 'parts', 'JT seed listing', 'published', 0, '{hive}', NOW(), NOW());""")
        d = int(scalar(f"SELECT count(*) FROM marketplace_listings WHERE seller_name='{JT_WORKER}' AND status='published';"))
        termini.append({"terminus": "D · marketplace_listings (published) row", "layer": "D",
                        "measured": d, "expected": 1, "ok": d == 1})
        a = int(scalar(f"SELECT active_listings_count FROM v_marketplace_sellers_truth WHERE worker_name='{JT_WORKER}';"))
        termini.append({"terminus": "canonical · v_marketplace_sellers_truth.active_listings_count (published rollup +1)",
                        "layer": "compute", "measured": a, "expected": base + 1, "ok": a == base + 1})
    finally:
        psql(f"DELETE FROM marketplace_listings WHERE seller_name='{JT_WORKER}';")
        psql(f"DELETE FROM marketplace_sellers WHERE worker_name='{JT_WORKER}';")

    return {
        "nerve": "marketplace_listing__active_count", "field": "marketplace_listings.status(published)",
        "input_surface": "marketplace", "target": {"hive_id": hive}, "delta": "+1 published listing",
        "baseline": {"active_listings_count": 0},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #11 -- ai_reports -> v_ai_reports_truth (report-sender, 9th surface).
# A generated report's type + recency must surface as the right flags
# (is_pm_overdue, fresh_24h). Self-seeds (ai_reports empty in local seed).
# ───────────────────────────────────────────────────────────────────────────
def probe_reportsender() -> dict:
    hive = scalar("SELECT hive_id FROM logbook WHERE hive_id IS NOT NULL LIMIT 1;")
    rid = None
    termini = []
    try:
        rid = scalar(f"""INSERT INTO ai_reports (id, hive_id, report_type, generated_at, created_at)
                         VALUES (gen_random_uuid(), '{hive}', 'pm_overdue', NOW(), NOW()) RETURNING id;""")
        row = psql(f"SELECT is_pm_overdue, fresh_24h, is_failure_digest FROM v_ai_reports_truth WHERE id='{rid}';")
        if not row:
            termini.append({"terminus": "canonical · v_ai_reports_truth row", "layer": "D/view",
                            "measured": None, "expected": "row present", "ok": False})
        else:
            is_pm, fresh, is_fail = bool_pg(row[0][0]), bool_pg(row[0][1]), bool_pg(row[0][2])
            termini.append({"terminus": "canonical · v_ai_reports_truth.is_pm_overdue (report_type)", "layer": "D/view",
                            "measured": is_pm, "expected": True, "ok": is_pm is True})
            termini.append({"terminus": "canonical · v_ai_reports_truth.fresh_24h (generated_at recency)", "layer": "compute",
                            "measured": fresh, "expected": True, "ok": fresh is True})
            termini.append({"terminus": "canonical · v_ai_reports_truth.is_failure_digest (negative — not this type)", "layer": "D/view",
                            "measured": is_fail, "expected": False, "ok": is_fail is False})
    finally:
        if rid:
            psql(f"DELETE FROM ai_reports WHERE id='{rid}';")
    return {
        "nerve": "reportsender_report__flags", "field": "ai_reports.report_type+generated_at",
        "input_surface": "report-sender", "target": {"hive_id": hive}, "delta": "+1 pm_overdue report (now)",
        "baseline": {"ai_reports": "empty seed"},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini) and len(termini) > 1,
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #12 -- external_sync.last_synced_at -> v_external_sync_truth.
# synced_within_24h (integrations, 10th surface). A sync that just ran must
# read as fresh. Self-seeds (external_sync empty in local seed).
# ───────────────────────────────────────────────────────────────────────────
def probe_integrations() -> dict:
    hive = scalar("SELECT hive_id FROM logbook WHERE hive_id IS NOT NULL LIMIT 1;")
    sid = None
    termini = []
    try:
        sid = scalar(f"""INSERT INTO external_sync
                         (id, hive_id, system_type, external_id, entity_type, last_synced_at)
                         VALUES (gen_random_uuid(), '{hive}', 'sap', 'JT-1', 'asset', NOW()) RETURNING id;""")
        row = psql(f"SELECT synced_within_24h, days_since_sync FROM v_external_sync_truth WHERE id='{sid}';")
        if not row:
            termini.append({"terminus": "canonical · v_external_sync_truth row", "layer": "D/view",
                            "measured": None, "expected": "row present", "ok": False})
        else:
            fresh, days = bool_pg(row[0][0]), row[0][1]
            termini.append({"terminus": "canonical · v_external_sync_truth.synced_within_24h (last_synced_at recency)",
                            "layer": "compute", "measured": fresh, "expected": True, "ok": fresh is True})
            termini.append({"terminus": "canonical · v_external_sync_truth.days_since_sync (=0 today)", "layer": "compute",
                            "measured": days, "expected": "0", "ok": str(days) == "0"})
    finally:
        if sid:
            psql(f"DELETE FROM external_sync WHERE id='{sid}';")
    return {
        "nerve": "integrations_sync__fresh", "field": "external_sync.last_synced_at",
        "input_surface": "integrations", "target": {"hive_id": hive}, "delta": "+1 sync (now)",
        "baseline": {"external_sync": "empty seed"},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini) and len(termini) > 1,
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #13 -- anomaly_signals.status -> v_anomaly_truth.status (alert-hub, 11th
# surface). ★Resolves the OTHER half of live_discovery_pending: alert-hub has no
# static capture markup (action-driven), but its acknowledge action (active ->
# acknowledged) is a real DB nerve, testable here without the browser.
# ───────────────────────────────────────────────────────────────────────────
def probe_alerthub() -> dict:
    tgt = psql("""SELECT id, hive_id, status FROM anomaly_signals
                  WHERE status <> 'acknowledged' AND hive_id IS NOT NULL ORDER BY id LIMIT 1;""")
    if not tgt:
        return {"nerve": "alerthub_ack__status", "error": "no non-acknowledged anomaly_signal"}
    aid, hive, orig = tgt[0][0], tgt[0][1], tgt[0][2]
    termini = []
    try:
        psql(f"UPDATE anomaly_signals SET status='acknowledged', acknowledged_at=NOW(), "
             f"acknowledged_by='{JT_WORKER}' WHERE id='{aid}';")
        v = scalar(f"SELECT status FROM v_anomaly_truth WHERE id='{aid}';")
        termini.append({"terminus": "canonical · v_anomaly_truth.status (acknowledge action)", "layer": "D/view",
                        "measured": v, "expected": "acknowledged", "ok": v == "acknowledged" and orig != "acknowledged"})
    finally:
        psql(f"UPDATE anomaly_signals SET status='{orig}', acknowledged_at=NULL, acknowledged_by=NULL WHERE id='{aid}';")
    return {
        "nerve": "alerthub_ack__status", "field": "anomaly_signals.status", "input_surface": "alert-hub",
        "target": {"hive_id": hive, "anomaly_id": aid}, "delta": f"status {orig}->acknowledged",
        "baseline": {"status": orig},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini) and len(termini) >= 1,
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #14 -- logbook.status='Open' -> v_logbook_truth open-jobs count (the
# curated lineage_edges chain: logbook.status -> v_logbook_truth -> hive.stat-
# open / ops-home Open Jobs tile). A SECOND nerve on logbook (depth toward
# P-fully) + a different terminus type (status-filter count).
# ───────────────────────────────────────────────────────────────────────────
def probe_logbook_openjobs() -> dict:
    hive = scalar("""SELECT hive_id FROM logbook WHERE hive_id IS NOT NULL
                     GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1;""")
    base = int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{hive}' AND status='Open';"))
    rid = f"__jt__{uuid.uuid4().hex[:12]}"
    marker = f"__JT__{uuid.uuid4().hex[:10]}"
    termini = []
    try:
        psql(f"""INSERT INTO logbook (id, worker_name, date, created_at, machine, hive_id,
                 maintenance_type, downtime_hours, status, problem, action)
                 VALUES ('{rid}', '{JT_WORKER}', NOW(), NOW(), 'JT-OPEN', '{hive}',
                 'Breakdown / Corrective', 0, 'Open', '{marker}', 'open jobs seed');""")
        d = psql(f"SELECT status FROM v_logbook_truth WHERE problem='{marker}';")
        termini.append({"terminus": "canonical · v_logbook_truth exposes the Open entry", "layer": "D/view",
                        "measured": d[0][0] if d else None, "expected": "Open", "ok": bool(d) and d[0][0] == "Open"})
        a = int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{hive}' AND status='Open';"))
        termini.append({"terminus": "KPI · Open Jobs count (status='Open' rollup, hive.stat-open) +1", "layer": "compute",
                        "measured": a, "expected": base + 1, "ok": a == base + 1})
    finally:
        psql(f"DELETE FROM logbook WHERE worker_name='{JT_WORKER}';")
    return {
        "nerve": "logbook_status__open_jobs", "field": "logbook.status", "input_surface": "logbook",
        "target": {"hive_id": hive}, "delta": "+1 Open entry",
        "baseline": {"open_jobs": base},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #15 -- worker_achievements.xp_total -> v_worker_achievements_truth
# (achievements, 12th surface; a TERMINUS page's lineage). The view derives
# xp_into_current_level = xp_total - current_level*xp_per_level and
# xp_to_next_level = (current_level+1)*xp_per_level - xp_total. A differential
# bump of xp_total must shift xp_into by +Δ and xp_to_next by -Δ (current_level
# is STORED, so it stays). Also asserts the formula-consistency invariant.
# UPDATE-only (no INSERT) so no auth.users FK concerns.
# ───────────────────────────────────────────────────────────────────────────
def probe_achievements(delta: int = 50) -> dict:
    tgt = psql("""SELECT id, xp_total, xp_per_level, current_level, xp_into_current_level, xp_to_next_level
                  FROM v_worker_achievements_truth
                  WHERE xp_per_level > 0 AND is_maxed = false ORDER BY id LIMIT 1;""")
    if not tgt:
        return {"nerve": "achievements_xp__level", "error": "no non-maxed achievement row"}
    aid, xp0, xpl, lvl = tgt[0][0], int(tgt[0][1]), int(tgt[0][2]), int(tgt[0][3])
    into0, tonext0 = int(tgt[0][4]), int(tgt[0][5])
    termini = []
    try:
        psql(f"UPDATE worker_achievements SET xp_total = xp_total + {delta} WHERE id='{aid}';")
        row = psql(f"""SELECT xp_total, xp_into_current_level, xp_to_next_level, current_level
                       FROM v_worker_achievements_truth WHERE id='{aid}';""")[0]
        xp_a, into_a, tonext_a, lvl_a = int(row[0]), int(row[1]), int(row[2]), int(row[3])
        termini.append({"terminus": "D · worker_achievements.xp_total (+Δ)", "layer": "D",
                        "measured": xp_a, "expected": xp0 + delta, "ok": xp_a == xp0 + delta})
        termini.append({"terminus": "canonical · v_worker_achievements_truth.xp_into_current_level (+Δ)", "layer": "compute",
                        "measured": into_a, "expected": into0 + delta, "ok": into_a == into0 + delta})
        termini.append({"terminus": "canonical · v_worker_achievements_truth.xp_to_next_level (-Δ)", "layer": "compute",
                        "measured": tonext_a, "expected": tonext0 - delta, "ok": tonext_a == tonext0 - delta})
        # formula-consistency invariant: xp_into == xp_total - current_level*xp_per_level
        termini.append({"terminus": "invariant · xp_into == xp_total - level*xp_per_level", "layer": "compute",
                        "measured": into_a, "expected": xp_a - lvl_a * xpl, "ok": into_a == xp_a - lvl_a * xpl})
    finally:
        psql(f"UPDATE worker_achievements SET xp_total = {xp0} WHERE id='{aid}';")
    return {
        "nerve": "achievements_xp__level", "field": "worker_achievements.xp_total",
        "input_surface": "achievements", "target": {"achievement_row": aid},
        "delta": f"+{delta} xp", "baseline": {"xp_total": xp0, "xp_into": into0, "xp_to_next": tonext0},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #16 -- hive_audit_log persist + hive-scope + cross-hive isolation
# (audit-log, 13th surface). The audit-log page reads hive_audit_log DIRECTLY
# (db.from('hive_audit_log')), hive-scoped. A seeded audit action must persist,
# be visible scoped to its OWN hive, and be INVISIBLE under another hive's
# filter. Self-seeds + cleans up.
# ───────────────────────────────────────────────────────────────────────────
def probe_auditlog() -> dict:
    a = scalar("SELECT hive_id FROM hive_audit_log WHERE hive_id IS NOT NULL LIMIT 1;") \
        or scalar("SELECT hive_id FROM logbook WHERE hive_id IS NOT NULL LIMIT 1;")
    b = scalar(f"SELECT hive_id FROM v_kpi_truth WHERE hive_id IS NOT NULL AND hive_id <> '{a}' LIMIT 1;")
    marker = f"__JT__{uuid.uuid4().hex[:10]}"
    termini = []
    try:
        psql(f"""INSERT INTO hive_audit_log (id, hive_id, actor, action, target_type, target_name, created_at)
                 VALUES (gen_random_uuid(), '{a}', '{JT_WORKER}', '{marker}', 'vaxis', 'probe', NOW());""")
        # persist
        d = int(scalar(f"SELECT count(*) FROM hive_audit_log WHERE action='{marker}';"))
        termini.append({"terminus": "D · hive_audit_log row persisted", "layer": "D",
                        "measured": d, "expected": 1, "ok": d == 1})
        # own-hive scoped (the page's read)
        own = int(scalar(f"SELECT count(*) FROM hive_audit_log WHERE hive_id='{a}' AND action='{marker}';"))
        termini.append({"terminus": "AU · visible scoped to own hive", "layer": "AU",
                        "measured": own, "expected": 1, "ok": own == 1})
        # cross-hive invisible
        cross = int(scalar(f"SELECT count(*) FROM hive_audit_log WHERE hive_id='{b}' AND action='{marker}';")) if b else 0
        termini.append({"terminus": "S · invisible under another hive's filter", "layer": "S",
                        "measured": cross, "expected": 0, "ok": cross == 0})
    finally:
        psql(f"DELETE FROM hive_audit_log WHERE actor='{JT_WORKER}';")
    return {
        "nerve": "auditlog_action__hive_scoped", "field": "hive_audit_log.action",
        "input_surface": "audit-log", "target": {"hive_id": a}, "delta": "+1 audit action",
        "baseline": {"hive_audit_log": "self-seeded marker"},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


# ───────────────────────────────────────────────────────────────────────────
# NERVE #17 -- asset_risk_scores.risk_score -> v_risk_truth.risk_level -> the
# top_risk_band "hot assets" count (high+critical). The 5th + FINAL registered
# kpi_source_registry metric (top_risk_band; critical>=0.85, high>=0.70). The ML
# risk band is a STORED score in asset_risk_scores (the view dedups DISTINCT ON
# (hive,asset)); bumping a below-band asset across the threshold must flip its
# band and +1 the hive's hot-asset count. Restores every touched row by id.
# ───────────────────────────────────────────────────────────────────────────
def probe_risk_band() -> dict:
    tgt = psql("""SELECT hive_id, asset_name, risk_score, risk_level FROM v_risk_truth
                  WHERE risk_score < 0.70 AND hive_id IS NOT NULL
                  ORDER BY risk_score DESC, asset_name LIMIT 1;""")
    if not tgt:
        return {"nerve": "risk_band__hot_count", "error": "no below-band (risk_score<0.70) asset"}
    hive, asset, score0, level0 = tgt[0][0], tgt[0][1], _f(tgt[0][2]), tgt[0][3]
    orig = psql(f"SELECT id, risk_score, risk_level FROM asset_risk_scores "
                f"WHERE hive_id='{hive}' AND asset_name='{asset.replace(chr(39), chr(39)*2)}';")
    base_hot = int(scalar(f"SELECT count(*) FROM v_risk_truth WHERE hive_id='{hive}' "
                          f"AND risk_level IN ('high','critical');"))
    termini = []
    try:
        psql(f"UPDATE asset_risk_scores SET risk_score=0.92, risk_level='critical' "
             f"WHERE hive_id='{hive}' AND asset_name='{asset.replace(chr(39), chr(39)*2)}';")
        v = psql(f"SELECT risk_score, risk_level FROM v_risk_truth WHERE hive_id='{hive}' "
                 f"AND asset_name='{asset.replace(chr(39), chr(39)*2)}';")[0]
        v_score, v_level = _f(v[0]), v[1]
        termini.append({"terminus": "canonical · v_risk_truth.risk_level (band flip → critical)", "layer": "D/view",
                        "measured": v_level, "expected": {"risk_level": "critical", "was": level0},
                        "ok": v_level == "critical" and level0 != "critical"})
        termini.append({"terminus": "canonical · v_risk_truth.risk_score (passthrough)", "layer": "D/view",
                        "measured": v_score, "expected": 0.92, "ok": _close(v_score, 0.92)})
        a_hot = int(scalar(f"SELECT count(*) FROM v_risk_truth WHERE hive_id='{hive}' "
                           f"AND risk_level IN ('high','critical');"))
        termini.append({"terminus": "KPI · top_risk_band hot-assets count (high+critical) +1", "layer": "compute",
                        "measured": a_hot, "expected": base_hot + 1, "ok": a_hot == base_hot + 1})
    finally:
        for rid, rs, rl in orig:
            psql(f"UPDATE asset_risk_scores SET risk_score={rs}, risk_level='{rl}' WHERE id='{rid}';")
    return {
        "nerve": "risk_band__hot_count", "field": "asset_risk_scores.risk_score",
        "input_surface": "predictive", "target": {"hive_id": hive, "asset_name": asset},
        "delta": f"risk {score0}/{level0} → 0.92/critical",
        "baseline": {"risk_score": score0, "risk_level": level0, "hive_hot_count": base_hot},
        "termini": termini, "termini_total": len(termini), "termini_ok": sum(1 for t in termini if t["ok"]),
        "verified": all(t["ok"] for t in termini),
    }


NERVES = {
    "logbook_downtime__mttr": probe_logbook_mttr,
    "logbook_status__open_jobs": probe_logbook_openjobs,
    "inventory_qty__low_stock": probe_inventory_low_stock,
    "pm_anchor__overdue": probe_pm_overdue,
    "pm_anchor__due_soon": probe_pm_due_soon,
    "pm_rpc__compliance": probe_pm_compliance,
    "skillmatrix_badge__level": probe_skillmatrix_level,
    "assethub__criticality_and_rollup": probe_assethub,
    "projectmgr_item__items_done": probe_projectmgr,
    "community_softdelete__is_deleted": probe_community,
    "marketplace_listing__active_count": probe_marketplace,
    "reportsender_report__flags": probe_reportsender,
    "integrations_sync__fresh": probe_integrations,
    "alerthub_ack__status": probe_alerthub,
    "achievements_xp__level": probe_achievements,
    "auditlog_action__hive_scoped": probe_auditlog,
    "risk_band__hot_count": probe_risk_band,
}


def main(argv: list[str]) -> int:
    TMP.mkdir(exist_ok=True)
    which = argv[1] if len(argv) > 1 else "all"
    names = list(NERVES) if which in ("all", "") else [which]

    print("=" * 78)
    print("  __JOURNEY_TRACE -- differential data-lineage nerve-probe (§13 P1)")
    print("  ground truth: docker exec", DB_CONTAINER, "psql")
    print("=" * 78)

    results, any_fail = [], False
    for name in names:
        fn = NERVES.get(name)
        if not fn:
            print(f"  unknown nerve: {name} (have: {', '.join(NERVES)})")
            any_fail = True
            continue
        r = fn()
        results.append(r)
        (TMP / f"journey_trace_{name}.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
        if r.get("error"):
            print(f"\n  ✗ {name}: {r['error']}")
            any_fail = True
            continue
        print(f"\n  NERVE: {r['nerve']}  ({r['field']} on {r['input_surface']})")
        tgt = ", ".join(f"{k}={str(v)[:12]}" for k, v in r.get("target", {}).items())
        print(f"  target: {tgt}  ·  seed Δ={r['delta']}")
        bl = ", ".join(f"{k}={v}" for k, v in r.get("baseline", {}).items())
        print(f"  baseline: {bl}")
        for t in r["termini"]:
            mark = "✅" if t["ok"] else "❌"
            print(f"    {mark} {t['terminus']}")
            print(f"        measured={t['measured']}  expected={t['expected']}")
        print(f"  → {r['termini_ok']}/{r['termini_total']} termini correct  "
              f"[{'NERVE VERIFIED' if r['verified'] else 'DEAD/WRONG NERVE'}]")
        if not r["verified"]:
            any_fail = True

    # Stable roll-up ledger (root artifact) -- ingested by mine_lineage_map.py so
    # a proven nerve flips its lineage_map path verified (closes §13's loop:
    # live probe -> the measured denominator moves off 0%).
    ledger = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/journey_trace.py",
        "nerves": {
            r["nerve"]: {
                "field": r.get("field"),
                "input_surface": r.get("input_surface"),
                "verified": r.get("verified", False),
                "termini_ok": r.get("termini_ok"),
                "termini_total": r.get("termini_total"),
                "consumers_proven": [t["terminus"] for t in r.get("termini", []) if t.get("ok")],
            } for r in results if not r.get("error")
        },
    }
    (ROOT / "journey_trace_results.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 78)
    verified = sum(1 for r in results if r.get("verified"))
    print(f"  {verified}/{len(results)} nerves verified  ·  per-nerve → .tmp/journey_trace_*.json"
          f"  ·  ledger → journey_trace_results.json")
    print("=" * 78)
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
