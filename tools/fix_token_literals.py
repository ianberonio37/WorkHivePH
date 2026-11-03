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


def palette(tokens_css: str):
    root = tokens_css[tokens_css.index(":root"):]
    root = root[:root.index("}")]
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


def rewrite_css(css: str, exact: dict, triplet: dict) -> tuple[str, int]:
    """Rewrite one stretch of CSS; @media print blocks are left exactly as they are."""
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


def targets(root: Path) -> list[str]:
    sys.path.insert(0, str(root / "tools"))
    from prove_design_source_drift import design_files  # noqa: E402 - the gate's own roster
    return [f for f in design_files(root) if not f.startswith(GENERATED) and not f.startswith("wh-tw")
            and f not in SKIP_CSS]


def run(root: Path, apply: bool, only: set | None) -> int:
    exact, triplet = palette((root / "tokens.css").read_text(encoding="utf-8"))
    grand = 0
    for f in targets(root):
        if only and f not in only:
            continue
        p = root / f
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        new, n = (rewrite_css(text, exact, triplet) if f.endswith(".css") else rewrite_html(text, exact, triplet))
        if n:
            grand += n
            print(f"  {f:<40} {n:>5} literal(s)")
            if apply:
                nl = "\r\n" if b"\r\n" in raw else "\n"
                p.write_text(new.replace("\r\n", "\n"), encoding="utf-8", newline=nl)
    print(f"{'rewrote' if apply else 'would rewrite'} {grand} literal(s); palette: {len(exact)} token values, "
          f"{len(triplet)} -rgb triplets")
    return 0


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
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return run(ROOT, a.apply, {x.strip() for x in a.only.split(",") if x.strip()} or None)


if __name__ == "__main__":
    sys.exit(main())
