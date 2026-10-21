#!/usr/bin/env python3
"""render_sources_area.py - ENH-R (Ian, 2026-10-19): provenance moves out of the top, to a Sources area at the foot.

Ian: "all that provenance should be all relocated somewhere that is not getting space on the upper part where the user's
attention the most, you can relocate it at the bottom most of the page."

Every page enhancement_inventory measures as class R (provenance in its source, no Sources area) gets ONE area, written
here at the foot of its main content (just before </main>, or at a `<!-- wh-sources-anchor -->` placed by hand on a page
with no <main>):

    <section class="wh-sources" data-wh-sources ...><h2>Where these figures come from</h2><div data-wh-sources-list>

and three kinds of provenance are moved into it:

  * the lines renderSourceChip() draws at runtime. utils.js hands the caller an inert carrier instead of the line, and
    its whSourcesArea mirrors the line into the area while the place it was drawn is on screen. What this script does
    for them is COLLAPSE the slot each one was drawn into (the <p id="...-source-chip"> under a header, often with a
    50-108px reserve): hidden + data-wh-sources-collapsed, its inline style and its reserve rule removed, so no space
    is kept at the top for a line that now lives at the foot.
  * a page's "Show details" explainer - the #details-toggle-btn and the "How this is computed" region it controls -
    moved as one unit, with a data-wh-source-anchor left where it was, so it is shown only while that place is
    (a supervisor card's explainer stays hidden from a worker, as it was).
  * static source lines (<p class="wh-source-chip">...</p> written in the markup, in any attribute order).

The area is styled inline, so it is styled before paint on every page whichever stylesheets the page loads, and it is
hidden while it would be empty.

    python tools/render_sources_area.py            # report pages whose area is missing, misplaced or leaves provenance out
    python tools/render_sources_area.py --apply    # write the areas and move the provenance into them
    python tools/render_sources_area.py --check    # the gate (provenance-at-foot): exit 1 on any page out of shape
    python tools/render_sources_area.py --self-test
    --only=root | --only=public narrows any of the above to the app pages or the public ones
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OPEN_MARK = "<!-- wh-sources: written by tools/render_sources_area.py (ENH-R) - lines are filed into the list at runtime -->"
CLOSE_MARK = "<!-- /wh-sources -->"
ANCHOR = "<!-- wh-sources-anchor -->"
# Right after the area, a guarded call to utils.js's whSourcesSync: it asks for a sync as soon as the area is parsed, and
# - the reason it is a typeof guard - it puts whSourcesSync on the page's skew-heal list (bug_hunt_inventory reads guarded
# utils functions), so a page met with an OLDER utils.js, which would leave the area hidden for good, heals itself.
NUDGE = "<script>typeof whSourcesSync === 'function' && whSourcesSync();</script>"
# index.html is held by the strict-CSP ratchet (tools/validate_csp.py: its un-nonced inline scripts may only fall), and the
# nudge as a script of its own was its 13th (2026-10-19). There the call is the FIRST LINE of the inline script that
# already follows the area - the same moment, the same guard (so the skew-heal list still names it) - and the area
# carries this mark instead; the check holds the call in that place. (2026-10-22)
NUDGE_CALL = "typeof whSourcesSync === 'function' && whSourcesSync();"
MERGED_MARK = "<!-- wh-sources-nudge: the first line of the next script (index.html's inline scripts may only fall) -->"
AREA_RX =re.compile(re.escape(OPEN_MARK) + r"[\s\S]*?" + re.escape(CLOSE_MARK))
STATIC_CHIP_RX = re.compile(r'\n?[ \t]*<p\b[^>]*\bclass="wh-source-chip"[^>]*>[\s\S]*?</p>')
EXPLAINER_BTN_RX = re.compile(r'[ \t]*<button\b[^>]*\bid="details-toggle-btn"[^>]*>[\s\S]*?</button>[ \t]*\n?')
NOTE_RX = re.compile(r"How (we compute|this is computed|it.s computed|we calculate)", re.I)
CALM_RX = re.compile(r'[ \t]*<details\b[^>]*\bdata-calm-disclosure="data-sources"[^>]*>[\s\S]*?</details>[ \t]*\n?')
SCRIPT_RX = re.compile(r"<script\b[\s\S]*?</script>|<style\b[\s\S]*?</style>|<!--[\s\S]*?-->", re.I)
# the slots renderSourceChip() is drawn into: `X.innerHTML = renderSourceChip(` with X = getElementById('<id>')
# \b first: without it a long run of word characters (an inline data: URI) is retried from every position inside it,
# which is quadratic - one page took 80 s.
CALL_RX = re.compile(r"\b(\w+)\s*(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/\s*)?\.innerHTML\s*=\s*(?:[^;=]*\?\s*)?renderSourceChip\(")
DIRECT_CALL_RX = re.compile(r"getElementById\(['\"]([\w-]+)['\"]\)\s*\.innerHTML\s*=\s*renderSourceChip\(")
COLLAPSED = "data-wh-sources-collapsed"
# a reserve rule kept for a slot that is now collapsed: only box-size declarations, nothing a page would miss
RESERVE_PROPS = {"min-height", "height", "margin", "margin-top", "margin-bottom", "padding", "max-width", "box-sizing"}


UTILS_TAG_RX = re.compile(r'<script\b[^>]*\bsrc="(?:\./|/)?utils\.js(?:\?[^"]*)?"')


def _live(src: str) -> bool:
    """A page that loads utils.js has its area revealed at runtime (whSourcesArea). A STATIC page - the calculators, the
    learn index, feedback: none of them loads utils.js - has nothing that could ever reveal it, so its area ships
    shown, holding its static lines, and carries no nudge."""
    spans = _code_spans(src)
    return any(not any(a < m.start() < b for a, b in spans) for m in UTILS_TAG_RX.finditer(src))


def shell(items: str = "", hidden: bool | None = None, live: bool = True) -> str:
    # ★A LIVE PAGE'S AREA SHIPS HIDDEN (walked 2026-10-19 on shift-brain: layout shift 1.0). A page that keeps its content
    # hidden until its start-up finishes (shift-brain's page-wrap ships display:none) painted the area FIRST - at the top
    # of an empty page - and then its content arrived above it and threw it down the screen. whSourcesArea reveals the
    # area only once a line it lists is on screen, so it can never be the first thing a page paints. A static page's
    # content is all there at first paint, so its area is too.
    hidden = live
    return (OPEN_MARK + "\n"
            '<section class="wh-sources" data-wh-sources aria-labelledby="wh-sources-title"' + (" hidden" if hidden else "") + ' '
            'style="margin:40px 0 24px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);">\n'
            '<h2 id="wh-sources-title" style="margin:0 0 10px;font-size:0.85rem;font-weight:600;line-height:1.4;'
            'color:rgba(255,255,255,0.80);">Where these figures come from</h2>\n'
            '<div data-wh-sources-list style="display:grid;gap:10px;">' + items + '</div>\n'
            "</section>\n" + (NUDGE + "\n" if live else "") + CLOSE_MARK)


def population() -> list[str]:
    from enhancement_inventory import _provenance
    pages = {c["page"] for c in _provenance(None)}
    for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*/index.html")) + list(ROOT.glob("*/*/index.html")):
        try:
            if OPEN_MARK in p.read_text(encoding="utf-8", errors="replace"):
                pages.add(p.relative_to(ROOT).as_posix())
        except OSError:
            pass
    return sorted(pages)


def _mask(src: str) -> str:
    """The page with its scripts, styles and comments blanked IN PLACE (positions kept), so markup can be matched
    without matching code. Blanked with , not spaces: a pattern that opens with [ 	]* re-scans a 100 KB run of
    spaces from every position inside it, which is quadratic - the first version took 70 s on one page."""
    return SCRIPT_RX.sub(lambda m: "" * len(m.group(0)), src)


def _code_spans(src: str) -> list[tuple[int, int]]:
    """The <script> and <style> blocks of the page, read in document order with comments taken first, so a comment that
    mentions "<script>" does not open a script."""
    return [(m.start(), m.end()) for m in SCRIPT_RX.finditer(src) if not m.group(0).startswith("<!--")]


def _in_code(spans: list[tuple[int, int]], i: int) -> bool:
    return any(a <= i < b for a, b in spans)


def _markup_find(src: str, needle: str) -> int:
    """The first `needle` that is MARKUP, not text inside a script or a style. ★asset-hub builds its printable report in a
    template literal that contains "</main>", and that was the first one in the file: the area - and the Show-details
    explainer moved into it - were written into the script's string, and the page lost its explainer (walked
    2026-10-19)."""
    spans = _code_spans(src)
    i = src.find(needle)
    while i >= 0 and _in_code(spans, i):
        i = src.find(needle, i + 1)
    return i


def outside(src: str) -> str:
    """The page with its Sources area, scripts, styles and comments removed - where static provenance must not be."""
    return SCRIPT_RX.sub("", AREA_RX.sub("", src))


def _own_scripts(src: str) -> str:
    """The page's OWN script files, joined: engineering-design.html draws its line from engineering-design.js, and a slot
    filled from a file the page loads was invisible to a reading of the page alone - it kept its 69px reserve at the top
    and collapsed late, a layout shift of 0.068 (walked 2026-10-19)."""
    out = []
    for m in re.finditer(r'<script\b[^>]*\bsrc="([\w-]+\.js)"', src):
        p = ROOT / m.group(1)
        if p.is_file() and p.stat().st_size and m.group(1) not in _SHARED_SCRIPTS:
            out.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


# the shared scripts every page loads: their renderSourceChip calls (if any) are not a page's slots
_SHARED_SCRIPTS = {"utils.js", "nav-hub.js", "companion-launcher.js", "offline-banner.js", "offline-queue.js",
                   "connectivity-widget.js", "session-timeout.js", "device-fingerprint.js", "form-autosave.js",
                   "browser-floor.js", "maturity-gate.js", "wh-ga4.js", "wh-feedback-fab.js", "skew-heal.js"}


def slot_ids(src: str) -> list[str]:
    """The ids of the elements renderSourceChip() lines are drawn into, read from the page's own calls - in the page and
    in the script files that are the page's own."""
    src = src + "\n" + _own_scripts(src)
    ids, lines = [], src.split("\n")
    for i, ln in enumerate(lines):
        for m in DIRECT_CALL_RX.finditer(ln):
            ids.append(m.group(1))
        for m in CALL_RX.finditer(ln):
            var = m.group(1)
            for j in range(i, max(-1, i - 60), -1):
                mm = re.search(r"\b" + re.escape(var) + r"\s*=\s*document\.(?:getElementById\(['\"]([\w-]+)['\"]\)"
                               r"|querySelector\(['\"]#([\w-]+)['\"]\))", lines[j])
                if mm:
                    ids.append(mm.group(1) or mm.group(2))
                    break
    return list(dict.fromkeys(ids))


def _static_tag(src: str, sid: str):
    """The opening tag of the element with id `sid` in the page's markup (not in a script), or None."""
    masked = _mask(src)
    return re.search(r"<([a-z][a-z0-9]*)\b[^>]*\bid=\"" + re.escape(sid) + r"\"[^>]*>", masked)


def collapse_slots(src: str) -> str:
    for sid in slot_ids(src):
        m = _static_tag(src, sid)
        if not m:
            continue
        tag = src[m.start():m.end()]
        if COLLAPSED in tag:
            continue
        new = re.sub(r'\s+style="[^"]*"', "", tag)
        new = re.sub(r'\s+class="wh-source-chip"', "", new)
        new = re.sub(r'(\s+class="[^"]*?)\bwh-source-chip\b\s*', r"\1", new)
        new = re.sub(r"\s+hidden(?=[\s>])", "", new)
        new = new[:-1].rstrip() + " hidden " + COLLAPSED + ">"
        src = src[:m.start()] + new + src[m.end():]
        # the reserve rule kept for the line at the top: only box-size declarations, so it has nothing left to do -
        # removed with its whole line (and that line's trailing comment) when it stood alone, else just the rule
        def reserve_only(body):
            props = {d.split(":", 1)[0].strip().lower() for d in body.split(";") if ":" in d}
            return bool(props) and props <= RESERVE_PROPS
        sel = r"#" + re.escape(sid) + r"(?:\s*>\s*\.wh-source-chip)?"
        src = re.sub(r"(?m)^[ \t]*" + sel + r"\s*\{([^{}]*)\}[ \t]*(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/)?[ \t]*\n",
                     lambda rm: "" if reserve_only(rm.group(1)) else rm.group(0), src)
        src = re.sub(r"([\s{};/>])" + sel + r"\s*\{([^{}]*)\}",
                     lambda rm: rm.group(1) if reserve_only(rm.group(2)) else rm.group(0), src)
        src = re.sub(r"(?m)^[ \t]*@media[^{}\n]*\{\s*\}[ \t]*\n", "", src)     # a media query left with no rule
        src = re.sub(r"@media[^{}\n]*\{\s*\}", "", src)
    return src


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _Stack(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        self.stack.append((tag, "hidden" in a or "hidden" in cls
                           or bool(re.search(r"display\s*:\s*none", a.get("style") or ""))))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def _starts_hidden(src: str, pos: int) -> bool:
    """True when the markup at `pos` sits inside an element the page ships hidden (attribute or .hidden class)."""
    p = _Stack()
    p.feed(SCRIPT_RX.sub("", src[:pos]))
    return any(h for _, h in p.stack)


def _balanced_div(src: str, start: int) -> int:
    """The index just past the </div> that closes the <div ...> opening at `start`."""
    depth = 0
    for m in re.finditer(r"<div\b|</div>", src[start:], re.I):
        depth += 1 if m.group(0).lower().startswith("<div") else -1
        if depth == 0:
            return start + m.end()
    raise ValueError("unbalanced div")


def relocate(src: str) -> str:
    """Move a page's provenance into its Sources area (which must exist): the "Show details" explainer with the region
    it controls, and every static source line outside the area."""
    if not AREA_RX.search(src):
        return src
    moved = []
    masked = _mask(src)
    a = AREA_RX.search(src)
    for btn in EXPLAINER_BTN_RX.finditer(masked):
        if a.start() <= btn.start() < a.end():
            continue
        rid = re.search(r'\baria-controls="([\w-]+-summary-details)"', btn.group(0))
        if not rid:
            continue                     # a toggle for something other than an explainer (plant-connections' cards)
        rid = rid.group(1)
        r = re.search(r'[ \t]*<div\b[^>]*\bid="' + re.escape(rid) + r'"[^>]*>', masked)
        if not r:
            continue
        end = _balanced_div(masked, masked.index("<div", r.start()))   # a <div> quoted in a comment is not a div
        if end < len(src) and src[end] == "\n":
            end += 1
        hidden = _starts_hidden(src, btn.start())
        unit = ('<div class="wh-sources-item" data-wh-source-key="' + rid + '"' + (" hidden" if hidden else "") + ">\n"
                + src[btn.start():btn.end()].strip() + "\n" + src[r.start():end].strip() + "\n</div>")
        indent = re.match(r"[ \t]*", src[btn.start():]).group(0)
        anchor = indent + '<span data-wh-source-anchor="' + rid + '" hidden></span>\n'
        (b0, b1), (r0, r1) = (btn.start(), btn.end()), (r.start(), end)
        if b0 < r0:
            src = src[:b0] + anchor + src[b1:r0] + src[r1:]
        else:
            src = src[:r0] + src[r1:b0] + anchor + src[b1:]
        moved.append((unit, hidden))
        break                            # one explainer per page; re-scan if there were ever more
    # Static source lines - in markup only (a chip spelled in a script or a comment is code, not a line). Each moves as
    # an item with an anchor left where it was, so it shows only while that place does (platform-actions' usage line
    # sits in a card only an admin is shown). An EMPTY line is moved too when a hand-written script fills it by id; one
    # renderSourceChip() fills is a slot, and collapse_slots() deals with it.
    slots = set(slot_ids(src))
    n_static = 0
    while True:
        a = AREA_RX.search(src)
        masked = _mask(src)
        c = None
        for m in STATIC_CHIP_RX.finditer(masked):
            if a.start() <= m.start() < a.end():
                continue
            head = m.group(0)[:m.group(0).index(">") + 1]
            idm = re.search(r'\bid="([\w-]+)"', head)
            if idm and idm.group(1) in slots:
                continue
            c = m
            break
        if not c:
            break
        chip = src[c.start():c.end()]
        head = chip[:chip.index(">") + 1]
        idm = re.search(r'\bid="([\w-]+)"', head)
        n_static += 1
        key = idm.group(1) if idm else "source-line-%d" % n_static
        empty = not re.sub(r"<[^>]+>|\s", "", chip.strip()[len(head.strip()):-4])
        hidden = _starts_hidden(src, c.start()) or empty
        lead = re.match(r"\n?[ \t]*", chip).group(0)
        src = src[:c.start()] + lead + '<span data-wh-source-anchor="' + key + '" hidden></span>' + src[c.end():]
        body = re.sub(r"\s*min-height:\s*[\d.]+(?:px|rem|em)\s*;?", "", chip.strip(), count=1)   # no reserve at the foot
        moved.append(('<div class="wh-sources-item" data-wh-source-key="' + key + '"' + (" hidden" if hidden else "")
                      + ">\n" + body + "\n</div>", hidden))
    # The "Calm Dashboard Contract" footer - <details data-calm-disclosure="data-sources"> "About this dashboard's data
    # sources" - is the same job as the area, written once more after the page's scripts on nine pages: one area, so it
    # folds in as the area's last item, with its own column layout dropped (the area is aligned to the content already).
    while True:
        a = AREA_RX.search(src)
        masked = _mask(src)
        c = next((m for m in CALM_RX.finditer(masked) if not (a.start() <= m.start() < a.end())), None)
        if not c:
            break
        body = src[c.start():c.end()].strip()
        body = re.sub(r'(<details\b[^>]*?)\s+style="[^"]*"', r'\1 style="margin:0;"', body, count=1)
        src = src[:c.start()] + src[c.end():]
        moved.append((body, False))
    if not moved:
        return src
    a = AREA_RX.search(src)
    block = a.group(0)
    k = block.index(">", block.index("<div data-wh-sources-list")) + 1
    block = block[:k] + "\n" + "\n".join(u for u, _ in moved) + "\n" + block[k:]
    if not _live(src) and any(not h for _, h in moved):          # a static page: nothing would ever reveal it
        block = block.replace(_OPEN_TAG + "hidden style=", _OPEN_TAG + "style=", 1)
    out = src[:a.start()] + block + src[a.end():]
    return relocate(out) if EXPLAINER_BTN_RX.search(outside(out)) and out != src else out


_TRAIL_TOK = re.compile(r"<script\b[\s\S]*?</script>|<!--[\s\S]*?-->", re.I)


def _foot_index(src: str, anchor_at: int) -> int:
    """Where the area belongs: at the end of the page's CONTENT - before the run of scripts and comments that ends
    <main> (or meets the hand-placed anchor), not after it. ★A SCRIPT ABOVE THE AREA RUNS BEFORE THE AREA EXISTS
    (walked 2026-10-19 on report-sender): its main script sits inside <main>, so at parse time renderSourceChip found
    no area and drew its line at the top again, and wireDetailToggle found no button - the moved "Show details" did
    nothing. Placed before the scripts, every script on the page runs with the area already in the document."""
    head = src[:anchor_at]
    start = len(head.rstrip())
    for m in reversed(list(_TRAIL_TOK.finditer(head))):
        if m.start() >= start or OPEN_MARK in m.group(0) or CLOSE_MARK in m.group(0):
            continue
        if head[m.end():start].strip() == "":
            start = m.start()
        else:
            break
    return start


def problems_of(page: str, src: str) -> list[str]:
    bad = []
    n = len(AREA_RX.findall(src))
    if n != 1:
        return [f"{page}: {n} Sources areas (wants exactly one)"]
    m = AREA_RX.search(src)
    if _in_code(_code_spans(src), m.start()):
        return [f"{page}: the Sources area was written inside a script or a style, not into the page"]
    for a in re.finditer(r"data-wh-source-anchor=", src):
        if _in_code(_code_spans(src), a.start()):
            bad.append(f"{page}: an explainer's anchor sits inside a script")
            break
    after = src[m.end():]
    anchor = ANCHOR if _markup_find(src, ANCHOR) >= 0 else "</main>"
    if not re.match(r"\s*" + re.escape(anchor), _TRAIL_TOK.sub(lambda t: t.group(0) if t.group(0) == ANCHOR else "", after)):
        bad.append(f"{page}: the Sources area is not at the foot (only scripts and comments may follow it before {anchor})")
    if re.search(r"<script\b", src[_foot_index(src, m.start()):m.start()]):
        bad.append(f"{page}: a script sits between the page's content and its Sources area - it runs before the area exists")
    rest = outside(src)
    for c in STATIC_CHIP_RX.finditer(rest):
        bad.append(f"{page}: a static source line sits outside the Sources area: {c.group(0).strip()[:70]!r}")
    for b in EXPLAINER_BTN_RX.finditer(rest):
        if re.search(r'aria-controls="[\w-]+-summary-details"', b.group(0)):
            bad.append(f"{page}: its Show-details explainer sits outside the Sources area")
    if re.search(r'<div\b[^>]*\bid="[\w-]+-summary-details"', rest):
        bad.append(f"{page}: a how-it-is-computed region sits outside the Sources area")
    if CALM_RX.search(rest):
        bad.append(f"{page}: its 'About this dashboard's data sources' disclosure sits outside the Sources area")
    if NOTE_RX.search(rest):
        bad.append(f"{page}: a how-it-is-computed note sits outside the Sources area: {NOTE_RX.search(rest).group(0)!r}")
    if _live(src):
        if MERGED_MARK in m.group(0):
            if NUDGE in m.group(0) or not re.match(r"\s*<script>\s*" + re.escape(NUDGE_CALL), src[m.end():]):
                bad.append(f"{page}: its Sources area hands the whSourcesSync nudge to the next script, and that script "
                           f"does not start with it - an older utils.js would leave the area hidden")
        elif NUDGE not in m.group(0):
            bad.append(f"{page}: its Sources area lacks the whSourcesSync nudge - an older utils.js would leave it hidden")
        if _OPEN_TAG + 'hidden ' not in m.group(0):
            bad.append(f"{page}: its Sources area does not ship hidden - it can paint before the page's content")
    elif _OPEN_TAG + 'hidden ' in m.group(0) and 'class="wh-sources-item"' in m.group(0):
        bad.append(f"{page}: a static page's Sources area ships hidden - nothing on the page would ever show its lines")
    for sid in slot_ids(src):
        t = _static_tag(src, sid)
        if t and COLLAPSED not in t.group(0):
            bad.append(f"{page}: #{sid} still keeps space at the top for a source line that now lives at the foot")
    return bad


_OPEN_TAG = '<section class="wh-sources" data-wh-sources aria-labelledby="wh-sources-title" '


COLUMN_TOKEN = re.compile(r"^(?:(?:sm|md|lg|xl):)?(?:max-w-\S+|mx-auto|px-\S+)$")


class _ClassStack(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, dict(attrs).get("class") or ""))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def _column_for(src: str, pos: int) -> str:
    """The content column a STATIC page's area should sit in, as the page's own Tailwind classes - '' when the area is
    already inside one (a calculator's <main> lives in its max-w-3xl column). ★A static page has no runtime to align
    the area (whSourcesArea is in utils.js, which these pages do not load): on the learn index and feedback the area
    sat in full-width <main> and its words touched the left edge of a phone (walked 2026-10-19)."""
    p = _ClassStack()
    p.feed(SCRIPT_RX.sub("", src[:pos]))
    if any("max-w-" in c for _, c in p.stack):
        return ""
    masked = _mask(src[:pos])
    last = None
    for m in re.finditer(r'\bclass="([^"]*\bmax-w-[^"]*)"', masked):
        if "mx-auto" in m.group(1):
            last = m.group(1)
    return " ".join(t for t in (last or "").split() if COLUMN_TOKEN.match(t))


def _columned(src: str) -> str:
    """A static page's area, its heading and list wrapped in the page's content column (see _column_for)."""
    m = AREA_RX.search(src)
    if not m or 'data-wh-sources-column' in m.group(0):
        return src
    col = _column_for(src, m.start())
    if not col:
        return src
    blk = m.group(0)
    h = blk.index('<h2 id="wh-sources-title"')
    end = blk.index("</section>")
    blk = blk[:h] + '<div class="' + col + '" data-wh-sources-column>\n' + blk[h:end] + "</div>\n" + blk[end:]
    return src[:m.start()] + blk + src[m.end():]


def _tidy(src: str) -> str:
    """The first version inserted the area after the </main> line's indent, leaving that indent on a line of its own;
    and every area ships hidden (see shell) - one written before that rule is brought under it."""
    src = re.sub(r"\n([ \t]+)\n(" + re.escape(OPEN_MARK) + r"[\s\S]*?" + re.escape(CLOSE_MARK) + r")\n</main>",
                 lambda m: "\n" + m.group(2) + "\n" + m.group(1) + "</main>", src)
    if not _live(src):
        return _columned(src)                # a static page's area is shown, has no runtime to nudge or align it
    src = src.replace(_OPEN_TAG + 'style=', _OPEN_TAG + 'hidden style=')
    m = AREA_RX.search(src)
    if m and NUDGE not in m.group(0) and MERGED_MARK not in m.group(0):   # an area written before the nudge existed
        blk = m.group(0)[:-len(CLOSE_MARK)].rstrip("\n") + "\n" + NUDGE + "\n" + CLOSE_MARK
        src = src[:m.start()] + blk + src[m.end():]
    return src


def _line_start(src: str, i: int) -> int:
    """`i` moved back to the start of its line when only indentation precedes it there."""
    ls = src.rfind("\n", 0, i) + 1
    return ls if src[ls:i].strip() == "" else i


def _reposition(src: str) -> str:
    """An area written after the page's trailing scripts (the first runs) moves to before them - see _foot_index."""
    m = AREA_RX.search(src)
    if not m:
        return src
    fi = _foot_index(src, m.start())
    if not re.search(r"<script\b", src[fi:m.start()]):
        return src
    block = m.group(0)
    end = m.end() + (1 if src[m.end():m.end() + 1] == "\n" else 0)
    src = src[:m.start()] + src[end:]
    at = _line_start(src, fi)
    return src[:at] + block + "\n" + src[at:]


def apply_to(src: str) -> str:
    found = AREA_RX.search(src)
    if found and _in_code(_code_spans(src), found.start()):
        raise ValueError("its Sources area is inside a script - restore the page and apply again")
    if not found:
        anchor = ANCHOR if _markup_find(src, ANCHOR) >= 0 else "</main>"
        i = _markup_find(src, anchor)
        if i < 0:
            raise ValueError("no </main> and no wh-sources anchor in the page's markup")
        at = _line_start(src, _foot_index(src, i))
        live = _live(src)
        if at == _line_start(src, i):            # nothing but whitespace before the anchor: keep its indent below the area
            head = src[:i]
            indent = re.search(r"[ \t]*$", head).group(0)
            src = head[:len(head) - len(indent)].rstrip("\n") + "\n" + shell(live=live) + "\n" + indent + src[i:]
        else:
            src = src[:at] + ("" if at == 0 or src[at - 1] == "\n" else "\n") + shell(live=live) + "\n" + src[at:]
    return _tidy(_reposition(collapse_slots(relocate(src))))


def run(apply: bool) -> int:
    pages = population()
    only = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")), None)
    if only == "root":
        pages = [p for p in pages if "/" not in p]
    elif only == "public":
        pages = [p for p in pages if "/" in p]
    bad, wrote = [], []
    for page in pages:
        p = ROOT / page
        src = p.read_text(encoding="utf-8")
        if apply:
            try:
                new = apply_to(src)
            except ValueError as e:
                bad.append(f"{page}: {e}")
                continue
            if new != src:
                p.write_text(new, encoding="utf-8", newline="")
                wrote.append(page)
                src = new
        bad += problems_of(page, src)
    for b in bad:
        print("  FAIL", b)
    if wrote:
        print("wrote", len(wrote), "page(s)")
    if bad:
        print(f"FAIL provenance-at-foot - {len(bad)} problem(s) across {len(pages)} page(s)")
        return 1
    print(f"PASS provenance-at-foot - {len(pages)} page(s) carry one Sources area at the foot of their content; no "
          f"static source line, explainer or how-it-is-computed note sits above it, and no slot keeps space for one")
    return 0


def self_test() -> int:
    page = ('<head><script src="utils.js"></script></head>' + '<main><h1>T</h1>\n<p class="wh-source-chip" role="status">Static · formula-only</p>\n<p>work</p>\n'
            '</main><script>renderSourceChip({})</script>')
    out = apply_to(page)
    cases = [
        ("the static line moved into the area", 'Static · formula-only</p>' in AREA_RX.search(out).group(0), True),
        ("nothing left at the top", 'class="wh-source-chip"' in outside(out), False),
        ("the area sits at the foot", bool(problems_of("t", out)), False),
        ("the area ships hidden even when it holds a line", 'title" hidden ' in AREA_RX.search(out).group(0), True),
        ("a page with no area is caught", bool(problems_of("t", page)), True),
        ("a note left above is caught", bool(problems_of("t", out.replace("<h1>T</h1>", "<h1>T</h1><p>How we compute this</p>"))), True),
        ("an area moved up is caught", bool(problems_of("t", AREA_RX.sub("", out).replace("<main>", "<main>" + shell(), 1))), True),
        ("a script mentioning the note is not provenance", bool(problems_of("t", out.replace("renderSourceChip({})</script>", "renderSourceChip({}); 'How we compute'</script>"))), False),
        ("an area without the skew-heal nudge is caught", bool(problems_of("t", out.replace(NUDGE, ""))), True),
        ("applying twice changes nothing", apply_to(out) == out, True),
        # index.html's form: the mark in the area, the call as the first line of the script after it
        ("the nudge merged into the next script holds",
         bool(problems_of("t", out.replace(NUDGE + "\n" + CLOSE_MARK, MERGED_MARK + "\n" + CLOSE_MARK + "\n<script>\n  " + NUDGE_CALL + "\n</script>"))), False),
        ("...and the merged form is left as it is by --apply",
         apply_to(out.replace(NUDGE + "\n" + CLOSE_MARK, MERGED_MARK + "\n" + CLOSE_MARK + "\n<script>\n  " + NUDGE_CALL + "\n</script>")).count(NUDGE), 0),
        ("the mark with no call in the next script is caught",
         bool(problems_of("t", out.replace(NUDGE + "\n" + CLOSE_MARK, MERGED_MARK + "\n" + CLOSE_MARK + "\n<script>\n  let x = 1;\n</script>"))), True),
    ]
    pg2 = ('<head><script src="utils.js"></script></head>' + '<main><h1>T</h1>\n<div id="card" class="hidden">\n  <button id="details-toggle-btn" type="button" '
           'aria-controls="x-summary-details">Show details</button>\n  <button id="keep">Recently deleted</button>\n'
           '  <div id="x-summary-details" role="region"><div><strong>How this is computed</strong></div></div>\n</div>\n'
           '<p id="slot" class="wh-source-chip" style="margin-top:4px;"></p><p>work</p></main>\n'
           '<style>#slot { min-height: 40px }\n#other{min-height:3px}</style>\n'
           '<script>const _c = document.getElementById(\'slot\');\n_c.innerHTML = renderSourceChip({});</script>')
    out2 = apply_to(pg2)
    area2 = AREA_RX.search(out2).group(0)
    cases += [
        ("the explainer and its toggle moved into the area", bool(problems_of("t", out2)), False),
        ("the explainer kept its nested content", "<div><strong>How this is computed</strong></div></div>" in area2, True),
        ("a control beside the toggle stays where it was", '<button id="keep">' in outside(out2), True),
        ("an anchor marks where the explainer was", '<span data-wh-source-anchor="x-summary-details" hidden></span>' in outside(out2), True),
        ("an explainer from a card shipped hidden starts hidden", 'data-wh-source-key="x-summary-details" hidden>' in area2, True),
        ("an area holding only hidden lines stays hidden", 'title" hidden ' in area2, True),
        ("the empty script slot is collapsed, keeping its id", '<p id="slot" hidden data-wh-sources-collapsed>' in out2, True),
        ("the slot's reserve rule is gone and a neighbour's is kept", "#slot {" not in out2 and "#other{min-height:3px}" in out2, True),
        ("an uncollapsed slot is caught", bool(problems_of("t", out2.replace(" hidden data-wh-sources-collapsed", ""))), True),
        ("applying twice changes nothing (explainer page)", apply_to(out2) == out2, True),
    ]
    pg3 = '<head><script src="utils.js"></script></head><main><h1>T</h1><p>work</p>\n  <script>wireDetailToggle()</script>\n  <!-- a note -->\n</main>'
    out3 = apply_to(pg3)
    late = pg3.replace("\n</main>", "\n" + shell() + "\n</main>")
    cases += [
        ("an area goes BEFORE the page's trailing scripts", out3.index(OPEN_MARK) < out3.index("<script>"), True),
        ("that placement passes", bool(problems_of("t", out3)), False),
        ("an area left after a script is caught", bool(problems_of("t", late)), True),
        ("an area left after a script is moved above it", apply_to(late).index(OPEN_MARK) < apply_to(late).index("<script>"), True),
    ]
    pg4 = ('<head><script src="utils.js"></script></head><main><h1>T</h1><p>work</p>\n<script>const report = `<main><footer>printed</footer></main>`;</script>\n'
           '<!-- a note that mentions <script> -->\n</main>')
    out4 = apply_to(pg4)
    cases += [
        ("a </main> inside a script is not the page's", "`<main><footer>printed</footer></main>`" in out4, True),
        ("the area lands in the page's markup", out4.index(OPEN_MARK) < out4.index("<script>"), True),
        ("that placement passes", bool(problems_of("t", out4)), False),
        ("an area written into a script is caught", bool(problems_of("t", pg4.replace("</footer></main>", "</footer>" + shell() + "</main>"))), True),
    ]
    pg5 = ('<head><script src="utils.js"></script></head>' + '<main><h1>T</h1><p>work</p>\n</main>\n<script>x()</script>\n'
           '<details data-calm-disclosure="data-sources" style="max-width:680px; margin:1rem auto 2rem;">'
           '<summary>About this dashboard\'s data sources</summary><p>Numbers come from your live data.</p></details>\n')
    out5 = apply_to(pg5)
    cases += [
        ("the calm data-sources disclosure folds into the area", 'data-calm-disclosure' in AREA_RX.search(out5).group(0), True),
        ("...with its own column layout dropped", 'max-width:680px' in out5, False),
        ("one left outside is caught", bool(problems_of("t", pg5.replace("</main>", shell() + "</main>"))), True),
        ("folding twice changes nothing", apply_to(out5) == out5, True),
    ]
    # a STATIC page (no utils.js - the calculators): the area ships shown with its line and needs no nudge
    pg6 = ('<main><nav>crumbs</nav><h1>OEE Calculator</h1>\n<p class="wh-source-chip" role="status">Static · formula-only'
           ' · no live data</p>\n<p>answer</p>\n<section><h2>Related</h2></section>\n</main>\n<footer>f</footer>')
    out6 = apply_to(pg6)
    area6 = AREA_RX.search(out6).group(0)
    cases += [
        ("a static page's area ships shown, holding its line", 'title" hidden ' not in area6 and "Static · formula-only" in area6, True),
        ("...and carries no nudge (no utils.js to run it)", NUDGE in area6, False),
        ("...and passes the gate", bool(problems_of("t", out6)), False),
        ("a static page's area left hidden is caught", bool(problems_of("t", out6.replace(_OPEN_TAG + "style=", _OPEN_TAG + "hidden style=", 1))), True),
        ("applying twice changes nothing (static page)", apply_to(out6) == out6, True),
    ]
    pg7 = ('<main><section><div class="max-w-4xl mx-auto px-5 sm:px-8 text-center"><h1>Learn</h1>\n'
           '<p class="wh-source-chip">Static · the library index</p></div></section>\n</main>')
    out7 = apply_to(pg7)
    pg8 = '<div class="max-w-3xl mx-auto px-5"><main><h1>T</h1>\n<p class="wh-source-chip">Static · formula-only</p>\n</main></div>'
    cases += [
        ("a static area in full-width <main> takes the page's column", 'class="max-w-4xl mx-auto px-5 sm:px-8" data-wh-sources-column' in out7, True),
        ("...one already inside a column does not", "data-wh-sources-column" in apply_to(pg8), False),
        ("columning twice changes nothing", apply_to(out7) == out7, True),
    ]
    ok = True
    for label, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {label}")
        ok &= got == want
    print("SELF-TEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run(apply="--apply" in sys.argv))
