#!/usr/bin/env python3
"""sync_lens_read_rpcs.py - keep the rubric lens's list of read-only RPCs equal to what the database says (2026-10-13).

survey_ufai_rubric.js's PP3 dim decides whether a page WRITES from its source, and reads any `.rpc('name')` not named
get_/list_/fetch_/v_/my_ as a write. audit-log's only call is audit_filter_vocab, which is STABLE and has no DML, so a
read-only viewer was graded 0% for "a submit gives no instant acknowledgment" on every walk. A name prefix cannot
decide this; the function's volatility can (Postgres refuses a write from a STABLE or IMMUTABLE function). So the lens
carries `_READ_RPCS`: every STABLE/IMMUTABLE public function that a page calls without a read prefix. This tool writes
that line from the database and, with --check, fails when it has drifted either way (a new read rpc a page calls, or
a listed one that became VOLATILE). Skips cleanly when the local database is not running.

  python tools/sync_lens_read_rpcs.py           # dry run: print the set and whether the lens agrees
  python tools/sync_lens_read_rpcs.py --apply   # rewrite the lens line
  python tools/sync_lens_read_rpcs.py --check   # exit 1 on drift (gate: lens-read-rpcs)
"""
from __future__ import annotations

import glob
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LENS = ROOT / "survey_ufai_rubric.js"
LINE = re.compile(r"^([ \t]*)const _READ_RPCS = new Set\(\[[^\]]*\]\); // sync_lens_read_rpcs(?=\r?$)", re.M)
SQL = ("select proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
       "where n.nspname = 'public' and provolatile in ('s','i') and proname !~ '^(get_|list_|fetch_|v_|my_)'")


def stable_functions():
    try:
        r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-tA", "-c", SQL],
                           capture_output=True, text=True, timeout=30)
    except Exception as e:      # docker missing or hung
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip()[:200]
    return {l.strip() for l in r.stdout.splitlines() if l.strip()}, None


def called_rpcs():
    names = set()
    files = glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "*" / "index.html")) + [str(ROOT / "utils.js")]
    for f in files:
        try:
            s = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names.update(re.findall(r"\.rpc\(\s*['\"]([a-z0-9_]+)['\"]", s))
    return names


def main() -> int:
    stable, err = stable_functions()
    if stable is None:
        print(f"SKIP lens-read-rpcs: the local database is not reachable ({err})")
        return 0
    want = sorted(stable & called_rpcs())
    # newline="" keeps the file's own line endings: a read in text mode turned 3,523 CRLF lines into LF (2026-10-13)
    src = LENS.open(encoding="utf-8", newline="").read()
    m = LINE.search(src)
    if not m:
        print("FAIL: the _READ_RPCS line is missing from survey_ufai_rubric.js")
        return 1
    have = sorted(re.findall(r"'([a-z0-9_]+)'", m.group(0)))
    print(f"read-only rpcs the pages call without a read prefix: {len(want)}")
    if have == want:
        print("  the lens agrees")
        return 0
    added, gone = sorted(set(want) - set(have)), sorted(set(have) - set(want))
    print(f"  lens drifted: missing {added or '-'}; no longer read-only or no longer called {gone or '-'}")
    if "--apply" in sys.argv:
        line = m.group(1) + "const _READ_RPCS = new Set([" + ", ".join(f"'{n}'" for n in want) + "]); // sync_lens_read_rpcs"
        LENS.open("w", encoding="utf-8", newline="").write(src[:m.start()] + line + src[m.end():])
        print("  lens line rewritten")
        return 0
    return 1 if "--check" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
