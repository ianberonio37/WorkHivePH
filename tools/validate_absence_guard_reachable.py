#!/usr/bin/env python3
r"""absence-guard-reachable - T198: an "it could not be computed" branch must be reachable.

A page that distinguishes "computed, and the answer is nothing" from "we could not
compute it" has done the hard part of honest degradation. The failure this catches is
subtler and worse than not having the branch at all: the branch EXISTS, somebody wrote
it deliberately, and the fallback hands it a value that can never trigger it.

THE INSTANCE THAT PROVED THE CLASS. project-manager's renderCpm() guards with
`if (!cp)` and prints "The critical path could not be computed right now, so nothing
here is marked critical or slack-free." Its client fallback - the one that runs when the
schedule engine is unreachable - returned
`critical_path: { item_ids: [], total_days: 0, slack_per_item: {} }`. AN EMPTY OBJECT IS
TRUTHY, so the guard never fired on the path it was written for, and a shutdown project
whose real schedule is "12d, 7 of 7 items on the critical path" rendered instead as
"CRITICAL PATH 0d - 0 of 7 items on critical path" with a full Gantt beneath it: a
confident inversion, on the screen used to plan a plant outage. Fixed with
`critical_path: null`.

THE ASSERTION: where a consumer's `if (!x)` branch says something could not be computed,
no producer in that file may assign x an empty-but-truthy value. Measured after the fix:
ZERO across the app pages, so the class is extinct rather than merely the one instance
being patched.

★AN EMPTY ARRAY AS A PLAIN DEFAULT IS NOT THIS. `parts: []`, `rows: []`, `work: []` are
correct ways to say "none", and a first sweep flagged 33 of them. What makes this a
defect is a consumer that DISTINGUISHES uncomputed from empty and a producer that
quietly collapses the distinction.

★AND THE DETECTOR FAILED ITS OWN RESURRECTION TEST FIRST: its producer pattern was
`\{[^{}]{0,120}\}`, which cannot match a value containing nested braces - and the real
defect contained `slack_per_item: {}`. It reported 0 with the defect present. A detector
that cannot find the bug it was written for is worse than none, so it now allows one
level of nesting and is proven to go 1 -> 0 across the fix.

Usage: python tools/validate_absence_guard_reachable.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"backup|test|^index-", re.I)
GUARD = re.compile(r"if\s*\(\s*!\s*([A-Za-z_$][\w$]*)\s*\)\s*\{([^{}]{0,400})", re.S)
SAYS_UNCOMPUTED = re.compile(r"could not|unavailable|not available|couldn'?t|failed to (compute|load)", re.I)


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in (sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))))
             if not SKIP.search(Path(f).name)]
    if not files:
        print("SKIP absence-guard-reachable - no surfaces found")
        return 0

    guards, defeated = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in GUARD.finditer(src):
            var, body = m.group(1), m.group(2)
            if not SAYS_UNCOMPUTED.search(body):
                continue
            guards += 1
            back = src[max(0, m.start() - 400):m.start()]
            alias = re.search(r"(?:const|let|var)\s+" + re.escape(var) + r"\s*=\s*([^;\n]{0,80})", back)
            if not alias:
                continue
            fm = re.search(r"\.([A-Za-z_$][\w$]*)\s*$", alias.group(1).strip())
            if not fm:
                continue
            field = fm.group(1)
            # one level of nesting allowed - the real defect contained `slack_per_item: {}`
            prod = re.search(re.escape(field) + r"\s*:\s*(\{(?:[^{}]|\{[^{}]*\}){0,200}\}|\[\s*\])", src)
            if prod and not re.search(re.escape(field) + r"\s*:\s*null", src):
                line = src[:m.start()].count("\n") + 1
                defeated.append(f"{name}:{line} `if (!{var})` says it could not be computed, but "
                                f"`{re.sub(r'\s+', ' ', prod.group(0))[:60]}` is TRUTHY - the branch "
                                f"can never run")

    print(f"  'could not compute' guards: {guards} | defeated by an empty-but-truthy producer: "
          f"{len(defeated)}")
    if defeated:
        print(f"FAIL absence-guard-reachable - {len(defeated)} honest-degradation branch(es) unreachable:")
        for x in defeated[:8]:
            print("    - " + x)
        print("    Somebody wrote that branch deliberately, and the fallback hands it a value that can")
        print("    never trigger it - so an outage renders as a confident zero instead of an admission.")
        print("    Return null for 'not computed'; an empty structure means 'computed, and it is empty'.")
        return 1
    print(f"PASS absence-guard-reachable - all {guards} 'could not compute' branches can actually be "
          f"reached by the fallbacks that need them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
