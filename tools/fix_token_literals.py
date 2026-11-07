#!/usr/bin/env python3
"""fix_token_literals.py - write a page's hand-typed token colours as the tokens they are (OD-D, 2026-11-03).

The open-source design lens (prove_design_source_drift.py, Project Wallace css-analyzer) found 1,213 colour literals that
ARE a token's value and 7,022 hand-typed tints of palette colours across the served pages. Most are not design decisions
- they are the token, typed. This rewrites them as what they are, and changes NOTHING a person sees:

  a literal equal to a token's full value (alpha included)  ->  var(--wh-x, <the literal>)
  a palette colour at an alpha, when the token has -rgb     ->  rgba(var(--wh-x-rgb, r, g, b), a)

★REPRESENTATION ONLY. The same RGB and the same alpha, byte for byte; the fallback is the literal itself, so a page that
does not load tokens.css renders exactly as before (component_purity_census.py already treats var(--token, #hex) as pure,
the async-load safety net). A contrast decision held elsewhere keeps its value: the learn ramp's 0.8 / 0.85 alphas stay
0.8 / 0.85 (and fix_learn_literal_alpha.py's DECL is widened to the var() form in the same change, or its check goes blind).

Not touched: @media print blocks (print is its own medium - its own tokens are OD-S rows), tokens.css itself, vendored
CSS, and the GENERATED families (learn/, tools/, wh-tw*.css) - their generator is the unit, a per-page edit is reverted by
the next build.

  python tools/fix_token_literals.py               # dry run: per-file counts
  python tools/fix_token_literals.py --apply [--only a.html,b.css]
  python tools/fix_token_literals.py --self-test
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

GENERATED = ("learn/", "tools/")
SKIP_CSS = {"tokens.css", "maplibre-gl.css"}
# ★A HEX IS NOT FOLLOWED BY A NAME CHARACTER (GJ M11, 2026-11-07). `\b` ends at '-', so `#fab` matched inside the id selector
# `#fab-post` and the page's FAB rule became `var(--wh-rose-200, #fab)-post { ... }` - an invalid selector, so community's
# and marketplace's post buttons shipped unstyled (an in-flow grey button after <main>) from cadf57fa until found; audit-log's
# `#feed` went the same way. proves_invisible() could not see it: the var() resolves to the literal, so the text "matched".
_HEX = r"#[0-9a-fA-F]{8}(?![\w-])|#[0-9a-fA-F]{6}(?![\w-])|#[0-9a-fA-F]{3,4}(?![\w-])"
_RGB = r"rgba?\(\s*[\d.]+%?\s*[, ]\s*[\d.]+%?\s*[, ]\s*[\d.]+%?\s*(?:[,/]\s*[\d.]+%?\s*)?\)"
COLOUR = re.compile(f"(?:{_HEX})|(?:{_RGB})")
VAR_OPEN = re.compile(r"var\(\s*--[\w-]+\s*,")


def rgba(lit: str):
    v = lit.strip().lower()
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(a, 3)
    n = [x for x in re.split(r"[\s,/()]+", v[v.index("(") + 1:]) if x]
    try:
        vals = [float(x[:-1]) / 100 if x.endswith("%") else float(x) for x in n]
    except ValueError:
        return None
    if len(vals) < 3:
        return None
    return int(vals[0]), int(vals[1]), int(vals[2]), round(vals[3] if len(vals) > 3 else 1.0, 3)


def _roots(tokens_css: str) -> str:
    """Every :root { } block - tokens.css declares tokens in more than one (the first parse read only the first, and
    never saw --wh-text-muted)."""
    return "\n".join(m.group(1) for m in re.finditer(r":root\s*\{([^}]*)\}", tokens_css))


def palette(tokens_css: str):
    root = _roots(tokens_css)
    exact, triplet = {}, {}
    for name, val in re.findall(r"(--wh-[\w-]+)\s*:\s*([^;]+);", root):
        val = val.strip()
        if name.endswith("-rgb") and re.fullmatch(r"\d+\s*,\s*\d+\s*,\s*\d+", val):
            triplet.setdefault(tuple(int(x) for x in val.split(",")), name)
        elif COLOUR.fullmatch(val):
            c = rgba(val)
            if c:
                exact.setdefault(c, name)
    return exact, triplet


def _in_selector(text: str, pos: int) -> bool:
    """Is pos in a SELECTOR rather than a declaration value? The next structural character at paren depth 0 decides: a
    selector runs into its rule's '{', a value into ';' or '}' (or the end of a style attribute). An all-hex id such as
    `#feed {` or `#add, .x {` is a selector and is never a colour (GJ M11, 2026-11-07)."""
    depth = 0
    for i in range(pos, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif not depth and ch in "{;}":
            return ch == "{"
    return False


def _in_var_fallback(text: str, pos: int) -> bool:
    """Is pos inside the fallback of a var(--x, ...)? (already excused - and must never be rewritten twice)

    Walk back to each enclosing '(' in turn; if any of them opens `var(--name,` with its comma before pos, the colour is
    a fallback. (rgba(var(--x-rgb, r, g, b), a) has its digits inside one - they are not a colour literal anyway.)"""
    depth = 0
    for i in range(pos - 1, -1, -1):
        ch = text[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth:
                depth -= 1
                continue
            if text[max(0, i - 3):i] == "var" and VAR_OPEN.match(text, i - 3) and \
                    VAR_OPEN.match(text, i - 3).end() <= pos:
                return True
        elif ch in "{};" and not depth:
            return False
    return False


# ★PRINT IS ITS OWN MEDIUM - until it has its own tokens (2026-11-04). The default leaves @media print alone: dark ink on
# paper is not the screen palette. OD-S then declared --wh-print-ink / --wh-print-rule / --wh-paper-rule, so a print
# block's #111 IS a token's value; --include-print rewrites inside print blocks too, under the same static proof.
INCLUDE_PRINT = False


def rewrite_css(css: str, exact: dict, triplet: dict) -> tuple[str, int]:
    """Rewrite one stretch of CSS; @media print blocks are left exactly as they are (unless INCLUDE_PRINT)."""
    if INCLUDE_PRINT:
        return _rewrite_plain(css, exact, triplet)
    out, n, i = [], 0, 0
    for m in re.finditer(r"@media\s+print[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", css):
        seg, k = _rewrite_plain(css[i:m.start()], exact, triplet)
        out += [seg, m.group(0)]
        n += k
        i = m.end()
    seg, k = _rewrite_plain(css[i:], exact, triplet)
    return "".join(out + [seg]), n + k


def _rewrite_plain(css: str, exact: dict, triplet: dict) -> tuple[str, int]:
    out, n, last = [], 0, 0
    for m in COLOUR.finditer(css):
        if _in_var_fallback(css, m.start()) or _in_selector(css, m.start()):
            continue
        c = rgba(m.group(0))
        if not c:
            continue
        rep = None
        if c in exact:
            rep = f"var({exact[c]}, {m.group(0)})"
        elif c[3] < 1 and c[:3] in triplet and not overlay_range(c):
            rep = f"rgba(var({triplet[c[:3]]}, {c[0]}, {c[1]}, {c[2]}), {_alpha(c[3])})"
        if rep:
            out += [css[last:m.start()], rep]
            last = m.end()
            n += 1
    css, n = "".join(out + [css[last:]]), n
    kw = {"white": exact.get((255, 255, 255, 1.0)), "black": exact.get((0, 0, 0, 1.0))}
    notes = [(c.start(), c.end()) for c in re.finditer(r"/\*.*?\*/", css, re.S)]

    def named(m):
        nonlocal n
        tok = kw.get(m.group(1))
        if not tok or _in_var_fallback(css, m.start()) or any(a <= m.start() < b for a, b in notes):
            return m.group(0)
        n += 1
        return f"var({tok}, {m.group(1)})"
    return KEYWORD.sub(named, css), n


def overlay_range(c) -> bool:
    """A white at alpha <= .20 or a black at any alpha below 1 is an OVERLAY - it belongs on the --wh-white-NN /
    --wh-black-NN steps, so it is never written through the bare -rgb triplet (that would type an off-scale alpha
    through a token and call it on the system)."""
    return c[3] < 1 and ((tuple(c[:3]) == (255, 255, 255) and c[3] <= 0.20) or tuple(c[:3]) == (0, 0, 0))


# ★AN OVERLAY ALPHA IS RETIRED BY WHAT IT PAINTS (OD-S, 2026-11-04). 95 overlay alphas sat between the scale's steps
# (white .03 / .09 / .14, black .25 / .4 ...). A white at .03 and at .04 over the platform's dark grounds paint colours
# an eye cannot tell apart, so --retire-overlay moves each onto the step whose COMPOSITE over every dark ground the
# pages use stays within the JND (CIE76 delta-E <= 2.3) - judged on the painted colour, not the alpha number, because
# the same alpha step means far more on a light ground. Past the JND it stays: a real design choice, a page call.
DARK_GROUNDS = ((15, 25, 35), (22, 32, 50), (31, 46, 69), (42, 61, 88))   # ink-deep, navy, navy-mid, navy-light
RETIRE_OVERLAY = False


def _composite(c, ground):
    a = c[3]
    return tuple(round(c[i] * a + ground[i] * (1 - a)) for i in range(3))


def _overlay_delta(a, b) -> float:
    """The largest CIE76 distance between two overlays' composites over any dark ground."""
    import math
    return max(math.dist(_lab3(_composite(a, g)), _lab3(_composite(b, g))) for g in DARK_GROUNDS)


def _overlay_steps(values: dict) -> list:
    out = []
    for n, v in values.items():
        if re.fullmatch(r"--wh-(white|black)-\d+", n) and COLOUR.fullmatch(v.strip()):
            out.append((n, rgba(v), v.strip()))
    return out


def retire_overlay(css: str, values: dict) -> tuple[str, int]:
    steps = _overlay_steps(values)
    out, n, last = [], 0, 0
    for m in COLOUR.finditer(css):
        if _in_var_fallback(css, m.start()) or _in_selector(css, m.start()):
            continue
        c = rgba(m.group(0))
        if not c or not overlay_range(c):
            continue
        cands = [(s, _overlay_delta(c, s[1])) for s in steps if tuple(s[1][:3]) == tuple(c[:3])]
        cands = [x for x in cands if x[1] <= JND]
        if not cands:
            continue
        (name, _rgb, val), _d = min(cands, key=lambda x: x[1])
        out += [css[last:m.start()], f"var({name}, {val})"]
        last = m.end()
        n += 1
    return "".join(out + [css[last:]]), n


def proves_overlay_within(old: str, new: str, values: dict) -> tuple[bool, str]:
    """Every difference is one overlay colour moved onto a declared step (fallback = the step's value), its composite
    over every dark ground within the JND; nothing else changed."""
    emit = re.compile(r"var\((--wh-(?:white|black)-\d+), (" + _RGB + r")\)")
    split = re.compile(r"(var\(--wh-(?:white|black)-\d+, " + _RGB + r"\)|" + _RGB + r"|" + _HEX + r")")
    pa, pb = split.split(old), split.split(new)
    if len(pa) != len(pb):
        return False, "the colour count differs"
    for x, y in zip(pa, pb):
        if x == y:
            continue
        e = emit.fullmatch(y)
        if not e or not (split.fullmatch(x) and not x.startswith("var(")):
            return False, f"non-overlay text changed: {x[:60]!r} -> {y[:60]!r}"
        tv = values.get(e.group(1), "").strip()
        if rgba(tv) != rgba(e.group(2)):
            return False, f"{y}: its fallback is not the step's value ({tv})"
        a, b = rgba(x), rgba(tv)
        if not overlay_range(a) or tuple(a[:3]) != tuple(b[:3]) or _overlay_delta(a, b) > JND:
            return False, f"{x} -> {y} paints past the JND over a dark ground"
    return True, ""


def _alpha(a: float) -> str:
    s = f"{a:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


_STYLE = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S | re.I)
_ATTR = re.compile(r"""(\sstyle\s*=\s*")([^"]*)(")""", re.I)


def _apply_html(html: str, fn) -> tuple[str, int]:
    """fn over each <style> block and style="" attribute of a page - the CSS a page carries itself."""
    total = 0

    def sub(m):
        nonlocal total
        s, k = fn(m.group(2))
        total += k
        return m.group(1) + s + m.group(3)
    return _ATTR.sub(sub, _STYLE.sub(sub, html)), total


def _apply_html_any(html: str, fn) -> tuple[str, int]:
    """fn over each <style> block (comments skipped) and each style attribute in EITHER quote."""
    total = 0

    def blk(m):
        nonlocal total
        s, k = outside_comments(fn)(m.group(2))
        total += k
        return m.group(1) + s + m.group(3)

    def att(m):
        nonlocal total
        q = m.group(2)
        s, k = fn(q[1:-1])
        total += k
        return m.group(1) + q[0] + s + q[-1]
    return _ATTR_ANY.sub(att, _STYLE.sub(blk, html)), total


def rewrite_html(html: str, exact: dict, triplet: dict) -> tuple[str, int]:
    total = 0

    def blk(m):
        nonlocal total
        s, k = rewrite_css(m.group(2), exact, triplet)
        total += k
        return m.group(1) + s + m.group(3)

    def att(m):
        nonlocal total
        q = m.group(2)
        s, k = _rewrite_plain(q[1:-1], exact, triplet)
        total += k
        return m.group(1) + q[0] + s + q[-1]

    # ★BOTH QUOTES (2026-11-04): markup a script builds writes style='...' as often as style="..."; the colour pass read
    # only the double-quoted form and left 141 exact token colours typed by hand that the drift lens (page_css) counts
    return _ATTR_ANY.sub(att, _STYLE.sub(blk, html)), total


# ★THE PROOF IS STATIC, NOT A SCREENSHOT (2026-11-03). A before/after computed-style diff of the live pages
# (tools/prove_token_rewrite_invisible.mjs) cannot bound pages that move on their own - alert-hub's chart bars and
# voice-journal's timed prompt changed between two loads of the SAME unrewritten file, at different elements each time.
# So every file is proven before it is written: resolve each emitted var() to the TOKEN'S declared value in tokens.css
# (never its fallback - that would prove nothing), normalise every colour on both sides to rgba(r,g,b,a), and the two
# texts must be identical. That holds the token == the literal it replaced AND that nothing else in the file moved.
_EMIT_VAR = re.compile(r"var\((--wh-[\w-]+), (?:" + _HEX + "|" + _RGB + r"|white|black)\)")
# ★A COLOUR KEYWORD IS A COLOUR (2026-11-04): after every hex and rgb() was named, the last literal on 11 pages was the word
# `white`. Only a keyword in VALUE position counts - after a colon or as the last word of a shorthand, followed by the
# end of the value - so `white-space`, `.text-white` and prose are never touched.
# lowercase only, and never inside a comment: the proof refused analytics-report the first time, where a NOTE said
# "this doc's WHITE print surface" - prose, not a value
KEYWORD = re.compile(r"(?<=[:\s])(white|black)(?=\s*(?:!important\s*)?[;}\"'\n]|\s*$)")
_KW_RGBA = {"white": "rgba(255,255,255,1.000)", "black": "rgba(0,0,0,1.000)"}
_EMIT_RGB = re.compile(r"rgba\(var\((--wh-[\w-]+-rgb), \d+, \d+, \d+\), ([\d.]+)\)")


def _canon(css: str) -> str:
    def c(m):
        v = rgba(m.group(0))
        return f"rgba({v[0]},{v[1]},{v[2]},{v[3]:.3f})" if v else m.group(0)
    css = KEYWORD.sub(lambda m: _KW_RGBA[m.group(1).lower()], css)
    return COLOUR.sub(c, css)


def proves_invisible(old: str, new: str, values: dict) -> tuple[bool, str]:
    """values: token name -> its declared value in tokens.css."""
    def var_val(m):
        return values[m.group(1)] if m.group(1) in values else "UNRESOLVED(" + m.group(1) + ")"

    def rgb_val(m):
        v = values.get(m.group(1))
        return f"rgba({v}, {m.group(2)})" if v else "UNRESOLVED(" + m.group(1) + ")"
    # a var() the page ALREADY had resolves the same way on both sides; only what the rewrite emitted can differ
    def resolve(css: str) -> str:
        return _EMIT_VAR.sub(var_val, _EMIT_RGB.sub(rgb_val, css))
    a, b = _canon(resolve(old)), _canon(resolve(new))
    if a == b:
        return True, ""
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return False, f"differs at char {i}: before {a[max(0, i - 40):i + 40]!r} | after {b[max(0, i - 40):i + 40]!r}"


# ★A NEAR-TWIN IS RETIRED ONLY BELOW WHAT AN EYE CAN TELL APART (2026-11-04). OD-S found colours typed a hair off a token
# - the learn/calculator glass header's rgb(13,24,36) x256 against --wh-ink-deep (15,25,35), delta-E 1.63. Moving them
# onto the token IS a value change, so it is not the invisible rewrite and does not borrow its proof: --retire-near-twins
# moves a colour only when CIE76 delta-E <= JND (2.3), keeps its alpha, and proves_within_jnd() holds that every
# difference between the files is one such colour and nothing else. Above the JND (#e5e7eb's six light greys, 2.44-2.82)
# a colour is a distinct one - a design call per page, never automated.
JND = 2.3
RETIRE = False


def _lab3(rgb):
    import open_design_census as odc  # noqa: E402 - one Lab conversion for the census and this
    return odc._lab(list(rgb))


def _near_token(c, values: dict):
    """(token name, its rgb) of the closest colour token within the JND, or None."""
    import math
    best = None
    for name, v in values.items():
        if name.endswith("-rgb") or not COLOUR.fullmatch(v.strip()):
            continue
        t = rgba(v)
        if not t or t[3] < 1:
            continue
        d = math.dist(_lab3(c[:3]), _lab3(t[:3]))
        if 0 < d <= JND and (best is None or d < best[2]):
            best = (name, t[:3], d)
    return best


def retire_plain(css: str, values: dict) -> tuple[str, int]:
    out, n, last = [], 0, 0
    for m in COLOUR.finditer(css):
        if _in_var_fallback(css, m.start()) or _in_selector(css, m.start()):
            continue
        c = rgba(m.group(0))
        hit = _near_token(c, values) if c else None
        if not hit:
            continue
        name, t, _d = hit
        trip = f"{name}-rgb"
        if c[3] >= 1:
            rep = f"var({name}, #{t[0]:02X}{t[1]:02X}{t[2]:02X})"
        elif trip in values:
            rep = f"rgba(var({trip}, {t[0]}, {t[1]}, {t[2]}), {_alpha(c[3])})"
        else:
            continue
        out += [css[last:m.start()], rep]
        last = m.end()
        n += 1
    return "".join(out + [css[last:]]), n


def proves_within_jnd(old: str, new: str, values: dict) -> tuple[bool, str]:
    """Every difference is one colour moved by delta-E <= JND with its alpha kept; nothing else changed."""
    import math

    def resolve(css: str) -> str:
        css = _EMIT_RGB.sub(lambda m: f"rgba({values.get(m.group(1), 'X')}, {m.group(2)})", css)
        return _EMIT_VAR.sub(lambda m: values.get(m.group(1), "UNRESOLVED"), css)
    a, b = _canon(resolve(old)), _canon(resolve(new))
    split = re.compile(r"(rgba\(\d+,\d+,\d+,[\d.]+\))")
    pa, pb = split.split(a), split.split(b)
    if len(pa) != len(pb):
        return False, "the colour count differs"
    for x, y in zip(pa, pb):
        if x == y:
            continue
        cx, cy = split.fullmatch(x), split.fullmatch(y)
        if not (cx and cy):
            return False, f"non-colour text changed: {x[:60]!r} -> {y[:60]!r}"
        vx, vy = rgba(x), rgba(y)
        if abs(vx[3] - vy[3]) > 1e-3 or math.dist(_lab3(vx[:3]), _lab3(vy[:3])) > JND:
            return False, f"{x} -> {y} moves more than the JND or changes alpha"
    return True, ""


def token_values(tokens_css: str) -> dict:
    return {n: v.strip() for n, v in re.findall(r"(--wh-[\w-]+)\s*:\s*([^;]+);", _roots(tokens_css))}


# ★THE TYPE SCALE IS THE SAME INVISIBLE MOVE, ON FONT SIZES (OD-S, 2026-11-04). tokens.css declares --wh-fs-* at the rem
# values pages already type, so `font-size: 0.85rem` -> `font-size: var(--wh-fs-sm, 0.85rem)` renders the same thing.
# Only rem is matched: 14px is 0.875rem only while the browser's base size is 16px, so moving a px size onto a rem token
# changes it for every reader who set a larger default - an accessibility decision, not a respelling. .75rem and
# 0.750rem are the same number as the token's 0.75rem and are matched on value; the fallback keeps the page's spelling.
TYPE = False
# ★PRINT HAS ITS OWN TYPE SCALE (2026-11-04): project-report and asset-hub's print sheet set paper in pt, so the print
# tokens are --wh-print-fs-* in pt and a size is matched within its own unit family - 12px is 9pt exactly, and a screen
# label must never be respelled as a print step.
_FS = re.compile(r"(font-size\s*:\s*)(\d*\.?\d+)(rem|pt)(?=\s*(?:!important\s*)?(?:[;}\"'\n]|$))", re.I)
_ATTR_ANY = re.compile(r"""(\sstyle\s*=\s*)("[^"]*"|'[^']*')""", re.I)
_SIZE_TOKEN = r"--wh-(?:print-)?fs-[\w-]+"


def _num(s: str) -> str:
    return f"{float(s):g}"


def fs_scale(values: dict) -> dict:
    """'0.85rem' -> '--wh-fs-sm' and '9pt' -> '--wh-print-fs-2xs': every size token, keyed by number + unit."""
    out = {}
    for n, v in values.items():
        m = re.fullmatch(r"(\d*\.?\d+)(rem|pt)", v)
        if m and ((n.startswith("--wh-fs-") and m.group(2) == "rem") or
                  (n.startswith("--wh-print-fs-") and m.group(2) == "pt")):
            out[_num(m.group(1)) + m.group(2)] = n
    return out


def rewrite_fs(css: str, scale: dict) -> tuple[str, int]:
    out, n, last = [], 0, 0
    for m in _FS.finditer(css):
        unit = m.group(3).lower()
        name = scale.get(_num(m.group(2)) + unit)
        if not name:
            continue
        out += [css[last:m.start()], f"{m.group(1)}var({name}, {m.group(2)}{unit})"]
        last = m.end()
        n += 1
    return "".join(out + [css[last:]]), n


def rewrite_fs_html(html: str, scale: dict) -> tuple[str, int]:
    """<style> blocks and style attributes in EITHER quote - the drift lens reads style='' too (page_css), so a
    double-quote-only pass would leave sizes it counts."""
    total = 0

    def blk(m):
        nonlocal total
        s, k = outside_comments(lambda c: rewrite_fs(c, scale))(m.group(2))   # a note keeps quoting what it describes
        total += k
        return m.group(1) + s + m.group(3)

    def att(m):
        nonlocal total
        q = m.group(2)
        s, k = rewrite_fs(q[1:-1], scale)
        total += k
        return m.group(1) + q[0] + s + q[-1]
    return _ATTR_ANY.sub(att, _STYLE.sub(blk, html)), total


_EMIT_FS = re.compile(r"var\((" + _SIZE_TOKEN + r"), \d*\.?\d+(?:rem|pt)\)")
_EMIT_FALLBACK = re.compile(r"var\((" + _SIZE_TOKEN + r"), (\d*\.?\d+)(rem|pt)\)")
_REM = re.compile(r"(?<![\w.])(\d*\.?\d+)(rem|pt)\b")


def _same_size(token_value: str, num: str, unit: str) -> bool:
    tv = re.fullmatch(r"(\d*\.?\d+)(rem|pt)", token_value or "")
    return bool(tv) and tv.group(2) == unit and _num(tv.group(1)) == _num(num)


def proves_fs_invisible(old: str, new: str, values: dict) -> tuple[bool, str]:
    """Resolve each emitted size var() to the TOKEN'S declared value (never its fallback), write every rem/pt number in
    one spelling on both sides, and require the two texts to be identical."""
    def canon(css: str) -> str:
        css = _EMIT_FS.sub(lambda m: values.get(m.group(1), "UNRESOLVED(" + m.group(1) + ")"), css)
        return _REM.sub(lambda m: _num(m.group(1)) + m.group(2), css)
    # the fallback is the first paint - it must be the token's own value, or the page paints one size and then another
    # (the colour fallbacks have the token-fallbacks-agree gate; the sizes are held here)
    for m in _EMIT_FALLBACK.finditer(new):
        if not _same_size(values.get(m.group(1)), m.group(2), m.group(3)):
            return False, f"{m.group(0)}: its fallback is not the token's value ({values.get(m.group(1))})"
    a, b = canon(old), canon(new)  # a var() the page already had resolves the same way on both sides
    if a == b:
        return True, ""
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return False, f"differs at char {i}: before {a[max(0, i - 40):i + 40]!r} | after {b[max(0, i - 40):i + 40]!r}"


# ★A SIZE IS RETIRED ONLY WITHIN HALF A PIXEL (OD-S, 2026-11-04). After the exact respell, 829 raw sizes remained: 204 are
# px sizes that ARE a scale step at the browser's 16px base (14px = 0.875rem), and 319 sit within half a pixel of one
# (0.78rem = 12.48px against the 0.8rem step's 12.8px). --retire-near-sizes moves each onto its step, as var(--wh-fs-x,
# <the step>): at the default base the px ones render identically, and they now follow a reader who set a larger default
# text size (a px size ignores that setting - WCAG 1.4.4's reason to prefer relative units). proves_size_within() holds
# that every difference between the files is one font-size moved by at most HALF_PX at a 16px base, its fallback the
# token's own value, and nothing else. Past half a pixel a size is a distinct one - a new step or a per-page call.
HALF_PX = 0.5
RETIRE_SIZES = False
_FS_ANY = re.compile(r"(font-size\s*:\s*)(\d*\.?\d+)(rem|px|pt)(?=\s*(?:!important\s*)?(?:[;}\"'\n]|$))", re.I)


def _px(n: float, unit: str) -> float:
    return n * 16 if unit == "rem" else n * 4 / 3 if unit == "pt" else n


# ★PAST HALF A PIXEL, THE NEAREST STEP - A VISIBLE MOVE, RECORDED AS ONE (OD-S, 2026-11-04). What the exact respell and
# the half-pixel retire left were ~95 sizes on ~20 pages (page titles at 1.3 / 1.4 / 1.6 / 1.8rem, stat numbers at 1.2 /
# 1.375 / 1.45 / 1.7rem, empty-state glyphs at 2 / 2.4 / 2.5rem) and the article family's h2 at 1.55rem. --snap-to-scale
# moves each to the NEAREST step of its medium (a tie goes to the larger step, so nothing loses prominence): the smallest
# change that puts the page on the scale. It is a value change, so it does not borrow the invisible proof:
# proves_snapped() holds that every moved size landed on exactly that nearest step and nothing else moved, and the
# rendered pages are re-measured by the overflow / text-grows / craft gates before anything ships.
SNAP = False


def _nearest(n: float, unit: str, scale: dict, on_paper: bool):
    paper = on_paper or unit == "pt"
    best = None
    for key, name in scale.items():
        km = re.fullmatch(r"(\d*\.?\d+)(rem|pt)", key)
        if (km.group(2) == "pt") != paper:
            continue
        sp = _px(float(km.group(1)), km.group(2))
        d = abs(_px(n, unit) - sp)
        if best is None or d < best[2] - 1e-9 or (abs(d - best[2]) <= 1e-9 and sp > best[3]):
            best = (name, key, d, sp)
    return best


def _near_step(n: float, unit: str, scale: dict, on_paper: bool = False):
    """(token, its value text) of the closest step within HALF_PX at a 16px base. The MEDIUM picks the family: paper
    (a pt size, or any size inside @media print - the analytics report sets its paper in rem) against the print pt
    steps, the screen (rem/px) against the rem steps. None if none, or if the size already IS that step."""
    paper = on_paper or unit == "pt"
    best = None
    for key, name in scale.items():
        km = re.fullmatch(r"(\d*\.?\d+)(rem|pt)", key)
        if (km.group(2) == "pt") != paper:
            continue
        d = abs(_px(n, unit) - _px(float(km.group(1)), km.group(2)))
        if d <= HALF_PX + 1e-9 and (best is None or d < best[2]):
            best = (name, key, d)
    if not best or (_num(str(n)) + unit == best[1]):
        return None
    return best[0], best[1]


_PRINT_BLOCK = re.compile(r"@media\s+print[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", re.I)


def retire_sizes(css: str, scale: dict) -> tuple[str, int]:
    # the medium is read off the WHOLE text and comments are skipped here, not split away first: a comment inside an
    # @media print block would otherwise cut the block from its header and hide that it is paper
    paper = [(m.start(), m.end()) for m in _PRINT_BLOCK.finditer(css)]
    notes = [(m.start(), m.end()) for m in _CSS_COMMENT.finditer(css)]
    out, n, last = [], 0, 0
    for m in _FS_ANY.finditer(css):
        if any(a <= m.start() < b for a, b in notes):
            continue
        on_paper = any(a <= m.start() < b for a, b in paper)
        if SNAP:
            nb = _nearest(float(m.group(2)), m.group(3).lower(), scale, on_paper)
            hit = (nb[0], nb[1]) if nb and _num(m.group(2)) + m.group(3).lower() != nb[1] else None
        else:
            hit = _near_step(float(m.group(2)), m.group(3).lower(), scale, on_paper)
        if not hit:
            continue
        out += [css[last:m.start()], f"{m.group(1)}var({hit[0]}, {hit[1]})"]
        last = m.end()
        n += 1
    return "".join(out + [css[last:]]), n


def retire_sizes_html(html: str, scale: dict) -> tuple[str, int]:
    total = 0

    def blk(m):
        nonlocal total
        s, k = retire_sizes(m.group(2), scale)
        total += k
        return m.group(1) + s + m.group(3)

    def att(m):
        nonlocal total
        q = m.group(2)
        s, k = retire_sizes(q[1:-1], scale)
        total += k
        return m.group(1) + q[0] + s + q[-1]
    return _ATTR_ANY.sub(att, _STYLE.sub(blk, html)), total


def proves_size_within(old: str, new: str, values: dict) -> tuple[bool, str]:
    """Every difference is one font size moved by <= HALF_PX at a 16px base, its fallback the token's value; nothing else."""
    split = re.compile(r"(font-size\s*:\s*(?:var\(" + _SIZE_TOKEN + r", \d*\.?\d+(?:rem|pt)\)|\d*\.?\d+(?:rem|px|pt)))",
                       re.I)
    pa, pb = split.split(old), split.split(new)
    if len(pa) != len(pb):
        return False, "the font-size count differs"

    def size(decl: str):
        v = re.search(r"var\((" + _SIZE_TOKEN + r"), (\d*\.?\d+)(rem|pt)\)", decl)
        if v:
            if not _same_size(values.get(v.group(1)), v.group(2), v.group(3)):
                return None
            return _px(float(v.group(2)), v.group(3))
        mm = re.search(r"(\d*\.?\d+)(rem|px|pt)", decl, re.I)
        return _px(float(mm.group(1)), mm.group(2).lower()) if mm else None
    for x, y in zip(pa, pb):
        if x == y:
            continue
        if not (split.fullmatch(x) and split.fullmatch(y)):
            return False, f"non-size text changed: {x[:60]!r} -> {y[:60]!r}"
        a, b = size(x), size(y)
        if a is None or b is None or abs(a - b) > HALF_PX + 1e-9:
            return False, f"{x} -> {y} moves more than half a pixel (or names an undeclared token, or a wrong fallback)"
    return True, ""


def proves_snapped(old: str, new: str, values: dict) -> tuple[bool, str]:
    """Every difference is one font size moved onto the NEAREST step of its medium (tie -> the larger), its fallback the
    token's value; nothing else changed."""
    scale = fs_scale(values)
    split = re.compile(r"(font-size\s*:\s*(?:var\(" + _SIZE_TOKEN + r", \d*\.?\d+(?:rem|pt)\)|\d*\.?\d+(?:rem|px|pt)))",
                       re.I)
    pa, pb = split.split(old), split.split(new)
    if len(pa) != len(pb):
        return False, "the font-size count differs"
    for x, y in zip(pa, pb):
        if x == y:
            continue
        if not (split.fullmatch(x) and split.fullmatch(y)):
            return False, f"non-size text changed: {x[:60]!r} -> {y[:60]!r}"
        raw = re.search(r":\s*(\d*\.?\d+)(rem|px|pt)$", x, re.I)
        v = re.search(r"var\((" + _SIZE_TOKEN + r"), (\d*\.?\d+)(rem|pt)\)", y)
        if not raw or not v or not _same_size(values.get(v.group(1)), v.group(2), v.group(3)):
            return False, f"{x} -> {y}: not a raw size onto a declared token with its own value as fallback"
        nb = _nearest(float(raw.group(1)), raw.group(2).lower(), scale, v.group(1).startswith("--wh-print-fs-"))
        if not nb or nb[0] != v.group(1):
            return False, f"{x} -> {y}: the nearest step is {nb and nb[0]}, not {v.group(1)}"
    return True, ""


# The generators' templates write NEW family pages (the shipped page is the source - targets()). Their CSS sits in Python
# strings, so they are read as plain text: the size patterns only ever occur inside that CSS.
TEMPLATES = ("tools/build_calc_pages.py", "tools/build_pillar_pages.py", "tools/scaffold_article.py")
ON_TEMPLATES = False


def targets(root: Path) -> list[str]:
    """Every served page and hand-written stylesheet. ★THE SHIPPED PAGE IS THE SOURCE (2026-11-04): the first version
    skipped the generated families (learn/, tools/) on the theory that a per-page edit is reverted by the next build.
    It is not - since 2026-10-23 a generator writes NEW pages only (build_calc_pages.py stages, never overwrites;
    build_pillar_pages.py needs --force), because the shipped pages carry fixes their templates never got (measured
    tonight: 196 lines between the calculator template and a shipped calculator page, the OWN text-grows rule among
    them). So the family's pages are rewritten where they ship, and the templates get the same rewrite for new pages.
    wh-tw*.css stays out of the default pass: the CDN writes it, so --tailwind respells it as its own roster, and
    tools/tw_public_build.mjs runs that after every build - a rebuild re-applies the respelling instead of reverting it."""
    sys.path.insert(0, str(root / "tools"))
    from prove_design_source_drift import design_files  # noqa: E402 - the gate's own roster
    if ON_TEMPLATES:
        return [t for t in TEMPLATES if (root / t).exists()]
    if TAILWIND:
        return [f for f in design_files(root) if f.startswith("wh-tw")]
    return [f for f in design_files(root) if not f.startswith("wh-tw") and f not in SKIP_CSS]


TAILWIND = False
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def outside_comments(fn):
    """fn over the CSS between comments only. ★A SHEET'S HEADER IS DATA (2026-11-04): a compiled Tailwind sheet records
    the config it was built from in its header comment, and tw-public-sheets compares that JSON with the manifest - the
    first --tailwind pass respelled the config's own colours and the gate read every public sheet as stale."""
    def g(css: str) -> tuple[str, int]:
        out, n, last = [], 0, 0
        for m in _CSS_COMMENT.finditer(css):
            s, k = fn(css[last:m.start()])
            out += [s, m.group(0)]
            n += k
            last = m.end()
        s, k = fn(css[last:])
        return "".join(out + [s]), n + k
    return g


def _proof_name() -> str:
    return ('proven within the JND over every dark ground' if RETIRE_OVERLAY else 'proven on the nearest step' if SNAP else 'proven within half a pixel' if RETIRE_SIZES else 'proven within the JND' if RETIRE
            else 'proven invisible')


def run(root: Path, apply: bool, only: set | None) -> int:
    tok = (root / "tokens.css").read_text(encoding="utf-8")
    exact, triplet = palette(tok)
    values = token_values(tok)
    grand, refused = 0, 0
    for f in targets(root):
        if only and f not in only:
            continue
        p = root / f
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        plain = f.endswith(".css") or f.endswith(".py")   # a template's CSS lives in its Python strings: read as text
        if RETIRE_OVERLAY:
            fn = lambda c: retire_overlay(c, values)  # noqa: E731
            new, n = outside_comments(fn)(text) if plain else _apply_html_any(text, fn)
        elif RETIRE_SIZES:
            scale = fs_scale(values)
            new, n = (retire_sizes(text, scale) if plain
                      else retire_sizes_html(text, scale))
        elif TAILWIND:
            scale = fs_scale(values)
            new, n = outside_comments((lambda c: rewrite_fs(c, scale)) if TYPE else (lambda c: rewrite_css(c, exact, triplet)))(text)
        elif TYPE and plain:
            scale = fs_scale(values)
            new, n = rewrite_fs(text, scale)
        elif TYPE:
            scale = fs_scale(values)
            new, n = (rewrite_fs(text, scale) if f.endswith(".css") else rewrite_fs_html(text, scale))
        elif RETIRE:
            new, n = (retire_plain(text, values) if f.endswith(".css") else _apply_html(text, lambda c: retire_plain(c, values)))
        else:
            new, n = (rewrite_css(text, exact, triplet) if f.endswith(".css") else rewrite_html(text, exact, triplet))
        if n:
            ok, why = (proves_overlay_within if RETIRE_OVERLAY else proves_snapped if SNAP
                       else proves_size_within if RETIRE_SIZES else proves_fs_invisible if TYPE
                       else proves_within_jnd if RETIRE else proves_invisible)(text, new, values)
            if not ok:
                refused += 1
                print(f"  REFUSED {f}: the rewrite would change what renders - {why}")
                continue
            grand += n
            print(f"  {f:<40} {n:>5} literal(s)  {_proof_name()}")
            if apply:
                nl = "\r\n" if b"\r\n" in raw else "\n"
                p.write_text(new.replace("\r\n", "\n"), encoding="utf-8", newline=nl)
    print(f"{'rewrote' if apply else 'would rewrite'} {grand} literal(s), each file {_proof_name()}; palette: "
          f"{len(exact)} token values, {len(triplet)} -rgb triplets" + (f"; {refused} file(s) REFUSED" if refused else ""))
    return 1 if refused else 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    tok = (":root{--wh-orange:#F7A21B;--wh-orange-rgb:247, 162, 27;--wh-text-muted:rgba(255, 255, 255, 0.80);"
           "--wh-navy:#162032;}")
    exact, triplet = palette(tok)
    s, n = _rewrite_plain(".a{color:#F7A21B}.b{background:rgba(247,162,27,.2)}.c{color:rgba(255,255,255,0.8)}", exact, triplet)
    t("an exact token value becomes var(token, literal)", "var(--wh-orange, #F7A21B)" in s)
    t("a tint with a triplet becomes rgba(var(--x-rgb, r,g,b), a) - same alpha", "rgba(var(--wh-orange-rgb, 247, 162, 27), 0.2)" in s)
    t("an rgba token's full value is exact", "var(--wh-text-muted, rgba(255,255,255,0.8))" in s and n == 3)
    ex2, tr2 = palette(tok.replace("}", "--wh-rose-200:#fab;}"))
    s, n = _rewrite_plain("#fab-post{color:#fab}#fab-post:hover{border-color:#fab}#fab, .x{color:#fab}", ex2, tr2)
    t("a hex-looking id selector is never a colour (#fab-post, #fab {) - only the values are rewritten",
      s.startswith("#fab-post{") and "#fab-post:hover{" in s and "#fab, .x{" in s and n == 3)
    s, n = _rewrite_plain(".n{background:rgba(22,32,50,.5)}", exact, triplet)
    t("a tint with NO triplet is left as it is (its triplet is an OD-S row)", n == 0)
    s, n = _rewrite_plain(".f{color:var(--wh-orange, #F7A21B)}", exact, triplet)
    t("a literal already inside a var() fallback is not rewritten again", n == 0 and s.count("var(") == 1)
    s, n = rewrite_css(".x{color:#F7A21B}@media print{.p{color:#F7A21B}}", exact, triplet)
    t("@media print is left exactly as it is", n == 1 and "@media print{.p{color:#F7A21B}}" in s)
    h, n = rewrite_html('<style>.x{color:#162032}</style><div style="color:#F7A21B"></div><svg fill="#F7A21B">', exact, triplet)
    t("html: style blocks and style attributes only - an svg attribute is not CSS", n == 2 and 'fill="#F7A21B"' in h)
    s, _ = rewrite_css(".a{color:#F7A21B}.b{background:rgba(247,162,27,.2)}.c{color:rgba(255,255,255,0.8)}"
                       "@media print{.p{color:#F7A21B}}", exact, triplet)
    s2, n2 = rewrite_css(s, exact, triplet)
    t("idempotent: a second pass rewrites nothing", n2 == 0 and s2 == s)
    t("an unknown colour is left as it is", _rewrite_plain(".z{color:#123456}", exact, triplet)[1] == 0)
    vals = token_values(tok)
    src = ".a{color:#F7A21B}.b{background:rgba(247,162,27,.2)}.c{color:rgba(255,255,255,0.8)}"
    new, _ = rewrite_css(src, exact, triplet)
    t("the static proof holds a correct rewrite", proves_invisible(src, new, vals)[0])
    t("teeth: a token whose value is NOT the literal is caught",
      not proves_invisible(src, new, dict(vals, **{"--wh-orange": "#F7A21C"}))[0])
    t("teeth: a rewrite that drops a neighbouring character is caught",
      not proves_invisible(src, new.replace("}.b{", ".b{", 1), vals)[0])
    t("teeth: a var() the tokens do not declare is caught",
      not proves_invisible(src, new, {k: v for k, v in vals.items() if k != "--wh-orange-rgb"})[0])
    vals2 = dict(vals, **{"--wh-ink-deep": "#0F1923", "--wh-ink-deep-rgb": "15, 25, 35"})
    src2 = ".h{background:rgba(13,24,36,0.85)}.g{color:#c0c0c0}.k{color:#123456}"
    new2, n2 = retire_plain(src2, vals2)
    t("retire: a JND-close tint moves onto the token's triplet, alpha kept",
      "rgba(var(--wh-ink-deep-rgb, 15, 25, 35), 0.85)" in new2)
    t("retire: a colour with no token within the JND is left alone", ".k{color:#123456}" in new2 and n2 == 1)
    t("retire: the JND proof holds a sub-JND move", proves_within_jnd(src2, new2, vals2)[0])
    t("teeth: the JND proof refuses a move past the JND",
      not proves_within_jnd(".a{color:#123456}", ".a{color:#FFFFFF}", vals2)[0])
    t("teeth: the JND proof refuses a changed non-colour character",
      not proves_within_jnd(src2, new2.replace("background", "backgrounx"), vals2)[0])
    fv = {"--wh-fs-2xs": "0.75rem", "--wh-fs-sm": "0.85rem", "--wh-fs-base": "1rem"}
    sc = fs_scale(fv)
    src3 = ".a{font-size:0.85rem}.b{font-size: .75rem !important}.c{font-size:14px}.d{font-size:0.78rem;padding:.75rem}"
    new3, n3 = rewrite_fs(src3, sc)
    t("type: an on-scale rem size becomes var(--wh-fs-x, its own spelling)",
      "font-size:var(--wh-fs-sm, 0.85rem)" in new3 and "font-size: var(--wh-fs-2xs, .75rem) !important" in new3)
    t("type: px is not respelled as rem (a reader's larger default would change it)", "font-size:14px" in new3)
    t("type: an off-scale size and a non-font rem are left alone", "font-size:0.78rem" in new3 and "padding:.75rem" in new3
      and n3 == 2)
    t("type: idempotent", rewrite_fs(new3, sc)[1] == 0)
    h3, hn = rewrite_fs_html("<style>.x{font-size:1rem}</style><p style='font-size:0.85rem'></p><i style=\"font-size:1rem\">",
                             sc)
    t("type: style blocks and BOTH attribute quotes", hn == 3 and "style='font-size:var(--wh-fs-sm, 0.85rem)'" in h3)
    t("type: the static proof holds a correct rewrite", proves_fs_invisible(src3, new3, fv)[0])
    t("teeth: a size token whose value is NOT the literal is caught",
      not proves_fs_invisible(src3, new3, dict(fv, **{"--wh-fs-sm": "0.875rem"}))[0])
    t("teeth: a dropped neighbouring character is caught", not proves_fs_invisible(src3, new3.replace("}.b", ".b", 1), fv)[0])
    t("teeth: an undeclared size token is caught",
      not proves_fs_invisible(src3, new3, {k: v for k, v in fv.items() if k != "--wh-fs-2xs"})[0])
    t("teeth: an exact respell whose fallback is not the token's value is caught",
      not proves_fs_invisible(src3, new3.replace("var(--wh-fs-sm, 0.85rem)", "var(--wh-fs-sm, 0.95rem)"), fv)[0])
    fv2 = {"--wh-fs-xs": "0.8rem", "--wh-fs-sm-plus": "0.875rem", "--wh-fs-lg": "1.25rem"}
    sc2 = fs_scale(fv2)
    src4 = ".a{font-size:0.78rem}.b{font-size:14px}.c{font-size:0.7rem}.d{font-size:0.8rem}"
    new4, n4 = retire_sizes(src4, sc2)
    t("retire: a size within half a pixel moves onto its step; a px step becomes the rem token",
      ".a{font-size:var(--wh-fs-xs, 0.8rem)}" in new4 and ".b{font-size:var(--wh-fs-sm-plus, 0.875rem)}" in new4)
    t("retire: past half a pixel (0.7rem = 11.2px) and an exact rem are left alone",
      ".c{font-size:0.7rem}" in new4 and ".d{font-size:0.8rem}" in new4 and n4 == 2)
    t("retire: the half-pixel proof holds a correct move", proves_size_within(src4, new4, fv2)[0])
    t("teeth: a wrong fallback is caught", not proves_size_within(src4, new4.replace("0.8rem)", "0.85rem)", 1), fv2)[0])
    t("teeth: a move past half a pixel is caught",
      not proves_size_within(src4, new4.replace("var(--wh-fs-xs, 0.8rem)", "var(--wh-fs-lg, 1.25rem)", 1), fv2)[0])
    t("teeth: a changed neighbour is caught", not proves_size_within(src4, new4.replace(".b{", ".x{"), fv2)[0])
    pv = {"--wh-fs-2xs": "0.75rem", "--wh-print-fs-2xs": "9pt", "--wh-print-fs-xl": "18pt"}
    psc = fs_scale(pv)
    p1, pn = rewrite_fs(".k{font-size:18pt}.l{font-size:9pt}.m{font-size:13pt}", psc)
    t("print: a pt size on the print scale becomes var(--wh-print-fs-x, its pt); an off-scale pt is left",
      ".k{font-size:var(--wh-print-fs-xl, 18pt)}" in p1 and ".m{font-size:13pt}" in p1 and pn == 2)
    t("print: the static proof holds the pt respell", proves_fs_invisible(".k{font-size:18pt}.l{font-size:9pt}.m{font-size:13pt}",
                                                                          p1, pv)[0])
    p2, _ = retire_sizes(".n{font-size:12px}.o{font-size:8.8pt}", psc)
    t("print: 12px (= 9pt) goes to the SCREEN step; 8.8pt retires to the print step",
      ".n{font-size:var(--wh-fs-2xs, 0.75rem)}" in p2 and ".o{font-size:var(--wh-print-fs-2xs, 9pt)}" in p2)
    t("print: the half-pixel proof holds a pt retire", proves_size_within(".n{font-size:12px}.o{font-size:8.8pt}", p2, pv)[0])
    pv2 = dict(pv, **{"--wh-print-fs-4xs": "8pt"})
    src5 = ".s{font-size:0.66rem}@media print{ /* paper */ .s{font-size:0.66rem} }"
    p3, n5 = retire_sizes(src5, fs_scale(pv2))
    t("print: inside @media print (past a comment) a rem size retires to the PRINT step; on screen it does not",
      p3.startswith(".s{font-size:0.66rem}") and "var(--wh-print-fs-4xs, 8pt)" in p3 and n5 == 1)
    global SNAP
    sv = {"--wh-fs-lg": "1.25rem", "--wh-fs-xl": "1.5rem", "--wh-fs-2xl": "1.75rem"}
    SNAP = True
    try:
        src6 = ".h{font-size:1.4rem}.t{font-size:1.375rem}.k{font-size:1.25rem}"
        p6, n6 = retire_sizes(src6, fs_scale(sv))
    finally:
        SNAP = False
    t("snap: a size moves to the NEAREST step; a tie goes to the larger; an on-step size stays",
      ".h{font-size:var(--wh-fs-xl, 1.5rem)}" in p6 and ".t{font-size:var(--wh-fs-xl, 1.5rem)}" in p6
      and ".k{font-size:1.25rem}" in p6 and n6 == 2)
    t("snap: the nearest-step proof holds it", proves_snapped(src6, p6, sv)[0])
    t("teeth: a snap to a step that is NOT the nearest is caught",
      not proves_snapped(src6, p6.replace("var(--wh-fs-xl, 1.5rem)", "var(--wh-fs-2xl, 1.75rem)", 1), sv)[0])
    kt = ":root{--wh-white:#FFFFFF;--wh-black:#000000;}"
    kex, ktr = palette(kt)
    ks, kn = _rewrite_plain(".a{color:white}.b{border:1px solid black;white-space:nowrap}.text-white{}", kex, ktr)
    t("keyword: a value-position white/black becomes var(token, keyword); white-space and .text-white are untouched",
      ".a{color:var(--wh-white, white)}" in ks and "solid var(--wh-black, black)" in ks and "white-space:nowrap" in ks
      and ".text-white{}" in ks and kn == 2)
    t("keyword: the static proof holds it", proves_invisible(".a{color:white}", ".a{color:var(--wh-white, white)}",
                                                            token_values(kt))[0])
    hdr = '/* built\n   config: {"orange":"#F7A21B"} */\n.a{color:#F7A21B}'
    hn, hk = outside_comments(lambda c: rewrite_css(c, exact, triplet))(hdr)
    t("tailwind: a colour inside a comment (the sheet's recorded config) is left alone; the rule is respelled",
      '{"orange":"#F7A21B"}' in hn and ".a{color:var(--wh-orange, #F7A21B)}" in hn and hk == 1)
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--include-print", action="store_true", help="also rewrite inside @media print (print tokens exist)")
    ap.add_argument("--retire-near-twins", action="store_true", help="move colours within the JND (delta-E <= 2.3) onto their token")
    ap.add_argument("--census-twins", action="store_true",
                    help="with --retire-near-twins: the census rule, delta-E < 3 (a colour that close to a token is a mistyped token)")
    ap.add_argument("--near-de", type=float, default=None,
                    help="with --retire-near-twins: an explicit delta-E bound (a VISIBLE unification past the JND - each move proven within it)")
    ap.add_argument("--type-scale", action="store_true", help="respell on-scale rem font sizes as var(--wh-fs-*, size)")
    ap.add_argument("--tailwind", action="store_true", help="the compiled Tailwind sheets (wh-tw*.css) instead of the pages")
    ap.add_argument("--retire-near-sizes", action="store_true",
                    help="move font sizes within half a pixel of a --wh-fs-* step (16px base) onto it, px included")
    ap.add_argument("--templates", action="store_true", help="the three generator templates instead of the pages")
    ap.add_argument("--retire-overlay", action="store_true", help="move overlay alphas onto the --wh-white/black steps within the JND")
    ap.add_argument("--snap-to-scale", action="store_true",
                    help="move every remaining size to the NEAREST step of its medium - a visible change")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    global INCLUDE_PRINT, RETIRE, TYPE, TAILWIND, RETIRE_SIZES, ON_TEMPLATES, SNAP, RETIRE_OVERLAY
    INCLUDE_PRINT = a.include_print
    RETIRE = a.retire_near_twins
    global JND
    if a.census_twins:      # open_design_census merges clusters at delta-E < 3: one rule for finding and for fixing
        JND = 2.99
    if a.near_de:
        JND = a.near_de
    TYPE = a.type_scale
    TAILWIND = a.tailwind
    RETIRE_SIZES = a.retire_near_sizes
    ON_TEMPLATES = a.templates
    SNAP = a.snap_to_scale
    RETIRE_OVERLAY = a.retire_overlay
    RETIRE_SIZES = RETIRE_SIZES or SNAP
    return run(ROOT, a.apply, {x.strip() for x in a.only.split(",") if x.strip()} or None)


if __name__ == "__main__":
    sys.exit(main())
