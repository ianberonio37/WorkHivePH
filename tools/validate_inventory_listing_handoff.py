#!/usr/bin/env python3
"""inventory-listing-handoff - T104 / T30: the sell hop keeps its intent (2026-08-26).

inventory offers "Sell surplus" only on rows holding 3x+ their minimum, with the
reason in the control's own title, and hands off to
marketplace.html?post=1&from_inventory=<id>. marketplace RE-FETCHES the row
server-side, so the prefill is authoritative and cannot be spoofed through the
URL: a person can only list from inventory their own session may read.

VERIFIED-GOOD, then locked. A handoff that drops what the system already knows
makes the seller retype it - the same intent-loss as a sign-in wall that forgets
where you were going, landing on the least-motivated user in the funnel: someone
listing a spare part for the first time. Measured: title, part number, quantity
(into the description), category classification and the source id all arrive.

*** THE MOST INTERESTING ASSERTION IS AN ABSENCE. *** The PRICE is deliberately
NOT prefilled, and the gate asserts it stays that way. What a plant paid is not
what it should ask, and a guessed price is the one field a seller must own - a
prefilled one would be the system making a commercial decision on their behalf.
The mutation test confirms this arm is independent: with the prefill disabled,
every other assertion flipped RED while priceLeftToTheSeller stayed green.

The prover picks a real surplus row by the same 3x rule the button uses rather
than hardcoding an id, so a reseed cannot turn this into a false red about
nothing, and it SKIPs cleanly if the fixture holds no surplus row.

Re-drive: node tools/prove_inventory_to_listing_handoff.mjs
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
        print("SKIP inventory-listing-handoff - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)) or not shutil.which("docker"):
        print("SKIP inventory-listing-handoff - local stack / docker down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_inventory_to_listing_handoff.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*(PASS|SKIP)", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL inventory-listing-handoff - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-10:]:
        print("  " + line.strip()[:150])
    if not ok:
        print("FAIL inventory-listing-handoff - the sell hop lost what the system already knew, or it "
              "started guessing the price on the seller's behalf.")
        return 1
    print("PASS inventory-listing-handoff - a surplus part reaches the composer complete, with the "
          "price still the seller's to decide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
