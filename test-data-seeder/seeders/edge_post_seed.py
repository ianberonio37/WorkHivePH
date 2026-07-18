"""Trigger edge functions that compute derived data after raw seeding.

Both functions read existing logbook/asset rows and write derived tables that
the dashboards rely on:
  - failure-signature-scan -> pattern_alerts (Hive Dashboard D)
  - benchmark-compute      -> hive_benchmarks (PH Intelligence G)

Skips silently if the edge functions are not deployed locally — the WARNs
will simply remain.
"""
import os
import urllib.request
import urllib.error
import json


def _functions_base_url() -> str:
    return os.getenv("SUPABASE_FUNCTIONS_URL", "http://127.0.0.1:54321/functions/v1")


def _service_key() -> str | None:
    # supabase Python client stores the key it was given — we read the env directly
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")


def _invoke(name: str, body: dict, log) -> dict | None:
    url = f"{_functions_base_url()}/{name}"
    headers = {"Content-Type": "application/json"}
    key = _service_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        log(f"  WARN: {name} returned HTTP {e.code} — {e.read().decode('utf-8', errors='replace')[:200]}")
        return None
    except urllib.error.URLError as e:
        log(f"  WARN: {name} unreachable ({e}) — derived data not refreshed")
        return None
    except Exception as e:
        log(f"  WARN: {name} crashed ({e})")
        return None


def run_post_seed_edges(client, log, ctx: dict) -> dict:
    hives = ctx.get("hives") or []
    log(f"Triggering post-seed edge functions for {len(hives)} hives...")

    fss_ok = 0
    bench_ok = 0
    intel_ok = 0
    for h in hives:
        hid = h["id"]
        if _invoke("failure-signature-scan", {"hive_id": hid}, log) is not None:
            fss_ok += 1
        if _invoke("benchmark-compute", {"hive_id": hid}, log) is not None:
            bench_ok += 1
        # intelligence-report populates the PH Intelligence page (failure modes + summary)
        if _invoke("intelligence-report", {"hive_id": hid}, log) is not None:
            intel_ok += 1

    log(f"  failure-signature-scan: {fss_ok}/{len(hives)} hives processed")
    log(f"  benchmark-compute:      {bench_ok}/{len(hives)} hives processed")
    log(f"  intelligence-report:    {intel_ok}/{len(hives)} hives processed")

    # Spare-parts BOM (Inventory PDDA, 2026-07-12): born-linked on every reseed. Runs
    # here because it needs BOTH inventory_items AND asset_nodes present in the DB (the
    # ctx assets carry in-memory ids, not the asset_nodes uuids linked_asset_node_ids needs).
    # Idempotent; only writes linked_asset_node_ids (ledger untouched). Mirrors
    # tools/backfill_asset_part_bom.py via the shared compute_asset_links mapping.
    bom_linked = 0
    try:
        from seeders.inventory import compute_asset_links
        assets = client.table("asset_nodes").select("id, tag, iso_class, hive_id").limit(5000).execute().data or []
        items  = client.table("inventory_items").select("id, part_number, hive_id").limit(5000).execute().data or []
        by_hive_a, by_hive_i = {}, {}
        for a in assets:
            by_hive_a.setdefault(a["hive_id"], []).append(a)
        for it in items:
            by_hive_i.setdefault(it["hive_id"], []).append(it)
        for hid, hitems in by_hive_i.items():
            links = compute_asset_links(hitems, by_hive_a.get(hid, []))
            for it in hitems:
                desired = links.get(it["id"])
                client.table("inventory_items").update({"linked_asset_node_ids": desired or None}).eq("id", it["id"]).execute()
                if desired:
                    bom_linked += 1
        log(f"  asset↔part BOM:         {bom_linked} parts linked to their equipment")
    except Exception as e:  # never let the BOM step break a seed run
        log(f"  WARN: asset↔part BOM link step failed ({e})")

    return {
        "edge_failure_scan_ok":   fss_ok,
        "edge_benchmark_ok":      bench_ok,
        "edge_intelligence_ok":   intel_ok,
        "asset_part_bom_linked":  bom_linked,
    }
