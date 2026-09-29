#!/usr/bin/env python3
"""prove_w4_confusions_receipt_shape.py - TEETH for the confusion-row receipt plumbing (2026-09-14, no browser).

tools/prove_w4_confusions.mjs writes .tmp/mcp_walks/W4confusions_<axis>.json; live_walk_manifest._w4_receipts must
read it (the W4* glob in mcp_walks) and _w4_missing must grade a `kind: confusion` row as BROWSER-SHAPED (>= 4 distinct
pages, a fit dict on every step, the axis matched). tools/bank_w4_passers.py then banks only a receipt that is BOTH
ok and complete - a predicate that failed writes ok:false and must never bank, however clean its overlap record.
A fix with no gate silently rots (the nav-hub plumbing once wrote stepless receipts and no row could close), so this
asserts the plumbing bites on synthetic receipts whose truth is known:

  well-formed (4 distinct pages, fit dict per step, axis matched, ok)  -> _w4_missing MUST accept ('')  AND the banker's
                                                                         condition (ok and complete) MUST hold
  predicate failed (same steps, ok:false)                              -> complete, but the banker's condition MUST NOT hold
  three pages (a short path)                                           -> _w4_missing MUST reject
  fit missing on one step                                              -> _w4_missing MUST reject
  and _w4_receipts MUST see a receipt written to the mcp_walks/W4confusions_* namespace.

  python tools/prove_w4_confusions_receipt_shape.py [--check]
"""
from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"


def _row(rid: str, axis: str) -> dict:
    dev, lang = axis.split(" ", 1)
    return {"id": rid, "status": "specced", "axis": {"device": dev, "language": lang},
            "title": "Lived start to end: the confusion C99 (synthetic) at a: - a · " + axis,
            "pages": ["index.html", "a.html", "b.html", "c.html"],
            "w4": {"kind": "confusion", "confusion": "C99", "component": None, "improvement": "synthetic"}}


def _steps(pages, fit=True):
    return [{"page": p, "chars": 900, "identityKept": True, **({"fit": {"findings": 0, "occlusion": []}} if fit else {})}
            for p in pages]


def main() -> int:
    axis = "phone-390 en"
    rid = "W4CONFTEST"
    four = ["index.html", "a.html", "b.html", "c.html"]
    base = {"id": rid, "instrument": "tools/prove_w4_confusions.mjs", "w4": {"axis": axis, "confusion": "C99", "predicate": "synthetic"}}
    good = {**base, "ok": True, "steps": _steps(four)}
    failed = {**base, "ok": False, "problems": ["C99 not lived clean: synthetic"], "steps": _steps(four)}
    short = {**base, "ok": True, "steps": _steps(four[:3])}
    nofit = {**base, "ok": True, "steps": _steps(four[:3]) + _steps(four[3:], fit=False)}
    banker_ok = lambda res, missing: bool(res.get("ok")) and missing == ""   # noqa: E731 - the banker's exact condition

    tmp = ROOT / ".tmp" / "mcp_walks" / "W4confusions_receiptshape-selftest.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    fails = []
    try:
        tmp.write_text(json.dumps({"instrument": "tools/prove_w4_confusions.mjs", "axis": axis, "results": [good]}), encoding="utf-8")
        sys.path.insert(0, str(ROOT / "tools"))
        import live_walk_manifest as m
        importlib.reload(m)
        rec = m._w4_receipts()
        if rid not in rec:
            fails.append("_w4_receipts does NOT read the mcp_walks/W4confusions_* namespace (confusion receipts invisible)")
        row = _row(rid, axis)
        miss_good = m._w4_missing(row, {rid: good})
        if miss_good != "":
            fails.append(f"a well-formed confusion receipt was REJECTED: {miss_good!r}")
        if not banker_ok(good, miss_good):
            fails.append("the banker's condition does not hold for a well-formed ok receipt")
        miss_failed = m._w4_missing(row, {rid: failed})
        if banker_ok(failed, miss_failed):
            fails.append("a receipt whose PREDICATE FAILED (ok:false) satisfies the banker's condition - a failed confusion could bank")
        if m._w4_missing(row, {rid: short}) == "":
            fails.append("a THREE-page receipt was ACCEPTED - the >= 4 distinct pages rule does not bite for confusion rows")
        if m._w4_missing(row, {rid: nofit}) == "":
            fails.append("a receipt with a step lacking `fit` was ACCEPTED - confusion rows are not graded as browser-shaped")
    finally:
        tmp.unlink(missing_ok=True)

    if fails:
        print(f"{RED}FAIL{RST} w4-confusions-receipt-shape - " + " | ".join(fails))
        return 1
    print(f"{GREEN}PASS{RST} w4-confusions-receipt-shape - a 4-page fit receipt in mcp_walks/W4confusions_* closes a confusion "
          "row and satisfies the banker; a failed predicate (ok:false), a 3-page path and a fit-less step are each refused")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
