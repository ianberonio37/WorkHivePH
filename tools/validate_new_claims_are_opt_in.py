#!/usr/bin/env python3
"""new-claims-are-opt-in - T84: an AI may reword what you wrote; it may not assert new things
about you by default (2026-08-26).

resume.html's review sheet is a good pattern: the AI only ever SUGGESTS, and nothing reaches the
document until the worker approves it. But two different acts were arriving with the same default.

  REWRITE  polish a bullet the worker wrote -> shown as "Was: <their text>", pre-ticked.
           Their content, improved, with the change visible. Fine.
  ADD      "suggested highlights" from tailor_to_jd -> pushed into their experience, pre-ticked,
           and with no "Was:", because there is no before. These are NET-NEW CLAIMS ABOUT THE
           WORKER, generated with the JOB AD in context - exactly the pressure that produces a
           line they cannot back up in an interview.

FOUND: both were checked:true, so the default path (Tailor, then Apply) added up to five such
claims without one deliberate act of accepting any of them. The prompt does instruct the model to
keep highlights truthful and grounded in stated skills, and that is worth having - but a prompt is
the only thing enforcing it, and pre-ticking removes the human check meant to be the backstop.

THE ASSERTION: in a review sheet, an item whose apply() PUSHES a new entry must default unchecked.
One whose apply() ASSIGNS over existing content may be pre-ticked - it is an edit the worker can
see, and undo covers it.

★IT READS THE APPLY FUNCTION, NOT THE LABEL. Whether something is an addition or an edit is
decided by what it does to the document (.push vs assignment), which no wording can disguise.

★AND IT DOES NOT BAN PRE-TICKING. Making every suggestion opt-in would push workers toward
tapping Apply without reading, which is the behaviour this is trying to prevent. Only new claims
about a person carry the burden.

Usage: python tools/validate_new_claims_are_opt_in.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"_bak|backup|node_modules|_fixtures|^index-.*test", re.I)

# one review-sheet item: items.push({ ... }) up to its closing brace, allowing one nesting level
ITEM = re.compile(r"items\.push\(\s*\{(?:[^{}]|\{[^{}]*\})*\}", re.S)
# ★THIS MATCHER WAS BLIND FIRST. It bounded the apply body with [^;]{0,400}, and every real
# apply is a few statements long - full of semicolons - so it matched nothing and the gate
# passed against the very world it was built to catch. Caught by teeth-proving, which is the
# only reason it is not registered vacuous.
ADDS = re.compile(r"apply\s*:\s*\([^)]*\)\s*=>[\s\S]{0,500}?\.push\s*\(", re.S)
CHECKED_TRUE = re.compile(r"\bchecked\s*:\s*true\b")


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html"))) if not SKIP.search(Path(f).name)]
    items, bad = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        if "items.push(" not in src:
            continue
        for m in ITEM.finditer(src):
            body = m.group(0)
            items += 1
            if ADDS.search(body) and CHECKED_TRUE.search(body):
                line = src[:m.start()].count("\n") + 1
                grp = re.search(r"group\s*:\s*['\"]([^'\"]{0,60})", body)
                bad.append(f"{name}:{line} \"{grp.group(1) if grp else '?'}\" adds a new entry, pre-ticked")

    print(f"  review-sheet items: {items} | new claims pre-accepted: {len(bad)}")
    for x in bad[:6]:
        print("    - " + x)

    if bad:
        print("FAIL new-claims-are-opt-in - a suggestion that ADDS a claim about the worker arrives already")
        print("    accepted, so the default path writes it into their document with no deliberate act of")
        print("    approving it. Rewording what they wrote may be pre-ticked; asserting something new")
        print("    about them may not. Set checked:false on the additions.")
        return 1
    if items == 0:
        print("SKIP new-claims-are-opt-in - no review-sheet items found to check")
        return 0
    print(f"PASS new-claims-are-opt-in - of {items} review-sheet items, every one that ADDS a claim "
          "waits to be ticked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
