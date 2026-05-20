"""
Filter Case / Enum Consistency Validator (L0, ratcheted).
==========================================================
Catches the class where two surfaces filter the same column with
DIFFERENT case or spelling, producing different counts from the same
canonical view:

  hive.html      → .eq('status', 'Open')
  inventory.html → .eq('status', 'open')       ← lower-case; misses Open rows

Or worse — text-typo drift:

  predictive.html → .in('risk_level', ['critical', 'high'])
  alert-hub.html  → .in('risk_level', ['Critical', 'High'])   ← capitalized

Postgres `.eq()` is case-sensitive on text columns; one of the two
returns zero rows even though the column is populated.

Detection
  1. Scan every page + edge fn for these Supabase query-builder filters:
       .eq('COL', 'VALUE')          single value
       .neq('COL', 'VALUE')         negated
       .in('COL', [...])            array — extract each literal
  2. Group by `(COL, lowercase(VALUE))`. If the same column+lowercase pair
     has MULTIPLE distinct case/spelling variants used by 2+ files →
     DRIFT.
  3. Single-file variants are fine (a page can intentionally check both
     'Open' and 'In Progress' separately).

Output
  filter_case_consistency_report.json
  Exit 1 when drift count > baseline; 0 otherwise.

Allow markers
  Inline `// filter-case-allow: <reason>` near the filter call. Use for
  legitimate case-mixing (e.g. a migration tolerance period where both
  values coexist by design).
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "filter_case_consistency_report.json"
BASELINE_PATH = ROOT / "filter_case_consistency_baseline.json"


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


# `.eq('COL', 'VALUE')` or `.eq("COL", "VALUE")` — only string literals.
EQ_RE = re.compile(
    r"""\.(?:eq|neq)\(\s*['"`](?P<col>[a-z_][\w]*)['"`]\s*,\s*['"`](?P<val>[^'"`]+)['"`]\s*\)""",
)

# `.in('COL', [...])` — capture column + the array literal text.
IN_RE = re.compile(
    r"""\.in\(\s*['"`](?P<col>[a-z_][\w]*)['"`]\s*,\s*\[(?P<arr>[^\]]+)\]\s*\)""",
)

# Pull each string literal from an array-body capture.
ARR_LIT_RE = re.compile(r"""['"`]([^'"`]+)['"`]""")

# Allow marker
ALLOW_RE = re.compile(r"filter-case-allow", re.IGNORECASE)

HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Columns we deliberately track. Filtering by other column names (uuid,
# email, free-text) where case differences are intentional shouldn't be
# flagged. Curated to enum-like columns.
ENUM_COLUMNS = {
    "status", "section", "kind", "level", "risk_level", "severity",
    "category", "tone", "criticality", "role", "tier",
    "type", "asset_type", "report_type", "frequency", "shift_type",
    "delivery_method", "approval_state",
}


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def _gather_files() -> dict[str, str]:
    """Return {filename: body} for all 30 pages + edge fns."""
    blobs: dict[str, str] = {}
    for name in PAGES:
        p = ROOT / name
        if p.exists():
            blobs[name] = HTML_COMMENT_RE.sub("", p.read_text(encoding="utf-8", errors="replace"))
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            rel = ts.relative_to(ROOT).as_posix()
            blobs[rel] = ts.read_text(encoding="utf-8", errors="replace")
    return blobs


# Sentinel binding: name the L2 test `test('filter_case_consistency: ...')` for coverage credit.
CHECK_NAMES = ["filter_case_consistency"]


def main() -> int:
    blobs = _gather_files()

    # (col, lowercase value) -> { variant_value -> set(filenames) }
    # We compare lowercase to detect case drift; keep variant for the report.
    occurrences: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for fname, body in blobs.items():
        # .eq() / .neq() — single string literal
        for m in EQ_RE.finditer(body):
            col = m.group("col").lower()
            if col not in ENUM_COLUMNS:
                continue
            val = m.group("val")
            # Skip allow-marked sites — check window around the match
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win):
                continue
            occurrences[(col, val.lower())][val].add(fname)

        # .in() — array of string literals
        for m in IN_RE.finditer(body):
            col = m.group("col").lower()
            if col not in ENUM_COLUMNS:
                continue
            arr_body = m.group("arr")
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win):
                continue
            for vm in ARR_LIT_RE.finditer(arr_body):
                val = vm.group(1)
                occurrences[(col, val.lower())][val].add(fname)

    # Now detect drift: same (col, lowercase) but multiple variant cases
    # appearing in 2+ distinct files.
    drift: list[dict] = []
    for (col, lower_val), variants in occurrences.items():
        if len(variants) < 2:
            continue
        # Multiple cases must each appear in DIFFERENT files (so an
        # in-file legitimate distinction isn't flagged).
        files_per_variant = {v: sorted(files) for v, files in variants.items()}
        distinct_files = {f for fs in variants.values() for f in fs}
        if len(distinct_files) < 2:
            continue
        drift.append({
            "column":        col,
            "lower_value":   lower_val,
            "variants":      files_per_variant,
        })

    drift.sort(key=lambda x: (x["column"], x["lower_value"]))

    # Baseline ratchet
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("issues", 0)
        except Exception:
            baseline = 0
    else:
        baseline = len(drift)
        BASELINE_PATH.write_text(
            json.dumps({"issues": baseline, "established": True}, indent=2),
            encoding="utf-8",
        )

    if len(drift) < baseline:
        baseline = len(drift)
        BASELINE_PATH.write_text(
            json.dumps({"issues": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    report = {
        "summary": {
            "files_scanned":  len(blobs),
            "enum_columns":   sorted(ENUM_COLUMNS),
            "drift_count":    len(drift),
            "baseline":       baseline,
        },
        "drift": drift,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("Filter Case Consistency Validator (L0)"))
    print("=" * 56)
    print(f"  files scanned:   {len(blobs)}")
    print(f"  drift items:     {len(drift)}  (baseline: {baseline})")

    if not drift:
        print()
        print(_green("PASS — every enum-column filter uses consistent case across files."))
        return 0

    print()
    print("Drift candidates (same column + lowercase value, different case across files):")
    for d in drift[:30]:
        print(f"  {d['column']} = '{d['lower_value']}'")
        for variant, files in d["variants"].items():
            print(f"    '{variant}' → {', '.join(files[:5])}{'...' if len(files) > 5 else ''}")

    if len(drift) > baseline:
        print()
        print(_red(f"FAIL — count {len(drift)} > baseline {baseline}"))
        print("Fix options:")
        print("  1. Normalize all callers to one case (the DB schema's canonical value).")
        print("  2. Migrate the DB column to be case-insensitive (citext) — if so, add allow.")
        print("  3. Add `// filter-case-allow: <reason>` near the call.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
