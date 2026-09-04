#!/usr/bin/env python3
"""validate_resume_review_sheet.py — T33's lock: the resume flow hands the worker a REVIEW SHEET, not
a finished CV to take or leave.

T33's north star: after upload -> extract, the worker can ACCEPT, EDIT or REJECT each extracted item
before it becomes their resume — the machine's guess is a draft the human curates, not a verdict. The
failure would be a one-shot "here is your CV" with no per-item control. This gate holds that the
review surface offers all three affordances and a per-item selection control:
  1. ACCEPT / include affordance present,
  2. EDIT affordance present,
  3. REJECT / remove affordance present,
  4. a per-item selection control (checkbox) so the choice is item-by-item, not all-or-nothing.

Static (file read), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import sys

CHECK_NAMES = ["resume-review-sheet"]
PAGE = "resume.html"


def _read() -> str | None:
    try:
        return io.open(PAGE, encoding="utf-8").read()
    except Exception:
        return None


def check(html: str) -> list[str]:
    problems: list[str] = []
    low = html.lower()
    if low.count("accept") < 1:
        problems.append("no ACCEPT/include affordance — the extracted items cannot be individually kept")
    if low.count("edit") < 1:
        problems.append("no EDIT affordance — the worker cannot correct an extracted item")
    if low.count("reject") < 1:
        problems.append("no REJECT/remove affordance — the worker cannot drop a wrong extraction")
    if html.count('type="checkbox"') < 1:
        problems.append("no per-item checkbox — the review is all-or-nothing, not item-by-item")
    return problems


def main() -> int:
    html = _read()
    if html is None:
        print(f"FAIL resume-review-sheet — {PAGE} not found or unreadable."); return 1
    problems = check(html)
    if problems:
        print("FAIL resume-review-sheet — the resume flow does not offer a per-item review:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS resume-review-sheet — the extracted resume is a review sheet: accept / edit / reject affordances "
          "with per-item checkboxes, so the worker curates the machine's guess rather than taking a finished CV.")
    return 0


def self_test() -> int:
    good = 'accept edit reject <input type="checkbox">'
    fails = []
    if check(good):
        fails.append("a full review sheet should PASS")
    if not any("ACCEPT" in p for p in check(good.replace("accept", "x"))):
        fails.append("missing accept should FAIL")
    if not any("EDIT" in p for p in check(good.replace("edit", "x"))):
        fails.append("missing edit should FAIL")
    if not any("REJECT" in p for p in check(good.replace("reject", "x"))):
        fails.append("missing reject should FAIL")
    if not any("all-or-nothing" in p for p in check(good.replace('type="checkbox"', "x"))):
        fails.append("missing checkbox should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_resume_review_sheet self-test (missing accept/edit/reject/checkbox redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
