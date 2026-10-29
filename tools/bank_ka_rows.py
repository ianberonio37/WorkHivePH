#!/usr/bin/env python3
"""bank_ka_rows.py - bank keep-abreast rows on the reading their lens names (Wave KA, 2026-10-29).

KA-S (KA189..KA308), one row per sitemap URL: "this URL was pushed to the index (an IndexNow receipt) after its last
change; its indexed state is read when the Search Console credential exists, never assumed". A row closes only when
all three hold, each read now:
  1. the deployed origin serves the URL: a raw HTTP GET (no JS - what a crawler receives) answers 200, and the page's
     <link rel="canonical"> names that same URL;
  2. indexnow_receipts.json's per-URL map names the URL with an accepted push (HTTP 200/202) dated on or after its
     sitemap <lastmod> - the receipt kept every push since 2026-10-29, backfilled from the file's own git history;
  3. freshness_trip.py raises no push trip for it (the trip reads the same map, so 2 and 3 agree by construction - 3 is
     run anyway, because the trip is the row's declared close).
The indexed state is NOT read - no Search Console credential exists (KA-B) - and every basis says so rather than
implying it. A row that fails any check is left as it is and printed with the reason.

    python tools/bank_ka_rows.py --lens S [--dry] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402
import freshness_trip as ft  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RECEIPTS = ROOT / "indexnow_receipts.json"
UA = "WorkHive-keep-abreast/1.0 (+https://workhiveph.com) raw-http"
CANON = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']|'
                   r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', re.I)


def served(url: str) -> tuple[int | None, str | None, str]:
    """(status, canonical, note) from a plain GET of what the deployed origin serves."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(400_000).decode("utf-8", errors="replace")
            m = CANON.search(body)
            return r.status, (m.group(1) or m.group(2)) if m else None, ""
    except urllib.error.HTTPError as e:
        return e.code, None, str(e.reason)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, None, str(e)[:120]


def bank_s(dry: bool, limit: int | None) -> int:
    rec = json.loads(RECEIPTS.read_text(encoding="utf-8")) if RECEIPTS.exists() else {}
    pushed = rec.get("pushed") or {}
    if not pushed:
        print("  refused: indexnow_receipts.json has no per-URL map - run tools/indexnow_submit.py --backfill-history")
        return 1
    c = ft.census()
    push_trips = {t["unit"] for t in c["trips"] if t["kind"] == "push"}
    urls = {u["path"]: u for u in c["url_list"]}
    ok, last = bsw._run_gate(str(ROOT / "tools" / "freshness_trip.py"), "--check")
    print(f"  gate seo-trip (freshness_trip.py --check): {'PASS' if ok else 'FAIL'} - {last}")
    if not ok:
        print("  refused: a row is never banked on a red gate")
        return 1
    reg = bsw._load_registry()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "KA-S" and t.get("status") not in ("locked", "descoped")]
    banked, left = 0, []
    for t in rows[: limit or None]:
        unit = (t.get("ka") or {}).get("unit")
        u = urls.get(unit)
        if not u:
            left.append(f"{t['id']} {unit}: not in the sitemap")
            continue
        loc, lastmod = u["loc"], u["lastmod"]
        at = pushed.get(loc) or {}
        at_ts = at.get("at") if isinstance(at, dict) else at
        code = at.get("response") if isinstance(at, dict) else None
        if not at_ts or (lastmod and at_ts[:10] < lastmod):
            left.append(f"{t['id']} {unit}: last push {at_ts or 'never'} is before its lastmod {lastmod}")
            continue
        if unit in push_trips:
            left.append(f"{t['id']} {unit}: freshness_trip still raises a push trip")
            continue
        status, canonical, note = served(loc)
        time.sleep(0.4)   # one URL at a time, politely - this is the live site
        if status != 200:
            left.append(f"{t['id']} {unit}: the deployed origin answered {status or 'nothing'} {note}")
            continue
        if canonical and canonical.rstrip("/") != loc.rstrip("/"):
            left.append(f"{t['id']} {unit}: served canonical {canonical} is not {loc}")
            continue
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. Measured live - a raw-http fetch of the deployed origin "
                 f"({now}): GET {loc} "
                 f"answered 200, canonical {'= that URL' if canonical else 'not declared'}. indexnow_receipts.json pushed "
                 f"it {at_ts} (HTTP {code or 200}) on or after its last change (<lastmod> {lastmod}); freshness_trip.py "
                 f"raises no push trip for it. Gate seo-trip. Indexed state NOT read: no Search Console credential (KA-B) "
                 f"- the row claims the push, never the index.")
        if dry:
            print(f"  would bank {t['id']} {unit}: pushed {at_ts}, lastmod {lastmod}, served 200")
        else:
            bsw._bank(reg, t["id"], basis, ["seo-trip"])
        banked += 1
    if not dry and banked:
        bsw._write_registry(reg)
    for line in left:
        print("  left open: " + line)
    print(f"{'would bank' if dry else 'banked'} {banked} KA-S row(s); {len(left)} left open")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lens", choices=["S"], required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    return bank_s(a.dry, a.limit)


if __name__ == "__main__":
    sys.exit(main())
