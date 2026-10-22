"""validate_long_list_render.py - SL LB3 (2026-10-21): every list on the LB3 pages stays responsive with a thousand rows
in it.

Measured with a thousand rows behind every list (the LB3 walk answers each list read from a pool of 1,000 rows built
from the cast's own rows - phone-390 with the CPU slowed 4x, and desktop-1280): the logbook's Load More rebuilt EVERY card
on every press, so reaching 1,000 entries took 49 presses that each re-rendered everything - 920 ms a press on a desktop,
2.4 s at phone speed. The same shape sat under eleven "show more" handlers on ten pages: a count raised by N, then a
render of the whole list. Inventory's press re-ran the whole page (the stats, a datalist of every part number, a
re-sort); pm-scheduler's re-enriched every asset's PM items; the seller, admin, asset and audit lists bound their buttons
again on every render. Four searches re-rendered their list in the keystroke's own task.

STATIC  R1 utils.js whRenderRows appends a grown list, patches a few changed rows in place and replaces anything else
           (tools/test_wh_render_rows.mjs, 21 cases), and the shared style block carries its off-screen rule
           (.wh-rows-cv>*{content-visibility:auto...});
        R2 every "show more" handler on the LB3 pages - a count raised by N (or a page constant), then a render - reaches
           a render that goes through whRenderRows, never a rebuild of every row;
        R3 a render that calls whRenderRows binds listeners only to rows not bound yet (:not([data-wh-bound])) or
           delegates: a row an append kept on screen must not be bound a second time (one tap, two actions);
        R4 a search or filter box whose typing re-renders a list is debounced (debounce(...) or a setTimeout) - the
           keystroke paints at once, the list follows when the typing pauses;
        R5 an LB3 page with no database read builds no list from data - it fetches nothing but utils.js and its
           translation files - or is declared in STATIC_DECLARED with the list's source and why it cannot reach a
           thousand;
        R6 the page-guide chip's control scan (learn-link.js pageControls, on every page and every list change) passes
           over rows the browser is skipping - checkVisibility({contentVisibilityAuto: true}) - before it reads any
           rect: reading one inside a skipped row lays that row out, which made report-sender's 500 contacts one 2.1 s
           task and cost the logbook 10 s of a thousand-row walk (CPU-profiled at 390, 2026-10-21);
        R7 utils.js whFmtDate keeps one formatter per locale and options instead of building one per date
           (toLocaleString): a thousand-row list draws two or three dates a row;
        R8 the guide chip never drives itself: its observer skips the chip's own style writes, its instant check
           (hideIfOccluding) tests the chip at its current lift by asking only what is under it - never pageControls()
           or dialogUp() - and sync() measures from the remembered box instead of showing the chip to measure it
           (measured live: 360 style writes in 3 s of a page at rest, then 0);
        R9 the chip's full pass (every control and dialog on the page) runs at most once per SYNC_GAP (>= 200 ms):
           leave at once, return at leisure;
        R10 utils.js markIn reads anything inside a long list (.wh-rows-cv) by its textContent, and never asks
           checkVisibility: a row the browser is not drawing has no innerText, so every figure below the first screen
           of a long list was never made tappable (measured on inventory at 390: 2 of 8 quantities marked, then 20 of
           20), and asking whether a row is skipped computes that row's styles (4.9 s of a thousand-part walk);
        R11 utils.js's overlay Back-dismiss observer answers only an overlay's own class change, and learn-link.js drops
           its remembered controls only when an ELEMENT outside a list is inserted or removed: both answered every class
           change or rewritten label on the page with a query of the whole document (1.4 s and 3.8 s of the walk);
        R12 the Sources area's observer counts an attribute change only on an element that holds one of its carriers,
           anchors or slots, or on a fixed control at the foot of the screen (BOTTOM): every class or style change on the
           page - a thousand figures marked, a card restyled under a passing pointer - queued its layout-reading pass;
        R13 the guide chip's instant check runs after the frame's own layout (a ResizeObserver on the chip) and asks only
           about the elements just inserted - one rect per long-list row - never hit-testing the page; a scroll queues the
           full pass and settles it at once on scrollend; the control scan leaves out the controls inside dialogs
           (traced at 390: the hit tests forced a layout of each insertion and walked a thousand rows, 119 + 54 ms of one
           logbook Load More press);
        R14 a row drawn through whRenderRows runs no animation of its own each time the list draws it - only a row
           marked as just arrived (.new-entry) moves (every logbook and inventory card slid in on every render: ~245 ms
           of rendering per 20-card append at phone speed, ~26 ms without).
        R15 every box that searches or filters - however it is named, and whatever its handler does - runs its inline
           handler after the typing pauses (a debounced function, a named wrapper of one, or a body that defers itself):
           R4 read a box by its id and a handler by what it re-renders, and analytics' list filters had no id and only
           hid rows - each keystroke read every row's text and laid out every match, 472 ms to paint with a thousand
           rows at 390 (CPU 4x slower).
        R16 the Sources area's room below is sampled when the fixed controls change, not on every pass: clearBottom keeps
           its sample by window and column (needAt), the observer drops it when a control at the foot of the screen
           changes (bottomChanged), and the area coming within reach runs only the room pass (roomSoon) - each Load More
           press scrolled the list's end into view and brought the area back, 21 hit tests through a thousand rows'
           layers and two queries over the whole document each time (2.6 s + 1.3 s of an 82-press inventory walk); each
           sample asks elementFromPoint for the top element (the stack walked every row's layer), and the guide chip
           moving itself is not a change at the foot of the screen.
        R17 a row drawn through whRenderRows carries no HTML comment in its template: a comment is one more node in
           every row, parsed, kept and traced by the collector - inventory's part card carried three (~1.5 KB of notes a
           card), and around each press the browser's collections were the longest tasks; notes live as JS comments.
           The scan follows a row builder the call passes or calls by name (project-manager's pcardHtml carried a
           note R17 never read), taking each builder's extent from comment-blanked source.
        R18 only a row the browser is drawing is a scroll anchor: the long-list rows are out of the anchor choice
           (overflow-anchor:none) and utils.js marks the rows the browser starts drawing (a contentvisibilityautostatechange
           listener setting the data-wh-drawn ATTRIBUTE - every page's observer answers class changes) and lets those
           back in. With every row in, the browser walked a thousand rows to pick its anchor on each frame that changed
           layout (logbook presses 208/256/192 ms to paint at 390, CPU 4x; 152/176/136 with the rows out; the choice
           alone at the foot of 920 rows 6.6 ms against 3.7 at full speed); with every row out, the list itself is the
           anchor and a row above the screen 300 px taller moved the screen 300 px (0 with the drawn rows in).
        R19 the shared chrome's quarter-second passes run after the paint, not before it: learn-link.js runFull hands the
           guide chip's full pass from its frame callback to a task (33-41 ms of each press at phone speed ran inside the
           press's own frame), and nav-hub.js runs every pass but a dialog's the same way (afterPaint; 14-16 ms a press).
        R20 a row's hidden part is drawn when it is shown, not on every press: the day planner's open-item card draws its
           body (the problem, its badges, "+ Place on Schedule") only for the SELECTED card, and the card's key carries
           the selection so a tap redraws it with its body. Every "Show more" press parsed fifty cards' hidden bodies:
           23-54 ms of the click at 390 with the CPU 4x slower (6-8 ms without), and the thousand cards held 14,584
           elements (9,584 without).
        R21 a list whose rows are REPLACED, never edited in place, keeps each row's key with the row: whRenderRows'
           immutable option keeps the default key in a WeakMap, and the logbook - whose entries change only by
           replacement (a spread of the old entry, the offline copy, the edit) - sets it and writes no listed entry in
           place. Each Load More re-serialised every entry it had drawn, and its slowest press at 390 (CPU 4x) held a
           19 ms major collection inside the click.
SELF-TEST (--self-test): each check broken in a copy of a real file (or on a synthetic page appended to one), each
        caught; the clean run is green.

    python tools/validate_long_list_render.py [--self-test]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    # reconfigure in place: a NEW wrapper here closes the one a gate importing this module made (its old wrapper is
    # dropped and collected, closing the shared buffer - "I/O operation on closed file")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_PAGES = ["achievements.html", "agentic-rag-observability.html", "ai-quality.html", "alert-hub.html",
              "analytics-report.html", "analytics.html", "asset-hub.html", "assistant.html", "audit-log.html",
              "community.html", "dayplanner.html", "feedback/index.html", "founder-console.html", "hive.html", "index.html",
              "integrations.html", "inventory.html", "llm-observability.html", "logbook.html", "marketplace-admin.html",
              "marketplace-seller-profile.html", "marketplace-seller.html", "marketplace.html", "ph-intelligence.html",
              "plant-connections.html", "platform-actions.html", "pm-scheduler.html", "project-manager.html",
              "project-report.html", "public-feed.html", "report-sender.html", "resume.html", "shift-brain.html",
              "skillmatrix.html"]
STATIC_PAGES = ["about/index.html", "design-system.html", "learn/index.html", "privacy-policy/index.html", "status.html",
                "terms-of-service/index.html"] + [
    "learn/" + s + "/index.html" for s in (
        "ai-companion-hezekiah-zaniah-personas", "ai-quality-and-roi-stage-2-plants", "ai-work-assistant-maintenance-technicians",
        "best-free-cmms-software-philippines", "building-asset-register-zero-budget", "cmms-vs-excel-spreadsheet-maintenance",
        "connecting-workhive-to-sap-maximo-cmms", "dilo-wilo-day-planner-supervisors", "dole-iso-audit-trail-from-logbook",
        "free-engineering-calculators-philippine-plants", "free-pm-checklist-templates", "gamifying-maintenance-for-engagement",
        "industrial-community-of-practice-philippines", "industrial-marketplace-philippine-specialists",
        "joining-and-growing-your-hive", "maintenance-metrics-reliability-guide", "maintenance-project-planning-template",
        "maintenance-shift-handover-template", "mtbf-vs-mttr-for-supervisors", "ph-industrial-benchmarks-intelligence",
        "ph-plant-compliance-guide", "philippine-plants-now-pay-the-highest-power-rates", "predictive-alert-thresholds-plants",
        "predictive-maintenance-on-a-budget-philippines", "reduce-unplanned-downtime-guide", "sensor-cmms-gateway-operations",
        "skill-matrix-for-maintenance-technicians", "spare-parts-inventory-philippine-plants",
        "start-digital-logbook-philippine-factory", "start-digital-maintenance-guide",
        "voice-to-text-maintenance-philippine-plant-floor", "what-is-oee-how-to-calculate",
        "what-is-workhive-complete-platform-guide", "workhive-ai-companion-complete-capabilities",
        "workhive-vs-maintainx-comparison", "workhive-vs-upkeep-free-cmms-comparison")]
# a static page that renders a list from a file the build ships: the source, and why it cannot reach a thousand rows
STATIC_DECLARED = {
    "design-system.html": ("design_component_registry.json", "component_adoption_baseline.json",
                           "api_component_registry.json", "api_adoption_baseline.json",
                           "the UI and API component catalogues the build ships - only a build grows them"),
}
CSS_RULE = ".wh-rows-cv>*{content-visibility:auto;contain-intrinsic-size:auto"
NOT_CALLS = {"if", "for", "while", "switch", "return", "catch", "function", "typeof", "new", "await", "async",
             "Math", "Number", "String", "Promise", "setTimeout", "clearTimeout", "requestAnimationFrame", "Array",
             "Object", "JSON", "Date", "Boolean", "parseInt", "parseFloat", "isNaN", "_t", "e", "escHtml", "escJsAttr"}
MORE = re.compile(r"\b([\w$]*(?:DisplayCount|Limit|Shown|_shown))\s*\+=\s*(\d+|[A-Z_][A-Z0-9_]*)\s*;")
# the other way a list grows: the next page is ACCUMULATED onto the rows already held (`_listings = append ? [..._listings,
# ...rows] : rows`, `x = x.concat(rows)`) and the list rendered again - the marketplace grid's keyset Load more
ACCUM = re.compile(r"\b([\w$]+)\s*=\s*(?:[\w$]+\s*\?\s*)?(?:\[\s*\.\.\.\s*\1\s*,|\1\s*\.concat\()")
# an append: whRenderRows, insertAdjacentHTML('beforeend') of the new rows, or new nodes appended (community's feed adds a
# stub per new post and renders it when it scrolls into view)
APPENDS = re.compile(r"whRenderRows\(|insertAdjacentHTML\(\s*['\"]beforeend['\"]|\.appendChild\(|\.append\(")


def blank_comments(src: str) -> str:
    out = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), out, flags=re.S)
    return re.sub(r"(^|[^:'\"\\])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), out)


def _block_end(src: str, i: int) -> int:
    """From i, the index of the '}' that closes the block i sits in (its depth-0 close)."""
    depth, j = 0, i
    while j < len(src):
        c = src[j]
        if c in "'\"`":
            q, j = c, j + 1
            while j < len(src) and src[j] != q:
                j += 2 if src[j] == "\\" else 1
        elif c == "{":
            depth += 1
        elif c == "}":
            if depth == 0:
                return j
            depth -= 1
        j += 1
    return len(src)


def fn_span(src: str, name: str) -> tuple[int, int] | None:
    """Where the body of the function `name` defined on the page sits (function name( / name = (...) => / name =
    function): (start, end) of its braces. Pass comment-blanked source - on the raw page an apostrophe in a comment
    reads as a string, and formatDate's braces ran on for 1,863 lines."""
    m = re.search(r"(?:\bfunction\s+" + re.escape(name) + r"\s*\(|\b" + re.escape(name)
                  + r"\s*=\s*(?:async\s*)?(?:function\b[^{]*|\([^)]*\)\s*=>\s*|[\w$]+\s*=>\s*))", src)
    if not m:
        return None
    k = src.find("{", m.end() - 1)
    if k < 0:
        return None
    return k, _block_end(src, k + 1) + 1


def fn_body(src: str, name: str) -> str | None:
    """The body of the function `name` defined on the page (function name( / name = (...) => / name = function)."""
    sp = fn_span(src, name)
    return src[sp[0]:sp[1]] if sp else None


def calls_in(text: str) -> list[str]:
    return [c for c in dict.fromkeys(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(", text)) if c not in NOT_CALLS]


def renders_list(body: str) -> bool:
    return "whRenderRows(" in body or bool(re.search(r"\.innerHTML\s*=\s*[^;]{0,300}\.map\(", body, re.S))


def check_helper(utils: str, test_src: str | None = None) -> list[str]:
    issues = []
    if CSS_RULE not in utils:
        issues.append("R1 utils.js no longer carries the off-screen rule for long lists (.wh-rows-cv>*{content-visibility:auto})")
    path = ROOT / "utils.js"
    tmp = None
    if test_src is not None:
        tmp = ROOT / ".tmp" / "lb3_utils_mutant.js"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(test_src, encoding="utf-8")
        path = tmp
    try:
        r = subprocess.run(["node", str(ROOT / "tools" / "test_wh_render_rows.mjs"), str(path)], capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        if r.returncode != 0:
            fails = [ln for ln in (r.stdout or "").splitlines() if ln.startswith("FAIL")]
            issues.append("R1 whRenderRows no longer appends a grown list and replaces anything else: "
                          + ("; ".join(fails[:3]) or (r.stderr or r.stdout).strip()[-200:]))
    except (OSError, subprocess.TimeoutExpired) as e:
        issues.append(f"R1 could not run tools/test_wh_render_rows.mjs: {e}")
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
    return issues


def check_page(page: str, raw: str) -> list[str]:
    src = blank_comments(raw)
    issues = []
    # R2: a "show more" handler - or a page of rows accumulated onto the ones held - reaches a render that appends
    # (whRenderRows, or insertAdjacentHTML('beforeend') of the new rows), never a rebuild of every row
    for m in list(MORE.finditer(src)) + list(ACCUM.finditer(src)):
        end = _block_end(src, m.end())
        if m.re is ACCUM:
            # an accumulation often sits in a try { } with the render after its catch: read to the function's end (two
            # blocks out at most, so the scan never wanders into the next function)
            end = _block_end(src, _block_end(src, end + 1) + 1) if end < len(src) else end
        tail = src[m.end():end]
        called = calls_in(tail)
        bodies = {c: fn_body(src, c) for c in called}
        rebuilds = [c for c, b in bodies.items() if b and renders_list(b) and not APPENDS.search(b)]
        if m.re is ACCUM and not rebuilds:
            continue   # the accumulated array is not rendered as a list here (an element sweep, a lookup)
        if not APPENDS.search(tail) and not any(b and APPENDS.search(b) for b in bodies.values()):
            line = src.count("\n", 0, m.start()) + 1
            how = f"raising {m.group(1)}" if m.re is MORE else f"accumulating the next page onto {m.group(1)}"
            issues.append(f"R2 {page}:{line} shows more by {how} and then rebuilding the whole list "
                          f"(it calls {', '.join(rebuilds or called) or 'nothing'}; none appends through whRenderRows)")
    # R3: after whRenderRows, per-row listeners bind only the rows not bound yet
    for m in re.finditer(r"whRenderRows\(", src):
        end = _block_end(src, m.end())
        tail = src[m.end():end]
        for q in re.finditer(r"querySelectorAll\(\s*(['\"`])(.*?)\1\s*\)\s*\.forEach\(", tail):
            cb_end = _block_end(tail, tail.find("{", q.end()) + 1) if tail.find("{", q.end()) >= 0 else q.end()
            if "addEventListener(" in tail[q.end():cb_end + 1] and ":not([data-wh-bound])" not in q.group(2):
                line = src.count("\n", 0, m.end() + q.start()) + 1
                issues.append(f"R3 {page}:{line} binds '{q.group(2)}' after an appending render without "
                              ":not([data-wh-bound]) - a row kept on screen is bound again, and one tap runs twice")
    # R14: a row drawn through whRenderRows runs no animation of its own each time the list draws it - only a row marked
    # as just arrived (.new-entry) moves. Every logbook and inventory card slid in on every search, filter and Load More,
    # and each sliding card made the browser re-check every row's place on every frame (~245 ms of rendering per 20-card
    # append at 390 with the CPU 4x slower, ~26 ms without; SL LB3, 2026-10-21)
    for start, end, _f in row_calls(src):
        cm = re.search(r"class=\"([^\"$]+)", src[start:end])
        if not cm:
            continue
        for c in cm.group(1).split():
            if not re.fullmatch(r"[A-Za-z][\w-]*", c):
                continue
            if re.search(r"(?:^|[\s,}])\." + re.escape(c) + r"\s*\{[^}]*\banimation\s*:\s*(?!none\b)", src):
                line = src.count("\n", 0, start) + 1
                issues.append(f"R14 {page}:{line} every .{c} row runs an animation each time the list draws it (a search, a "
                              f"filter, a Load More) - animate only the row that just arrived (.{c}.new-entry)")
    # R4: typing into a search or filter box that re-renders a list is debounced
    soon = set(re.findall(r"\b(?:const|let|var)\s+([\w$]+)\s*=\s*debounce\(", src))
    for fn, inner in re.findall(r"function\s+([\w$]+)\s*\(\s*\)\s*\{\s*([\w$]+)\(\s*\)\s*;?\s*\}", src):
        if inner in soon:
            soon.add(fn)   # a named wrapper around a debounced call (an inline oninput needs a name)
    sites = []
    for m in re.finditer(r"(?:getElementById\(\s*'([^']+)'\s*\)|\$\(\s*'([^']+)'\s*\))\??\s*\.addEventListener\(\s*'input'\s*,", src):
        sid = m.group(1) or m.group(2)
        k = m.end()
        sites.append((sid, k))
    for m in re.finditer(r"<input\b[^>]*\bid=\"([^\"]+)\"[^>]*\boninput=\"([^\"]+)\"", src):
        sites.append((m.group(1), None, m.group(2), m.start()))
    for site in sites:
        sid = site[0]
        if not re.search(r"search|filter|query|find", sid, re.I):
            continue
        if len(site) == 2:
            k = site[1]
            rest = src[k:k + 200].lstrip()
            if rest.startswith("debounce("):
                continue
            # the handler itself: an arrow or function literal's own { ... } body, or the named function it passes
            fm = re.match(r"\s*(?:async\s*)?(?:function\b[^{]*|\(?[\w$\s,]*\)?\s*=>\s*)\{", src[k:k + 200])
            if fm:
                brace = k + fm.end() - 1
                handler = src[brace:_block_end(src, brace + 1) + 1]
            else:
                nm = re.match(r"\s*([\w$.]+)\s*\)", src[k:k + 120])
                handler = (nm.group(1) + "()") if nm else src[k:k + 120]
            line = src.count("\n", 0, k) + 1
        else:
            handler = site[2]
            line = src.count("\n", 0, site[3]) + 1
        if re.search(r"\bdebounce\(|setTimeout\(", handler):
            continue
        called = [c for c in calls_in(handler) if c not in soon]
        if any(c in soon for c in calls_in(handler)) and not called:
            continue
        heavy = [c for c in called if (lambda b: b and renders_list(b))(fn_body(src, c))]
        if heavy:
            issues.append(f"R4 {page}:{line} re-renders a list ({', '.join(heavy)}) in the keystroke's own task on "
                          f"#{sid} - debounce it")
    # R15 (2026-10-21): R4 reads a box by its id and a handler by what it RE-RENDERS - analytics' list filters have no id
    # and only hide rows, so each keystroke read the text of every row and laid out every match (472 ms to paint with a
    # thousand rows at 390, CPU 4x slower). Every box that searches or filters, however it is named, runs its inline
    # handler after the typing pauses: a debounced function, a named wrapper of one, or a body that defers itself.
    for m in re.finditer(r"<input\b([^>]*)>", src, re.S):
        attrs = m.group(1)
        oi = re.search(r'\boninput="([^"]+)"', attrs)
        if not oi or not re.search(r'type="search"|class="[^"]*search|placeholder="[^"]*(?:[Ss]earch|[Ff]ilter)'
                                   r'|aria-label="[^"]*(?:[Ss]earch|[Ff]ilter)|id="[^"]*(?:search|filter|query|find)', attrs):
            continue
        handler = oi.group(1)
        if re.search(r"\bdebounce\(|setTimeout\(", handler):
            continue
        slow = []
        for c in calls_in(handler):
            if c in soon:
                continue
            body = fn_body(src, c)
            if body is None or re.search(r"\bdebounce\(|setTimeout\(", body):
                continue
            slow.append(c)
        if slow:
            line = src.count("\n", 0, m.start()) + 1
            issues.append(f"R15 {page}:{line} a search box runs {', '.join(slow)} in the keystroke's own task - let it "
                          "wait for the typing to pause")
    # R17 (2026-10-21): a row drawn through whRenderRows carries no HTML comment in its template - a comment is one more
    # node in EVERY row, parsed, kept and traced by the collector: inventory's part card carried three (~1.5 KB of notes a
    # card), and with a thousand cards on screen the browser's collections were the longest tasks around each press
    for line, n in comments_in_row_templates(raw):   # the RAW page: blank_comments removes exactly what this looks for
        issues.append(f"R17 {page}:{line} a row template drawn through whRenderRows carries {n} HTML comment(s) - one more "
                      "node in every row; keep the note as a JS comment beside the template")
    return issues


def comments_in_row_templates(src: str) -> list[tuple[int, int]]:
    """For each whRenderRows( call whose template literals hold '<!--' - its own, or those of a row builder it passes or
    calls by name and the page defines (project-manager passes pcardHtml; hive's feed calls buildFeedCard): (its line,
    how many)."""
    out = []
    bsrc = blank_comments(src)   # extents read here (an apostrophe in a comment is no string); markup read in src
    for s, e, f in row_calls(src):
        # names only from the call's CODE (its ${...} included): a name inside template text - onclick="openModal(..)" -
        # is a handler the row points at, not markup the row is built from
        _n, call = scan_js(src[s + len("whRenderRows("):e])
        names = set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", call)) | set(re.findall(r"[,(]\s*([A-Za-z_$][\w$]*)\s*(?=[,)])", call))
        for nm in sorted(names - {"whRenderRows", "JSON", "String", "Number", "Math", "Object", "Array", "escHtml", "escJsAttr"}):
            sp = fn_span(bsrc, nm)
            if sp:
                f += scan_js(src[sp[0]:sp[1]])[0]
        if f:
            out.append((src.count("\n", 0, s) + 1, f))
    return out


def scan_js(text: str) -> tuple[int, str]:
    """A piece of JS read as row_calls reads it (strings, comments, template literals and the ${...} in them followed):
    how many '<!--' sit inside its template literals, and its code alone - template text, quoted strings and comments as
    spaces."""
    i, n, stack, found = 0, len(text), [], 0
    code = list(text)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if code[k] != "\n":
                code[k] = " "
    while i < n:
        ch = text[i]
        top = stack[-1] if stack else None
        if top == "tpl":
            if ch == "\\":
                blank(i, i + 2)
                i += 2
                continue
            if ch == "`":
                stack.pop()
            elif ch == "$" and text[i + 1:i + 2] == "{":
                stack.append(["expr", 0])
                i += 2
                continue
            else:
                if text.startswith("<!--", i):
                    found += 1
                blank(i, i + 1)
            i += 1
            continue
        if ch in "'\"":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            blank(i, j + 1)
            i = j + 1
            continue
        if ch == "`":
            stack.append("tpl")
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue
        if isinstance(top, list):
            if ch == "{":
                top[1] += 1
            elif ch == "}":
                if top[1] == 0:
                    stack.pop()
                else:
                    top[1] -= 1
        i += 1
    return found, "".join(code)


def row_calls(src: str) -> list[tuple[int, int, int]]:
    """Every whRenderRows( call as (start, end, '<!--' count inside its template literals) - a scanner that follows
    strings, comments, template literals and the ${...} nested in them, so the call ends where JS ends it. (R14 read a
    fixed 1,500 characters past the call for the row's class, and a note moved above a template's return pushed the class
    out of its window - the call's own extent has no such edge.)"""
    out = []
    for m in re.finditer(r"\bwhRenderRows\(", src):
        i, n, depth = m.end() - 1, len(src), 0
        stack = []           # frames: 'tpl', or ['expr', brace depth] for a ${...} inside a template literal
        found = 0
        while i < n:
            ch = src[i]
            top = stack[-1] if stack else None
            if top == "tpl":
                if ch == "\\":
                    i += 2
                    continue
                if ch == "`":
                    stack.pop()
                elif ch == "$" and src[i + 1:i + 2] == "{":
                    stack.append(["expr", 0])
                    i += 2
                    continue
                elif src.startswith("<!--", i):
                    found += 1
                i += 1
                continue
            # code (top level or inside ${...})
            if ch in "'\"":
                j = i + 1
                while j < n and src[j] != ch:
                    j += 2 if src[j] == "\\" else 1
                i = j + 1
                continue
            if ch == "`":
                stack.append("tpl")
                i += 1
                continue
            if src.startswith("//", i):
                i = src.find("\n", i)
                i = n if i < 0 else i
                continue
            if src.startswith("/*", i):
                i = src.find("*/", i + 2)
                i = n if i < 0 else i + 2
                continue
            if isinstance(top, list):
                if ch == "{":
                    top[1] += 1
                elif ch == "}":
                    if top[1] == 0:
                        stack.pop()
                    else:
                        top[1] -= 1
                i += 1
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append((m.start(), i, found))
    return out


def check_static(page: str, raw: str) -> list[str]:
    src = blank_comments(raw)
    issues = []
    if re.search(r"\.(?:from|rpc)\(\s*['\"]", src):
        issues.append(f"R5 {page} now reads the database - it is a data page: measure its lists (move it to DATA_PAGES)")
    declared = STATIC_DECLARED.get(page, ())
    for m in re.finditer(r"fetch\(\s*['\"`]([^'\"`]+)['\"`]", src):
        target = m.group(1)
        if target.endswith("utils.js") or re.match(r"(?:\.\./)*i18n/", target) or target in declared:
            continue
        issues.append(f"R5 {page} fetches {target} - a list built from it can grow; declare it in STATIC_DECLARED with "
                      "why it cannot reach a thousand rows, or measure it as a data page")
    return issues


CV_SKIP = re.compile(r"checkVisibility\(\s*\{[^}]*contentVisibilityAuto\s*:\s*true")
SELF_WRITE_SKIP = re.compile(r"t\s*===\s*bar\s*&&\s*rec\.type\s*===\s*'attributes'\s*&&\s*rec\.attributeName\s*===\s*'style'\s*\)\s*continue")


def check_shared(utils: str, learn: str) -> list[str]:
    """R6 + R7: the shared code every long list runs through."""
    issues = []
    # the per-control loop: takeControls() since the scan reads long lists row by row, pageControls() before that
    body = fn_body(blank_comments(learn), "takeControls") or fn_body(blank_comments(learn), "pageControls")
    if body is None:
        issues.append("R6 learn-link.js has no pageControls() - the page-guide chip's control scan moved; point R6 at it")
    else:
        cv = CV_SKIP.search(body)
        rects = [i for i in (body.find("getBoundingClientRect("), body.find("ctrlRect(")) if i >= 0]
        rect = min(rects) if rects else -1
        if not cv or (rect >= 0 and cv.start() > rect):
            issues.append("R6 learn-link.js pageControls() reads a control's rect before passing over rows the browser is "
                          "skipping (checkVisibility({contentVisibilityAuto: true})) - on a thousand-row list every scan "
                          "lays out every off-screen row")
    src = blank_comments(learn)
    if not SELF_WRITE_SKIP.search(src):
        issues.append("R8 learn-link.js's observer answers the chip's OWN style writes - each lift or stand-down schedules "
                      "another pass, which writes again: 360 writes in 3 s of a page at rest, a long task every frame "
                      "with a thousand rows")
    hb = fn_body(src, "vacateFresh")
    bb = fn_body(src, "bringsControlUnder") or ""
    if hb is None or not re.search(r"at\(\s*h\s*,\s*lastLift", hb):
        issues.append("R8 learn-link.js vacateFresh() (the instant check) must test the chip where it IS (at its current "
                      "lift) - testing its resting box hides a chip sync() just lifted clear, every frame")
    elif re.search(r"\b(pageControls|dialogUp)\s*\(", hb + bb):
        issues.append("R8 learn-link.js's instant check scans the whole page (pageControls/dialogUp) - it runs after every "
                      "insertion; it asks only about the elements just inserted")
    # R13: the instant check runs after the frame's own layout - a ResizeObserver that calls vacateFresh, armed by
    # schedule() through vacateSoon() - and nothing in the chip hit-tests the page; a scroll queues the full pass only
    sched = fn_body(src, "schedule") or ""
    if not re.search(r"new\s+ResizeObserver\(\s*function\s*\(\)\s*\{[^}]*vacateFresh\(\)", src) \
            or "vacateSoon(" not in sched or "vacateFresh(" in sched:
        issues.append("R13 learn-link.js runs its instant check inside the page's own task - its hit tests forced the layout "
                      "of whatever was just inserted (119 ms of one logbook Load More at phone speed); run it after the "
                      "frame's layout (a ResizeObserver on the chip, vacateSoon)")
    if "elementsFromPoint(" in src:
        issues.append("R13 learn-link.js hit-tests the page (elementsFromPoint) - each walks every row of a long list (a "
                      "content-visibility row is its own paint layer); ask about the inserted elements' own boxes")
    if re.search(r"addEventListener\(\s*'scroll'\s*,\s*schedule\s*[,)]", src):
        issues.append("R13 learn-link.js runs the instant check on every frame of a scroll - a scroll moves controls and "
                      "inserts none; queue the full pass, and settle it at once on scrollend")
    if not re.search(r"CTRL_OUT\s*=.*:not\(\[role=\"dialog\"\] \*\)", src):
        issues.append("R13 learn-link.js's control scan reads the controls inside dialogs - while one is shown the chip "
                      "stands down and while it is closed they are hidden; the logbook's pickers held 1,500")
    sch = fn_body(src, "scheduleFull")
    gap = re.search(r"SYNC_GAP\s*=\s*(\d+)", src)
    if sch is None or not gap or int(gap.group(1)) < 200 or "setTimeout(" not in sch:
        issues.append("R9 learn-link.js schedule() runs the full pass (every control, every dialog) on the frame after "
                      "every mutation and scroll - it waits SYNC_GAP (>= 200 ms) since the last one")
    sb = fn_body(src, "sync")
    if sb is None or re.search(r"setState\(\s*'flex'", sb.split("if (!h)")[0]):
        issues.append("R8 learn-link.js sync() shows the chip before measuring - a chip standing down is shown and "
                      "hidden on every pass; measure from the remembered box (home())")
    mb = fn_body(blank_comments(utils), "markIn")
    if mb is None or not re.search(r"closest\(\s*'\.wh-rows-cv'\s*\)\s*\?\s*\(?\s*c\.textContent", mb):
        issues.append("R10 utils.js markIn judges a figure by innerText alone - a row the browser is not drawing "
                      "(content-visibility:auto) has no innerText, so its figures are never made tappable; read anything "
                      "inside a long list (.wh-rows-cv) by its textContent")
    elif "checkVisibility(" in mb:
        issues.append("R10 utils.js markIn asks checkVisibility() - on a row the browser is skipping that computes the "
                      "row's styles, once per figure: 4.9 s of a thousand-part walk at phone speed; read a long list's rows "
                      "by their textContent instead")
    ub = blank_comments(utils)
    ob = ub[ub.find("whOverlayBackDismiss"):]
    ob = ob[:ob.find("})();")]
    if "whOverlayBackDismiss" in ub and not re.search(r"\.matches\(\s*OVERLAY\s*\)", ob):
        issues.append("R11 utils.js whOverlayBackDismiss queries the whole document on every class change on the page - "
                      "only an overlay's own class change opens or closes it (tg.matches(OVERLAY))")
    if not re.search(r"if\s*\(\s*el\s*&&\s*!\(\s*t\s*&&\s*t\.closest\s*&&\s*t\.closest\('\.wh-rows-cv'\)\)\)\s*followOut\(\s*rec\s*\)", src):
        issues.append("R11 learn-link.js answers any childList change outside a list - a label rewriting its words adds no "
                      "control; only an ELEMENT inserted or removed outside a list reaches the remembered controls (followOut)")
    # ...and an element inserted outside a list ADDS its controls to the remembered ones instead of throwing them away: a
    # list's "Showing N of M" note is replaced on every press, and dropping the cache for it re-queried the whole page
    fo = src[src.find("function followOut("):]
    fo = fo[:fo.find("\n        }") + 10]
    if "function followOut(" not in src or "addOut(" not in fo or re.search(r"(?<!if \(outGone > 200\) )outCache\s*=\s*null", fo):
        issues.append("R11 learn-link.js throws its remembered controls away when an element is inserted outside a list - "
                      "followOut adds the inserted element's controls (addOut) and rebuilds only once removed ones pile up")
    sa = ub[ub.find("function carries(nodes)"):]
    sa = sa[:sa.find(".observe(document.body")]
    if "function carries(nodes)" not in ub or not re.search(r"!\s*holdsMark\(\s*t\s*\)\s*&&[^;]*closest\(\s*BOTTOM\s*\)[^;]*continue", sa):
        issues.append("R12 utils.js's Sources area answers every attribute change on the page with its layout-reading pass "
                      "- count one only on an element that holds a carrier, anchor or slot (holdsMark) or on a fixed "
                      "control at the foot of the screen (BOTTOM)")
    # R16: the Sources area's room below is sampled when the fixed controls change, not on every pass - clearBottom keeps
    # its sample by the window and column it was taken in (needAt), the observer drops it when a control at the foot of the
    # screen changes (bottomChanged), and the area coming within reach runs only that room pass (roomSoon), never the full
    # pass: each Load More press scrolls the list's end into view and brought the area back, 21 hit tests through a
    # thousand rows' layers and two queries over the whole document each time (2.6 s + 1.3 s of an inventory walk)
    cb = fn_body(ub, "clearBottom") or ""
    io = ub[ub.find("new IntersectionObserver(function (es)"):]
    io = io[:io.find("observe(area)")]
    # ...and (2026-10-22) the sample is kept until a fixed control's BOX changes, not its class: the connectivity popover,
    # hidden, changed its class on every request, and dropping the sample for it re-ran all 21 samples on every press
    # (1.5 s of an inventory walk at 390). The key is the window and column (needAt.key) and the controls' boxes
    # (bottomSig, which reads boxes and never a class), and nothing in the observer throws the sample away
    sg = fn_body(ub, "bottomSig") or ""
    if ("needAt.key === key" not in cb or "needAt.sig === sig" not in cb or "var sig = bottomSig();" not in cb
            or "getBoundingClientRect()" not in sg or re.search(r"className|classList|getAttribute", sg)
            or re.search(r"needAt\s*=\s*null", sa) or "roomSoon()" not in io or "queue()" in io):
        issues.append("R16 utils.js's Sources area samples the foot of the screen on every pass - keep the sample until "
                      "the window, the column or a fixed control's box changes (needAt keyed on bottomSig, never on a "
                      "class), and let the area coming within reach run only the room pass (roomSoon), not the full one")
    # ...each sample asks for the TOP element at its point (elementsFromPoint walked every row's paint layer: ~1.5 ms a
    # sample at phone speed, 2.6 s of an 82-press walk; elementFromPoint ~0.15 ms), and the guide chip moving itself is not a change at the
    # foot of the screen (it moved twice a press, and each move re-ran the pass and the samples)
    if "elementsFromPoint(" in cb or "elementFromPoint(" not in cb or "t.id === 'wh-guide-link' && m.attributeName === 'style'" not in sa:
        issues.append("R16 utils.js's Sources area samples with elementsFromPoint, or answers the guide chip moving itself - "
                      "ask elementFromPoint for the top element, and pass over the chip's own style changes")
    # R11, the role branch: only a role that makes a dialog rebuilds the chip's remembered controls - inventory's figure
    # marking gives each stat number a role on every press, and an unconditional rebuild re-ran the whole-page query
    if re.search(r"rec\.attributeName\s*===\s*'role'\s*\)\s*outCache\s*=\s*null", src) or "rv === 'dialog'" not in src:
        issues.append("R11 learn-link.js rebuilds its remembered controls on every role change - only a role that makes a "
                      "dialog hides controls; any other role change adds the element if it is now a control")
    fb = fn_body(blank_comments(utils), "whFmtDate")
    if fb is None or "toLocaleString(" in fb or "_whDateFmts" not in fb:
        issues.append("R7 utils.js whFmtDate builds a new date formatter on every call - a thousand-row list draws two or "
                      "three dates a row; keep one Intl.DateTimeFormat per locale and options")
    return issues


# R18 (2026-10-22): the rows out of the scroll-anchor choice, the drawn ones back in
ANCHOR_OUT = re.compile(r"\.wh-rows-cv>\*\{[^}]*overflow-anchor:\s*none[^}]*\}")
ANCHOR_DRAWN = re.compile(r"\.wh-rows-cv>\[data-wh-drawn\]\{[^}]*overflow-anchor:\s*auto[^}]*\}")


def check_anchor_and_paint(utils: str, learn: str, nav: str) -> list[str]:
    """R18 + R19: what a press's frame does besides the page's own script."""
    issues = []
    ub = blank_comments(utils)
    if not ANCHOR_OUT.search(ub) or not ANCHOR_DRAWN.search(ub):
        issues.append("R18 utils.js lets every long-list row be a scroll anchor, or none - with every row in, the browser "
                      "walks a thousand rows to pick one on each frame that changes layout (presses 208/256/192 ms to "
                      "paint at phone speed, 152/176/136 without); with none, a row above the screen that changes height "
                      "moves the screen. Rows out (overflow-anchor:none), the drawn ones in ([data-wh-drawn] auto)")
    i = ub.find("addEventListener('contentvisibilityautostatechange'")
    body = ub[i:_block_end(ub, ub.find("{", i) + 1) + 1] if i >= 0 else ""
    if i < 0 or "ev.skipped" not in body or "setAttribute('data-wh-drawn'" not in body \
            or "removeAttribute('data-wh-drawn'" not in body:
        issues.append("R18 utils.js no longer marks the rows the browser is drawing - a contentvisibilityautostatechange "
                      "listener sets data-wh-drawn on a row it starts drawing and removes it when it stops; without it no "
                      "row is a scroll anchor and a row above the screen that changes height moves the screen")
    elif re.search(r"classList\.(?:add|remove|toggle)\(|className\s*=", body):
        issues.append("R18 utils.js marks the drawn rows with a class - every page's observer answers class changes (each "
                      "filters on class, style, hidden, open, role, aria-hidden); mark them with the data-wh-drawn attribute")
    rf = fn_body(blank_comments(learn), "runFull") or ""
    if not re.search(r"requestAnimationFrame\(\s*function\s*\(\)\s*\{\s*setTimeout\(\s*function\s*\(\)\s*\{[^}]*\bsync\(\)", rf):
        issues.append("R19 learn-link.js runs the guide chip's full pass inside a frame callback - a press's own insertion "
                      "schedules it, so it ran in the press's frame before the paint (33-41 ms of a press at phone speed); "
                      "the frame's callback hands it to a task (setTimeout), which runs once the frame is painted")
    sb = fn_body(blank_comments(nav), "schedule") or ""
    if not re.search(r"afterPaint\s*=\s*function\s*\(\)\s*\{\s*requestAnimationFrame\(\s*function\s*\(\)\s*\{\s*setTimeout\(\s*run\s*,", sb) \
            or not re.search(r"else\s+if\s*\(\s*wait\s*>\s*0\s*\)\s*setTimeout\(\s*afterPaint\s*,\s*wait\s*\)", sb) \
            or not re.search(r"else\s+afterPaint\(\)", sb):
        issues.append("R19 nav-hub.js runs its quarter-second pass inside a frame callback - a press's class and style "
                      "changes put it in the press's own frame (14-16 ms of a press at phone speed); only a dialog's pass "
                      "runs before the paint, every other one after it (afterPaint)")
    return issues

# R20: the day planner's card body is drawn for the selected card only, and the key carries the selection
DP_BODY_LAZY = re.compile(r'class="lb-card-body"\s+id="lbc-body-\$\{item\.id\}">\$\{isSelected\s*\?')
# R21: a listed logbook entry written in place - the kept key would hide the change
LB_IN_PLACE = re.compile(r"\b(?:_allEntries|_teamEntries)\[[^\]]+\]\.[A-Za-z_$][\w$]*\s*=(?!=)|Object\.assign\(\s*(?:_allEntries|_teamEntries)\[")


def check_row_cost(utils: str, dayplanner: str, logbook: str) -> list[str]:
    """R20 + R21: what each press builds for rows it does not change."""
    issues = []
    dp = blank_comments(dayplanner)
    k = dp.find("sig: 'dp-open-items'")
    key = dp[k:dp.find("});", k)] if k >= 0 else ""
    if not DP_BODY_LAZY.search(dp) or "r.isSelected" not in key:
        issues.append("R20 dayplanner.html draws every open-item card's hidden body on every Show more press - draw the body "
                      "only for the selected card (${isSelected ? ...}) and keep the selection in the card's key, so a tap "
                      "redraws the card with its body (fifty hidden bodies cost 23-54 ms of each press at phone speed)")
    rb = fn_body(blank_comments(utils), "whRenderRows") or ""
    if not re.search(r"opts\.immutable\s*&&\s*_whRowKeyMemo\s*\)\s*\?", rb) or "_whRowKeyMemo.get(x)" not in rb \
            or "_whRowKeyMemo.set(x, k)" not in rb or "var _whRowKeyMemo" not in utils:
        issues.append("R21 utils.js whRenderRows no longer keeps a row's default key with the row when the page says its "
                      "rows are replaced, never edited (immutable) - every press serialises every drawn row again")
    lb = blank_comments(logbook)
    # the list it draws into, or the search's own list beside it (whSearchList, SL LB3 2026-10-23)
    _m = re.search(r"whRenderRows\((?:list|_lbListEl\(_searching\)), visible", lb)
    i = _m.start() if _m else -1
    j = lb.find("sig: JSON.stringify([query, _viewMode", i) if i >= 0 else -1
    opts = lb[j:lb.find("});", j)] if j >= 0 else ""
    if "immutable: true" not in opts:
        issues.append("R21 logbook.html re-serialises every entry it has drawn on each Load More - its entries change only "
                      "by replacement, so its whRenderRows call says so (immutable: true)")
    m = LB_IN_PLACE.search(lb)
    if m:
        line = lb.count("\n", 0, m.start()) + 1
        issues.append(f"R21 logbook.html:{line} writes a listed entry in place ({m.group(0)[:60]}) - its list keeps each "
                      "entry's key with the entry (immutable), so a changed entry must be a NEW object or its card never "
                      "redraws")
    return issues


def check(files: dict[str, str] | None = None, utils_override: str | None = None) -> list[str]:
    def text(rel: str) -> str:
        return files[rel] if files and rel in files else (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    issues = check_helper(text("utils.js"), utils_override)
    issues += check_shared(text("utils.js"), text("learn-link.js"))
    issues += check_anchor_and_paint(text("utils.js"), text("learn-link.js"), text("nav-hub.js"))
    issues += check_row_cost(text("utils.js"), text("dayplanner.html"), text("logbook.html"))
    for page in DATA_PAGES:
        issues += check_page(page, text(page))
    for page in STATIC_PAGES:
        issues += check_static(page, text(page))
    return issues


SYNTH_GOOD = """<script>
let _synDisplayCount = 10;
function loadMoreSyn() { _synDisplayCount += 10; renderSyn(); }
function renderSyn() {
  const list = document.getElementById('syn-list');
  whRenderRows(list, rows.slice(0, _synDisplayCount), r => '<li>' + r + '</li>', { key: 'html', long: true });
  list.querySelectorAll('li:not([data-wh-bound])').forEach(li => { li.setAttribute('data-wh-bound', ''); li.addEventListener('click', go); });
}
const _synSearch = debounce(renderSyn, 150);
document.getElementById('syn-search').addEventListener('input', () => { _synSearch(); });
let _synPage = [];
async function loadSynPage(append) {
  try { const rows = await fetchSyn(); _synPage = append ? [..._synPage, ...rows] : rows; } catch (_) { _synPage = []; }
  renderSynPage();
}
function renderSynPage() { whRenderRows(document.getElementById('syn-page'), _synPage, r => '<li>' + r + '</li>', { key: 'html' }); }
</script>"""


MUTANTS_RUN = [0]


def self_test() -> list[str]:
    fails = []
    clean = check()
    if clean:
        fails.append(f"the clean run is not green: {clean[:3]}")
    page0 = DATA_PAGES[0]
    real0 = (ROOT / page0).read_text(encoding="utf-8")
    good = check({page0: real0 + SYNTH_GOOD})
    if good:
        fails.append(f"the clean synthetic page is not green: {good[:2]}")
    utils = (ROOT / "utils.js").read_text(encoding="utf-8")
    static0 = STATIC_PAGES[0]
    sreal = (ROOT / static0).read_text(encoding="utf-8")
    mutants = [
        ("whRenderRows rebuilds a grown list", None,
         utils.replace("listEl.insertAdjacentHTML('beforeend', rowsHtml(prev.keys.length));", "listEl.innerHTML = rowsHtml(0);", 1), "R1"),
        ("the off-screen rule is gone", {"utils.js": utils.replace(CSS_RULE, ".wh-rows-cv>*{display:block", 1)}, None, "R1"),
        ("a show-more that rebuilds every row", {page0: real0 + SYNTH_GOOD.replace(
            "whRenderRows(list, rows.slice(0, _synDisplayCount), r => '<li>' + r + '</li>', { key: 'html', long: true });",
            "list.innerHTML = rows.slice(0, _synDisplayCount).map(r => '<li>' + r + '</li>').join('');", 1)}, None, "R2"),
        ("a page accumulated and the whole list rebuilt", {page0: real0 + SYNTH_GOOD.replace(
            "function renderSynPage() { whRenderRows(document.getElementById('syn-page'), _synPage, r => '<li>' + r + '</li>', { key: 'html' }); }",
            "function renderSynPage() { document.getElementById('syn-page').innerHTML = _synPage.map(r => '<li>' + r + '</li>').join(''); }", 1)}, None, "R2"),
        ("rows bound again after an append", {page0: real0 + SYNTH_GOOD.replace("querySelectorAll('li:not([data-wh-bound])')", "querySelectorAll('li')", 1)}, None, "R3"),
        ("a search re-rendering the list per keystroke", {page0: real0 + SYNTH_GOOD.replace("() => { _synSearch(); }", "() => { renderSyn(); }", 1)}, None, "R4"),
        ("a static page that starts reading the database", {static0: sreal + "<script>db.from('logbook').select('*').limit(50);</script>"}, None, "R5"),
        ("a static page that builds a list from a fetched file", {static0: sreal + "<script>fetch('jobs.json').then(r => r.json());</script>"}, None, "R5"),
        ("the guide chip reads every row's rect", {"learn-link.js": CV_SKIP.sub("Boolean({contentVisibilityAuto: true",
            (ROOT / "learn-link.js").read_text(encoding="utf-8"), count=1)}, None, "R6"),
        ("a date formatter built per date", {"utils.js": utils.replace("return _f.format(dt);", "return dt.toLocaleString(_loc, fmt);", 1)}, None, "R7"),
        ("figures judged by innerText alone", {"utils.js": utils.replace(
            "var t = ((c.closest('.wh-rows-cv') ? (c.textContent || '').replace(/\\s+/g, ' ') : c.innerText) || '').trim();",
            "var t = (c.innerText || '').trim();", 1)}, None, "R10"),
        ("figures judged by asking each row whether it is skipped", {"utils.js": utils.replace(
            "var t = ((c.closest('.wh-rows-cv')",
            "var skipped = c.checkVisibility && !c.checkVisibility({ contentVisibilityAuto: true });\n      var t = ((c.closest('.wh-rows-cv')",
            1)}, None, "R10"),
        ("the overlay Back-dismiss answering every class change", {"utils.js": utils.replace(
            "hit = !!(tg && tg.matches && tg.matches(OVERLAY));", "hit = true;", 1)}, None, "R11"),
        ("a part card that slides in every time the list draws it", {"inventory.html": (ROOT / "inventory.html").read_text(encoding="utf-8").replace(
            "      border-left-width: 1px;\n      transition: border-color 0.2s;",
            "      border-left-width: 1px;\n      animation: slide-in 0.22s ease-out;\n      transition: border-color 0.2s;", 1)}, None, "R14"),
        ("a logbook card that slides in every time the list draws it", {"logbook.html": (ROOT / "logbook.html").read_text(encoding="utf-8").replace(
            "    .entry-card.new-entry { animation:", "    .entry-card { animation:", 1)}, None, "R14"),
        ("an analytics list filter run in the keystroke's own task", {"analytics.html": (ROOT / "analytics.html").read_text(encoding="utf-8").replace(
            'oninput="filterShowAllListSoon(this)"', 'oninput="filterShowAllList(this)"', 1)}, None, "R15"),
        ("the instant check back inside the page's task", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "if (fresh.length) vacateSoon();", "if (fresh.length) vacateFresh();", 1)}, None, "R13"),
        ("the chip hit-testing the page again", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "var cur = at(h, lastLift || 0);", "var cur = at(h, lastLift || 0); document.elementsFromPoint(cur.left, cur.top);", 1)}, None, "R13"),
        ("the instant check on every scroll frame", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "window.addEventListener('scroll', function () { scheduleFull(); }, { passive: true });",
            "window.addEventListener('scroll', schedule, { passive: true });", 1)}, None, "R13"),
        ("the scan reading every dialog's controls", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            ":not([role=\"dialog\"] *):not(dialog *)'; }).join(',');", "'; }).join(',');", 1)}, None, "R13"),
        ("the Sources area answering every attribute change", {"utils.js": utils.replace(
            "if (!holdsMark(t) && (t.closest('.wh-rows-cv') || !t.closest(BOTTOM))) continue;", "", 1)}, None, "R12"),
        ("the chip dropping its controls on a rewritten label", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "if (el && !(t && t.closest && t.closest('.wh-rows-cv'))) followOut(rec);",
            "if (!(t && t.closest && t.closest('.wh-rows-cv'))) followOut(rec);", 1)}, None, "R11"),
        ("the Sources area's full pass on every Load More", {"utils.js": utils.replace(
            "if (es[i].isIntersecting) { roomSoon(); break; }", "if (es[i].isIntersecting) { queue(); break; }", 1)}, None, "R16"),
        ("the Sources area sampling the foot of the screen every pass", {"utils.js": utils.replace(
            "if (needAt && needAt.key === key && needAt.sig === sig) need = needAt.need;", "if (false) need = 0;", 1)}, None, "R16"),
        ("the Sources area dropping its samples on any change at the foot again", {"utils.js": utils.replace(
            "if (!holdsMark(t) && (t.closest('.wh-rows-cv') || !t.closest(BOTTOM))) continue;",
            "if (!holdsMark(t) && (t.closest('.wh-rows-cv') || !t.closest(BOTTOM))) continue;\n          needAt = null;", 1)}, None, "R16"),
        ("the Sources area's samples keyed on a control's class", {"utils.js": utils.replace(
            "+ cs.visibility.charAt(0) + cs.pointerEvents.charAt(0) + ';';",
            "+ cs.visibility.charAt(0) + cs.pointerEvents.charAt(0) + el.className + ';';", 1)}, None, "R16"),
        ("a note written into every inventory card as an HTML comment", {"inventory.html": (ROOT / "inventory.html").read_text(encoding="utf-8").replace(
            '<div class="part-card stock-${st} p-5 mb-3"', '<!-- a note --><div class="part-card stock-${st} p-5 mb-3"', 1)}, None, "R17"),
        ("the Sources area walking every layer under a sample", {"utils.js": utils.replace(
            "var top = document.elementFromPoint(xs[xi], H - 10 - yi * 40);",
            "var top = (document.elementsFromPoint(xs[xi], H - 10 - yi * 40) || [])[0];", 1)}, None, "R16"),
        ("the Sources area answering the guide chip moving itself", {"utils.js": utils.replace(
            "if (t.id === 'wh-guide-link' && m.attributeName === 'style') continue;", "", 1)}, None, "R16"),
        ("the chip rebuilding its controls on every role change", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "if (rv === 'dialog' || rv === 'alertdialog') outCache = null;", "outCache = null;", 1)}, None, "R11"),
        ("the chip throwing its controls away for a replaced note", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "for (var i = 0; i < rec.addedNodes.length; i++) addOut(rec.addedNodes[i]);",
            "outCache = null; return;", 1)}, None, "R11"),
        ("the chip answers its own style writes", {"learn-link.js": SELF_WRITE_SKIP.sub("false) continue",
            (ROOT / "learn-link.js").read_text(encoding="utf-8"), count=1)}, None, "R8"),
        ("the chip hidden by its resting box", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "var cur = at(h, lastLift || 0);", "var cur = h;", 1)}, None, "R8"),
        ("the instant check scans the whole page", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "var cur = at(h, lastLift || 0);", "var cur = at(h, lastLift || 0); if (dialogUp()) { setState('none', 0); return; }", 1)}, None, "R8"),
        ("the full pass on every frame", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "var SYNC_GAP = 250", "var SYNC_GAP = 0", 1)}, None, "R9"),
        ("the chip shown to be measured", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "var h = home();\n          if (!h) { setState('flex', 0); h = home(); }",
            "setState('flex', lastLift || 0);\n          var h = home();\n          if (!h) { setState('flex', 0); h = home(); }", 1)}, None, "R8"),
        ("every long-list row a scroll anchor again", {"utils.js": utils.replace(";overflow-anchor:none}'", "}'", 1)}, None, "R18"),
        ("no long-list row a scroll anchor", {"utils.js": utils.replace(
            "'.wh-rows-cv>[data-wh-drawn]{overflow-anchor:auto}'", "'.wh-rows-cv>[data-wh-drawn]{}'", 1)}, None, "R18"),
        ("the drawn rows never marked", {"utils.js": utils.replace(
            "document.addEventListener('contentvisibilityautostatechange', function (ev) {\n    var t = ev.target, pe",
            "document.addEventListener('contentvisibilitychange', function (ev) {\n    var t = ev.target, pe", 1)}, None, "R18"),
        ("the drawn rows marked by a class", {"utils.js": utils.replace(
            "if (ev.skipped) t.removeAttribute('data-wh-drawn');\n    else t.setAttribute('data-wh-drawn', '');",
            "if (ev.skipped) { t.classList.remove('wh-drawn'); t.removeAttribute('data-wh-drawn'); }\n    else { t.classList.add('wh-drawn'); t.setAttribute('data-wh-drawn', ''); }", 1)}, None, "R18"),
        ("the guide chip's full pass back inside the press's frame", {"learn-link.js": (ROOT / "learn-link.js").read_text(encoding="utf-8").replace(
            "requestAnimationFrame(function () {\n            setTimeout(function () { fullFrame = false; ctrlCache = null; lastSync = performance.now(); sync(); }, 0);\n          });",
            "requestAnimationFrame(function () { fullFrame = false; ctrlCache = null; lastSync = performance.now(); sync(); });", 1)}, None, "R19"),
        ("the nav hub's pass back inside the press's frame", {"nav-hub.js": (ROOT / "nav-hub.js").read_text(encoding="utf-8").replace(
            "var afterPaint = function () { requestAnimationFrame(function () { setTimeout(run, 0); }); };",
            "var afterPaint = function () { requestAnimationFrame(run); };", 1)}, None, "R19"),
        ("the nav hub's waited pass back inside a frame", {"nav-hub.js": (ROOT / "nav-hub.js").read_text(encoding="utf-8").replace(
            "else if (wait > 0) setTimeout(afterPaint, wait);", "else if (wait > 0) setTimeout(function () { requestAnimationFrame(run); }, wait);", 1)}, None, "R19"),
        ("a comment in a row builder passed by name", {"project-manager.html": (ROOT / "project-manager.html").read_text(encoding="utf-8").replace(
            '<div class="pname">${e(p.name)}</div>', '<div class="pname">${e(p.name)}</div><!-- a note -->', 1)}, None, "R17"),
        ("every planner card's body drawn on every press", {"dayplanner.html": (ROOT / "dayplanner.html").read_text(encoding="utf-8").replace(
            '<div class="lb-card-body" id="lbc-body-${item.id}">${isSelected ? `', '<div class="lb-card-body" id="lbc-body-${item.id}">${true ? `', 1)}, None, "R20"),
        ("a planner card's key without its selection", {"dayplanner.html": (ROOT / "dayplanner.html").read_text(encoding="utf-8").replace(
            "const st = r.isSelected + '|' + r.hasDone", "const st = r.hasDone", 1)}, None, "R20"),
        ("whRenderRows never keeping a row's key", {"utils.js": utils.replace(
            "(opts.immutable && _whRowKeyMemo) ?", "(false) ?", 1)}, None, "R21"),
        ("the logbook not saying its entries are replaced", {"logbook.html": (ROOT / "logbook.html").read_text(encoding="utf-8").replace(
            "    immutable: true,\n  });", "  });", 1)}, None, "R21"),
        ("the logbook writing a listed entry in place", {"logbook.html": (ROOT / "logbook.html").read_text(encoding="utf-8").replace(
            "async function loadMoreLogbook() {", "async function loadMoreLogbook() {\n  if (_allEntries[0]) _allEntries[0].status = 'Closed';", 1)}, None, "R21"),
    ]
    MUTANTS_RUN[0] = len(mutants)
    for name, files, utils_src, want in mutants:
        got = check(files, utils_src)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print(f"SELF-TEST PASS ({MUTANTS_RUN[0]} mutants caught; the clean runs are green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues = check()
    print("Long-list render (SL LB3): every list on the LB3 pages stays responsive with a thousand rows in it")
    for i in issues[:60]:
        print("  [FAIL] " + i)
    print(f"  PASS - {len(DATA_PAGES)} data pages: every show-more appends, no row is bound twice, every search waits for "
          f"the typing to pause; {len(STATIC_PAGES)} static pages build no list from data" if not issues
          else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
