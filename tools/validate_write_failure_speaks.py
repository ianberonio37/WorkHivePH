#!/usr/bin/env python3
"""write-failure-speaks - T147: a failed write must not be silent (2026-08-26).

`if (!error) { paint }` with no else is the quietest bug this platform can ship. The
write fails, the screen does not move, and nothing is said - so from the user's side it
is indistinguishable from a dead control. The natural next move is to press it again,
which is how a silent refusal becomes repeated writes.

FOUND ON community's toggleReaction, both branches: tapping an emoji whose insert or
delete failed left the count sitting still with no message. Fixed using the vocabulary
the same page already owns (submitReply uses whWriteError), and the add path names the
one case where doing nothing IS correct - a duplicate reaction (23505) says "You have
already reacted with this emoji" rather than reporting a failure the person cannot act
on. Verified live with an injected 500: the count correctly does not move AND the toast
now reads "Your reaction was not saved. Tap again to retry."

MEASURED AFTER: 223 awaited db writes destructure `error` across the app pages, and ZERO
now guard with a bare `if (!error)` and no else. Resurrection-proven - removing the new
else-branches puts the count back to 1.

★IT IS DELIBERATELY NARROW. It does not demand a particular message, or that every write
speak in a particular way - plenty of writes correctly stay quiet because the render
that follows IS the receipt. It catches one specific shape: the code explicitly took the
error into its hands (destructured it), branched on it, and then dropped it. That is
never intentional.

Usage: python tools/validate_write_failure_speaks.py
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

WRITE = re.compile(r"const\s*\{[^}]*\berror\b[^}]*\}\s*=\s*await\s+db\s*\n?\s*\.?from\(")
SPEAKS = re.compile(r"showToast|whWriteError|whReadError|whAiError|alert\(|throw\b|"
                    r"textContent\s*=|innerHTML\s*=", re.I)


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html"))) if not SKIP.search(Path(f).name)]
    if not files:
        print("SKIP write-failure-speaks - no pages found")
        return 0

    total, silent = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in WRITE.finditer(src):
            total += 1
            after = src[m.end():m.end() + 900]
            guard = re.search(r"if\s*\(\s*!\s*error\s*\)\s*\{", after)
            if not guard:
                continue                       # no !error branch: not this shape
            tail = after[guard.end():guard.end() + 700]
            has_else = re.search(r"\}\s*else\b", tail)
            speaks = SPEAKS.search(after[:guard.start()]) or (has_else and SPEAKS.search(tail))
            if not has_else and not speaks:
                line = src[:m.start()].count("\n") + 1
                silent.append(f"{name}:{line} guards on `if (!error)` and says nothing when it fails")

    print(f"  awaited db writes handling `error`: {total} | silent on failure: {len(silent)}")
    if silent:
        print(f"FAIL write-failure-speaks - {len(silent)} write(s) fail silently:")
        for x in silent[:10]:
            print("    - " + x)
        print("    The screen does not move and nothing is said, so the control looks dead and the")
        print("    natural next move is to press it again - which turns one silent refusal into")
        print("    repeated writes. Use whWriteError, the vocabulary the platform already has.")
        return 1
    print(f"PASS write-failure-speaks - all {total} awaited writes that branch on `error` say something "
          f"when it is set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
