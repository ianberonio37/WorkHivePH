#!/usr/bin/env python3
"""validate_listing_hold_disclosed.py - the marketplace's money copy says what the system charges (2026-11-09).

★WHAT WAS FALSE. A seller's listing holds 10% of its price in credits. `sweep_listing_holding_fee`, scheduled as
`listing-holding-fee-monthly` (03:00 on the 1st), retires `holding_fee_pct` of every LIVE listing's hold each month -
platform default 2%, an anti-nuisance charge. Meanwhile the seller wallet said the hold "is not a fee" and "comes back
in full if the listing does not sell", the marketplace hero and meta said "Free, No Platform Fees", the landing page,
learn hub and the AI assistant's own knowledge said "no platform fees", and the provider refusal said the minimum
balance "is spent on your own commission" - while commission defaults to 0. Twenty sentences across nine shipped files,
each found while rewriting a learn guide for plain language, none caught by any gate.

What this holds, over every shipped .html/.js (tools, tests and fixtures excluded; comments skipped):
  1. no copy says "no platform fee(s)", "comes back in full", or that the hold "is not a fee";
  2. any copy that promises the hold comes back ("comes back", "get the rest back") also states the monthly shrink,
     at the knob's real rate ("2% a month" / "shrinks by 2%");
  3. that rate is the platform default read from the database's own service_knob_pct when the stack is up (else from the
     latest migration that defines it) - so a change to the knob turns this red until the copy follows.

    python tools/validate_listing_hold_disclosed.py
    python tools/validate_listing_hold_disclosed.py --self-test
"""
from __future__ import annotations

import glob
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FALSE = re.compile(r"no platform fees?\b|comes? back in full|(?:hold|credits?)[^.<]{0,40}\bis not a fee|\bit is not a fee\b", re.I)
PROMISE = re.compile(r"comes back (?:to you|if)|get the rest back|rest comes back", re.I)
SKIP_DIRS = ("tools/", "tests/", "test-data-seeder/", "_fixtures/", "node_modules/", ".claude/", "supabase/")


def knob_default() -> float | None:
    """holding_fee_pct's platform default, from the live function first, then the newest migration."""
    if shutil.which("docker"):
        try:
            r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
                                "-tAq", "-c", "select prosrc from pg_proc where proname='service_knob_pct'"],
                               capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
            m = re.search(r"WHEN 'holding_fee_pct'\s+THEN\s+([\d.]+)\s*(?:--|\n|$)", r.stdout or "")
            if m:
                return float(m.group(1))
        except Exception:
            pass
    for f in sorted(glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql")), reverse=True):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if "service_knob_pct" in src and "holding_fee_pct" in src:
            m = re.search(r"WHEN 'holding_fee_pct'\s+THEN\s+([\d.]+)\s*(?:--|\n|$)", src)
            if m:
                return float(m.group(1))
    return None


def shipped() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "*.js"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return [ROOT / p for p in out if not p.startswith(SKIP_DIRS) and "survey_ufai_rubric" not in p]


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", " ", src)
    return "\n".join("" if re.match(r"\s*(//|\*|/\*)", ln) else ln for ln in src.splitlines())


def check_text(src: str, rate: float) -> list[str]:
    bad = []
    body = _strip_comments(src)
    for m in FALSE.finditer(body):
        bad.append("says " + repr(body[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")))
    pct = f"{rate:g}%"
    shrink = re.compile(rf"{re.escape(pct)} (?:a|on the 1st of each|each|per) month|shrinks by {re.escape(pct)}", re.I)
    for m in PROMISE.finditer(body):
        window = body[max(0, m.start() - 260):m.end() + 160]
        if not re.search(r"\bhold\b|\bcredits?\b|10%", body[max(0, m.start() - 260):m.end()], re.I):
            continue                     # "the answer comes back to you" - not about the listing hold
        if not shrink.search(window):
            bad.append("promises the hold back without the monthly shrink: " + repr(body[max(0, m.start() - 60):m.end() + 20].replace("\n", " ")))
    return bad


def _self_test() -> int:
    fails = []
    good = "Publishing holds 10% of the price in credits. While the listing is live, the hold shrinks by 2% on the 1st of each month. The rest comes back if you take it down."
    if check_text(good, 2.0):
        fails.append("the corrected wording must pass")
    for bad, why in [("Free, No Platform Fees", "the old hero"),
                     ("It is not a fee. It comes back in full if the listing does not sell.", "the old wallet note"),
                     ("Publishing holds 10% of the price in credits. The rest comes back if you take it down.", "a promise with no shrink"),
                     ("While live, the hold shrinks by 3% a month. The rest comes back if you take it down.", "the wrong rate")]:
        if not check_text(bad, 2.0):
            fails.append(f"{why} must fail")
    if check_text("Sent. The answer from WorkHive comes back to you as a notification.", 2.0):
        fails.append("a sentence about something else coming back is not about the hold")
    if check_text("// It is not a fee - an old comment\n<!-- no platform fees -->", 2.0):
        fails.append("comments are not copy")
    print("FAIL listing-hold-disclosed self-test - " + "; ".join(fails) if fails
          else "self-test OK: the corrected copy passes; the old hero, the old wallet note, a bare promise and a wrong rate all fail")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    rate = knob_default()
    if rate is None:
        print("FAIL listing-hold-disclosed - cannot read holding_fee_pct's platform default (database or migrations)")
        return 1
    hits = {}
    for p in shipped():
        try:
            errs = check_text(p.read_text(encoding="utf-8", errors="replace"), rate)
        except Exception:
            continue
        if errs:
            hits[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(hits.items()):
        for e in errs[:3]:
            print(f"  BAD {f}: {e[:200]}")
    if hits:
        print(f"FAIL listing-hold-disclosed - {sum(len(v) for v in hits.values())} sentence(s) in {len(hits)} file(s) "
              f"tell a seller less than the system charges (holding fee {rate:g}% a month on a live listing's hold)")
        return 1
    print(f"PASS listing-hold-disclosed - every shipped page that promises the hold back names the {rate:g}%-a-month "
          f"holding charge, and none says 'no platform fees' or 'comes back in full'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
