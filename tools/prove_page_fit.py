#!/usr/bin/env python3
"""prove_page_fit.py - SL sub-layer F2 (2026-10-15): "The platform must fit this page at 320 and 390 wide and at 1280,
with nothing clipped, overlapped or scrolled sideways."

The reading is the phone-fit lens's own record, never re-derived: tools/prove_phone_fit.mjs writes
phone_fit_report.json - the issue count it MEASURED per axis and page on its last full run (a --pages re-read is
merged in with its own time). Three axes are F2's:
  phone-fit@320   the narrowest phone (320x844, mobile, touch)
  phone-fit@390   the iPhone 14 class (390x844, mobile, touch)
  phone-fit@1280  a desktop (1280x800, no touch, DPR 1 - not a wide phone)
each signed in as the harness's cast, a public page signed out as its visitor, and a retired page that shows this
reader its overlay measured as that overlay. The record covers horizontal page overflow, an element outside the
viewport, clipped or spilled text, an unbroken token wider than its box, element overflow inside its clipping
container, an occluded control, and every more/menu trigger's menu inside the viewport.

A page's F2 row closes only at 0 on all three. The GATE is separate: prove_phone_fit.mjs holds each axis at a per-page
floor (phone_fit_baseline.json) so a count can only fall while the rest are brought to 0.
TEETH (in memory): a page missing from one axis's run, and a page given one issue on one axis, must each be caught.

  python tools/prove_page_fit.py [--page a.html,...] [--json .tmp/page_fit_results.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AXES = ("phone-fit@320", "phone-fit@390", "phone-fit@1280")


def load() -> dict:
    p = ROOT / "phone_fit_report.json"
    rep = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {ax: (rep.get("axes") or {}).get(ax) or {} for ax in AXES}


def check(page: str, R: dict) -> dict:
    problems, read = [], {}
    for ax in AXES:
        pages = R[ax].get("pages") or {}
        if page not in pages:
            problems.append(f"not measured at {ax.split('@')[1]}")
            continue
        read[ax] = pages[page]
        if pages[page]:
            problems.append(f"{pages[page]} issue(s) at {ax.split('@')[1]}")
    return {"page": page, "read": read, "problems": problems, "ok": not problems}


def teeth(R: dict, sample: str) -> dict:
    ax = AXES[0]
    R1 = dict(R, **{ax: dict(R[ax], pages={k: v for k, v in (R[ax].get("pages") or {}).items() if k != sample})})
    R2 = dict(R, **{ax: dict(R[ax], pages={**(R[ax].get("pages") or {}), sample: 1})})
    missing, issue = not check(sample, R1)["ok"], not check(sample, R2)["ok"]
    return {"sample": sample, "missing_caught": missing, "issue_caught": issue, "bit": missing and issue}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "page_fit_results.json"))
    a = ap.parse_args()
    R = load()
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    f2 = {t["sl"]["page"]: t.get("persona") for t in reg["trajectories"]
          if (t.get("sl") or {}).get("sublayer") == "F2" and t.get("status") != "descoped"}
    pages = a.page.split(",") if a.page else sorted(f2)
    results, bad = [], 0
    for page in pages:
        r = check(page, R)
        r.update({"cast": f2.get(page), "engine": "chromium", "condition": "fit"})
        bad += 0 if r["ok"] else 1
        results.append(r)
        print(f"  {'ok  ' if r['ok'] else 'open'} {page:<56} " + ", ".join(f"{k.split('@')[1]}:{v}" for k, v in r["read"].items())
              + ("" if r["ok"] else "   - " + "; ".join(r["problems"])))
    t = teeth(R, next((p for p in pages if p in (R[AXES[0]].get("pages") or {})), pages[0]))
    print(f"\n  teeth - {t['sample']} taken out of the 320 run, and given one issue at 320: "
          f"{'both CAUGHT' if t['bit'] else 'NOT CAUGHT'}")
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayer": "F2", "pages": len(results),
                               "runs": {ax: R[ax].get("generated") for ax in AXES}, "open": bad, "teeth": t,
                               "results": results}, indent=1), encoding="utf-8")
    # the GATE is the teeth and the readings' presence: every axis must have a run. A page's own count is held by
    # prove_phone_fit.mjs's per-page floor on each axis; an open row here is the next unit of work, not a red board.
    missing_runs = [ax for ax in AXES if not R[ax].get("pages")]
    failed = (0 if t["bit"] else 1) + len(missing_runs)
    print(f"\n{'FAIL' if failed else 'PASS'} page-fit - {len(results) - bad}/{len(results)} page(s) fit at 320, 390 and 1280 "
          f"with nothing clipped, overlapped or scrolled sideways"
          + (f"; no run on file for {missing_runs}" if missing_runs else "") + f" -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
