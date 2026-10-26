#!/usr/bin/env python3
"""in-app-search-honest - the OWN in-app search lens, held (2026-10-26).

Walked as the person on 13 pages at phone-390 and desktop-1280 (an empty query, a miss, special characters, many results).
What the walk found and fixed, held here as static facts:

  S1 pm-scheduler's Add Asset search said "No registered assets found" when a SEARCH matched nothing - to a supervisor
     with 22 assets. A miss names the query and how to see all.
  S2 the operator console can find a PUBLISHED listing and take it back to review (Unpublish, with the reason the seller
     sees) - the control lived only on retired marketplace-admin, so a buyer's "Report listing" had nowhere to go. The
     person's text sits quoted inside PostgREST's or=() and LIKE's % and _ are escaped; the write is guarded on the
     listing still being published and on the version searched (updated_at).
  S3 the console can REMOVE a seller's ID or certification badge (also stranded on marketplace-admin): confirmed by name,
     written by id only, guarded on the badge still being held; the database records the removal (20261026000016).
  S4 index.html's solo PM-overdue count read the newest 500 completions per 100 assets, so a busy month counted an asset
     serviced last week as overdue; a 501st row now asks the unseen assets one by one.

Teeth: the tree at 1045f447 fails S1-S4.
    python tools/validate_in_app_search_honest.py [--ref <git-ref>]   (--ref reads that commit's files instead)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: str, ref: str | None) -> str:
    if ref:
        try:
            return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                                           stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return ""
    p = ROOT / path
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def check(ref: str | None = None) -> list[str]:
    bad = []
    pm = _read("pm-scheduler.html", ref)
    if not re.search(r"No registered assets match \"\$\{q", pm):
        bad.append("S1 pm-scheduler: a search miss in the Add Asset wizard does not name the query (it says 'No registered assets found')")
    fc = _read("founder-console.html", ref)
    oa = _read("operator-actions.js", ref)
    src = _read("platform-actions.html", ref)
    for name, text in (("operator-actions.js", oa), ("platform-actions.html", src)):
        if "function fetchPublished" not in text or "unpublish-listing" not in text:
            bad.append(f"S2 {name}: no published-listing search with Unpublish")
            continue
        if not re.search(r"\.ilike\.\"\*\$\{", text) or "replace(/[\\\\%_]/g" not in text:
            bad.append(f"S2 {name}: the listing search does not quote the person's text or escape LIKE's % and _")
        if not re.search(r"\.eq\('status', 'published'\)\s*;?\s*\n\s*if \(btn\.dataset\.stamp\)", text):
            bad.append(f"S2 {name}: Unpublish is not guarded on the listing still being published and on the version searched")
        if "unverify-kyb" not in text or "unverify-cert" not in text:
            bad.append(f"S3 {name}: no Remove-badge control for a verified seller")
        elif not re.search(r"\.eq\(_isCert \? 'cert_verified' : 'kyb_verified', true\)", text):
            bad.append(f"S3 {name}: a badge removal is not guarded on the badge still being held")
    for el in ("mkt-published-search", "mkt-verified-search"):
        if f'id="{el}"' not in fc:
            bad.append(f"S2/S3 founder-console.html: #{el} is missing")
    mig = ROOT / "supabase" / "migrations" / "20261026000016_a_removed_badge_is_a_decision.sql"
    mig_text = _read("supabase/migrations/20261026000016_a_removed_badge_is_a_decision.sql", ref) if ref else (mig.read_text(encoding="utf-8") if mig.exists() else "")
    if "unverify_seller_kyb" not in mig_text or "unpublish_listing" not in mig_text:
        bad.append("S3 the database does not record a badge removal or an unpublish (migration 20261026000016)")
    ix = _read("index.html", ref)
    if not re.search(r"from\('pm_completions'\)[\s\S]{0,400}\.limit\(500 \+ 1\)", ix) or "part.filter(id => !seen.has(id))" not in ix:
        bad.append("S4 index.html: a full piece of PM completions still drops the assets past the 500th")
    return bad


def main() -> int:
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    bad = check(ref)
    print(f"in-app-search-honest{' @ ' + ref if ref else ''}: {4 - len({b.split()[0][:2] for b in bad})}/4 facts hold")
    for b in bad:
        print("  - " + b)
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
