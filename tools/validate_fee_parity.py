#!/usr/bin/env python3
"""fee-parity gate — T103's stated-vs-charged oracle (2026-08-26).

Every fee percentage a page STATES to a user is a promise; the DB is what
actually charges. They are wired independently — the glass hardcodes "10%"
while `listing_reservation_amount` resolves a per-hive `reward_pct` knob
through `service_knob_pct` (defaulting from the platform table) — so a knob
change silently makes the copy a lie. That gap is exactly the surprise-charge
class this gate exists to prevent.

What it checks, per claim in CLAIMS below:
  1. the stated percentage still appears on its page (the copy has not moved
     without this gate noticing);
  2. the DB's own effective rate for that knob equals the stated number.

The DB side is read LIVE via psql (the platform default plus every hive
override, so a single divergent hive fails the gate rather than hiding behind
an average). SKIPs when the stack is down — a gate that cannot read the DB
must say SKIP, never PASS.

Usage: python tools/validate_fee_parity.py
"""
import io
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# page, the literal the page shows a user, the knob the DB charges from, what the claim is about
CLAIMS = [
    ("marketplace.html", "10%", "reward_pct", "publishing holds N% of the asking price in credits"),
]


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def psql(sql: str) -> str:
    return subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    ).stdout.strip()


def main() -> int:
    if not shutil.which("docker") or not _port_open(54321):
        print("SKIP fee-parity — local stack down (docker / Supabase :54321)")
        return 0

    failures = []
    for page, stated, knob, what in CLAIMS:
        src = (ROOT / page).read_text(encoding="utf-8", errors="replace")
        if stated not in src:
            failures.append(f"{page}: the stated '{stated}' ({what}) is no longer on the page — "
                            f"copy moved without updating this gate's CLAIMS")
            continue
        # every rate the DB could actually charge for this knob: the platform default and
        # every per-hive override. A single divergent row is a real surprise-charge.
        rates = psql(
            "SELECT DISTINCT public.service_knob_pct(h.id, '%s')::text FROM public.hives h "
            "UNION SELECT public.service_knob_pct(NULL::uuid, '%s')::text;" % (knob, knob)
        )
        vals = sorted({r.strip() for r in rates.splitlines() if r.strip()})
        if not vals:
            failures.append(f"{page}: could not read the '{knob}' rate from the DB")
            continue
        want = stated.rstrip("%")
        bad = [v for v in vals if abs(float(v) - float(want)) > 0.001]
        print(f"  {page}: states {stated} · DB charges {', '.join(v + '%' for v in vals)} ({knob})")
        if bad:
            failures.append(f"{page}: states {stated} but the DB would charge "
                            f"{', '.join(b + '%' for b in bad)} for '{knob}' — {what}")

    if failures:
        for f in failures:
            print("  FAIL " + f)
        print(f"FAIL fee-parity — {len(failures)} stated fee(s) do not match what the DB charges.")
        return 1
    print(f"PASS fee-parity — all {len(CLAIMS)} stated fee(s) match the rate the DB would charge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
