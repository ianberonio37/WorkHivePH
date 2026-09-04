#!/usr/bin/env python3
"""media-fails-alone - T197: storage down must not take the write with it (2026-08-26).

Supabase Storage is a separate service from the database and it fails independently. The
question that matters is whether the feature that ATTACHES a photo takes the whole
submission down with it. A seller who has written a listing, priced it and typed a
description should not lose that work because a bucket is refusing writes.

Same decoupling ethic T12 established for the voice journal, where an AI 429 was losing
the worker's typed note: the SECONDARY enrichment must never destroy the PRIMARY work.

MEASURED with every bucket write forced to 500 while the database stays up:
  * the picker announces the real reason ("storage unavailable") instead of swallowing it
  * #post-image-url is CLEARED, so the listing submits with no photo rather than a
    broken link
  * the rest of the form is untouched and still submittable

★IT INJECTS A STORAGE-ONLY OUTAGE, not a general one. Failing everything proves nothing
about isolation; the point is that ONE service is down and the others carry on, which is
the only shape that distinguishes a decoupled feature from a lucky one.

★AND THE PROVER FAILED ITS OWN FIRST TEETH TEST, which is the reusable part: it checked
`toast.offsetHeight > 0`, and the toast CONTAINER is always in the DOM, so an EMPTY toast
counted as "the user was told". Silencing the error still passed. It now requires the
toast to contain actual words - a string is not an announcement until it has some.

Re-drive: node tools/prove_media_fails_alone.mjs
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
        print("SKIP media-fails-alone - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP media-fails-alone - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_media_fails_alone.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL media-fails-alone - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if not ok:
        print("FAIL media-fails-alone - a storage outage no longer degrades the photo alone. If the url")
        print("    is left set the listing saves a broken link; if the failure is silent the seller")
        print("    submits believing a photo is attached; if the form is disabled, one service took")
        print("    the whole piece of work hostage.")
        return 1
    print("PASS media-fails-alone - with storage refusing every write, the photo feature degrades on "
          "its own: the reason is said out loud and the listing still saves without it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
