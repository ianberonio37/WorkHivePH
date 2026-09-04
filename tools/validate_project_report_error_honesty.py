#!/usr/bin/env python3
"""validate_project_report_error_honesty.py — T73's lock instrument: the project-report page tells a
reader the TRUTH about why they cannot see a project — access vs. not-found vs. server fault — and never
asserts 'this project no longer exists' to someone from another hive for whom it is merely invisible.

T73 measured the break: a server fault answered 7 reads with 500 and the page told the reader they might
lack permission (sending them to ask an admin for access they already had); and a cross-hive stakeholder,
for whom RLS simply filters the row, was told 'This project no longer exists' — a deletion claim that is
false. The fix reads the error CODE: 42501 (insufficient_privilege) = the caller was identified and
refused → an ACCESS message ('you do not have access — ask its manager'); anything else visible-but-empty
→ 'not found or not visible to you' (never 'no longer exists'); a real fault → retry, not 'ask for access'.

Assertions on project-report.html (comments stripped; each refutable — see the self-test):
  1. THE CODE IS READ — `42501` is branched on (access is distinguished from absence).
  2. THE ACCESS MESSAGE EXISTS — a 'do not have access' / 'No access' string for the 42501 branch.
  3. NO FALSE DELETION — the rendered copy never says 'no longer exists' (a filtered row is not a deleted
     one). Allowed in a comment that documents the old bug; forbidden in a live string.

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "project-report.html"

CHECK_NAMES = ["project-report-error-honesty"]


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    return src


def check(src: str) -> list[str]:
    nc = _strip_comments(src)
    problems: list[str] = []
    if "42501" not in nc:
        problems.append("42501 is not branched on — access (a refused-but-identified caller) is not "
                        "distinguished from a genuinely-absent project.")
    if not re.search(r"do not have access|does not have access|don't have access|No access", nc, re.I):
        problems.append("no ACCESS message for the 42501 branch — a refused caller is not told it is a "
                        "permission boundary.")
    if re.search(r"no longer exists", nc, re.I):
        problems.append("the copy asserts 'no longer exists' — a row RLS merely FILTERS for a cross-hive "
                        "reader is not a deleted one; this is the false-deletion claim T73 removed.")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL project-report-error-honesty: project-report.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL project-report-error-honesty — the page does not tell the truth about why a project is "
              "unseen:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS project-report-error-honesty — 42501 is distinguished (access, not absence), the access "
          "message exists, and the copy never falsely claims the project 'no longer exists'.")
    return 0


def self_test() -> int:
    fails = []
    good = "if (code === '42501') { _title='No access'; _body='You do not have access to this project.'; } else { _title='not found or not visible'; }"
    if check(good):
        fails.append("the real access/absent-distinguishing copy should PASS")
    if not any("42501" in p for p in check("_body='You do not have access'; _title='not visible';")):
        fails.append("not branching on 42501 should FAIL")
    if not any("ACCESS message" in p for p in check("if (code==='42501'){ _title='Cannot show'; }")):
        fails.append("a 42501 branch with no access message should FAIL")
    if not any("no longer exists" in p for p in check("if(code==='42501'){_body='you do not have access';} _body='This project no longer exists.';")):
        fails.append("a live 'no longer exists' string should FAIL")
    # 'no longer exists' ONLY in a comment must PASS
    if check("// old bug: said 'this project no longer exists'\nif(code==='42501'){_body='you do not have access';}"):
        fails.append("'no longer exists' only inside a comment should NOT fail")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_project_report_error_honesty self-test (no-42501 / no-access-msg / live-deletion redden; comment spared)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
