#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_calc_method_defaults_split.py — the calculators' method note was one 23-word sentence on 60 public pages.

FOUND 2026-10-13 by the critic batch: B3 (sentences of 20 words or fewer, grade 8 or lower) failed on 57 calculator
pages with the SAME sentence as the longest and the hardest, which points at the generator rather than at 57 pages
([[feedback_a_family_that_measures_identically_is_a_reason_to_read_the_generator]]):

  "Anything the worked example does not state uses this calculator's standard default; the interactive version
   shows every input and lets you change it."

Two facts joined by a semicolon. Split at the semicolon, nothing reworded: the default, then where to change it.

Like fix_calc_cta_crew_context.py this is a sweep over the SERVED pages (`tools/<slug>/index.html`), because the
generator writes to staging and the served pages are ahead of it; the generator is fixed too, so a rebuild is born
correct. It is a PAIRED write: each page's `index.html.md` twin carries the same prose, so --apply rebuilds the twins.

  python tools/fix_calc_method_defaults_split.py --check
  python tools/fix_calc_method_defaults_split.py --apply
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

OLD = ("Anything the worked example does not state uses this calculator's standard default; "
       "the interactive version shows every input and lets you change it.")
NEW = ("Anything the worked example does not state uses this calculator's standard default. "
       "The interactive version shows every input and lets you change it.")


def pages() -> list[Path]:
    return sorted(p for p in ROOT.glob("tools/*/index.html") if p.is_file())


def main() -> int:
    check = "--check" in sys.argv
    apply = "--apply" in sys.argv
    if not (check or apply):
        print(__doc__)
        return 0
    todo, done, absent = [], [], []
    for p in pages():
        s = io.open(p, encoding="utf-8").read()
        (todo if OLD in s else done if NEW in s else absent).append(p)
    stale = [p for p in pages() if (p.parent / "index.html.md").exists()
             and OLD in io.open(p.parent / "index.html.md", encoding="utf-8").read()]
    print(f"  calc method note: {len(todo)} to split · {len(done)} already split · {len(absent)} carry neither "
          f"· {len(stale)} markdown twin(s) still joined")
    if check:
        if todo or stale:
            print(f"{RED}FAIL{RST} calc-method-defaults-split - {len(todo)} page(s) and {len(stale)} twin(s) still join the "
                  f"default and the way to change it in one 23-word sentence (run --apply)")
            return 1
        print(f"{GREEN}PASS{RST} calc-method-defaults-split - the method note is two short sentences on every calculator "
              f"page that carries it ({len(done)}), and the markdown twins agree")
        return 0
    for p in todo:
        s = io.open(p, encoding="utf-8").read().replace(OLD, NEW)
        tmp = p.with_suffix(".html.tmp")
        io.open(tmp, "w", encoding="utf-8", newline="\n").write(s)
        tmp.replace(p)                      # atomic: open(w) truncates before the write
    print(f"  split {len(todo)} method note(s)")
    if todo or stale:
        twin = ROOT / "tools" / "build_md_twins.py"
        if twin.exists():
            r = subprocess.run([sys.executable, str(twin)], capture_output=True, text=True,
                               timeout=600, encoding="utf-8", errors="replace")
            tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
            print(f"  md twins: {'ok' if r.returncode == 0 else 'WARN'} {(tail[-1] if tail else '')[:92]}")
        else:
            print(f"  {YEL}WARN{RST} tools/build_md_twins.py is missing - the twins still carry the joined sentence")
    left = [p for p in pages() if (p.parent / "index.html.md").exists()
            and OLD in io.open(p.parent / "index.html.md", encoding="utf-8").read()]
    if left:
        print(f"  {RED}{len(left)} markdown twin(s) still carry the joined sentence{RST}")
        return 1
    print(f"{GREEN}done{RST} - {len(todo)} page(s) and their markdown twins carry the split method note")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    raise SystemExit(main())
