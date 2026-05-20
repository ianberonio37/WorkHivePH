"""
Source-Chip Truth Validator (L0, ratcheted).
=============================================
Calm Dashboard pages declare which canonical views back each panel via:

  renderSourceChip({
    source: 'v_logbook_truth + v_pm_compliance_truth + v_inventory_items_truth',
    freshness: '...',
    notes:    ['...'],
  })

The chip is a USER-VISIBLE truth claim: "this panel reads from these views."
If the page renames or removes a view but the chip text is left behind, the
user is being lied to about lineage. Same class as the bug we hit on
2026-05-20 — page+number disagreed because the lineage drifted.

Detection
  1. For every renderSourceChip(...) call, extract the `source:` string.
  2. Parse view names from the string — every `v_<name>_truth` token.
     Also detect raw table tokens (no `_truth` suffix) for completeness;
     the chip can legitimately name raw tables it reads.
  3. Read the whole page for actual `.from('<NAME>')` calls.
  4. For each CLAIMED view: if it is NOT in the actual `.from()` set,
     flag as STALE_CLAIM. The chip is asserting a read that no longer
     happens.

False-positive controls
  - Allow inline `// source-chip-allow: <reason>` near the renderSourceChip
    call to document an intentional declaration (e.g. the page reads via
    an edge-fn invoke rather than a direct db.from()).
  - Ignore chip tokens that aren't view-shaped (`v_*_truth` or known raw
    tables like `pm_completions`, `logbook`) — narrative text in the
    source string is fine.

Output
  source_chip_truth_report.json (machine)
  Exit 1 when stale_claims > baseline; 0 otherwise.
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
REPORT_PATH   = ROOT / "source_chip_truth_report.json"
BASELINE_PATH = ROOT / "source_chip_truth_baseline.json"


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


# Capture each renderSourceChip({...}) call body. We don't try to parse
# the JS object; we just grab the {...} block and then extract source: '...'.
CHIP_CALL_RE = re.compile(
    r"""renderSourceChip\s*\(\s*\{(?P<body>[^}]{0,2000})\}""",
    re.DOTALL,
)

SOURCE_FIELD_RE = re.compile(
    r"""\bsource\s*:\s*['"`](?P<txt>[^'"`]+)['"`]""",
)

# v_<name>_truth tokens inside the chip text
VIEW_TOKEN_RE = re.compile(r"\bv_[a-z0-9_]+_truth\b", re.IGNORECASE)

# Raw-table tokens the chip might name. Whitelisted set — we don't want to
# flag narrative words like "Open" as missing reads.
KNOWN_RAW_TOKENS = {
    "pm_completions", "pm_assets", "pm_scope_items", "logbook",
    "asset_nodes", "anomaly_signals", "amc_briefings", "automation_log",
    "failure_signature_alerts", "hive_audit_log", "shift_plans",
    "ai_reports", "skill_badges", "hive_benchmarks", "network_benchmarks",
    "marketplace_listings", "marketplace_orders", "marketplace_inquiries",
}

# .from('TABLE') call detection — also catches edge-fn invokes which look like
# `functions.invoke('NAME', ...)`. We don't pair invokes with chip text by name,
# but we'll allow chips that name an edge-fn read via the source-chip-allow marker.
FROM_RE = re.compile(
    r"""\.from\(\s*['"`](?P<name>[a-z_][\w]*)['"`]\s*\)""",
)

# Allow marker — within ±300 chars of the renderSourceChip call
ALLOW_RE = re.compile(r"source-chip-allow", re.IGNORECASE)

# Strip HTML/JS comments before scanning so a commented-out renderSourceChip
# example doesn't get parsed.
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
JS_LINE_RE      = re.compile(r"^[ \t]*//[^\n]*$", re.MULTILINE)


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def _scan_page(page: Path) -> list[dict]:
    try:
        raw = page.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    # Strip ONLY HTML comments — keep JS line comments visible so inline
    # `// source-chip-allow: ...` markers above renderSourceChip calls are
    # picked up by ALLOW_RE. Stripping JS line comments deleted them silently.
    body = HTML_COMMENT_RE.sub("", raw)

    # All .from() reads anywhere on the page.
    page_reads = {m.group("name").lower() for m in FROM_RE.finditer(body)}

    issues: list[dict] = []
    for m in CHIP_CALL_RE.finditer(body):
        chip_body = m.group("body")
        sm = SOURCE_FIELD_RE.search(chip_body)
        if not sm:
            continue
        src_text = sm.group("txt")

        # Allow marker within ±600 chars of the renderSourceChip call.
        # 600 captures the typical "block comment above function" placement
        # that the team uses (e.g. comment on line N, chip render on line N+5).
        win_start = max(0, m.start() - 600)
        win_end   = min(len(body), m.end() + 300)
        if ALLOW_RE.search(body[win_start:win_end]):
            continue

        # Extract claimed views.
        claimed_views = {v.lower() for v in VIEW_TOKEN_RE.findall(src_text)}
        # Also extract raw-table claims (only the curated set).
        claimed_raw = set()
        for tok in re.split(r"[\s+,/&]+", src_text):
            t = tok.strip().lower()
            if t in KNOWN_RAW_TOKENS:
                claimed_raw.add(t)

        all_claims = claimed_views | claimed_raw
        if not all_claims:
            # Narrative-only chip (no view/table names); ignore.
            continue

        missing = sorted(c for c in all_claims if c not in page_reads)
        if missing:
            issues.append({
                "source":      src_text[:120],
                "claimed":     sorted(all_claims),
                "missing":     missing,
                "char_offset": m.start(),
            })

    return issues


def main() -> int:
    per_page: list[dict] = []
    total_issues = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        issues = _scan_page(page)
        per_page.append({"page": name, "issues": issues})
        total_issues += len(issues)

    # Baseline ratchet
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("issues", 0)
        except Exception:
            baseline = 0
    else:
        baseline = total_issues
        BASELINE_PATH.write_text(
            json.dumps({"issues": baseline, "established": True}, indent=2),
            encoding="utf-8",
        )

    if total_issues < baseline:
        baseline = total_issues
        BASELINE_PATH.write_text(
            json.dumps({"issues": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    report = {
        "summary": {
            "pages_scanned":  len(per_page),
            "total_issues":   total_issues,
            "baseline":       baseline,
        },
        "per_page": per_page,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("Source-Chip Truth Validator (L0)"))
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  stale claims:     {total_issues}  (baseline: {baseline})")

    if total_issues == 0:
        print()
        print(_green("PASS — every renderSourceChip declaration is backed by a real .from() read."))
        return 0

    print()
    print("Stale source-chip claims (chip names a view the page never reads):")
    for p in per_page:
        if not p["issues"]:
            continue
        print(f"  {p['page']}")
        for i in p["issues"]:
            print(f"    source: {i['source'][:100]}")
            print(f"    missing reads: {', '.join(i['missing'])}")

    if total_issues > baseline:
        print()
        print(_red(f"FAIL — count {total_issues} > baseline {baseline} (new stale claim introduced)"))
        print("Fix options:")
        print("  1. Remove the now-unread view from the chip's source string.")
        print("  2. Restore the .from() read if the chip's claim is correct.")
        print("  3. Add `// source-chip-allow: <reason>` near the call to document.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
