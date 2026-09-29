#!/usr/bin/env python3
"""prove_w4_navhub_receipt_shape.py - TEETH for the nav-hub receipt plumbing (2026-09-14, no browser).

The wave-4 nav-hub ratchet (tools/prove_w4_navhub.mjs) once wrote receipts with NO `steps`, so
live_walk_manifest._w4_missing rejected EVERY nav-hub row ("fewer than 4 pages walked; a step has no
overlap/occlusion record") and not one of the ~90 rows could ever close, however clean its walk. The fix, three
parts: the walker returns a compact per-page `steps` array (page + a fit dict), the driver writes it into the
receipt, and `_w4_receipts` reads BOTH the mcp_walks namespace AND the driver's own full_journeys_w4navhub_*.json.
A fix with no gate silently rots, so this asserts the plumbing BITES, on synthetic receipts whose truth is known:

  well-formed (4 pages, a fit DICT per step, axis matched, hub_controls 11) -> _w4_missing MUST accept ('')
  stepless    (the old shape - no steps)                                    -> _w4_missing MUST reject
  and _w4_receipts MUST see a receipt written to the full_journeys_w4navhub namespace (not only mcp_walks).

  python tools/prove_w4_navhub_receipt_shape.py            # run the checks
  python tools/prove_w4_navhub_receipt_shape.py --check    # same, for the gate registry
"""
from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"


def _row_stub(rid: str, axis: str) -> dict:
    dev, lang = axis.split(" ", 1) if " " in axis else (axis, "en")
    return {"id": rid, "status": "specced", "axis": {"device": dev, "language": lang},
            "title": "The whole nav-hub, every control, on this page, lived start to end - synthetic",
            "pages": ["a.html", "b.html", "c.html", "d.html"],
            "w4": {"kind": "nav-hub", "host": "a.html"}}


def main() -> int:
    axis = "phone-390 en"
    rid = "W4RCPTTEST"
    steps = [{"page": p, "chars": 900, "identityKept": True, "fit": {"findings": 0, "occlusion": []}}
             for p in ("a.html", "b.html", "c.html", "d.html")]
    good = {"id": rid, "ok": True, "instrument": "tools/prove_w4_navhub.mjs",
            "w4": {"axis": axis, "hub_controls": 11}, "steps": steps}
    stepless = {"id": rid, "ok": True, "instrument": "tools/prove_w4_navhub.mjs",
                "w4": {"axis": axis, "hub_controls": 11}, "steps": []}

    # write a synthetic receipt into the full_journeys_w4navhub namespace, prove _w4_receipts reads it there
    tmp = ROOT / ".tmp" / "full_journeys_w4navhub_receiptshape-selftest.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    fails = []
    try:
        tmp.write_text(json.dumps({"instrument": "tools/prove_w4_navhub.mjs", "axis": axis, "results": [good]}),
                       encoding="utf-8")
        sys.path.insert(0, str(ROOT / "tools"))
        import live_walk_manifest as m
        importlib.reload(m)
        rec = m._w4_receipts()
        if rid not in rec:
            fails.append("_w4_receipts does NOT read the full_journeys_w4navhub namespace (nav-hub receipts invisible)")
        row = _row_stub(rid, axis)
        if rec.get(rid) and m._w4_missing(row, {rid: good}) != "":
            fails.append(f"a well-formed nav-hub receipt was REJECTED: {m._w4_missing(row, {rid: good})!r}")
        if m._w4_missing(row, {rid: stepless}) == "":
            fails.append("a STEPLESS receipt (the old broken shape) was ACCEPTED - the gate does not bite")
    finally:
        tmp.unlink(missing_ok=True)

    if fails:
        print(f"{RED}FAIL{RST} w4-navhub-receipt-shape - " + " | ".join(fails))
        return 1
    print(f"{GREEN}PASS{RST} w4-navhub-receipt-shape - a 4-page fit receipt in the full_journeys_w4navhub namespace "
          "closes the row; a stepless receipt is rejected (the plumbing bites both ways)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
