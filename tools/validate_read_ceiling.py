#!/usr/bin/env python3
"""validate_read_ceiling.py - no read asks one response for more rows than the API will send (2026-10-28).

WHY. PostgREST answers at most max_rows rows per request - 1,000, Supabase's default and ours (supabase/config.toml sets
no other) - whatever .limit() asks. So `.limit(2000)` reads 1,000, and every `.limit(N + 1)` "one row past the cap says
more exist" probe with N >= 1,000 can never receive its probe row. Found by the first cube walk (CX-PROD, achievements as
the adversary): a worker with 1,982 XP events this week saw "+20,120" for 39,760, with no "At least" - the page's own
floor sentence could never fire. 25 reads on 12 pages asked past the ceiling; inventory and the logbook parts picker
would have lost every part past the 1,000th with no sign.

A read that must hold more than 1,000 rows is asked a page at a time: `whReadPaged((a, b) => db.from(...)...range(a, b),
N)` (utils.js). This gate fails any `.limit(N)` or RPC `p_limit: N` above the ceiling in a served page or script, so the
class cannot come back. Comments are blanked first - several quote the old reads they replaced.

    python tools/validate_read_ceiling.py
    python tools/validate_read_ceiling.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CEILING = 1000
LIMIT = re.compile(r"\.limit\(\s*(\d+)\s*(?:\+\s*(\d+))?\s*\)")
PLIMIT = re.compile(r"\bp_limit\s*:\s*(\d+)\s*(?:\+\s*(\d+))?")


def blank_comments(src: str) -> str:
    """Comments to spaces, offsets kept (a // inside a string or a URL is left alone)."""
    src = re.sub(r"/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src)
    src = re.sub(r"<!--[\s\S]*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src)
    return re.sub(r"(^|[^:'\"`\\])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), src, flags=re.M)


def findings(name: str, src: str) -> list[str]:
    code, out = blank_comments(src), []
    for rx, what in ((LIMIT, ".limit"), (PLIMIT, "p_limit")):
        for m in rx.finditer(code):
            n = int(m.group(1)) + int(m.group(2) or 0)
            if n > CEILING:
                line = code.count("\n", 0, m.start()) + 1
                out.append(f"{name}:{line} asks {what} {n} - one response carries at most {CEILING} rows, so this reads "
                           f"{CEILING}{' and its probe row never arrives' if m.group(2) else ''}; ask it a page at a time "
                           f"(whReadPaged)")
    return out


def roster() -> list[Path]:
    return sorted(p for p in ROOT.glob("*.html")) + sorted(p for p in ROOT.glob("*.js"))


def self_test() -> int:
    cases = [
        (".from('x').select('a').limit(2000)", 1, "a 2,000 cap"),
        (".from('x').select('a').limit(1000 + 1)", 1, "a probe past the ceiling"),
        ("db.rpc('f', { p_limit: 5000 })", 1, "an RPC page past the ceiling"),
        (".from('x').select('a').limit(500 + 1)", 0, "a probe under the ceiling"),
        ("whReadPaged((a, b) => db.from('x').select('a').order('id').range(a, b), 2000)", 0, "a paged read"),
        ("// the old .limit(10000) scan saw 6%\n.limit(50)", 0, "a quoted old read in a comment"),
        ("/* .limit(20000) */ .limit(1000)", 0, "exactly the ceiling, and a block comment"),
    ]
    bad = 0
    for src, want, label in cases:
        got = len(findings("fixture", src))
        ok = got == want
        bad += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {got} finding(s), expected {want}")
    print("self-test " + ("PASS" if not bad else "FAIL"))
    return 1 if bad else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    allf = []
    files = roster()
    for p in files:
        allf += findings(p.name, p.read_text(encoding="utf-8", errors="replace"))
    print(f"read-ceiling - {len(files)} served page(s) and script(s), API ceiling {CEILING} rows per response")
    for f in allf:
        print("  - " + f)
    print(("FAIL" if allf else "PASS") + f" read-ceiling - {len(allf)} read(s) ask one response for more than it may carry")
    return 1 if allf else 0


if __name__ == "__main__":
    sys.exit(main())
