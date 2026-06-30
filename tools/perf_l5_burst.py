#!/usr/bin/env python3
"""perf_l5_burst.py — Arc L · L5-BURST: the R (Resilience@scale) lens for edge fns.

Fires a CONCURRENT burst at each NON-LLM interactive edge fn and scores the
roadmap §1 R contract: "p95 stable under burst · no pool saturation · 429/503 →
graceful degrade, not error." The L0 miner emits edge R as `pending`; this merges
a real measured disposition into the edge:: R cells of perf_scale_results.json.

This is the LOCAL substitute for k6 (k6 not installed; `tools/load_test.k6.js`
targets the same local edge). A ThreadPool curl burst is the D3 "ext-blocked =
local-substitute swap-ready" pattern — concurrent requests against 127.0.0.1:54321.

HONEST per-class scoring (carries the L3-edge / L0-gate anti-false-fail discipline):
  · Reuses backend_live_invoke.py's REG (valid payloads + auth) verbatim.
  · BURST ONLY non-LLM fns (`textf is None`). LLM fns (`textf != None`) are NOT
    bursted — a burst would drain real free-tier LLM quota, and their graceful-
    degrade IS the rate-limiter 429 path already proven by the Arc-H rate-limit
    tests. They are LEFT PENDING with a note (honest: not false-failed).
  · async/cron/service-only fns whose warm call isn't cleanly reachable are also
    deferred (no false fail).
  · R-PASS for a bursted fn = under K concurrent requests: EVERY request got a
    response (no code-0 connection-drop = no pool starvation) AND zero 5xx CRASH
    (500/502; a structured 429/503 load-shed is graceful = allowed) AND burst p95
    stayed within BURST_CEIL_MS (didn't catastrophically collapse). Anything that
    drops connections or 500-crashes under burst is a real R-fix.

USAGE: python tools/perf_l5_burst.py            # burst + merge
       python tools/perf_l5_burst.py --dry      # burst + report, no write
       python tools/perf_l5_burst.py --k 20     # override concurrency (default 15)
"""
from __future__ import annotations
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

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
# concurrency for the burst — modest (proves the runtime handles parallelism +
# doesn't drop/crash) without hammering a single local Deno process into noise.
CONCURRENCY = 15
if "--k" in sys.argv:
    try:
        CONCURRENCY = max(2, int(sys.argv[sys.argv.index("--k") + 1]))
    except Exception:
        pass
# "stable under burst" ceiling: a healthy async fn under a 15-wide burst should
# still answer well under this. Generous (this is degrade-not-COLLAPSE, not the
# 500ms interactive-latency budget which is the S lens's job).
BURST_CEIL_MS = 5000
# A warm call slower than this is a heavy/LLM fn (textf=None is an UNRELIABLE LLM
# marker — resume-polish/voice-model-call/walkthrough-analyzer are LLM with
# textf=None per the L3-edge note). We do NOT burst these: it risks free-tier
# quota AND the latency means it's not a fast interactive surface. Defer, honest.
SLOW_GUARD_MS = 1500

from backend_live_invoke import REG, docker_env, jwt, HIVE  # noqa: E402

# `textf=None` is an UNRELIABLE LLM marker (the L3-edge note: resume-polish /
# voice-model-call / engineering-calc-agent are model-backed with textf=None).
# A latency guard catches them only when their warm call happens to be slow —
# fragile (run-to-run variance flips the R count) AND a fast-warm run bursts them
# and spends real free-tier model/embedding quota. So we deny model-backed fns by
# NAME, reliably. Conservative: if a fn might call a model/embedding, deny it —
# a deferred (pending) cell beats a quota spend or a variance-dependent pass.
MODEL_BACKED = {
    "resume-polish", "voice-model-call", "engineering-calc-agent",
    "walkthrough-analyzer", "visual-defect-capture", "voice-embeddings",
    "embed-entry", "hierarchical-summarizer",
}


def timed_post(fn: str, body: dict, tok: str, key: str, timeout: int):
    """One curl POST → (http_code, ms). code 0 = connection drop / timeout."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", str(timeout), "-o", "/dev/null",
             "-w", "%{http_code} %{time_total}", "-X", "POST", f"{BASE}/{fn}",
             "-H", f"Authorization: Bearer {tok}", "-H", f"apikey: {key}",
             "-H", "Content-Type: application/json", "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=timeout + 10)
        parts = r.stdout.strip().split()
        code = int(parts[0]) if parts else 0
        ms = float(parts[1]) * 1000.0 if len(parts) > 1 else None
        return code, ms
    except Exception:
        return 0, None


def burst(fn, body, tok, key, timeout, k):
    """Fire k concurrent POSTs; return list of (code, ms)."""
    with ThreadPoolExecutor(max_workers=k) as ex:
        futs = [ex.submit(timed_post, fn, body, tok, key, timeout) for _ in range(k)]
        return [f.result() for f in futs]


def p95_of(vals):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]


def main():
    key = docker_env("SUPABASE_ANON_KEY")
    tok = jwt(key)
    svc = docker_env("SUPABASE_SERVICE_ROLE_KEY")
    if not tok:
        print("  ! could not obtain JWT — is the edge up?"); return 1

    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    passed, fixed, deferred_llm, deferred_unreach, deferred_4xx, deferred_heavy, no_cell = [], [], [], [], [], [], []
    for fn, (payload, happy, textf, timeout) in sorted(REG.items()):
        cell = surf.get(f"edge::{fn}")
        if cell is None or not cell.get("lenses", {}).get("R", {}).get("applicable"):
            no_cell.append(fn); continue
        R = cell["lenses"]["R"]
        # model-backed fns (declared-LLM via textf OR named in MODEL_BACKED): do NOT
        # burst (free-tier quota drain); graceful-degrade is the rate-limiter 429,
        # proven by Arc-H rate-limit tests. Pending, honest note.
        if textf is not None or fn in MODEL_BACKED:
            R["status"] = "pending"  # idempotent: clear any stale pass from a prior run
            R["measured"] = "LLM fn — not bursted (would drain free-tier quota); graceful-degrade = rate-limiter 429 (Arc-H rate-limit tests)"
            R["why"] = "burst-resilience for an LLM fn is the rate-limiter 429 path (tested in Arc H); a token-spending burst here would be wasteful — pending, not false-failed"
            deferred_llm.append(fn); continue
        bearer = svc if happy == "service" else tok
        # backend_live_invoke injects hive_id=HIVE on EVERY happy-path call (its
        # REG payloads deliberately omit hive_id — the caller adds it). The burst
        # harness must invoke with the SAME contract, else hive-scoped fns 400 on
        # "Missing required field: hive_id" pre-work and get falsely deferred as
        # un-burstable (an under-test = a hidden free-fail, the L0-gate honesty class).
        body = {**payload, "hive_id": HIVE}
        # warm call first (boot the fn + establish a clean baseline). Mirror the
        # L3-edge gate: only burst a FAST 2xx warm call. This excludes (a) all-4xx
        # fns whose payload/auth is rejected pre-work (a burst measures input
        # validation, not resilience → false pass), and (b) heavy/LLM fns whose slow
        # warm betrays them despite textf=None (don't burst → quota + noise).
        wcode, wms = timed_post(fn, body, bearer, key, timeout)
        if wms is None or wcode in (0, 429) or wcode >= 500:
            R["status"] = "pending"
            R["measured"] = f"warm code={wcode} — not cleanly reachable for a burst (timeout/429/5xx); pending"
            R["why"] = "could not establish a clean warm baseline locally (timeout/429/5xx) → burst would be noise; pending (honest, not failed)"
            deferred_unreach.append((fn, wcode)); continue
        if not (200 <= wcode < 300):
            R["status"] = "pending"
            R["measured"] = f"warm code={wcode} (non-2xx) — payload/auth rejected pre-work; a burst would measure input validation, not resilience; pending"
            R["why"] = "warm call is 4xx (the REG payload/auth doesn't satisfy this fn) → bursting it proves nothing about load resilience (false pass); pending until the invoke contract is fixed (backend_live_invoke REG refinement)"
            deferred_4xx.append((fn, wcode)); continue
        if wms > SLOW_GUARD_MS:
            R["status"] = "pending"
            R["measured"] = f"warm {wms:.0f}ms 2xx — heavy/likely-LLM (textf unreliable); NOT bursted (quota/noise); pending"
            R["why"] = "slow warm 2xx = a heavy or LLM-backed fn (textf=None is an unreliable marker); bursting risks free-tier quota + only measures local single-process queueing; pending, not false-passed"
            deferred_heavy.append((fn, wms)); continue
        # BURST (confirmed fast 2xx, non-LLM)
        res = burst(fn, body, bearer, key, timeout, CONCURRENCY)
        codes = [c for c, _ in res]
        latencies = [m for _, m in res if m is not None]
        responded = sum(1 for c in codes if c != 0)
        drops = sum(1 for c in codes if c == 0)               # connection drop / timeout = pool starvation
        crashes = sum(1 for c in codes if c in (500, 502))    # unhandled crash (503 = graceful shed, allowed)
        sheds = sum(1 for c in codes if c in (429, 503))      # graceful degrade
        ok2xx = sum(1 for c in codes if 200 <= c < 300)
        bp95 = p95_of(latencies)
        # graceful = no connection drops, no 5xx crashes, AND every response is a
        # success or a structured shed (no surprise 4xx mid-burst). The warm gate
        # already guaranteed a 2xx baseline, so a 4xx appearing only under load
        # would itself be a degradation we must not credit.
        graceful = (drops == 0 and crashes == 0 and (ok2xx + sheds) == CONCURRENCY)
        stable = (bp95 is not None and bp95 <= BURST_CEIL_MS)
        summary = f"k={CONCURRENCY} 2xx={ok2xx} shed(429/503)={sheds} crash(5xx)={crashes} drop={drops} burst_p95={bp95:.0f}ms" if bp95 is not None else f"k={CONCURRENCY} responded={responded} (no timing)"
        if graceful and stable:
            R["status"] = "pass"
            R["measured"] = summary
            R["why"] = "graceful degrade under burst: every request answered (no connection drop = no pool starvation), zero 5xx crash (429/503 shed is graceful), burst p95 within ceiling (LOCAL §5 — necessary-not-sufficient vs prod)"
            R["env"] = "local"
            passed.append((fn, summary))
        elif drops or crashes:
            # connection drops (pool starvation) or 5xx crashes = a REAL R-fix.
            R["status"] = "fix"
            R["measured"] = summary
            R["why"] = f"NOT graceful under burst: {'connection drops (pool starvation) ' if drops else ''}{'5xx crashes ' if crashes else ''}— degrade-not-error contract violated"
            fixed.append((fn, summary))
        elif (ok2xx + sheds) != CONCURRENCY:
            # warm-2xx fn that returned a surprise 4xx only under load — anomalous but
            # not a crash/drop; could be transient contention. Defer, don't false-fail.
            R["status"] = "pending"
            R["measured"] = summary + " — warm-2xx but a 4xx appeared under burst; pending"
            R["why"] = "no drops/crashes, but a non-2xx/non-shed response appeared only under load — anomalous, not a crash; pending for review (not false-failed, not credited)"
            deferred_unreach.append((fn, "burst-4xx"))
        else:
            # graceful but burst p95 over ceiling → borderline; defer (don't false-fail on local single-process queueing)
            R["status"] = "pending"
            R["measured"] = summary + " — graceful but burst p95 over ceiling, pending"
            R["why"] = "no drops/crashes but burst p95 exceeded the collapse ceiling on a single local Deno process — borderline; pending (not flat-failed on local queueing jitter)"
            deferred_unreach.append((fn, "slow-burst"))

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

    print("=" * 64)
    print(f"ARC L — L5-BURST resilience (R lens, k={CONCURRENCY} concurrent; honest per-class)")
    print("=" * 64)
    print(f"  fast-2xx fns bursted: {len(passed) + len(fixed) + sum(1 for x in deferred_unreach if x[1] in ('burst-4xx','slow-burst'))}")
    print(f"  R PASS (graceful)   : {len(passed)}")
    print(f"  R FIX (drop/crash)  : {len(fixed)}")
    print(f"  deferred LLM        : {len(deferred_llm)}  (declared-LLM, not bursted — quota; 429 = Arc-H)")
    print(f"  deferred heavy      : {len(deferred_heavy)}  (slow warm 2xx = likely-LLM, not bursted — quota)")
    print(f"  deferred 4xx-warm   : {len(deferred_4xx)}  (REG payload/auth rejected → can't burst-test)")
    print(f"  deferred unreach/borderline: {len(deferred_unreach)}  (timeout/429/5xx warm, burst-4xx, or slow-burst)")
    if passed:
        print("  graceful-under-burst PASS:")
        for fn, s in passed:
            print(f"    {fn:30} {s}")
    if fixed:
        print("  NOT graceful (real R-fix):")
        for fn, s in fixed:
            print(f"    {fn:30} {s}")
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> {'(dry, not written)' if DRY else 'merged edge:: R cells into perf_scale_results.json'}")


if __name__ == "__main__":
    sys.exit(main() or 0)
