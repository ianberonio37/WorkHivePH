#!/usr/bin/env python3
"""validate_hive_restore_adoption.py - every page that scopes by the stored hive re-seats a missing one from the
account (gate `hive-restore-adoption`, 2026-10-14).

WHY. Ian, 2026-10-14: his 6 hive assets were missing from the logbook's Select Asset. The stored hive
(localStorage wh_active_hive_id) is a cache of a server fact - "which hive is this account a member of" - and until
today only index.html refilled it when it was empty. The logbook before 2026-10-13 even DELETED it on a display-name
mismatch, so a member who then opened any other page directly ran it in solo mode, where a hive's records cannot
appear and nothing says so (the wrong answer is the default).

THE TWO WAYS A PAGE IS COVERED (both proved live, both ways, by tools/prove_logbook_hive_restore.mjs):
  1. it re-seats the hive in its own start-up with whEnsureHiveContext(db) - no reload (logbook, asset-hub); such a
     page sets window.WH_SEATS_HIVE_ITSELF so the shared recovery leaves it alone;
  2. otherwise utils.js whHiveRecovery does it after load: whHiveId() marks the page as having found no hive, and on
     load the recovery seats it and reloads once (pm-scheduler is the proved representative).
WHAT THIS HOLDS, statically:
  - utils.js carries all three parts (the helper, the recovery wired to 'load', and whHiveId's missing-read mark);
  - every page that reads whHiveId() loads utils.js (the recovery lives there);
  - a page that opts out of the recovery (WH_SEATS_HIVE_ITSELF) really calls whEnsureHiveContext - an opt-out with no
    restore of its own is the original defect again, now silenced.
index.html (resolveActiveHiveContext) and hive.html (join/create/switch) own seating and are exempt.

  python tools/validate_hive_restore_adoption.py
  python tools/validate_hive_restore_adoption.py --self-test
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNS_SEATING = {"index.html", "hive.html"}
READS = re.compile(r"\bwhHiveId\(\)")
RESTORES = re.compile(r"\bwhEnsureHiveContext\(")
OPTS_OUT = re.compile(r"\bWH_SEATS_HIVE_ITSELF\s*=\s*true")
LOADS_UTILS = re.compile(r"<script[^>]+src=[\"'](?:\./|/)?utils\.js")
UTILS_PARTS = {
    "the helper": re.compile(r"async function whEnsureHiveContext\("),
    "the recovery wired to load": re.compile(r"function whHiveRecovery\(\)[\s\S]{0,400}addEventListener\('load'"),
    "whHiveId's missing-read mark": re.compile(r"function whHiveId\(\)[\s\S]{0,600}_whHiveMissingAtRead\s*=\s*true"),
}


def problems_in(pages: dict, utils_src: str) -> list:
    out = [f"utils.js lacks {name}" for name, rx in UTILS_PARTS.items() if not rx.search(utils_src)]
    for name, src in sorted(pages.items()):
        if name in OWNS_SEATING or not READS.search(src):
            continue
        if not LOADS_UTILS.search(src):
            out.append(f"{name} reads whHiveId() without loading utils.js, so no recovery can reach it")
        if OPTS_OUT.search(src) and not RESTORES.search(src):
            out.append(f"{name} opts out of the shared recovery (WH_SEATS_HIVE_ITSELF) but never calls whEnsureHiveContext")
    return out


def self_test() -> int:
    good_utils = ("function whHiveId() { var id = null; if (!id) window._whHiveMissingAtRead = true; return id; }\n"
                  "async function whEnsureHiveContext(db) {}\n"
                  "(function whHiveRecovery() { window.addEventListener('load', function () {}); })();")
    pages = {
        "covered.html": '<script src="utils.js"></script><script>let HIVE_ID = whHiveId();</script>',
        "self.html": '<script src="utils.js"></script><script>let HIVE_ID = whHiveId(); window.WH_SEATS_HIVE_ITSELF = true; await whEnsureHiveContext(db);</script>',
        "fake.html": '<script src="utils.js"></script><script>let HIVE_ID = whHiveId(); window.WH_SEATS_HIVE_ITSELF = true;</script>',
        "orphan.html": '<script>let HIVE_ID = whHiveId();</script>',
        "index.html": '<script>let HIVE_ID = whHiveId();</script>',
    }
    got = problems_in(pages, good_utils)
    want_names = {"fake.html", "orphan.html"}
    named = {g.split(" ")[0] for g in got}
    bare = problems_in({}, "function whHiveId() {}")
    ok = named == want_names and len(got) == 2 and len(bare) == 3
    print(("PASS" if ok else "FAIL") + f" hive-restore-adoption self-test - flagged {sorted(named)} (expected {sorted(want_names)}), "
          f"a utils.js without the parts raises {len(bare)}/3")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    pages = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in sorted(ROOT.glob("*.html"))}
    utils = (ROOT / "utils.js").read_text(encoding="utf-8", errors="replace")
    probs = problems_in(pages, utils)
    readers = [n for n, s in pages.items() if n not in OWNS_SEATING and READS.search(s)]
    own = [n for n in readers if RESTORES.search(pages[n])]
    if probs:
        print(f"FAIL hive-restore-adoption - {len(probs)} problem(s): " + "; ".join(probs))
        return 1
    print(f"PASS hive-restore-adoption - {len(readers)} page(s) scope by the stored hive: {len(own)} re-seat it in their own "
          f"start-up ({', '.join(own)}), {len(readers) - len(own)} through utils.js whHiveRecovery; none opts out without a restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
