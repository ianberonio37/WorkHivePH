"""prove_no_stale_typed_dates.py - a date that is TYPED goes stale silently (2026-09-16).

`advance_trajectory.py` carried

    TODAY = "2026-09-05"

as a plain module constant for ELEVEN DAYS. It is the date stamped on the `[date]` prefix of every
basis entry the tool appends, and on `reg["updated"]`, which the GENERATED roadmap header prints. So
the registry announced it was last updated on 2026-09-05 while it was being rewritten several
thousand times after that, and every row banked in those eleven days carries a prefix naming a day
it did not happen on.

IT HID BEHIND A TRUE SENTENCE. The entries read

    [2026-09-05] pct -> 60. WALKED LIVE 2026-09-16 via playwright-mcp ...

- wrong prefix, right claim, one string. The inner date comes from the receipt and is correct; only
the prefix came from the constant. Anyone reading an entry sees a correct date and moves on, which
is why nobody noticed for eleven days.

THE CHECK. Scan the tools for a module-level constant whose NAME says it means now (TODAY, NOW,
DATE, TIMESTAMP, AS_OF, CURRENT_DATE...) and whose VALUE is a typed ISO date, then fail when that
date is more than --max-age-days old. The name is what makes it a claim about the present: a
constant called `BASELINE_DATE` or `CUTOFF` is a deliberate historical anchor and is left alone.

This is the same class as the two other records this project found lying on the same day - a
`validates_at` column no edge function implements, and a `schema_migrations` table holding 209 rows
while 613 migrations exist and post-cutoff ones are demonstrably live. A record of intent is not the
thing. Where the thing is derivable, derive it.

Usage:  python tools/prove_no_stale_typed_dates.py [--check] [--max-age-days N] [--self-test]
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

# A constant whose NAME claims to be the present moment. `BASELINE_DATE`, `CUTOFF`, `SINCE`,
# `RELEASE_DATE` are deliberate anchors and are NOT matched - a historical date is supposed to be
# typed, and flagging it would teach people to silence this gate.
_NOW_NAME = re.compile(r"^(TODAY|NOW|CURRENT_DATE|TODAY_ISO|DATE_TODAY|AS_OF|ASOF|RUN_DATE|STAMP|TIMESTAMP)$")
_ASSIGN = re.compile(r"""^\s{0,3}([A-Z][A-Z0-9_]*)\s*=\s*["'](\d{4}-\d{2}-\d{2})["']\s*(?:#.*)?$""")


def scan_text(text: str):
    """-> [(name, iso)] for module-level typed 'now' constants. Indented lines are skipped: a
    constant inside a function or class is not the module's declaration of the present."""
    out = []
    for line in text.splitlines():
        m = _ASSIGN.match(line)
        if m and _NOW_NAME.match(m.group(1)):
            out.append((m.group(1), m.group(2)))
    return out


def scan_repo(root: Path = TOOLS):
    found = []
    for p in sorted(root.glob("*.py")):
        if p.name == Path(__file__).name:
            continue          # this file quotes the pattern in its own docstring
        try:
            text = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for name, iso in scan_text(text):
            found.append((p.name, name, iso))
    return found


def age_days(iso: str, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    return (today - dt.date.fromisoformat(iso)).days


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--max-age-days", type=int, default=7)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    found = scan_repo()
    stale = [(f, n, v, age_days(v)) for f, n, v in found if age_days(v) > a.max_age_days]

    print("typed 'now' constants: %d found across tools/" % len(found))
    for f, n, v in found:
        print("   %-42s %s = %s  (%d day(s) old)" % (f, n, v, age_days(v)))

    if not stale:
        print("PASS no-stale-typed-dates: no constant that claims to be today is more than %d day(s) old."
              % a.max_age_days)
        return 0

    print("")
    print("FAIL no-stale-typed-dates: %d constant(s) name the present and hold the past." % len(stale))
    for f, n, v, age in stale:
        print("       %s: %s = %s is %d days old" % (f, n, v, age))
    print("     A constant called TODAY is read as the day the tool RUNS, so everything it stamps -")
    print("     an audit prefix, an `updated` field, a generated header - says the wrong day while")
    print("     looking authoritative. Derive it: `dt.date.today().isoformat()`. If the date really")
    print("     is a fixed historical anchor, give it a name that says so (BASELINE_DATE, CUTOFF),")
    print("     which this gate deliberately does not match.")
    return 1


def self_test() -> int:
    ok = True

    got = scan_text('TODAY = "2026-09-05"\n')
    if got != [("TODAY", "2026-09-05")]:
        print("FAIL: a typed TODAY must be found -> %s" % got)
        ok = False

    # A historical anchor is NOT a claim about the present and must not be flagged, or the gate
    # teaches people to silence it.
    for benign in ('BASELINE_DATE = "2021-01-01"\n', 'CUTOFF = "2020-05-05"\n', 'RELEASE_DATE = "2019-01-01"\n'):
        if scan_text(benign):
            print("FAIL: a deliberately historical constant must be left alone -> %r" % benign.strip())
            ok = False

    # Indented = inside a function or class; not the module's declaration of now.
    if scan_text('    TODAY = "2026-09-05"\n'):
        print("FAIL: an indented assignment is not a module-level constant")
        ok = False

    # A derived value must not match.
    if scan_text('TODAY = dt.date.today().isoformat()\n'):
        print("FAIL: a DERIVED today must not be reported - that is the fix, not the defect")
        ok = False

    if age_days("2026-09-05", dt.date(2026, 9, 16)) != 11:
        print("FAIL: age arithmetic -> %s" % age_days("2026-09-05", dt.date(2026, 9, 16)))
        ok = False

    # And the real repo must now be clean, because advance_trajectory.py was fixed today. This is
    # the assertion that fails if anyone types one back in.
    live = scan_repo()
    if live:
        print("FAIL: tools/ carries a typed 'now' constant again -> %s" % live)
        ok = False

    print("self-test: %s" % ("PASS - finds a typed TODAY, ignores a named historical anchor and an "
                             "indented or derived value, and the live tools/ carries none"
                             if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
