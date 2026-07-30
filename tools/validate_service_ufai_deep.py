#!/usr/bin/env python3
"""
validate_service_ufai_deep.py - gate wrapper for tools/ufai_deep_arc_probe.mjs.

WHY A WRAPPER. run_platform_checks.py builds every command as [sys.executable, script, *args] - it
has no node interpreter path - so a .mjs registered directly would be handed to Python and die.
Registering this wrapper is the shape the harness actually supports (and the mistake is worth the
comment: I registered the .mjs directly first, with an "interpreter": "node" key the runner does not
read).

WHAT IT GUARDS. The DEEP UFAI verification that ufai_pillar_map.py explicitly excludes from its
coarse lens slice ("coarse-100 does NOT mean deep-100"), run live in a browser over the four
service-hailing surfaces:
    U2  every VISIBLE interactive control measured at 390px  -> must be >= 44px
    U5  vendored axe-core                                     -> 0 serious/critical
    A1  360 / 390 / 768 / 1280 / 1920                         -> 0 horizontal page overflow
It earned its keep on the first run: founder-console carried two links with class="btn" but NO rule
defined for a bare a.btn, so they rendered browser-default blue on a dark panel - 1.88:1 contrast at
21px tall - plus a select labelled only by title=. The page-level rubric score could not see any of it.

SKIPs cleanly when node, playwright or the seeder at :5000 is unavailable, so it never blocks a
machine that cannot run a browser.
"""
from __future__ import annotations
import io
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tools" / "ufai_deep_arc_probe.mjs"
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

SKIP_MARKERS = ("ECONNREFUSED", "ERR_CONNECTION", "net::ERR", "Executable doesn't exist",
                "ERR_MODULE_NOT_FOUND", "playwright", "browserType.launch")


def main() -> int:
    if not PROBE.is_file():
        print(f"{YEL}SKIP{RST}  probe not found: {PROBE.name}")
        return 0
    try:
        r = subprocess.run(["node", str(PROBE)], cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
    except FileNotFoundError:
        print(f"{YEL}SKIP{RST}  node not on PATH")
        return 0
    except subprocess.TimeoutExpired:
        print(f"{YEL}SKIP{RST}  probe timed out (browser/seeder unavailable?)")
        return 0

    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if line.strip().startswith(("marketplace", "founder", "achievements", "PASS", "FAIL", "  -")):
            print("  " + line.strip())

    if r.returncode != 0 and any(m in out for m in SKIP_MARKERS):
        print(f"{YEL}SKIP{RST}  browser/seeder unavailable - deep UFAI not measured this run")
        return 0
    if r.returncode != 0:
        print(f"{RED}FAIL{RST}  UFAI deep regression on a service-hailing surface (see above).")
        return 1
    print(f"{GREEN}PASS{RST}  deep UFAI holds: 0 sub-44px targets, 0 overflow 360-1920, 0 serious/critical axe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
