#!/usr/bin/env python3
"""no-execute-on-builders - a supabase-js query is awaited, never `.execute()`d (OWN55 walk, 2026-10-27).

`.execute()` is the Python client's idiom. supabase-js v2's builders have no such method, so a chain ending in it throws
a TypeError the moment it runs - and every place it was found had that TypeError inside a try whose catch returned
"nothing found". voice-semantic-rag's recency fallback and voice-handler.js's direct fallback both did this, so the voice
companion's journal recall had never returned a row from either (the semantic half was broken separately: a 768-dim Jina
query against a vector(384) corpus). Nothing failed loudly; the companion simply never remembered.

Scans what ships: supabase/functions/**/*.ts (not *.test.ts) and the root *.js / *.html. A line comment or a block-comment
line is skipped. No baseline - the class is empty, so any hit is new.

  python tools/validate_no_execute_on_builders.py [--self-test]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIT = re.compile(r"\.execute\(\s*\)")
COMMENT = re.compile(r"^\s*(//|\*|/\*|<!--)")


def files() -> list:
    out = [p for p in (ROOT / "supabase" / "functions").rglob("*.ts") if not p.name.endswith(".test.ts")]
    out += sorted(ROOT.glob("*.js")) + sorted(ROOT.glob("*.html"))
    return out


TAIL = re.compile(r"(?<![:\"'\\w])//.*$")   # a trailing line comment (not the // inside "https://")


def hits_in(text: str) -> list:
    return [i for i, ln in enumerate(text.splitlines(), 1) if not COMMENT.match(ln) and HIT.search(TAIL.sub("", ln))]


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok   " if c else "  FAIL ") + m)
        ok = ok and bool(c)
    ck(hits_in("const { data } = await db.from('t').select('a')\n  .limit(5)\n  .execute();") == [3], "a chained .execute() is a hit")
    ck(not hits_in("// the old code ended in .execute()"), "a line comment is not")
    ck(not hits_in("   * it used .execute() before"), "a block-comment line is not")
    ck(not hits_in("const CACHE = 'v1';  // the fallback ended in .execute()"), "a trailing comment on a code line is not")
    ck(hits_in("fetch('https://x.io/a'); q.limit(1).execute();") == [1], "a URL's // does not hide a real hit after it")
    ck(not hits_in("const { data } = await db.from('t').select('a').limit(5);"), "an awaited builder is not")
    print("SELF-TEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    found = []
    fs = files()
    for f in fs:
        for ln in hits_in(f.read_text(encoding="utf-8", errors="replace")):
            found.append(f"{f.relative_to(ROOT).as_posix()}:{ln}")
    for h in found:
        print("  .execute() on a supabase-js builder (it has no such method - the chain throws): " + h)
    print(("FAIL" if found else "PASS") + f" no-execute-on-builders - {len(fs)} shipped files, {len(found)} chain(s) ending in .execute()")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
