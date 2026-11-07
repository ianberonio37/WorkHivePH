#!/usr/bin/env python3
"""prove_design_source_drift.py - the open-source design-source lens (2026-11-03).

Ian retired the Figma design lens on 2026-10-13 (20 metered MCP calls a month could not walk 31 pages) and kept the
design source in code: tokens.css and the shared components. On 2026-11-03 he asked for the open-source instruments
that do the job instead ("there are so many open source in github repos ... just extend my ideas"). This is the
code-side half: Project Wallace's css-analyzer (MIT) reads every served page's own CSS - its <style> blocks and style=""
attributes - plus the shared stylesheets, and tools/lib/wallace_drift.mjs sorts each value by what tokens.css says:

  exact      a colour literal that IS a token's value          (should be var(--token))
  tint       a palette colour at an alpha, hard-coded           (should be rgba(var(--token-rgb), a))
  off        a colour the palette does not have                 (drift - or a token the system is missing)
  fontSizes  distinct raw font sizes; families; zIndexes        (each a scale the system does not own)

The first reading (47 files): 93 exact, 3,669 tints, 705 off-palette, 563 raw font sizes, 113 raw z-indexes. The
synthesis it forced: the base background #0f1923 is hard-coded on 19 files with no token, and the navy palette has no
-rgb triplets, so every navy tint HAS to be a literal. The gate is a forward-only ratchet, the house shape
(design_detector_baseline.json): per (file :: metric) counts against design_source_drift_baseline.json, any rise
fails, a fix lowers the floor with --rebase, and a file missing from the baseline counts from 0 - a new page starts
on tokens.

  python tools/prove_design_source_drift.py --check       # the gate
  python tools/prove_design_source_drift.py --report      # the board + the palette's missing tokens, no verdict
  python tools/prove_design_source_drift.py --rebase      # after fixes: lower the floor (refuses a rise)
  python tools/prove_design_source_drift.py --self-test   # fixtures + teeth in a temp root
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = Path(__file__).resolve().parent / "lib" / "wallace_drift.mjs"
BASELINE_NAME = "design_source_drift_baseline.json"
METRICS = ("exact", "tint", "neutral", "off", "fontSizes", "families", "zIndexes")
# tokens.css defines the palette; maplibre-gl.css is a vendored library's own stylesheet, not WorkHive's design source
NOT_DESIGN_SOURCE = {"tokens.css", "maplibre-gl.css"}

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
_ATTR = re.compile(r"""\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def page_css(html: str) -> str:
    """A page's own CSS: its <style> blocks, and each style="" attribute as a one-rule block of its own."""
    html = _COMMENT.sub(" ", html)
    blocks = [m.group(1) for m in _STYLE.finditer(html)]
    attrs = [f".a{i}{{{m.group(1) if m.group(1) is not None else m.group(2)}}}" for i, m in enumerate(_ATTR.finditer(html))]
    return "\n".join(blocks + attrs)


# ★A var() IS NEVER FOLLOWED BY A NAME CHARACTER, AND NEVER OPENS A SELECTOR (GJ M11, 2026-11-07). The colour codemod read the
# id `#fab-post` as the colour #fab and wrote `var(--wh-rose-200, #fab)-post { ... }`: an invalid selector, so the browser
# dropped the whole rule and community's and marketplace's post buttons rendered as bare grey buttons after <main> - in
# production from cadf57fa. Both shapes are invalid CSS anywhere, so either one is a codemod's wound, not a style choice.
_CSS_NOTE = re.compile(r"/\*.*?\*/", re.S)
_MANGLED = re.compile(r"var\(--[\w-]+(?:,[^(){};]*)?\)[A-Za-z_-]|(?:^|[{};])\s*var\(--[\w-]+[^{};]*\{", re.M)


def mangled_selectors(root: Path, files: list[str]) -> list[str]:
    out = []
    for f in files:
        text = (root / f).read_text(encoding="utf-8", errors="replace")
        css = _CSS_NOTE.sub(" ", text if f.endswith(".css") else page_css(text))
        out += [f"{f}: {m.group(0).strip()[:70]}" for m in _MANGLED.finditer(css)]
    return out


def design_files(root: Path) -> list[str]:
    """The served pages the anti-slop ratchet reads (one roster for both design gates), plus the shared stylesheets."""
    sys.path.insert(0, str(root / "tools"))
    from prove_design_detector_ratchet import served_files  # noqa: E402
    pages = [f for f in served_files() if f.endswith(".html") and (root / f).exists()]
    css = sorted(p.name for p in root.glob("*.css") if p.name not in NOT_DESIGN_SOURCE)
    return pages + css


def measure(root: Path, files: list[str]) -> dict:
    items = []
    for f in files:
        text = (root / f).read_text(encoding="utf-8", errors="replace")
        items.append({"file": f, "css": text if f.endswith(".css") else page_css(text)})
    payload = json.dumps({"tokens": (root / "tokens.css").read_text(encoding="utf-8", errors="replace"), "items": items})
    r = subprocess.run(["node", str(HELPER)], input=payload, capture_output=True, text=True, encoding="utf-8", cwd=root)
    if r.returncode != 0:
        raise RuntimeError(f"wallace_drift.mjs failed: {r.stderr.strip()[:400]}")
    return json.loads(r.stdout)


# ★THE RATCHET COUNTS WHAT A PAGE TYPES, NOT WHICH BUCKET IT LANDS IN (2026-11-03). The first version ratcheted exact,
# tint and off separately - so declaring the token a page already typed (OD-S: --wh-ink-deep for rgb(15,25,35)) MOVED
# its literals from 'off' to 'exact' and read as a rise: growing the design system failed the gate built to grow it.
# A file's colour total (exact + tint + off) cannot rise when a token is added and can only fall when a literal becomes
# var(); the buckets stay in the report, where they say what kind of fix each literal needs.
# (2026-11-04) neutral joined the total too: declaring --wh-black-* moved black alphas from neutral to exact - the
# same re-bucketing, one bucket over. Every colour literal a page types is one count, whatever bucket names it.
RATCHETED = ("colour", "fontSizes", "families", "zIndexes")


def counts(m: dict) -> dict[str, int]:
    out = {}
    for f, v in m["files"].items():
        row = dict(v, colour=v.get("exact", 0) + v.get("tint", 0) + v.get("off", 0) + v.get("neutral", 0))
        out.update({f"{f} :: {k}": row[k] for k in RATCHETED if row.get(k)})
    return out


def compare(now: dict[str, int], base: dict[str, int]) -> tuple[list[str], list[str]]:
    rose = [f"{k}: {base.get(k, 0)} -> {v}" for k, v in sorted(now.items()) if v > base.get(k, 0)]
    fell = [f"{k}: {v} -> {now.get(k, 0)}" for k, v in sorted(base.items()) if now.get(k, 0) < v]
    return rose, fell


def missing_tokens(m: dict, min_files: int = 5) -> list[tuple[str, int]]:
    """An off-palette colour used on several files is not drift so much as a token the system never declared."""
    c = Counter(rgb for v in m["files"].values() for rgb in v.get("offRgbs", []))
    return [(k, n) for k, n in c.most_common() if n >= min_files]


def report(m: dict) -> str:
    tot = Counter()
    for v in m["files"].values():
        for k in METRICS:
            tot[k] += v.get(k, 0)
    lines = [f"design-source drift over {len(m['files'])} files (palette: {m['palette']} RGBs in tokens.css)",
             "  " + "  ".join(f"{k}={tot[k]}" for k in METRICS),
             "  worst off-palette: " + ", ".join(f"{f} {v['off']}" for f, v in
                                                sorted(m["files"].items(), key=lambda x: -x[1]["off"])[:8])]
    miss = missing_tokens(m)
    if miss:
        lines.append(f"  off-palette colours on >=5 files (a token the system is missing?): " +
                     ", ".join(f"rgb({k}) x{n}" for k, n in miss[:10]))
    return "\n".join(lines)


def load_baseline(root: Path) -> dict[str, int] | None:
    p = root / BASELINE_NAME
    return json.loads(p.read_text(encoding="utf-8"))["counts"] if p.exists() else None


def write_baseline(root: Path, c: dict[str, int], note: str) -> None:
    doc = {"_doc": "GENERATED by tools/prove_design_source_drift.py --rebase - per (file :: metric) counts of the values "
                   "a page's own CSS hard-codes instead of taking from tokens.css (Project Wallace css-analyzer). "
                   "Forward-only: a count may fall, never rise; a file missing here counts from 0.",
           "generated": date.today().isoformat(), "note": note, "counts": dict(sorted(c.items()))}
    (root / BASELINE_NAME).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "tokens.css").write_text(":root{--wh-orange:#F7A21B;--wh-orange-rgb:247, 162, 27;--wh-navy:#162032;"
                                         "--wh-text-muted:rgba(255, 255, 255, 0.80);}", encoding="utf-8")
        page = ("<html><head><style>.x{color:#F7A21B}.y{background:rgba(247,162,27,.2)}.z{color:#123456}"
                ".f{color:var(--wh-orange, #abcdef)}.g{background:rgba(var(--wh-orange-rgb), .3)}"
                ".s{font-size:13px}.v{font-size:var(--fs)}.r{font-size:inherit}.e{font-size:1.5em}.p{font-size:80%}"
                ".q{z-index:5}.m{color:rgba(255,255,255,.8)}.t{box-shadow:0 0 #0000;background:rgba(0,0,0,0)}"
                ".w{background:rgba(255,255,255,.07)}</style></head>"
                "<body><div style=\"color:#162032\"></div><!-- <div style=\"color:#999999\"></div> --></body></html>")
        (root / "a.html").write_text(page, encoding="utf-8")
        m = measure(root, ["a.html"])["files"]["a.html"]
        t("an exact token value is 'exact' (navy, orange, and text-muted's full rgba)", m["exact"] == 3)
        t("a palette colour at another alpha is 'tint' (orange .2, white .07)", m["tint"] == 2)
        t("an unknown colour is 'off'", m["off"] == 1 and m["offRgbs"] == ["18,52,86"])
        t("a var() fallback is excused (#abcdef not counted)", "171,205,239" not in m["offRgbs"])
        t("rgba(var(--token-rgb), a) is on the system (not counted)", m["tint"] == 2)
        t("a commented-out style attribute is not read", "153,153,153" not in m["offRgbs"])
        t("raw font sizes count; var() and relative ones (inherit / em / %) do not", m["fontSizes"] == 1)
        t("a raw z-index counts", m["zIndexes"] == 1)
        base = counts({"files": {"a.html": m}})
        # teeth: one more off-palette colour must rise; a new file with drift must rise; a fix must fall
        (root / "a.html").write_text(page.replace(".q{z-index:5}", ".q{z-index:5}.n{border-color:#00ff00}"),
                                     encoding="utf-8")
        rose, _ = compare(counts(measure(root, ["a.html"])), base)
        t("teeth: a new off-palette colour rises", any("a.html :: colour" in r for r in rose))
        (root / "b.html").write_text("<style>.k{color:#010203}</style>", encoding="utf-8")
        rose, _ = compare(counts(measure(root, ["a.html", "b.html"])), base)
        t("teeth: a new page outside the baseline counts from 0", any(r.startswith("b.html :: colour") for r in rose))
        (root / "a.html").write_text(page.replace(".z{color:#123456}", ".z{color:var(--wh-orange)}"), encoding="utf-8")
        rose, fell = compare(counts(measure(root, ["a.html"])), base)
        t("a fix (literal -> var) falls and nothing rises", not rose and any("a.html :: colour" in f for f in fell))
        # declaring a token the page already types moves its literal from off to exact - never a rise
        (root / "a.html").write_text(page, encoding="utf-8")
        (root / "tokens.css").write_text((root / "tokens.css").read_text(encoding="utf-8").replace("}", "--x:#123456;}"),
                                         encoding="utf-8")
        rose, _ = compare(counts(measure(root, ["a.html"])), base)
        t("a new token for a typed colour reclassifies it without a rise", not rose)
        (root / "c.html").write_text("<style>/* var(--x, #fab)-post in a note */.k{color:var(--wh-orange, #F7A21B)}"
                                     "var(--wh-rose-200, #fab)-post{left:0}</style>", encoding="utf-8")
        bad = mangled_selectors(root, ["c.html"])
        t("teeth: a selector a codemod turned into var(...)-post is caught (and a CSS comment is not)", len(bad) == 1)
        (root / "c.html").write_text("<style>#fab-post{color:var(--wh-orange, #F7A21B)}</style>", encoding="utf-8")
        t("a var() in a value position is not a mangled selector", not mangled_selectors(root, ["c.html"]))
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--rebase", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--root", default=str(ROOT), help="the site root to read (default: this repo)")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    root = Path(a.root).resolve()
    bad = mangled_selectors(root, design_files(root))
    if bad and not a.report:
        print(f"FAIL design-source-drift: {len(bad)} rule(s) where a var() sits in a SELECTOR - a colour codemod read an id "
              f"such as #fab-post as the colour #fab; restore the selector:")
        for b in bad[:20]:
            print("  " + b)
        return 1
    m = measure(root, design_files(root))
    now = counts(m)
    if a.report:
        print(report(m))
        return 0
    base = load_baseline(root)
    if a.rebase:
        if base is not None:
            rose, _ = compare(now, base)
            if rose:
                print(f"REFUSED --rebase: {len(rose)} count(s) rose; fix them first:")
                for r in rose[:20]:
                    print("  " + r)
                return 1
        write_baseline(root, now, a.note or ("first reading" if base is None else "lowered after fixes"))
        print(f"baseline written: {len(now)} (file :: metric) counts\n{report(m)}")
        return 0
    if base is None:
        print(f"FAIL design-source-drift: no {BASELINE_NAME} - run --rebase once to record the first reading")
        return 1
    rose, fell = compare(now, base)
    if rose:
        print(f"FAIL design-source-drift: {len(rose)} (file :: metric) count(s) ROSE - a page hard-codes a value "
              f"tokens.css owns (use var(--token) / rgba(var(--token-rgb), a), or add the missing token):")
        for r in rose[:40]:
            print("  " + r)
        return 1
    tail = f"; {len(fell)} fell - run --rebase to lower the floor" if fell else ""
    print(f"PASS design-source-drift - no page hard-codes more than its floor ({len(m['files'])} files, "
          f"{sum(now.values())} counted values{tail})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
