#!/usr/bin/env python3
"""fix_token_fallbacks.py - a var() fallback must say what its token says (2026-11-03).

`var(--wh-orange-text, #F7A21B)` is how the shared chrome survives tokens.css arriving late (it loads async): until the
token resolves, the fallback IS the colour a person sees. Found while proving the OD-D token rewrite invisible: 30
fallbacks across the pages and the shared chrome disagreed with the token they stand in for - and they disagreed the same
way every time. They were STALE COPIES of the token's older value. --wh-orange-text was raised #F7A21B -> #FDB94A for APCA
contrast (2026-07-24), --wh-red-text #FCA5A5 -> #FDC9C9, --wh-text-muted to 0.80; the tokens moved and ten, five and one
fallbacks did not. So the first paint of nav-hub, utils and a dozen pages showed the colour the platform had already
measured as too faint, then flashed to the right one.

  python tools/fix_token_fallbacks.py            # the gate: every var(--wh-x, <colour>) fallback equals tokens.css
  python tools/fix_token_fallbacks.py --apply    # set each disagreeing fallback to the token's own value
  python tools/fix_token_fallbacks.py --self-test

A fallback is compared as a colour (rgba, alpha included), so `#fdb94a` and `#FDB94A` agree; a token whose value is not a
plain colour (a gradient, another var) is not judged.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fix_token_literals import COLOUR, _HEX, _RGB, rgba, token_values  # noqa: E402 - one colour parser for both tools

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

FALLBACK = re.compile(r"(var\(\s*(--wh-[\w-]+)\s*,\s*)(" + _HEX + "|" + _RGB + r")(\s*\))")


def files(root: Path) -> list[str]:
    from prove_design_source_drift import design_files  # noqa: E402 - the served roster
    out = [f for f in design_files(root) if f != "tokens.css"]
    out += sorted(p.name for p in root.glob("*.js") if p.name not in ("sw.js",))
    return out


def scan(text: str, values: dict) -> list[tuple[int, int, str, str, str]]:
    """(start, end, token, fallback, token value) for each fallback that disagrees."""
    out = []
    for m in FALLBACK.finditer(text):
        name, fb = m.group(2), m.group(3)
        tv = values.get(name)
        if not tv or not COLOUR.fullmatch(tv.strip()):
            continue
        a, b = rgba(tv), rgba(fb)
        if a and b and a != b:
            out.append((m.start(3), m.end(3), name, fb, tv.strip()))
    return out


def fix(text: str, values: dict) -> tuple[str, int]:
    hits = scan(text, values)
    for s, e, _n, _fb, tv in reversed(hits):
        text = text[:s] + tv + text[e:]
    return text, len(hits)


def run(apply: bool) -> int:
    values = token_values((ROOT / "tokens.css").read_text(encoding="utf-8"))
    total, where = 0, []
    for f in files(ROOT):
        p = ROOT / f
        if not p.exists():
            continue
        raw = p.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        hits = scan(text, values)
        if not hits:
            continue
        total += len(hits)
        where.append((f, hits))
        if apply:
            new, _ = fix(text, values)
            nl = "\r\n" if b"\r\n" in raw else "\n"
            p.write_text(new.replace("\r\n", "\n"), encoding="utf-8", newline=nl)
    if apply:
        print(f"set {total} fallback(s) in {len(where)} file(s) to their token's value")
        return 0
    if total:
        print(f"FAIL token-fallbacks-agree: {total} var() fallback(s) disagree with tokens.css - the first paint shows a "
              f"colour the token no longer holds (run --apply):")
        for f, hits in where[:20]:
            for _s, _e, n, fb, tv in hits[:3]:
                print(f"  {f}: {n} falls back to {fb}, the token is {tv}")
        return 1
    print(f"PASS token-fallbacks-agree - every var(--wh-x, colour) fallback equals its token ({len(files(ROOT))} files)")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    vals = {"--wh-orange-text": "#FDB94A", "--wh-text-muted": "rgba(255, 255, 255, 0.80)", "--wh-grad": "linear-gradient(x)"}
    src = (".a{color:var(--wh-orange-text, #F7A21B)} .b{color:var(--wh-orange-text, #fdb94a)}"
           ".c{color:var(--wh-text-muted, rgba(255,255,255,0.62))} .d{color:var(--wh-text-muted,rgba(255,255,255,.8))}"
           ".e{background:var(--wh-grad, #000)} .f{color:var(--wh-unknown, #123456)}")
    hits = scan(src, vals)
    t("a stale fallback is caught (orange-text #F7A21B)", any(h[2] == "--wh-orange-text" and h[3] == "#F7A21B" for h in hits))
    t("a fallback that differs only in case agrees", sum(1 for h in hits if h[2] == "--wh-orange-text") == 1)
    t("an rgba fallback is compared with its alpha (0.62 vs 0.80 caught, .8 agrees)",
      sum(1 for h in hits if h[2] == "--wh-text-muted") == 1)
    t("a token that is not a plain colour is not judged; an undeclared token is not judged", len(hits) == 2)
    fixed, n = fix(src, vals)
    t("--apply writes the token's own value", n == 2 and "var(--wh-orange-text, #FDB94A)" in fixed
      and "var(--wh-text-muted, rgba(255, 255, 255, 0.80))" in fixed)
    t("idempotent: a fixed file has nothing left", scan(fixed, vals) == [])
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else run(a.apply)


if __name__ == "__main__":
    sys.exit(main())
