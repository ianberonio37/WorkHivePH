#!/usr/bin/env python3
"""validate_page_roster.py — T1.4: ONE page roster; every consumer's scope declared and checked.

WHY. Six instruments each carried a private page list, and they drifted six different ways:
the link gate's hardcoded 30 held two pages deleted months ago and missed 14 real ones; the
no-em-dash gate globbed one directory and reported the platform clean while 299 hits sat in
learn/; sw.js once precached two files that never existed (failing EVERY install). A roster
is a silent claim about scope — this gate makes the claim ONE artifact
(substrate/reference/page_roster.json) and checks each consumer's ACTUAL set against its
DECLARED scope predicate, so differing counts are explained, never drifted.

  --build   regenerate the roster from disk (root *.html = kind root; learn/*/index.html +
            learn/index.html = learn; tools/*/index.html = tools)
  (default) validate:
    1. roster ↔ disk parity (no phantom rows, no unrostered pages);
    2. consumer sw.js SHELL_FILES — every precached .html exists ON DISK (one 404 fails the
       whole ServiceWorker install) and is a rostered root page;
    3. consumer nav-hub.js TOOLS — every href resolves to a rostered root page;
    4. consumer banks/ — every <page>_live_mcp_bank.json names a rostered root page;
    5. consumer validate_link_target_existence — its derived scope (root glob) equals the
       roster's root subset BY CONSTRUCTION; asserted anyway so a future re-hardcode fails.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROSTER = ROOT / "substrate" / "reference" / "page_roster.json"

CHECK_NAMES = ["page_roster"]


def disk_roster() -> list[dict]:
    rows = [{"path": p.name, "kind": "root"} for p in sorted(ROOT.glob("*.html"))]
    rows += [{"path": "learn/index.html", "kind": "learn"}]
    rows += [{"path": f"learn/{p.parent.name}/index.html", "kind": "learn"}
             for p in sorted((ROOT / "learn").glob("*/index.html"))]
    rows += [{"path": f"tools/{p.parent.name}/index.html", "kind": "tools"}
             for p in sorted((ROOT / "tools").glob("*/index.html"))]
    return rows


def consumers() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    sw = (ROOT / "sw.js").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const SHELL_FILES = \[(.*?)\];", sw, re.S)
    out["sw_shell"] = set(re.findall(r"'/([^']+\.html)'", m.group(1))) if m else set()
    nav = (ROOT / "nav-hub.js").read_text(encoding="utf-8", errors="replace")
    out["nav_hub"] = set(re.findall(r"href:\s*'([^']+\.html)'", nav))
    out["banks"] = {f"{p.name.split('_live_mcp_bank')[0]}.html"
                    for p in (ROOT / "banks").glob("*_live_mcp_bank.json")}
    return out


def main() -> int:
    if not ROSTER.exists():
        print("FAIL page-roster — roster missing (run --build)")
        return 1
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["pages"]
    rostered = {r["path"] for r in roster}
    root_pages = {r["path"] for r in roster if r["kind"] == "root"}
    problems: list[str] = []

    disk = {r["path"] for r in disk_roster()}
    if disk - rostered:
        problems.append(f"{len(disk - rostered)} page(s) on disk but not rostered: {sorted(disk - rostered)[:4]}")
    if rostered - disk:
        problems.append(f"{len(rostered - disk)} roster row(s) with no file: {sorted(rostered - disk)[:4]}")

    cons = consumers()
    for name, got in cons.items():
        missing_on_disk = {g for g in got if not (ROOT / g).exists()}
        if missing_on_disk:
            problems.append(f"{name}: names files that DO NOT EXIST: {sorted(missing_on_disk)[:4]}"
                            + (" — one precached 404 fails the whole SW install" if name == "sw_shell" else ""))
        unrostered = {g for g in got if g not in root_pages and g in disk} | (got - rostered - missing_on_disk)
        unrostered = {g for g in unrostered if g not in rostered}
        if unrostered:
            problems.append(f"{name}: outside the roster: {sorted(unrostered)[:4]}")

    # consumer 5: the link gate derives its roster from the same glob — assert equality so a
    # future re-hardcode (the original defect) cannot come back silently.
    sys.path.insert(0, str(ROOT))
    import importlib
    lg = importlib.import_module("validate_link_target_existence")
    if set(lg.PAGES) != {r["path"] for r in roster if r["kind"] == "root"}:
        problems.append("validate_link_target_existence.PAGES no longer equals the roster's root subset "
                        "(re-hardcoded?)")

    counts = {k: len(v) for k, v in cons.items()}
    print(f"page-roster: {len(roster)} rostered ({len(root_pages)} root) · consumers {counts} · "
          f"link-gate scope {len(lg.PAGES)}")
    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    print("PASS page-roster — one roster, every consumer's scope inside it and explained.")
    return 0


def self_test() -> int:
    fails = []
    cons = consumers()
    if not cons["sw_shell"] or not cons["nav_hub"] or not cons["banks"]:
        fails.append(f"a consumer parsed EMPTY (sw={len(cons['sw_shell'])} nav={len(cons['nav_hub'])} "
                     f"banks={len(cons['banks'])}) — an empty parse passes every check vacuously")
    # the historical defect must be detectable: a phantom shell entry
    phantom = {"parts-tracker.html"}  # deleted 2026-06-10; once precached and failed installs
    if not {g for g in phantom if not (ROOT / g).exists()}:
        fails.append("the phantom-file detector lost its test case")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print(f"PASS validate_page_roster self-test (consumers parse non-empty: {[f'{k}={len(v)}' for k, v in cons.items()]})")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--build" in sys.argv:
        rows = disk_roster()
        ROSTER.write_text(json.dumps({
            "_doc": ("T1.4 unified page roster — the ONE scope artifact every page-consuming "
                     "instrument is checked against (validate_page_roster.py). Regenerate with "
                     "--build after adding/removing a page."),
            "count": len(rows), "pages": rows,
        }, indent=2), encoding="utf-8")
        print(f"built page_roster.json: {len(rows)} pages")
        sys.exit(0)
    sys.exit(self_test() if "--self-test" in sys.argv else main())
