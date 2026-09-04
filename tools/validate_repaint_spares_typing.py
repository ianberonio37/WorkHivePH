#!/usr/bin/env python3
"""repaint-spares-typing - T142: a live update must not evict a typist (2026-08-26).

The recorded incident is precise: a 15-second poll rebuilt a region while somebody was
typing in it and the repaint threw focus to <body>. The DRAFT survived - the text was
still there - which is exactly what made it hard to notice, because the person kept
typing into nothing. Realtime is the same hazard with worse timing: the update arrives
when a colleague acts, not on a schedule anyone could learn.

THE INVARIANT, and it is structural rather than behavioural: a container a realtime
handler REPLACES must not contain a typing surface. If the composer is not in the
subtree being rebuilt, no repaint can evict it and no focus-restoration code is needed -
which is better than restoring focus correctly, because restoration has to be right
every single time.

MEASURED, and both of T142's named subjects hold:
  community  updates one card via _updateRenderedCard() for the ordinary case and
             rebuilds #feed-list ONLY when a pin moves (a genuine reorder). Both
             composers sit outside it - the post box on the page, the reply box inside
             #thread-overlay - confirmed in the live DOM, not from source offsets.
  hive       realtime reloads targeted display cards (loadAdoptionCard,
             loadMaturityStairway), which hold no inputs at all.

★IT ASSERTS CONTAINMENT, NOT FOCUS SURVIVAL. Driving a real focus test needs the
composer open and an update to land, and would prove one path on one run. Containment is
what makes every path safe, and it is checkable every run.

★IT READS THE POST-RENDER DOM, WHICH IS WHY THE FIRST TEETH TEST FAILED TO FIRE: a
textarea pasted into the empty #feed-list markup is wiped by the page's own render
before the probe looks. The faithful test puts one in the CARD TEMPLATE, so the render
itself places it inside the rebuilt container - and then the gate reports 16 typing
surfaces and fails, which is the behaviour that matters.

Re-drive: node tools/prove_repaint_spares_typing.mjs
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
        print("SKIP repaint-spares-typing - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP repaint-spares-typing - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_repaint_spares_typing.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL repaint-spares-typing - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL repaint-spares-typing - a container a realtime handler rebuilds now holds a typing")
        print("    surface. When the update lands it evicts whoever is mid-sentence, and because the")
        print("    draft survives while the focus does not, they keep typing into nothing. Move the")
        print("    composer out of the rebuilt subtree, or update the card in place.")
        return 1
    print("PASS repaint-spares-typing - no container that a realtime update rebuilds contains a place "
          "someone could be typing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
