#!/usr/bin/env python3
"""quota-warns-before-the-wall - T89: a count is not a warning (2026-08-26).

_shared/rate-limit.ts returns `remaining` on EVERY allowed call, so the platform always knows how
close a hive is to its hourly cap. Nothing consumed it. There is no threshold anywhere in the
codebase, and the only signal a worker ever got was the 429 AFTER the wall - mid-task, with the
work half done. asset-hub was the single surface rendering the number at all, and it rendered it
flat ("12 AI calls remaining this hour"), which reads the same at 12 as at 1.

whQuotaNotice() turns the number the server already sends into a warning at 5 or fewer, names the
reset so "wait" has a "how long", and stays silent when the value is unknown.

★THAT LAST PART WAS A BUG IN THE FIRST VERSION, caught by exercising the shipped helper rather
than trusting it: Number(null) is 0, so a quota the server did not report was announced as "No AI
calls left this hour" - absence rendered as a value, alarming and false. An absent reading is not a
reading of zero.

THE ASSERTION: a rendered quota goes through the helper rather than being concatenated raw, and
the helper still distinguishes unknown from empty.

★IT DOES NOT REQUIRE EVERY AI SURFACE TO SHOW A QUOTA. Most never receive `remaining` at all, and
demanding a plumbing change everywhere would make this a migration rather than a gate. It holds the
surfaces that DO show it to showing it usefully.

Usage: python tools/validate_quota_warns_before_the_wall.py
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

# a bare quota count being built into displayed text
RAW_RENDER = re.compile(r"(?:textContent|innerHTML|innerText)\s*=\s*[^;\n]{0,80}"
                        r"\bremain(?:ing)?\b\s*\+\s*['\"]\s*AI calls?", re.I)
# ★MATCH THE DEFINITION, NOT A CALL. The first version looked for "whQuotaNotice(" and utils.js
# defines it as "whQuotaNotice = function", so the gate reported the helper missing while it sat
# ten lines above - it would have failed forever on a correct file.
HELPER = re.compile(r"whQuotaNotice\s*=\s*function")


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    fails = []

    utils = ROOT / "utils.js"
    if not utils.exists():
        print("SKIP quota-warns-before-the-wall - utils.js not present")
        return 0
    u = strip_comments(utils.read_text(encoding="utf-8", errors="replace"))
    if not HELPER.search(u):
        fails.append("utils.js no longer defines whQuotaNotice - there is nothing to turn the server's "
                     "remaining count into a warning")
    else:
        if "=== null" not in u.replace("=== undefined", "=== null"):
            fails.append("whQuotaNotice does not special-case an unknown remaining, so Number(null)=0 "
                         "makes it announce 'No AI calls left' to someone whose quota it never learned")
        if not re.search(r"resets on the hour", u):
            fails.append("the notice does not say when the limit resets - 'wait' without 'how long' is "
                         "not a remedy")

    raw = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))):
        name = Path(f).name
        if SKIP.search(name):
            continue
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in RAW_RENDER.finditer(src):
            raw.append(f"{name}:{src[:m.start()].count(chr(10)) + 1} renders a bare quota count")

    print(f"  bare quota renders: {len(raw)} | helper problems: {len(fails)}")
    for x in (raw + fails)[:6]:
        print("    - " + x)

    if raw or fails:
        print("FAIL quota-warns-before-the-wall - the server says how many calls are left on every")
        print("    request; showing that as a flat number reads the same at 12 as at 1, so the worker")
        print("    still learns the limit exists by hitting it mid-task. Route it through whQuotaNotice.")
        return 1
    print("PASS quota-warns-before-the-wall - a shown quota warns before it runs out, names the reset, "
          "and stays silent when unknown.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
