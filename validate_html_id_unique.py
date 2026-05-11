"""
HTML ID Uniqueness Detector -- WorkHive Platform
=================================================
Catches duplicate `id="..."` attributes within the same HTML file.
`document.getElementById()` returns the FIRST match only — every later
duplicate is silently inert. The bug shape:

  <button id="save-btn">Save A</button>     <!-- only this one is reachable -->
  ...
  <button id="save-btn">Save B</button>     <!-- click handler never wires -->

The duplicate often arises from copy-paste templates, modal markup
duplicated across screens, or partial-include shared HTML fragments.

Layer 1 -- Duplicate id within the same file                           [FAIL]
  Any `id="xyz"` value that appears 2+ times in the same HTML file
  (excluding empty / template-literal IDs).

Layer 2 -- Duplicate id across LIVE pages                              [WARN]
  Same `id` used across N+ different production HTML files where the
  IDs are bound via shared event handlers — high risk of cross-page
  drift when one page renames the id but forgets the rest.

Layer 3 -- Per-page id density (informational)                         [INFO]
  Top files by distinct id count. Surfaces pages worth refactoring
  toward data-attributes or scoped DOM.

Layer 4 -- Reserved-name collisions (informational)                    [INFO]
  IDs that shadow window/document properties (`name`, `length`,
  `submit`, `body`, `head`) — JS `someEl.querySelector(...)` patterns
  can confuse these with the property accessor.

Skills consulted: frontend (DOM id semantics), qa-tester (silent
click-handler failures are a recurring bug class), mobile-maestro
(double-bound listeners on duplicate ids = double-fire on touch).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Per (path, id) exemptions. Each entry needs a one-line justification.
ID_DUPLICATE_OK: dict[tuple[str, str], str] = {
    # All 17 historical "duplicates" were RESOLVED on 2026-05-11 by
    # improving the validator's _strip_html_comments() to also strip
    # <script>...</script> blocks. Each duplicate was a JS string-template
    # literal that gets rendered into innerHTML/outerHTML, REPLACING the
    # existing DOM element. The live DOM only ever has one id at a time.
    # Allowlist intentionally left empty so any FUTURE static-HTML
    # duplicate is caught immediately.
}

# DOM properties that an id can shadow (window/document/element members).
RESERVED_DOM_NAMES = {
    "name", "length", "submit", "body", "head", "title", "form",
    "items", "options", "value", "src", "href", "id", "class",
    "innerHTML", "textContent",
}

# Match `id="..."` -- avoid matching `id="${...}"` template literals and
# javascript-generated ids that come from string concat. We capture only
# stable static ids.
ID_ATTR_RE = re.compile(
    r"""\bid\s*=\s*["'](?P<id>[a-zA-Z][a-zA-Z0-9_-]*)["']""",
)
# Template-literal id (contains `${...}`) — explicitly skip.
TEMPLATE_ID_RE = re.compile(r"""\bid\s*=\s*["'][^"']*\$\{""")


def list_html_pages() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    return out


def _strip_html_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    # Strip <script>...</script> blocks entirely. IDs that appear inside
    # JS source (in string literals being concatenated and later assigned
    # to innerHTML/outerHTML) live in dynamic templates that REPLACE the
    # existing DOM element when rendered. The live DOM only has one
    # element per id at any time. Only STATIC HTML duplicates outside
    # script blocks are real getElementById-returns-first bugs.
    src = re.sub(
        r"""<script\b[^>]*>[\s\S]*?</script>""",
        "", src, flags=re.IGNORECASE,
    )
    return src


def extract_ids(path: str) -> list[tuple[str, int]]:
    """Return [(id, line_no)] for every static id attribute in file."""
    src = read_file(path) or ""
    src = _strip_html_comments(src)
    out: list[tuple[str, int]] = []
    for m in ID_ATTR_RE.finditer(src):
        # Skip if this match is inside a template-literal context (rare but
        # possible). Heuristic: look at the 20 chars after id= to see if
        # there's a ${ between the quote and the value.
        seg = src[max(0, m.start() - 5):m.end() + 5]
        if "${" in seg and m.group("id") in seg.split("${")[0]:
            pass   # the id value itself is static; the surrounding ${} is benign
        line_no = src.count("\n", 0, m.start()) + 1
        out.append((m.group("id"), line_no))
    return out


# -- Layer 1: Duplicate id within the same file ---------------------------

def check_within_file(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in pages:
        ids = extract_ids(path)
        by_id: dict[str, list[int]] = defaultdict(list)
        for (id_val, line) in ids:
            by_id[id_val].append(line)
        for id_val, lines in by_id.items():
            if len(lines) < 2:
                continue
            if (path, id_val) in ID_DUPLICATE_OK:
                continue
            report.append({
                "path":     path,
                "id":       id_val,
                "n":        len(lines),
                "lines":    lines[:5],
            })
            issues.append({
                "check": "duplicate_id_within_file", "skip": False,
                "reason": (
                    f"{path}: id='{id_val}' appears {len(lines)} times "
                    f"(first lines: {lines[:5]}). getElementById('{id_val}') "
                    f"returns the FIRST element only — any click/event "
                    f"handler wired to the others never fires. Rename one, "
                    f"or list ({path}, '{id_val}') in ID_DUPLICATE_OK if "
                    f"the duplication is intentional."
                ),
            })
    return issues, report


# -- Layer 2: Same id across multiple pages -------------------------------

def check_cross_page_drift(pages: list[str]) -> tuple[list[dict], list[dict]]:
    """ids that appear in N+ different files. Not all duplicates are bad
    (header / nav / brand) but high-count ids that aren't part of a known
    shared component scaffold are drift candidates."""
    id_to_pages: dict[str, set[str]] = defaultdict(set)
    for path in pages:
        for (id_val, _line) in extract_ids(path):
            id_to_pages[id_val].add(path)
    THRESH = 5
    # IDs we know are intentionally shared via shared scripts (nav-hub.js,
    # floating-ai.js etc.). Filter these out -- they are by design.
    SHARED_OK = {
        # Nav hub injected on every page
        "wh-nav-hub-root", "wh-nav-hub", "wh-nav-hub-toggle",
        "wh-nav-hub-overlay", "wh-nav-hub-search",
        # Floating AI assistant
        "wh-ai-fab", "wh-ai-drawer", "wh-ai-messages",
        "wh-ai-input", "wh-ai-send", "wh-ai-close",
        # QR scanner
        "wh-qr-overlay", "wh-qr-video",
        # Toast container
        "wh-toast", "toast", "toast-container", "toast-text",
        # Page chrome
        "app", "root", "main", "header", "footer", "main-content",
        # Hive scoping gate (component duplicated across hive-scoped pages)
        "hive-gate",
        # Common search input pattern across list pages
        "search-input",
    }
    rows: list[dict] = []
    issues: list[dict] = []
    for id_val, paths in id_to_pages.items():
        if len(paths) < THRESH:
            continue
        if id_val in SHARED_OK:
            continue
        rows.append({
            "id":       id_val,
            "n_pages":  len(paths),
            "sample":   sorted(paths)[:5],
        })
        issues.append({
            "check": "cross_page_drift", "skip": True,
            "reason": (
                f"id='{id_val}' appears in {len(paths)} different pages "
                f"({sorted(paths)[:3]}...). If this is a shared widget id, "
                f"add it to SHARED_OK. Otherwise rename to a page-prefixed "
                f"or data-attribute pattern to avoid drift when one page "
                f"renames it."
            ),
        })
    return issues, rows


# -- Layer 3: Per-page id density (informational) -------------------------

def check_density(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        ids = extract_ids(path)
        if not ids:
            continue
        rows.append({
            "path":      path,
            "n_total":   len(ids),
            "n_unique":  len(set(i for i, _ in ids)),
        })
    rows.sort(key=lambda r: -r["n_total"])
    return [], rows


# -- Layer 4: Reserved-name collisions (informational) -------------------

def check_reserved_names(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        for (id_val, line) in extract_ids(path):
            if id_val not in RESERVED_DOM_NAMES:
                continue
            rows.append({
                "path": path, "id": id_val, "line": line,
            })
    return [], rows


# -- Runner --------------------------------------------------------------

CHECK_NAMES = [
    "duplicate_id_within_file",
    "cross_page_drift",
    "density",
    "reserved_names",
]
CHECK_LABELS = {
    "duplicate_id_within_file": "L1  No duplicate id within the same HTML file                  [FAIL]",
    "cross_page_drift":         "L2  Same id used in 5+ different pages (or in SHARED_OK)        [WARN]",
    "density":                  "L3  Per-page id density (informational)                        [INFO]",
    "reserved_names":           "L4  IDs that shadow DOM/window names (informational)            [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nHTML ID Uniqueness Detector (4-layer)"))
    print("=" * 60)

    pages = list_html_pages()
    print(f"  {len(pages)} HTML page(s) scanned (ID_DUPLICATE_OK={len(ID_DUPLICATE_OK)}).\n")

    l1_issues, l1_report = check_within_file(pages)
    l2_issues, l2_report = check_cross_page_drift(pages)
    l3_issues, l3_report = check_density(pages)
    l4_issues, l4_report = check_reserved_names(pages)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('TOP ID-DENSITY PAGES (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            print(f"  {r['path']:<32}  total={r['n_total']:<4} unique={r['n_unique']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":            "html_id_unique",
        "total_checks":         total,
        "passed":               n_pass,
        "warned":               n_warn,
        "failed":               n_fail,
        "n_pages":              len(pages),
        "duplicate_within":     l1_report,
        "cross_page_drift":     l2_report,
        "density":              l3_report,
        "reserved_collisions":  l4_report,
        "issues":               [i for i in all_issues if not i.get("skip")],
        "warnings":             [i for i in all_issues if i.get("skip")],
    }
    with open("html_id_unique_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
