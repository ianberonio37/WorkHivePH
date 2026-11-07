#!/usr/bin/env python3
"""copy_locate.py - the SOURCE lines that hold a page's B3/B1 offenders (Wave CF, 2026-11-08).

Reads .tmp/copy/<slug>.json (tools/copy_offenders.mjs) and prints each source line that holds one or more offending
sentences or verbose blocks, once, with the offender numbers it holds - the lines a rewrite map works from.

    python tools/copy_locate.py learn/ph-industrial-benchmarks-intelligence/index.html
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_rewrite import pattern, protected  # noqa: E402

page = Path(sys.argv[1])
parts = page.as_posix().split("/")
slug = parts[-2] if parts[-1] == "index.html" and len(parts) > 1 else parts[-1].replace(".html", "")
d = json.loads((Path(".tmp/copy") / f"{slug}.json").read_text(encoding="utf-8"))
src = page.read_text(encoding="utf-8")
prot = protected(src)
starts = [0] + [i + 1 for i, ch in enumerate(src) if ch == "\n"]


def line_of(pos: int) -> int:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


items = []
for t in (d.get("b3") or {}).get("long", []) + (d.get("b3") or {}).get("passive", []) + \
        [o["text"] for o in (d.get("b3") or {}).get("overGrade", [])]:
    if t not in items:
        items.append(t)
blocks = list(d.get("b1") or [])
lines: dict = {}
missing = []
for i, t in enumerate(items):
    hits = [m for m in pattern(t).finditer(src) if not any(a <= m.start() < b for a, b in prot)]
    if not hits:
        missing.append(f"S{i}: {t[:90]}")
    for m in hits:
        lines.setdefault(line_of(m.start()), []).append(f"S{i}")
for j, b in enumerate(blocks):
    words = b.split()
    probe = " ".join(words[:6])
    hits = [m for m in pattern(probe).finditer(src) if not any(a <= m.start() < bb for a, bb in prot)] if len(words) >= 6 else []
    for m in hits[:1]:
        lines.setdefault(line_of(m.start()), []).append(f"B{j}")
src_lines = src.split("\n")
sys.stdout.reconfigure(encoding="utf-8")
for n in sorted(lines):
    print(f"--- L{n} [{' '.join(lines[n])}]")
    print(src_lines[n - 1].strip())
if missing:
    print("--- not found in one piece (split by an element boundary - read around them):")
    for x in missing:
        print("   " + x)
