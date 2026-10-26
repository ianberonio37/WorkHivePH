#!/usr/bin/env python3
"""validate_prod_signed_in_pages.py - every app page is seen signed in on production after a deploy (BRH-AG, 2026-10-26).

The 2026-10-24 deploy's smoke walked 120 public pages and 0 of the 26 app pages signed in: production had no account it
could use. With the bench identity (BRH-AF), tools/post_deploy_smoke.mjs --tier=app walks every app page on
workhiveph.com as the bench supervisor and writes post_deploy_smoke_report.json. This holds that report:

  - it was taken against production (https://workhiveph.com), never a local rehearsal
  - its signed-in tier covers every page of the smoke's own APP_PAGES roster
  - each page loaded its own UI with no page error and no failed resource

The first run (2026-10-26) read 23/26: skillmatrix, resume and engineering-design lost Chart.js / html2pdf / Mermaid to
the service worker (sw.js v576 fixes it; it ships with the next frontend push). This stays red until the post-deploy
smoke after that push reads 26/26 - the gate says what production does, not what the tree would do.

    python tools/validate_prod_signed_in_pages.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "post_deploy_smoke_report.json"
SMOKE = ROOT / "tools" / "post_deploy_smoke.mjs"
PROD = "https://workhiveph.com"


def roster() -> list[str]:
    s = SMOKE.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const APP_PAGES = \[([\s\S]*?)\];", s)
    return [f"{p}.html" for p in re.findall(r"'([a-z0-9-]+)'", m.group(1))] if m else []


def main() -> int:
    print("prod-signed-in-pages (BRH-AG): every app page seen signed in on production after a deploy")
    if not REPORT.exists():
        print("  - no post_deploy_smoke_report.json: run the smoke against production with the bench (--tier=app)")
        print("FAIL")
        return 1
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    base = (rep.get("base") or "").rstrip("/")
    if base != PROD:
        print(f"  - the report was taken against {base or '?'}, not {PROD}: run the smoke against production")
        print("FAIL")
        return 1
    seen = {}
    for r in rep.get("tier2") or []:
        name = (r.get("url") or r.get("page") or "").split("/")[-1]
        seen[name] = r
    want = roster()
    missing = [p for p in want if p not in seen]
    failing = [f"{p}: {(seen[p].get('errors') or ['not ok'])[0][:90]}" for p in want if p in seen and not seen[p].get("ok")]
    print(f"  report {rep.get('at', '?')} · {len(want) - len(missing) - len(failing)}/{len(want)} app pages clean signed in")
    for p in missing:
        print(f"  - {p}: not walked signed in")
    for f in failing:
        print(f"  - {f}")
    bad = missing + failing
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
