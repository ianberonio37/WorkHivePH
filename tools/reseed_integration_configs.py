#!/usr/bin/env python3
"""reseed_integration_configs - give every hive the CMMS connector its own pages assume it has.

WHY THIS EXISTS (2026-09-09). The contract prober asked cmms-webhook-receiver to carry out its
documented job and got "Config not found", then "Integration disabled". Looking at why turned up 16
rows in integration_configs, every one labelled plainly 'test', every one disabled, dating back to
2026-07-21 - probe residue that no cleanup had ever reached, because a cleanup in a `finally` does
not survive a kill and because a bare 'test' is invisible to the WH-<x>-PROBE marker convention the
residue sweep scans for. validate_no_probe_residue now covers the table and removed them.

That left the honest state: ZERO integration configs on the whole platform. Which is worse than it
sounds, because integrations.html counts three tiles off this table - connectors that are ACTIVE
(enabled and synced within 7 days), STALE (enabled, not synced in 7+ days) and DISABLED - so every
hive read 0/0/0, and the webhook receiver had nothing it could ever be proven against.

A seeded platform should look like a real one: mostly working, with the odd connector gone quiet and
the odd one switched off. That is what this writes, deterministically, one config per hive:

    hive 1, 4, 7 ...  enabled, synced hours ago      -> ACTIVE tile
    hive 2, 5, 8 ...  enabled, synced 11 days ago    -> STALE tile
    hive 3, 6, 9 ...  disabled                       -> DISABLED tile

It goes through seeders/cmms_config_seeder.py rather than writing SQL of its own, so the row shape
stays owned by the generator; only the enabled/last-sync spread is applied here afterwards. Re-runs
replace (the seeder deletes its own "(Local Mock)" rows first), so this is idempotent.

    python tools/reseed_integration_configs.py            # every hive
    python tools/reseed_integration_configs.py --check    # report only, write nothing
"""
import io
import os
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SEEDER = ROOT / "test-data-seeder"
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
CHECK = "--check" in sys.argv

# one connector kind per hive, cycling, so the integrations page is not three copies of SAP
KINDS = ["sap_pm", "maximo", "generic"]
# and the three states its own KPI tiles count separately
STATES = ["active", "stale", "disabled"]


def psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
        input=sql, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def _tally() -> dict:
    """The three tiles integrations.html renders, counted the way its own renderer counts them.

    ★READ THE RENDERER, NOT THE KPI PROSE. The seeded KPI text says these are "sourced from
    external_sync.last_sync_at", and external_sync's column is actually `last_synced_at`, so following
    the prose led to a query that errored and reported both live tiles as empty. The page does not use
    that table at all: renderIntegrationsSummary reads `integration_configs.last_sync_at` off the rows
    it already selected. Counting a tile a different way from the surface that draws it is how a
    fixture ends up 'correct' against a number no reader will ever see.
    """
    q = ("SELECT count(*) FILTER (WHERE enabled AND last_sync_at > now() - interval '7 days'), "
         "count(*) FILTER (WHERE enabled AND (last_sync_at IS NULL OR last_sync_at <= now() - interval '7 days')), "
         "count(*) FILTER (WHERE NOT enabled) FROM integration_configs;")
    parts = (psql(q) or "0|0|0").split("|")
    while len(parts) < 3:
        parts.append("0")
    return {"active": parts[0], "stale": parts[1], "disabled": parts[2]}


def main() -> int:
    if not psql("SELECT 1;"):
        print("SKIP reseed-integration-configs - local database not reachable")
        return 0

    hives = [h for h in psql("SELECT id::text FROM hives ORDER BY created_at;").split("\n") if h.strip()]
    if not hives:
        print("SKIP reseed-integration-configs - no hives to attach a connector to")
        return 0

    before = psql("SELECT count(*) FROM integration_configs;")
    if CHECK:
        print(f"  {len(hives)} hive(s), {before} integration config(s) today")
        for state, n in _tally().items():
            print(f"    {state:9s} {n}")
        return 0

    sys.path.insert(0, str(SEEDER))
    os.chdir(SEEDER)
    try:
        from lib.supabase_client import get_client                      # noqa: E402
        from seeders.cmms_config_seeder import seed_integration_config  # noqa: E402
    except Exception as e:
        print(f"SKIP reseed-integration-configs - seeder not importable ({type(e).__name__}: {e})")
        return 0

    client = get_client()
    written = 0
    for i, hive in enumerate(hives):
        kind = KINDS[i % len(KINDS)]
        state = STATES[i % len(STATES)]
        try:
            seed_integration_config(client, hive, cmms_type=kind, log=lambda _s: None)
        except Exception as e:
            print(f"  ! {hive[:8]} {kind}: {type(e).__name__}: {e}")
            continue
        written += 1
        # the seeder always writes enabled=True with no sync clock; apply this hive's state on top.
        # last_sync_at lives on integration_configs itself - the same column the page's renderer reads.
        if state == "disabled":
            psql(f"UPDATE integration_configs SET enabled = false WHERE hive_id = '{hive}';")
        else:
            ago = "4 hours" if state == "active" else "11 days"
            psql("UPDATE integration_configs SET last_sync_at = now() - interval "
                 f"'{ago}', last_sync_status = 'ok', last_sync_count = 42 WHERE hive_id = '{hive}';")
        print(f"  {hive[:8]}  {kind:8s} -> {state}")

    after = psql("SELECT count(*) FROM integration_configs;")
    print(f"\nOK reseed-integration-configs - {written} connector(s) across {len(hives)} hive(s); "
          f"integration_configs {before} -> {after}. Every tile on integrations.html now has "
          f"something to count, and cmms-webhook-receiver has an enabled config to be proven against.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
