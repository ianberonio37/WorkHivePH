#!/usr/bin/env python3
"""
spec_route_sw_gate — a route interception on a service-worker-controlled page measures NOTHING.

THE DEFECT THIS EXISTS TO STOP, twice paid for now.

`page.route()` does not intercept requests issued by a service worker. nav-hub.js registers
sw.js with scope '/', and sw.js calls `clients.claim()`, so every WorkHive page in a Playwright
context is controlled the moment one of them loads. A spec that then routes a read gets ZERO
interceptions -- and, because the page is behaving perfectly, whatever the spec asserts next is
measured against an un-injected page.

That failure is silent in both directions:

  - marketplace-state-inducers (2026, first occurrence) reported the PAGE as broken for 25
    seconds of polling while the listings grid was full and correct. Proven by running the
    identical abort with and without the block: 0 interceptions and a full grid, versus 25
    interceptions and the correct "Couldn't load listings ... Retry" state.
  - failure-injection (second occurrence) reported 41 of 43 tests failing. Every one landed on
    that spec's own "the route never matched -- instrument failure" guard, so no oracle beneath
    it ever ran. Measured on a healthy marketplace load: page.on('request') counted 62 supabase
    reads while page.route counted 0, with navigator.serviceWorker.controller truthy.

The first occurrence was fixed correctly and scoped to one file. Nothing carried the lesson to
the other four specs that intercept routes, so the second occurrence cost a full 30-minute run
and very nearly got 41 fabricated product defects banked. This gate is that carry.

WHY BLOCKING IS FAITHFUL AND NOT A CONVENIENCE. sw.js answers API traffic with a plain
pass-through (`url.includes('supabase.co')` -> `fetch(e.request)`), and its only cache write is
`cache.addAll(SHELL_FILES)` at install. No API or REST response is ever served from its cache,
so a page with the worker blocked receives byte-identical responses. Blocking removes the
interception blind spot without changing what the surface under test is answered with.

THE RULE. A spec is IN SCOPE when it both intercepts routes and drives a WorkHive page (a
`/workhive/` URL, or the `whPage` fixture, which signs in through workhive/index.html and is
therefore always controlled). An in-scope spec must declare `test.use({ serviceWorkers: 'block' })`.

Out of scope, deliberately: specs that route against another origin. journey-notebooklm.spec.ts
drives the Flask video-marketing dashboard on port 5001, which registers no worker -- sweeping it
in would have been a blind fix, and the check is written so it stays out on the evidence rather
than on a hand-maintained allowlist.

ESCAPE HATCH. A spec that genuinely exercises the service worker cannot block it. Such a file
declares, on its own line:

    // sw-route-exempt: <why this spec must keep the worker alive>

An exemption with no reason after the colon is rejected, because "exempt" with nothing behind it
is how a gate stops biting.

Usage:
    python tools/spec_route_sw_gate.py                 # gate; exit 1 on a violation
    python tools/spec_route_sw_gate.py --self-test     # teeth
    python tools/spec_route_sw_gate.py --json          # report only
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(ROOT, "tests")
REPORT = os.path.join(ROOT, "spec_route_sw_report.json")

# `.route(` on ANY receiver. The first draft required the receiver's name to contain page/context/
# ctx, which matches both receivers in the suite today (46 `page.`, 21 `whPage.`) and would quietly
# stop matching the day someone adds a fixture called `buyerTab` or `sellerView`. Binding a check to
# a NAMING CONVENTION is how a gate goes silent without failing. In a Playwright spec `.route(` is
# Page/BrowserContext interception and nothing else, so the receiver carries no information worth
# depending on; a false positive costs one `serviceWorkers: 'block'` line or one exemption.
ROUTE_RE = re.compile(r"\.\s*route\s*\(")

# Evidence the spec drives a WorkHive page, and is therefore under a claiming service worker.
WORKHIVE_URL_RE = re.compile(r"['\"`][^'\"`]*/workhive/[^'\"`]*['\"`]")
WHPAGE_FIXTURE_RE = re.compile(r"\bwhPage\b")

BLOCK_RE = re.compile(r"serviceWorkers\s*:\s*['\"]block['\"]")
# `\s` matches a newline, so a lazy `\s*(?P<reason>.*)` after the colon happily skipped the line
# break and adopted the NEXT line as the reason -- which made a bare `// sw-route-exempt:` read as
# a fully-reasoned exemption. Caught by the teeth case, not by the run. Stay on one line.
EXEMPT_RE = re.compile(r"//[ \t]*sw-route-exempt[ \t]*:[ \t]*(?P<reason>[^\r\n]*)")


_STRIPPER = None


def _code_only(src: str) -> str:
    """The source with comments removed, because a gate that greps prose grades prose.

    This gate said "blocked" about a file whose only `serviceWorkers: 'block'` was inside the very
    comment explaining why it does NOT block -- I wrote that comment and the gate believed it. Same
    failure the T-arc refusal census hit when it credited inventory.html with four refusal states
    that were every one a source comment. The stripper is validate_live_mcp_bank's, not a second
    copy: it already survived the case this house style keeps producing, a prose sentence that
    names the call it is describing.
    """
    global _STRIPPER
    if _STRIPPER is None:
        spec = importlib.util.spec_from_file_location(
            "_vlmb_strip", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _STRIPPER = mod._strip_js_comments
    return _STRIPPER(src)


def analyze(src: str) -> dict:
    """Classify one spec's source. Pure: no filesystem, so the self-test can feed it strings."""
    code = _code_only(src)
    routes = len(ROUTE_RE.findall(code))
    workhive_urls = len(WORKHIVE_URL_RE.findall(code))
    uses_whpage = bool(WHPAGE_FIXTURE_RE.search(code))
    in_scope = routes > 0 and (workhive_urls > 0 or uses_whpage)

    blocks = bool(BLOCK_RE.search(code))
    # The exemption is DECLARED in a comment by design, so it alone is read from the raw source.
    m = EXEMPT_RE.search(src)
    reason = (m.group("reason").strip() if m else "")
    # An exemption marker with an empty reason is not an exemption.
    exempt = bool(m and reason)

    if not in_scope:
        status = "out-of-scope"
    elif blocks:
        status = "blocked"
    elif exempt:
        status = "exempt"
    else:
        status = "VIOLATION"

    return {
        "routes": routes,
        "workhive_urls": workhive_urls,
        "uses_whpage": uses_whpage,
        "in_scope": in_scope,
        "blocks": blocks,
        "exempt": exempt,
        "exempt_reason": reason,
        "status": status,
    }


def _spec_files() -> list:
    """Every spec Playwright would run. It walks, because playwright.config.ts says
    `testMatch: '**/*.spec.ts'` under `testDir: './tests'` -- a flat os.listdir would agree with
    that only by luck. Today all 161 specs sit at the top level and tests/bank_probes/ holds none,
    so the first spec added one directory down would have been invisible to this gate while being
    perfectly visible to the runner. A checker that scans a narrower set than the thing it checks
    reports a green it did not earn."""
    out = []
    for dirpath, _dirnames, filenames in os.walk(TESTS_DIR):
        for name in filenames:
            if name.endswith(".spec.ts"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def scan() -> dict:
    rows = []
    for path in (_spec_files() if os.path.isdir(TESTS_DIR) else []):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        row = analyze(src)
        rel = os.path.relpath(path, TESTS_DIR).replace(os.sep, "/")
        row["file"] = "tests/" + rel
        rows.append(row)

    violations = [r for r in rows if r["status"] == "VIOLATION"]
    return {
        "scanned": len(rows),
        "in_scope": sum(1 for r in rows if r["in_scope"]),
        "blocked": sum(1 for r in rows if r["status"] == "blocked"),
        "exempt": sum(1 for r in rows if r["status"] == "exempt"),
        "violations": violations,
        "rows": rows,
        "ok": not violations,
    }


# ── teeth ────────────────────────────────────────────────────────────────────────────────────
# Every case is a source string the gate must classify a stated way. The point is not that the
# gate runs; it is that it says NO to the exact shape that shipped twice, and does not say no to
# the shapes that are legitimately fine.
_CASES = [
    (
        "the real second occurrence: routes a workhive page, no block",
        "import { test } from './_fixtures';\n"
        "test('x', async ({ whPage }) => { await whPage.route(/rest/, r => r.fulfill({})); });\n",
        "VIOLATION",
    ),
    (
        "same spec once fixed",
        "import { test } from './_fixtures';\n"
        "test.use({ serviceWorkers: 'block' });\n"
        "test('x', async ({ whPage }) => { await whPage.route(/rest/, r => r.fulfill({})); });\n",
        "blocked",
    ),
    (
        "a /workhive/ url is enough on its own, without the fixture",
        "test('x', async ({ page }) => {\n"
        "  await page.goto('/workhive/marketplace.html');\n"
        "  await page.route('**/maplibre-gl.js', r => r.abort());\n"
        "});\n",
        "VIOLATION",
    ),
    (
        "journey-notebooklm's shape: routes, but another origin and no workhive page",
        "test('x', async ({ page }) => {\n"
        "  await page.goto('/');\n"
        "  await page.route('**/api/notebooklm/doctor', r => r.fulfill({}));\n"
        "});\n",
        "out-of-scope",
    ),
    (
        "a workhive spec that never routes is not this gate's business",
        "test('x', async ({ whPage }) => { await whPage.goto('/workhive/index.html'); });\n",
        "out-of-scope",
    ),
    (
        "an exemption with a stated reason is honoured",
        "// sw-route-exempt: this spec asserts the offline shell, so the worker must live\n"
        "test('x', async ({ whPage }) => { await whPage.route(/rest/, r => r.abort()); });\n",
        "exempt",
    ),
    (
        "an exemption with no reason is not an exemption",
        "// sw-route-exempt:\n"
        "test('x', async ({ whPage }) => { await whPage.route(/rest/, r => r.abort()); });\n",
        "VIOLATION",
    ),
    (
        "context.route counts too -- the blind spot is not page-specific",
        "test('x', async ({ context, whPage }) => { await context.route(/rest/, r => r.abort()); });\n",
        "VIOLATION",
    ),
    (
        "a block mentioned only in PROSE is not a block — the real sim-map case",
        "// four specs were swept onto `test.use({ serviceWorkers: 'block' })` because of it, but\n"
        "// this one intercepts a vendored script and does not need it.\n"
        "test('x', async ({ whPage }) => { await whPage.route(/maplibre/, r => r.abort()); });\n",
        "VIOLATION",
    ),
    (
        "the same file once it declares the exemption properly",
        "// sw-route-exempt: the one intercept is a vendored script and fires with the worker alive\n"
        "// four specs were swept onto `test.use({ serviceWorkers: 'block' })`, this one is not one.\n"
        "test('x', async ({ whPage }) => { await whPage.route(/maplibre/, r => r.abort()); });\n",
        "exempt",
    ),
    (
        "a .route( that only appears inside a comment is not an interception",
        "// the older draft called whPage.route(/rest/, ...) here and it matched nothing\n"
        "test('x', async ({ whPage }) => { await whPage.goto('/workhive/index.html'); });\n",
        "out-of-scope",
    ),
    (
        "a fixture named nothing like 'page' still intercepts, and still counts",
        "test('x', async ({ buyerTab }) => {\n"
        "  await buyerTab.goto('/workhive/marketplace.html');\n"
        "  await buyerTab.route(/rest/, r => r.abort());\n"
        "});\n",
        "VIOLATION",
    ),
]


def self_test() -> int:
    failed = 0
    for label, src, expected in _CASES:
        got = analyze(src)["status"]
        ok = got == expected
        failed += (not ok)
        print("  %s  %-62s expected=%-13s got=%s" % ("ok  " if ok else "FAIL", label[:62], expected, got))

    # The gate must also survive a real directory read. Point it at a temp tests/ dir holding one
    # known-bad file and confirm scan() surfaces it, so a refactor that breaks the file walk
    # cannot pass on the string cases alone.
    global TESTS_DIR
    saved = TESTS_DIR
    bad = "test('x', async ({ whPage }) => { await whPage.route(/rest/, r => r.abort()); });\n"
    try:
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "temp.spec.ts"), "w", encoding="utf-8") as fh:
                fh.write(bad)
            TESTS_DIR = td
            res = scan()
        ok = (not res["ok"]) and len(res["violations"]) == 1
        failed += (not ok)
        print("  %s  scan() reads a directory and reports the violation" % ("ok  " if ok else "FAIL"))

        # Playwright's testMatch is '**/*.spec.ts', so a spec one directory down is a spec it runs.
        # A flat listdir passed the case above and would have missed this one entirely.
        with tempfile.TemporaryDirectory() as td:
            sub = os.path.join(td, "bank_probes")
            os.makedirs(sub)
            with open(os.path.join(sub, "nested.spec.ts"), "w", encoding="utf-8") as fh:
                fh.write(bad)
            TESTS_DIR = td
            res = scan()
        ok = (not res["ok"]) and res["violations"][0]["file"] == "tests/bank_probes/nested.spec.ts"
        failed += (not ok)
        print("  %s  a spec in a SUBDIRECTORY is scanned, as Playwright's testMatch would"
              % ("ok  " if ok else "FAIL"))
    finally:
        TESTS_DIR = saved

    print("\n%s  %d case(s) failed" % ("FAIL" if failed else "PASS", failed))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="run the teeth cases and exit")
    ap.add_argument("--json", action="store_true", help="print the report and always exit 0")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    res = scan()
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)

    print("spec_route_sw: %d spec(s) scanned, %d in scope, %d blocked, %d exempt"
          % (res["scanned"], res["in_scope"], res["blocked"], res["exempt"]))
    for r in res["rows"]:
        if r["in_scope"]:
            print("   %-11s %-46s routes=%d" % (r["status"], r["file"], r["routes"]))

    if args.json:
        return 0

    if res["violations"]:
        print("\nFAIL: a route interception on a service-worker-controlled page matches nothing,")
        print("so whatever these specs assert next is measured against an un-injected page:")
        for r in res["violations"]:
            print("   %s  (%d route interception(s))" % (r["file"], r["routes"]))
        print("\nAdd `test.use({ serviceWorkers: 'block' });` below the imports, or, if the spec")
        print("genuinely needs the worker alive, `// sw-route-exempt: <reason>`.")
        return 1

    print("\nPASS: every route-intercepting WorkHive spec blocks the service worker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
