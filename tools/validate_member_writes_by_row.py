#!/usr/bin/env python3
"""validate_member_writes_by_row.py - no page changes a hive membership by DISPLAY NAME (gate `member-writes-by-row`,
2026-10-14).

WHY. hive.html removed a member with UPDATE hive_members SET status='kicked' WHERE hive_id=.. AND worker_name=<name>,
and handed the supervisor role over the same way, so two members sharing a display name were both removed or both
promoted. Found while fixing Ian's missing assets, which were the same class one step earlier: a stored name
standing in for an identity. Membership writes now target the row (`.eq('id', ...)`); the roster carries the row
id from get_hive_board_dashboard (migration 20261014000001) and from the fallback hive_members read.

WHAT IT HOLDS. In every root page, a Supabase chain on hive_members that UPDATES or DELETES may not filter by
worker_name. Reads are not graded here (a profile popup reading by name shows the wrong person at worst; a write by
name changes the wrong person's access).

  python tools/validate_member_writes_by_row.py
  python tools/validate_member_writes_by_row.py --self-test
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# one chain: from('hive_members') ... up to the statement's end (a ';' at depth 0 is approximated by the first ';')
CHAIN = re.compile(r"from\(\s*['\"]hive_members['\"]\s*\)([^;]{0,600})", re.S)
WRITE = re.compile(r"\.(update|delete|upsert)\s*\(")
BY_NAME = re.compile(r"\.eq\(\s*['\"]worker_name['\"]")


def offences(name: str, src: str) -> list:
    out = []
    for m in CHAIN.finditer(src):
        chain = m.group(1)
        if WRITE.search(chain) and BY_NAME.search(chain):
            line = src[:m.start()].count("\n") + 1
            out.append(f"{name}:{line}")
    return out


def self_test() -> int:
    bad = "await db.from('hive_members').update({ status: 'kicked' }).eq('hive_id', H).eq('worker_name', n);"
    good = "await db.from('hive_members').update({ status: 'kicked' }).eq('hive_id', H).eq('id', rowId);"
    read = "await db.from('hive_members').select('role').eq('worker_name', n).maybeSingle();"
    ok = offences("bad.html", bad) and not offences("good.html", good) and not offences("read.html", read)
    print(("PASS" if ok else "FAIL") + " member-writes-by-row self-test - a write by name is caught; a write by row and a read by name are not")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    found = []
    pages = sorted(ROOT.glob("*.html"))
    for p in pages:
        found += offences(p.name, p.read_text(encoding="utf-8", errors="replace"))
    if found:
        print(f"FAIL member-writes-by-row - {len(found)} membership write(s) keyed by display name: {', '.join(found)} "
              "(target the row: .eq('id', member.id); two members can share a name)")
        return 1
    print(f"PASS member-writes-by-row - no hive_members update/delete in {len(pages)} root pages filters by worker_name")
    return 0


if __name__ == "__main__":
    sys.exit(main())
