# audit-scope-allow: Calm-opted-in pages declare their opt-in via a root-level <meta name="calm-dashboard"> tag; only root HTML pages opt in. Subdirectory HTML is intentionally out of scope.
"""
Calm Dashboard Canonical-Wiring Auditor (Layer -1.5).
======================================================

Classifies every `.from('table')` read on a Calm-opted-in HTML page into
one of four buckets:

  CANONICAL  — the read targets a `v_*_truth` view (good)
  DRIFT      — the read targets a raw table that HAS a canonical wrapper
               (validate_canonical_sources.py also flags this; we cross-list
               here so the dashboard audit has a single self-contained view)
  GAP        — the read targets a raw table that has NO wrapper yet. This is
               the class today's validators miss entirely. These tables are
               the next-build queue for v_*_truth views.
  ALLOWED    — table is on the LEGITIMATE_RAW allowlist (write-only forms,
               audit logs, etc.) — these don't need a wrapper.

Reads canonical_registry.json (the file-based inventory) and
skill_rules_manifest.json (for the calm-dashboard opt-in convention).

Output:
  - calm_canonical_audit_report.json (machine-readable)
  - calm_canonical_audit_report.md   (human-readable, per-page tables)

Designed to slot into the existing platform mega-gate:
  Layer -1.5 (this auditor) ->  Hardening Loop (proposes fixes)
   ->  Sentinel (locks behavior) ->  Layer 2 Playwright (tests)
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

# Canonical wrapper map — table_name -> v_*_truth view that should be used
# instead. Hand-curated from CANONICAL_SOURCES_AUDIT.md plus v_*_truth
# discovery from canonical_registry.json. Edit here when a new wrapper
# ships.
WRAPPERS = {
    "logbook":              "v_logbook_truth",
    "asset_nodes":          "v_asset_truth",
    "assets":               "v_asset_truth",
    "asset_risk_scores":    "v_risk_truth",
    "pm_assets":            "v_pm_compliance_truth",
    "pm_completions":       "v_pm_compliance_truth",  # partial — compliance roll-up only
    "pm_scope_items":       "v_pm_scope_items_truth",
    "inventory_items":      "v_inventory_items_truth",
    "marketplace_sellers":  "v_marketplace_sellers_truth",
    "projects":             "v_project_truth",
    "hive_readiness":       "v_hive_readiness_truth",
    "worker_profiles":      "v_worker_truth",   # composite per audit §C5
    "hive_members":         "v_worker_truth",
    # 2026-05-20 wrappers shipped to close gap reads:
    "failure_signature_alerts": "v_alert_truth",
    "anomaly_signals":          "v_alert_truth",
    "amc_briefings":            "v_amc_truth",
    "sensor_readings":          "v_sensor_truth",
}

# Tables that are legitimately raw — they don't need a v_*_truth wrapper
# because they're either write-only forms, system-internal audit logs,
# or single-purpose tables consumed by exactly one surface.
# Pages that are the CANONICAL OWNER of raw-table CRUD. When a page both
# WRITES (insert/upsert/update/delete) and READS a table, the writes
# can't go through a read-only truth view — and the page's own reads
# typically need the same columns it just wrote. Wrapping the read in
# the truth view is artificial. Encode the ownership instead.
PAGE_RAW_OWNERS: dict[str, dict[str, str]] = {
    "asset-hub.html": {
        "asset_nodes":    "asset-hub is the canonical owner of asset CRUD (registration, neighbor graph, approval)",
        "pm_assets":      "asset-hub creates PM assets when an asset is first registered",
        "pm_scope_items": "asset-hub creates initial PM scope items for new assets",
        "pm_completions": "asset-hub reads completion history on the per-asset 360 view",
        "hive_members":   "asset-hub reads membership for permission checks (same write/read column set as v_worker_truth would project)",
        "asset_edges":                   "asset-hub is the canonical owner of the asset neighbor graph (add/remove edges)",
        "equipment_reading_templates":   "asset-hub is the canonical owner of reading-template CRUD per asset",
        "parts_staged_reservations":     "asset-hub stages part reservations when scheduling PM/jobs on an asset",
        "parts_staging_recommendations": "asset-hub generates staging recommendations from the asset PM context",
        "rcm_fmea_modes":                "asset-hub is the canonical FMEA-mode entry point per asset",
        "rcm_strategies":                "asset-hub is the canonical RCM strategy entry point per asset",
    },
    "hive.html": {
        "hive_members": "hive.html is the canonical owner of hive membership CRUD (create/join/leave/kick/promote)",
        "asset_nodes":  "hive.html approves pending asset registrations (admin workflow writes)",
        "logbook":      "hive.html approves/closes logbook entries via supervisor workflows",
        "pm_completions": "hive.html PM Health card reads completions with bespoke filters",
        "hives":        "hive.html IS the hive page — reads/writes the current hive row (canonical CRUD owner)",
    },
    "index.html": {
        "worker_profiles": "index.html signup flow creates worker_profiles rows (canonical write owner)",
    },
    "alert-hub.html": {
        "amc_briefings":            "alert-hub is the supervisor's AMC approval surface (read + write workflow)",
        "anomaly_signals":          "alert-hub writes acknowledge/resolve transitions on anomaly_signals",
        "failure_signature_alerts": "alert-hub renders + acknowledges raw signature alerts; consumers needing the wrapper read v_alert_truth instead",
        "parts_staging_recommendations": "alert-hub is the supervisor's parts-staging review surface (read + approve workflow)",
    },
    "achievements.html": {
        "achievement_xp_log":  "achievements.html writes XP log entries when a badge unlocks (canonical write owner)",
        "worker_achievements": "achievements.html is the canonical owner of worker badge unlocks (insert/read)",
    },
    "ph-intelligence.html": {
        "ph_intelligence_reports": "ph-intelligence is the canonical owner of intelligence-report CRUD",
    },
    "plant-connections.html": {
        "gateway_audit_log":     "plant-connections is the canonical owner of integration audit logging",
        "hive_retention_config": "plant-connections owns retention config CRUD (settings panel)",
        "integration_configs":   "plant-connections is the canonical owner of integration config CRUD",
        "sensor_topic_map":      "plant-connections owns sensor topic mapping CRUD",
        "sso_configs":           "plant-connections owns SSO config CRUD",
    },
    "shift-brain.html": {
        "shift_plans": "shift-brain is the canonical owner of shift_plans CRUD (create/edit/approve)",
    },
}

LEGITIMATE_RAW = {
    "early_access_emails":     "write-only marketing form, not a dashboard signal",
    "hive_audit_log":          "audit feed read raw by design (moderation surface needs full row context)",
    "automation_log":          "system-internal cron log; not a user-facing KPI",
    "ai_cost_log":             "founder/admin surface only; raw row needed",
    "ai_quality_log":          "internal eval data; not user-facing",
    "ai_rate_limits":          "internal quota state; not user-facing",
    "marketplace_platform_admins": "admin-table lookup; one read per page load",
    "report_contacts":         "single-purpose form; not a dashboard signal",
    "schedule_items":          "calendar feed; chronological, not a KPI",
    "skill_exam_attempts":     "personal log; raw row needed",
    "voice_journal_entries":   "personal log; raw row needed",
    "community_xp":            "single-purpose XP tally read per worker",
    "canonical_sources":       "the registry itself; trivially canonical",
    # 2026-05-20 — admin/observability surfaces read these raw; no per-user KPI is built on top.
    "analytics_events":     "raw event stream; read by founder-console for admin observability",
    "marketplace_disputes": "admin observability surface read; no per-user KPI built on top yet",
    "marketplace_orders":   "admin observability surface read; no per-user KPI built on top yet",
    "platform_feedback":    "admin observability surface read raw (founder-console)",
    "hive_benchmarks":      "benchmark comparison snapshot; read by hive + ph-intelligence for comparison tiles",
    "network_benchmarks":   "network-wide benchmark snapshot; read for comparison tiles",
    "ai_reports":           "observability tile data; read raw for display in cards",
    "skill_badges":         "badge-definitions catalog table; read for display lookups",
    "v_sensor_recent":      "recent-reads view consumed as-is (not a _truth wrapper, but already an aggregation view)",
}

CALM_TRIGGER_RE = re.compile(r"""<meta\s+name=["']calm-dashboard["']\s+content=["']1["']""", re.IGNORECASE)
FROM_RE = re.compile(r"""\.from\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)""", re.IGNORECASE)
ALLOW_RE = re.compile(r"canonical-allow", re.IGNORECASE)
SOURCE_CHIP_RE = re.compile(r"renderSourceChip\s*\(", re.IGNORECASE)

EXCLUDED_PAGE_PATTERNS = [
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"-test\.html$"),
]


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text)


def _is_excluded(name: str) -> bool:
    return any(rx.search(name) for rx in EXCLUDED_PAGE_PATTERNS)


def main() -> int:
    reg_path = ROOT / "canonical_registry.json"
    if not reg_path.exists():
        print(f"FAIL: canonical_registry.json missing ({reg_path})")
        return 2

    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    truth_views = {n for n in reg["views"].keys() if n.endswith("_truth")}
    all_views   = set(reg["views"].keys())
    all_tables  = set(reg["tables"].keys())

    # Find every Calm-opted-in page (presence of the meta tag).
    pages = []
    for p in sorted(ROOT.glob("*.html")):
        if _is_excluded(p.name):
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        if not CALM_TRIGGER_RE.search(raw):
            continue
        pages.append(p)

    page_results = []
    grand = {"canonical": 0, "drift": 0, "gap": 0, "allowed": 0, "unknown": 0}
    gap_counts = {}
    drift_counts = {}

    for p in pages:
        raw = p.read_text(encoding="utf-8", errors="replace")
        stripped = _strip_html_comments(raw)
        reads = set(FROM_RE.findall(stripped))
        has_allow_comment = ALLOW_RE.search(raw) is not None
        renders_source_chip = bool(SOURCE_CHIP_RE.search(stripped))

        # Per-call-site allowlist: collect every table name where a
        # `canonical-allow` comment appears within ~6 lines BEFORE the
        # .from('X') call. The strict comment scope (HTML comments include
        # both <!-- canonical-allow --> and inline // canonical-allow lines
        # inside <script>) lets writers exonerate a specific call without
        # turning off the rule for the whole page.
        allowlist_per_call: set[str] = set()
        # Pre-strip-aware regex: scan the RAW text for "canonical-allow"
        # markers near a `.from('X')` call. We look 800 chars (~ a small
        # block) ahead from each allow marker.
        for m in re.finditer(r"canonical-allow", raw, re.IGNORECASE):
            window = raw[m.end(): m.end() + 800]
            for fm in re.finditer(r"""\.from\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)""", window, re.IGNORECASE):
                allowlist_per_call.add(fm.group(1))

        canonical, drift, gap, allowed, unknown = [], [], [], [], []
        page_owners = PAGE_RAW_OWNERS.get(p.name, {})

        for r in sorted(reads):
            if r in truth_views:
                canonical.append(r)
            elif r in allowlist_per_call:
                allowed.append({"table": r, "reason": "inline canonical-allow comment"})
            elif r in page_owners:
                # Page is the canonical CRUD owner — read+write live together.
                allowed.append({"table": r, "reason": page_owners[r]})
            elif r in WRAPPERS:
                drift.append({"table": r, "use_instead": WRAPPERS[r]})
                drift_counts[r] = drift_counts.get(r, 0) + 1
            elif r in LEGITIMATE_RAW:
                allowed.append({"table": r, "reason": LEGITIMATE_RAW[r]})
            elif r in all_tables or r in all_views:
                gap.append(r)
                gap_counts[r] = gap_counts.get(r, 0) + 1
            else:
                unknown.append(r)

        # Per-page severity: a page is COMPLIANT if it has 0 drift + 0 gap.
        is_compliant = (len(drift) == 0 and len(gap) == 0)
        page_results.append({
            "page":           p.name,
            "compliant":      is_compliant,
            "canonical":      canonical,
            "drift":          drift,
            "gap":            gap,
            "allowed":        allowed,
            "unknown":        unknown,
            "has_canonical_allow_comment": has_allow_comment,
            "renders_source_chip":         renders_source_chip,
        })
        grand["canonical"] += len(canonical)
        grand["drift"]     += len(drift)
        grand["gap"]       += len(gap)
        grand["allowed"]   += len(allowed)
        grand["unknown"]   += len(unknown)

    compliant_pages = sum(1 for r in page_results if r["compliant"])
    total_pages = len(page_results)
    conformance = (compliant_pages / total_pages) if total_pages else 1.0

    report = {
        "summary": {
            "calm_opted_in_pages":    total_pages,
            "compliant_pages":        compliant_pages,
            "conformance":            round(conformance, 3),
            "total_canonical_reads":  grand["canonical"],
            "total_drift_reads":      grand["drift"],
            "total_gap_reads":        grand["gap"],
            "total_allowed_reads":    grand["allowed"],
            "total_unknown_reads":    grand["unknown"],
            "v_truth_views_in_registry": len(truth_views),
        },
        "by_page":      page_results,
        "gap_counts":   dict(sorted(gap_counts.items(),   key=lambda kv: -kv[1])),
        "drift_counts": dict(sorted(drift_counts.items(), key=lambda kv: -kv[1])),
    }

    (ROOT / "calm_canonical_audit_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # Human-readable report
    md = []
    md.append("# Calm Dashboard Canonical-Wiring Audit (Layer -1.5)\n")
    md.append("Classifies every `.from('table')` read on Calm-opted-in pages as")
    md.append("CANONICAL / DRIFT / GAP / ALLOWED. Run by `tools/audit_calm_dashboard_canonical.py`.\n")
    s = report["summary"]
    md.append("## Summary\n")
    md.append(f"- Calm-opted-in pages: **{s['calm_opted_in_pages']}**")
    md.append(f"- Fully compliant pages (0 drift + 0 gap): **{s['compliant_pages']}** ({int(s['conformance']*100)}%)")
    md.append(f"- Canonical reads (✅): **{s['total_canonical_reads']}**")
    md.append(f"- Drift reads (⚠️ wrapper exists, page reads raw): **{s['total_drift_reads']}**")
    md.append(f"- Gap reads (❌ no wrapper exists yet): **{s['total_gap_reads']}**")
    md.append(f"- Allowed reads (legitimate raw): **{s['total_allowed_reads']}**")
    md.append(f"- Truth views in registry: **{s['v_truth_views_in_registry']}**")
    md.append("")
    md.append("## Per-page conformance\n")
    md.append("| Page | Canonical | Drift | Gap | Allowed | Chip? | Compliant |")
    md.append("|---|---:|---:|---:|---:|:---:|:---:|")
    for r in report["by_page"]:
        md.append(
            f"| `{r['page']}` | {len(r['canonical'])} | {len(r['drift'])} | "
            f"{len(r['gap'])} | {len(r['allowed'])} | "
            f"{'✓' if r['renders_source_chip'] else '—'} | "
            f"{'✅' if r['compliant'] else '❌'} |"
        )
    md.append("")
    md.append("## Top GAP tables (no `v_*_truth` exists — next-build queue)\n")
    md.append("| Raw table | Pages reading it | Suggested wrapper |")
    md.append("|---|---:|---|")
    for tbl, cnt in list(report["gap_counts"].items())[:20]:
        suggested = f"v_{tbl}_truth" if not tbl.endswith("s") else f"v_{tbl[:-1]}_truth"
        md.append(f"| `{tbl}` | {cnt} | `{suggested}` (suggested) |")
    md.append("")
    md.append("## Top DRIFT tables (wrapper exists, pages still reading raw)\n")
    md.append("| Raw table | Use instead | Pages reading raw |")
    md.append("|---|---|---:|")
    for tbl, cnt in list(report["drift_counts"].items())[:20]:
        md.append(f"| `{tbl}` | `{WRAPPERS[tbl]}` | {cnt} |")
    md.append("")
    md.append("## Per-page detail\n")
    for r in report["by_page"]:
        md.append(f"### `{r['page']}` — {'✅ compliant' if r['compliant'] else '❌ not compliant'}\n")
        if r['canonical']:
            md.append(f"**Canonical** ({len(r['canonical'])}): " + ", ".join(f"`{x}`" for x in r['canonical']))
        if r['drift']:
            md.append(f"**Drift** ({len(r['drift'])}): " + ", ".join(f"`{d['table']}` → `{d['use_instead']}`" for d in r['drift']))
        if r['gap']:
            md.append(f"**Gap** ({len(r['gap'])}): " + ", ".join(f"`{x}`" for x in r['gap']))
        if r['allowed']:
            md.append(f"**Allowed raw** ({len(r['allowed'])}): " + ", ".join(f"`{a['table']}`" for a in r['allowed']))
        md.append("")

    (ROOT / "calm_canonical_audit_report.md").write_text("\n".join(md), encoding="utf-8")

    # Stdout banner
    print("Calm Dashboard Canonical-Wiring Audit")
    print(f"  pages opted in:    {s['calm_opted_in_pages']}")
    print(f"  fully compliant:   {s['compliant_pages']}/{s['calm_opted_in_pages']} ({int(s['conformance']*100)}%)")
    print(f"  canonical reads:   {s['total_canonical_reads']}")
    print(f"  drift reads:       {s['total_drift_reads']}")
    print(f"  gap reads:         {s['total_gap_reads']}")
    print(f"  allowed raw reads: {s['total_allowed_reads']}")
    print()
    if drift_counts:
        print("Top DRIFT tables (wrapper exists; pages should switch):")
        for tbl, cnt in list(report["drift_counts"].items())[:5]:
            print(f"  {tbl:<28} -> {WRAPPERS[tbl]:<30} ({cnt} page{'s' if cnt > 1 else ''})")
    print()
    if gap_counts:
        print("Top GAP tables (no wrapper exists; build next):")
        for tbl, cnt in list(report["gap_counts"].items())[:5]:
            print(f"  {tbl:<28} ({cnt} page{'s' if cnt > 1 else ''})")

    # Exit non-zero only on drift (gap is informational; building wrappers
    # is a follow-up project, not a CI gate). Drift is fixable today.
    return 1 if grand["drift"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
