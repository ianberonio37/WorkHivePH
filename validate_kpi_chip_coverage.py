"""
KPI Chip Coverage Validator -- WorkHive Platform Guardian
=========================================================
Companion gate to validate_canonical_sources.py and Phase 3.1 (the
renderSourceChip helper in utils.js). When a page reads any KPI canonical
view -- v_risk_truth, v_pm_compliance_truth, v_logbook_truth,
v_inventory_items_truth, or v_asset_truth -- it MUST also render a source/
window chip somewhere visible, so the driver knows which gauge they are
looking at (the metaphor in KPI_ENGINE.md).

Without a chip, two pages can show the same metric label with different
numbers and the user has no way to know they're reading different windows.
This is exactly the "feels off" failure mode the 2026-05-12 audit surfaced.

One layer, one rule:

L1 -- Chip coverage (FAIL)
  Every HTML page that reads at least one v_*_truth canonical view via
  .from('v_<name>_truth').select(...) must also contain one of:
    (a) a `renderSourceChip(...)` call (the canonical helper from utils.js)
    (b) a `<p class="wh-source-chip">` element (manually rendered chip)
    (c) an inline `// chip-allow: <reason>` comment near the .from() call
        documenting why no chip is needed (e.g. the page is a write-only
        editor that happens to also read its own table for autocomplete).

Pre-existing pages without chips are listed in KNOWN_NO_CHIP with a TODO so
the gate can ratchet down as each page gets a chip. The list shrinks over
time; new pages outside the list FAIL immediately.

Skills consulted: analytics-engineer (one chart, one insight; KPI label
discipline), frontend (shared helper pattern), KPI_ENGINE.md rules 2 and 3.
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# -- Paths -------------------------------------------------------------------

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# The canonical KPI views. A page that reads any of these is reporting a
# canonical metric and needs a source/window chip somewhere.
KPI_VIEWS = {
    "v_risk_truth",
    "v_pm_compliance_truth",
    "v_logbook_truth",
    "v_inventory_items_truth",
    "v_asset_truth",
}

# Pre-existing pages that read KPI views but don't yet have a chip. Each
# entry is documented debt scheduled for a chip; remove when the page
# ships its chip via renderSourceChip(). New pages outside this set FAIL.
#
# Forward-slash path keys so the set works on Windows and Linux.
KNOWN_NO_CHIP: set[str] = set()  # cleared 2026-05-12 in the everything-at-once
                                  # revamp batch -- every remaining KPI-reading
                                  # page either has a real chip or carries an
                                  # inline `chip-allow:` comment documenting why.

# Inline opt-out: `<!-- chip-allow: reason -->` or `// chip-allow: reason`
# within the file documents that a chip is intentionally absent.
CHIP_ALLOW_TOKEN = "chip-allow:"

# Detect KPI canonical view reads -- same shape the canonical-sources
# validator uses but narrower (only the 5 KPI views above).
FROM_KPI_VIEW_RE = re.compile(
    r"\.from\(\s*['\"](?P<view>v_(?:risk|pm_compliance|logbook|inventory_items|asset)_truth)['\"]\s*\)"
)

# Detect chip presence: helper call, manual chip class, or any of the
# pre-Phase-3.1 inline-styled <p> blocks. The third form lets pages that
# already had a static chip pass before they migrate to the helper.
HAS_CHIP_RE = re.compile(
    r"renderSourceChip\(|"
    r"class=['\"](?:[^'\"]*\s)?wh-source-chip(?:\s[^'\"]*)?['\"]|"
    r"id=['\"]wh-source-chip['\"]",
)


CHECK_NAMES  = ["chip_coverage"]
CHECK_LABELS = {
    "chip_coverage": "L1  Every page reading a KPI canonical view also renders a source/window chip [FAIL]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nKPI Chip Coverage Validator (1-layer)"))
    print("=" * 60)

    html_files = []
    for path in sorted(glob.glob("*.html")):
        if any(path.endswith(ex) for ex in EXCLUDED_HTML_PATTERNS):
            continue
        html_files.append(path)

    print(f"  {len(html_files)} HTML files scanned, "
          f"{len(KPI_VIEWS)} KPI views tracked.\n")

    issues  = []
    report  = []
    chipped = []
    no_chip = []
    no_kpi  = []
    debt    = []

    for path in html_files:
        content = read_file(path) or ""
        if not content:
            continue

        kpi_reads = FROM_KPI_VIEW_RE.findall(content)
        if not kpi_reads:
            no_kpi.append({"path": path})
            continue

        # Inline file-level opt-out: chip-allow anywhere in the file.
        if CHIP_ALLOW_TOKEN in content:
            chipped.append({
                "path":      path,
                "kpi_views": sorted(set(kpi_reads)),
                "kind":      "inline_allowed",
            })
            continue

        has_chip = HAS_CHIP_RE.search(content) is not None

        if has_chip:
            chipped.append({
                "path":      path,
                "kpi_views": sorted(set(kpi_reads)),
                "kind":      "has_chip",
            })
        elif path in KNOWN_NO_CHIP:
            debt.append({
                "path":      path,
                "kpi_views": sorted(set(kpi_reads)),
                "kind":      "known_debt",
            })
        else:
            no_chip.append({
                "path":      path,
                "kpi_views": sorted(set(kpi_reads)),
            })
            issues.append({
                "check":  "chip_coverage",
                "reason": (
                    f"{path} reads KPI view(s) {sorted(set(kpi_reads))} but has no "
                    f"source/window chip. Add `renderSourceChip({{ source, freshness, "
                    f"window }})` to the page's init script (helper lives in utils.js), "
                    f"or add `{path}` to KNOWN_NO_CHIP with a TODO, or place a "
                    f"`<!-- {CHIP_ALLOW_TOKEN} <reason> -->` comment in the file "
                    f"if a chip is intentionally absent."
                ),
            })

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print(f"\n{bold('CHIP COVERAGE SUMMARY')}")
    print("  " + "-" * 56)
    print(f"  pages reading KPI views:       {len(chipped) + len(debt) + len(no_chip)}")
    print(f"  pages with chip:               {len(chipped)}")
    print(f"  pages on KNOWN_NO_CHIP debt:   {len(debt)}")
    print(f"  pages MISSING chip (FAIL):     {len(no_chip)}")
    print(f"  pages without KPI reads:       {len(no_kpi)}")

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "kpi_chip_coverage",
        "total_checks": len(CHECK_NAMES),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "n_files":      len(html_files),
        "n_kpi_views":  len(KPI_VIEWS),
        "chipped":      chipped,
        "known_debt":   debt,
        "missing":      no_chip,
        "no_kpi":       no_kpi,
        "issues":       [i for i in issues if not i.get("skip")],
        "warnings":     [i for i in issues if i.get("skip")],
    }
    with open("kpi_chip_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
