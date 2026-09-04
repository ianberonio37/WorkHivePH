#!/usr/bin/env python3
"""listing-preview - T100: see it as a buyer before it is a commitment (2026-08-26).

T100's walk found the AI listing assist SOUND - it names its own inputs and
invented no specs from a bare title - and recorded exactly one gap: a seller
could not see their listing AS A BUYER WILL before publishing. Posting is a
commitment: it spends a credit hold, it goes to moderation, and it is the first
thing a stranger judges the seller by. J3's bar is preview-before-irreversible.

*** THIS GATE EXISTS BECAUSE THE FIX FAILED TWICE, SILENTLY. ***
  1. The handler called getElementById at script-parse time and returned early
     when the composer was not yet in the DOM - the button rendered perfectly and
     did NOTHING. Declared, never wired.
  2. Rewritten as a delegated listener, it was inserted INSIDE the submit
     handler's function body, so it only registered once a seller pressed Post -
     the one moment a preview is useless.
Both loaded with ZERO console errors, and a gate that merely checked the button
EXISTS would have been green through both. So this one CLICKS it and reads what
appears - the only check that could tell the difference.

Four assertions: it opens; it shows the draft the seller typed; a blank price
reads "Negotiable" while a filled one renders through whFmtPeso (a preview that
formats money its own way is showing the seller something the buyer will not
see); and it closes again, because a preview that traps you is a modal.

Resurrection both ways: RED with no preview control at all, and RED again with
the listener deliberately un-wired.

Re-drive: node tools/prove_listing_preview.mjs
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


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP listing-preview - node not on PATH (live gate)")
        return 0
    if not _port_open(5000):
        print("SKIP listing-preview - local Flask (:5000) down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_listing_preview.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL listing-preview - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-8:]:
        print("  " + line.strip()[:150])
    if not ok:
        print("FAIL listing-preview - the preview is missing, un-wired, or shows the seller something "
              "different from what a buyer will see. Check that the handler is registered at TOP LEVEL, "
              "not inside the submit handler.")
        return 1
    print("PASS listing-preview - a seller can see the listing as a buyer will, before it becomes a "
          "commitment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
