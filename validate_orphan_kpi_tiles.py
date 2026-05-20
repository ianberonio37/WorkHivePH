"""
Orphan KPI Tile Validator (L0, ratcheted).
==========================================
Catches the class of bug we surfaced on 2026-05-20:

  - `marketplace.html` declares `<div id="mk-total-hero">0</div>` and
    `<div id="mk-mine-hero">0</div>` but no JS ever sets them — the tile
    visibly says "0" on every page load forever.
  - `skillmatrix.html` declares `sm-ontrack-hero`, `sm-quizzes-hero`,
    `sm-badges-hero` — same pattern, never set.

These look correct (the design system places the tile, the initial
value reads as a real zero) but the data flow is broken. The home tile
fix on 2026-05-20 was the same root class: a number rendered to the
user that was structurally disconnected from the data.

Detection
  1. Scan every page in the canonical 30-page inventory.
  2. Find every KPI-style element: id matches one of the conventional
     KPI prefixes (`stat-`, `pulse-`, `kpi-`, `*-hero`, `count-`,
     `*-num`, etc.) AND initial text content is a default placeholder
     ("0", "—", "-", "Loading...", whitespace, or empty).
  3. For each, scan the SAME FILE for setter calls — any of:
       document.getElementById('ID').{textContent|innerHTML|value} =
       querySelector('#ID')
       document.getElementById('PREFIX' + dynamic + 'SUFFIX')  ← detected
                                                                  by the dynamic
                                                                  helper pattern
                                                                  below
  4. If no setter is found, the tile is ORPHAN. Either:
       (a) wire it up to real data,
       (b) remove the dead element, or
       (c) allowlist with reason via `data-orphan-allow="reason"`.

Allow markers
  Add `data-orphan-allow="<reason>"` on the element to document an
  intentional always-zero / always-placeholder tile (rare — usually
  a design choice for a coming-soon section).

Forward-only baseline
  `orphan_kpi_tiles_baseline.json` locks the count at first clean run.
  New orphans push above the baseline and fail; resolved ones tighten.

Exit codes
  0 if orphan_count <= baseline
  1 otherwise
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
REPORT_PATH   = ROOT / "orphan_kpi_tiles_report.json"
BASELINE_PATH = ROOT / "orphan_kpi_tiles_baseline.json"


# User-confirmed 30-page canonical inventory (2026-05-20). The 31 includes
# voice-journal (separate from voice-handler.js).
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


# KPI-style id prefixes/suffixes the team uses across the codebase.
# An id matching ANY of these AND showing a default-state initial value
# is a candidate for orphan detection.
KPI_ID_PATTERNS = [
    re.compile(r"^stat-[\w-]+$"),
    re.compile(r"^pulse-[\w-]+$"),
    re.compile(r"^kpi-[\w-]+$"),
    re.compile(r"^count-[\w-]+$"),
    re.compile(r"^[\w]+-hero$"),
    re.compile(r"^[\w]+-num$"),
    re.compile(r"^ah-[\w-]+-(hero|sub|tag|count)$"),
    re.compile(r"^sb-[\w-]+-(hero|sub|tag|count)$"),
    re.compile(r"^sm-[\w-]+-(hero|sub|tag|count)$"),
    re.compile(r"^mk-[\w-]+-(hero|sub|tag|count)$"),
    re.compile(r"^pr-[\w-]+-(hero|sub|tag|count)$"),
    re.compile(r"^inv-[\w-]+-(hero|sub|tag|count)$"),
    re.compile(r"^ph-[\w-]+-(hero|sub|tag|count)$"),
]

# What counts as a default/placeholder initial value:
DEFAULT_VALUES = {"", "0", "-", "—", "–", "—", "Loading...", "Loading…", "...", "…"}
DEFAULT_RE = re.compile(r"^\s*(0|-|—|–|—|\.\.\.|…|Loading\.\.\.|Loading…)?\s*$")


# Strip HTML comments from text before scanning — never a real declaration.
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")

# Match `<tag ... id="X" ...>CONTENT</tag>` — captures id + content.
# We require the tag to have an opening + closing on the same scope (no
# nested children) so we don't grab containers with rich content.
ELEMENT_RE = re.compile(
    r"""<(?P<tag>[a-z][\w-]*)
        \s+[^>]*\bid\s*=\s*['"](?P<id>[a-z][\w-]*)['"]
        [^>]*>
        (?P<content>[^<]{0,80})
        </(?P=tag)>""",
    re.VERBOSE | re.IGNORECASE,
)

# Allow markers — element has data-orphan-allow="<reason>"
ALLOW_RE_TEMPLATE = lambda id_: re.compile(
    r"""id\s*=\s*['"]""" + re.escape(id_) + r"""['"][^>]*data-orphan-allow\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


def _id_is_kpi(id_: str) -> bool:
    return any(pat.match(id_) for pat in KPI_ID_PATTERNS)


def _is_default_value(content: str) -> bool:
    # Strip whitespace + HTML entity-escapes; treat &#8212; (em-dash) and
    # &mdash; as default placeholders.
    cleaned = content.strip()
    cleaned = cleaned.replace("&#8212;", "—").replace("&mdash;", "—")
    cleaned = cleaned.replace("&ndash;", "–").replace("&nbsp;", " ")
    cleaned = cleaned.strip()
    return bool(DEFAULT_RE.match(cleaned))


def _scan_page(page_path: Path) -> tuple[list[dict], list[dict]]:
    """Returns (orphans, allowlisted)."""
    try:
        raw = page_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [], []
    # Strip HTML comments so a commented-out template doesn't count.
    body = HTML_COMMENT_RE.sub("", raw)

    orphans: list[dict] = []
    allowlisted: list[dict] = []
    seen_ids: set[str] = set()

    for m in ELEMENT_RE.finditer(body):
        id_ = m.group("id")
        if id_ in seen_ids:
            continue
        seen_ids.add(id_)
        if not _id_is_kpi(id_):
            continue
        content = m.group("content")
        if not _is_default_value(content):
            continue

        # Check for allow marker on the raw (un-comment-stripped) element.
        allow_m = ALLOW_RE_TEMPLATE(id_).search(raw)
        if allow_m:
            allowlisted.append({"id": id_, "reason": allow_m.group(1)})
            continue

        # Look for setters in the same file.
        # Direct: getElementById('ID')
        direct = re.search(
            r"""(?:getElementById|querySelector|querySelectorAll)\s*\(\s*['"`]#?""" + re.escape(id_) + r"""['"`]\s*\)""",
            body,
        )
        if direct:
            continue

        # Dynamic: `getElementById('prefix-' + name + '-suffix')`.
        # We accept this as a real setter ONLY when the specific stem segment
        # also appears as a string literal in the file (e.g. `setCard('total', ...)`
        # or `'total'` passed somewhere in the same scope). Without that, the
        # dynamic helper exists but never fires for THIS id — the tile is still
        # orphan. Caught marketplace 'mk-total-hero' / 'mk-mine-hero' which a
        # generic dynamic-helper match was hiding.
        dyn_setter = False
        for tail in ("hero", "sub", "tag", "count", "num"):
            if not id_.endswith("-" + tail):
                continue
            stem = id_[: -(len(tail) + 1)]
            last_dash = stem.rfind("-")
            if last_dash <= 0:
                continue
            prefix  = stem[:last_dash + 1]                # e.g. "mk-"
            segment = stem[last_dash + 1:]                # e.g. "total"
            dyn_pat = re.compile(
                r"""(?:getElementById|querySelector)\s*\(\s*['"`]""" +
                re.escape(prefix) + r"""['"`]\s*\+[^)]*['"`]\-""" + re.escape(tail) + r"""['"`]""",
            )
            if not dyn_pat.search(body):
                continue
            # Require the segment to appear specifically as a FIRST string
            # argument in a function call (e.g. `setCard('total', ...)` /
            # `dispatch('total', ...)`) — that's how the dynamic helper
            # actually gets fired for this segment. Mere occurrence of
            # the literal (in a comment, HTML, console.log) isn't enough.
            seg_call = re.compile(
                r"""\b\w+\s*\(\s*['"`]""" + re.escape(segment) + r"""['"`]\s*,""",
            )
            if seg_call.search(body):
                dyn_setter = True
                break

        if dyn_setter:
            continue

        # No setter — orphan
        orphans.append({
            "id":      id_,
            "default": content.strip(),
        })

    return orphans, allowlisted


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def main() -> int:
    per_page: list[dict] = []
    total_orphans = 0
    total_allowlisted = 0
    total_pages_with_orphans = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        orphans, allowlisted = _scan_page(page)
        per_page.append({
            "page":        name,
            "orphans":     orphans,
            "allowlisted": allowlisted,
        })
        total_orphans     += len(orphans)
        total_allowlisted += len(allowlisted)
        if orphans:
            total_pages_with_orphans += 1

    # Baseline ratchet (forward-only)
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("orphans", 0)
        except Exception:
            baseline = 0
    else:
        baseline = total_orphans
        BASELINE_PATH.write_text(
            json.dumps({"orphans": baseline, "established": True}, indent=2),
            encoding="utf-8",
        )

    if total_orphans < baseline:
        baseline = total_orphans
        BASELINE_PATH.write_text(
            json.dumps({"orphans": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    report = {
        "summary": {
            "pages_scanned":           len(per_page),
            "pages_with_orphans":      total_pages_with_orphans,
            "total_orphans":           total_orphans,
            "total_allowlisted":       total_allowlisted,
            "baseline":                baseline,
        },
        "per_page": per_page,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Console
    print()
    print(_bold("Orphan KPI Tile Validator (L0)"))
    print("=" * 56)
    print(f"  pages scanned:       {len(per_page)}")
    print(f"  pages with orphans:  {total_pages_with_orphans}")
    print(f"  orphans found:       {total_orphans}  (baseline: {baseline})")
    print(f"  allowlisted tiles:   {total_allowlisted}")

    if total_orphans == 0:
        print()
        print(_green("PASS — every KPI tile is wired (or allowed with reason)."))
        return 0

    print()
    print("Orphan tiles by page:")
    for entry in per_page:
        if not entry["orphans"]:
            continue
        print(f"  {entry['page']}")
        for o in entry["orphans"]:
            print(f"    #{o['id']:<35}  initial={o['default'] or '(empty)'!r}")

    if total_orphans > baseline:
        print()
        print(_red(f"FAIL — orphan count {total_orphans} > baseline {baseline}"))
        print("Fix options:")
        print("  1. Wire the tile to real data (add a getElementById setter).")
        print("  2. Remove the dead element from HTML.")
        print("  3. Add data-orphan-allow=\"<reason>\" to keep it as a placeholder.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
