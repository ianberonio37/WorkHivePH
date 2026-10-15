#!/usr/bin/env python3
"""prove_page_ratchets.py - SL sub-layer CI3 (2026-10-15): "The platform must hold this page under the design, phone-fit
and accessibility ratchets, so a count can only fall."

HELD means MEASURED, not listed. A ratchet holds a page when its latest run read that page and the page sits at or under
the floor the ratchet keeps for it. Each ratchet's own record is read, never re-derived:
  design         prove_design_detector_ratchet.served_files() is the scope the detector reads on every run, and
                 design_detector_baseline.json its floors (any (file, antipattern) count that rises fails)
  phone fit      phone_fit_report.json - what tools/prove_phone_fit.mjs measured, per axis and page, on its last full run
                 (390 wide, signed in; a public page signed out) - against phone_fit_baseline.json's floor for that page
                 (absent = 0)
  accessibility  axe_live_violations_report.json - what tools/axe_scan_live.js scanned (a public page signed out), every
                 page not skipped - against axe_live_baseline.json's floor for that page

The roster widened on 2026-10-15: the phone-fit pool was a hand-written 51 pages and the axe list 12; both are now the
program's 155 (a page's first measurement its floor), so every page is held from today without failing it for findings
that predate the read. TEETH (in memory): a page missing from a ratchet's last run, and a count above its floor, must
each be caught.

  python tools/prove_page_ratchets.py [--page a.html,...] [--json .tmp/page_ratchets_results.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
PHONE_AXIS = "phone-fit@390"


def _load(name: str) -> dict:
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load() -> dict:
    from prove_design_detector_ratchet import served_files
    rep = _load("phone_fit_report.json").get("axes", {}).get(PHONE_AXIS, {})
    axe = _load("axe_live_violations_report.json")
    return {
        "design_scope": set(served_files()),
        "design_floor": _load("design_detector_baseline.json").get("counts") is not None,
        "phone_measured": rep.get("pages", {}),
        "phone_when": rep.get("generated"),
        "phone_floor": _load("phone_fit_baseline.json").get("axes", {}).get(PHONE_AXIS, {}),
        "axe_detail": axe.get("detail", {}),
        "axe_when": axe.get("generated"),
        "axe_floor": _load("axe_live_baseline.json").get("pages", {}),
    }


def check(page: str, R: dict) -> dict:
    problems, held = [], []
    if page in R["design_scope"] and R["design_floor"]:
        held.append("design (scanned on every ratchet run; floors in design_detector_baseline.json)")
    else:
        problems.append("not in the design ratchet's scope")
    if page in R["phone_measured"]:
        c, floor = R["phone_measured"][page], R["phone_floor"].get(page, 0)
        if c <= floor:
            held.append(f"phone fit @390 ({c} issue(s), floor {floor})")
        else:
            problems.append(f"phone fit @390 measured {c} issue(s), above its floor {floor}")
    else:
        problems.append("not measured by the phone-fit ratchet's last full run")
    d = R["axe_detail"].get(page)
    if d and not d.get("skipped"):
        c, floor = d.get("nodes", 0), R["axe_floor"].get(page)
        if floor is None:
            problems.append("scanned by axe but holds no floor in axe_live_baseline.json")
        elif c <= floor:
            held.append(f"accessibility, axe WCAG 2.2 AA ({c} node(s), floor {floor}, {d.get('as', 'signed in')})")
        else:
            problems.append(f"axe measured {c} node(s), above its floor {floor}")
    else:
        problems.append("not scanned by the accessibility ratchet's last run" + (f" ({d.get('reason')})" if d else ""))
    return {"page": page, "held": held, "problems": problems, "ok": not problems}


def teeth(R: dict, sample: str) -> dict:
    R1 = dict(R, phone_measured={k: v for k, v in R["phone_measured"].items() if k != sample})
    R2 = dict(R, axe_floor={**R["axe_floor"], sample: -1})
    missing = not check(sample, R1)["ok"]
    rose = not check(sample, R2)["ok"]
    return {"sample": sample, "missing_caught": missing, "rise_caught": rose, "bit": missing and rose}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "page_ratchets_results.json"))
    a = ap.parse_args()
    R = load()
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    ci3 = {t["sl"]["page"]: t.get("persona") for t in reg["trajectories"]
           if (t.get("sl") or {}).get("sublayer") == "CI3" and t.get("status") != "descoped"}
    pages = a.page.split(",") if a.page else sorted(ci3)
    results, bad = [], 0
    for page in pages:
        r = check(page, R)
        r.update({"cast": ci3.get(page), "engine": "static", "condition": "ratchets"})
        bad += 0 if r["ok"] else 1
        results.append(r)
        print(f"  {'ok  ' if r['ok'] else 'FAIL'} {page:<56} {len(r['held'])}/3 ratchets"
              + ("" if r["ok"] else "\n         " + "; ".join(r["problems"])))
    t = teeth(R, next((p for p in pages if p in R["phone_measured"]), pages[0]))
    print(f"\n  teeth - {t['sample']} taken out of the phone-fit run, and given an axe count above its floor: "
          f"{'both CAUGHT' if t['bit'] else 'NOT CAUGHT'}")
    failed = bad + (0 if t["bit"] else 1)
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayer": "CI3", "pages": len(results),
                               "phone_run": R["phone_when"], "axe_run": R["axe_when"], "failed": failed, "teeth": t,
                               "results": results}, indent=1), encoding="utf-8")
    print(f"\n{'FAIL' if failed else 'PASS'} page-ratchets - {len(results) - bad}/{len(results)} page(s) held by the design, "
          f"phone-fit and accessibility ratchets (measured, at or under their floors) -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
