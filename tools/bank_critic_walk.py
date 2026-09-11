#!/usr/bin/env python3
"""bank_critic_walk.py — bank one IN-MOTION critic walk onto every row that walk covers.

★THE DEEPWALK IS WALKED BY HAND THROUGH THE MCPs, SO ITS BANKING NEEDS A TOOL (2026-09-10).
`critic_from_board.py` banks a page-at-rest board and is deliberately forbidden from touching a
multi-page journey (validator rule R6). This is the other half: the rows walked step by step through the
MCP, where each step's snapshot decided the next, with `__RUBRIC.survey()` run on every surface after it
settled.

WHAT IT BANKS ONTO. Ian: *"deepwalk each trajectory OR GROUP OF CATEGORIES, but do not repeat what you
already done."* `tools/critic_walk_groups.py` says which rows are the SAME walk - same cell, same page
path, same language, same condition, same moment, differing only in which hive's data sits behind the
screens. One walk settles all of them, and every finding it writes says how wide the observation was, so
a reader is never misled into thinking six hives were each visited.

WHAT IT REFUSES, because a critique that grades nothing is worse than a pending row:
  * a survey file whose page graded no dims at all (a page that never became ready)
  * a dim the rubric spec does not define - dropped, never invented (validator R4)
  * an id that is not pending/critiqued, so a locked or improving row is never quietly rewritten

    python tools/bank_critic_walk.py --ids W312,W313 --surveys ".tmp/critic_g2_*.json" --note "..."
    python tools/bank_critic_walk.py --self-test
"""
from __future__ import annotations

import argparse
import datetime
import glob
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
SPEC = ROOT / "ufai-rubric-spec.json"


def severity(pct: int) -> int:
    """Arc K's scale: 4 blocker, 3 major, 2 minor, 1 polish. A zero is a blocker by construction."""
    return 4 if pct == 0 else 3 if pct < 50 else 2 if pct < 80 else 1


def read_surveys(paths: list[str]) -> list[dict]:
    out = []
    for p in sorted(paths):
        try:
            d = json.loads(io.open(p, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and "result" in d:      # the MCP tool wraps its output
            d = d["result"]
        if isinstance(d, dict) and d.get("dims"):
            d["_src"] = p                              # kept so a refusal can name the offending FILE
            out.append(d)
    return out


def path_mismatch(surveys: list, rows: list) -> tuple[list, list]:
    """Survey files grading a page this walk's rows do not declare. Returns (strays, the declared path).

    ★A REUSED GLOB PREFIX SILENTLY MIXES TWO WALKS (2026-09-10). Banking the fleet supervisor's
    alert-hub -> logbook -> dayplanner -> analytics journey with `--surveys ".tmp/critic_g3_*.json"`
    matched the four files from the walk in hand AND three left over from a different walk an hour
    earlier - audit-log, hive, index. The dry run said "12 findings across 7 pages" and every one of
    those numbers looked healthy; nothing in the output said that three of the pages had never been
    opened on this journey. One --apply later the bank would have carried, in the rows' own prose, a
    claim about surfaces this persona never visited - the hardest kind of error to find afterwards,
    because a survey file is real evidence, just of something else.
    The rows carry the refutation themselves: every critic row declares `pages`, the ordered path of
    the walk. A survey whose pageId is not on that path did not come from this walk. Same shape as the
    receipt-namespace fix in record_mcp_walk.py - the instrument must be unable to attribute evidence
    to a journey that did not produce it.
    """
    # ★A NESTED index.html IS IDENTIFIED BY ITS DIRECTORY, NOT ITS FILENAME (2026-09-10). The first
    # version keyed on the basename alone, so `learn/ra-11285-energy-efficiency-plant-checklist/index.html`
    # and `tools/load-estimation-calculator/index.html` BOTH collapsed to "index" - two entirely different
    # public pages sharing one key, and the root index.html sharing it too. The guard then refused a
    # perfectly good bank of the RA 11285 energy-audit walk, reporting its path as "engineering-design,
    # index, project-manager...". A guard that cries wolf gets narrowed or ignored, so the identity has to
    # match how these pages are actually named: the 54 learn articles and 60 calculators are one-index-per-
    # directory, and the directory IS the page. Each declared page therefore contributes its basename AND
    # its parent directory, and a survey matching either is on the path.
    declared = set()
    for r in rows:
        for p in (r.get("pages") or []):
            parts = str(p).replace("\\", "/").split("/")
            declared.add(parts[-1].replace(".html", ""))
            if len(parts) > 1 and parts[-1] == "index.html":
                declared.add(parts[-2])
    strays = [f"{d.get('pageId') or '?'}  <- {d.get('_src', '?')}"
              for d in surveys if str(d.get("pageId") or "?") not in declared]
    return strays, sorted(declared)


def collect(surveys: list[dict], dims_ok: set) -> tuple[list, list, list, int]:
    graded: set = set()
    findings: list = []
    per_page: list = []
    dropped = 0
    for d in surveys:
        pg = d.get("pageId") or "?"
        dims = [x for x in (d.get("dims") or []) if isinstance(x, dict)]
        sub = [x for x in dims if x.get("pct") is not None and x["pct"] < 100]
        per_page.append(f"{pg} {len(dims)} dims, {len(sub)} sub-100")
        for x in dims:
            if x.get("dim") in dims_ok:
                graded.add(x["dim"])
            elif x.get("dim"):
                dropped += 1
        for x in sub:
            if x.get("dim") not in dims_ok:
                continue
            findings.append({
                "dim": x["dim"], "layer": "heuristic", "severity": severity(int(x["pct"])),
                "evidence": f"{pg}: {x['dim']} {x['pct']}% - {(x.get('note') or '')[:150]}",
                "owner": "Designer",
                "receipt": "in-motion MCP walk, tools/bank_critic_walk.py",
            })
    return sorted(graded), findings, per_page, dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="comma-separated critic row ids this walk covers")
    ap.add_argument("--surveys", required=True, help="glob of __RUBRIC.survey() outputs, one per page")
    ap.add_argument("--note", default="", help="what the walk saw that a page-at-rest board cannot")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    surveys = read_surveys(glob.glob(args.surveys))
    if not surveys:
        print(f"refused: no survey file under {args.surveys!r} graded any dims - a walk that scored "
              "nothing is a FAILED walk, never a clean page")
        return 1

    spec = set(json.loads(io.open(SPEC, encoding="utf-8").read()).keys()) - {"_meta"}
    graded, findings, per_page, dropped = collect(surveys, spec)
    if not graded:
        print("refused: not one graded dim survived the rubric spec - nothing to bank")
        return 1

    reg = json.loads(io.open(CRITIC, encoding="utf-8").read())
    by = {r["id"]: r for r in reg.get("rows") or []}
    missing = [i for i in ids if i not in by]
    if missing:
        print(f"refused: not in the critic bank: {', '.join(missing[:5])}")
        return 1
    wrong = [i for i in ids if by[i].get("status") not in ("pending", "critiqued")]
    if wrong:
        print(f"refused: these are not pending/critiqued and must not be quietly rewritten: "
              f"{', '.join(wrong[:5])}")
        return 1

    strays, declared = path_mismatch(surveys, [by[i] for i in ids])
    if strays:
        print("refused: these survey files grade pages these rows do NOT declare - a reused glob prefix "
              "is mixing two different walks:\n  " + "\n  ".join(strays)
              + f"\n  this walk's declared path is: {', '.join(declared)}"
              + "\n  narrow --surveys to this walk's own files (a per-walk directory is safest).")
        return 1

    scope = (f"One in-motion MCP walk, banked onto {len(ids)} row(s) that share its cell, page path, "
             f"language, condition and moment (they differ only in which hive's data sits behind the "
             f"screens - see tools/critic_walk_groups.py). ")
    note = scope + (args.note or "") + " Surveyed: " + " | ".join(per_page) + "."
    if not args.apply:
        print(f"would bank {len(findings)} finding(s) across {len(graded)} graded dim(s) onto "
              f"{len(ids)} row(s): {', '.join(ids[:8])}{' …' if len(ids) > 8 else ''}")
        print(f"  pages: {' | '.join(per_page)}")
        if dropped:
            print(f"  {dropped} board dim(s) not in the rubric spec would be DROPPED, never invented")
        print("  (re-run with --apply)")
        return 0

    # ★THE BANK RECORDED WHICH DIMENSIONS, NEVER WHICH LENS (2026-09-10). `critic_registry.rubric_sha`
    # is the sha of ufai-rubric-spec.json - the DEFINITIONS - and the scoreboard header quotes it. But
    # the thing that actually produces a verdict is survey_ufai_rubric.js, and it is not stamped
    # anywhere. Five lens bugs were corrected in a single session (X1 scoping to a panel, H1 punishing
    # an empty slot, J1 blind to a guard one hop away, C2's disabled-control exemption, N1's data-i
    # census) and EVERY one of them changed verdicts - yet a row banked before a fix and a row banked
    # after it both read "rubric 975123b63769" and are otherwise indistinguishable. That is the gap the
    # retraction tool has to close by hand. Stamping the lens per row makes it answerable by query:
    # a reader can ask which rows were graded by the ruler that had the bug.
    lens_sha = ""
    lens = ROOT / "survey_ufai_rubric.js"
    if lens.exists():
        import hashlib
        lens_sha = hashlib.sha256(lens.read_bytes()).hexdigest()[:12]

    today = datetime.date.today().isoformat()
    for i in ids:
        r = by[i]
        r["status"] = "critiqued"
        r["walked_at"] = today
        if lens_sha:
            r["lens_sha"] = lens_sha
        r["dims_graded"] = graded + ["IN-MOTION"]
        r["findings"] = findings
        r["target_source"] = "mcp-in-motion-walk"
        r["clean_note"] = note
        r.pop("improvement_refs", None)
    tmp = str(CRITIC) + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(reg, indent=1, ensure_ascii=False))
    os.replace(tmp, CRITIC)
    print(f"banked {len(ids)} row(s) -> critiqued | {len(graded)} dims | {len(findings)} findings")
    return 0


def _self_test() -> int:
    fails = []
    spec = {"A1", "B3", "C2"}
    surveys = [
        {"pageId": "hive", "dims": [{"dim": "A1", "pct": 100}, {"dim": "B3", "pct": 40, "note": "long"}]},
        {"pageId": "logbook", "dims": [{"dim": "C2", "pct": 0, "note": "contrast"},
                                       {"dim": "ZZ9", "pct": 10, "note": "not in the spec"}]},
    ]
    graded, findings, per_page, dropped = collect(surveys, spec)
    if graded != ["A1", "B3", "C2"]:
        fails.append("every spec dim seen must be counted as graded")
    if dropped != 1:
        fails.append("a dim the spec does not define must be DROPPED and counted, never invented")
    if any(f["dim"] == "ZZ9" for f in findings):
        fails.append("an invented dim must never reach findings - validator R4 would reject the bank")
    if len(findings) != 2:
        fails.append("each sub-100 spec dim must become exactly one finding")

    # the reused-glob guard: a survey for a page the rows never declare must REFUSE the bank
    rows_decl = [{"pages": ["alert-hub.html", "logbook.html"]}]
    on_path = [{"pageId": "alert-hub", "dims": [], "_src": "a.json"},
               {"pageId": "logbook", "dims": [], "_src": "b.json"}]
    strays, declared = path_mismatch(on_path, rows_decl)
    if strays:
        fails.append(f"a survey ON the declared path must not be called a stray: {strays}")
    if declared != ["alert-hub", "logbook"]:
        fails.append("the declared path must be reported so a refusal is actionable")
    strays, _ = path_mismatch(on_path + [{"pageId": "hive", "dims": [], "_src": "old.json"}], rows_decl)
    if len(strays) != 1 or "hive" not in strays[0] or "old.json" not in strays[0]:
        fails.append("a leftover survey from another walk must be caught AND named with its file")

    # a nested index.html is identified by its DIRECTORY, not by the filename "index"
    nested = [{"pages": ["learn/ra-11285-energy-efficiency-plant-checklist/index.html",
                         "tools/load-estimation-calculator/index.html", "project-manager.html"]}]
    ok_nested = [{"pageId": "ra-11285-energy-efficiency-plant-checklist", "dims": [], "_src": "a.json"},
                 {"pageId": "load-estimation-calculator", "dims": [], "_src": "b.json"},
                 {"pageId": "project-manager", "dims": [], "_src": "c.json"}]
    strays, declared = path_mismatch(ok_nested, nested)
    if strays:
        fails.append(f"a nested index.html must be matchable by its directory name, got strays {strays}")
    if "load-estimation-calculator" not in declared:
        fails.append("the declared path must list the directory so a refusal names something recognisable")
    strays, _ = path_mismatch(ok_nested + [{"pageId": "marketplace", "dims": [], "_src": "x.json"}], nested)
    if len(strays) != 1:
        fails.append("widening to directory names must not stop catching a genuine stray")
    sev = {f["dim"]: f["severity"] for f in findings}
    if sev.get("C2") != 4:
        fails.append("a 0% dim is a blocker (severity 4)")
    if sev.get("B3") != 3:
        fails.append("a 40% dim is a major (severity 3)")
    if not all(p in " ".join(per_page) for p in ("hive", "logbook")):
        fails.append("the per-page summary must name every page walked")
    if severity(85) != 1 or severity(60) != 2:
        fails.append("the severity scale must map 85->polish and 60->minor")
    if read_surveys(["nope-*.json"]):
        fails.append("a glob matching nothing must yield no surveys, so the caller is refused")

    print("FAIL bank_critic_walk self-test - " + "; ".join(fails) if fails
          else "self-test OK: spec dims graded, an unknown dim dropped not invented, severities mapped, "
               "every page named, and an empty glob banks nothing")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
