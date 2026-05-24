"""
Hierarchical Summaries Backfill (Item 5 of integration runbook)
================================================================
Calls the deployed hierarchical-summarizer edge fn for every (hive_id,
level, period) combination needed so the agentic-rag-loop Retriever Lane C
(Item 2) has data to read.

DEFAULT BEHAVIOUR: dry-run. Prints what WOULD be backfilled. Pass --commit
to actually invoke the edge fn. Pass --hive-ids to scope (otherwise pulls
all active hives from the hives table).

Spread schedule: yearly first (cheapest, biggest payoff), then quarterly,
then monthly. Each level run gets a tiny sleep between hives to avoid
hitting Groq TPM caps on the digest LLM call.

Usage:
  # Dry-run for all active hives, last 5 years yearly + 4 quarters + 12 months
  python tools/backfill_hierarchical_summaries.py

  # Production backfill for two hives
  python tools/backfill_hierarchical_summaries.py --hive-ids <UUID1>,<UUID2> --commit

Env:
  SUPABASE_URL                 required when --commit
  SUPABASE_SERVICE_ROLE_KEY    required when --commit
"""

from __future__ import annotations
import os
import sys
import time
import json
import argparse
from datetime import date, timedelta
from typing import List, Tuple


def lazy_imports():
    try:
        import requests  # noqa: F401
        from supabase import create_client  # noqa: F401
    except ImportError as e:
        print(f"FAIL: missing dep ({e}). pip install requests supabase")
        sys.exit(2)


def yearly_periods(n_years: int) -> List[Tuple[str, str, str]]:
    # Returns [(year_label, period_start_iso, period_end_iso), ...]
    out = []
    today = date.today()
    for offset in range(n_years, 0, -1):
        y = today.year - offset
        out.append((str(y), f"{y}-01-01", f"{y}-12-31"))
    return out


def quarterly_periods(n_quarters: int) -> List[Tuple[str, str, str]]:
    out = []
    today = date.today()
    cur_y, cur_q = today.year, (today.month - 1) // 3
    for offset in range(n_quarters, 0, -1):
        q = cur_q - offset
        y = cur_y
        while q < 0:
            q += 4
            y -= 1
        start_m = q * 3 + 1
        end_m   = start_m + 3
        end_y   = y + (1 if end_m > 12 else 0)
        end_m   = end_m if end_m <= 12 else end_m - 12
        period_start = date(y, start_m, 1).isoformat()
        period_end   = (date(end_y, end_m, 1) - timedelta(days=1)).isoformat()
        out.append((f"Q{q+1} {y}", period_start, period_end))
    return out


def monthly_periods(n_months: int) -> List[Tuple[str, str, str]]:
    out = []
    today = date.today().replace(day=1)
    for offset in range(n_months, 0, -1):
        y = today.year
        m = today.month - offset
        while m < 1:
            m += 12
            y -= 1
        start = date(y, m, 1)
        next_m = m + 1
        next_y = y
        if next_m > 12:
            next_m = 1
            next_y = y + 1
        end = date(next_y, next_m, 1) - timedelta(days=1)
        out.append((start.strftime("%B %Y"), start.isoformat(), end.isoformat()))
    return out


def invoke_summarizer(url: str, key: str, hive_id: str, level: str, period_start: str, period_end: str) -> dict:
    import requests
    r = requests.post(
        f"{url}/functions/v1/hierarchical-summarizer",
        headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": "application/json"},
        json={"hive_id": hive_id, "level": level, "period_start": period_start, "period_end": period_end},
        timeout=60,
    )
    return {"status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill hierarchical-summarizer for past periods")
    ap.add_argument("--hive-ids", help="Comma-separated hive UUIDs (default: all active hives via hives table)")
    ap.add_argument("--years",    type=int, default=5,  help="N yearly summaries (default 5)")
    ap.add_argument("--quarters", type=int, default=4,  help="N quarterly summaries (default 4)")
    ap.add_argument("--months",   type=int, default=12, help="N monthly summaries (default 12)")
    ap.add_argument("--sleep-ms", type=int, default=400, help="Sleep between calls to avoid TPM caps (default 400ms)")
    ap.add_argument("--commit",   action="store_true", help="Actually invoke (default: dry-run)")
    args = ap.parse_args()

    if args.commit:
        lazy_imports()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            print("FAIL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in env when --commit.")
            return 2
        if args.hive_ids:
            hive_ids = [h.strip() for h in args.hive_ids.split(",") if h.strip()]
        else:
            from supabase import create_client
            db = create_client(url, key)
            res = db.table("hives").select("id").limit(1000).execute()
            hive_ids = [r["id"] for r in (res.data or [])]
    else:
        hive_ids = (args.hive_ids or "<dry-run-no-db>").split(",")

    yp = yearly_periods(args.years)
    qp = quarterly_periods(args.quarters)
    mp = monthly_periods(args.months)
    print(f"Plan: yearly={len(yp)} + quarterly={len(qp)} + monthly={len(mp)} per hive × {len(hive_ids)} hives")
    print(f"Total calls: {(len(yp) + len(qp) + len(mp)) * len(hive_ids)}")
    print(f"Commit mode: {'YES' if args.commit else 'NO (dry-run)'}")
    print()

    summary = {"ok": 0, "fail": 0, "skipped": 0}
    for hive_id in hive_ids:
        for level, plan in [("year", yp), ("quarter", qp), ("month", mp)]:
            for label, period_start, period_end in plan:
                tag = f"hive={hive_id[:8]}... level={level:<7} {label:<14}"
                if not args.commit:
                    print(f"  [dry-run] {tag}  would call hierarchical-summarizer for {period_start}..{period_end}")
                    summary["skipped"] += 1
                else:
                    try:
                        res = invoke_summarizer(url, key, hive_id, level, period_start, period_end)
                        if res["status"] == 200:
                            summary["ok"] += 1
                            print(f"  OK    {tag}  {res['body'].get('written', 0)} written")
                        else:
                            summary["fail"] += 1
                            print(f"  FAIL  {tag}  HTTP {res['status']}: {str(res['body'])[:80]}")
                    except Exception as err:
                        summary["fail"] += 1
                        print(f"  FAIL  {tag}  {err}")
                    time.sleep(args.sleep_ms / 1000)

    print()
    print(f"Done. ok={summary['ok']} fail={summary['fail']} skipped={summary['skipped']}")
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
