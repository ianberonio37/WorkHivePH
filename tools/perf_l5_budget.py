#!/usr/bin/env python3
"""perf_l5_budget.py — Arc L · L5-BUDGET: the B (free-tier) lens projections.

Projects each free-tier resource (DB rows/size, storage, egress, edge invocations,
LLM tokens) at a documented TARGET SCALE and scores it vs the free-tier ceiling —
the budget::* cells of perf_scale_results.json (L0 emits them `pending`). B is the
HIGHEST floor (95%): a free platform that blows the free tier gets a surprise bill.

HONEST-BY-TRANSPARENCY (the Arc-L measured-not-credited ethos): every projection
prints its ceiling, its INPUT ASSUMPTIONS, the computed projection, and the margin.
A cell PASSES only if the projection is at or under the ceiling WITH headroom; the
assumption set is written into the cell's `why` so the verdict is auditable, never
a silent "stays free ✓". Where a resource is dominated by an assumed activity rate
(not a measured fact), that is stated — this is a PROJECTION (roadmap §1 wording),
conservative by design.

★Resource-model correctness (the trap): Supabase free-tier EGRESS (5 GB/mo) bills
DB-row + storage egress, NOT the static HTML/JS (served from the static host/CDN,
off Supabase). So the egress projection is the API read-row bytes + storage
downloads — NOT the per-page transfer weight (that is the S/E lens's concern).

Scale + ceilings + activity rates are CONSTANTS with sources, overridable by args
(--hives N --workers M) so Ian can re-target without code edits.

USAGE: python tools/perf_l5_budget.py                 # project + merge
       python tools/perf_l5_budget.py --dry           # project + report, no write
       python tools/perf_l5_budget.py --hives 100 --workers 20
"""
from __future__ import annotations
import json, os, sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "perf_scale_results.json")
DRY = "--dry" in sys.argv


def _arg(flag, default):
    if flag in sys.argv:
        try:
            return type(default)(sys.argv[sys.argv.index(flag) + 1])
        except Exception:
            pass
    return default


# ── Free-tier ceilings (Supabase Free + Groq/Gemini Free; sourced, as of 2026-01;
#    these are CONSTANTS to re-check against the providers — the projection method,
#    not the exact ceiling, is the durable value). ─────────────────────────────────
CEIL_DB_BYTES        = 500 * 1024**2          # Supabase Free: 500 MB Postgres
CEIL_STORAGE_BYTES   = 1 * 1024**3            # Supabase Free: 1 GB Storage
CEIL_EGRESS_BYTES_MO = 5 * 1024**3            # Supabase Free: 5 GB egress / month
CEIL_EDGE_INVOKE_MO  = 500_000               # Supabase Free: 500 K edge invocations / month
CEIL_LLM_REQ_MO      = 14_400 * 30           # Groq Free ~14.4 K req/day/model → /month (Gemini ~1.5 K/day is lower; Groq is the primary)

# ── Target scale (documented DEFAULT — a free maintenance platform's realistic
#    early-adoption scale; override with --hives/--workers). ────────────────────────
HIVES   = _arg("--hives", 50)
WORKERS = _arg("--workers", 15)              # workers per hive
USERS   = HIVES * WORKERS                     # total active workers
WORK_DAYS_MO = 22                             # active working days / month
MONTHS_HORIZON = 12                           # cumulative horizon for stock resources (DB/storage)

# ── Per-worker ACTIVITY assumptions (documented; conservative-typical for an
#    active maintenance worker. These dominate the projection — stated explicitly). ─
PAGE_LOADS_DAY   = 20                          # app opens / page views per worker-day (egress = API reads on these)
READS_PER_LOAD   = 6                           # bounded supabase reads per page load (avg; all now .limit-capped)
AVG_ROW_BYTES    = 1024                        # avg returned row size (~1 KB; logbook/inventory rows)
AVG_ROWS_PER_READ = 40                         # avg rows actually returned by a bounded read (well under the .limit caps)
EDGE_CALLS_DAY   = 8                           # edge-fn invocations per worker-day (AI/orchestrator/sync)
LLM_CALLS_DAY    = 5                           # LLM-backed calls per worker-day (companion/voice/assistant)
# write/stock growth (DB + storage)
ROWS_WRITTEN_WORKER_MO = 120                   # logbook+pm+schedule+txn+journal rows a worker creates / month
UPLOADS_WORKER_MO      = 6                      # photo/resume/defect uploads / worker / month
AVG_UPLOAD_BYTES       = 350 * 1024            # ~350 KB per uploaded image/doc


def _fmt(b):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024 or u == "TB":
            return f"{b:.1f}{u}"
        b /= 1024


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    # ── projections ──────────────────────────────────────────────────────────────
    # DB size (cumulative over horizon): rows written × row bytes × users × months.
    db_rows = ROWS_WRITTEN_WORKER_MO * USERS * MONTHS_HORIZON
    db_bytes = db_rows * AVG_ROW_BYTES * 1.6   # ×1.6 for index + tuple overhead
    # Storage (cumulative): uploads × size × users × months.
    storage_bytes = UPLOADS_WORKER_MO * AVG_UPLOAD_BYTES * USERS * MONTHS_HORIZON
    # Egress / month: API read bytes (rows returned × row size) + storage re-downloads.
    read_bytes_mo = PAGE_LOADS_DAY * READS_PER_LOAD * AVG_ROWS_PER_READ * AVG_ROW_BYTES * USERS * WORK_DAYS_MO
    storage_dl_mo = UPLOADS_WORKER_MO * AVG_UPLOAD_BYTES * USERS  # ~each upload viewed ~1×/mo across the hive
    egress_mo = read_bytes_mo + storage_dl_mo
    # Edge invocations / month.
    edge_mo = EDGE_CALLS_DAY * USERS * WORK_DAYS_MO
    # LLM requests / month.
    llm_mo = LLM_CALLS_DAY * USERS * WORK_DAYS_MO

    SCALE_NOTE = f"scale: {HIVES} hives × {WORKERS} workers = {USERS} users, {WORK_DAYS_MO} work-days/mo"
    proj = {
        "budget::db-rows": (
            db_bytes, CEIL_DB_BYTES,
            f"{db_rows:,} rows × ~{AVG_ROW_BYTES}B ×1.6 overhead over {MONTHS_HORIZON}mo = {_fmt(db_bytes)} vs {_fmt(CEIL_DB_BYTES)} ({SCALE_NOTE}; {ROWS_WRITTEN_WORKER_MO} rows/worker/mo)"),
        "budget::storage": (
            storage_bytes, CEIL_STORAGE_BYTES,
            f"{UPLOADS_WORKER_MO} uploads/worker/mo × {_fmt(AVG_UPLOAD_BYTES)} × {USERS} users × {MONTHS_HORIZON}mo = {_fmt(storage_bytes)} vs {_fmt(CEIL_STORAGE_BYTES)}"),
        "budget::egress": (
            egress_mo, CEIL_EGRESS_BYTES_MO,
            f"API reads {PAGE_LOADS_DAY}×{READS_PER_LOAD}×{AVG_ROWS_PER_READ}rows×~{AVG_ROW_BYTES}B + storage dl = {_fmt(egress_mo)}/mo vs {_fmt(CEIL_EGRESS_BYTES_MO)}/mo ({SCALE_NOTE}). NB: static HTML/JS is off-Supabase (host/CDN), excluded."),
        "budget::edge-invocations": (
            edge_mo, CEIL_EDGE_INVOKE_MO,
            f"{EDGE_CALLS_DAY} edge calls/worker/day × {USERS} × {WORK_DAYS_MO} = {edge_mo:,}/mo vs {CEIL_EDGE_INVOKE_MO:,}/mo"),
        "budget::llm-tokens": (
            llm_mo, CEIL_LLM_REQ_MO,
            f"{LLM_CALLS_DAY} LLM calls/worker/day × {USERS} × {WORK_DAYS_MO} = {llm_mo:,} req/mo vs Groq free ~{CEIL_LLM_REQ_MO:,} req/mo (per-min RPM also gated by the rate-limiter, Arc H)"),
    }

    # ── Free-tier-viable SCALE per resource: the max #users where each stays under
    #    ceiling (the answer to "how free is it?"). The TIGHTEST is the binding
    #    constraint. Resolves the free-vs-paid fork with a measured number, not a guess.
    per_user = {  # monthly cost contribution per user, at the current per-user assumptions
        "budget::db-rows":          db_bytes / USERS,
        "budget::storage":          storage_bytes / USERS,
        "budget::egress":           egress_mo / USERS,
        "budget::edge-invocations": edge_mo / USERS,
        "budget::llm-tokens":       llm_mo / USERS,
    }
    viable = {sid: (ceil / per_user[sid]) if per_user.get(sid) else float("inf")
              for sid, (_v, ceil, _w) in proj.items()}
    binding_sid = min(viable, key=viable.get)
    free_users = viable[binding_sid]
    # runway-EXTENDERS (what each lever buys, honestly): db-rows -> a 60-day hot window +
    # cold-Parquet archival (~×{12/2}); storage -> client WebP/resize compression (~×5) +
    # external image host; egress -> SW network-first caching of repeat reads + the static
    # CDN (already off-Supabase). NOTE egress is the binding constraint and is inherent to
    # active-user data serving — caching extends it but it is genuinely PAID at large scale.
    EXTENDER = {
        "budget::db-rows": "60-day hot window + cold-Parquet archival prune (cold-archive-query read side exists; the WRITE/prune cron is the build)",
        "budget::storage": "client-side WebP/resize compression (~5x) + an external image host; lifecycle-delete archived uploads",
        "budget::egress":  "the BINDING constraint, and GENUINELY PAID beyond the free scale: egress = API DATA reads, which MUST be network-first (caching live maintenance data = a staleness/safety bug — the SW correctly does NOT cache supabase.co), so it is not cache-reducible; the static shell is already off-Supabase (CDN). Only lever = fewer/leaner reads (already L2-bounded). Coupled to the SW fork: the correct network-first strategy is exactly why egress can't be cached away.",
    }

    rows_out = []
    for sid, (val, ceil, why) in proj.items():
        cell = surf.get(sid)
        if not cell:
            continue
        B = cell["lenses"]["B"]
        margin = (ceil - val) / ceil if ceil else 0
        vscale = viable.get(sid, float("inf"))
        if val <= ceil:
            B["status"] = "pass"
            B["measured"] = f"projected {why} — {margin*100:.0f}% headroom (free to ~{vscale:.0f} users)"
            B["why"] = "projected free-tier usage at the documented target scale is within the ceiling (B = stays-free; re-run --hives/--workers to re-target)"
        else:
            # OVER at the aspirational 750-user scale. The free-vs-paid fork is RESOLVED
            # (Ian, 2026-06-23): the platform is FREE up to its viable scale; beyond that
            # is ACCEPTED paid-at-scale, with the named runway-extender to push the ceiling.
            B["status"] = "fix"
            B["measured"] = f"projected {why} — OVER by {(-margin)*100:.0f}% (free to ~{vscale:.0f} users)"
            B["why"] = (f"DOCUMENTED free-tier scale ceiling (fork RESOLVED, not an open bug): genuinely free to ~{vscale:.0f} users, "
                        f"paid beyond = accepted business reality. Runway-extender: {EXTENDER.get(sid, 'n/a')}")
        rows_out.append((sid, val, ceil, margin, B["status"]))

    # recompute aggregates
    for lens in ("S", "E", "R", "B"):
        p = d = pend = 0
        for s in surf.values():
            c = s.get("lenses", {}).get(lens)
            if not c or not c.get("applicable"):
                continue
            d += 1
            if c["status"] == "pass":
                p += 1
            elif c["status"] == "pending":
                pend += 1
        results["lens_pass"][lens] = p
        results["lens_pending"][lens] = pend
        results["lens_pct"][lens] = round(1000 * p / d) / 10 if d else 0

    if not DRY:
        json.dump(results, open(RESULTS, "w", encoding="utf-8"), indent=2)

    print("=" * 70)
    print(f"ARC L — L5-BUDGET free-tier projections (B lens) — {SCALE_NOTE}")
    print("=" * 70)
    for sid, val, ceil, margin, st in rows_out:
        flag = "PASS" if st == "pass" else "FIX "
        print(f"  [{flag}] {sid:28} {_fmt(val):>10} / {_fmt(ceil):>8}  ({margin*100:+.0f}% headroom)")
    # ── Honest free-tier-viable scale: the DEFAULT constants are deliberately
    #    conservative-PESSIMISTIC (the B lens errs toward "stays free"). Report the
    #    worst-case AND what the cheap buildable levers buy, so the headline number
    #    isn't misread as a hard cap. (storage: WebP/resize ~5x + a lifecycle prune;
    #    egress: realistic field-worker activity vs the heavy 20-loads/day default;
    #    db-rows: a 60-day hot window archival prune.)
    worst = min(viable.values())
    # viable users per resource = ceiling / PER-USER cost (no ×USERS — we are solving for users)
    real_storage = CEIL_STORAGE_BYTES / (UPLOADS_WORKER_MO * (AVG_UPLOAD_BYTES / 5) * 6)            # 5x WebP compress + 6mo lifecycle
    real_egress  = CEIL_EGRESS_BYTES_MO / (10 * READS_PER_LOAD * 25 * AVG_ROW_BYTES * WORK_DAYS_MO)  # 10 loads/day, 25 rows (realistic field worker)
    real_db      = CEIL_DB_BYTES / (ROWS_WRITTEN_WORKER_MO * AVG_ROW_BYTES * 1.6 * 2)                # 60-day hot window archival
    realistic = min(real_storage, real_egress, real_db)
    print(f"\n  -> FREE-TIER-VIABLE SCALE (users):")
    print(f"       worst-case (current pessimistic constants, NO compression/lifecycle): ~{worst:.0f} users  [binding: {binding_sid.split('::')[1]}]")
    print(f"       realistic + cheap buildable levers (img compression 5x + lifecycle/archival prune + real activity): ~{realistic:.0f} users  [binding: egress]")
    print(f"       -> 40 is the FLOOR, not the cap; egress (network-first live data) is the irreducible ceiling at a few hundred active users.")
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> B = {results['lens_pass']['B']}/{sum(1 for s in surf.values() if s['lenses'].get('B',{}).get('applicable'))} = {results['lens_pct']['B']}% (floor 95)")
    print(f"  -> {'(dry, not written)' if DRY else 'merged budget:: B cells into perf_scale_results.json'}")
    print("  NB: assumptions are documented constants — re-target with --hives N --workers M; re-check ceilings vs current provider free tiers.")


if __name__ == "__main__":
    sys.exit(main() or 0)
