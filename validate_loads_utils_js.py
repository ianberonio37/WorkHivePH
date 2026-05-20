"""
Loads-Utils-JS Validator -- WorkHive Platform
==============================================
First validator graduated from L-1 Convention Mining (the edge_pattern +
html_pattern miners under tools/). Enforces an implicit rule the codebase
already follows at 86% conformance: every production HTML page must load
`utils.js`.

Why utils.js matters:
  - escHtml(): the single defence against XSS when rendering user-supplied
    data. A page that interpolates `${user.name}` into innerHTML without
    escHtml is a real XSS hole.
  - Shared Supabase singleton (`window.workhiveSupabase`): pages that
    call `createClient()` directly create a SECOND GoTrueClient and break
    session sync (auth state drifts between the two clients).
  - Identity helpers (getWorkerName, getHiveId, fetchWithTimeout).

Any page that renders data from the DB or talks to auth needs utils.js.
Pure brochure/docs pages that do neither are legitimate exceptions and
ride on the ALLOWLIST below.

Promotion source: tools/mine_html_patterns.py surfaced this as the
86%-conformance candidate. The 5 outliers were each reviewed and
ALLOWLISTED rather than fixed in this commit -- the validator is the
contract that says "stop the drift HERE; new pages must comply."

Layer 1 -- every non-allowlisted root HTML page loads utils.js     [FAIL]
  A `<script src="utils.js">` tag (defer / type=module / leading slash
  variants all accepted) must appear somewhere in the file.

Layer 2 -- allowlist freshness check                               [WARN]
  Any page on the allowlist that has since started loading utils.js
  should be removed from the allowlist (graduation -- the convention
  tightens automatically as outliers come into compliance).

Layer 3 -- allowlist drift census                                  [INFO]
  Per-allowlist-entry status line so the deferred-debt count is visible
  every Mega Gate run.

Skills consulted: security (escHtml as XSS defence, singleton pattern),
frontend (utils.js shared identity helpers, script load order),
qa-tester (allowlist pattern + graduation gate).
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import format_result


ROOT = Path(__file__).resolve().parent

# Same scope as the miner -- root HTML, excluding backups + test pages.
EXCLUDE_PATTERNS = [
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"-test\.html$"),
]


# Pages exempt from the rule. Each entry is annotated with the reason
# so future readers (and future-you on graduation review) understand why
# it's here. Graduate a page OFF this list by deleting its line once it
# starts loading utils.js.
ALLOWLIST: dict[str, str] = {
    "architecture.html":     "static architecture brochure -- no DB calls, no user-data rendering",
    "symbol-gallery.html":   "static reference page (drawing symbols only)",
    "parts-tracker.html":    "RETIRED STUB (2026-05-18 review) -- 38-line redirect page to inventory.html#usage-history. No DB, no user data, no script rendering. <meta refresh> + setTimeout JS redirect. SAFE.",
    # analytics-report.html GRADUATED 2026-05-18: now loads utils.js after removing inline escHtml.
    # platform-health.html   GRADUATED 2026-05-18: now loads utils.js after removing inline escHtml.
}


SCRIPT_RE = re.compile(
    r"""<script\b[^>]*\bsrc=["'][^"']*\butils\.js\b""",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _list_pages() -> list[Path]:
    pages = []
    for p in sorted(ROOT.glob("*.html")):
        if not p.is_file():
            continue
        if any(rx.search(p.name) for rx in EXCLUDE_PATTERNS):
            continue
        pages.append(p)
    return pages


def _loads_utils(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8", errors="replace")
    # Strip HTML comments so commented-out <script> tags don't count.
    code = COMMENT_RE.sub("", raw)
    return bool(SCRIPT_RE.search(code))


def check_pages():
    """L1 + L2: pages must load utils.js OR be on the allowlist; allowlist
    entries that already comply should be graduated off."""
    issues = []
    census = {"required": [], "allowlisted_violating": [],
              "allowlisted_graduated": [], "allowlisted_compliant_still_listed": []}

    for path in _list_pages():
        name = path.name
        ok = _loads_utils(path)
        on_allowlist = name in ALLOWLIST

        if ok:
            if on_allowlist:
                # Graduated -- still on allowlist but no longer needs to be.
                census["allowlisted_graduated"].append(name)
                issues.append({
                    "check":  "allowlist_freshness",
                    "skip":   True,  # WARN, not FAIL
                    "reason": (
                        f"{name} now loads utils.js -- remove from ALLOWLIST "
                        f"(graduation: the convention tightens automatically)."
                    ),
                })
            else:
                census["required"].append(name)
        else:
            if on_allowlist:
                census["allowlisted_violating"].append(name)
            else:
                issues.append({
                    "check":  "loads_utils_js",
                    "reason": (
                        f"{name} does not load utils.js. "
                        f"Add `<script src=\"utils.js\"></script>` before the page "
                        f"renders data, or add to ALLOWLIST with a documented "
                        f"reason if this page is genuinely brochure-only."
                    ),
                })

    return issues, census


CHECK_NAMES  = ["loads_utils_js", "allowlist_freshness"]
CHECK_LABELS = {
    "loads_utils_js":      "L1  Every non-allowlisted root HTML page loads utils.js",
    "allowlist_freshness": "L2  Allowlist entries that already comply should be graduated off",
}


def main() -> int:
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nLoads-Utils-JS Validator"))
    print("=" * 55)

    pages = _list_pages()
    issues, census = check_pages()
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    # L3 informational census
    print("\nAllowlist census:")
    print(f"  scoped pages:              {len(pages)}")
    print(f"  required-and-compliant:    {len(census['required'])}")
    print(f"  allowlisted (still valid): {len(census['allowlisted_violating'])}")
    print(f"  allowlisted (graduate!):   {len(census['allowlisted_graduated'])}")

    if census["allowlisted_violating"]:
        print("\n  Active allowlist entries:")
        for name in census["allowlisted_violating"]:
            print(f"    - {name}  ({ALLOWLIST[name]})")

    report = {
        "summary": {
            "pages_scanned":           len(pages),
            "required_and_compliant":  len(census["required"]),
            "allowlisted_violating":   len(census["allowlisted_violating"]),
            "allowlisted_graduated":   len(census["allowlisted_graduated"]),
            "fail":                    n_fail,
            "skip":                    n_skip,
        },
        "allowlist":  ALLOWLIST,
        "census":     census,
        "issues":     issues,
    }
    (ROOT / "loads_utils_js_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    if n_fail == 0:
        print(f"\n\033[92m  PASS  ({n_pass}/{len(CHECK_NAMES)} checks across {len(pages)} pages)\033[0m")
        return 0
    print(f"\n\033[91m  FAIL  ({n_fail} issues)\033[0m")
    return 1


if __name__ == "__main__":
    sys.exit(main())
