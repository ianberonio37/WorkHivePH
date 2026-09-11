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


def _all_rows(url: str, key: str, select: str, page: int = 1000) -> List[Dict[str, Any]]:
    """Every logbook row for `select`, paged - never a capped window.

    ★A CAP ON AN INVENTORY READ SILENTLY CHOOSES WHO GETS SEEDED (2026-09-10). Both readers below
    asked for `logbook?...&limit=2000` against a table holding 3,847 rows, unordered. Whichever hives
    happened to fall inside that window became the whole world: the checkpoint records THREE hive ids,
    and the platform has SIX. The three that missed out (the delivery fleets) were not skipped by any
    rule anyone wrote - they were simply past row 2000, and the seeder's own summary line then reported
    "3 hives" as though that were the plan. Five years of history for half the platform, and nothing
    anywhere said so.

    The cost showed up far away and much later: sixteen journey walks across nine archetypes failed on
    "this row is set at year-2 ... this hive holds 90 days", which reads as a product gap and is really
    this cap. A capped read that feeds a WRITE is worse than a capped read that feeds a list, because
    the list is merely short while the write is wrong everywhere it did not reach.

    Paged with an explicit stable order, so the last page is the end of the table and not the end of a
    budget. See [[feedback_a_row_cap_is_not_pagination]].
    """
    import requests
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        r = requests.get(
            f"{url}/rest/v1/logbook?select={select}&order=id.asc&limit={page}&offset={offset}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=60,
        )
        r.raise_for_status()
        chunk = r.json()
        out.extend(chunk)
        if len(chunk) < page:
            return out
        offset += page


def _registered_assets(url: str, key: str) -> Dict[str, set]:
    """{hive_id: {lowercased name and tag}} from asset_nodes - the REGISTRY of what exists."""
    import requests
    from collections import defaultdict
    out: Dict[str, set] = defaultdict(set)
    offset = 0
    while True:
        r = requests.get(f"{url}/rest/v1/asset_nodes?select=hive_id,name,tag&limit=1000&offset={offset}",
                         headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=60)
        r.raise_for_status()
        chunk = r.json()
        for row in chunk:
            if row.get("hive_id"):
                for v in (row.get("name"), row.get("tag")):
                    if v and str(v).strip():
                        out[row["hive_id"]].add(str(v).strip().lower())
        if len(chunk) < 1000:
            return out
        offset += 1000


def fetch_hive_assets(url: str, key: str) -> Dict[str, List[str]]:
    """Return {hive_id: [asset names]} that BOTH appear in the logbook AND resolve to a registered asset.

    ★A SEEDER THAT TAKES ITS INVENTORY FROM THE LOGBOOK MULTIPLIES THAT LOGBOOK'S ORPHANS (2026-09-10).
    `machine` is free text a worker types, so a hive accumulates names that were never registered as
    assets. Lucena held 71 such rows out of 1,170 - about 6%, a normal amount of field mess. Cloning
    five years of history from that list turned 71 into 1,200: the seeder had faithfully reproduced
    every orphan forty times over, and the hive went from 6% unresolvable to 17%.

    That is not cosmetic. `batch-risk-scoring` deliberately DROPS any score whose machine name this hive
    cannot resolve to an asset_nodes row (its own comment: "a score for an asset that does not exist is a
    dead-end headline"), so every orphan the seeder invents is history the intelligence layer must then
    throw away - and the more history we add, the more of it is unusable. A fixture that grows its own
    noise faster than its signal is worse than a smaller one.

    So the inventory is INTERSECTED with the asset registry. Where a hive has no registered assets at all
    the logbook list still stands, because seeding nothing would be worse than seeding names that at least
    match the hive's real usage - and that case is reported rather than silently taken.
    """
    from collections import defaultdict
    seen: Dict[str, set] = defaultdict(set)
    for row in _all_rows(url, key, "hive_id,machine"):
        if row.get("hive_id") and row.get("machine"):
            seen[row["hive_id"]].add(row["machine"])
    registry = _registered_assets(url, key)
    out: Dict[str, List[str]] = {}
    for hive, names in seen.items():
        known = registry.get(hive) or set()
        kept = sorted(n for n in names if str(n).strip().lower() in known)
        if not kept and names:
            print(f"  ! {hive[:8]}: none of its {len(names)} logbook machine name(s) resolve to a "
                  f"registered asset - seeding its history on the unresolved names")
            kept = sorted(names)
        elif len(kept) < len(names):
            print(f"  · {hive[:8]}: {len(names) - len(kept)} of {len(names)} logbook machine name(s) are "
                  f"not registered assets and are NOT being cloned (they would multiply into orphans)")
        out[hive] = kept
    return out


def fetch_hive_workers(url: str, key: str) -> Dict[str, List[str]]:
    """Return {hive_id: [worker_names]} from existing logbook - EVERY hive, not a window's worth."""
    from collections import defaultdict
    out: Dict[str, set] = defaultdict(set)
    for row in _all_rows(url, key, "hive_id,worker_name"):
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
        # ★A CORPUS WRITE MUST BE TELLABLE FROM THE CORPUS (2026-09-10). The first 13,400 rows carried no
        # mark at all, so once inserted they were indistinguishable from hand-seeded fixture data and the
        # only way to reverse them was a date guess. `sync_meta` is the row's own metadata column
        # (jsonb NOT NULL DEFAULT '{}'), and its single reader is
        # `COALESCE((sync_meta->>'offline_queued')::boolean, false)` in the hive-readiness RPC - a key it
        # does not set is invisible to that reader, so this marks the rows without changing what any
        # query about them returns. Reversal is now exact:
        #   delete from logbook where sync_meta->>'seed' = '5y-synthetic';
        "sync_meta":        {"seed": "5y-synthetic"},
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


def _assets_without_history():
    """[(asset name, hive name)] for every REGISTERED asset that holds no logbook row at all.

    ★THE UNIT OF WORK IS THE ASSET, SO THAT IS WHAT THE RECEIPT MUST COUNT (2026-09-10). The span
    check above is about hives, and a hive stays deep forever once seeded - so eighteen vehicles
    registered into the three fleet hives afterwards were invisible to it, and the seeder refused to
    run while they held nothing. This asks the question the seeder's own loop asks: which assets have
    it never written for? Empty list on an unreadable database, never a re-seed on a guess - the same
    rule the span check follows, because an unverifiable claim is left alone.

    ★AND THE JOIN KEY IS THE TAG, NOT THE NAME - checked before this was believed. The first version
    matched `logbook.machine = asset_nodes.name` and reported 113 unseeded assets including ALL 96
    plant assets, which is impossible beside 7,000 logbook rows per plant. `logbook.machine` holds the
    TAG ("M-003", "UPS-004"); the fleets match on name only because their vehicles are named that way.
    Matching either key gives the honest figure: 23, being the vehicles registered today plus six in
    Lucena. A checkpoint that over-reports is as useless as one that under-reports - it would have
    re-seeded the whole platform every run, so the number was verified against the database before a
    single row was written on the strength of it.
    """
    import subprocess
    # ★AND ONLY EQUIPMENT CAN HAVE MACHINE HISTORY. The hierarchy also holds one `enterprise`, one
    # `plant` and one `site` node - containers, not machines - which will never carry a logbook row.
    # Counting them would make this checkpoint UNSATISFIABLE: it would report work outstanding on
    # every run for ever, and a guard that can never be satisfied is one people learn to pass with
    # --force. Scope it to the level the seeder actually writes for.
    sql = ("select a.name || '|' || h.name from asset_nodes a join hives h on h.id = a.hive_id "
           "where a.level = 'equipment' "
           "  and not exists (select 1 from logbook l where l.hive_id = a.hive_id "
           "                  and (l.machine = a.tag or l.machine = a.name)) "
           "order by h.name, a.name")
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres",
             "-d", "postgres", "-tA", "-c", sql],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        if out.returncode != 0:
            return []
        rows = []
        for line in (out.stdout or "").splitlines():
            if "|" in line:
                name, _, hive = line.rpartition("|")
                if name.strip() and hive.strip():
                    rows.append((name.strip(), hive.strip()))
        return rows
    except Exception:
        return []


def _history_span_days():
    """(shallowest, deepest, per-hive list) of logbook SPAN in days, or (None, None, []) if unreadable.

    Read straight from the database through the local container, because that is the state the
    checkpoint is making a claim about. Returns None rather than a number when it cannot look, so an
    unreadable database never silently triggers a re-seed - an unverifiable claim is left alone.

    ★A MAX OVER HIVES CERTIFIES THE ONE HIVE THAT PASSED (2026-09-10). The first version of this guard
    asked for `max(d)` - the DEEPEST hive - and one deep hive then vouched for all six. Lucena holds 591
    days, so the gate printed "verified, deepest hive holds 591 days" and refused to re-seed while five
    hives sat at 137 days or less and the fleets at 61. The number was true and the conclusion was
    wrong: a seeder's job is every hive, so the honest measure of whether it did its job is the
    SHALLOWEST one, never the best. Same shape as [[feedback_compare_like_with_like_or_the_number_means_nothing]].

    And the measure is the SPAN (max - min), not the age of the oldest row, because that is what a
    "year-2" walk asks of a hive: two years of life it has lived, not one ancient row and a gap.
    """
    import subprocess
    sql = ("select h.name || '|' || (extract(epoch from (max(l.created_at) - min(l.created_at))) / 86400)::int "
           "from hives h join logbook l on l.hive_id = h.id group by h.name order by 1")
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres",
             "-d", "postgres", "-tA", "-c", sql],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        rows = []
        for line in (out.stdout or "").splitlines():
            if "|" in line:
                name, _, d = line.rpartition("|")
                if d.strip().lstrip("-").isdigit():
                    rows.append((name.strip(), int(d.strip())))
        if not rows:
            return None, None, []
        spans = [d for _, d in rows]
        return min(spans), max(spans), rows
    except Exception:
        return None, None, []


def main() -> int:
    ap = argparse.ArgumentParser(description="5-year synthetic history seeder for RAG Flywheel substrate")
    ap.add_argument("--commit", action="store_true", help="Actually insert (default: dry-run)")
    ap.add_argument("--events-per-asset-per-year", type=int, default=EVENTS_PER_ASSET_PER_YEAR)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--force", action="store_true", help="Ignore checkpoint and re-seed")
    args = ap.parse_args()

    if CHECKPOINT.exists() and not args.force:
        ck = json.loads(CHECKPOINT.read_text())
        # ★A CHECKPOINT MUST VERIFY THE STATE IT CLAIMS, NOT MERELY ASSERT IT (2026-09-09).
        # This guard lived entirely in a FILE while the rows it certifies live in the DATABASE, and
        # test-data-seeder/seeders/reset.py truncates `logbook` without touching `.tmp/` - so the
        # receipt can outlive its subject, and a seeder that refuses on a stale receipt suppresses
        # the very fix it exists to apply. It now asks the database instead of trusting the file.
        #
        # HONESTY NOTE, because the first version of this comment overstated it: the check was added
        # on the suspicion that the 13,400 rows were gone, and the verification DISPROVED that -
        # the deepest hive holds 592 days, which is seeded history doing its job. What is true is
        # narrower and still worth the code: only ONE of the three hives the checkpoint names is deep
        # (the other two floor at 137 days), and no hive reaches the ~730 days a "year-2" walk needs,
        # which leaves 38 journey rows measurably short of the moment their cell names. The threshold
        # below is set to catch a WIPE (a reset leaves ~60-137 days), not to judge sufficiency for any
        # particular walk - that is the caller's question, and the depth is now printed so it can ask.
        shallow, deep, per_hive = _history_span_days()
        if per_hive:
            print("  per-hive logbook span (days): "
                  + ", ".join(f"{n} {d}" for n, d in sorted(per_hive, key=lambda x: x[1])))
        # the SHALLOWEST hive decides, because a seeder that skipped a hive has not run for that hive,
        # however deep its best one is
        # ★A SPAN CANNOT SEE AN ASSET THAT WAS REGISTERED AFTER THE RUN (2026-09-10). The check above
        # asks "is every hive deep enough", and every hive is - so this refused to run while EIGHTEEN
        # vehicles, added to the three fleet hives the same day, held zero rows between them. That is
        # the identical shape as the `max()` guard this file already carries a scar from: a number that
        # is true about the corpus as a whole and silent about the part that is missing. The unit of
        # work here is the ASSET, because that is what the seeder iterates and what it writes 40
        # events per year against - so the checkpoint has to count assets, not days.
        unseeded = _assets_without_history()
        if shallow is not None and shallow < 400:
            print(f"CHECKPOINT says {ck.get('rows_inserted', '?')} rows on {ck.get('ran_at', '?')} across "
                  f"{len(ck.get('hives') or [])} hive(s), but the SHALLOWEST hive holds only {shallow} days "
                  f"of history (deepest {deep}) - either a reset cleared `logbook` and not `.tmp/`, or the "
                  "run never reached that hive at all. Re-seeding.")
        elif unseeded:
            print(f"CHECKPOINT says {ck.get('rows_inserted', '?')} rows on {ck.get('ran_at', '?')}, and every "
                  f"hive is deep enough - but {len(unseeded)} registered asset(s) hold NO logbook history at "
                  f"all, so the corpus is deep and incomplete at the same time. Re-seeding.")
            for name, hive in unseeded[:8]:
                print(f"    {hive}: {name}")
            if len(unseeded) > 8:
                print(f"    ... and {len(unseeded) - 8} more")
        else:
            print(f"CHECKPOINT exists: seeded {ck.get('rows_inserted', '?')} rows on {ck.get('ran_at', '?')}"
                  + (f"; verified, EVERY hive spans at least {shallow} days" if shallow is not None else ""))
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
