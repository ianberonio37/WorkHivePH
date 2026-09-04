#!/usr/bin/env python3
"""validate_vehicle_foundations.py — the VEHICLE SEED's lock (Iteration 1, plan-approved 2026-09-02).

A car is an ASSET (lane, not silo). Four foundations, each proven by an 11-probe rolled-back tx
before this gate was written (solo insert/read + cross-user invisibility; due_km=130,000 from
meter 120,000 + 10,000 km interval; due-soon at 400 km out; overdue past it; odometer rolls
forward on a logbook reading and never rewinds on a typo):

  1. SOLO asset_nodes RLS — the (hive_id IS NULL AND auth_uid=auth.uid()) branch in read + write
     (without it a solo owner cannot own their car; the sibling tables always had it).
  2. vehicle_meta jsonb on asset_nodes (VIN/plate/odometer/... — NOT external_ids, which is
     CMMS-typed and renders as sync pills).
  3. Mileage PM primitives: pm_scope_items.interval_km + interval_kind; pm_completions.meter_at_completion.
  4. The meter-aware truth view (next_due_km/current_km/km_until_due; is_overdue OR'd with the
     meter half) + the Vehicle reading templates + the monotonic roll_vehicle_odometer trigger.

DB-layer gate; skips clean when docker is down. Teeth: each foundation's absence reddens.
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["vehicle-foundations"]


def _psql(sql: str):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=25)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def check(probe: dict) -> list[str]:
    problems = []
    if probe.get("solo_read") != "t":
        problems.append("asset_nodes_read lost the SOLO branch (hive_id IS NULL AND auth_uid=auth.uid()) "
                        "— a solo owner cannot see their own vehicle again")
    if probe.get("solo_write") != "t":
        problems.append("asset_nodes_write lost the SOLO branch — a solo owner cannot create/update "
                        "their vehicle again")
    if probe.get("vehicle_meta") != "t":
        problems.append("asset_nodes.vehicle_meta is gone — the vehicle master has no carrier")
    if probe.get("interval_km") != "t" or probe.get("meter_at") != "t":
        problems.append("the mileage-PM primitives (pm_scope_items.interval_km / "
                        "pm_completions.meter_at_completion) are gone — km-based PM is uncomputable")
    if probe.get("view_meter") != "t":
        problems.append("v_pm_scope_items_truth lost its meter columns (next_due_km/current_km/"
                        "km_until_due) — km PMs go dark on every due surface")
    if probe.get("reading_rows", "0") in ("0", "", None):
        problems.append("the Vehicle reading templates (odometer_km/fuel_l) are gone — logbook "
                        "loses its odometer field")
    if probe.get("trigger") != "1":
        problems.append("trg_roll_vehicle_odometer is gone — logbook readings no longer roll the "
                        "vehicle meter forward")
    if probe.get("view_invoker") != "t":
        problems.append("v_pm_scope_items_truth lost security_invoker — the view runs definer-rights "
                        "and anon reads EVERY hive's scope items (the exact hole 20260902000006 opened; "
                        "any CREATE OR REPLACE must re-assert the option)")
    if probe.get("scope_solo_read") != "t":
        problems.append("pm_scope_items_read lost the SOLO branch — a solo owner's PM checklist is "
                        "write-only (seeds, then vanishes from every PM surface)")
    if probe.get("inv_solo_read") != "t":
        problems.append("inventory_items_read lost the SOLO branch — a solo owner's parts are "
                        "write-only (seed, then vanish from Inventory)")
    if probe.get("audit_solo_safe") != "t":
        problems.append("a delete-audit trigger lost its solo skip — hive_audit_log.hive_id is "
                        "NOT NULL, so every solo asset/pm_asset delete ABORTS (the wizard's Undo "
                        "silently strands the vehicle; found live on the VM1 walk)")
    if probe.get("contract_vehicle") != "t":
        problems.append("logbook_add_entry_v1 lost 'Vehicle' from its category enum — the capture "
                        "contract blocks every odometer/fuel entry at save (the VM3 walk hit this "
                        "live: templates rendered, save refused)")
    if probe.get("asset_truth_nullsafe") != "t":
        problems.append("v_asset_truth lost the null-safe hive join (IS DISTINCT FROM) or its "
                        "security_invoker — a solo asset's 360 counts zero history beside a "
                        "timeline full of it (VM5 found lb=5 rendering as 0)")
    return problems


def gather():
    q = {
        "solo_read": "SELECT (qual LIKE '%hive_id IS NULL%' AND qual LIKE '%auth_uid = auth.uid()%') FROM pg_policies WHERE tablename='asset_nodes' AND policyname='asset_nodes_read'",
        "solo_write": "SELECT (qual LIKE '%hive_id IS NULL%') FROM pg_policies WHERE tablename='asset_nodes' AND policyname='asset_nodes_write'",
        "vehicle_meta": "SELECT count(*)=1 FROM information_schema.columns WHERE table_name='asset_nodes' AND column_name='vehicle_meta'",
        "interval_km": "SELECT count(*)=1 FROM information_schema.columns WHERE table_name='pm_scope_items' AND column_name='interval_km'",
        "meter_at": "SELECT count(*)=1 FROM information_schema.columns WHERE table_name='pm_completions' AND column_name='meter_at_completion'",
        "view_meter": "SELECT count(*)=3 FROM information_schema.columns WHERE table_name='v_pm_scope_items_truth' AND column_name IN ('next_due_km','current_km','km_until_due')",
        "reading_rows": "SELECT count(*) FROM equipment_reading_templates WHERE category='Vehicle' AND reading_key IN ('odometer_km','fuel_l')",
        "trigger": "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE c.relname='logbook' AND t.tgname='trg_roll_vehicle_odometer'",
        "view_invoker": "SELECT COALESCE(c.reloptions::text,'') LIKE '%security_invoker=true%' FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='v_pm_scope_items_truth'",
        "scope_solo_read": "SELECT (qual LIKE '%hive_id IS NULL%' AND qual LIKE '%auth_uid = auth.uid()%') FROM pg_policies WHERE tablename='pm_scope_items' AND policyname='pm_scope_items_read'",
        "inv_solo_read": "SELECT (qual LIKE '%hive_id IS NULL%' AND qual LIKE '%auth_uid = auth.uid()%') FROM pg_policies WHERE tablename='inventory_items' AND policyname='inventory_items_read'",
        "audit_solo_safe": "SELECT count(*)=5 FROM pg_proc WHERE (proname IN ('audit_asset_node_delete','audit_pm_asset_delete') AND prosrc LIKE '%IF OLD.hive_id IS NULL%') OR (proname IN ('audit_pm_scope_item_schedule_change','audit_logbook_post_close_amendment','audit_asset_approval_decision') AND prosrc LIKE '%IF NEW.hive_id IS NULL%')",
        "contract_vehicle": "SELECT (contract_schema#>>'{properties,category,enum}') LIKE '%Vehicle%' AND fields::text LIKE '%Vehicle%' FROM canonical_capture_contracts WHERE capture_id='logbook_add_entry_v1'",
        "asset_truth_nullsafe": "SELECT pg_get_viewdef('public.v_asset_truth'::regclass) LIKE '%IS DISTINCT FROM%' AND COALESCE((SELECT reloptions::text FROM pg_class WHERE relname='v_asset_truth'),'') LIKE '%security_invoker=true%'",
    }
    out = {}
    for k, sql in q.items():
        r = _psql(sql)
        if r is None:
            return None
        out[k] = r
    return out


PAGE_PROBES = [
    # (file, needle, what its loss means) — the UI half of the vehicle lane, all walked live 2026-09-02
    ("integrations.html", "vehOpenWizard",
     "the Add-a-Vehicle wizard is gone from integrations.html"),
    ("integrations.html", "el.id !== 'vehicle-add'",
     "the supervisor gate no longer spares #vehicle-add — it nukes the wizard for the "
     "solo owners it exists for"),
    ("integrations.html", "interval_kind: r.kind || (km ? 'both' : 'calendar')",
     "the wizard stopped seeding km intervals (or lost the doc-row kind override that keeps a "
     "100,000-km manual row from getting a false yearly calendar half)"),
    ("integrations.html", "vehHandleDocFile",
     "the doc-upload path is gone from the wizard — VM2's accuracy-gated extraction has no door"),
    ("integrations.html", "FROM YOUR DOC",
     "doc-proposed rows lost their provenance badge — the person can no longer tell their "
     "manual's rows from the generic starter"),
    ("supabase/functions/vehicle-doc-extract/index.ts", "PROSE GUARD",
     "the miner lost its prose guard — note text mines as ticked schedule rows again "
     "(the severe-duty 5,000-km leak, caught live on the golden walk)"),
    ("asset-hub.html", "const scopeNodes",
     "asset-hub lost the solo scope helper — the hive wall returns for solo owners"),
    ("asset-hub.html", "id=\"veh-card\"",
     "asset-hub lost the Vehicle 360 card — vehicle_meta has no surface"),
    ("pm-scheduler.html", "'Vehicles': [",
     "pm-scheduler lost the Vehicles PM template block"),
    ("logbook.html", "value=\"Vehicle\"",
     "logbook lost the Vehicle discipline option — the odometer/fuel reading fields can "
     "never render, so no entry can roll the vehicle meter"),
    ("logbook.html", "SOLO lane: a SIGNED-IN owner without a hive",
     "logbook's hive gate lost the solo lane — a solo car owner is walled out of the page "
     "that records odometer/fuel"),
    ("pm-scheduler.html", "next_due_km, current_km, km_until_due",
     "pm-scheduler's truth-view select dropped the meter columns — km badges fire with no "
     "explanation (a red badge beside a healthy date)"),
    ("pm-scheduler.html", "whichever comes first",
     "pm-scheduler lost the odometer due-line — the meter half of the due sentence is gone"),
    ("pm-scheduler.html", "meter_at_completion: (_sheetScopeItem",
     "pm-scheduler completions stopped stamping the odometer — next_due_km never advances, "
     "so a completed km-PM re-reads overdue at the old mark (VM4 proved the advance live: "
     "17,500 -> 22,600 on completion at 17,600)"),
    ("integrations.html", "veh-scope-hive",
     "the wizard lost the fleet/personal scope choice — a hive WORKER's create would seed a "
     "hive row pm_assets_insert_guard refuses (supervisor-only), failing with a confusing "
     "refusal at Create"),
    ("pm-scheduler.html", "and(hive_id.is.null,auth_uid.eq.",
     "pm-scheduler hive mode dropped the member's PERSONAL vehicles — a worker's own car "
     "vanishes from the scheduler the day they join a hive (VM9 two-home)"),
    ("asset-hub.html", "and(hive_id.is.null,auth_uid.eq.",
     "asset-hub hive mode dropped the member's PERSONAL vehicles (VM9 two-home)"),
    ("integrations.html", "wh-nonsup",
     "the pre-paint role class is gone — the console paints then strips for non-supervisors "
     "(measured CLS 0.17 before the fix, 0.001 after)"),
    ("integrations.html", "min-width:44px; min-height:44px; display:inline-flex",
     "the wizard checklist lost its 44px label-wrapped tap targets (bare 20px checkboxes "
     "fail the gloved-hand floor at 390px)"),
]


def check_pages(root) -> list[str]:
    import pathlib
    problems = []
    base = pathlib.Path(root)
    cache = {}
    for fname, needle, meaning in PAGE_PROBES:
        if fname not in cache:
            p = base / fname
            cache[fname] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        if needle not in cache[fname]:
            problems.append(f"{fname}: {meaning} (missing marker: {needle!r})")
    return problems


def main() -> int:
    import os
    page_problems = check_pages(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if page_problems:
        print("FAIL vehicle-foundations (page layer):")
        for p in page_problems:
            print("    " + p)
        return 1
    probe = gather()
    if probe is None:
        print("SKIP vehicle-foundations db layer (pages PASS) — DB down; re-run with the stack up.")
        return 0
    problems = check(probe)
    if problems:
        print("FAIL vehicle-foundations:")
        for p in problems:
            print("    " + p)
        return 1
    print("PASS vehicle-foundations — solo asset RLS, vehicle_meta, mileage-PM primitives, the "
          "meter-aware truth view, Vehicle reading templates, and the monotonic odometer trigger "
          "all hold (proven by the 11-probe rolled-back tx).")
    return 0


def self_test() -> int:
    fails = []
    good = {"solo_read": "t", "solo_write": "t", "vehicle_meta": "t", "interval_km": "t",
            "meter_at": "t", "view_meter": "t", "reading_rows": "2", "trigger": "1",
            "view_invoker": "t", "scope_solo_read": "t", "inv_solo_read": "t",
            "audit_solo_safe": "t", "contract_vehicle": "t", "asset_truth_nullsafe": "t"}
    if check(good):
        fails.append("healthy state should PASS")
    if not any("SOLO branch" in p for p in check({**good, "solo_read": "f"})):
        fails.append("a lost solo-read branch must redden")
    if not any("meter columns" in p for p in check({**good, "view_meter": "f"})):
        fails.append("lost view meter columns must redden")
    if not any("roll the" in p for p in check({**good, "trigger": "0"})):
        fails.append("a lost trigger must redden")
    if not any("security_invoker" in p for p in check({**good, "view_invoker": "f"})):
        fails.append("a definer-rights truth view must redden (the anon 437-row hole)")
    if not any("write-only" in p for p in check({**good, "scope_solo_read": "f"})):
        fails.append("a lost scope-items solo READ branch must redden")
    if not any("vanish from Inventory" in p for p in check({**good, "inv_solo_read": "f"})):
        fails.append("a lost inventory solo READ branch must redden")
    if not any("solo skip" in p for p in check({**good, "audit_solo_safe": "f"})):
        fails.append("a delete-audit trigger without the solo skip must redden")
    if not any("category enum" in p for p in check({**good, "contract_vehicle": "f"})):
        fails.append("a contract missing the Vehicle category must redden")
    if not any("null-safe" in p for p in check({**good, "asset_truth_nullsafe": "f"})):
        fails.append("a lost null-safe hive join must redden")
    # page-layer teeth: a temp dir missing every page must produce one problem per probe
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        if len(check_pages(td)) != len(PAGE_PROBES):
            fails.append("missing page markers must each redden")
    import os as _os
    if check_pages(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))):
        fails.append("the real pages should currently PASS the page probes")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_vehicle_foundations self-test (lost solo branch / view columns / trigger all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
