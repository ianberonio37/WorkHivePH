#!/usr/bin/env python3
"""scale_readiness.py — Arc L · SCALE-OUT: 1,000,000-user readiness assessment.

Ian (2026-06-23): "do what is needed, I am planning to have a million users." The
free-tier Budget lens (perf_l5_budget.py) is the WRONG frame at 1M users — at that
scale you are on a paid/self-hosted tier and the binding ceilings are ARCHITECTURE,
not free-tier dollars. This tool re-projects each layer at the target scale and names,
per layer: the projected load, the REAL ceiling (the architecture limit, not the free
tier), the LEVER (build / config / architecture-decision), and its STATUS.

It is a map, not a gate — it tells the build order. Honest about what is local-buildable
(compression, archival, caching, pagination) vs an infra/config choice (CDN, read
replicas, pooler tier) vs a hard architecture ceiling that needs a decision (Realtime
fan-out at 1M concurrent).

USAGE: python tools/scale_readiness.py [--users 1000000]
"""
from __future__ import annotations
import sys

def _arg(flag, d):
    if flag in sys.argv:
        try: return type(d)(sys.argv[sys.argv.index(flag) + 1])
        except Exception: pass
    return d

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

USERS = _arg("--users", 1_000_000)
WORK_DAYS = 22
# activity (same constants as perf_l5_budget.py, realistic-typical)
ROWS_WORKER_MO = 120
UPLOADS_WORKER_MO = 6
UPLOAD_BYTES = 350 * 1024
PAGE_LOADS_DAY = 12
READS_PER_LOAD = 6
ROWS_PER_READ = 30
ROW_BYTES = 1024
EDGE_CALLS_DAY = 8
LLM_CALLS_DAY = 5
CONCURRENT_FRAC = 0.02      # ~2% of users active at peak (a common SaaS peak-concurrency ratio)
RT_SUBS_PER_USER = 2        # realtime channels a live user holds (dashboards/alerts)


def human(n, unit=""):
    for s, d in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= d:
            return f"{n/d:.1f}{s}{unit}"
    return f"{n:.0f}{unit}"


def bytes_h(b):
    for u in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(b) < 1024 or u == "PB":
            return f"{b:.1f}{u}"
        b /= 1024


def main():
    peak = USERS * CONCURRENT_FRAC
    rows_yr = ROWS_WORKER_MO * USERS * 12
    db_bytes = rows_yr * ROW_BYTES * 1.6
    storage_yr = UPLOADS_WORKER_MO * UPLOAD_BYTES * USERS * 12
    egress_mo = PAGE_LOADS_DAY * READS_PER_LOAD * ROWS_PER_READ * ROW_BYTES * USERS * WORK_DAYS
    edge_mo = EDGE_CALLS_DAY * USERS * WORK_DAYS
    llm_mo = LLM_CALLS_DAY * USERS * WORK_DAYS
    rt_peak = peak * RT_SUBS_PER_USER

    # (layer, projected@scale, real ceiling at scale, lever, status)
    rows = [
        ("DB data tier (Postgres)",
         f"{human(rows_yr)} rows/yr = {bytes_h(db_bytes)}",
         "a single un-partitioned table degrades into the billions; managed-PG disk + autovacuum + index bloat",
         "declarative PARTITIONING (by hive/month) + ARCHIVAL prune of cold rows to object storage + read replicas for analytics",
         "BUILD — archival read-side exists (cold-archive-query); the WRITE/prune cron + partition migrations are unbuilt"),
        ("DB connections",
         f"~{human(peak)} peak-concurrent users",
         "Postgres direct conns cap ~100-500; 1M users cannot each hold one",
         "Supavisor/pgbouncer TRANSACTION-mode pooling (port 6543) for any direct conn; edge fns already go via PostgREST (pooled)",
         "VERIFY/CONFIG — confirm no client uses the direct 5432 string; PostgREST path already pools"),
        ("Object storage",
         f"{bytes_h(storage_yr)}/yr",
         "cost + per-bucket scale; uncompressed 350KB photos dominate",
         "client WebP/resize COMPRESSION (~5x) + lifecycle archival + serve via CDN, not the API",
         "BUILD — compression does not exist yet (single biggest cost lever)"),
        ("Egress / bandwidth",
         f"{bytes_h(egress_mo)}/mo",
         "cost; API DATA reads (network-first, uncacheable for freshness) dominate",
         "CDN for static (already off-API) + aggressive PAGINATION/lean reads (mostly done, L2) + per-read column trimming",
         "PARTIAL — L2 reads bounded; column-trim + CDN edge-cache for read-mostly reference data is the next lever"),
        ("Edge functions (Deno)",
         f"{human(edge_mo)}/mo invocations",
         "autoscaling runtime; cost-per-invoke + cold starts",
         "Deno Deploy / Supabase Edge autoscale (config); keep boot lean (Arc-L S) + cache deterministic sub-calls",
         "OK — scales horizontally; cost-managed; Arc-L already trimmed boot/CWV"),
        ("LLM provider",
         f"{human(llm_mo)} calls/mo",
         "provider RPM/TPM + COST (110M calls/mo is a real bill)",
         "ai_cache on deterministic sub-calls + cheaper/tiered models + the per-hive rate-limiter (built) + batch where possible",
         "PARTIAL — rate-limiter + some cache built; cache-adoption is the cost lever to widen"),
        ("Realtime (WebSocket)",
         f"~{human(rt_peak)} peak channels",
         "Supabase Realtime ~10K concurrent (the capacity-plan HARD ceiling) << 1M",
         "cut per-user subscriptions to the essential; poll-fallback for non-critical; shard/multiplex or a dedicated RT tier at scale",
         "ARCHITECTURE DECISION — the hardest 1M ceiling; needs a fan-out strategy"),
    ]

    print("=" * 96)
    print(f"ARC L — SCALE-OUT READINESS @ {human(USERS)} users  (peak-concurrent ~{human(peak)} @ {CONCURRENT_FRAC*100:.0f}%)")
    print("=" * 96)
    for layer, proj, ceil, lever, status in rows:
        tag = status.split(" ")[0]
        print(f"\n  ▸ {layer}")
        print(f"      load@scale : {proj}")
        print(f"      ceiling    : {ceil}")
        print(f"      lever      : {lever}")
        print(f"      status     : [{tag}] {status[len(tag)+1:].strip(' -')}")
    builds = [r for r in rows if r[4].startswith(("BUILD", "PARTIAL"))]
    print("\n" + "=" * 96)
    print(f"  BUILD ORDER (local-buildable structural levers, highest cost/risk first):")
    print("    1. Image COMPRESSION (storage — biggest cost lever, client-side, contained)")
    print("    2. ARCHIVAL prune + PARTITIONING (DB data tier — the billions-of-rows ceiling)")
    print("    3. LLM cache-adoption widening (LLM cost)")
    print("    4. Egress column-trim + CDN edge-cache for reference data")
    print("    5. CONNECTION-pool verify (no direct-5432 client) — config")
    print("    6. REALTIME fan-out strategy (architecture decision — the 10K hard ceiling)")
    print(f"\n  Free-tier Budget lens (perf_l5_budget.py) is SUPERSEDED at this scale — it answers")
    print(f"  'stays free for ~150 small-team users'; THIS answers 'scales to {human(USERS)}'.")


if __name__ == "__main__":
    sys.exit(main() or 0)
