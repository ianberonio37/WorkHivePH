#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert page-bank live-walk rows to GATE-backed evidence where a registered prover's fresh report
carries that row's exact cell, green.

WHY. A15 (one-way green): a live-walk row expires whenever a shared file moves — a gate-backed row
re-earns by re-running the gate (+ bank_gate_restamp). The marketplace did this conversion once
(bank_marketplace_gate.py, 905 rows) and its green stopped churning. The page banks still carry
~2,600 live-walk rows, and two prover families now measure the SAME cells those rows claim,
per-page and per-persona/mode — so the conversion is row-specific, not a blanket stamp:

  CN-ux-journey       journey_report.json          personas[] (page, slot P1/P2/P3, five journeys)
  CC failure cells     failure_injection_report.json / _v2  cells[] (page, mode)

RAILS (same as every banker here):
  · the report must be FRESHER than every dep of the row (a stale report cannot testify);
  · only a cell the report marks GREEN converts; '--' / ungraded / missing cells leave the row as-is;
  · every converted row re-classifies through the gate's own classify() or it is reverted;
  · rows already gate-backed, owed, or declared-na are never touched.

USAGE  python tools/bank_prover_reports.py --family journey|failure|all [--apply]
"""
import argparse
import glob
import importlib.util
import io
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load(name):
    p = os.path.join(ROOT, name)
    if not os.path.exists(p):
        return None, 0
    return json.load(open(p, encoding="utf-8")), os.path.getmtime(p)


# ── family adapters: (bank row) -> (cell verdict, human line) or None ────────────────────────────

JOURNEY_FIELDS = {          # oracle_key -> journey_report persona field (schema read 2026-08-21:
    "first_run_to_value": "first_run",   # persona keys are first_run/repeat/two_sided/handoff/abandon,
    "repeat_visit": "repeat",            # each {ok, verdict} or None when not walked for that persona)
    "two_sided_same_object": "two_sided",
    "cross_surface_handoff": "handoff",
    "abandon_resume": "abandon",
}


def journey_lookup(report):
    idx = {}
    for p in report.get("personas", []):
        idx[(p.get("page"), p.get("slot"))] = p
    def look(row):
        fld = JOURNEY_FIELDS.get(row.get("oracle_key"))
        if not fld:
            return None
        p = idx.get((row.get("page"), (row.get("subject") or {}).get("key")))
        if not p:
            return None
        cell = p.get(fld)
        ok = (cell or {}).get("ok") if isinstance(cell, dict) else cell
        if ok is not True and str(ok).upper() != "PASS":
            return None                       # '--', failed, or unwalked: leave the row alone
        reached = p.get("firstRead") or {}
        return (f"walked as {p.get('label') or (row.get('subject') or {}).get('key')}: "
                f"{row.get('oracle_key')} PASS"
                + (f"; reached value {reached.get('chars')} chars, {reached.get('actionable')} "
                   f"actionable" if reached.get("chars") else ""))
    return look


FAIL_ORACLES = {"fail_500", "fail_401", "fail_timeout", "fail_offline", "fail_partial",
                "fail_slow", "fail_null_field"}


def failure_lookup(report_v1, report_v2):
    idx = {}
    for rep, view in ((report_v1, "V1"), (report_v2, "V2")):
        if not rep:
            continue
        for c in rep.get("cells", []):
            idx[(c.get("page"), c.get("mode"), view)] = c
    def look(row):
        ok_ = row.get("oracle_key")
        if ok_ not in FAIL_ORACLES:
            return None
        view = (row.get("subject") or {}).get("key") or "V1"
        view = view if view in ("V1", "V2") else "V1"
        c = idx.get((row.get("page"), ok_, view))
        if not c or c.get("ok") is not True:
            return None                       # ungraded (N/A) or failing: leave the row alone
        return f"{view} {ok_}: {str(c.get('verdict') or '')[:180]}"
    return look


# The flow->(page,view) map shared by every flow-keyed prover family (double_fire, did_it_land,
# wrong_then_fix, what_happens_next). Each entry is PROVEN: the flow's submit control lives in the
# dialog matching dialog_targets' (page, view, modal) triple. Page-level/unproven flows are absent.
FLOW_VIEW = {
    "inventory":             ("inventory", "V2"),        # Save Part in part-modal
    "pm-scheduler-edit":     ("pm-scheduler", "V3"),     # Save Changes in pm-edit-modal
    "pm-scheduler-complete": ("pm-scheduler", "V2"),     # completion-sheet
    "hive-intent":           ("hive", "V3"),             # Save in intent-capture
    "community-thread":      ("community", "V2"),        # Reply in thread-overlay
    "community":             ("community", "V3"),        # Post to Hive in composer-overlay
    "skillmatrix-exam":      ("skillmatrix", "V3"),      # Submit exam in exam-modal
    "index-signin":          ("index", "V3"),            # Sign In in signin-modal
    "asset-hub-weibull":     ("asset-hub", "V3"),        # Compute Weibull in rel-panel-weibull
    "project-manager-co":    ("project-manager", "V3"),  # Submit for approval in modal-co
    "report-sender-contacts": ("report-sender", "V3"),   # Save Contact in sheet-overlay
}


def flow_view_lookup(report, oracle_key, ok_pred, describe):
    cells = {}
    for fk, cell in (report.get("pages") or {}).items():
        pv = FLOW_VIEW.get(fk)
        if pv and ok_pred(cell):
            cells[pv] = (fk, cell)
    def look(row):
        if row.get("oracle_key") != oracle_key:
            return None
        view = (row.get("subject") or {}).get("key") or "V1"
        hit = cells.get((row.get("page"), view))
        if not hit:
            return None
        fk, cell = hit
        return describe(view, fk, cell)
    return look


def convert(V, family, gate_id, report_names, look, apply, na_kind=False):
    newest_report = 0
    for n in report_names:
        p = os.path.join(ROOT, n)
        if os.path.exists(p):
            newest_report = max(newest_report, os.path.getmtime(p))
    today = date.today().isoformat()
    tot_conv = tot_skip = 0
    for bank_path in sorted(glob.glob(os.path.join(ROOT, "banks", "*_live_mcp_bank.json"))):
        reg = json.load(open(bank_path, encoding="utf-8"))
        rows = reg.get("scenarios") if isinstance(reg, dict) else reg
        if not rows:
            continue
        gates, urls = V.gate_ids(), V.surface_urls(reg)
        conv = 0
        for row in rows:
            ev = row.get("evidence")
            # declared-na rows are IN scope since 2026-08-22: a hand-declared NA expires on R4
            # (whole-file sha moved) and nothing could ever refresh it - while the view families
            # now MEASURE the same (page,view,oracle) cells each cycle. A fresh measured cell may
            # re-stamp an R4-expired declaration (measured NA > declared NA); a green declaration
            # is left alone, and every existing rail (report newer than deps, classify-green-after)
            # still applies.
            kind0 = ev.get("kind") if isinstance(ev, dict) else None
            if kind0 not in ("live-walk", "declared-na"):
                continue
            if row.get("status") != "green":
                continue                     # owed rows need a real walk, not a conversion
            state, _ = V.classify(row, gates, urls)
            if kind0 == "declared-na" and state != "stale":
                continue                     # nothing to refresh
            if state not in ("stale", "green"):
                continue
            line = look(row)
            if not line:
                tot_skip += 1
                continue
            deps = ev.get("depends_on") or [f"{row.get('page')}.html", "utils.js"]
            newest_dep = max((os.path.getmtime(os.path.join(ROOT, d))
                              for d in deps if os.path.exists(os.path.join(ROOT, d))), default=0)
            if newest_report < newest_dep:
                tot_skip += 1                # the prover has not seen the current file
                continue
            before = json.loads(json.dumps(ev))
            if na_kind and str(line).startswith("NA:"):
                row["evidence"] = {
                    "kind": "declared-na",
                    "ref": f"{today} — measured not-applicable by the {gate_id} view pass",
                    "asserts": str(line)[3:],
                    "depends_on": deps,
                    "sha": V.sha_of(deps),
                    "fn_digests": V.fn_digests(deps),
                    "walked_at": today,
                }
                st2, why2 = V.classify(row, gates, urls)
                if st2 != "green":
                    row["evidence"] = before
                    tot_skip += 1
                    continue
                conv += 1
                continue
            checked = (ev.get("checked") if line == "KEEP_CHECKED"
                       else (f"converted from live-walk to gate-backed {today}: the registered gate "
                             f"{gate_id} measures this exact cell each run — {line}. Re-earns via "
                             f"the gate + bank_gate_restamp instead of expiring on every shared-file "
                             f"edit (A15 one-way green; the marketplace conversion precedent)."))
            row["evidence"] = {
                "kind": "gate",
                "ref": f"gate:{gate_id}",
                "asserts": row.get("oracle") or ev.get("asserts") or "",
                "checked": checked,
                "depends_on": deps,
                "sha": V.sha_of(deps),
                "fn_digests": V.fn_digests(deps),
                "walked_at": today,
            }
            st2, why2 = V.classify(row, gates, urls)
            if st2 != "green":
                row["evidence"] = before
                tot_skip += 1
                continue
            conv += 1
        if conv and apply:
            # ATOMIC write (2026-08-31): the bare open(bank_path,"w") truncated the bank in place;
            # a concurrent reader (the board's own validate_live_mcp_bank gate) could read a torn or
            # empty file and false-FAIL. Temp + os.replace so a reader sees the whole old or whole
            # new file, never a partial one. Same open_w_truncates fix applied to bank_gate_restamp.
            tmp = bank_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, bank_path)
        if conv:
            print(f"  {os.path.basename(bank_path):44s} {GREEN}{conv} converted{RST}")
        tot_conv += conv
    print(f"  {family:8s} {GREEN}{tot_conv} converted{RST} · {DIM}{tot_skip} left as-is (no green "
          f"cell / stale report / gate would reject){RST}")
    return tot_conv


# ── page-level report adapters. The reports below measure at PAGE level while the bank rows are
# per-VIEW (V1/V2/V3): a page-level reading may only settle the V1 (page) row — converting a V2/V3
# view-scoped claim on page-level evidence would be the recorded wrong-subject sin. The one
# exception is back_out V2/V3, where prove_modal_escape_live measures the EXACT (page, view) target.


def page_level_lookup(rows_by_page, oracle_keys, view="V1"):
    def look(row):
        if row.get("oracle_key") not in oracle_keys:
            return None
        if ((row.get("subject") or {}).get("key") or "V1") != view:
            return None
        cell = rows_by_page.get(row.get("page"))
        if not cell or cell.get("ok") is not True:
            return None
        return f"{row.get('oracle_key')} ({view}): {str(cell.get('verdict') or cell.get('why') or 'PASS')[:180]}"
    return look


def modal_escape_lookup(report):
    idx = {}
    for t in report.get("targets", []):
        if t.get("ok") is True:
            idx[(t.get("page"), t.get("view"))] = t
    def look(row):
        if row.get("oracle_key") != "back_out":
            return None
        view = (row.get("subject") or {}).get("key")
        if view not in ("V2", "V3"):
            return None
        t = idx.get((row.get("page"), view))
        if not t:
            return None
        extra = ("state view: Escape leaves the state intact" if t.get("kind") == "state"
                 else f"Escape closes #{t.get('modal')}"
                      + (", focus returns to the opener" if t.get("focusRestored") else ""))
        return f"back_out ({view}): {extra}"
    return look


def a11y_lookup(report):
    # cells carry (page, view, family) since the 2026-08-21 V2/V3 pass: the prover opens each view
    # from the shared dialog_targets roster and scopes the scans to the view root, so a V2/V3 row is
    # settled by ITS OWN view's measurement, never by V1's (the wrong-subject rail).
    idx = {}
    for c in report.get("cells", []):
        if c.get("ok") is True:
            idx[(c.get("page"), c.get("view") or "V1", c.get("family"))] = c
    def look(row):
        ok_ = row.get("oracle_key")
        if ok_ not in ("focus_visible", "reduced_motion", "icon_only_name", "no_raw_enum"):
            return None
        view = (row.get("subject") or {}).get("key") or "V1"
        if view not in ("V1", "V2", "V3"):
            return None
        c = idx.get((row.get("page"), view, ok_))
        if not c:
            return None
        return f"{ok_} ({view}): {str(c.get('verdict') or '')[:180]}"
    return look


def quota_lookup(report):
    pages = report.get("pages") or {}
    def look(row):
        if row.get("oracle_key") != "rate_limit_legible":
            return None
        if ((row.get("subject") or {}).get("key") or "V1") != "V1":
            return None
        c = pages.get(row.get("page"))
        # the quota prover covers only pages WITH an edge invoke; a page absent from its roster is
        # not settled by it — leave those rows for their own judgment. Its verdict field is
        # status: "PASS" (schema read 2026-08-21), not ok:true.
        if not isinstance(c, dict) or str(c.get("status")).upper() != "PASS":
            return None
        return f"rate_limit_legible (V1): {str(c.get('message') or c.get('why') or 'held at 429, in-page notice')[:160]}"
    return look


def jwt_lookup(report):
    # jwt_not_body is a TRANSPORT claim with two halves, both platform-proven: the page may well put
    # hive_id in a payload, but (1) gateway-tenancy proves 0 edge sites trust a client-sent tenant
    # (resolveIdentity/resolveTenancy chokepoint, unsafe_count in the fresh report), and (2) every
    # REST write lands under RLS whose policies derive identity from auth.uid() (policy-hive-binding,
    # rls_tenant_isolation both green). No per-page cell exists because the mechanism is not
    # per-page — the page cannot opt out of the chokepoint. That is exactly when a platform gate is
    # the STRONGER evidence (the R2-hyphen lesson: whole-layer gates beat weaker live-walks).
    unsafe = int((report or {}).get("unsafe_count", 1))
    def look(row):
        if row.get("oracle_key") != "jwt_not_body":
            return None
        if unsafe != 0:
            return None
        return ("jwt_not_body: gateway-tenancy reports 0 edge sites trusting a client-sent tenant; "
                "REST writes bind identity via auth.uid() under RLS (policy-hive-binding)")
    return look


SECURITY_CHECK_MARK = "WHICH OF THE GATE'S CHECKS PROVE THIS ORACLE"


def security_kindflip_lookup(report):
    # These rows were ALREADY gate-derived: their checked text opens with "WHICH OF THE GATE'S
    # CHECKS PROVE THIS ORACLE (named, not inherited...)" and names hive-isolation's own cross-tenant
    # checks (read_logbook_xhive, read_cxp_xhive, ...). They were merely recorded as kind=live-walk,
    # which makes them expire on page edits although the page is not what proves them. The flip keeps
    # each row's OWN bespoke reasoning verbatim and re-anchors the kind to the gate that carries it —
    # nothing is asserted here that the original walk did not already argue. Rows WITHOUT that
    # citation mark are left alone: a row whose reasoning does not name the gate's checks has not
    # earned the gate's evidence.
    fails = (report or {}).get("fail")
    healthy = report is not None and not (report or {}).get("skipped") and not fails
    def look(row):
        if row.get("oracle_key") not in ("bola_object", "bfla_function", "tenant_boundary",
                                          "boundary_not_emptiness"):
            return None
        if not healthy:
            return None
        checked = str((row.get("evidence") or {}).get("checked") or "")
        if SECURITY_CHECK_MARK not in checked:
            return None
        return "KEEP_CHECKED"          # sentinel: preserve the row's own reasoning verbatim
    return look


# batch-1 walk instruments, promoted to gates 2026-08-21. Page-level reports settle V1 rows only
# (the per-view wrong-subject rail); each entry: (family key, gate id, report, row-oracle-keys,
# per-page pass predicate — read from each prover's OWN verdict fields, not guessed).
BATCH1 = [
    ("didland",  "cb_did_it_land",          "did_it_land_report.json",     {"did_it_land"},
     lambda c: c.get("status") == "PASS"),
    ("retry",    "cb_retry_path",           "retry_path_report.json",      {"retry_path"},
     lambda c: c.get("outcome") == "PASS"),
    ("countsrc", "cf_count_matches_source", "count_matches_source_report.json", {"count_matches_source"},
     lambda c: bool(c.get("checks")) and all(x.get("ok") for x in c.get("checks", []))),
    ("wrongfix", "cb_wrong_then_fix",       "wrong_then_fix_report.json",  {"wrong_then_fix"},
     lambda c: c.get("status") == "PASS"),
    ("effect",   "cf_effect_visible",       "effect_visible_report.json",  {"effect_visible", "effect_in_db"},
     lambda c: c.get("drove") and c.get("effect_in_db") is True and c.get("effect_visible") is True),
    ("whatnext", "cb_what_happens_next",    "what_happens_next_report.json", {"what_happens_next"},
     lambda c: c.get("status") == "PASS"),
    ("doubletap", "cb_double_fire",         "double_fire_report.json",     {"double_tap"},
     lambda c: c.get("status") == "PASS"),
    # batch-2 promotions (2026-08-21): same page-level V1-only rail.
    ("fallback", "cd_fallback_engaged",     "fallback_engaged_report.json", {"fallback_engaged"},
     lambda c: c.get("ok") is True),
    ("numexpl",  "cm_number_explained",     "number_explained_report.json", {"number_explained"},
     lambda c: c.get("ok") is True),
    ("abandon2", "cb_abandon_resume",       "abandon_resume_report.json",  {"abandon_resume"},
     lambda c: c.get("outcome") == "PASS"),
    ("cost",     "cm_cost_before_commit",   "cost_before_commit_report.json", {"what_does_it_cost"},
     lambda c: c.get("status") == "PASS" if "status" in c else c.get("ok") is True),
]


def batch1_lookup(rows_by_page, oracle_keys, pred):
    def look(row):
        if row.get("oracle_key") not in oracle_keys:
            return None
        if ((row.get("subject") or {}).get("key") or "V1") != "V1":
            return None
        c = rows_by_page.get(row.get("page"))
        if not c or not pred(c):
            return None
        return f"{row.get('oracle_key')} (V1): page cell PASS in the gate's fresh report"
    return look


def viewlevel_lookup(rows, oracle_keys, ok_pred, view_field="view"):
    # (page, view)-matched: these reports grade PER VIEW, so V2/V3 rows convert on their OWN cells.
    idx = {}
    for c in rows:
        if isinstance(c, dict) and ok_pred(c):
            idx[(c.get("page"), c.get(view_field) or "V1")] = c
    def look(row):
        if row.get("oracle_key") not in oracle_keys:
            return None
        view = (row.get("subject") or {}).get("key") or "V1"
        c = idx.get((row.get("page"), view))
        if not c:
            return None
        return f"{row.get('oracle_key')} ({view}): view cell green in the gate's fresh report"
    return look


def slow_honest_lookup(report_v1, report_v2):
    # slow_honest maps to the SAME measured cell as fail_slow: a 6s read must show a busy state at
    # 2.5s. cc_failure_injection measures exactly that per (page, view); the oracle name differs,
    # the measurement is identical.
    idx = {}
    for rep, view in ((report_v1, "V1"), (report_v2, "V2")):
        if not rep:
            continue
        for c in rep.get("cells", []):
            if c.get("mode") == "fail_slow" and c.get("ok") is True:
                idx[(c.get("page"), view)] = c
    def look(row):
        if row.get("oracle_key") != "slow_honest":
            return None
        view = (row.get("subject") or {}).get("key") or "V1"
        view = view if view in ("V1", "V2") else "V1"
        c = idx.get((row.get("page"), view))
        if not c:
            return None
        return f"slow_honest ({view}) via fail_slow: {str(c.get('verdict'))[:150]}"
    return look


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="all",
                    choices=["journey", "failure", "refused", "backout", "a11y", "quota", "jwt",
                             "security", "batch1", "viewlevel", "session", "cost", "doubletap", "flowland", "rateviews", "numviews", "backnavviews", "offlineviews", "retryviews", "fallbackviews", "all"])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    V = _gate()
    total = 0
    if a.family in ("journey", "all"):
        rep, _ = _load("journey_report.json")
        if rep:
            total += convert(V, "journey", "cn_journey", ["journey_report.json"],
                             journey_lookup(rep), a.apply)
        else:
            print(f"  {YEL}journey_report.json missing — run prove_journey.mjs first{RST}")
    if a.family in ("failure", "all"):
        v1, _ = _load("failure_injection_report.json")
        v2, _ = _load("failure_injection_v2_report.json")
        if v1 or v2:
            total += convert(V, "failure", "cc_failure_injection",
                             ["failure_injection_report.json", "failure_injection_v2_report.json"],
                             failure_lookup(v1, v2), a.apply)
        else:
            print(f"  {YEL}failure_injection reports missing — run the prover first{RST}")
    if a.family in ("refused", "all"):
        rep, _ = _load("why_refused_report.json")
        if rep:
            byp = {p.get("page"): p for p in rep.get("pages", [])}
            total += convert(V, "refused", "cm_why_refused", ["why_refused_report.json"],
                             page_level_lookup(byp, {"why_refused"}), a.apply)
            # the view pass (2026-08-22): the report now grades V2/V3 cells per dialog_targets view,
            # so view-scoped why_refused rows convert on their OWN cells - same shape as viewlevel
            total += convert(V, "refusedV", "cm_why_refused", ["why_refused_report.json"],
                             viewlevel_lookup(rep.get("views") or [], {"why_refused"},
                                              lambda c: c.get("ok") is True), a.apply)
            # DOUBLY-PROVEN no-subject views -> declared-na. The prover tried BOTH induction paths
            # (Escape+reopen AND a fresh first open under a pre-installed refusal) and neither made
            # the view issue a single REST read: the view populates from memory, so "does the view
            # say WHY the server refused" has no subject there. Recorded as declared-na with the
            # measurement as its reasoning and the view's LIVING gates named as the replacement.
            noread = {}
            for c in (rep.get("views") or []):
                if c.get("ok") is None and "NOR on a fresh first open" in str(c.get("verdict") or ""):
                    noread[(c.get("page"), c.get("view") or "V1")] = c
            def _na_look(row):
                if row.get("oracle_key") != "why_refused":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = noread.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"why_refused ({view}): measured on BOTH induction paths - the view issues no "
                        "REST read of its own (reopen and fresh-first-open both counted zero), so the "
                        "refusal oracle has no subject; the view's interaction is gated by "
                        "co_modal_escape_live + cl_a11y_states, which stay its living coverage")
            total += convert(V, "refusedNA", "cm_why_refused", ["why_refused_report.json"],
                             _na_look, a.apply, na_kind=True)
    if a.family in ("cost", "all"):
        # what_does_it_cost per (page, view) from prove_cost_views.mjs (2026-08-22): PASS cells
        # convert gate-backed; NA cells (no commit control in the view, proven by enumeration)
        # convert declared-na; ungraded-for-declaration cells are left for the FLOWS list.
        rep, _ = _load("cost_views_report.json")
        if rep:
            total += convert(V, "costV", "cm_cost_views", ["cost_views_report.json"],
                             viewlevel_lookup(rep.get("views") or [], {"what_does_it_cost"},
                                              lambda c: c.get("ok") is True), a.apply)
            nacells = {}
            for c in (rep.get("views") or []):
                if c.get("na"):
                    nacells[(c.get("page"), c.get("view") or "V1")] = c
            def _cost_na(row):
                if row.get("oracle_key") != "what_does_it_cost":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = nacells.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"what_does_it_cost ({view}): {str(c.get('verdict'))[3:280]} - measured by "
                        "prove_cost_views.mjs; if this view ever gains a commit control the cell "
                        "re-enters judgment on the next sweep")
            total += convert(V, "costNA", "cm_cost_views", ["cost_views_report.json"],
                             _cost_na, a.apply, na_kind=True)
    if a.family in ("doubletap", "all"):
        rep, _ = _load("double_fire_report.json")
        if rep:
            total += convert(V, "doubletap", "cb_double_fire", ["double_fire_report.json"],
                             flow_view_lookup(rep, "double_tap",
                                 lambda c: isinstance(c.get("writesAfter1"), int)
                                           and c.get("writesAfter1") >= 1
                                           and c.get("writesAfter1") == c.get("writesAfter2"),
                                 lambda view, fk, c: (
                                     f"double_tap ({view}): flow '{fk}' pressed '{c.get('control')}' twice "
                                     f"with every write HELD in-page - {c.get('writesAfter1')} write after "
                                     f"press one, still {c.get('writesAfter2')} after press two")),
                             a.apply)
    if a.family in ("flowland", "all"):
        for fam, repname, gate, okey in (
                ("didland",  "did_it_land_report.json",      "cb_did_it_land",       "did_it_land"),
                ("wrongfix", "wrong_then_fix_report.json",   "cb_wrong_then_fix",    "wrong_then_fix"),
                ("nextfam",  "what_happens_next_report.json","cb_what_happens_next", "what_happens_next")):
            rep, _ = _load(repname)
            if rep:
                total += convert(V, fam, gate, [repname],
                                 flow_view_lookup(rep, okey,
                                     lambda c: c.get("status") == "PASS",
                                     lambda view, fk, c, _o=okey: (
                                         f"{_o} ({view}): flow '{fk}' PASS - "
                                         f"{str(c.get('why') or c.get('message') or '')[:150]}")),
                                 a.apply)
    if a.family in ("rateviews", "all"):
        # rate_limit_legible per (page, view) from prove_rate_views.mjs (2026-08-22): PASS cells
        # convert gate-backed; doubly-proven no-read cells convert declared-na.
        rep, _ = _load("rate_views_report.json")
        if rep:
            total += convert(V, "rateV", "cm_rate_views", ["rate_views_report.json"],
                             viewlevel_lookup(rep.get("views") or [], {"rate_limit_legible"},
                                              lambda c: c.get("ok") is True), a.apply)
            rna = {}
            for c in (rep.get("views") or []):
                verd = str(c.get("verdict") or "")
                if c.get("ok") is None and (c.get("na") or "NOR on a fresh first open" in verd):
                    rna[(c.get("page"), c.get("view") or "V1")] = c
            def _rate_na(row):
                if row.get("oracle_key") != "rate_limit_legible":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = rna.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"rate_limit_legible ({view}): {str(c.get('verdict'))[:260]}")
            total += convert(V, "rateNA", "cm_rate_views", ["rate_views_report.json"],
                             _rate_na, a.apply, na_kind=True)
    if a.family in ("numviews", "all"):
        # number_explained per (page, view) from prove_number_views.mjs (2026-08-22): PASS cells
        # (every derived figure carries naming context) convert gate-backed; no-derived-figure
        # cells convert declared-na. The vocab half stays FINDINGS-ONLY - one_vocabulary's real
        # oracle is CROSS-surface naming, which a per-view snake_case check cannot settle.
        rep, _ = _load("number_views_report.json")
        if rep:
            nv = {}
            nvna = {}
            for c in (rep.get("views") or []):
                num = c.get("numbers") or {}
                key = (c.get("page"), c.get("view") or "V1")
                if num.get("ok") is True:
                    nv[key] = c
                elif num.get("na"):
                    nvna[key] = c
            def _nv_look(row):
                if row.get("oracle_key") != "number_explained":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = nv.get((row.get("page"), view))
                if not c:
                    return None
                return f"number_explained ({view}): {str((c.get('numbers') or {}).get('verdict'))[:180]}"
            total += convert(V, "numV", "cm_number_views", ["number_views_report.json"],
                             _nv_look, a.apply)
            def _nv_na(row):
                if row.get("oracle_key") != "number_explained":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = nvna.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"number_explained ({view}): {str((c.get('numbers') or {}).get('verdict'))[4:240]}")
            total += convert(V, "numNA", "cm_number_views", ["number_views_report.json"],
                             _nv_na, a.apply, na_kind=True)
    if a.family in ("backnavviews", "all"):
        # back_nav per (page, view) from prove_backnav_views.mjs (2026-08-22): browser BACK out of
        # an open sheet leaves no orphaned overlay/locked body, judged for both the history-state
        # sheet (closes in place) and the plain sheet (leaves cleanly).
        rep, _ = _load("backnav_views_report.json")
        if rep:
            total += convert(V, "backnavV", "cm_backnav_views", ["backnav_views_report.json"],
                             viewlevel_lookup(rep.get("views") or [], {"back_nav"},
                                              lambda c: c.get("ok") is True), a.apply)
    if a.family in ("retryviews", "all"):
        # retry_path per (page, view) from prove_retry_views.mjs (2026-08-22): PASS cells (failure
        # painted, the view's own retry re-attempted after the cause cleared, content recovered)
        # convert gate-backed; NA cells (no read of its own / memory-rendered under induction, the
        # rate-views subject discriminator) convert declared-na.
        rep, _ = _load("retry_views_report.json")
        if rep:
            total += convert(V, "retryV", "cm_retry_views", ["retry_views_report.json"],
                             viewlevel_lookup(rep.get("views") or [], {"retry_path"},
                                              lambda c: c.get("ok") is True), a.apply)
            tna = {}
            for c in (rep.get("views") or []):
                if c.get("ok") is None and c.get("na"):
                    tna[(c.get("page"), c.get("view") or "V1")] = c
            def _retry_na(row):
                if row.get("oracle_key") != "retry_path":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = tna.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"retry_path ({view}): {str(c.get('verdict'))[4:260]}")
            total += convert(V, "retryNA", "cm_retry_views", ["retry_views_report.json"],
                             _retry_na, a.apply, na_kind=True)
    if a.family in ("fallbackviews", "all"):
        # fallback_engaged per (page, view) from prove_fallback_views.mjs (2026-08-22): PASS cells
        # (the view's own edge call 500'd, content rendered, the view names a stored source or
        # announces the failure - both judged as a per-sentence delta against the healthy-open
        # baseline) convert gate-backed; measured no-primary cells convert declared-na.
        rep, _ = _load("fallback_views_report.json")
        if rep:
            total += convert(V, "fbV", "cm_fallback_views", ["fallback_views_report.json"],
                             viewlevel_lookup(rep.get("views") or [], {"fallback_engaged"},
                                              lambda c: c.get("ok") is True), a.apply)
            fna = {}
            for c in (rep.get("views") or []):
                if c.get("ok") is None and c.get("na"):
                    fna[(c.get("page"), c.get("view") or "V1")] = c
            def _fb_na(row):
                if row.get("oracle_key") != "fallback_engaged":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = fna.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"fallback_engaged ({view}): {str(c.get('verdict'))[4:260]}")
            total += convert(V, "fbNA", "cm_fallback_views", ["fallback_views_report.json"],
                             _fb_na, a.apply, na_kind=True)
    if a.family in ("offlineviews", "all"):
        # fail_offline per (page, view) from prove_offline_refusal's per-case artifact (2026-08-22).
        # CASE_VIEW is PROVEN against dialog_targets: each case's control lives in that view's modal
        # (contact/Save Contact in report-sender's sheet-overlay = V3; reply in community's
        # thread-overlay = V2; exam in skillmatrix's exam-modal = V3; lessons + scopestatus both act
        # inside project-manager's detail-view = V2). Unproven cases are deliberately absent.
        CASE_VIEW = {
            "contact":     ("report-sender", "V3"),
            "reply":       ("community", "V2"),
            "exam":        ("skillmatrix", "V3"),
            "lessons":     ("project-manager", "V2"),
            "scopestatus": ("project-manager", "V2"),
        }
        rep, _ = _load("offline_refusal_report.json")
        if rep:
            cells = {}
            for ck, cell in (rep.get("cases") or {}).items():
                pv = CASE_VIEW.get(ck)
                if pv and cell.get("ok") is True:
                    cells[pv] = (ck, cell)
            def _off_look(row):
                if row.get("oracle_key") != "fail_offline":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                hit = cells.get((row.get("page"), view))
                if not hit:
                    return None
                ck, cell = hit
                return (f"fail_offline ({view}): case '{ck}' driven offline (navigator.onLine overridden "
                        f"AND network cut) - refusedBeforeFiring={cell.get('refusedBeforeFiring')}, "
                        f"saidSo={cell.get('saidSo')}: \"{str(cell.get('said'))[:120]}\"")
            total += convert(V, "offlineV", "cg_offline_views", ["offline_refusal_report.json"],
                             _off_look, a.apply)
    if a.family in ("backout", "all"):
        rep, _ = _load("back_out_report.json")
        if rep:
            byp = {p.get("page"): p for p in rep.get("pages", [])}
            total += convert(V, "backout", "co_back_out", ["back_out_report.json"],
                             page_level_lookup(byp, {"back_out"}), a.apply)
        mrep, _ = _load("modal_escape_live_report.json")
        if mrep:
            total += convert(V, "backout23", "co_modal_escape_live",
                             ["modal_escape_live_report.json"], modal_escape_lookup(mrep), a.apply)
    if a.family in ("a11y", "all"):
        rep, _ = _load("a11y_states_report.json")
        if rep:
            total += convert(V, "a11y", "cl_a11y_states", ["a11y_states_report.json"],
                             a11y_lookup(rep), a.apply)
    if a.family in ("quota", "all"):
        rep, _ = _load("quota_legible_report.json")
        if rep:
            total += convert(V, "quota", "cm_quota_legible", ["quota_legible_report.json"],
                             quota_lookup(rep), a.apply)
    if a.family in ("jwt", "all"):
        rep, _ = _load("gateway_tenancy_report.json")
        if rep:
            total += convert(V, "jwt", "gateway-tenancy", ["gateway_tenancy_report.json"],
                             jwt_lookup(rep), a.apply)
    if a.family in ("security", "all"):
        rep, _ = _load("hive_isolation_report.json")
        if rep:
            total += convert(V, "security", "hive-isolation", ["hive_isolation_report.json"],
                             security_kindflip_lookup(rep), a.apply)
    if a.family in ("viewlevel", "all"):
        rep, _ = _load("source_chip_report.json")
        if rep:
            rows_ = rep.get("views") or rep.get("results") or []
            total += convert(V, "srcchip", "cf_source_chip", ["source_chip_report.json"],
                             viewlevel_lookup(rows_, {"source_chip_true"},
                                              lambda c: c.get("ok") is True), a.apply)
        rep, _ = _load("units_visible_report.json")
        if rep:
            rows_ = rep.get("views") or rep.get("pages") or rep.get("results") or []
            total += convert(V, "unitsvis", "cf_units_visible", ["units_visible_report.json"],
                             viewlevel_lookup(rows_, {"units_visible"},
                                              lambda c: c.get("ok") is True), a.apply)
        # units_visible view cells that ABSTAIN (no dimension-labelled number renders in the
        # dialog) are measured not-applicable: the oracle has no subject there (2026-08-22).
        rep_u, _ = _load("units_visible_report.json")
        if rep_u:
            una = {}
            for c in (rep_u.get("views") or []):
                if c.get("ok") is None and not c.get("error"):
                    una[(c.get("page"), c.get("view") or "V1")] = c
            def _units_na(row):
                if row.get("oracle_key") != "units_visible":
                    return None
                view = (row.get("subject") or {}).get("key") or "V1"
                c = una.get((row.get("page"), view))
                if not c:
                    return None
                return ("NA:" + f"units_visible ({view}): the opened view renders no dimension-labelled "
                        "quantity (0 examined by the eleven-dimension lens with counted-noun and "
                        "spelled-out-unit vocabularies), so the units oracle has no subject; a view "
                        "that gains a dimensioned figure re-enters judgment on the next sweep")
            total += convert(V, "unitsNA", "cf_units_visible", ["units_visible_report.json"],
                             _units_na, a.apply, na_kind=True)
        rep, _ = _load("zoom200_report.json")
        if rep:
            byp = {p.get("page"): p for p in (rep.get("pages") or []) if p.get("ok") is True}
            total += convert(V, "zoom200", "cj_zoom200", ["zoom200_report.json"],
                             page_level_lookup(byp, {"zoom200"}), a.apply)
        v1, _ = _load("failure_injection_report.json")
        v2, _ = _load("failure_injection_v2_report.json")
        if v1 or v2:
            total += convert(V, "slowhon", "cc_failure_injection",
                             ["failure_injection_report.json", "failure_injection_v2_report.json"],
                             slow_honest_lookup(v1, v2), a.apply)
    if a.family in ("session", "all"):
        # session_died/dialog_session_died and session_expiry: view-matched fresh reports from the
        # 2026-08-21 batch-3 runs (co_session_died 16 pages clean, co_dialog_session_died 34 views).
        rep, _ = _load("session_died_report.json")
        if rep:
            byp = {p.get("page"): p for p in (rep.get("pages") or [])
                   if p.get("redirected") or p.get("newAuthForm")}
            total += convert(V, "sessdied", "co_session_died", ["session_died_report.json"],
                             page_level_lookup({k: dict(v, ok=True) for k, v in byp.items()},
                                               {"session_died"}), a.apply)
        rep, _ = _load("session_expiry_report.json")
        if rep:
            rows_ = rep.get("targets") or rep.get("pages") or []
            total += convert(V, "sessexp", "co_dialog_session_died", ["session_expiry_report.json"],
                             viewlevel_lookup(rows_, {"session_expiry"},
                                              lambda c: c.get("ok") is True), a.apply)
        rep, _ = _load("dialog_a11y_report.json")
        if rep:
            rows_ = rep.get("targets") or []
            ok3 = lambda c: c.get("iconOk") is True and c.get("focusOk") is True and c.get("motionOk") is True
            for fam_key, oracle in (("dlgfocus", "focus_visible"), ("dlgicon", "icon_only_name"),
                                     ("dlgmotion", "reduced_motion")):
                total += convert(V, fam_key, "cl_dialog_a11y", ["dialog_a11y_report.json"],
                                 viewlevel_lookup(rows_, {oracle}, ok3), a.apply)
    if a.family in ("batch1", "all"):
        for fam, gid, repname, keys, pred in BATCH1:
            rep, _ = _load(repname)
            if not rep:
                continue
            rows = rep.get("pages") or rep.get("results") or rep.get("cells") or []
            if isinstance(rows, dict):
                rows = list(rows.values())
            byp = {c.get("page"): c for c in rows if isinstance(c, dict)}
            total += convert(V, fam, gid, [repname], batch1_lookup(byp, keys, pred), a.apply)
    print(f"\n  {GREEN}{total} row(s) converted{RST}"
          + ("" if a.apply else f"   {YEL}dry run — pass --apply to write{RST}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
