#!/usr/bin/env python3
"""fix_stacking_tokens.py - the stacking (z-index) scale, written so no page's layers change order (OD-S, 2026-11-04).

The pages typed 31 distinct z-index values (254 declarations). A z-index only matters RELATIVE to the other layers that
can meet it, so a remap is invisible exactly when, in every context where layers meet, every pair keeps its order and no
two distinct values become one. A context is one page: its own <style> and style="" layers, the stylesheets it links,
and the fixed points nobody remaps - the z-indexes its scripts set (el.style.zIndex, z-index inside a JS string) and the
shell scripts' chrome (the FAB, the companion, the feedback drawer, the consent sheet, the skip link).

  1. census()   every raw z-index per file, and every page's context
  2. ladder()   sort the values; walk them in order and merge a value into the current rung only if no context holds
                it together with any value already on that rung. The map is monotone, so order is kept; a merge never
                joins two values one context holds, so no tie is made. Each rung takes the value of its LARGEST member,
                so a rung never sinks below a layer it used to clear.
  3. names      a rung is named by the role of the layers on it (read off their selectors), not by its number.
  4. proves_order_kept()  recomputes every context's order before and after and requires them identical.

  python tools/fix_stacking_tokens.py                # the ladder, and what would be rewritten
  python tools/fix_stacking_tokens.py --tokens       # the :root block to declare in tokens.css
  python tools/fix_stacking_tokens.py --apply        # rewrite (tokens.css must already declare the rungs)
  python tools/fix_stacking_tokens.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

SHELL_SCRIPTS = ("utils.js", "nav-hub.js", "maturity-gate.js", "wh-feedback-fab.js", "offline-banner.js")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_Z = re.compile(r"(z-index\s*:\s*)(-?\d+)(?=\s*(?:!important\s*)?(?:[;}\"'\n]|$))", re.I)
_JS_Z = re.compile(r"zIndex\s*=\s*['\"]?(-?\d+)|z-index\s*:\s*(-?\d+)")
_STYLE = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S | re.I)
_ATTR = re.compile(r"""(\sstyle\s*=\s*)("[^"]*"|'[^']*')""", re.I)
_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)

# role words read off a selector -> the rung's name; first match wins, in this order
ROLES = [("skip", "skip-link"), ("retired", "retired"), ("toast", "toast"), ("consent", "consent"),
         ("fb-drawer", "drawer"), ("drawer", "drawer"), ("levelup", "celebration"), ("modal", "modal"),
         ("preview", "modal"), ("sheet", "sheet"), ("overlay", "overlay"), ("gate", "gate"), ("dropdown", "menu"),
         ("menu", "menu"), ("tooltip", "tooltip"), ("compare", "bar"), ("toolbar", "bar"), ("tabs", "bar"),
         ("bottom-nav", "nav"), ("fab", "fab"), ("sticky", "sticky"), ("header", "sticky"), ("aurora", "art"),
         ("scene", "art"), ("glow", "art"), ("page", "base"), ("layout", "base")]


def page_css(html: str) -> str:
    import prove_design_source_drift as dsd
    return dsd.page_css(html)


def design_files() -> list[str]:
    import prove_design_source_drift as dsd
    return dsd.design_files(ROOT)


def _raw_layers(css: str) -> list[tuple[int, str]]:
    """(value, selector) for every raw z-index in a stretch of CSS (comments skipped, var() ones are already tokens)."""
    out = []
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", _COMMENT.sub(" ", css)):
        for z in _Z.finditer(m.group(2)):
            out.append((int(z.group(2)), re.sub(r"\s+", " ", m.group(1).strip())[-80:]))
    return out


_TAG_STYLE = re.compile(r"""<(\w+)([^>]*?)\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)


def _html_layers(html: str) -> list[tuple[int, str]]:
    """<style> layers by selector, and style="" layers by their element's id or class - page_css() renames an attribute
    rule .aN, which would leave the skip link (z 10001 on 121 pages) with no role to be named by."""
    out = []
    for m in _STYLE.finditer(html):
        out += _raw_layers(m.group(2))
    for m in _TAG_STYLE.finditer(html):
        body = m.group(3) if m.group(3) is not None else m.group(4)
        ident = re.search(r"""\b(?:id|class)\s*=\s*["']([^"']{0,60})""", m.group(2))
        for z in _Z.finditer(body):
            out.append((int(z.group(2)), f"<{m.group(1)} {ident.group(1) if ident else ''}>"))
    return out


def census(root: Path = ROOT):
    files = design_files()
    texts = {f: (root / f).read_text(encoding="utf-8", errors="replace") for f in files}
    own = {f: (_raw_layers(t) if f.endswith(".css") else _html_layers(t)) for f, t in texts.items()}
    chrome = set()
    for s in SHELL_SCRIPTS:
        p = root / s
        if p.exists():
            for m in _JS_Z.finditer(p.read_text(encoding="utf-8", errors="replace")):
                chrome.add(int(m.group(1) or m.group(2)))
    sheets = [f for f in files if f.endswith(".css")]
    ctx = {}
    for f, t in texts.items():
        if f.endswith(".css"):
            continue
        fixed = set(chrome)
        for sm in _SCRIPT.finditer(t):          # a page's own scripts set layers too; they are fixed points
            for m in _JS_Z.finditer(sm.group(1)):
                fixed.add(int(m.group(1) or m.group(2)))
        linked = [s for s in sheets if re.search(r"""href=["'][^"']*""" + re.escape(s), t)]
        vals = {v for v, _ in own[f]} | {v for s in linked for v, _ in own[s]}
        ctx[f] = (vals, fixed)
    return own, ctx, chrome


def ladder(own: dict, ctx: dict):
    """[(rung value, [member values])] - monotone, merging only values no context holds together."""
    vals = sorted({v for layers in own.values() for v, _ in layers})
    together = [vals_c | fixed for vals_c, fixed in ctx.values()]
    rungs, cur = [], []
    for v in vals:
        clash = any(v in c and any(u in c for u in cur) for c in together)
        if cur and not clash:
            cur.append(v)
        else:
            if cur:
                rungs.append(cur)
            cur = [v]
    if cur:
        rungs.append(cur)
    return [(max(r), r) for r in rungs]


def existing_z(tokens_css: str) -> dict:
    """--wh-z-* names tokens.css already declares -> their value (int when numeric)."""
    out = {}
    for n, v in re.findall(r"(--wh-z-[\w-]+)\s*:\s*([^;]+);", tokens_css):
        v = v.strip()
        out[n] = int(v) if re.fullmatch(r"-?\d+", v) else v
    return out


def names(rungs, own: dict, taken: dict | None = None) -> dict:
    """member value -> token name, by the roles of the layers on the rung; a clash of names is made unique by rank.
    ★A NAME tokens.css ALREADY HOLDS IS TAKEN (2026-11-04): --wh-z-sticky is 100 and --wh-z-modal 1100 there, used
    through var() - declaring the 3 and the 50 rungs under those names would restack every existing use. An existing
    name is reused only when its value IS the rung's value."""
    taken = taken or {}
    sel = defaultdict(list)
    for layers in own.values():
        for v, s in layers:
            sel[v].append(s.lower())
    used, out = set(), {}
    for value, members in rungs:
        role = "layer"
        for word, r in ROLES:
            if any(word in s for m in members for s in sel[m]):
                role = r
                break
        name, k = f"--wh-z-{role}", 2
        while name in used or (name in taken and taken[name] != value):
            name, k = f"--wh-z-{role}-{k}", k + 1
        used.add(name)
        for m in members:
            out[m] = (name, value)
    return out


def proves_order_kept(ctx: dict, mapping: dict) -> tuple[bool, str]:
    """In every context, the order of every pair - its remapped layers and its fixed points - is unchanged."""
    def to(v, fixed):
        return mapping[v][1] if v in mapping and v not in fixed else v
    for page, (vals, fixed) in ctx.items():
        allv = sorted(vals | fixed)
        for i, a in enumerate(allv):
            for b in allv[i + 1:]:
                na, nb = to(a, fixed) if a in vals else a, to(b, fixed) if b in vals else b
                if not na < nb:
                    return False, f"{page}: {a} < {b} became {na} vs {nb}"
    return True, ""


def rewrite(css: str, mapping: dict) -> tuple[str, int]:
    out, n, last = [], 0, 0
    for m in _Z.finditer(css):
        v = int(m.group(2))
        if v not in mapping:
            continue
        name, value = mapping[v]
        out += [css[last:m.start()], f"{m.group(1)}var({name}, {value})"]
        last = m.end()
        n += 1
    return "".join(out + [css[last:]]), n


def rewrite_html(html: str, mapping: dict) -> tuple[str, int]:
    total = 0

    def blk(m):
        nonlocal total
        s, k = rewrite(m.group(2), mapping)
        total += k
        return m.group(1) + s + m.group(3)

    def att(m):
        nonlocal total
        q = m.group(2)
        s, k = rewrite(q[1:-1], mapping)
        total += k
        return m.group(1) + q[0] + s + q[-1]
    return _ATTR.sub(att, _STYLE.sub(blk, html)), total


def plan():
    own, ctx, chrome = census()
    rungs = ladder(own, ctx)
    mapping = names(rungs, own, existing_z((ROOT / "tokens.css").read_text(encoding="utf-8")))
    return own, ctx, chrome, rungs, mapping


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    own, ctx, chrome, rungs, mapping = plan()
    ok, why = proves_order_kept(ctx, mapping)
    if "--tokens" in sys.argv:
        print("  /* The stacking scale (OD-S): one rung per role, merged only where no page holds two of its values. */")
        for value, members in rungs:
            print(f"  {mapping[members[0]][0]}: {value};   /* was {', '.join(map(str, members))} */")
        return 0
    print(f"{sum(len(l) for l in own.values())} raw z-index declarations, {len({v for l in own.values() for v, _ in l})} "
          f"values -> {len(rungs)} rungs; shell chrome fixed points {sorted(chrome)}")
    for value, members in rungs:
        print(f"  {mapping[members[0]][0]:<24} {value:>7}  <- {members}")
    print(f"order kept in every one of {len(ctx)} page contexts: {ok}" + ("" if ok else f" ({why})"))
    if not ok:
        return 1
    if "--apply" not in sys.argv:
        return 0
    tokens = (ROOT / "tokens.css").read_text(encoding="utf-8")
    missing = sorted({n for n, _ in mapping.values() if not re.search(re.escape(n) + r"\s*:", tokens)})
    if missing:
        print(f"REFUSED: tokens.css does not declare {missing} - add the --tokens block first")
        return 1
    total = 0
    for f in design_files():
        if f == "tokens.css":
            continue
        p = ROOT / f
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        if f.startswith("wh-tw"):
            # the compiled Tailwind sheets carry their z-utilities too (z-10 .. z-[60]); their header comment is data
            # (tw-public-sheets compares its config), so only the CSS between comments is respelled
            from fix_token_literals import outside_comments  # noqa: E402
            new, n = outside_comments(lambda c: rewrite(c, mapping))(text)
        else:
            new, n = rewrite(text, mapping) if f.endswith(".css") else rewrite_html(text, mapping)
        if n:
            nl = "\r\n" if b"\r\n" in raw else "\n"
            p.write_text(new.replace("\r\n", "\n"), encoding="utf-8", newline=nl)
            total += n
    print(f"rewrote {total} z-index declaration(s)")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)
    own = {"a.html": [(5, ".x"), (200, ".toast")], "b.html": [(10, ".y"), (9999, ".toast")],
           "c.html": [(5, ".p"), (10, ".q")]}
    ctx_free = {"a.html": ({5, 200}, set()), "b.html": ({10, 9999}, set())}
    r = ladder(own, ctx_free)
    t("values no page holds together merge onto one rung (5 and 10)", any(set(m) >= {5, 10} for _, m in r))
    ctx_clash = dict(ctx_free, **{"c.html": ({5, 10}, set())})
    r2 = ladder(own, ctx_clash)
    t("values one page holds together stay on separate rungs", not any(set(m) >= {5, 10} for _, m in r2))
    m2 = names(r2, own)
    m3 = names([(3, [3])], {"x": [(3, ".sticky-head")]}, {"--wh-z-sticky": 100})
    t("an existing token name with a different value is not reused", m3[3][0] != "--wh-z-sticky")
    m4 = names([(100, [100])], {"x": [(100, ".sticky-head")]}, {"--wh-z-sticky": 100})
    t("an existing token name with the SAME value is reused", m4[100][0] == "--wh-z-sticky")
    t("every remap keeps every page's order", proves_order_kept(ctx_clash, m2)[0])
    bad = dict(m2)
    bad[10] = (bad[10][0], 1)
    t("teeth: a rung moved below a layer it used to clear is caught", not proves_order_kept(ctx_clash, bad)[0])
    t("teeth: a fixed point a script sets is never crossed",
      not proves_order_kept({"d.html": ({5}, {6})}, {5: ("--wh-z-x", 7)})[0])
    s, n = rewrite(".a{z-index:5}.b{z-index: var(--wh-z-base, 1)}", {5: ("--wh-z-lift", 10)})
    t("rewrite writes var(token, rung value) and leaves a var() alone", s == ".a{z-index:var(--wh-z-lift, 10)}"
      ".b{z-index: var(--wh-z-base, 1)}" and n == 1)
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
