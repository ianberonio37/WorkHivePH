#!/usr/bin/env python3
"""install-affordance - §BRH.11 AM: an install icon a person can find, and an icon worth landing (2026-10-26).

Ian, in his own hands: "users should have something icon where they can just click or tap to easily install it and
visible right away on their homescreen for desktop and phone." Measured on 2026-10-26: the only install control lived
on the landing page inside the desktop header and showed only after beforeinstallprompt (which iOS never fires); the
manifest declared one 640x640 transparent PNG as 192, 512 and maskable; the hub injected an apple-touch-icon with a
RELATIVE href to a file that was not at the root (a 404 on every page) and was 768x543.

THE GATE IS THE MEASURE ITSELF: tools/bug_hunt_inventory.install_affordance_sites() is what seeded the AM rows, and it
returns a site for every fact above that still holds. After the fix it must return NOTHING but the `start_url` lens
(a row that asks, it does not accuse), and the shared chrome must carry an install control visible at rest
(nav-hub.js #wh-hub-install) - so a revert of the control, the manifest or the icon href reddens this without a
browser. The browser half is tools/prove_hub_panel_on_screen.mjs's `install` case (the control visible with the hub
open, the guide shown on tap, in Chromium and WebKit).

    python tools/validate_install_affordance.py
    python tools/validate_install_affordance.py --self-test
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
HUB = ROOT / "nav-hub.js"
MANIFEST = ROOT / "manifest.json"
ALLOWED_KEYS = re.compile(r"^start_url ")


def findings() -> list[str]:
    from bug_hunt_inventory import HIDDEN_AT_REST, INSTALL_CONTROL, install_affordance_sites
    out = []
    hub = HUB.read_text(encoding="utf-8", errors="replace") if HUB.exists() else ""
    if not any(not HIDDEN_AT_REST.search(m.group(0)) for m in INSTALL_CONTROL.finditer(hub)):
        out.append("nav-hub.js carries no install control visible at rest (an element whose id/class says install, not hidden)")
    for s in install_affordance_sites():
        if not ALLOWED_KEYS.match(s["key"]):
            out.append(f"{s['page']} · {s['key']}: {s['detail'][:160]}")
    try:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        purposes = {str(i.get("purpose", "")) for i in man.get("icons") or []}
        if not any("maskable" in p for p in purposes):
            out.append("manifest.json declares no maskable icon (Android's adaptive shape gets a cropped default)")
        if not any(p.strip() in ("any", "") for p in purposes):
            out.append("manifest.json declares no plain (purpose any) icon")
    except Exception as e:
        out.append(f"manifest.json unreadable: {e}")
    return out


def self_test() -> int:
    from bug_hunt_inventory import HIDDEN_AT_REST, INSTALL_CONTROL
    ok = bool(INSTALL_CONTROL.search('<button type="button" id="wh-hub-install" class="x">')) \
        and bool(HIDDEN_AT_REST.search('<button id="pwa-install-btn" class="hidden md:flex">')) \
        and not HIDDEN_AT_REST.search('<button id="wh-hub-install" class="wh-hub-assist-btn" aria-expanded="false">') \
        and bool(ALLOWED_KEYS.match("start_url /")) and not ALLOWED_KEYS.match("manifest icon 192x192")
    print(("PASS" if ok else "FAIL") + " install-affordance self-test")
    return 0 if ok else 1


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        return self_test()
    f = findings()
    print("install-affordance (§BRH.11 AM): an install control at rest in the shared chrome; manifest sizes true; maskable "
          "on a solid ground; apple-touch-icon root-absolute and square")
    for x in f:
        print(f"  - {x}")
    print("PASS" if not f else "FAIL")
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
