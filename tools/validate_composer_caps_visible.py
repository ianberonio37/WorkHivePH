#!/usr/bin/env python3
"""composer-caps-visible - T168: a cap must announce itself (2026-08-26).

A maxlength with no counter is a SILENT WALL. The textarea stops accepting keystrokes
and the person typing does not read that as "you reached 1000 characters" - they read
it as a broken keyboard, and they lose the thought they were part-way through. The
guard is right; the silence is the defect. That is the whole of T168: guards that
protect without insulting the person they stop.

FOUND ON community.html, which had built the right pattern and applied it unevenly -
the post composer (2000) and the report box (500) each carried a live "n / max"
counter, and the reply box (1000) carried none. One page, three composers, two honest.
Added the counter in the page's own idiom, wired its input listener, and reset it at
BOTH clear sites (opening a thread, and after a reply posts) - a counter still showing
the last message's length is a stale reading, which is worse than no counter at all.

★THE STATIC SCAN THAT FOUND IT WAS WRONG TWICE FIRST, AND THAT IS WHY THE PROVER IS
LIVE. Inferring the counter's id from the field's id ("<id>-char-count") reported
#post-content as uncounted - its counter is #post-char-count, and the convention is
not a convention. A counter is whatever visible element MOVES WHEN YOU TYPE, so the
only honest oracle types into the field and watches.

Asserts per composer: typing raises a visible element showing length and cap, and
clearing returns it to zero. Signed-in live probe.

Re-drive: node tools/prove_composer_caps_visible.mjs
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
        print("SKIP composer-caps-visible - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP composer-caps-visible - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_composer_caps_visible.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if not ok:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL composer-caps-visible - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-5:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL composer-caps-visible - a capped composer does not show its limit, or its counter "
              "keeps a stale count. A maxlength with no counter reads as a broken keyboard, not a rule.")
        return 1
    print("PASS composer-caps-visible - every capped composer on the page shows its limit while you type "
          "and returns to zero when cleared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
