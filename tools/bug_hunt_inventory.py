#!/usr/bin/env python3
"""bug_hunt_inventory.py - the MEASURED population for the BUG-HUNT wave (BRH), 2026-10-14.

Ian, 2026-10-14, after the release that fixed his missing logbook assets and the MCP journey that found WHY the fix
had not reached his phone: *"we have to expand and extend the numbers of our trajectories roadmap to hunt and sort
out bugs, painpoints, gaps, defects or whatever the terminologies, anything that affects my platform ... we use the
same trajectories roadmap, the same flow that we use MCP walk, with open and closed. I will let you decide the
numbers of trajectories first."*

The number is DERIVED, never typed (the BRP rule). Every class below is a defect class met on 2026-10-13/14 in a
real person's hands, generalised to every production page by measuring the real source and the committed
evidence artifacts. A class that cannot be measured seeds no rows. Each site is one CONCRETE place + a mechanism
+ a reproduction that can be made to fail on demand + a fix target + the gate that reddens on revert.

CLASSES (each measurable, each with its own repro recipe):
  D  version skew silenced by a guard       a page calls utils.js functions behind `typeof whX === 'function'`;
                                            with yesterday's utils.js still cached the guard turns a missing fix
                                            into silence (Ian's logbook: no restore, "No assets registered yet")
  E  scope-silent empty state               a page with a hive mode and a personal mode renders "No X yet." without
                                            saying WHICH list is empty, nor offering the other one
  F  stored role trusted without re-check   a page gates supervisor controls on localStorage wh_hive_role and never
                                            re-validates the role against the membership row
  G  stored hive name never reconciled      a page shows localStorage wh_hive_name and never calls whReconcileHiveName,
                                            so a rename on another device never reaches this one
  H  hive restored by reload, not start-up  a page that scopes by the stored hive relies on utils.js whHiveRecovery
                                            (render solo, then reload once) instead of re-seating the hive in its own
                                            start-up before the first read - a visible flash and a double load
  J  a live journey that is not live        live_page_journeys_results.json: a non-external journey with a failing lens
  K  design slop the ratchet still holds    design_detector_baseline.json: a (file :: antipattern) pair with a count
                                            above zero - the committed, print-exempt population, not a raw detector run

Only PRODUCTION pages seed rows (LX_NON_PRODUCTION, per Ian 2026-09-30). Deterministic: source regexes and committed
JSON only, so the registry validator can replay it on every run.

    python tools/bug_hunt_inventory.py            # the human report
    python tools/bug_hunt_inventory.py --json     # the machine population (what the seeder reads)
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OWNS_SEATING = {"index.html", "hive.html"}          # these pages seat the hive themselves (join/create/switch, the home)
JOURNEYS = ROOT / "live_page_journeys_results.json"
DESIGN_BASELINE = ROOT / "design_detector_baseline.json"

GUARD = re.compile(r"typeof\s+(wh[A-Za-z0-9_]+)\s*(?:===|==)\s*'function'")
DEFINED = re.compile(r"^(?:async\s+)?function\s+(wh[A-Za-z0-9_]+)\s*\(|^\s*window\.(wh[A-Za-z0-9_]+)\s*=", re.M)
DUAL_MODE = re.compile(r"is\('hive_id',\s*null\)|hive_id\.is\.null|!HIVE_ID\b")
EMPTY_STATE = re.compile(r"[>`'\"]\s*(No [a-z][^<`'\"]{3,60}?yet\.?)")
ROLE_READ = re.compile(r"localStorage\.getItem\(\s*'wh_hive_role'\s*\)")
ROLE_REVALIDATES = re.compile(r"from\(\s*'hive_members'\s*\)[^;]{0,300}select\([^)]*role|from\(\s*'v_worker_truth'|"
                              r"get_hive_board_dashboard|validateHiveMembership|validateMembership", re.S)
NAME_READ = re.compile(r"localStorage\.getItem\(\s*'wh_hive_name'\s*\)")
HIVE_READ = re.compile(r"\bwhHiveId\(\)")
OWN_RESTORE = re.compile(r"\bwhEnsureHiveContext\(")


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _non_production() -> set:
    try:
        from seed_expansion_wave4 import LX_NON_PRODUCTION
        return set(LX_NON_PRODUCTION)
    except Exception:
        return set()


def production_pages() -> list[str]:
    skip = _non_production()
    return sorted(os.path.basename(p) for p in glob.glob(str(ROOT / "*.html"))
                  if not os.path.basename(p).startswith("_") and os.path.basename(p) not in skip)


def _line_of(src: str, pos: int) -> int:
    return src[:pos].count("\n") + 1


def collect(sources: dict | None = None) -> list[dict]:
    """Every measured site, sorted (cls, page, line, key). `sources` lets the self-test pass page text in."""
    pages = production_pages() if sources is None else sorted(sources)
    read = (lambda p: sources[p]) if sources is not None else (lambda p: (ROOT / p).read_text(encoding="utf-8", errors="replace"))
    utils_src = (sources.get("utils.js", "") if sources is not None
                 else (ROOT / "utils.js").read_text(encoding="utf-8", errors="replace"))
    defined = {a or b for a, b in DEFINED.findall(utils_src)}
    sites: list[dict] = []
    for page in pages:
        if not page.endswith(".html"):
            continue
        src = read(page)
        # D - version skew silenced by typeof guards (one row per page: the heal is per page)
        guards = [(m.group(1), _line_of(src, m.start())) for m in GUARD.finditer(src) if m.group(1) in defined]
        if guards:
            names = sorted({g for g, _ in guards})
            sites.append({"cls": "D", "page": page, "line": guards[0][1], "key": f"{len(guards)} guards",
                          "detail": f"{len(guards)} typeof guards on {len(names)} utils.js functions: "
                                    + ", ".join(names[:6]) + (" ..." if len(names) > 6 else "")})
        # E - scope-silent empty states on a dual-mode page (one row per distinct string)
        if DUAL_MODE.search(src):
            seen = set()
            for m in EMPTY_STATE.finditer(src):
                text = re.sub(r"\s+", " ", m.group(1)).strip()
                if text in seen:
                    continue
                seen.add(text)
                sites.append({"cls": "E", "page": page, "line": _line_of(src, m.start()), "key": text,
                              "detail": f'empty state "{text}" names neither the personal nor the hive list'})
        # F - stored role trusted without re-validation (one row per page)
        rm = ROLE_READ.search(src)
        if rm and not ROLE_REVALIDATES.search(src):
            sites.append({"cls": "F", "page": page, "line": _line_of(src, rm.start()), "key": "wh_hive_role",
                          "detail": "reads wh_hive_role from localStorage and never re-validates it against hive_members"})
        # G - stored hive name never reconciled (one row per page)
        nm = NAME_READ.search(src)
        if nm and "whReconcileHiveName" not in src:
            sites.append({"cls": "G", "page": page, "line": _line_of(src, nm.start()), "key": "wh_hive_name",
                          "detail": "shows wh_hive_name from localStorage and never calls whReconcileHiveName"})
        # H - hive restored by reload instead of in the page's own start-up (one row per page)
        hm = HIVE_READ.search(src)
        if hm and page not in OWNS_SEATING and not OWN_RESTORE.search(src):
            sites.append({"cls": "H", "page": page, "line": _line_of(src, hm.start()), "key": "whHiveRecovery",
                          "detail": "scopes by whHiveId() and relies on utils.js whHiveRecovery (render solo, reload once) "
                                    "instead of whEnsureHiveContext before its first hive-scoped read"})
    # J - journeys that are not live (committed results file)
    if sources is None and JOURNEYS.exists():
        j = json.loads(JOURNEYS.read_text(encoding="utf-8"))
        skip = _non_production()
        for row in j.get("journeys", []):
            if row.get("external") or row.get("live") or row.get("page") in skip:
                continue
            failing = "".join(k for k, v in (row.get("verdict") or {}).items() if v is False)
            sites.append({"cls": "J", "page": row.get("page"), "line": 0, "key": row.get("id"),
                          "persona": row.get("role") or "any",
                          "detail": f"journey {row.get('id')} ({row.get('role')}) fails lens(es) {failing}: {str(row.get('title', ''))[:90]}"})
    # K - design slop pairs the ratchet still holds (committed baseline; print-exempt primaries)
    if sources is None and DESIGN_BASELINE.exists():
        b = json.loads(DESIGN_BASELINE.read_text(encoding="utf-8"))
        skip = _non_production()
        for pair, n in sorted((b.get("counts") or {}).items()):
            if not n or " :: " not in pair:
                continue
            f, anti = pair.split(" :: ", 1)
            if f in skip:
                continue
            page = f if f.endswith(".html") and (ROOT / f).exists() else "index.html"   # shared chrome is met on the home
            sites.append({"cls": "K", "page": page, "line": 0, "key": pair,
                          "detail": f"{n} primary '{anti}' finding(s) in {f} still held by the design-detector ratchet"})
    sites.sort(key=lambda s: (s["cls"], s["page"], s["line"], s["key"]))
    return sites


def self_test() -> int:
    utils = "function whEnsureHiveContext(db){}\nfunction whHiveId(){}\nfunction whReconcileHiveName(db){}\n"
    pages = {
        "utils.js": utils,
        "skew.html": "<script>if (typeof whHiveId === 'function') {} if (typeof whNotDefined === 'function') {}</script>",
        "dual.html": "<script>let HIVE_ID = whHiveId(); if (!HIVE_ID) {} x.innerHTML = `<p>No parts yet.</p><p>No parts yet.</p>`; y = 'No jobs yet'</script>",
        "role.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role');</script>",
        "role_ok.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role'); await validateHiveMembership();</script>",
        "name.html": "<script>const HIVE_NAME = localStorage.getItem('wh_hive_name');</script>",
        "name_ok.html": "<script>const HIVE_NAME = localStorage.getItem('wh_hive_name'); whReconcileHiveName(db);</script>",
        "reload.html": "<script>let HIVE_ID = whHiveId();</script>",
        "own.html": "<script>let HIVE_ID = whHiveId(); await whEnsureHiveContext(db);</script>",
    }
    got = Counter((s["cls"], s["page"]) for s in collect(pages))
    want = {("D", "skew.html"): 1, ("E", "dual.html"): 2, ("F", "role.html"): 1, ("G", "name.html"): 1,
            ("H", "reload.html"): 1, ("H", "dual.html"): 1, ("H", "skew.html"): 0}
    ok = all(got.get(k, 0) == v for k, v in want.items()) and ("D", "dual.html") not in got and ("F", "role_ok.html") not in got \
        and ("G", "name_ok.html") not in got and ("H", "own.html") not in got
    print(("PASS" if ok else "FAIL") + f" bug-hunt inventory self-test - {dict(got)}")
    return 0 if ok else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    sites = collect()
    if args.json:
        print(json.dumps(sites, indent=1, ensure_ascii=False))
        return 0
    by_cls = Counter(s["cls"] for s in sites)
    print("\nBUG-HUNT INVENTORY (production pages only)")
    print("=" * 74)
    print(f"  total measured defect sites: {len(sites)}")
    for c, label in (("D", "version skew silenced by a typeof guard   (layer H, per page)"),
                     ("E", "scope-silent empty state on a dual-mode page (layer F, per string)"),
                     ("F", "stored role trusted without re-validation  (layer AU, per page)"),
                     ("G", "stored hive name never reconciled          (layer D, per page)"),
                     ("H", "hive restored by reload, not in start-up   (layer F, per page)"),
                     ("J", "a live journey that is not live            (layer F, per journey)"),
                     ("K", "design slop the ratchet still holds        (layer F, per file :: antipattern)")):
        print(f"    {c} · {label}: {by_cls.get(c, 0)}")
    print()
    for c in "DEFGHJK":
        rows = [s for s in sites if s["cls"] == c]
        if not rows:
            continue
        print(f"  class {c} by page:")
        for pg, n in Counter(s["page"] for s in rows).most_common(8):
            print(f"    {pg:<32} {n:>3}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
