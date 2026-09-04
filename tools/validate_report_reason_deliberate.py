#!/usr/bin/env python3
"""validate_report_reason_deliberate.py — T31's lock: reporting a post requires a DELIBERATE
reason, and the audit row names whose post it was.

Walked live (T31): the report dialog's select DEFAULTED to 'Harassment' (no placeholder), so an
untouched Send silently filed the gravest accusation — and openReport() reset the value back to
'harassment' on every open; the audit row also carried a blank target_name ('report_post | Bryan
Garcia | (blank)'), a report pointing at nothing. Fixed+verified live 2026-09-02: placeholder-first
('Choose a reason…', value='', disabled), submitReport refuses an empty reason with the triage-why
('Pick a reason - it is what your supervisor triages by.'), openReport resets to the PLACEHOLDER,
and the audit write carries the reported post's author (verified row: 'report_post | Bryan Garcia |
Wilfredo Malabanan | unsafe').

Lock: all four shapes. Teeth: each reddens when reverted.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["report-reason-deliberate"]

PLACEHOLDER_RE = re.compile(r'<option value="" selected disabled>Choose a reason')
VALIDATE_RE = re.compile(r"if \(!reason\) \{[\s\S]{0,300}?return;")
RESET_RE = re.compile(r"function openReport\(postId\) \{[\s\S]{0,600}?report-reason'\)\.value = ''")
TARGET_RE = re.compile(r"writeAuditLog\('report_post'[^;]{0,220}author_name")


def problems_for(src: str) -> list[str]:
    out = []
    if not PLACEHOLDER_RE.search(src):
        out.append("community.html: the report-reason placeholder is gone — an untouched select "
                   "defaults to a real accusation again")
    if not VALIDATE_RE.search(src):
        out.append("community.html: submitReport no longer refuses an empty reason")
    if not RESET_RE.search(src):
        out.append("community.html: openReport no longer resets to the placeholder — it pre-files "
                   "a reason again (the reset that defeated the placeholder)")
    if not TARGET_RE.search(src):
        out.append("community.html: the report's audit write no longer carries the reported post's "
                   "author — target_name goes blank again")
    return out


def main() -> int:
    src = io.open(ROOT / "community.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL report-reason-deliberate:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS report-reason-deliberate — reporting requires a deliberate reason (placeholder + "
          "refusal + placeholder-reset) and the audit row names the reported author.")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "community.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    if not any("placeholder is gone" in p for p in problems_for(PLACEHOLDER_RE.sub('<option value="harassment">X', src))):
        fails.append("removing the placeholder must redden")
    if not any("pre-files" in p for p in problems_for(RESET_RE.sub("function openReport(postId) { document.getElementById('report-reason').value = 'harassment'", src))):
        fails.append("reverting the reset must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_report_reason_deliberate self-test (removed placeholder + reverted reset both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
