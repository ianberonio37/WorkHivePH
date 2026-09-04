#!/usr/bin/env python3
"""search-button-is-not-dead - T78: the spine's search button must not swallow a press (2026-08-26).

nav-hub.js is on every page and lazy-loads search-overlay.js asynchronously, so window.WHSearch is
briefly absent on EVERY page load and permanently absent if that request fails - a cache miss, a
bad deploy, a flaky plant connection.

★THE HANDLER HAD ONLY THE HAPPY BRANCH: `if (window.WHSearch) { open() }` and nothing else, so a
press with the script missing did nothing whatsoever. Measured with search-overlay.js answered 404:
the overlay never opened, NOTHING was said, and there were zero page errors - the exact shape of a
control that looks alive and is not, on the one element every page carries.

It now retries the load once (the usual cause is a request that had not landed yet) and then says
why it cannot open. A search that will not start is a small failure; a button that swallows the
press teaches the worker the platform is broken and gives them nothing to do about it.

BOTH DIRECTIONS: healthy opens the overlay and does not cry unavailable; script-dead does not open
and says so. The first half is what stops the fix from being "always claim it is broken".

Driven at 390, because the hub is the phone's only navigation.

Re-drive: node tools/prove_search_button_is_not_dead.mjs
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
        print("SKIP search-button-is-not-dead - node not on PATH (live gate)")
        return 0
    if not _port_open(5000):
        print("SKIP search-button-is-not-dead - local page server down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_search_button_is_not_dead.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if re.search(r"^\s*SKIP", out, re.M):
            return None, out
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if ok is False:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL search-button-is-not-dead - timed out at 300s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP search-button-is-not-dead - the hub or its search button was not reachable")
        return 0
    if not ok:
        print("FAIL search-button-is-not-dead - the global search button either failed to open when it")
        print("    could, or swallowed the press when it could not. A press that changes nothing, on the")
        print("    one control every page carries, teaches the worker the platform is broken and gives")
        print("    them nothing to do about it.")
        return 1
    print("PASS search-button-is-not-dead - search opens when it can and says why when it cannot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
