#!/usr/bin/env python3
"""hs_year_layer.py - Wave HS L4 "a year of the hive": lay a year of thirty members' work into the thirty-member hive.

The seeded hive (test-data-seeder/seeders/full_hive.py) holds a year on some lists only - 421 logbook entries, 180 trail
rows - and a handful on others: 12 machines, 5 projects, 11 PM assets, 25 gateway calls. A list cannot show whether it is
paged, counted honestly past its cap, or searchable for an old item while it holds fewer rows than its cap. This lays a
year's volume per relation, the way age_hive_fixture.py ages one hive's logbook:

  - CLONE AND SHIFT the hive's own rows (the seed's vocabulary stays platform-correct). Every date column of a clone moves
    by ONE offset, so a row's own timeline stays in order (an entry closed after it was opened stays so).
  - the author rotates across the hive's active members, name and account together;
  - a uniquely indexed text (machine tag, part number, project code, change-order number) gets a suffix; any other unique
    collision is skipped (on conflict do nothing);
  - ONE planted old item per relation (--plant) carries a phrase nothing else does, about a year back - the item a search
    must find;
  - triggers off (session_replication_role = replica): a seed writes no trail row, no XP, no re-embed, no daily-cap count.

Every id goes into a manifest; --revert deletes exactly those, also with triggers off (nothing new references a clone).
Do not run a board while the layer is down: data-anchored gates (the stock ledger, counts) read the hive.

  python tools/hs_year_layer.py --lay logbook,hive_audit_log      # lay those relations to a year's volume
  python tools/hs_year_layer.py --lay all
  python tools/hs_year_layer.py --status
  python tools/hs_year_layer.py --revert
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "hs_year_layer_manifest.json"
HIVE = "30303030-3030-4030-8030-303030303030"
PSQL = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tAq", "-v", "ON_ERROR_STOP=1"]

# A year of a thirty-member refinery maintenance hive, per relation (the total the hive holds once laid), and the window
# its rows spread over. A gateway's calls are an integration polling every few minutes: the page reads seven days.
YEAR = {
    "logbook": 2500, "hive_audit_log": 3000, "community_posts": 400, "community_replies": 1200, "pm_completions": 2500,
    "inventory_items": 600, "inventory_transactions": 3000, "asset_nodes": 300, "ai_cost_log": 3000,
    "ai_reply_feedback": 400, "ai_audit_log": 1500, "gateway_audit_log": 2000, "pm_assets": 200, "engineering_calcs": 250,
    "projects": 40, "project_items": 400, "project_change_orders": 60, "project_roles": 120, "rcm_fmea_modes": 150,
    "external_sync": 300,   # a year of the plant's CMMS (SAP PM) work orders synced in
    "marketplace_listings": 60,     # a year of the plant's surplus listed by its two sellers
    "marketplace_inquiries": 240,   # a year of buyers' questions to them
}
WINDOW_DAYS = {"gateway_audit_log": 7}
ANCHOR = {"pm_completions": "completed_at", "project_roles": "assigned_at", "external_sync": "last_synced_at"}
NAME_COLS = {"worker_name", "author_name", "submitted_by", "actor", "owner_name", "requested_by", "created_by"}
UID_COLS = {"auth_uid"}
# uniquely indexed text, kept unique by a suffix (and a name a person would tell apart)
SUFFIX = {("asset_nodes", "tag"), ("asset_nodes", "name"), ("inventory_items", "part_number"),
          ("projects", "project_code"), ("project_change_orders", "co_number"), ("external_sync", "external_id")}
FIXED = {("community_replies", "is_accepted"): "false", ("community_replies", "accepted_at"): "null",
         ("marketplace_listings", "sold_to_inquiry_id"): "null"}
# a listing stays its seller's (its account is the seller, not a member drawn at random); an inquiry's BUYER is the one who rotates
KEEP = {("marketplace_listings", "auth_uid"), ("marketplace_listings", "seller_name")}
ROTATE = {("marketplace_inquiries", "buyer_name"): "m.names[s._m]", ("marketplace_inquiries", "buyer_auth_uid"): "m.uids[s._m]"}
# the one old item per relation a search must find: (column, phrase)
PLANT = {
    "logbook": ("problem", "Cracked impeller on cooling water pump CW-P-07B"),
    "hive_audit_log": ("target_name", "Cooling water pump CW-P-07B impeller record"),
    "community_posts": ("content", "Impeller cracking on the CW-P-07 pumps - anyone seen this?"),
    "community_replies": ("content", "We traced our CW-P-07B impeller cracks to cavitation at low suction head"),
    "inventory_items": ("part_name", "Impeller, bronze, CW-P-07B (OEM 4471-220)"),
    "asset_nodes": ("name", "Cooling water pump CW-P-07B"),
    "pm_assets": ("asset_name", "Cooling water pump CW-P-07B"),
    "engineering_calcs": ("project_name", "CW-P-07B suction head check"),
    "projects": ("name", "CW-P-07B impeller replacement"),
    "project_items": ("title", "Replace CW-P-07B impeller"),
    "project_change_orders": ("title", "Add CW-P-07B impeller to scope"),
    "rcm_fmea_modes": ("failure_mode", "Impeller cracked by cavitation (CW-P-07B)"),
    "marketplace_listings": ("title", "Bronze impeller for CW-P-07B, surplus, never fitted"),
    "marketplace_inquiries": ("message", "Is the bronze impeller for CW-P-07B still available? We run the same pump."),
}


def run(sql: str) -> str:
    r = subprocess.run(PSQL, input=sql, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:600])
    return r.stdout.strip()


def columns(rel: str) -> list[tuple[str, str]]:
    out = run("select column_name || '|' || data_type || '|' || is_generated from information_schema.columns "
              f"where table_schema = 'public' and table_name = '{rel}' order by ordinal_position;")
    cols = []
    for line in out.splitlines():
        name, dtype, gen = line.split("|")
        if name == "id" or gen == "ALWAYS" or dtype == "tsvector":
            continue
        cols.append((name, dtype))
    return cols


def expr(rel: str, name: str, dtype: str) -> str:
    if (rel, name) in FIXED:
        return FIXED[(rel, name)]
    if (rel, name) in KEEP:
        return f"s.{name}"
    if (rel, name) in ROTATE:
        return ROTATE[(rel, name)]
    if (rel, name) == ("rcm_fmea_modes", "asset_id"):
        # a failure mode is unique per machine and function: a year's analyses spread across the hive's machines
        live = f"from public.asset_nodes where hive_id = '{HIVE}' and deleted_at is null"
        return f"(array(select id {live} order by id))[1 + (s._g % (select count(*) {live}))::int]"
    if dtype.startswith("timestamp"):
        return f"s.{name} + s._d"
    if dtype == "date":
        return f"(s.{name} + s._d)::date"
    if name in NAME_COLS:
        return f"m.names[s._m]"
    if name in UID_COLS:
        return f"m.uids[s._m]"
    if (rel, name) in SUFFIX:
        return f"s.{name} || '-Y' || s._g"
    return f"s.{name}"


def lay(rel: str, manifest: dict, plant: bool) -> str:
    cols = columns(rel)
    names = {c for c, _ in cols}
    anchor = ANCHOR.get(rel, "created_at")
    have = int(run(f"select count(*) from public.{rel} where hive_id = '{HIVE}';") or 0)
    want = max(0, YEAR[rel] - have)
    live = "and deleted_at is null" if "deleted_at" in names else ""
    days = WINDOW_DAYS.get(rel, 365)
    col_list = ", ".join(c for c, _ in cols)
    exprs = ", ".join(expr(rel, c, t) for c, t in cols)
    members = ("m as (select array_agg(worker_name order by worker_name) as names, array_agg(auth_uid order by worker_name) "
               f"as uids, count(*)::int as n from public.hive_members where hive_id = '{HIVE}' and status = 'active')")
    ids = []
    if want:
        mult = want // max(1, have) + 2
        sql = ("begin; set local session_replication_role = replica;\n"
               f"with {members}, src as (select * from public.{rel} where hive_id = '{HIVE}' {live} and {anchor} is not null), "
               f"s as (select src.*, row_number() over () as _g, "
               f"((now() - random() * interval '{days} days') - src.{anchor}) as _d, "
               f"1 + floor(random() * (select n from m))::int as _m from src, generate_series(1, {mult}) k "
               f"order by random() limit {want}) "
               f"insert into public.{rel} ({col_list}) select {exprs} from s, m on conflict do nothing returning id;\ncommit;\n")
        ids += [i for i in run(sql).splitlines() if i and i not in ("BEGIN", "COMMIT", "SET")]
    if plant and rel in PLANT and PLANT[rel][0] in names:
        col, phrase = PLANT[rel]
        pexprs = ", ".join(f"'{phrase.replace(chr(39), chr(39) * 2)}'" if c == col else expr(rel, c, t) for c, t in cols)
        sql = ("begin; set local session_replication_role = replica;\n"
               f"with {members}, s as (select src.*, 0 as _g, (now() - interval '358 days') - src.{anchor} as _d, "
               f"1 + floor(random() * (select n from m))::int as _m from public.{rel} src where hive_id = '{HIVE}' {live} "
               f"and {anchor} is not null order by {anchor}, id limit 1) "
               f"insert into public.{rel} ({col_list}) select {pexprs} from s, m on conflict do nothing returning id;\ncommit;\n")
        planted = [i for i in run(sql).splitlines() if i and i not in ("BEGIN", "COMMIT", "SET")]
        ids += planted
        manifest.setdefault("_plants", {})[rel] = {"id": planted[0] if planted else None, "column": col, "phrase": phrase}
    manifest.setdefault(rel, []).extend(ids)
    now = run(f"select count(*) from public.{rel} where hive_id = '{HIVE}';")
    return f"{rel}: {have} -> {now} (+{len(ids)}{', old item planted' if plant and rel in PLANT else ''})"


def revert(manifest: dict, only: list[str] | None = None) -> None:
    for rel, ids in list(manifest.items()):
        if rel.startswith("_") or not ids or (only and rel not in only):
            continue
        idt = "bigint" if rel == "gateway_audit_log" else "text"
        for i in range(0, len(ids), 2000):
            chunk = ",".join(f"'{x}'" for x in ids[i:i + 2000])
            run("begin; set local session_replication_role = replica;\n"
                f"delete from public.{rel} where id::text = any (array[{chunk}]::text[]);\ncommit;\n")
        print(f"  {rel}: removed {len(ids)} ({idt} ids)")
        manifest[rel] = []
        manifest.get("_plants", {}).pop(rel, None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lay", help="comma-separated relations, or 'all'")
    ap.add_argument("--no-plant", action="store_true", help="do not plant the old item a search must find")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--only", help="with --revert: comma-separated relations to remove (default: all)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    if a.status:
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in manifest.items()}, indent=1))
        return 0
    if a.revert:
        if not manifest:
            print("nothing laid")
            return 0
        only = [r.strip() for r in a.only.split(",")] if a.only else None
        revert(manifest, only)
        if only and any(v for k, v in manifest.items() if not k.startswith("_")):
            MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
            print(f"removed {', '.join(only)}; the rest of the layer stays")
        else:
            MANIFEST.unlink()
            print("year layer removed")
        return 0
    if not a.lay:
        ap.print_help()
        return 2
    rels = list(YEAR) if a.lay == "all" else [r.strip() for r in a.lay.split(",") if r.strip()]
    for rel in rels:
        if rel not in YEAR:
            print(f"  {rel}: not a year-layer relation ({', '.join(YEAR)})")
            continue
        if manifest.get(rel):
            print(f"  {rel}: already laid ({len(manifest[rel])} rows) - --revert first")
            continue
        try:
            print("  " + lay(rel, manifest, not a.no_plant))
        except RuntimeError as e:
            print(f"  {rel}: NOT laid - {e}")
        MANIFEST.parent.mkdir(exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
