"""
Realtime Subscription Consistency Validator (L0, ratcheted).
=============================================================
Catches the class found 2026-05-20 on hive.html:

  `hive.html` subscribed to `postgres_changes` on table 'assets'
   but never read from 'assets' — the canonical table is 'asset_nodes'.
   Result: supervisors got ZERO realtime "asset pending approval"
   notifications + workers got ZERO realtime approval/rejection toasts.
   The bug was invisible because static validators look at .from()
   reads, and chip auditors look at chip strings — neither inspects
   .channel().on('postgres_changes', { table: X }).

Detection
  1. For each page, collect:
     A. The set of tables the page READS via `.from('TABLE')`.
        If the read is on `v_<name>_truth`, treat it as a read of the
        underlying tables (we approximate by stripping the v_/_truth
        wrappers — covers ~90% of cases without parsing view DDL).
     B. The set of tables the page SUBSCRIBES to via
        `.on('postgres_changes', { ... table: 'TABLE' ... })`.
  2. For each subscribed table that is NOT in the read set (and not
     allowlisted), flag DRIFT — the subscription does nothing useful
     to update the UI.

Allow markers
  Add `// realtime-allow: <reason>` near the .on() call. Use for
  audit-only listeners (e.g. observability that doesn't refresh UI).

Output
  realtime_subscription_consistency_report.json (machine)
  Exit 1 when drift > baseline; 0 otherwise.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "realtime_subscription_consistency_report.json"
BASELINE_PATH = ROOT / "realtime_subscription_consistency_baseline.json"


PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]


# .from('NAME') — captures tables OR views the page reads.
FROM_RE = re.compile(r"""\.from\(\s*['"`](?P<name>[a-z_][\w]*)['"`]\s*\)""")

# .on('postgres_changes', { ... table: 'NAME' ... })
# Tolerates multi-line object literals.
CHANNEL_ON_RE = re.compile(
    r"""\.on\(\s*['"`]postgres_changes['"`]\s*,\s*\{(?P<obj>[^}]{0,500})\}""",
    re.DOTALL,
)
TABLE_FIELD_RE = re.compile(r"""\btable\s*:\s*['"`](?P<table>[a-z_][\w]*)['"`]""")

ALLOW_RE = re.compile(r"realtime-allow", re.IGNORECASE)

HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def _underlying_tables(view_name: str) -> set[str]:
    """Approximate the underlying tables for a v_<name>_truth view by
    stripping the v_/_truth wrappers. Covers patterns like:
      v_pm_compliance_truth → pm_compliance / pm_compliances (heuristic)
      v_asset_truth         → asset / assets
      v_logbook_truth       → logbook / logbooks
      v_inventory_items_truth → inventory_items
    For VIEWS that union 2+ tables (v_alert_truth = failure_signature_alerts +
    anomaly_signals), the heuristic returns an APPROXIMATION; allowlist or
    accept noise. Real lineage edges live in canonical/lineage_edges.json
    for the audit-pair pipeline; this validator keeps the heuristic for now."""
    if not (view_name.startswith("v_") and view_name.endswith("_truth")):
        return {view_name}
    stem = view_name[2:-6]  # strip v_ and _truth
    # Returns: stem itself + plural variant + known multi-table view bases.
    out = {stem}
    if stem.endswith("s"):
        out.add(stem)
    else:
        out.add(stem + "s")
    # Known multi-table views (hand-curated; extend as new views ship)
    EXTRA = {
        "alert":       {"failure_signature_alerts", "anomaly_signals"},
        "pm_compliance": {"pm_assets", "pm_completions", "pm_scope_items"},
        "pm_scope_items": {"pm_scope_items", "pm_completions"},
        "amc":         {"amc_briefings"},
        "sensor":      {"sensor_readings"},
        "asset":       {"asset_nodes"},
        "risk":        {"asset_risk_scores"},
        "logbook":     {"logbook"},
        "worker":      {"hive_members", "worker_profiles"},
        "inventory_items": {"inventory_items"},
        "marketplace_listings": {"marketplace_listings"},
        "marketplace_orders":   {"marketplace_orders"},
        "marketplace_inquiries": {"marketplace_inquiries"},
        "marketplace_sellers":  {"marketplace_sellers"},
        "ai_reports":  {"ai_reports"},
        "hives":       {"hives"},
        "hive_readiness": {"hive_readiness"},
        "external_sync": {"external_sync"},
        "project":     {"projects"},
        "project_items": {"project_items"},
        "project_progress": {"project_progress_logs"},
    }
    if stem in EXTRA:
        out |= EXTRA[stem]
    return out


def _scan_page(page: Path) -> dict:
    try:
        raw = page.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"reads": set(), "subscriptions": [], "drift": []}
    body = HTML_COMMENT_RE.sub("", raw)

    # Tables / views read on this page
    reads = {m.group("name").lower() for m in FROM_RE.finditer(body)}

    # Expand reads to include underlying tables for v_*_truth views.
    expanded_reads = set(reads)
    for r in reads:
        expanded_reads |= _underlying_tables(r)

    # Subscriptions
    subscriptions: list[dict] = []
    drift: list[dict] = []
    for m in CHANNEL_ON_RE.finditer(body):
        obj = m.group("obj")
        tm = TABLE_FIELD_RE.search(obj)
        if not tm:
            continue
        table = tm.group("table").lower()

        # Allow window — 500 chars before / 200 after covers the typical
        # "comment block above .channel() chain → .on()" placement where
        # the marker is on a different line than the subscription itself.
        win = body[max(0, m.start() - 500):m.end() + 200]
        allowed = bool(ALLOW_RE.search(win))

        subscriptions.append({
            "table":   table,
            "allowed": allowed,
            "offset":  m.start(),
        })

        if not allowed and table not in expanded_reads:
            drift.append({
                "table":     table,
                "char_offset": m.start(),
            })

    return {
        "reads":          sorted(reads),
        "subscriptions":  subscriptions,
        "drift":          drift,
    }


# Sentinel binding: name the L2 test `test('realtime_subscription_consistency: ...')` for coverage credit.
CHECK_NAMES = ["realtime_subscription_consistency"]


def main() -> int:
    per_page: list[dict] = []
    total_drift = 0
    total_subs  = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        result = _scan_page(page)
        per_page.append({
            "page":         name,
            "reads":        result["reads"],
            "subscriptions": result["subscriptions"],
            "drift":        result["drift"],
        })
        total_drift += len(result["drift"])
        total_subs  += len(result["subscriptions"])

    # Baseline ratchet
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception:
            baseline = 0
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(
            json.dumps({"drift": baseline, "established": True}, indent=2),
            encoding="utf-8",
        )

    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(
            json.dumps({"drift": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    report = {
        "summary": {
            "pages_scanned":  len(per_page),
            "total_subs":     total_subs,
            "total_drift":    total_drift,
            "baseline":       baseline,
        },
        "per_page": per_page,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("Realtime Subscription Consistency Validator (L0)"))
    print("=" * 56)
    print(f"  pages scanned:       {len(per_page)}")
    print(f"  total subscriptions: {total_subs}")
    print(f"  drift:               {total_drift}  (baseline: {baseline})")

    if total_drift == 0:
        print()
        print(_green("PASS — every postgres_changes subscription targets a table the page reads."))
        return 0

    print()
    print("Drift (subscribed to a table the page never reads):")
    for entry in per_page:
        if not entry["drift"]:
            continue
        print(f"  {entry['page']}  reads: [{', '.join(entry['reads'][:6])}{'...' if len(entry['reads'])>6 else ''}]")
        for d in entry["drift"]:
            print(f"    subscribed to '{d['table']}' but never reads it")

    if total_drift > baseline:
        print()
        print(_red(f"FAIL — count {total_drift} > baseline {baseline}"))
        print("Fix options:")
        print("  1. Update the subscription to the table the page actually reads.")
        print("  2. Remove the dead subscription entirely.")
        print("  3. Add `// realtime-allow: <reason>` if observability-only listener.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
