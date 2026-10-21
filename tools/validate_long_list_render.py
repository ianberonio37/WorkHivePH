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


def fn_body(src: str, name: str) -> str | None:
    """The body of the function `name` defined on the page (function name( / name = (...) => / name = function)."""
    m = re.search(r"(?:\bfunction\s+" + re.escape(name) + r"\s*\(|\b" + re.escape(name)
                  + r"\s*=\s*(?:async\s*)?(?:function\b[^{]*|\([^)]*\)\s*=>\s*|[\w$]+\s*=>\s*))", src)
    if not m:
        return None
    k = src.find("{", m.end() - 1)
    if k < 0:
        return None
    return src[k:_block_end(src, k + 1) + 1]


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
    for m in re.finditer(r"whRenderRows\(", src):
        cm = re.search(r"class=\"([^\"$]+)", src[m.end():m.end() + 1500])
        if not cm:
            continue
        for c in cm.group(1).split():
            if not re.fullmatch(r"[A-Za-z][\w-]*", c):
                continue
            if re.search(r"(?:^|[\s,}])\." + re.escape(c) + r"\s*\{[^}]*\banimation\s*:\s*(?!none\b)", src):
                line = src.count("\n", 0, m.start()) + 1
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
    return issues


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
    if not re.search(r"if\s*\(\s*el\s*&&\s*!\(\s*t\s*&&\s*t\.closest\s*&&\s*t\.closest\('\.wh-rows-cv'\)\)\)\s*outCache\s*=\s*null", src):
        issues.append("R11 learn-link.js drops its remembered controls on any childList change outside a list - a label "
                      "rewriting its words adds no control; drop them only when an ELEMENT is inserted or removed")
    sa = ub[ub.find("function carries(nodes)"):]
    sa = sa[:sa.find(".observe(document.body")]
    if "function carries(nodes)" not in ub or not re.search(r"!\s*holdsMark\(\s*t\s*\)\s*&&[^;]*closest\(\s*BOTTOM\s*\)[^;]*continue", sa):
        issues.append("R12 utils.js's Sources area answers every attribute change on the page with its layout-reading pass "
                      "- count one only on an element that holds a carrier, anchor or slot (holdsMark) or on a fixed "
                      "control at the foot of the screen (BOTTOM)")
    fb = fn_body(blank_comments(utils), "whFmtDate")
    if fb is None or "toLocaleString(" in fb or "_whDateFmts" not in fb:
        issues.append("R7 utils.js whFmtDate builds a new date formatter on every call - a thousand-row list draws two or "
                      "three dates a row; keep one Intl.DateTimeFormat per locale and options")
    return issues


def check(files: dict[str, str] | None = None, utils_override: str | None = None) -> list[str]:
    def text(rel: str) -> str:
        return files[rel] if files and rel in files else (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    issues = check_helper(text("utils.js"), utils_override)
    issues += check_shared(text("utils.js"), text("learn-link.js"))
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
            "if (el && !(t && t.closest && t.closest('.wh-rows-cv'))) outCache = null;",
            "if (!(t && t.closest && t.closest('.wh-rows-cv'))) outCache = null;", 1)}, None, "R11"),
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
    ]
    for name, files, utils_src, want in mutants:
        got = check(files, utils_src)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (26 mutants caught; the clean runs are green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
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
