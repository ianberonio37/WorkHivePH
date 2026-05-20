"""
Canonical Drift — Platform-Wide Miner (Layer -1.5).
====================================================

This is the SECOND-GENERATION canonical drift detector. Two layers already
exist:

  - `validate_canonical_sources.py` (L0): blocks NEW raw reads on a small
    set of "owner pages." Grandfathers existing drift via `KNOWN_DRIFT`,
    which is how the PM Scheduler / PM Overdue dashboard mismatch shipped
    (pm-scheduler.html is on the allowlist; it reads `pm_scope_items` raw
    and reimplements FREQ_DAYS + calcNextDue locally, so its `0 overdue`
    disagrees with the home tile's `21 overdue` read from
    `v_pm_scope_items_truth`).

  - `tools/audit_calm_dashboard_canonical.py` (L-1.5): per-page
    canonical/drift/gap/allowed audit, but only for pages that opted into
    the Calm Dashboard Contract.

This miner closes the seam between them. It scans EVERY HTML page plus
shared JS and adds two signals neither existing layer carries:

  KPI-aware classification
    The miner detects whether a page renders a user-facing hero number
    (#stat-*, #*-count, #*-overdue, .sc-hero, [data-kpi], etc.). When a
    page reads raw `T` AND a `v_T_truth` view exists AND the page renders
    a KPI from that read, the drift is escalated to TIER A — the class
    that produces "two pages, two numbers" inconsistency for users. TIER B
    is drift on internal admin pages or shared JS where the user is less
    likely to see disagreement.

  Truth-math reimplementation
    The miner detects pages that read raw `T` while ALSO defining
    constants/functions that duplicate the math the canonical view bakes
    in. Hits: `FREQ_DAYS`, `RISK_TIERS`, `OEE_FACTORS`, `calcNextDue`,
    `getItemStatus`, `daysUntil`, etc. This is what makes drift go from
    "same numbers, different query path" to "wrong numbers."

Output:
  - canonical_drift_platform_report.json
  - canonical_drift_platform_report.md

Exit code:
  - 0 when there are 0 TIER A NEW drifts (TIER A grandfathered + TIER B
    drift do not fail the gate today; they are the punch list)
  - 1 otherwise

Wire-up:
  - Mega Gate: registered in run_platform_checks.py
  - Manifest:  frontend_kpi_reads_canonical rule
  - L0:        validate_user_facing_kpi_canonical.py reads the JSON
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Iterable


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent


# Curated underlying-table to canonical-view map. Mirrors CANONICAL_PAIRS in
# validate_canonical_sources.py + the wrapper list in
# audit_calm_dashboard_canonical.py. Single source of truth here for the miner.
CANONICAL_PAIRS: dict[str, str] = {
    "logbook":                  "v_logbook_truth",
    "asset_nodes":              "v_asset_truth",
    "assets":                   "v_asset_truth",
    "asset_risk_scores":        "v_risk_truth",
    "pm_assets":                "v_pm_compliance_truth",
    "pm_completions":           "v_pm_compliance_truth",
    "pm_scope_items":           "v_pm_scope_items_truth",
    "inventory_items":          "v_inventory_items_truth",
    "marketplace_sellers":      "v_marketplace_sellers_truth",
    "marketplace_listings":     "v_marketplace_listings_truth",
    "marketplace_inquiries":    "v_marketplace_inquiries_truth",
    "community_posts":          "v_community_posts_truth",
    "hives":                    "v_hives_truth",
    "external_sync":            "v_external_sync_truth",
    "projects":                 "v_project_truth",
    "hive_readiness":           "v_hive_readiness_truth",
    "worker_profiles":          "v_worker_truth",
    "hive_members":             "v_worker_truth",
    "failure_signature_alerts": "v_alert_truth",
    "anomaly_signals":          "v_alert_truth",
    "amc_briefings":            "v_amc_truth",
    "sensor_readings":          "v_sensor_truth",
    "rcm_pf_intervals":         "v_pf_truth",
}

# Tables that legitimately read raw — the miner classifies these as ALLOWED
# instead of GAP so they don't pollute the next-build queue.
LEGITIMATE_RAW: dict[str, str] = {
    "early_access_emails":           "write-only marketing form",
    "hive_audit_log":                "moderation surface needs full row context",
    "automation_log":                "system-internal cron log",
    "ai_cost_log":                   "founder/admin surface only",
    "ai_quality_log":                "internal eval data",
    "ai_rate_limits":                "internal quota state",
    "analytics_events":              "internal admin telemetry; founder-console-only surface",
    "marketplace_platform_admins":   "admin-table lookup",
    "report_contacts":               "single-purpose form",
    "schedule_items":                "calendar feed, chronological",
    "skill_exam_attempts":           "personal log",
    "voice_journal_entries":         "personal log",
    "community_xp":                  "single-purpose XP tally",
    "canonical_sources":             "the registry itself",
}

# Pages whose role is the CANONICAL CRUD OWNER for a table — they write the
# rows and need raw-read access to the same column set they just wrote.
# Mirrors PAGE_RAW_OWNERS in audit_calm_dashboard_canonical.py.
PAGE_RAW_OWNERS: dict[str, dict[str, str]] = {
    "asset-hub.html": {
        "asset_nodes":    "canonical owner of asset CRUD",
        "pm_assets":      "creates PM assets when an asset is registered",
        "pm_scope_items": "creates initial PM scope items",
        "pm_completions": "reads completion history on per-asset 360 view",
        "hive_members":   "permission checks (same write/read column set)",
    },
    "hive.html": {
        "hive_members":   "canonical owner of membership CRUD",
        "asset_nodes":    "approves pending asset registrations",
        "logbook":        "approves/closes logbook entries",
        "pm_completions": "PM Health card reads completions with bespoke filters",
    },
    "index.html": {
        "worker_profiles": "signup flow creates worker_profiles rows",
    },
    "alert-hub.html": {
        "amc_briefings":            "AMC approval surface (read + write)",
        "anomaly_signals":          "writes acknowledge/resolve transitions",
        "failure_signature_alerts": "renders + acknowledges raw signature alerts",
    },
    "logbook.html": {
        "logbook":         "canonical owner of logbook CRUD",
        "inventory_items": "parts-picker writes deductions on logbook close",
        "project_links":   "logbook entry -> project link writer (small join table)",
    },
    "inventory.html": {
        "inventory_items": "canonical owner of inventory CRUD",
    },
    "pm-scheduler.html": {
        "pm_assets":      "creates + edits PM asset configs",
        "pm_completions": "writes completion rows when a PM is marked done",
        "project_links":  "PM completion -> project link writer (small join table)",
        # pm_scope_items intentionally NOT here: reads should go through
        # v_pm_scope_items_truth. The page DOES write scope items, but the
        # write path can stay raw (`.insert(...)`); only the SELECT reads
        # need to migrate. The miner separates by verb.
    },
    "project-manager.html": {
        "projects":      "canonical owner of project CRUD",
        "asset_nodes":   "project asset linker (writes project_links rows)",
        "project_links": "project_links is owned by project-manager (it's the join table)",
    },
    "parts-tracker.html": {
        "inventory_items": "parts deduction writer",
    },
    "integrations.html": {
        "integration_configs": "canonical owner of integration config CRUD",
        "external_sync":        "CMMS sync upsert writer (owner page does its own raw reads too)",
    },
}

# ── User-facing KPI surfaces ──────────────────────────────────────────────────
# Pages where a wrong number is a wrong NUMBER on a tile a user reads in
# 5 seconds. Drift here is TIER A: must not disagree with another surface.
USER_FACING_KPI_SURFACES = {
    "hive.html", "index.html", "pm-scheduler.html", "inventory.html",
    "alert-hub.html", "logbook.html", "asset-hub.html", "analytics.html",
    "ai-quality.html", "founder-console.html", "platform-health.html",
    "dayplanner.spec.ts",  # placeholder — keeps the set sortable
    "dayplanner.html",
    "report-sender.html",
    "achievements.html",
}

# Hero-number HTML signals — presence on a page = "renders a user KPI".
HERO_ID_RE = re.compile(
    r"""id\s*=\s*["']("""
    r"stat-[a-z0-9_-]+|"
    r"[a-z0-9_-]+-(?:count|overdue|hero|kpi|score|total)|"
    r"hero-[a-z0-9_-]+|"
    r"kpi-[a-z0-9_-]+|"
    r"pulse-[a-z0-9_-]+"
    r""")["']""",
    re.IGNORECASE,
)
HERO_CLASS_RE = re.compile(
    r"""class\s*=\s*["'][^"']*\b(sc-hero|hero|kpi-hero|metric-hero|stat-hero)\b""",
    re.IGNORECASE,
)
HERO_DATA_KPI_RE = re.compile(
    r"""data-kpi\s*=\s*["'][^"']+["']""",
    re.IGNORECASE,
)

# ── Truth-math reimplementation signals ───────────────────────────────────────
# Pages that define these locally AND read a raw table that has a v_*_truth
# already baking in the same math are flagged as TIER A:reimplemented.
# Names that historically collided across domains (e.g. `getItemStatus` lives
# in both pm-scheduler.html and dayplanner.html with different semantics) are
# deliberately excluded. The PM-domain truth-math is identified by the
# FREQ_DAYS-style constants + the compute*/calcNextDue function names, all of
# which are PM/OEE/risk-specific.
TRUTH_MATH_PATTERNS = [
    (re.compile(r"\bFREQ_DAYS\s*=\s*\{"),                          "FREQ_DAYS",        "pm_scope_items"),
    (re.compile(r"\bHIVE_FREQ_DAYS\s*=\s*\{"),                     "HIVE_FREQ_DAYS",   "pm_scope_items"),
    (re.compile(r"\bcalcNextDue\s*\("),                            "calcNextDue()",    "pm_scope_items"),
    (re.compile(r"\bRISK_TIERS?\s*=\s*\{"),                        "RISK_TIERS",       "asset_risk_scores"),
    (re.compile(r"\bOEE_FACTORS?\s*=\s*\{"),                       "OEE_FACTORS",      "logbook"),
    (re.compile(r"\bcomputeOEE\s*\("),                             "computeOEE()",     "logbook"),
    (re.compile(r"\bcomputeMTBF\s*\("),                            "computeMTBF()",    "logbook"),
    (re.compile(r"\bcomputeCompliance\s*\("),                      "computeCompliance()", "pm_scope_items"),
    (re.compile(r"\bSEVERITY_WEIGHTS?\s*=\s*\{"),                  "SEVERITY_WEIGHTS", "failure_signature_alerts"),
]

# ── Regexes ───────────────────────────────────────────────────────────────────
# We need verbs to distinguish reads from writes: SELECT-style reads must use
# the canonical view; INSERT / UPDATE / UPSERT / DELETE legitimately target
# the underlying.
FROM_VERB_RE = re.compile(
    r"""\.from\(\s*['"](?P<tbl>[a-z_][a-z0-9_]*)['"]\s*\)"""
    r"""(?P<chain>[\s\S]{0,400}?)"""
    r"""\.(?P<verb>select|insert|update|upsert|delete)\b""",
    re.IGNORECASE,
)
ALLOW_TOKEN_RE = re.compile(r"canonical-allow", re.IGNORECASE)

EXCLUDED_HTML = [
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"-test\.html$"),
]


def _replace_keep_newlines(rx_pattern: str, text: str) -> str:
    """Replace each match with spaces, preserving newlines so line numbers
    of any subsequent regex match still align with the original file."""
    def repl(m: re.Match) -> str:
        s = m.group(0)
        return "".join(c if c == "\n" else " " for c in s)
    return re.sub(rx_pattern, repl, text)


def _strip_comments_html(text: str) -> str:
    return _replace_keep_newlines(r"<!--[\s\S]*?-->", text)


def _strip_comments_js(text: str) -> str:
    text = _replace_keep_newlines(r"/\*[\s\S]*?\*/", text)
    text = _replace_keep_newlines(r"(?<!:)//[^\n]*", text)
    return text


def _is_excluded(name: str) -> bool:
    return any(rx.search(name) for rx in EXCLUDED_HTML)


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _line_at(text: str, line_no: int) -> str:
    lines = text.splitlines()
    idx = line_no - 1
    return lines[idx] if 0 <= idx < len(lines) else ""


def _allow_reason_near(text: str, match_start: int) -> str | None:
    # Scan up to 8 lines back so multi-line comment blocks AND any
    # intervening boilerplate (Promise.all([ ..., loadingEl, etc.) between
    # the comment and the .from() call still count. Real-world annotations
    # tend to wrap to 3-4 lines plus 2-3 lines of code before the SELECT.
    ln = _line_no(text, match_start)
    for probe in range(ln, max(0, ln - 8), -1):
        if probe <= 0:
            continue
        line = _line_at(text, probe)
        idx = line.lower().find("canonical-allow")
        if idx >= 0:
            return line[idx:].strip()
    return None


def _renders_kpi(raw: str, basename: str) -> bool:
    if basename in USER_FACING_KPI_SURFACES:
        return True
    return bool(HERO_ID_RE.search(raw) or HERO_CLASS_RE.search(raw) or HERO_DATA_KPI_RE.search(raw))


def _truth_math_local(raw: str) -> list[dict]:
    hits = []
    for rx, label, related in TRUTH_MATH_PATTERNS:
        if rx.search(raw):
            hits.append({"pattern": label, "related_table": related})
    return hits


def _scan_file(path: Path, layer: str) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    basename = path.name
    page_owners = PAGE_RAW_OWNERS.get(basename, {})

    # Comment stripping — keep raw for KPI-id detection (since some tile ids
    # live in templates we don't want to lose), but the verb scan should
    # ignore commented-out queries.
    if layer == "html":
        scan_text = _strip_comments_html(raw)
    else:
        scan_text = _strip_comments_js(raw)

    canonical, drift, gap, allowed, unknown = [], [], [], [], []

    for m in FROM_VERB_RE.finditer(scan_text):
        tbl = m.group("tbl").lower()
        verb = m.group("verb").lower()
        line_no = _line_no(scan_text, m.start())

        # Writes always legitimately target the underlying.
        if verb in ("insert", "update", "upsert", "delete"):
            continue

        # If the table itself IS a canonical view, score it as canonical.
        if tbl.startswith("v_") and tbl.endswith("_truth"):
            canonical.append({"table": tbl, "line": line_no, "verb": verb})
            continue

        # Inline allow.
        allow = _allow_reason_near(scan_text, m.start())
        if allow:
            allowed.append({"table": tbl, "line": line_no, "reason": allow})
            continue

        if tbl in page_owners:
            allowed.append({"table": tbl, "line": line_no, "reason": page_owners[tbl]})
            continue

        if tbl in CANONICAL_PAIRS:
            drift.append({"table": tbl, "line": line_no, "use_instead": CANONICAL_PAIRS[tbl]})
            continue

        if tbl in LEGITIMATE_RAW:
            allowed.append({"table": tbl, "line": line_no, "reason": LEGITIMATE_RAW[tbl]})
            continue

        gap.append({"table": tbl, "line": line_no})

    renders_kpi = _renders_kpi(raw, basename) if layer == "html" else False
    truth_math = _truth_math_local(raw) if layer == "html" else []

    return {
        "file":         str(path.relative_to(ROOT)).replace("\\", "/"),
        "layer":        layer,
        "basename":     basename,
        "renders_kpi":  renders_kpi,
        "truth_math":   truth_math,
        "canonical":    canonical,
        "drift":        drift,
        "gap":          gap,
        "allowed":      allowed,
        "unknown":      unknown,
    }


def _classify_severity(result: dict) -> str:
    """TIER A = user-facing KPI surface with drift (must not ship divergent
                numbers); intensifies if local truth-math is present.
       TIER B = drift on a non-KPI page or shared JS.
       OK     = no drift."""
    if not result["drift"]:
        return "OK"
    if result["renders_kpi"] or result["truth_math"]:
        return "TIER_A"
    return "TIER_B"


def main() -> int:
    targets: list[tuple[Path, str]] = []
    for p in sorted(ROOT.glob("*.html")):
        if _is_excluded(p.name):
            continue
        targets.append((p, "html"))
    for fname in ("utils.js", "nav-hub.js", "companion-launcher.js",
                  "search-overlay.js", "wh-persona.js"):
        candidate = ROOT / fname
        if candidate.exists():
            targets.append((candidate, "shared_js"))

    results = []
    grand = {"canonical": 0, "drift": 0, "gap": 0, "allowed": 0,
             "tier_a": 0, "tier_b": 0, "kpi_pages": 0, "truth_math_pages": 0}
    drift_table_counts: dict[str, int] = {}
    gap_table_counts:   dict[str, int] = {}
    tier_a_pages: list[dict] = []

    for path, layer in targets:
        r = _scan_file(path, layer)
        r["severity"] = _classify_severity(r)
        results.append(r)

        grand["canonical"] += len(r["canonical"])
        grand["drift"]     += len(r["drift"])
        grand["gap"]       += len(r["gap"])
        grand["allowed"]   += len(r["allowed"])

        if r["renders_kpi"]:
            grand["kpi_pages"] += 1
        if r["truth_math"]:
            grand["truth_math_pages"] += 1

        if r["severity"] == "TIER_A":
            grand["tier_a"] += 1
            tier_a_pages.append({
                "file":          r["file"],
                "drift":         r["drift"],
                "truth_math":    r["truth_math"],
                "renders_kpi":   r["renders_kpi"],
            })
        elif r["severity"] == "TIER_B":
            grand["tier_b"] += 1

        for d in r["drift"]:
            drift_table_counts[d["table"]] = drift_table_counts.get(d["table"], 0) + 1
        for g in r["gap"]:
            gap_table_counts[g["table"]] = gap_table_counts.get(g["table"], 0) + 1

    report = {
        "summary": {
            "files_scanned":        len(results),
            "kpi_rendering_pages":  grand["kpi_pages"],
            "truth_math_pages":     grand["truth_math_pages"],
            "tier_a_pages":         grand["tier_a"],
            "tier_b_pages":         grand["tier_b"],
            "total_canonical_reads": grand["canonical"],
            "total_drift_reads":     grand["drift"],
            "total_gap_reads":       grand["gap"],
            "total_allowed_reads":   grand["allowed"],
        },
        "tier_a_pages":      tier_a_pages,
        "drift_table_counts": dict(sorted(drift_table_counts.items(), key=lambda kv: -kv[1])),
        "gap_table_counts":   dict(sorted(gap_table_counts.items(),   key=lambda kv: -kv[1])),
        "by_file":           results,
    }

    out_json = ROOT / "canonical_drift_platform_report.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = []
    s = report["summary"]
    md.append("# Canonical Drift — Platform-Wide (Layer -1.5)\n")
    md.append("Every HTML page + shared JS scanned for `.from('T').select(...)` calls.")
    md.append("Drift on a **user-facing KPI page** (e.g. hero numbers on tiles) is TIER A —")
    md.append("the class that produces _two pages, two numbers_ inconsistency.\n")
    md.append("## Summary\n")
    md.append(f"- Files scanned: **{s['files_scanned']}**")
    md.append(f"- KPI-rendering pages: **{s['kpi_rendering_pages']}**")
    md.append(f"- Pages with local truth-math (FREQ_DAYS / calcNextDue / ...): **{s['truth_math_pages']}**")
    md.append(f"- **TIER A drift pages** (user-facing KPI surface): **{s['tier_a_pages']}**")
    md.append(f"- TIER B drift pages (internal / shared JS): **{s['tier_b_pages']}**")
    md.append(f"- Canonical reads: {s['total_canonical_reads']} · Drift: {s['total_drift_reads']} · "
              f"Gap: {s['total_gap_reads']} · Allowed: {s['total_allowed_reads']}")
    md.append("")

    if tier_a_pages:
        md.append("## TIER A — User-facing KPI surfaces with canonical drift\n")
        md.append("These pages render hero numbers AND read raw tables that have a canonical view.")
        md.append("Same metric can read 'one number here, different number there' compared to the home tile.\n")
        md.append("| Page | Drift reads | Local truth-math | Fix |")
        md.append("|---|---|---|---|")
        for r in tier_a_pages:
            drifts = ", ".join(f"`{d['table']}`→`{d['use_instead']}`" for d in r["drift"])
            tm     = ", ".join(t["pattern"] for t in r["truth_math"]) or "—"
            fix    = f"Migrate reads to `v_*_truth`; drop local constants" if r["truth_math"] else "Migrate reads to `v_*_truth`"
            md.append(f"| `{r['file']}` | {drifts} | {tm} | {fix} |")
        md.append("")

    if report["drift_table_counts"]:
        md.append("## Drift by table (which raw tables are still being read)\n")
        md.append("| Raw table | Files reading raw | Use instead |")
        md.append("|---|---:|---|")
        for tbl, cnt in report["drift_table_counts"].items():
            md.append(f"| `{tbl}` | {cnt} | `{CANONICAL_PAIRS.get(tbl, '?')}` |")
        md.append("")

    if report["gap_table_counts"]:
        md.append("## Gap tables (no `v_*_truth` yet — next-build queue)\n")
        md.append("| Raw table | Files reading it |")
        md.append("|---|---:|")
        for tbl, cnt in list(report["gap_table_counts"].items())[:30]:
            md.append(f"| `{tbl}` | {cnt} |")
        md.append("")

    (ROOT / "canonical_drift_platform_report.md").write_text("\n".join(md), encoding="utf-8")

    print("Canonical Drift — Platform-Wide Miner")
    print(f"  files scanned:        {s['files_scanned']}")
    print(f"  KPI-rendering pages:  {s['kpi_rendering_pages']}")
    print(f"  TIER A drift pages:   {s['tier_a_pages']}")
    print(f"  TIER B drift pages:   {s['tier_b_pages']}")
    print(f"  drift reads:          {s['total_drift_reads']}")
    print(f"  gap reads:            {s['total_gap_reads']}")
    if tier_a_pages:
        print()
        print("Top TIER A pages (user-facing KPI + canonical drift):")
        for r in tier_a_pages[:8]:
            drifts = ", ".join(f"{d['table']}->{d['use_instead']}" for d in r["drift"])
            print(f"  {r['file']:<30} {drifts}")

    # Miner is informational: it surfaces TIER A pages but does not gate.
    # The L0 ratchet `validate_user_facing_kpi_canonical.py` enforces
    # forward-only motion over the baseline this report produces.
    return 0


if __name__ == "__main__":
    sys.exit(main())
