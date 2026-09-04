#!/usr/bin/env python3
"""toast-is-readable - T182: a message shown too briefly was never shown (2026-08-26).

A toast is how this platform says "saved", "not saved", "you cannot do that yet". It
is the entire receipt for most actions, and a receipt that vanishes before it can be
read is worse than none: the action LOOKS silent, so the person repeats it. That is
not hypothetical here - the recorded 0ms incident had nine refusals displayed for zero
milliseconds, which is to say never displayed at all, on the paths where the user most
needed to know why they were refused.

MEASURED 2026-08-26 and the class is EXTINCT: 937 showToast calls across the platform,
906 on their page's default and 31 with an explicit duration - all between 4000 and
7000ms. Every one of the 27 per-page showToast definitions holds its toast for
2200-3500ms. Nothing anywhere is under 1500ms.

TWO ASSERTIONS, guarding the absence rather than fixing a present defect:
  calls        no showToast call passes an explicit duration below the floor
  definitions  no showToast implementation holds its toast for less than the floor

★THE FLOOR IS 1500ms AND IT IS DELIBERATELY LOW. This gate is not litigating whether
3000 beats 3500 - that is a design judgement 27 pages have already made sensibly, and a
gate that argued it would be enforcing taste. It catches the thing that is objectively
broken: a message a human cannot finish reading.

★THE CENSUS BEHIND IT PARSES ARGUMENTS, IT DOES NOT SCAN A WINDOW, and that matters. A
first version looked for the nearest `, <number>)` after each call and reported ten
short toasts - every one false. It had matched `slice(0, 24)`, `setTimeout(..., 60)`
and other numerics belonging to entirely different calls, including a "24ms toast" in
utils.js that does not exist. Only balanced-paren splitting knows which arguments
belong to which call.

Usage: python tools/validate_toast_is_readable.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FLOOR_MS = 1500

SKIP = re.compile(r"backup|test|^index-", re.I)
CALL = re.compile(r"\bshowToast\s*\(")
DEF = re.compile(r"function\s+showToast\s*\(([^)]*)\)")
TIMEOUT = re.compile(r"setTimeout\s*\([^,]*,\s*(\d+)")
FALLBACK = re.compile(r"(?:ms|dur|duration)\s*(?:\|\||\?\?)\s*(\d+)")
DEFAULT_ARG = re.compile(r"=\s*(\d+)")


def split_args(src: str, open_idx: int):
    """Top-level arguments of the call whose '(' sits at open_idx. Quote- and nest-aware."""
    depth, i, args, cur, quote = 0, open_idx, [], [], None
    while i < len(src) and i - open_idx < 4000:
        ch = src[i]
        if quote:
            if ch == "\\":
                cur.append(src[i:i + 2]); i += 2; continue
            if ch == quote:
                quote = None
            cur.append(ch)
        elif ch in "\"'`":
            quote = ch; cur.append(ch)
        elif ch in "([{":
            depth += 1
            if depth > 1:
                cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                args.append("".join(cur).strip())
                return args
            cur.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(cur).strip()); cur = []
        else:
            cur.append(ch)
        i += 1
    return None


def main() -> int:
    files = [f for f in (sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))))
             if not SKIP.search(Path(f).name)]
    if not files:
        print("SKIP toast-is-readable - no pages found")
        return 0

    calls = defs = 0
    short_calls, short_defs = [], []
    for f in files:
        name = Path(f).name
        src = io.open(f, encoding="utf-8", errors="replace").read()

        for m in CALL.finditer(src):
            args = split_args(src, m.end() - 1)
            if args is None:
                continue
            calls += 1
            nums = [int(a) for a in args[1:] if re.fullmatch(r"\d+", a)]
            if nums and nums[-1] < FLOOR_MS:
                line = src[:m.start()].count("\n") + 1
                short_calls.append(f"{name}:{line} shows a toast for {nums[-1]}ms: {args[0][:56]}")

        for m in DEF.finditer(src):
            defs += 1
            body = src[m.end():m.end() + 900]
            found = ([int(x) for x in TIMEOUT.findall(body)]
                     + [int(x) for x in FALLBACK.findall(body)]
                     + [int(x) for x in DEFAULT_ARG.findall(m.group(1))])
            low = [n for n in found if n < FLOOR_MS]
            if low:
                line = src[:m.start()].count("\n") + 1
                short_defs.append(f"{name}:{line} showToast holds its message {min(low)}ms")

    print(f"  showToast calls: {calls} | definitions: {defs} | floor: {FLOOR_MS}ms")
    fails = short_calls + short_defs
    if fails:
        print(f"FAIL toast-is-readable - {len(fails)} message(s) shown too briefly to read:")
        for x in fails[:12]:
            print("    - " + x)
        if len(fails) > 12:
            print(f"    ... and {len(fails) - 12} more")
        print("    A receipt that vanishes before it can be read is worse than none - the action looks")
        print("    silent, so the person does it again. The recorded incident was nine REFUSALS shown")
        print("    for zero milliseconds, on exactly the paths where the reason mattered most.")
        return 1
    print(f"PASS toast-is-readable - all {calls} toast calls and {defs} implementations hold their "
          f"message long enough to read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
