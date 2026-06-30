#!/usr/bin/env python3
"""perf_l5_llm_resilience.py — Arc L · L5-R for the LLM/model-backed edge fns.

The R (Resilience@scale) bar (roadmap §1): "429/503 -> graceful degrade, not error."
`perf_l5_burst.py` deliberately does NOT burst LLM fns (a token-spending burst would
drain free-tier quota), so it leaves their R cell PENDING with a note that the
graceful-degrade IS the rate-limiter 429 path. PENDING counts against the R floor —
so the honest move (CLAUDE.md "build the structure to make it live-able, don't
declare a ceiling") is to PROVE that 429 path deterministically and FOR FREE.

★The zero-token proof. `_shared/rate-limit.ts checkAIRateLimit` returns a structured
429 (`rateLimitedResponse`) the instant `ai_rate_limits.call_count >= cap`, BEFORE any
`callAI()`. So we:
  1. Pre-seed BOTH counter tables to the cap for the test hive + user:
       ai_rate_limits[HIVE]            (the per-hive gate, checkAIRateLimit)
       ai_user_rate_limits[auth_uid]   (per-user + solo gates, checkUserRateLimit / checkSoloRateLimit)
  2. Invoke each LLM/model-backed fn ONCE with a valid body.
  3. A graceful 429 (not a 5xx crash, not a connection drop) = the degrade-at-scale
     contract is honored = R PASS, with ZERO tokens spent (the gate runs first).
     A 500/502/0 = the fn crashes under quota pressure = a REAL R-fix.
     A 200 = the fn did NOT gate on these buckets (deterministic / different limiter)
             -> NOT credited here (honest pending), and no quota was at risk.
  4. ALWAYS truncate the seeded rows afterward (finally) so normal operation resumes.

This is BETTER evidence than a local burst: a 15-wide burst on one local Deno process
measures local queueing; the quota-shed 429 IS the real production degrade path when
many users exhaust a hive's hourly budget at scale.

USAGE: python tools/perf_l5_llm_resilience.py            # seed + probe + merge + cleanup
       python tools/perf_l5_llm_resilience.py --dry      # probe + report, no results write (still seeds+cleans)
"""
from __future__ import annotations
import json, os, re, subprocess, sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

RESULTS = os.path.join(ROOT, "perf_scale_results.json")
BASE = "http://127.0.0.1:54321/functions/v1"
DRY = "--dry" in sys.argv
DB_CONTAINER = "supabase_db_workhive"
# The seeded user = the JWT identity the probe authenticates as (backend_live_invoke
# signs in leandromarquez). Its auth_uid keys the per-user + solo buckets.
TEST_AUTH_UID = "e701ea32-406b-4020-891c-3cffba3aaa12"
CAP_FILL = 999999  # >> any DEFAULT_RATE_LIMIT_PER_HOUR (50) / user (25) / solo (30) cap

from backend_live_invoke import REG, docker_env, jwt, HIVE  # noqa: E402
from perf_l5_burst import MODEL_BACKED, timed_post  # reuse the LLM denylist + curl helper


def _psql(sql: str):
    return subprocess.run(["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres",
                           "-d", "postgres", "-c", sql],
                          capture_output=True, text=True, timeout=30)


def seed_caps():
    """Fill BOTH rate-limit counters to the cap for the test hive + user so the
    very next call to any gate (hive / per-user / solo) sheds with a 429."""
    now = "now()"
    _psql(f"delete from ai_rate_limits where hive_id='{HIVE}';")
    _psql(f"insert into ai_rate_limits(hive_id,call_count,window_start) "
          f"values('{HIVE}',{CAP_FILL},{now});")
    _psql(f"delete from ai_user_rate_limits where user_id='{TEST_AUTH_UID}';")
    _psql(f"insert into ai_user_rate_limits(user_id,hive_id,call_count,window_start) "
          f"values('{TEST_AUTH_UID}','{HIVE}',{CAP_FILL},{now});")


def clear_caps():
    """Remove the seeded rows so normal operation resumes immediately (otherwise the
    inflated call_count would 429 every real call for the next hour)."""
    _psql("truncate ai_rate_limits;")
    _psql("truncate ai_user_rate_limits;")


def is_model_backed(fn: str, textf) -> bool:
    return textf is not None or fn in MODEL_BACKED


_GATE_RE = re.compile(r"check(?:AI|User|Solo|Classed|Route)RateLimit")


def is_rate_gated(fn: str) -> bool:
    """The quota-shed 429 proof applies ONLY to fns that actually invoke a
    rate-limit gate (checkAIRateLimit / User / Solo / Classed / Route). For an
    UNGATED fn the exhausted-quota probe would just make a real model call (spend
    quota, run long) and never 429 — so we skip it (its R is covered by the burst
    tool's defer-note or by an upstream-gated gateway), never false-probed here."""
    src = os.path.join(ROOT, "supabase", "functions", fn, "index.ts")
    try:
        with open(src, encoding="utf-8") as fh:
            return bool(_GATE_RE.search(fh.read()))
    except OSError:
        return False


def main():
    key = docker_env("SUPABASE_ANON_KEY")
    tok = jwt(key)
    svc = docker_env("SUPABASE_SERVICE_ROLE_KEY")
    if not tok:
        print("  ! could not obtain JWT — is the edge up?"); return 1

    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    passed, fixed, ungated, no_cell, notgate_2xx, skipped_ungated = [], [], [], [], [], []
    seed_caps()
    try:
        for fn, (payload, happy, textf, timeout) in sorted(REG.items()):
            if not is_model_backed(fn, textf):
                continue
            cell = surf.get(f"edge::{fn}")
            if cell is None or not cell.get("lenses", {}).get("R", {}).get("applicable"):
                no_cell.append(fn); continue
            if not is_rate_gated(fn):
                # model-backed but no AI rate-limit gate in its own source — the
                # quota-shed proof does not apply (it would make a real call). Leave
                # its cell as the burst tool set it (pending w/ LLM note); don't probe.
                skipped_ungated.append(fn); continue
            R = cell["lenses"]["R"]
            bearer = svc if happy == "service" else tok
            body = {**payload, "hive_id": HIVE}
            # one call with the quota already exhausted; a fast 429 = the gate fired
            # before any model call. Short cap: the gate answers immediately; only an
            # UNGATED fn would run long (real model call) — we still bound it.
            code, ms = timed_post(fn, body, bearer, key, min(timeout, 30))
            if code == 429:
                R["status"] = "pass"
                R["measured"] = f"quota-exhausted -> {code} graceful shed in {ms:.0f}ms (0 tokens; gate before callAI)"
                R["why"] = ("R degrade-at-scale PROVEN free: with ai_rate_limits/ai_user_rate_limits at cap, the "
                            "fn returns a structured 429 (rateLimitedResponse) BEFORE any model call — the real "
                            "production shed path when a hive exhausts its hourly budget (LOCAL §5 — deterministic, "
                            "necessary-not-sufficient vs prod)")
                R["env"] = "local"
                passed.append((fn, f"{code} {ms:.0f}ms"))
            elif code in (500, 502, 0):
                R["status"] = "fix"
                R["measured"] = f"quota-exhausted -> code={code} ({'crash' if code else 'connection drop'}) — NOT graceful"
                R["why"] = "under exhausted quota the fn crashed/dropped instead of returning a structured 429 — degrade-not-error violated (real R-fix)"
                fixed.append((fn, code))
            elif 200 <= code < 300:
                # the fn did NOT gate on these buckets (deterministic calc, or a
                # different limiter). NOT credited by this method — honest pending.
                R["status"] = "pending"
                R["measured"] = f"quota-exhausted -> {code} (fn did not gate on ai_rate_limits/ai_user_rate_limits — deterministic or other limiter); pending"
                R["why"] = "this fn returned 2xx with the AI quota exhausted -> it is not gated by the hive/user/solo AI limiter (likely deterministic or embedding-local); the quota-shed proof does not apply — pending (not false-passed)"
                notgate_2xx.append((fn, code))
            else:
                R["status"] = "pending"
                R["measured"] = f"quota-exhausted -> code={code} (non-429/2xx/5xx) — pending"
                R["why"] = f"unexpected status {code} under exhausted quota — not a crash, not the 429 shed; pending for review"
                ungated.append((fn, code))
    finally:
        clear_caps()

    # recompute lens aggregates
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

    print("=" * 66)
    print("ARC L — L5-LLM resilience (R lens via quota-shed 429; ZERO tokens)")
    print("=" * 66)
    print(f"  LLM/model-backed fns probed: {len(passed)+len(fixed)+len(notgate_2xx)+len(ungated)}")
    print(f"  R PASS (graceful 429 shed) : {len(passed)}")
    print(f"  R FIX  (5xx/drop under cap): {len(fixed)}")
    print(f"  not-gated 2xx (pending)    : {len(notgate_2xx)}  (deterministic / other limiter — honest pending)")
    print(f"  other non-429 (pending)    : {len(ungated)}")
    print(f"  skipped (no AI gate)       : {len(skipped_ungated)}  (model-backed but ungated — quota-shed N/A; left as-is): {', '.join(skipped_ungated)}")
    if passed:
        print("  graceful quota-shed PASS:")
        for fn, s in passed:
            print(f"    {fn:30} {s}")
    if fixed:
        print("  NOT graceful under quota (real R-fix):")
        for fn, c in fixed:
            print(f"    {fn:30} code={c}")
    if notgate_2xx:
        print("  returned 2xx w/ quota exhausted (not gated by AI limiter):")
        for fn, c in notgate_2xx:
            print(f"    {fn:30} code={c}")
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> R = {results['lens_pass']['R']}/{sum(1 for s in surf.values() if s['lenses'].get('R',{}).get('applicable'))} = {results['lens_pct']['R']}% (floor 85)")
    print(f"  -> {'(dry, not written)' if DRY else 'merged edge:: R cells into perf_scale_results.json'}  · caps cleared")


if __name__ == "__main__":
    sys.exit(main() or 0)
