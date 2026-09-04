#!/usr/bin/env python3
"""g5d-reauth-restore gate — T8's return-trip context contract (2026-08-26).

Runs tools/prove_g5d_reauth_restore.mjs: on each covered page, set a filter,
kill the session, re-auth through index.html?signin=1&return=<page>, and
assert the page comes back WITH the filter still applied. Session expiry must
cost one sign-in and zero context.

Covered this slice: logbook (filter-category) + pm-scheduler (cat-filter) —
the two pages wired through the central whAutoRememberFilters helper. Pages
with bespoke persistence are later slices; the prover states its scope.

Instrument lesson baked into the prover: the G5a wiring lands DEEP inside each
page's async init(), seconds after the filter element parses — the setter is
therefore SELF-VERIFYING (retries until the wh_view_* store actually holds the
save) so a probe race can never again read as a page defect.

Discipline: retry-once, node direct (ampersand path), utf-8 pinned,
line-anchored PASS, SKIP when node/stack absent.

Re-drive: node tools/prove_g5d_reauth_restore.mjs
"""
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A BROKEN MACHINE IS NOT A BROKEN PRODUCT (2026-08-28). This gate drives a real browser and had no
# health check, so an infra death read as a product failure. Measured the same day on dialog-floor: the
# prover died on `SIGN-IN FAILED: Failed to fetch` after Docker Desktop stopped, and the gate reported a
# layout defect that no run had measured. A false RED is worse than a SKIP - a skip says "not measured",
# a red sends someone to read page code that was never wrong, and gates that cry wolf get excluded.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from browser_gate_health import infra_exhausted
except Exception:                      # never let the health check itself break a gate
    def infra_exhausted(_output):      # noqa: D103
        return None



def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str) -> tuple[bool, str, str]:
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_g5d_reauth_restore.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed = bool(re.search(r"^\s*PASS", out, re.M))
    tail = out.strip().splitlines()[-3:] if out.strip() else ["<no output>"]
    return passed, " | ".join(line.strip() for line in tail), out


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP g5d-reauth-restore — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP g5d-reauth-restore — local stack down (Flask :5000 / Supabase :54321)")
        return 0

    try:
        ok, tail, out = _run(node)
        if not ok:
            ok, tail, out = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL g5d-reauth-restore — timed out at 300s")
        return 1

    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        verdict = infra_exhausted(out)
        if verdict:
            print(f"  SKIP (infrastructure): {verdict}")
            return 0
        # NAME WHAT FAILED. The verdict line above is a 3-line tail, which on 2026-08-28 read
        # "waiting for locator('#f-problem') | | FAIL 0/5 pages" - enough to know something broke and
        # not enough to know WHICH page or WHY, so diagnosing meant re-running the prover by hand.
        # A gate that reports a failure owes the reader the evidence it already has in memory.
        for _l in [l.rstrip() for l in out.splitlines() if l.strip()][-14:]:
            print("    | " + _l[:160])
        print("FAIL g5d-reauth-restore — a page lost its filter across the auth round trip.")
        return 1
    print("PASS g5d-reauth-restore — covered pages keep their context across session expiry + re-auth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
