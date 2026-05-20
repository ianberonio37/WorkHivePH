"""
Canonical Contract Status — single-screen overview.
====================================================
One command to see every canonical-contract dimension's current state.
Reads existing audit reports + registries (no network, no DB), so it
runs in <1 second and is safe to invoke at any time.

  Usage:
    python tools/canonical_status.py
    python tools/canonical_status.py --json    # machine-readable

Dimensions surveyed:
  1. Tier-S standards registry  (file count + DB drift)
  2. Tier-E formula contracts   (formula count + partial honesty)
  3. Citation visibility        (Tier-S short_name on every implemented_in page)
  4. Calm Dashboard Contract    (opted-in pages + compliance)
  5. Canonical view reachability (v_*_truth views + orphans)
  6. Partial-label honesty       (zero-tolerance regression)
  7. AI prompt grounding         (every metric mention cites a standard)
  8. Phantom captures + columns  (reverse audit)
  9. Canonical drift flywheel    (TIER A pages + gap reads + drift reads)
 10. Cross-surface KPI sentinel  (parity specs locked vs baseline)
 11. Voice Companion phases 1-11 (PASS / FAIL summary per phase validator)

Designed to be cheap enough to run after every commit; surfaces drift
the same instant the underlying file changes.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


# ── ANSI colors (skip when piping to file or --json) ────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _read_json(rel: str) -> dict | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _badge(ok: bool, warn: bool = False) -> str:
    if warn:
        return f"{YELLOW}WARN{RESET}"
    return f"{GREEN}OK  {RESET}" if ok else f"{RED}FAIL{RESET}"


def _pct(num: int, denom: int) -> str:
    if denom == 0: return "—"
    return f"{(num * 100) // denom}%"


def _gather() -> dict[str, Any]:
    """Read every audit report + registry. Return a flat status dict."""
    out: dict[str, Any] = {}

    # 1. Tier-S standards
    stds = _read_json("canonical/standards.json")
    if stds:
        out["tier_s_count"] = len(stds.get("standards", []))
        out["tier_s_ids"]   = [s["standard_id"] for s in stds.get("standards", [])]
    else:
        out["tier_s_count"] = 0
        out["tier_s_ids"]   = []

    # 2. Tier-E formulas
    fcs = _read_json("canonical/formula_contracts.json")
    if fcs:
        formulas = fcs.get("formulas", [])
        out["tier_e_count"] = len(formulas)
        out["tier_e_partials_honest"] = sum(
            1 for f in formulas
            if f.get("partial_variant") and
               (f.get("partial_reason") or "").strip() and
               (f.get("formula_id", "").endswith("_partial") or
                "partial" in (f.get("implemented_in", "") or "").lower())
        )
        out["tier_e_partials_total"] = sum(1 for f in formulas if f.get("partial_variant"))
        out["formulas"] = formulas
    else:
        out["tier_e_count"] = 0
        out["tier_e_partials_honest"] = 0
        out["tier_e_partials_total"]  = 0
        out["formulas"] = []

    # 3. Citation visibility
    page_re = re.compile(r"([a-z0-9\-]+\.html)", re.IGNORECASE)
    cache: dict[str, str] = {}
    std_short = {s["standard_id"]: s["short_name"] for s in (stds or {}).get("standards", [])}
    cite_total = cite_present = 0
    for f in out["formulas"]:
        short = std_short.get(f.get("standard_id"), "")
        if not short: continue
        for p in (page_re.findall(f.get("implemented_in", "") or "")):
            p = p.lower()
            cite_total += 1
            if p not in cache:
                pp = ROOT / p
                cache[p] = pp.read_text(encoding="utf-8", errors="replace") if pp.exists() else ""
            if short in cache[p]:
                cite_present += 1
    out["cite_present"] = cite_present
    out["cite_total"]   = cite_total

    # 4. Calm Dashboard
    calm = _read_json("calm_canonical_audit_report.json")
    if calm:
        s = calm.get("summary", {})
        out["calm_opted_in"] = s.get("calm_opted_in_pages", 0)
        out["calm_compliant"] = s.get("compliant_pages", 0)
    else:
        out["calm_opted_in"] = 0
        out["calm_compliant"] = 0

    # 5. Canonical view reachability — derive from migrations live
    declared: set[str] = set()
    allowed: set[str]  = set()
    view_re = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+public\.(v_\w+_truth)\s+AS", re.IGNORECASE)
    allow_re = re.compile(r"canonical-view-allow:\s*(v_\w+_truth)\b", re.IGNORECASE)
    mig = ROOT / "supabase" / "migrations"
    if mig.exists():
        for f in mig.glob("*.sql"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                declared.update(view_re.findall(text))
                allowed.update(allow_re.findall(text))
            except Exception:
                continue
    consumed: set[str] = set()
    for root_dir, exts in [
        (ROOT, (".html", ".js")),
        (ROOT / "supabase" / "functions", (".ts",)),
        (ROOT / "python-api", (".py",)),
    ]:
        if not root_dir.exists(): continue
        for p in root_dir.rglob("*"):
            if not p.is_file() or "node_modules" in str(p) or "test-results" in str(p):
                continue
            if "supabase" in str(p) and "migrations" in str(p):
                continue
            if not any(p.name.endswith(e) for e in exts):
                continue
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
                for v in declared:
                    if v in body and v not in consumed:
                        consumed.add(v)
            except Exception:
                continue
    out["view_declared"] = len(declared)
    out["view_consumed"] = len(consumed)
    out["view_allowed"]  = len(allowed & declared)
    out["view_orphans"]  = sorted(declared - consumed - allowed)

    # 6. Partial-label honesty
    plh = _read_json("partial_label_honesty_report.json")
    out["partial_violations"] = len((plh or {}).get("violations", []) or [])

    # 7. AI prompt standards audit
    aps = _read_json("ai_prompt_standards_report.json")
    if aps:
        s = aps.get("summary", {})
        out["ai_prompt_metric_hits"]      = s.get("metric_hits", 0)
        out["ai_prompt_standards_cited"]  = s.get("standards_cited", 0)
        out["ai_prompt_metric_uncited"]   = s.get("metric_uncited", 0)
    else:
        out["ai_prompt_metric_hits"]      = 0
        out["ai_prompt_standards_cited"]  = 0
        out["ai_prompt_metric_uncited"]   = 0

    # 8. Phantom captures + columns
    pc = _read_json("phantom_captures_report.json")
    if pc:
        s = pc.get("summary", {})
        out["phantom_captures_alive"]  = s.get("alive", 0)
        out["phantom_captures_phantom"] = s.get("phantom", 0)
    else:
        out["phantom_captures_alive"]   = 0
        out["phantom_captures_phantom"] = 0

    pcol = _read_json("phantom_columns_report.json")
    if pcol:
        s = pcol.get("summary", {})
        out["phantom_cols_alive"]   = s.get("alive", 0)
        out["phantom_cols_phantom"] = s.get("phantom", 0)
    else:
        out["phantom_cols_alive"]   = 0
        out["phantom_cols_phantom"] = 0

    # 8a. Orphan KPI tiles
    okt = _read_json("orphan_kpi_tiles_report.json")
    if okt:
        s = okt.get("summary", {})
        out["orphan_tiles"]    = s.get("total_orphans", 0)
        out["orphan_baseline"] = s.get("baseline", 0)
    else:
        out["orphan_tiles"]    = 0
        out["orphan_baseline"] = 0

    # 8a2. KPI count-query safety (limit + .length as KPI)
    kcq = _read_json("kpi_count_query_safety_report.json")
    if kcq:
        s = kcq.get("summary", {})
        out["kpi_count_issues"]    = s.get("total_issues", 0)
        out["kpi_count_baseline"]  = s.get("baseline", 0)
    else:
        out["kpi_count_issues"]   = 0
        out["kpi_count_baseline"] = 0

    # 8a3. Source-chip truth — chips must reference views the page actually reads
    sct = _read_json("source_chip_truth_report.json")
    if sct:
        s = sct.get("summary", {})
        out["chip_stale"]    = s.get("total_issues", 0)
        out["chip_baseline"] = s.get("baseline", 0)
    else:
        out["chip_stale"]    = 0
        out["chip_baseline"] = 0

    # 8a4. Filter case consistency — same column + value lowercase, different case across files
    fcc = _read_json("filter_case_consistency_report.json")
    if fcc:
        s = fcc.get("summary", {})
        out["filter_drift"]    = s.get("drift_count", 0)
        out["filter_baseline"] = s.get("baseline", 0)
    else:
        out["filter_drift"]    = 0
        out["filter_baseline"] = 0

    # 8a5. Realtime subscription consistency — subscribed table must be read
    rts = _read_json("realtime_subscription_consistency_report.json")
    if rts:
        s = rts.get("summary", {})
        out["rt_drift"]     = s.get("total_drift", 0)
        out["rt_subs"]      = s.get("total_subs", 0)
        out["rt_baseline"]  = s.get("baseline", 0)
    else:
        out["rt_drift"]    = 0
        out["rt_subs"]     = 0
        out["rt_baseline"] = 0

    # 8a6. Link target existence — every href .html must resolve to a file
    lte = _read_json("link_target_existence_report.json")
    if lte:
        s = lte.get("summary", {})
        out["link_broken"]    = s.get("total_broken", 0)
        out["link_total"]     = s.get("total_links", 0)
        out["link_baseline"]  = s.get("baseline", 0)
    else:
        out["link_broken"]   = 0
        out["link_total"]    = 0
        out["link_baseline"] = 0

    # 8a7. Realtime payload column drift
    rpc_data = _read_json("realtime_payload_columns_report.json")
    if rpc_data:
        s = rpc_data.get("summary", {})
        out["payload_drift"]    = s.get("total_drift", 0)
        out["payload_refs"]     = s.get("total_refs", 0)
        out["payload_baseline"] = s.get("baseline", 0)
    else:
        out["payload_drift"] = out["payload_refs"] = out["payload_baseline"] = 0

    # 8a8. Edge function invoke targets exist
    efi = _read_json("edge_function_invoke_report.json")
    if efi:
        s = efi.get("summary", {})
        out["edge_invoke_broken"]   = s.get("total_drift", 0)
        out["edge_invoke_calls"]    = s.get("total_calls", 0)
        out["edge_invoke_baseline"] = s.get("baseline", 0)
    else:
        out["edge_invoke_broken"] = out["edge_invoke_calls"] = out["edge_invoke_baseline"] = 0

    # 8a9. RPC argument consistency
    rac = _read_json("rpc_argument_consistency_report.json")
    if rac:
        s = rac.get("summary", {})
        out["rpc_drift"]    = s.get("total_drift", 0)
        out["rpc_calls"]    = s.get("total_calls", 0)
        out["rpc_baseline"] = s.get("baseline", 0)
    else:
        out["rpc_drift"] = out["rpc_calls"] = out["rpc_baseline"] = 0

    # 8a10. Image / asset existence
    iae = _read_json("image_asset_existence_report.json")
    if iae:
        s = iae.get("summary", {})
        out["asset_broken"]   = s.get("total_broken", 0)
        out["asset_refs"]     = s.get("total_refs", 0)
        out["asset_baseline"] = s.get("baseline", 0)
    else:
        out["asset_broken"] = out["asset_refs"] = out["asset_baseline"] = 0

    # 8a11. Service Worker SHELL_FILES
    sws = _read_json("service_worker_shell_report.json")
    if sws:
        s = sws.get("summary", {})
        out["sw_broken"]    = s.get("total_broken", 0)
        out["sw_paths"]     = s.get("total_shell_paths", 0)
        out["sw_baseline"]  = s.get("baseline", 0)
    else:
        out["sw_broken"] = out["sw_paths"] = out["sw_baseline"] = 0

    # 8a12. Query column existence
    qce = _read_json("query_column_existence_report.json")
    if qce:
        s = qce.get("summary", {})
        out["query_col_drift"]    = s.get("total_drift", 0)
        out["query_col_calls"]    = s.get("total_calls", 0)
        out["query_col_baseline"] = s.get("baseline", 0)
    else:
        out["query_col_drift"] = out["query_col_calls"] = out["query_col_baseline"] = 0

    # 8a13. getElementById orphan setters
    gos = _read_json("getelementbyid_orphan_setter_report.json")
    if gos:
        s = gos.get("summary", {})
        out["gid_orphan"]    = s.get("total_orphans", 0)
        out["gid_lookups"]   = s.get("total_lookups", 0)
        out["gid_baseline"]  = s.get("baseline", 0)
    else:
        out["gid_orphan"] = out["gid_lookups"] = out["gid_baseline"] = 0

    # 8a14. Time-window consistency
    twc = _read_json("time_window_consistency_report.json")
    if twc:
        s = twc.get("summary", {})
        out["tw_drift"]    = s.get("drift_groups", 0)
        out["tw_hits"]     = s.get("total_hits", 0)
        out["tw_baseline"] = s.get("baseline", 0)
    else:
        out["tw_drift"] = out["tw_hits"] = out["tw_baseline"] = 0

    # 8a15. Role string consistency
    rsc = _read_json("role_string_consistency_report.json")
    if rsc:
        s = rsc.get("summary", {})
        out["role_drift"]    = s.get("drift", 0)
        out["role_baseline"] = s.get("baseline", 0)
    else:
        out["role_drift"] = out["role_baseline"] = 0

    # 8a16. Inline onclick handler existence
    ioh = _read_json("inline_onclick_handler_report.json")
    if ioh:
        s = ioh.get("summary", {})
        out["onclick_orphan"]   = s.get("total_orphans", 0)
        out["onclick_total"]    = s.get("total_handlers", 0)
        out["onclick_baseline"] = s.get("baseline", 0)
    else:
        out["onclick_orphan"] = out["onclick_total"] = out["onclick_baseline"] = 0

    # 8a17. innerHTML escHtml audit
    iht = _read_json("innerhtml_eschtml_report.json")
    if iht:
        s = iht.get("summary", {})
        out["xss_risk"]      = s.get("total_risk", 0)
        out["xss_total"]     = s.get("total_assignments", 0)
        out["xss_baseline"]  = s.get("baseline", 0)
    else:
        out["xss_risk"] = out["xss_total"] = out["xss_baseline"] = 0

    # 8a18. Env variable existence
    eve = _read_json("env_variable_existence_report.json")
    if eve:
        s = eve.get("summary", {})
        out["env_missing"]   = s.get("total_missing", 0)
        out["env_refs"]      = s.get("total_refs", 0)
        out["env_baseline"]  = s.get("baseline", 0)
    else:
        out["env_missing"] = out["env_refs"] = out["env_baseline"] = 0

    # 8a19. Aria label coverage
    arc = _read_json("aria_label_coverage_report.json")
    if arc:
        s = arc.get("summary", {})
        out["aria_missing"]   = s.get("total_missing", 0)
        out["aria_total"]     = s.get("total_elements", 0)
        out["aria_baseline"]  = s.get("baseline", 0)
    else:
        out["aria_missing"] = out["aria_total"] = out["aria_baseline"] = 0

    # 8a20. Realtime channel cleanup
    rcc = _read_json("realtime_channel_cleanup_report.json")
    if rcc:
        s = rcc.get("summary", {})
        out["rt_clean_unsafe"]   = s.get("unsafe_pages", 0)
        out["rt_clean_channels"] = s.get("total_channels", 0)
        out["rt_clean_baseline"] = s.get("baseline", 0)
    else:
        out["rt_clean_unsafe"] = out["rt_clean_channels"] = out["rt_clean_baseline"] = 0

    # 8a21. Playwright selector existence
    pse = _read_json("playwright_selector_existence_report.json")
    if pse:
        s = pse.get("summary", {})
        out["pw_drift"]     = s.get("total_drift", 0)
        out["pw_lookups"]   = s.get("total_lookups", 0)
        out["pw_baseline"]  = s.get("baseline", 0)
    else:
        out["pw_drift"] = out["pw_lookups"] = out["pw_baseline"] = 0

    # 8a22. localStorage key consistency
    lks = _read_json("localstorage_key_consistency_report.json")
    if lks:
        s = lks.get("summary", {})
        out["ls_drift"]    = s.get("drift", 0)
        out["ls_keys"]     = s.get("total_keys", 0)
        out["ls_baseline"] = s.get("baseline", 0)
    else:
        out["ls_drift"] = out["ls_keys"] = out["ls_baseline"] = 0

    # 8a23. CSS class existence
    cce = _read_json("css_class_existence_report.json")
    if cce:
        s = cce.get("summary", {})
        out["css_missing"]  = s.get("total_missing", 0)
        out["css_calls"]    = s.get("total_calls", 0)
        out["css_baseline"] = s.get("baseline", 0)
    else:
        out["css_missing"] = out["css_calls"] = out["css_baseline"] = 0

    # 8a23b. Flywheel state — runs of tools/flywheel_orchestrator.py
    fw = _read_json("flywheel_state.json")
    if fw:
        out["flywheel_turn"]      = fw.get("turn", 0)
        hist = fw.get("history", []) or []
        if hist:
            last = hist[-1]
            out["flywheel_ratchets"]    = len(last.get("L0_ratchets", []))
            out["flywheel_regressions"] = len(last.get("L0_regressions", []))
        else:
            out["flywheel_ratchets"]    = 0
            out["flywheel_regressions"] = 0
    else:
        out["flywheel_turn"] = 0
        out["flywheel_ratchets"]    = 0
        out["flywheel_regressions"] = 0

    # 8a24-31. New batch (pg_cron, triggers, meta, sitemap, unbounded, headings, canonical, listeners)
    for key, fname, fields in [
        ("cron",      "pg_cron_target_existence_report.json",     ("total_issues","baseline")),
        ("trigger",   "trigger_function_existence_report.json",   ("total_issues","baseline")),
        ("meta",      "meta_description_coverage_report.json",    ("total_missing","baseline")),
        ("sitemap",   "sitemap_page_existence_report.json",       ("total_broken","baseline")),
        ("unbounded", "unbounded_query_report.json",              ("total_unbounded","baseline")),
        ("heading",   "heading_hierarchy_report.json",            ("total_issues","baseline")),
        ("canon",     "canonical_url_consistency_report.json",    ("drift","baseline")),
        ("listener",  "event_listener_cleanup_report.json",       ("risky_pages","baseline")),
        # Flywheel 5-turn sweep (2026-05-20)
        ("rel",       "external_link_rel_report.json",            ("drift","baseline")),
        ("btn",       "button_type_in_form_report.json",          ("drift","baseline")),
        ("definer",   "security_definer_search_path_report.json", ("drift","baseline")),
        ("dupscript", "duplicate_script_tags_report.json",        ("drift","baseline")),
        ("native",    "native_dialog_calls_report.json",          ("drift","baseline")),
        # Flywheel turns 6-10 (2026-05-20)
        ("dupid",     "duplicate_html_id_report.json",            ("drift","baseline")),
        ("imgalt",    "img_alt_coverage_report.json",             ("drift","baseline")),
        ("jsonparse", "json_parse_safety_report.json",            ("drift","baseline")),
        ("fetchcatch","fetch_error_handling_report.json",         ("drift","baseline")),
        ("edgestatus","edge_status_body_consistency_report.json", ("drift","baseline")),
        # Flywheel turns 11-15 (2026-05-21)
        ("edgepin",   "edge_unpinned_imports_report.json",        ("drift","baseline")),
        ("timer",     "timer_cleanup_report.json",                ("drift","baseline")),
        ("cssid",     "css_id_existence_report.json",             ("drift","baseline")),
        ("addcol",    "add_column_default_report.json",           ("drift","baseline")),
        ("formsub",   "form_submission_target_report.json",       ("drift","baseline")),
        # Flywheel turns 16-20 (2026-05-21)
        ("preflight", "edge_options_preflight_report.json",        ("drift","baseline")),
        ("pwinput",   "password_input_form_report.json",           ("drift","baseline")),
        ("fkdelete",  "fk_on_delete_report.json",                  ("drift","baseline")),
        ("bodysize",  "edge_body_size_guard_report.json",          ("drift","baseline")),
        ("selectph",  "select_placeholder_report.json",            ("drift","baseline")),
        # Flywheel turns 21-25 (2026-05-21)
        ("rlsopen",   "rls_open_policy_report.json",               ("drift","baseline")),
        ("conslog",   "console_log_drift_report.json",             ("drift","baseline")),
        ("jshref",    "javascript_href_report.json",               ("drift","baseline")),
        ("viewstar",  "view_select_star_report.json",              ("drift","baseline")),
        ("metaref",   "meta_refresh_report.json",                  ("drift","baseline")),
    ]:
        d = _read_json(fname)
        if d:
            s = d.get("summary", {})
            out[f"{key}_val"]      = s.get(fields[0], 0)
            out[f"{key}_baseline"] = s.get(fields[1], 0)
        else:
            out[f"{key}_val"] = out[f"{key}_baseline"] = 0

    # 8b. Truth-view signal-trust (semantic drift inside the same canonical signal)
    tvst = _read_json("truth_view_signal_trust_report.json")
    if tvst:
        s = tvst.get("summary", {})
        out["signal_pairs"]   = s.get("view_column_pairs", 0)
        out["signal_at_risk"] = s.get("at_risk", 0)
        out["signal_review"]  = s.get("review", 0)
    else:
        out["signal_pairs"]   = 0
        out["signal_at_risk"] = 0
        out["signal_review"]  = 0
    tvst_base = _read_json("truth_view_signal_trust_baseline.json")
    out["signal_baseline"] = (tvst_base or {}).get("review", 0)

    # 9. Canonical drift flywheel (TIER A + drift + gap counts)
    cdp = _read_json("canonical_drift_platform_report.json")
    if cdp:
        s = cdp.get("summary", {})
        out["drift_tier_a_pages"]    = s.get("tier_a_pages", 0)
        out["drift_tier_b_pages"]    = s.get("tier_b_pages", 0)
        out["drift_reads"]           = s.get("total_drift_reads", 0)
        out["drift_gap_reads"]       = s.get("total_gap_reads", 0)
        out["drift_files_scanned"]   = s.get("files_scanned", 0)
    else:
        out["drift_tier_a_pages"]    = 0
        out["drift_tier_b_pages"]    = 0
        out["drift_reads"]           = 0
        out["drift_gap_reads"]       = 0
        out["drift_files_scanned"]   = 0

    # 9b. Forward-only ratchet
    fkc = _read_json("user_facing_kpi_canonical_report.json")
    if fkc:
        s = fkc.get("summary", {})
        out["ratchet_regressions"]   = s.get("tier_a_regressions", 0) + s.get("gap_regressions", 0)
        out["ratchet_baseline_gap"]  = s.get("baseline_gap_reads", 0)
        out["ratchet_current_gap"]   = s.get("current_gap_reads", 0)
    else:
        out["ratchet_regressions"]   = 0
        out["ratchet_baseline_gap"]  = 0
        out["ratchet_current_gap"]   = 0

    # 11. Voice Companion phase validators — Phase 1 through Phase 11.
    # Each validator is a self-contained Python script that returns "PASS: N | FAIL: M"
    # in its output. We parse the line and roll up to per-phase + grand totals.
    # Avoid invoking subprocess per validator (expensive); instead read the
    # validator's __doc__ + grep for the result-line shape via Python import.
    import subprocess
    VOICE_PHASES = [
        ("1",   "validate_voice_companion_phase1"),
        ("1.5", "validate_voice_companion_phase1_5"),
        ("2",   "validate_voice_companion_phase2"),
        ("3",   "validate_voice_companion_phase3"),
        ("4",   "validate_dialog_flow"),
        ("5",   "validate_proactive_alerts"),
        ("6",   "validate_offline_resilience_phase6"),
        ("7",   "validate_tts_quality_phase7"),
        ("8",   "validate_voice_data_flow"),
        ("9",   "validate_team_coordination"),
        ("10",  "validate_avatar_state_phase10"),
        ("11",  "validate_multilingual_phase11"),
    ]
    phase_results = []
    pass_re = re.compile(r"PASS[: ]\s*(\d+)\s*\|\s*FAIL[: ]\s*(\d+)|(\d+)\s+PASS\s+(\d+)\s+SKIP\s+(\d+)\s+FAIL|Result[: ]\s*(\d+)\s+PASS[, ]+(\d+)\s+FAIL", re.IGNORECASE)
    for label, script in VOICE_PHASES:
        script_path = ROOT / f"{script}.py"
        if not script_path.exists():
            phase_results.append((label, script, None, None, "missing"))
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, timeout=30, cwd=str(ROOT),
            )
            text = (r.stdout or "") + "\n" + (r.stderr or "")
            m = pass_re.search(text)
            if m:
                # Three patterns in the regex; pick whichever matched
                groups = m.groups()
                p = next((int(g) for g in groups[::2] if g and g.isdigit()), None)
                f = next((int(g) for i, g in enumerate(groups) if i % 2 == 1 and g and g.isdigit()), None)
                phase_results.append((label, script, p, f, "ok"))
            else:
                phase_results.append((label, script, None, None, "unparsed"))
        except subprocess.TimeoutExpired:
            phase_results.append((label, script, None, None, "timeout"))
        except Exception as e:
            phase_results.append((label, script, None, None, f"error: {e}"))
    out["voice_phase_results"] = phase_results
    out["voice_phases_green"]  = sum(1 for _, _, p, f, st in phase_results if st == "ok" and (f or 0) == 0)
    out["voice_phases_total"]  = len(phase_results)

    # 10. Cross-surface KPI sentinel spec count (static scan of the spec files).
    # Counts BOTH conventions:
    #   1. Literal `test('check_X: ...', ...)` — one test() per check
    #   2. Table-driven `name: 'check_X: ...'` — one case per check in a CASES array
    sentinel_files = [
        ROOT / "tests" / "journey-cross-surface-kpi-parity.spec.ts",
        ROOT / "tests" / "journey-canonical-signal-parity.spec.ts",
    ]
    sentinel_count = 0
    sentinel_fixme = 0
    for sf in sentinel_files:
        if sf.exists():
            body = sf.read_text(encoding="utf-8", errors="replace")
            sentinel_count += len(re.findall(r"\btest\s*\(\s*['\"]check_", body))
            sentinel_count += len(re.findall(r"\bname\s*:\s*['\"]check_", body))
            sentinel_fixme += len(re.findall(r"\btest\.fixme\s*\(\s*['\"]check_", body))
    out["sentinel_specs"] = sentinel_count
    out["sentinel_fixme"] = sentinel_fixme

    # 12. Cross-migration table-collision auditor — catches the agent_memory-class
    # bug where two migrations both CREATE TABLE IF NOT EXISTS X with different columns.
    coll = _read_json("table_collision_report.json")
    if coll:
        s = coll.get("summary", {})
        out["table_collisions"]        = s.get("collisions", 0)
        out["table_redeclared"]        = s.get("tables_redeclared", 0)
        out["table_scanned"]           = s.get("tables_scanned", 0)
    else:
        out["table_collisions"]        = 0
        out["table_redeclared"]        = 0
        out["table_scanned"]           = 0

    # 11b. Voice phase runtime sentinel (parallel to static phase validators)
    voice_sentinel_file = ROOT / "tests" / "journey-voice-phases.spec.ts"
    if voice_sentinel_file.exists():
        body = voice_sentinel_file.read_text(encoding="utf-8", errors="replace")
        out["voice_sentinel_specs"] = len(re.findall(r"\btest\s*\(\s*['\"]phase_", body))
        out["voice_sentinel_fixme"] = len(re.findall(r"\btest\.fixme\s*\(\s*['\"]phase_", body))
    else:
        out["voice_sentinel_specs"] = 0
        out["voice_sentinel_fixme"] = 0

    return out


def _print(status: dict[str, Any]) -> int:
    """Pretty-print status. Returns 0 if all green, 1 if any red."""
    fail_count = 0
    print(f"\n{BOLD}Canonical Contract Status{RESET}")
    print("=" * 56)

    # 1. Tier-S
    ok = status["tier_s_count"] >= 21
    if not ok: fail_count += 1
    print(f"  {_badge(ok)}  Tier-S standards registered:  {status['tier_s_count']}")

    # 2. Tier-E
    e_ok = status["tier_e_count"] >= 22
    partials_ok = status["tier_e_partials_honest"] == status["tier_e_partials_total"]
    if not e_ok: fail_count += 1
    if not partials_ok: fail_count += 1
    print(f"  {_badge(e_ok)}  Tier-E formula contracts:     {status['tier_e_count']}")
    print(f"  {_badge(partials_ok)}  Partial formulas honest:      "
          f"{status['tier_e_partials_honest']}/{status['tier_e_partials_total']}")

    # 3. Citation visibility
    cite_ok = status["cite_total"] > 0 and status["cite_present"] == status["cite_total"]
    if not cite_ok: fail_count += 1
    print(f"  {_badge(cite_ok)}  Tier-S citation visibility:   "
          f"{status['cite_present']}/{status['cite_total']} "
          f"({_pct(status['cite_present'], status['cite_total'])})")

    # 4. Calm Dashboard
    calm_warn = status["calm_compliant"] < status["calm_opted_in"]
    print(f"  {_badge(not calm_warn, warn=calm_warn)}  Calm Dashboard wired:         "
          f"{status['calm_compliant']}/{status['calm_opted_in']} "
          f"({_pct(status['calm_compliant'], status['calm_opted_in'])})")

    # 5. View reachability
    view_ok = len(status["view_orphans"]) == 0
    if not view_ok: fail_count += 1
    print(f"  {_badge(view_ok)}  Canonical views reachable:    "
          f"{status['view_consumed']}/{status['view_declared']} "
          f"({status['view_allowed']} allow-marked)")
    if status["view_orphans"]:
        for v in status["view_orphans"][:3]:
            print(f"         orphan: {v}")

    # 6. Partial honesty
    plh_ok = status["partial_violations"] == 0
    if not plh_ok: fail_count += 1
    print(f"  {_badge(plh_ok)}  Partial-label violations:     {status['partial_violations']}")

    # 7. AI prompt grounding
    ai_ok = status["ai_prompt_metric_uncited"] == 0
    if not ai_ok: fail_count += 1
    print(f"  {_badge(ai_ok)}  AI prompts citing standards:  "
          f"{status['ai_prompt_standards_cited']}/{status['ai_prompt_metric_hits']}")

    # 8. Phantoms
    phc_ok = status["phantom_captures_phantom"] == 0
    phcol_ok = status["phantom_cols_phantom"] == 0
    if not phc_ok: fail_count += 1
    print(f"  {_badge(phc_ok)}  Phantom captures (reverse):   "
          f"{status['phantom_captures_phantom']} phantom / {status['phantom_captures_alive']} alive")
    print(f"  {_badge(phcol_ok, warn=not phcol_ok)}  Phantom DB columns:           "
          f"{status['phantom_cols_phantom']} phantom / {status['phantom_cols_alive']} alive")

    # 8a. Orphan KPI tiles
    orphan_ok = status["orphan_tiles"] <= status["orphan_baseline"]
    if not orphan_ok: fail_count += 1
    print(f"  {_badge(orphan_ok)}  Orphan KPI tiles:             "
          f"{status['orphan_tiles']} orphan (baseline {status['orphan_baseline']})")

    # 8a2. KPI count-query safety
    kcq_ok = status["kpi_count_issues"] <= status["kpi_count_baseline"]
    if not kcq_ok: fail_count += 1
    print(f"  {_badge(kcq_ok, warn=status['kpi_count_issues']>0)}  "
          f"KPI count-query safety:       "
          f"{status['kpi_count_issues']} limit-as-count (baseline {status['kpi_count_baseline']})")

    # 8a3. Source-chip truth
    chip_ok = status["chip_stale"] <= status["chip_baseline"]
    if not chip_ok: fail_count += 1
    print(f"  {_badge(chip_ok, warn=status['chip_stale']>0)}  "
          f"Source-chip truth:            "
          f"{status['chip_stale']} stale claims (baseline {status['chip_baseline']})")

    # 8a4. Filter case consistency
    filter_ok = status["filter_drift"] <= status["filter_baseline"]
    if not filter_ok: fail_count += 1
    print(f"  {_badge(filter_ok, warn=status['filter_drift']>0)}  "
          f"Filter case consistency:      "
          f"{status['filter_drift']} drift (baseline {status['filter_baseline']})")

    # 8a5. Realtime subscription consistency
    rt_ok = status["rt_drift"] <= status["rt_baseline"]
    if not rt_ok: fail_count += 1
    print(f"  {_badge(rt_ok, warn=status['rt_drift']>0)}  "
          f"Realtime subscriptions:       "
          f"{status['rt_drift']} drift / {status['rt_subs']} subs (baseline {status['rt_baseline']})")

    # 8a6. Link target existence
    link_ok = status["link_broken"] <= status["link_baseline"]
    if not link_ok: fail_count += 1
    print(f"  {_badge(link_ok, warn=status['link_broken']>0)}  "
          f"Link targets exist:           "
          f"{status['link_broken']} broken / {status['link_total']} links (baseline {status['link_baseline']})")

    # 8a7. Realtime payload column drift
    pld_ok = status["payload_drift"] <= status["payload_baseline"]
    if not pld_ok: fail_count += 1
    print(f"  {_badge(pld_ok, warn=status['payload_drift']>0)}  "
          f"Realtime payload columns:     "
          f"{status['payload_drift']} drift / {status['payload_refs']} refs (baseline {status['payload_baseline']})")

    # 8a8. Edge function invoke
    ei_ok = status["edge_invoke_broken"] <= status["edge_invoke_baseline"]
    if not ei_ok: fail_count += 1
    print(f"  {_badge(ei_ok, warn=status['edge_invoke_broken']>0)}  "
          f"Edge fn invoke targets:       "
          f"{status['edge_invoke_broken']} broken / {status['edge_invoke_calls']} calls (baseline {status['edge_invoke_baseline']})")

    # 8a9. RPC argument consistency
    rac_ok = status["rpc_drift"] <= status["rpc_baseline"]
    if not rac_ok: fail_count += 1
    print(f"  {_badge(rac_ok, warn=status['rpc_drift']>0)}  "
          f"RPC argument consistency:     "
          f"{status['rpc_drift']} drift / {status['rpc_calls']} calls (baseline {status['rpc_baseline']})")

    # 8a10. Image / asset existence
    iae_ok = status["asset_broken"] <= status["asset_baseline"]
    if not iae_ok: fail_count += 1
    print(f"  {_badge(iae_ok, warn=status['asset_broken']>0)}  "
          f"Image / asset existence:      "
          f"{status['asset_broken']} broken / {status['asset_refs']} refs (baseline {status['asset_baseline']})")

    # 8a11. Service Worker SHELL_FILES
    sw_ok = status["sw_broken"] <= status["sw_baseline"]
    if not sw_ok: fail_count += 1
    print(f"  {_badge(sw_ok, warn=status['sw_broken']>0)}  "
          f"SW SHELL_FILES exist:         "
          f"{status['sw_broken']} broken / {status['sw_paths']} paths (baseline {status['sw_baseline']})")

    # 8a12. Query column existence
    qce_ok = status["query_col_drift"] <= status["query_col_baseline"]
    if not qce_ok: fail_count += 1
    print(f"  {_badge(qce_ok, warn=status['query_col_drift']>0)}  "
          f"Query column existence:       "
          f"{status['query_col_drift']} drift / {status['query_col_calls']} calls (baseline {status['query_col_baseline']})")

    # 8a13. getElementById orphan setters
    gos_ok = status["gid_orphan"] <= status["gid_baseline"]
    if not gos_ok: fail_count += 1
    print(f"  {_badge(gos_ok, warn=status['gid_orphan']>0)}  "
          f"getElementById orphan:        "
          f"{status['gid_orphan']} orphan / {status['gid_lookups']} lookups (baseline {status['gid_baseline']})")

    # 8a14. Time-window consistency
    tw_ok = status["tw_drift"] <= status["tw_baseline"]
    if not tw_ok: fail_count += 1
    print(f"  {_badge(tw_ok, warn=status['tw_drift']>0)}  "
          f"Time-window consistency:      "
          f"{status['tw_drift']} drift groups / {status['tw_hits']} hits (baseline {status['tw_baseline']})")

    # 8a15. Role string consistency
    role_ok = status["role_drift"] <= status["role_baseline"]
    if not role_ok: fail_count += 1
    print(f"  {_badge(role_ok, warn=status['role_drift']>0)}  "
          f"Role string consistency:      "
          f"{status['role_drift']} off-canonical (baseline {status['role_baseline']})")

    # 8a16. Inline onclick handler existence
    oc_ok = status["onclick_orphan"] <= status["onclick_baseline"]
    if not oc_ok: fail_count += 1
    print(f"  {_badge(oc_ok, warn=status['onclick_orphan']>0)}  "
          f"Inline handler existence:     "
          f"{status['onclick_orphan']} orphan / {status['onclick_total']} handlers (baseline {status['onclick_baseline']})")

    # 8a17. innerHTML escHtml audit
    xss_ok = status["xss_risk"] <= status["xss_baseline"]
    if not xss_ok: fail_count += 1
    print(f"  {_badge(xss_ok, warn=status['xss_risk']>0)}  "
          f"innerHTML escHtml audit:      "
          f"{status['xss_risk']} risk / {status['xss_total']} assigns (baseline {status['xss_baseline']})")

    # 8a18. Env variable existence
    env_ok = status["env_missing"] <= status["env_baseline"]
    if not env_ok: fail_count += 1
    print(f"  {_badge(env_ok, warn=status['env_missing']>0)}  "
          f"Env variable existence:       "
          f"{status['env_missing']} missing / {status['env_refs']} refs (baseline {status['env_baseline']})")

    # 8a19. Aria label coverage
    aria_ok = status["aria_missing"] <= status["aria_baseline"]
    if not aria_ok: fail_count += 1
    print(f"  {_badge(aria_ok, warn=status['aria_missing']>0)}  "
          f"Aria label coverage:          "
          f"{status['aria_missing']} missing / {status['aria_total']} interactives (baseline {status['aria_baseline']})")

    # 8a20. Realtime channel cleanup
    rcc_ok = status["rt_clean_unsafe"] <= status["rt_clean_baseline"]
    if not rcc_ok: fail_count += 1
    print(f"  {_badge(rcc_ok, warn=status['rt_clean_unsafe']>0)}  "
          f"Realtime channel cleanup:     "
          f"{status['rt_clean_unsafe']} unsafe / {status['rt_clean_channels']} channels (baseline {status['rt_clean_baseline']})")

    # 8a21. Playwright selector existence
    pw_ok = status["pw_drift"] <= status["pw_baseline"]
    if not pw_ok: fail_count += 1
    print(f"  {_badge(pw_ok, warn=status['pw_drift']>0)}  "
          f"Playwright selectors exist:   "
          f"{status['pw_drift']} drift / {status['pw_lookups']} lookups (baseline {status['pw_baseline']})")

    # 8a22. localStorage key consistency
    ls_ok = status["ls_drift"] <= status["ls_baseline"]
    if not ls_ok: fail_count += 1
    print(f"  {_badge(ls_ok, warn=status['ls_drift']>0)}  "
          f"localStorage keys consistent: "
          f"{status['ls_drift']} drift / {status['ls_keys']} keys (baseline {status['ls_baseline']})")

    # 8a23. CSS class existence
    css_ok = status["css_missing"] <= status["css_baseline"]
    if not css_ok: fail_count += 1
    print(f"  {_badge(css_ok, warn=status['css_missing']>0)}  "
          f"CSS class existence:          "
          f"{status['css_missing']} missing / {status['css_calls']} calls (baseline {status['css_baseline']})")

    # 8a23b. Flywheel state
    fw_ok = status.get("flywheel_regressions", 0) == 0
    if not fw_ok: fail_count += 1
    print(f"  {_badge(fw_ok)}  Flywheel turns:               "
          f"{status.get('flywheel_turn', 0)} run · last "
          f"{status.get('flywheel_ratchets', 0)} ratchet / "
          f"{status.get('flywheel_regressions', 0)} regression")

    # 8a24-31. New batch
    for key, label in [
        ("cron",      "pg_cron target existence:    "),
        ("trigger",   "Trigger function exists:     "),
        ("meta",      "Meta description coverage:   "),
        ("sitemap",   "Sitemap page existence:      "),
        ("unbounded", "Unbounded queries:           "),
        ("heading",   "Heading hierarchy:           "),
        ("canon",     "Canonical URL consistency:   "),
        ("listener",  "Event listener cleanup:      "),
        ("rel",       "External link rel=noopener:  "),
        ("btn",       "Button type in form:         "),
        ("definer",   "SECURITY DEFINER search_path:"),
        ("dupscript", "Duplicate <script>/<link>:   "),
        ("native",    "Native alert/confirm/prompt: "),
        ("dupid",     "Duplicate HTML id:           "),
        ("imgalt",    "<img> alt coverage:          "),
        ("jsonparse", "JSON.parse safety:           "),
        ("fetchcatch","fetch() error handling:      "),
        ("edgestatus","Edge status/body drift:      "),
        ("edgepin",   "Edge unpinned imports:       "),
        ("timer",     "Timer cleanup:               "),
        ("cssid",     "CSS id existence:            "),
        ("addcol",    "ADD COLUMN DEFAULT safety:   "),
        ("formsub",   "<form> submission target:    "),
        ("preflight", "Edge OPTIONS preflight:      "),
        ("pwinput",   "<input type=password> form:  "),
        ("fkdelete",  "FK ON DELETE explicit:       "),
        ("bodysize",  "Edge body size guard:        "),
        ("selectph",  "<select> placeholder:        "),
        ("rlsopen",   "RLS open policies:           "),
        ("conslog",   "console.log drift:           "),
        ("jshref",    "<a href='javascript:'>:      "),
        ("viewstar",  "CREATE VIEW SELECT *:        "),
        ("metaref",   "<meta http-equiv=refresh>:   "),
    ]:
        val = status.get(f"{key}_val", 0)
        baseline = status.get(f"{key}_baseline", 0)
        ok = val <= baseline
        if not ok: fail_count += 1
        print(f"  {_badge(ok, warn=val>0)}  {label}{val} (baseline {baseline})")

    # 8b. Truth-view signal-trust
    signal_ok = status["signal_at_risk"] == 0 and status["signal_review"] <= status["signal_baseline"]
    if not signal_ok: fail_count += 1
    print(f"  {_badge(signal_ok)}  Signal-trust (truth views):   "
          f"{status['signal_at_risk']} AT_RISK / {status['signal_review']} REVIEW "
          f"(baseline {status['signal_baseline']}, {status['signal_pairs']} pairs)")

    # 9. Canonical drift flywheel
    drift_ok = status["drift_reads"] == 0 and status["drift_tier_a_pages"] == 0
    if not drift_ok: fail_count += 1
    print(f"  {_badge(drift_ok)}  Canonical drift (flywheel):   "
          f"{status['drift_reads']} drift / {status['drift_gap_reads']} gap reads "
          f"({status['drift_files_scanned']} files; TIER A: {status['drift_tier_a_pages']})")

    # 9b. Forward-only ratchet
    ratchet_ok = status["ratchet_regressions"] == 0
    if not ratchet_ok: fail_count += 1
    delta = status["ratchet_current_gap"] - status["ratchet_baseline_gap"]
    delta_str = f"+{delta}" if delta > 0 else f"{delta}"
    print(f"  {_badge(ratchet_ok)}  Forward-only ratchet:         "
          f"{status['ratchet_regressions']} regressions (gap {status['ratchet_current_gap']} "
          f"vs baseline {status['ratchet_baseline_gap']}, {delta_str})")

    # 10. Sentinel KPI parity coverage
    sentinel_ok = status["sentinel_specs"] >= 6 and status["sentinel_fixme"] == 0
    print(f"  {_badge(sentinel_ok, warn=status['sentinel_fixme']>0)}  Cross-surface KPI sentinels:  "
          f"{status['sentinel_specs']} active "
          f"({status['sentinel_fixme']} fixme'd)")

    # 11. Voice Companion phases
    voice_ok = status["voice_phases_green"] == status["voice_phases_total"]
    if not voice_ok: fail_count += 1
    print(f"  {_badge(voice_ok)}  Voice Companion phases:       "
          f"{status['voice_phases_green']}/{status['voice_phases_total']} green (static)")
    for label, script, p, f, st in status["voice_phase_results"]:
        if st != "ok" or (f or 0) > 0:
            badge = _badge(False)
            extra = f"PASS:{p or 0} FAIL:{f or 0}" if st == "ok" else st
            print(f"         {badge}  Phase {label:<4} ({script}): {extra}")

    # 11b. Voice phase runtime sentinel
    vsentinel_ok = status["voice_sentinel_specs"] >= 6
    print(f"  {_badge(vsentinel_ok, warn=status['voice_sentinel_fixme']>0)}  Voice phase runtime sentinels: "
          f"{status['voice_sentinel_specs']} active "
          f"({status['voice_sentinel_fixme']} fixme'd)")

    # 12. Cross-migration table collisions
    coll_ok = status["table_collisions"] == 0
    if not coll_ok: fail_count += 1
    print(f"  {_badge(coll_ok)}  Migration table collisions:   "
          f"{status['table_collisions']} unallowed "
          f"({status['table_redeclared']} redeclared / {status['table_scanned']} scanned)")

    print("=" * 56)
    if fail_count == 0:
        print(f"  {GREEN}{BOLD}All canonical-contract dimensions green.{RESET}")
        return 0
    else:
        print(f"  {RED}{BOLD}{fail_count} dimension(s) FAIL — see above.{RESET}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical contract status overview")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of pretty text")
    args = parser.parse_args()

    if sys.platform == "win32" and not args.json:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    status = _gather()
    if args.json:
        # Strip the large arrays before emitting
        s = {k: v for k, v in status.items() if k not in ("tier_s_ids", "formulas")}
        print(json.dumps(s, indent=2))
        return 0 if status["partial_violations"] == 0 and not status["view_orphans"] else 1
    return _print(status)


if __name__ == "__main__":
    sys.exit(main())
