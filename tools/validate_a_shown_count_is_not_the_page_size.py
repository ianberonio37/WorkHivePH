""" -*- coding: utf-8 -*-
A number shown to a person must count the WORLD, not the fetch (T15/T129).

`.limit(N)` then `data.length` on the glass is a sentence about the array wearing the clothes of a
sentence about the plant.

MEASURED 2026-08-28 on logbook's machine-history panel: `.limit(5)` and a title reading
`data.length + ' past repairs on ' + machineId`. 94 machines in the fixture hold more than five
fault_knowledge rows; M-003 holds 77. The panel told a technician "5 past repairs on M-003" - and
this is the panel they consult BEFORE opening equipment. Under-reporting a machine's history to the
person deciding how careful to be is the wrong direction to be wrong in.

★THE CLASS WAS ALREADY KNOWN HERE, WHICH IS WHY THE GATE HOLDS THE SHAPE RATHER THAN ONE SITE.
asset-hub hit the identical bug (AH16: "500 reading(s) in the last 30 days" for an asset with
3,174 - under-reporting by 6x while every mean and sigma above it came from the same truncated
slice) and fixed it by asking for the exact count and rendering "latest N of M". marketplace solves
it a third way, rendering an em-dash when the read was partial rather than a number it cannot
support. Three surfaces, one property; logbook was simply the instance nobody had walked.

THE PROPERTY: where a capped read's length is DISPLAYED, the code must either
  (a) fetch the true total (count:'exact', head:true) and show both, or
  (b) say the number describes the LIST ("latest 5"), or
  (c) refuse to show a number at all when the read was partial.
What it must not do is state the page size as a fact about the world.

★SCOPED TO THE SITES WHERE THE CAP IS REACHABLE. founder-console (500 voucher campaigns) and
marketplace-admin (100 disputes) share the shape, but hold 3 and 0 rows - the ceiling is not
reachable and gating them would be enforcing a rule against arithmetic that cannot happen yet.
Recorded in T15's basis instead, so the day either grows a denominator, the note is there.

TEETH: synthetic negatives - each disclosure removed in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """Both fixes are documented directly above the code, quoting the wrong sentence they replaced."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(sources: dict) -> list:
    out = []

    lb = sources.get("logbook.html")
    if lb is None:
        out.append("logbook.html: missing - re-point this gate")
    else:
        s = _strip_comments(lb)
        i = s.find("async function loadMachineHistory")
        body = s[i:i + 3000] if i >= 0 else ""
        if not body:
            out.append("logbook.html: loadMachineHistory() is gone - the panel a technician reads "
                       "before opening a machine has been removed")
        else:
            if not re.search(r"count:\s*['\"]exact['\"]", body):
                out.append("logbook.html: the machine-history panel no longer asks for the TRUE total - "
                           "with a .limit() read its title states the page size as the machine's "
                           "history. 94 machines in the fixture exceed the cap; the worst holds 77 and "
                           "would announce 5")
            if not re.search(r"showing the latest|Latest ", body):
                out.append("logbook.html: the panel no longer discloses that it is showing a SUBSET - "
                           "a total with no 'showing the latest N' reads as the whole history")

    ah = sources.get("asset-hub.html")
    if ah is None:
        out.append("asset-hub.html: missing - re-point this gate")
    else:
        s = _strip_comments(ah)
        if "reading(s) in the last 30 days" in s:
            # the disclosure must live near the claim
            j = s.find("reading(s) in the last 30 days")
            near = s[j:j + 900]
            if not re.search(r"count:\s*['\"]exact['\"]", near):
                out.append("asset-hub.html: the 30-day readings footer no longer fetches the exact "
                           "count - AH16's defect returns, where the footer under-reports by 6x while "
                           "every mean and sigma above it is computed from the same truncated slice")
            if not re.search(r"latest \$\{rows\.length\} of|latest .{0,12} of ", near):
                out.append("asset-hub.html: the readings footer no longer renders 'latest N of M' - the "
                           "cap is invisible again")
    return out


def _load() -> dict:
    out = {}
    for n in ("logbook.html", "asset-hub.html"):
        p = ROOT / n
        out[n] = io.open(p, encoding="utf-8", errors="replace").read() if p.exists() else None
    return out


def selftest() -> int:
    src = _load()
    cases = [("both panels disclose their cap today", audit(src), 0)]
    # ★THE MUTATION MUST LAND INSIDE THE SUBJECT. logbook.html holds THREE
    # `count: 'exact', head: true` occurrences; replacing the first one edits an unrelated query
    # 1,600 lines away, leaves loadMachineHistory untouched, and the negative passes while
    # detecting nothing - the same scope-the-check-to-its-subject error this gate family keeps
    # making. Cut the function body out, mutate that, and splice it back.
    m = dict(src)
    _lb = src["logbook.html"]
    _i = _lb.find("async function loadMachineHistory")
    _body = _lb[_i:_i + 3000]
    m["logbook.html"] = _lb[:_i] + _body.replace("count: 'exact', head: true", "head: true", 1) + _lb[_i + 3000:]
    cases.append(("logbook losing the exact-count read is caught", audit(m), 1))
    m2 = dict(src)
    m2["logbook.html"] = src["logbook.html"].replace("showing the latest ", "").replace("'Latest '", "''")
    cases.append(("logbook losing the subset disclosure is caught", audit(m2), 1))
    m3 = dict(src)
    m3["logbook.html"] = src["logbook.html"].replace("async function loadMachineHistory",
                                                     "async function _retired_loadMachineHistory")
    cases.append(("retiring the history panel is caught", audit(m3), 1))
    m4 = dict(src)
    j = src["asset-hub.html"].find("reading(s) in the last 30 days")
    seg = src["asset-hub.html"][j:j + 900]
    m4["asset-hub.html"] = src["asset-hub.html"].replace(seg, seg.replace("count: 'exact', head: true", "head: true"), 1)
    cases.append(("asset-hub losing its exact count is caught", audit(m4), 1))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    findings = audit(_load())
    print("a-shown-count-is-not-the-page-size - a number on the glass counts the world, not the fetch")
    if findings:
        print("\nFAIL - a capped read's length is being stated as a fact about the plant:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every capped count names its true total and says it is showing a subset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
