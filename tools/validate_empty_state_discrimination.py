#!/usr/bin/env python3
"""
validate_empty_state_discrimination.py - DEEPWALK D3 empty-state-vs-no-results discrimination gate (2026-07-22).
================================================================================================================
DEEPWALK FINDING #1 (live, logbook team-feed): a list render that owns BOTH a first-run "empty-state"
(the "No entries yet - log your first X" CTA) AND a search "no-results" ("nothing matched your filters")
must route a **0-result SEARCH** to no-results, NEVER to the first-run empty-state. The bug class:

  if (entries.length === 0) { show empty-state; return; }   // fires FIRST
  ...
  if (filtered.length === 0) { show no-results; return; }    // DEAD when filtered === entries

For a **server-filtered** view (the list variable IS the query result, so `filtered === entries`), a search
that returns 0 rows hits the first branch and shows the first-run empty-state - telling a supervisor who just
searched the whole TEAM feed "Log your first repair" (a nonsensical CTA; they aren't logging, they're
searching). Found + fixed live in logbook.html renderEntries (2026-07-22): the length-0 branch is now
view-aware (team -> no-results, mine -> empty-state).

Client-filtered views (inventory: `filtered = items.filter(...)`) are CORRECT - `items` is the full set
(true-empty -> empty-state) and `filtered` is a proper subset (0 matches -> no-results), so both branches
are reachable and distinct. Those are NOT in scope; only server-filtered search views can collapse.

THIS GATE locks the invariant on the curated server-filtered search surfaces: the FIRST `.length === 0`
branch in the named render function must be view/search-aware (carry a view discriminator AND route the
searched-0 case to the no-results element). Adding a new server-filtered search view is a conscious UX
decision that must extend the curated list. Static (reads the HTML source); `--selftest` proves teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_empty_state_discrimination"]
ROOT = Path(__file__).resolve().parent.parent

# page -> (render-fn name, first-run-empty-state elem-id, no-results elem-id, filter/view-discriminator token).
# Each is a SERVER-FILTERED search view whose 0-result render must reach a no-match message, NOT the first-run
# CTA. Two valid discrimination shapes: (a) a two-element toggle (logbook: routes to the #no-results element);
# (b) an inline filter-active check that renders a "no ... match" message (marketplace: _filterActive + text).
SERVER_FILTERED_VIEWS = {
    "logbook.html":     ("renderEntries",  "empty-state", "no-results", "_viewMode"),
    "marketplace.html": ("renderListings", "empty-state", "no-results", "_filterActive"),
}


def _render_body(src: str, fn: str) -> str | None:
    """Return the source of function `fn` (brace-balanced from its opening '{'), or None."""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(fn) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    i = src.index("{", m.start())
    depth, j = 0, i
    while j < len(src):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return None


def _first_zero_branch(body: str) -> str | None:
    """The block guarded by the FIRST empty-list check (`X.length === 0` OR `!X.length`), brace-balanced
    from its opening `{` to the matching `}` (robust to any comment length inside the branch)."""
    m = re.search(r"if\s*\(\s*(?:!\s*\w+\.length|\w+\.length\s*===?\s*0)\s*\)\s*\{", body)
    if not m:
        return None
    i = body.index("{", m.start())
    depth, j = 0, i
    while j < len(body):
        if body[j] == "{":
            depth += 1
        elif body[j] == "}":
            depth -= 1
            if depth == 0:
                return body[m.start():j + 1]
        j += 1
    return body[m.start():m.start() + 1200]  # fallback: unbalanced source


def _branch_is_discriminated(branch: str, no_results_id: str, discriminator: str) -> bool:
    """The searched-0 branch must carry the filter/view discriminator AND route to a no-MATCH outcome —
    EITHER a #no-results element toggle OR an inline 'no ... match (your search/filter)' message."""
    routes_no_results = bool(
        re.search(r"(noResults?|noRes)\b[^\n]*remove\(\s*['\"]hidden['\"]\s*\)", branch)
        or re.search(r"getElementById\(\s*['\"]" + re.escape(no_results_id) + r"['\"]\s*\)[^\n]*remove\(\s*['\"]hidden['\"]", branch)
        or re.search(r"no\s+\w+\s+match|match\s+(those\s+)?(filter|search)|match\s+your\s+(search|filter)", branch, re.IGNORECASE)
    )
    has_discriminator = discriminator in branch
    return routes_no_results and has_discriminator


def _check_page(page: str, fn: str, empty_id: str, nr_id: str, disc: str) -> tuple[bool, str]:
    p = ROOT / page
    if not p.exists():
        return True, f"SKIP  {page} (absent)"
    src = p.read_text(encoding="utf-8", errors="replace")
    body = _render_body(src, fn)
    if body is None:
        return False, f"FAIL  {page}:{fn}() not found - render fn renamed? re-point the gate."
    branch = _first_zero_branch(body)
    if branch is None:
        return False, f"FAIL  {page}:{fn}() has no `.length === 0` guard - structure changed."
    if _branch_is_discriminated(branch, nr_id, disc):
        return True, f"PASS  {page}:{fn}() - searched-0 branch is view-aware (routes to #{nr_id})."
    return False, (f"FAIL  {page}:{fn}() - the first `.length === 0` branch shows the first-run "
                   f"#{empty_id} unconditionally; a 0-result SEARCH must route to #{nr_id} "
                   f"(missing `{disc}` discriminator). DEEPWALK D3 regression.")


def self_test() -> bool:
    ok = True
    pre_fix = ("if (entries.length === 0) { list.innerHTML=''; "
               "empty.classList.remove('hidden'); noResults.classList.add('hidden'); return; }")
    post_fix = ("if (entries.length === 0) { list.innerHTML=''; if (_viewMode === 'team') { "
                "empty.classList.add('hidden'); noResults.classList.remove('hidden'); } else { "
                "empty.classList.remove('hidden'); noResults.classList.add('hidden'); } return; }")
    # inline (marketplace) shape: `!X.length` + a filter-active discriminator + a "no ... match" message
    inline_post = ("if (!_listings.length) { const _filterActive = _query || _cat!=='All'; "
                   "if (_filterActive) { grid.innerHTML='<h3>No listings match those filters</h3>'; return; } "
                   "grid.innerHTML='No spare parts listed yet be the first to sell'; return; }")
    inline_pre = ("if (!_listings.length) { const cfg = emptyConfig[_section]; "
                  "grid.innerHTML='No spare parts listed yet be the first to sell'; return; }")
    if _branch_is_discriminated(_first_zero_branch(pre_fix), "no-results", "_viewMode"):
        print(f"{R}self-test FAIL: pre-fix (unconditional empty-state) wrongly PASSED.{X}"); ok = False
    if not _branch_is_discriminated(_first_zero_branch(post_fix), "no-results", "_viewMode"):
        print(f"{R}self-test FAIL: post-fix (view-aware) wrongly FAILED.{X}"); ok = False
    if not _branch_is_discriminated(_first_zero_branch(inline_post), "no-results", "_filterActive"):
        print(f"{R}self-test FAIL: inline post-fix (filter-aware message) wrongly FAILED.{X}"); ok = False
    if _branch_is_discriminated(_first_zero_branch(inline_pre), "no-results", "_filterActive"):
        print(f"{R}self-test FAIL: inline pre-fix (first-run CTA, no discriminator) wrongly PASSED.{X}"); ok = False
    if not SERVER_FILTERED_VIEWS:
        print(f"{R}self-test FAIL: curated view list empty.{X}"); ok = False
    print((G + "self-test PASS - empty-state-discrimination check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}DEEPWALK D3 gate: a 0-result SEARCH must show no-results, not the first-run empty-state CTA{X}")
    fails = []
    for page, (fn, empty_id, nr_id, disc) in sorted(SERVER_FILTERED_VIEWS.items()):
        good, msg = _check_page(page, fn, empty_id, nr_id, disc)
        print(f"  {(G+'PASS'+X) if good and msg.startswith('PASS') else (msg[:6])}  {msg[6:]}"
              if msg[:4] in ("PASS", "SKIP") else f"  {R}{msg}{X}")
        if not good:
            fails.append(page)
    if fails:
        print(f"{R}FAIL: {len(fails)} server-filtered search view(s) collapse a 0-result search into the "
              f"first-run empty-state.{X}")
        return 1
    print(f"{G}PASS - every curated server-filtered search view routes a 0-result search to no-results.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
