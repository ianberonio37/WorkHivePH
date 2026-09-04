#!/usr/bin/env python3
"""absent-money-is-not-zero - T94: a peso amount that did not arrive must not render as zero.

"₱0.00" is a confident statement that something moved nothing. When the number is actually ABSENT -
a read that failed, a column a view reports nullable, a join that missed - printing zero trades a
visible defect (₱NaN) for an invisible one, and the reader cannot tell. A filed top-up of ₱300 once
rendered as ₱0.00, and a ledger line of unknown value as "+₱0", which says the entry moved nothing:
the most misleading thing a ledger can say.

★THE GUARANTEE IS CENTRAL, so this checks the centre first: whFmtPeso returns a GAP for null,
undefined and '' and for anything non-finite, while a real zero still prints ₱0. A person can act on
"we do not know"; they cannot act on a wrong number.

★AND IT CHECKS THE BYPASS, because a helper is only as good as its use: `'₱' + Number(x || 0)` is
the exact resurrection, since Number(null) is 0 AND finite. Such a line is allowed ONLY inside the
`typeof whFmtPeso === 'function' ? ... : ...` fallback that exists for a page whose utils.js did not
load - anywhere else it is a live path that will one day be handed a null.

★WHY IT MATTERS EVEN THOUGH THE BASE TABLES ARE NOT NULL: Postgres does not propagate NOT NULL
through a VIEW, so every v_*_truth column reports as nullable, and the reads here go through those
views. The door is already open; the helper is what stands in it.

Re-drive: python tools/validate_absent_money_is_not_zero.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("node_modules", "_fixtures", ".tmp", "test-data-seeder", "tools", ".git")


def main() -> int:
    failures = []

    # 1. the centre holds
    utils = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    m = re.search(r"function whFmtPeso\([^)]*\)\s*\{(.*?)\n\}", utils, re.S)
    if not m:
        print("FAIL absent-money-is-not-zero - whFmtPeso is gone from utils.js; every money render "
              "on the platform depends on it")
        return 1
    body = m.group(1)
    if not re.search(r"n === null \|\| n === undefined \|\| n === ''", body):
        failures.append("whFmtPeso no longer treats null/undefined/'' as ABSENT - Number(null) is 0 "
                        "and finite, so an amount that never arrived would print as a confident ₱0.00")
    if not re.search(r"isFinite", body):
        failures.append("whFmtPeso no longer rejects non-finite values - ₱NaN or ₱Infinity reaches "
                        "the glass")
    if not re.search(r"opts\.gap", body):
        failures.append("whFmtPeso lost its gap character - an absent amount has nothing to render as")

    # 2. nobody bypasses it on a live path
    bypass = re.compile(r"['\"]₱['\"]\s*\+\s*Number\([^)]*\|\|\s*0\s*\)")
    live = []
    for p in sorted(ROOT.glob("*.html")) + [ROOT / "utils.js"]:
        if set(p.relative_to(ROOT).parts[:-1]) & set(SKIP):
            continue
        src = io.open(p, encoding="utf-8", errors="replace").read()
        for hit in bypass.finditer(src):
            # Allowed ONLY as the else-branch of a whFmtPeso availability check in the SAME
            # STATEMENT. Two cheaper delimiters failed first, and both failures are instructive:
            # a fixed 260-character lookback found the `typeof whFmtPeso` of an UNRELATED helper
            # two lines above and exempted a genuine bypass - the teeth test for this very clause
            # passed GREEN; switching to the nearest brace then cut the expression at the `{`
            # inside `{ decimals: 2 }`, which sits AFTER the check, and reported three legitimate
            # fallbacks as live bypasses. A statement boundary is the only delimiter here that
            # survives someone reformatting the file.
            line_start = src.rfind(chr(10), 0, hit.start()) + 1
            # Start with the hit's OWN line: a bypass that opens its own statement must be
            # judged on that statement, not on whatever preceded it. An earlier version began
            # one line up, walked past `const _bad = ...` into the helper above, inherited its
            # `typeof whFmtPeso` check and exempted the bypass - this clause's teeth test
            # passed GREEN twice before that was found.
            stmt_start = line_start
            while stmt_start > 0:
                line_end = src.find(chr(10), stmt_start)
                line = src[stmt_start:line_end if line_end != -1 else len(src)]
                if re.match(r"\s*(const|let|var|return|function|if|\})", line):
                    break
                prev = src.rfind(chr(10), 0, stmt_start - 1)
                if prev == -1:
                    stmt_start = 0
                    break
                stmt_start = prev + 1
            stmt = src[stmt_start:hit.start()]
            if re.search(r"typeof\s+whFmtPeso\s*===\s*['\"]function['\"]", stmt):
                continue
            line = src[:hit.start()].count("\n") + 1
            live.append(f"{p.name}:{line}")
    for site in live:
        failures.append(f"{site}: renders '₱' + Number(x || 0) on a LIVE path - Number(null) is 0 and "
                        f"finite, so an absent amount becomes a confident zero. Use whFmtPeso, which "
                        f"prints a gap for absent and still prints ₱0 for a real zero")

    if failures:
        print("FAIL absent-money-is-not-zero:")
        for f in failures:
            print("    - " + f)
        return 1

    print("  whFmtPeso: absent -> gap, non-finite -> gap, real zero -> ₱0 · no live bypass found")
    print("PASS absent-money-is-not-zero - an amount that did not arrive shows a gap, not a number "
          "the reader would act on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
