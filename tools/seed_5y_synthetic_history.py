"""
5-Year Synthetic History Seeder (RAG Flywheel substrate)
=========================================================
Generates 5 years of realistic synthetic logbook history per hive so the
Phase 2 hierarchical summarizer, Phase 3 temporal orchestrator, and the
agentic RAG flywheel have deep data to chew on. Without this the AI
"learns" only on 2 months of seeded data and Phase 3's temporal fold
collapses to one-period analyses.

Strategy: CLONE-AND-SHIFT, not pure-random generation.
  - Pulls existing logbook rows as templates (preserves real platform shape)
  - For each year 5/4/3/2/1 back, generates ~40 events per (hive, asset)
  - Shifts created_at by (years_back × 365 + random day-of-year) days
  - Randomizes downtime, root_cause (Breakdown only), within realistic dists
  - Distribution bias toward Breakdown (40% vs original 29%) so Phase 2
    aggregates have failure-count signal across periods

Idempotent: writes a checkpoint file after success. Re-runs no-op.

Usage:
  python tools/seed_5y_synthetic_history.py             # dry-run preview
  python tools/seed_5y_synthetic_history.py --commit    # actually insert

Env (only when --commit):
  SUPABASE_URL                 = http://127.0.0.1:54321
  SUPABASE_SERVICE_ROLE_KEY    = sb_secret_* (local) or service role JWT (remote)
"""

from __future__ import annotations
import os
import sys
import json
import random
import uuid
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

CHECKPOINT = Path(".tmp/seed_5y_synthetic_checkpoint.json")
TEMPLATE_LIMIT = 500          # how many existing rows to pull as templates
EVENTS_PER_ASSET_PER_YEAR = 40
YEARS_BACK = [5, 4, 3, 2, 1]  # 2021, 2022, 2023, 2024, 2025

# Distribution weights (bias toward Breakdown so summaries have signal)
MAINTENANCE_TYPE_WEIGHTS = {
    "Preventive Maintenance": 0.50,
    "Breakdown / Corrective": 0.40,
    "Inspection":             0.08,
    "Project Work":           0.02,
}

# Root-cause weights (only for Breakdown rows)
ROOT_CAUSE_WEIGHTS = {
    "Wear":                  0.25,
    "Lubrication Failure":   0.20,
    "Vibration / Fatigue":   0.15,
    "Misalignment":          0.12,
    "Overload":              0.10,
    "Contamination / Dirt":  0.08,
    "Corrosion":             0.06,
    "Electrical Fault":      0.04,
}

# Pareto-ish downtime in hours: most fixes <2h, long tail
def synthetic_downtime_h(maint_type: str) -> float:
    if maint_type != "Breakdown / Corrective":
        return 0.0
    # Pareto: alpha=1.5 → heavy tail. clip at 24h.
    raw = random.paretovariate(1.5) * 0.5
    return round(min(raw, 24.0), 2)


def weighted_choice(weights: Dict[str, float]) -> str:
    keys = list(weights.keys())
    vals = list(weights.values())
    return random.choices(keys, weights=vals, k=1)[0]


def lazy_imports():
    try:
        import requests  # noqa: F401
    except ImportError:
        print("FAIL: install requests (pip install requests)")
        sys.exit(2)


def fetch_templates(url: str, key: str) -> List[Dict[str, Any]]:
    """Pull existing logbook rows to use as templates."""
    import requests
    r = requests.get(
        f"{url}/rest/v1/logbook?select=hive_id,machine,maintenance_type,category,root_cause,downtime_hours,status,worker_name,action,problem&limit={TEMPLATE_LIMIT}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_hive_assets(url: str, key: str) -> Dict[str, List[str]]:
    """Return {hive_id: [distinct asset_tags]} from existing logbook."""
    import requests
    # Pull more rows to get a fuller asset list per hive
    r = requests.get(
        f"{url}/rest/v1/logbook?select=hive_id,machine&limit=2000",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )
    r.raise_for_status()
    from collections import defaultdict
    out: Dict[str, set] = defaultdict(set)
    for row in r.json():
        if row.get("hive_id") and row.get("machine"):
            out[row["hive_id"]].add(row["machine"])
    return {k: sorted(v) for k, v in out.items()}


def fetch_hive_workers(url: str, key: str) -> Dict[str, List[str]]:
    """Return {hive_id: [worker_names]} from existing logbook."""
    import requests
    r = requests.get(
        f"{url}/rest/v1/logbook?select=hive_id,worker_name&limit=2000",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )
    r.raise_for_status()
    from collections import defaultdict
    out: Dict[str, set] = defaultdict(set)
    for row in r.json():
        if row.get("hive_id") and row.get("worker_name"):
            out[row["hive_id"]].add(row["worker_name"])
    return {k: sorted(v) for k, v in out.items()}


def build_one_row(
    hive_id: str,
    asset: str,
    template: Dict[str, Any],
    workers: List[str],
    when_utc: datetime,
) -> Dict[str, Any]:
    maint_type = weighted_choice(MAINTENANCE_TYPE_WEIGHTS)
    cat = template.get("category") or "Mechanical"
    if maint_type == "Breakdown / Corrective":
        root_cause = weighted_choice(ROOT_CAUSE_WEIGHTS)
        downtime = synthetic_downtime_h(maint_type)
        status = "Closed"
        # PM-style entries have no root cause; Breakdown gets the random one
    else:
        root_cause = ""
        downtime = 0.0
        status = "Closed"

    # closed_at: shift from created_at by the downtime (minimum 30 min for closed rows)
    closed_offset_min = max(30, int(downtime * 60))
    closed_at = when_utc + timedelta(minutes=closed_offset_min)

    return {
        "id":               str(uuid.uuid4()),    # logbook.id is NOT NULL without DEFAULT — client must generate
        "hive_id":          hive_id,
        "machine":          asset,
        "date":             when_utc.date().isoformat(),  # NOT NULL legacy day-grouping field
        "maintenance_type": maint_type,
        "category":         cat,
        "root_cause":       root_cause,
        "downtime_hours":   downtime,
        "status":           status,
        "worker_name":      random.choice(workers) if workers else (template.get("worker_name") or "Synthetic Worker"),
        "action":           (template.get("action") or "")[:200] or "Routine work per SOP.",
        "problem":          (template.get("problem") or "")[:200] or ("Reported fault" if maint_type == "Breakdown / Corrective" else None),
        "created_at":       when_utc.isoformat(),
        "closed_at":        closed_at.isoformat(),
    }


def insert_batch(url: str, key: str, rows: List[Dict[str, Any]]) -> int:
    """Bulk-insert into logbook. PostgREST accepts arrays."""
    import requests
    if not rows:
        return 0
    r = requests.post(
        f"{url}/rest/v1/logbook",
        headers={
            "apikey":         key,
            "Authorization":  f"Bearer {key}",
            "Content-Type":   "application/json",
            "Prefer":         "return=minimal",
        },
        data=json.dumps(rows),
        timeout=60,
    )
    if r.status_code in (200, 201, 204):
        return len(rows)
    raise RuntimeError(f"insert failed: HTTP {r.status_code} body={r.text[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="5-year synthetic history seeder for RAG Flywheel substrate")
    ap.add_argument("--commit", action="store_true", help="Actually insert (default: dry-run)")
    ap.add_argument("--events-per-asset-per-year", type=int, default=EVENTS_PER_ASSET_PER_YEAR)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--force", action="store_true", help="Ignore checkpoint and re-seed")
    args = ap.parse_args()

    if CHECKPOINT.exists() and not args.force:
        ck = json.loads(CHECKPOINT.read_text())
        print(f"CHECKPOINT exists: seeded {ck.get('rows_inserted', '?')} rows on {ck.get('ran_at', '?')}")
        print("Re-run with --force to seed again (will produce duplicate-shape data).")
        return 0

    if args.commit:
        lazy_imports()
        url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not key:
            print("FAIL: SUPABASE_SERVICE_ROLE_KEY required for --commit.")
            return 2
        print(f"Pulling templates + asset inventory from {url} ...")
        templates    = fetch_templates(url, key)
        hive_assets  = fetch_hive_assets(url, key)
        hive_workers = fetch_hive_workers(url, key)
    else:
        url, key  = "http://127.0.0.1:54321", "DRY-RUN"
        templates = []
        hive_assets = {
            "<dry-run-hive-A>": ["AC-001", "MILL-001", "BLR-001"],
            "<dry-run-hive-B>": ["PT-001", "GEN-001"],
        }
        hive_workers = {k: ["Pablo Aguilar", "Bryan Garcia"] for k in hive_assets}

    random.seed(20260521)
    today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)

    total_planned = sum(len(assets) * len(YEARS_BACK) * args.events_per_asset_per_year for assets in hive_assets.values())
    print(f"Plan: {len(hive_assets)} hives × per-hive assets × {len(YEARS_BACK)} years × {args.events_per_asset_per_year} events")
    print(f"Total rows to insert: ~{total_planned}")
    print(f"Commit mode: {'YES' if args.commit else 'NO (dry-run)'}")
    print()

    batch: List[Dict[str, Any]] = []
    rows_inserted = 0

    for hive_id, assets in hive_assets.items():
        workers = hive_workers.get(hive_id, ["Synthetic Worker"])
        for years_back in YEARS_BACK:
            for asset in assets:
                # Pick templates that match this asset's category if available
                asset_templates = [t for t in templates if t.get("machine") == asset and t.get("hive_id") == hive_id]
                if not asset_templates:
                    asset_templates = [t for t in templates if t.get("hive_id") == hive_id] or templates
                if not asset_templates and not args.commit:
                    asset_templates = [{"category": "Mechanical", "action": "Inspection done", "problem": "n/a", "worker_name": "Synthetic"}]

                for _ in range(args.events_per_asset_per_year):
                    # Random day in the target year
                    day_offset = random.randint(0, 364)
                    target = today - timedelta(days=years_back * 365 - day_offset)
                    # Add hour/min jitter
                    target = target.replace(hour=random.randint(6, 22), minute=random.randint(0, 59))
                    template = random.choice(asset_templates) if asset_templates else {}
                    row = build_one_row(hive_id, asset, template, workers, target)
                    batch.append(row)

                    if len(batch) >= args.batch_size:
                        if args.commit:
                            n = insert_batch(url, key, batch)
                            rows_inserted += n
                            print(f"  ... +{n} rows (total {rows_inserted})", end="\r")
                        else:
                            rows_inserted += len(batch)
                        batch = []

    # Flush remainder
    if batch:
        if args.commit:
            n = insert_batch(url, key, batch)
            rows_inserted += n
        else:
            rows_inserted += len(batch)
    print()
    print(f"Done. {rows_inserted} rows {'inserted' if args.commit else 'planned (dry-run)'}.")

    if args.commit:
        CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT.write_text(json.dumps({
            "ran_at":         datetime.now(timezone.utc).isoformat(),
            "rows_inserted":  rows_inserted,
            "hives":          list(hive_assets.keys()),
            "years_back":     YEARS_BACK,
            "events_per_asset_per_year": args.events_per_asset_per_year,
        }, indent=2))
        print(f"Wrote checkpoint: {CHECKPOINT}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
