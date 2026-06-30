#!/usr/bin/env python3
"""companion_memory_health_gate.py - Companion-Memory C3.2: health-regression gate for the
companion memory store (agent_episodic_memory + agent_memory).
================================================================================
The M2.2 pattern (tools/memory_health_gate.py) ported natively to the Companion's pg store: wrap
the store's health metrics in thresholds so a degraded one FAILs CI instead of needing a human to
read a dashboard. Honesty doctrine inherited from M2.2: a `warming_up` clause defers activity
thresholds on a tiny sample (only always-valid structural invariants run); "show gap, not fiction".

GROUNDED 2026-06-24 (measured before built): the roadmap named silent_rate / p95 latency / grounding,
but on the live store `agent_memory.response_time_ms` is 0/99 populated and there is NO silent_rate /
grounding column — those metrics are UNINSTRUMENTED. So this gate enforces the metrics that ARE
groundable today and SURFACES the instrumentation gap as an informational finding (it does not gate a
metric that is never written — that would be fiction):
  - STRUCTURAL (always): agent_episodic_memory + agent_memory non-empty.
  - INTEGRITY (activity, warming-up if too few procedural rows): procedural_null_embedding_rate must
    be low — a procedural memory stored with embedding=null is INVISIBLE FOREVER to
    match_procedural_memories (the C2.3 "invisible-forever" bug); a spike means recall is silently
    losing the skill library. This is the real, queryable health signal.
  - COVERAGE (informational, NOT gated): response_time_ms / intent_confidence population — surfaces
    the instrumentation gap so a future C3.2b can wire latency/silent thresholds once they're written.

  --self-test  prove teeth: a synthetic DEGRADED snapshot (empty index OR 90% null-embedding) FAILs;
               a healthy one PASSes.

Exit 0 = healthy (or warming up with sound structure / DB down -> SKIP); 1 = a threshold breached.
Stdlib only; reads the LOCAL docker DB read-only; never writes.
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"

MIN_PROC_FOR_RATE = 10        # below this many procedural rows the null-rate is statistically noisy
NULL_EMBED_MAX_PCT = 20.0     # > this fraction of procedural memories un-embedded => recall is losing skills


def _psql(sql: str, timeout: int = 20):
    return subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _db_up() -> bool:
    try:
        r = _psql("select 1;", timeout=10)
        return r.returncode == 0 and r.stdout.strip().startswith("1")
    except Exception:
        return False


def _scalar(sql: str) -> int:
    r = _psql(sql)
    try:
        return int((r.stdout or "").strip())
    except ValueError:
        return -1


def build_payload() -> dict:
    ep_total   = _scalar("select count(*) from public.agent_episodic_memory;")
    proc_total = _scalar("select count(*) from public.agent_episodic_memory where memory_type='procedural';")
    proc_null  = _scalar("select count(*) from public.agent_episodic_memory where memory_type='procedural' and embedding is null;")
    am_total   = _scalar("select count(*) from public.agent_memory;")
    rt_pop     = _scalar("select count(response_time_ms) from public.agent_memory;")
    ic_pop     = _scalar("select count(intent_confidence) from public.agent_memory;")
    # C3.2b: turn latency is now instrumented (saveTurn promotes the gateway's measured latency into
    # response_time_ms; older rows carry it in meta.latency_ms). Surfaced INFORMATIONAL only — it is
    # WHOLE-TURN latency (LLM-dominated on the free tier, high + variable), not memory-RETRIEVAL latency,
    # so a hard memory-health threshold on it would conflate model slowness with store health.
    lat_p95    = _scalar("with l as (select coalesce(response_time_ms, nullif(meta->>'latency_ms','')::int) ms "
                         "from public.agent_memory where kind='turn') "
                         "select coalesce(percentile_disc(0.95) within group(order by ms),0) from l where ms is not null;")
    null_rate  = round(100.0 * proc_null / proc_total, 1) if proc_total > 0 else 0.0
    return {
        "episodic_total": ep_total, "procedural_total": proc_total, "procedural_null": proc_null,
        "procedural_null_rate_pct": null_rate, "agent_memory_total": am_total,
        "response_time_ms_pop": rt_pop, "intent_confidence_pop": ic_pop, "turn_latency_p95_ms": lat_p95,
        "warming_up": proc_total < MIN_PROC_FOR_RATE,
    }


def evaluate(p: dict) -> tuple[list[str], list[str], list[str]]:
    """Return (breaches, applied, skipped)."""
    breaches, applied, skipped = [], [], []
    # structural — always
    for name, val in (("episodic_total", p["episodic_total"]), ("agent_memory_total", p["agent_memory_total"])):
        applied.append(f"{name}={val} >= 1")
        if val < 1:
            breaches.append(f"{name}={val} violates >=1 (store empty — memory layer not persisting)")
    # integrity — procedural null-embedding rate (deferred while warming up)
    if p["warming_up"]:
        skipped.append(f"procedural_null_rate_pct (warming up: {p['procedural_total']} proc rows < {MIN_PROC_FOR_RATE})")
    else:
        applied.append(f"procedural_null_rate_pct={p['procedural_null_rate_pct']} <= {NULL_EMBED_MAX_PCT}")
        if p["procedural_null_rate_pct"] > NULL_EMBED_MAX_PCT:
            breaches.append(f"procedural_null_rate_pct={p['procedural_null_rate_pct']} violates <={NULL_EMBED_MAX_PCT} "
                            f"({p['procedural_null']}/{p['procedural_total']} procedures invisible to match_procedural_memories)")
    return breaches, applied, skipped


def do_self_test() -> int:
    healthy  = {"episodic_total": 239, "procedural_total": 50, "procedural_null": 2,
                "procedural_null_rate_pct": 4.0, "agent_memory_total": 99, "warming_up": False}
    degraded = {"episodic_total": 0, "procedural_total": 50, "procedural_null": 45,
                "procedural_null_rate_pct": 90.0, "agent_memory_total": 0, "warming_up": False}
    hb, _, _ = evaluate(healthy)
    db, _, _ = evaluate(degraded)
    print(f"  healthy snapshot  -> {len(hb)} breaches ({'CLEAN' if not hb else hb})")
    print(f"  degraded snapshot -> {len(db)} breaches ({'CAUGHT' if db else 'MISSED'})")
    if not hb and len(db) >= 3:
        print(f"  {G}TEETH VERIFIED{X} healthy passes; degraded breaches {db} -> gate catches it.")
        return 0
    print(f"  {R}TOOTHLESS{X} healthy_breaches={hb} degraded_breaches={db}")
    return 1


def main() -> int:
    print(f"{B}Companion-Memory C3.2 - memory health-regression gate{X}")
    print("=" * 62)
    if "--self-test" in sys.argv[1:]:
        rc = do_self_test()
        print(f"\n{(G if rc == 0 else R)}{B}  COMPANION HEALTH GATE SELFTEST: {'PASS' if rc == 0 else 'FAIL'}{X}")
        return rc

    if not _db_up():
        print(f"  {Y}SKIP{X} local Supabase DB ({DB}) not reachable — nothing to health-check. Not a failure.")
        return 0

    p = build_payload()
    breaches, applied, skipped = evaluate(p)
    print(f"  store: episodic {p['episodic_total']} ({p['procedural_total']} procedural, "
          f"{p['procedural_null']} null-embedding) · agent_memory {p['agent_memory_total']}")
    for a in applied:
        print(f"    {G}check{X} {a}")
    for s in skipped:
        print(f"    {Y}skip {X} {s}")
    # COVERAGE — informational (the instrumentation gap; NOT gated — gating an unwritten metric = fiction)
    print(f"    {C}info {X} instrumentation: response_time_ms {p['response_time_ms_pop']}/{p['agent_memory_total']} "
          f"populated (C3.2b: saveTurn now writes it going forward), intent_confidence {p['intent_confidence_pop']}/"
          f"{p['agent_memory_total']}. turn-latency p95={p['turn_latency_p95_ms']}ms (INFORMATIONAL — whole-turn/"
          f"LLM-dominated, not retrieval latency; not memory-health-gated).")
    if breaches:
        print(f"\n{R}{B}  COMPANION HEALTH GATE: FAIL{X} - {'; '.join(breaches)}")
        return 1
    note = " (warming up — integrity threshold deferred)" if p["warming_up"] else ""
    print(f"\n{G}{B}  COMPANION HEALTH GATE: PASS{X} - structural + integrity health thresholds met{note}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
