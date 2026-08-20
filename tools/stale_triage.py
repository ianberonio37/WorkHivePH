# -*- coding: utf-8 -*-
"""A16.D2/C3 · Why is each row stale, and what would re-earn it?

"501 stale" is not an instruction. This turns the number into a work list by asking two questions of
every stale row:

  WHY did it expire?  - its anchor is wrong for the claim (R7), or a file it depends on moved, and which
                        file. A count with no cause invites the worst response, which is to re-walk
                        everything by hand.
  WHAT re-earns it?   - the row's own `evidence.replay` command, if it has one. Rows that carry a recipe
                        are SELF-HEALING: group them by command, run each command once, done. Rows that
                        do not are HAND-WALKED, and that is the real backlog.

The split is the point. On 2026-08-11 one session re-earned 48 `ordering_totality` rows with a single
command while the layout rows stayed stale, and the only difference between them was whether the
measurement had been written down as something runnable. So this tool reports **prover coverage** beside
the stale count: the fraction of stale rows a machine can re-earn without a human deciding anything.

    python tools/stale_triage.py            # the work list
    python tools/stale_triage.py --commands # just the distinct replay commands, one per line
    python tools/stale_triage.py --json
"""
import argparse
import collections
import datetime
import re
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import validate_live_mcp_bank as V  # noqa: E402

GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def cause_of(row, why):
    """Group a stale row by WHY, in the words the fix would use."""
    if why.startswith("R7"):
        return "mis-anchored (R7): the claim does not name what it rests on"
    ev = row.get("evidence") or {}
    deps = ev.get("depends_on") or []
    if not deps:
        return "no depends_on at all"
    # ATTRIBUTION FROM MTIMES, NOT FROM A GUESS. `sha` hashes the WHOLE dep set, so it says the set moved
    # and nothing about which member - and the first cut of this function simply NAMED `utils.js` whenever
    # it appeared in the deps, reporting "360 rows: a SHARED file moved (utils.js)" on no evidence at all.
    # The row's own evidence ref carries the date it was measured, so the honest question is answerable
    # cheaply: which of its dependencies has been modified SINCE then? (Verified while writing this:
    # utils.js is modified with an mtime of 2026-08-08, three days before the session that ran this, so
    # rows banked on 08-06 did expire from it and rows banked on 08-11 did not.)
    measured = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(ev.get("ref") or ""))
    if measured:
        when = datetime.datetime(int(measured.group(1)), int(measured.group(2)),
                                 int(measured.group(3)), 23, 59, 59).timestamp()
        moved = []
        for d in deps:
            path = os.path.join(ROOT, str(d))
            if os.path.isdir(path):
                newest = max((os.path.getmtime(os.path.join(r, f))
                              for r, _, fs in os.walk(path) for f in fs), default=0)
            elif os.path.exists(path):
                newest = os.path.getmtime(path)
            else:
                return "a dependency no longer exists (%s)" % d
            if newest > when:
                moved.append(str(d))
        if moved:
            return "%s modified after the walk" % ", ".join(sorted(moved))
        return ("the dep set hashes differently but no dep is newer than the walk date - a same-day edit, "
                "so the day-resolution ref cannot separate them")
    return "no date in the evidence ref, so the cause cannot be attributed"


def collect():
    out = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "banks", "*_live_mcp_bank.json"))):
        page = os.path.basename(fp).replace("_live_mcp_bank.json", "")
        reg = V.load(fp)
        gates, urls = V.gate_ids(), V.surface_urls(reg)
        for row in V.rows_of(reg) or []:
            state, why = V.classify(row, gates, urls)
            if state != "stale":
                continue
            ev = row.get("evidence") or {}
            rid = str(row.get("id") or "")
            out.append({"page": page, "id": rid,
                        "oracle": rid.rsplit("-", 1)[-1],
                        "subject": (row.get("subject") or {}).get("name"),
                        "cause": cause_of(row, why or ""),
                        "replay": ev.get("replay") or None,
                        "why": (why or "")[:160]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--commands", action="store_true",
                    help="print only the distinct replay commands, for piping into a shell")
    a = ap.parse_args(argv)
    rows = collect()
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0

    with_replay = [r for r in rows if r["replay"]]
    without = [r for r in rows if not r["replay"]]
    by_cmd = collections.Counter(r["replay"] for r in with_replay)

    if a.commands:
        for cmd in by_cmd:
            print(cmd)
        return 0

    print("  %sSTALE TRIAGE%s — %d stale row(s)" % (YEL, RST, len(rows)))
    if not rows:
        print("  %snothing stale.%s" % (GREEN, RST))
        return 0

    print("\n  %sBY CAUSE%s" % (DIM, RST))
    for cause, n in collections.Counter(r["cause"] for r in rows).most_common():
        print("    %4d  %s" % (n, cause))

    print("\n  %sBY ORACLE%s (the top 12 - these are the provers worth writing)" % (DIM, RST))
    for oracle, n in collections.Counter(r["oracle"] for r in rows).most_common(12):
        has = sum(1 for r in rows if r["oracle"] == oracle and r["replay"])
        mark = "%s(has a prover)%s" % (GREEN, RST) if has else "%sno prover%s" % (RED, RST)
        print("    %4d  %-24s %s" % (n, oracle, mark))

    pct = (100.0 * len(with_replay) / len(rows)) if rows else 0.0
    print("\n  %sPROVER COVERAGE%s  %d of %d stale rows carry a replay recipe  (%.1f%%)"
          % (DIM, RST, len(with_replay), len(rows), pct))
    if by_cmd:
        print("  %sre-earn them by running %d distinct command(s):%s" % (DIM, len(by_cmd), RST))
        for cmd, n in by_cmd.most_common():
            print("    %4d rows  %s" % (n, cmd))
    if without:
        print("\n  %s%d row(s) have NO replay - this is the real backlog.%s" % (RED, len(without), RST))
        print("  %sPer A16.C4 (the rule of two): hand-walk a claim twice and write its prover the third\n"
              "  time. The oracle list above is ordered by how much a prover would buy.%s" % (DIM, RST))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
