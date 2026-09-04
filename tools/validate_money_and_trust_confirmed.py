#!/usr/bin/env python3
r"""money-trust-confirmed - T67/T50: the two writes that cannot be taken back.

Most admin actions are reversible: approve a listing, flip a voucher, edit a note. Two
are not, in the way that matters:

  money   service_credit_topups -> 'verified' MINTS credits into a provider's wallet.
          Once spent they cannot be pulled back from this console. The mirror action is
          just as sharp: 'rejected' refuses a top-up somebody actually PAID for.
  trust   marketplace_sellers.kyb_verified / cert_verified is the platform VOUCHING for
          a stranger to a buyer who is about to send them money. It is the same claim
          trust-claim-backed keeps honest at the render end; this keeps it honest at the
          grant end.

★THE FAILURE MODE IS NOT A CHANGE OF MIND, IT IS THE WRONG ROW. Both live in per-row
button lists on the founder console, 12px apart, one row per seller or per top-up. A
misclick does not undo the last action - it applies a real one to the wrong person, and
the person who loses is the one who sent the GCash or the one now vouched for.

FOUND 2026-08-26: founder-console carried 6 writes and ZERO whConfirm. svcTopupDecide()
minted credits on a single click ("Credits minted to the provider's wallet") and the
verify-kyb / verify-cert branch granted the badge with nothing asked. Both now confirm
with the consequence NAMED - and the seller's name in the trust one, because the name is
the part a misclick gets wrong. Verified live: cancelling sends zero writes.

THE ASSERTION: every client write to a money or trust column is preceded by a confirm in
the same handler.

★NARROW ON PURPOSE. It does not demand a confirm on every admin verb - approving a
listing is reversible and a dialog there is friction that trains people to click through.
Only these two, because only these two cannot be undone from the console that performs
them.

Usage: python tools/validate_money_and_trust_confirmed.py
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

# (what it is, how the write looks)
GUARDED_WRITES = [
    ("mints or refuses paid credits",
     re.compile(r"from\(\s*['\"]service_credit_topups['\"]\s*\)\s*\.?\s*\n?\s*\.update\(", re.S)),
    ("grants a verification badge buyers rely on",
     re.compile(r"(kyb_verified|cert_verified)\s*:\s*true", re.I)),
]
CONFIRM = re.compile(r"whConfirm\s*\(", re.I)


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def preceding_scopes(src: str, pos: int):
    """Every enclosing block's text UP TO the write, innermost outward.

    ★THE NEAREST BLOCK IS NOT THE HANDLER. The first version of this gate took the closest
    enclosing braces and reported platform-actions unconfirmed - with the confirm sitting
    four lines above, just outside the `try {` the write lives in. Guarding before the try
    is not a loophole, it is the CORRECT place to guard: a cancel there leaves the button
    untouched. A confirm counts when it precedes the write in ANY enclosing scope, so this
    yields all of them and stops at the function boundary rather than guessing which one.
    """
    out, start, seen = [], src.rfind("{", 0, pos), 0
    while start >= 0 and seen < 8:
        depth, i, close = 0, start, -1
        while i < len(src) and i - start < 40000:
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    close = i
                    break
            i += 1
        if close >= pos:                    # this block really does contain the write
            out.append(src[start:pos])
            seen += 1
            head = src[max(0, start - 120):start]
            if re.search(r"(function\b|=>|\basync\b)[^{}]*$", head):
                break                       # reached the handler; no need to go wider
        start = src.rfind("{", 0, start)
    out.append(src[max(0, pos - 2500):pos])
    return out


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html"))) if not SKIP.search(Path(f).name)]
    if not files:
        print("SKIP money-trust-confirmed - no pages found")
        return 0

    checked, unguarded = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for what, rx in GUARDED_WRITES:
            for m in rx.finditer(src):
                checked += 1
                if not any(CONFIRM.search(b) for b in preceding_scopes(src, m.start())):
                    line = src[:m.start()].count("\n") + 1
                    unguarded.append(f"{name}:{line} {what} with no confirm in the same handler")

    print(f"  money/trust writes: {checked} | unconfirmed: {len(unguarded)}")
    if unguarded:
        print(f"FAIL money-trust-confirmed - {len(unguarded)} irreversible admin write(s) ask nothing:")
        for x in unguarded[:8]:
            print("    - " + x)
        print("    These sit in per-row button lists, so the failure is not a change of mind but the")
        print("    WRONG ROW - and the person who loses is the one who sent the GCash, or the buyer")
        print("    who trusted a badge. Name the consequence, and name WHO it applies to.")
        return 1
    if checked == 0:
        print("SKIP money-trust-confirmed - no money or trust writes found to check")
        return 0
    print(f"PASS money-trust-confirmed - all {checked} money and trust writes confirm before they act.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
