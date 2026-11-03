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
_HEX = r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b"
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
        if _in_var_fallback(css, m.start()):
            continue
        c = rgba(m.group(0))
        if not c:
            continue
        rep = None
        if c in exact:
            rep = f"var({exact[c]}, {m.group(0)})"
        elif c[3] < 1 and c[:3] in triplet:
            rep = f"rgba(var({triplet[c[:3]]}, {c[0]}, {c[1]}, {c[2]}), {_alpha(c[3])})"
        if rep:
            out += [css[last:m.start()], rep]
            last = m.end()
            n += 1
    return "".join(out + [css[last:]]), n


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


def rewrite_html(html: str, exact: dict, triplet: dict) -> tuple[str, int]:
    total = 0

    def blk(m):
        nonlocal total
        s, k = rewrite_css(m.group(2), exact, triplet)
        total += k
        return m.group(1) + s + m.group(3)

    def att(m):
        nonlocal total
        s, k = _rewrite_plain(m.group(2), exact, triplet)
        total += k
        return m.group(1) + s + m.group(3)

    return _ATTR.sub(att, _STYLE.sub(blk, html)), total


# ★THE PROOF IS STATIC, NOT A SCREENSHOT (2026-11-03). A before/after computed-style diff of the live pages
# (tools/prove_token_rewrite_invisible.mjs) cannot bound pages that move on their own - alert-hub's chart bars and
# voice-journal's timed prompt changed between two loads of the SAME unrewritten file, at different elements each time.
# So every file is proven before it is written: resolve each emitted var() to the TOKEN'S declared value in tokens.css
# (never its fallback - that would prove nothing), normalise every colour on both sides to rgba(r,g,b,a), and the two
# texts must be identical. That holds the token == the literal it replaced AND that nothing else in the file moved.
_EMIT_VAR = re.compile(r"var\((--wh-[\w-]+), (?:" + _HEX + "|" + _RGB + r")\)")
_EMIT_RGB = re.compile(r"rgba\(var\((--wh-[\w-]+-rgb), \d+, \d+, \d+\), ([\d.]+)\)")


def _canon(css: str) -> str:
    def c(m):
        v = rgba(m.group(0))
        return f"rgba({v[0]},{v[1]},{v[2]},{v[3]:.3f})" if v else m.group(0)
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
        if _in_var_fallback(css, m.start()):
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


def targets(root: Path) -> list[str]:
    """Every served page and hand-written stylesheet. ★THE SHIPPED PAGE IS THE SOURCE (2026-11-04): the first version
    skipped the generated families (learn/, tools/) on the theory that a per-page edit is reverted by the next build.
    It is not - since 2026-10-23 a generator writes NEW pages only (build_calc_pages.py stages, never overwrites;
    build_pillar_pages.py needs --force), because the shipped pages carry fixes their templates never got (measured
    tonight: 196 lines between the calculator template and a shipped calculator page, the OWN text-grows rule among
    them). So the family's pages are rewritten where they ship, and the templates get the same rewrite for new pages.
    wh-tw*.css stays out: it IS rebuilt from the Tailwind config, so its colours are fixed there."""
    sys.path.insert(0, str(root / "tools"))
    from prove_design_source_drift import design_files  # noqa: E402 - the gate's own roster
    return [f for f in design_files(root) if not f.startswith("wh-tw") and f not in SKIP_CSS]


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
        if RETIRE:
            new, n = (retire_plain(text, values) if f.endswith(".css") else _apply_html(text, lambda c: retire_plain(c, values)))
        else:
            new, n = (rewrite_css(text, exact, triplet) if f.endswith(".css") else rewrite_html(text, exact, triplet))
        if n:
            ok, why = (proves_within_jnd if RETIRE else proves_invisible)(text, new, values)
            if not ok:
                refused += 1
                print(f"  REFUSED {f}: the rewrite would change what renders - {why}")
                continue
            grand += n
            print(f"  {f:<40} {n:>5} literal(s)  {'proven within the JND' if RETIRE else 'proven invisible'}")
            if apply:
                nl = "\r\n" if b"\r\n" in raw else "\n"
                p.write_text(new.replace("\r\n", "\n"), encoding="utf-8", newline=nl)
    print(f"{'rewrote' if apply else 'would rewrite'} {grand} literal(s), each file {'proven within the JND' if RETIRE else 'proven invisible'}; palette: "
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
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--include-print", action="store_true", help="also rewrite inside @media print (print tokens exist)")
    ap.add_argument("--retire-near-twins", action="store_true", help="move colours within the JND (delta-E <= 2.3) onto their token")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    global INCLUDE_PRINT, RETIRE
    INCLUDE_PRINT = a.include_print
    RETIRE = a.retire_near_twins
    return run(ROOT, a.apply, {x.strip() for x in a.only.split(",") if x.strip()} or None)


if __name__ == "__main__":
    sys.exit(main())
