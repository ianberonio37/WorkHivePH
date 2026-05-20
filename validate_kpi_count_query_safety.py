"""
KPI Count-Query Safety Validator (L0, ratcheted).
==================================================
Catches the class caught 2026-05-20 on `index.html` home tiles:

  - Page does `db.from('v_logbook_truth').select(...).limit(5)`.
  - Then renders `jobs.length` as the KPI tile number.
  - If there are >5 open jobs, the tile silently undercounts to 5.

This pattern is hard to spot in code review because the LIMIT looks
intentional ("show top 5 in the list") and the `.length` rendering
looks correct ("count of items I have"). The bug only shows up at
the boundary — when actual data exceeds the limit.

Detection heuristic
  1. Scan each .html / .js page for blocks of the shape:
       `await db.from(<table>).select(...).limit(N) ... .data ...
        const arr = ...; ... arr.length ...`
     within a small window (≤2500 chars).
  2. Then check whether the same `arr` (or its length) is rendered to
     a KPI-style element via `.textContent` / `tile.num` / `setCard(...)`.

Because exact AST tracking is hard, we use a coarser regex:

  - LIMIT_SELECT_RE: matches `db.from('NAME').select(...).limit(N)`.
    Captures the table name (must be `v_*_truth` to focus on canonical
    surfaces — raw-table fetches with limit are usually paginated lists
    where local .length IS the right count for the page).
  - LENGTH_AS_COUNT_RE: matches `<var>.length` appearing as a numeric
    KPI value: in `.textContent = <var>.length`, `{ num: <var>.length }`,
    `(<var>.length)` next to a known KPI selector update.

Output
  kpi_count_query_safety_report.json (machine)
  Exit 1 when issues > baseline; 0 otherwise.

Allow markers
  Add an inline `// limit-as-count-allow: <reason>` comment within
  ~120 chars of the offending `.limit()` to document an intentional
  truncated count (e.g. "show up to 5 latest, count is best-effort").
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
REPORT_PATH   = ROOT / "kpi_count_query_safety_report.json"
BASELINE_PATH = ROOT / "kpi_count_query_safety_baseline.json"


# Canonical 30-page inventory + shared JS modules that render KPI tiles.
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


# Match `db.from('v_X_truth').select(...).limit(N)` with the chain potentially
# spanning multiple lines.
LIMIT_SELECT_RE = re.compile(
    r"""\.from\(\s*['"`](?P<view>v_[a-z0-9_]+_truth)['"`]\s*\)"""
    r"""(?:[^;]{0,500})?\.limit\(\s*(?P<n>\d+)\s*\)""",
    re.DOTALL | re.IGNORECASE,
)

# Allow marker — `// limit-as-count-allow: ...` close to the .limit() call.
ALLOW_RE = re.compile(r"limit-as-count-allow", re.IGNORECASE)

# Match `<var>.length` used as a numeric KPI value. The signature patterns:
#   `<var>.length` inside `{ num: ... }` / `textContent = ...` / inside
#   a `tiles = [ ... ]` declaration line that we later render.
LENGTH_KPI_PATTERNS = [
    # `{ num: jobs.length, ... }` — tile array shape used by index.html ops-home
    re.compile(r"""\{\s*[^}]*\bnum\s*:\s*(?P<var>\w+)\.length\b"""),
    # `textContent = <var>.length`
    re.compile(r"""\.textContent\s*=\s*(?P<var>\w+)\.length\b"""),
    # `innerHTML = ... ${<var>.length} ...`
    re.compile(r"""\.innerHTML\s*=[^;]*\$\{[^}]*\b(?P<var>\w+)\.length\b"""),
    # Direct assignment in `let X = <var>.length` followed by KPI-style render
    # is harder to track; skip for now.
]


def _strip_html_comments(t: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", t)


def _strip_js_line_comments(t: str) -> str:
    return re.sub(r"^[ \t]*//[^\n]*$", "", t, flags=re.MULTILINE)


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def _scan(name: str, body_raw: str) -> list[dict]:
    """Return list of issues for this page."""
    body = _strip_js_line_comments(_strip_html_comments(body_raw))
    issues: list[dict] = []

    for lm in LIMIT_SELECT_RE.finditer(body):
        view = lm.group("view")
        n    = int(lm.group("n"))

        # Look for allow marker within ±300 chars (covers the comment-on-line-above pattern).
        window_start = max(0, lm.start() - 300)
        window_end   = min(len(body_raw), lm.end() + 300)
        if ALLOW_RE.search(body_raw[window_start:window_end]):
            continue

        # Scan a window AFTER the .limit() call to find the variable that
        # holds the result and check if its .length is rendered as a KPI.
        tail_start = lm.end()
        tail_end   = min(len(body), lm.end() + 4000)
        tail = body[tail_start:tail_end]

        # Try each KPI-length pattern; if any matches, flag.
        hits = []
        for pat in LENGTH_KPI_PATTERNS:
            for m in pat.finditer(tail):
                hits.append({
                    "var":     m.group("var"),
                    "shape":   pat.pattern[:40] + "...",
                })

        if hits:
            issues.append({
                "view":       view,
                "limit_n":    n,
                "hits":       hits[:3],
                "char_offset": lm.start(),
            })

    return issues


def main() -> int:
    per_page = []
    total_issues = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        body = page.read_text(encoding="utf-8", errors="replace")
        issues = _scan(name, body)
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
    print(_bold("KPI Count-Query Safety Validator (L0)"))
    print("=" * 56)
    print(f"  pages scanned:     {len(per_page)}")
    print(f"  issues found:      {total_issues}  (baseline: {baseline})")

    if total_issues == 0:
        print()
        print(_green("PASS — no `.limit(N) + .length` count-rendering pattern detected on _truth views."))
        return 0

    print()
    print("Issues (limit-then-length as KPI count):")
    for p in per_page:
        if not p["issues"]:
            continue
        print(f"  {p['page']}")
        for i in p["issues"]:
            shapes = ", ".join(f"{h['var']}.length" for h in i["hits"])
            print(f"    {i['view']}  limit({i['limit_n']})  →  {shapes}")

    if total_issues > baseline:
        print()
        print(_red(f"FAIL — count {total_issues} > baseline {baseline} (new limit-as-count introduced)"))
        print("Fix options:")
        print("  1. Add a head-only count query alongside the detail .limit() call.")
        print("  2. Drop the .limit() if you actually need the full count.")
        print("  3. Add `// limit-as-count-allow: <reason>` if the truncated count is intentional.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
