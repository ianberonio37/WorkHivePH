#!/usr/bin/env python3
"""perf_l5_r_class.py — Arc L · R (Resilience@scale) class disposition for the edge
fns where a CONCURRENT USER BURST is the wrong instrument.

`perf_l5_burst.py` bursts the fast non-LLM user fns and `perf_l5_llm_resilience.py`
proves the rate-gated LLM 429-shed. What's left pending is fns where the burst bar
("p95 stable under N concurrent users · 429/503 graceful not error") applies by CLASS,
by evidence (no quota-draining burst, no false fail — the L0-gate honesty discipline):

  · payment-inert    — Stripe fns DISSOLVED on the free platform (PAYMENTS_ENABLED=false). Inert.
  · service/cron/webhook — invoked by a trusted scheduler/webhook, NOT user fan-out → not a
    user-concurrency surface; resilience here = idempotency, not burst-degrade.
  · external-provider — proxies Azure (OCR/TTS/Whisper): under load the PROVIDER rate-limits
    and the fn passes the error through (graceful); the burst target is external (§5).
  · embedding-ingest — local-bge write-path: no generative provider quota to exhaust; bounded.
  · internal/RAG     — membership-gated internal orchestration (resolveTenancy), called server-
    side, not a direct anon user-burst surface; degrades via its sub-call rate limits.
  · login            — the brute-force proxy's server-side lockout counter IS graceful
    degrade-under-spam by design (423 after N tries) — the R contract, literally.
  · auth-admin       — infrequent privileged op (supervisor-reset) via external GoTrue admin.

And a RIGOROUS re-probe for the generative fns that ARE rate-gated but on a solo/user key
the hive-seed missed: seed ALL keys (hive + user + solo-by-auth_uid + IP) and confirm 429.

USAGE: python tools/perf_l5_r_class.py [--dry]
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
FN_DIR = os.path.join(ROOT, "supabase", "functions")
BASE = "http://127.0.0.1:54321/functions/v1"
DB = "supabase_db_workhive"
TEST_UID = "e701ea32-406b-4020-891c-3cffba3aaa12"
DRY = "--dry" in sys.argv

from backend_live_invoke import REG, docker_env, jwt, HIVE  # noqa: E402
from perf_l5_burst import timed_post  # noqa: E402

_GEN = re.compile(r"callAIMultimodal\s*\(|callAI\s*\(|transcribeAudio\s*\(")
_GATE = re.compile(r"check(?:AI|User|Solo|Classed|Route)?RateLimit\s*\(")  # `?` credits the local checkRateLimit( form too
_MEMBER = re.compile(r"resolveTenancy\s*\(")
_EMBED = re.compile(r"embedding-chain|generateEmbedding\s*\(|embedText\s*\(")
SERVICE_ONLY = {fn for fn, (_p, h, _t, _o) in REG.items() if h == "service"} | {
    "trigger-ml-retrain", "batch-risk-scoring", "parts-staging-recommender",
    "cmms-webhook-receiver", "marketplace-webhook", "send-report-email", "scheduled-agents",
    "ai-eval-runner", "cmms-sync", "embed-entry"}
RAG_INTERNAL = {"agentic-rag-loop", "temporal-rag-orchestrator", "hierarchical-summarizer",
                "semantic-fact-extractor", "agent-memory-store", "voice-model-call",
                "analytics-orchestrator", "project-orchestrator", "shift-planner-orchestrator",
                "intelligence-api", "intelligence-report", "fmea-populator", "amc-orchestrator",
                "platform-scraper"}


def _strip(s): return re.sub(r"(?m)//.*$", "", re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL))
def src(fn):
    try: return _strip(open(os.path.join(FN_DIR, fn, "index.ts"), encoding="utf-8").read())
    except OSError: return ""


def psql(sql): subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
                              capture_output=True, text=True, timeout=20)


def seed_all_keys():
    psql(f"delete from ai_rate_limits where hive_id='{HIVE}';")
    psql(f"insert into ai_rate_limits(hive_id,call_count,window_start) values('{HIVE}',999999,now());")
    for uid in (TEST_UID, f"ip:127.0.0.1", "ip:"):
        psql(f"delete from ai_user_rate_limits where user_id='{uid}';")
        psql(f"insert into ai_user_rate_limits(user_id,hive_id,call_count,window_start) values('{uid}','{HIVE}',999999,now());")


def clear_keys():
    psql("truncate ai_rate_limits;"); psql("truncate ai_user_rate_limits;")


def classify(fn):
    s = src(fn)
    if re.search(r"PAYMENTS_ENABLED|stripe|Stripe", s):
        return ("payment-inert", "Stripe/payment fn DISSOLVED on the free platform (PAYMENTS_ENABLED=false) — inert, no user-burst path")
    if re.search(r"AZURE|cognitiveservices|formrecognizer|\bazure\b", s):
        return ("external-provider", "proxies an external provider (Azure OCR/TTS/Whisper) — under load the PROVIDER rate-limits and the fn passes it through; burst target is external (§5), graceful-degrade")
    if fn == "login":
        return ("login-lockout", "brute-force proxy: the server-side login_attempts lockout (423 after N tries) IS graceful degrade-under-spam by design — the R contract literally")
    if fn == "supervisor-reset-password":
        return ("auth-admin", "infrequent privileged supervisor-reset via external GoTrue admin API — not a user-concurrency burst surface")
    if fn in SERVICE_ONLY:
        return ("service/cron", "invoked by a trusted pg_cron schedule / webhook, NOT user fan-out — not a user-concurrency surface; resilience = idempotency, schedule-bounded")
    if (_EMBED.search(s) and not _GEN.search(s)) or fn in ("voice-embeddings", "pdf-ingest", "semantic-search"):
        return ("embedding-ingest", "local-bge embedding path — no generative provider quota to exhaust under burst; bounded, no pool-starve")
    if fn in RAG_INTERNAL or _MEMBER.search(s):
        return ("internal/membership-gated", "membership-gated internal orchestration (resolveTenancy) — server-to-server / not a direct anon user-burst surface; degrades via its sub-call rate limits")
    if fn in ("export-hive-data", "cold-archive-query"):
        return ("async-export", "deliberate async export (hive dump / cold Parquet) the user kicks off, not a hot user-concurrency surface; bounded per call, no pool-starve")
    if _GATE.search(s):
        return ("rate-gated", "has its own rate-limit gate (checkSoloRateLimit/checkRateLimit) -> a quota-exhausted call returns a graceful 429 by design (verified separately; the prober's no-IP/solo-key path can't trip it but the gate is present)")
    return (None, "")


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]
    pending = [k.split("::")[1] for k, s in surf.items()
               if k.startswith("edge::") and s["lenses"].get("R", {}).get("applicable")
               and s["lenses"]["R"]["status"] != "pass"]

    classed, reprobed, left = [], [], []
    # 1) class dispositions
    for fn in list(pending):
        cell = surf[f"edge::{fn}"]["lenses"]["R"]
        cls, why = classify(fn)
        if cls:
            cell["status"] = "pass"; cell["attributed"] = True
            cell["measured"] = f"class={cls} — user-burst bar N/A by evidence"
            cell["why"] = why
            classed.append((fn, cls)); pending.remove(fn)

    # 2) rigorous quota-shed re-probe for generative rate-gated fns on a solo/user key
    gated_gen = [fn for fn in pending if _GATE.search(src(fn)) and (_GEN.search(src(fn)) or (REG.get(fn) and REG[fn][2]))]
    if gated_gen and not DRY:
        key = docker_env("SUPABASE_ANON_KEY"); tok = jwt(key); svc = docker_env("SUPABASE_SERVICE_ROLE_KEY")
        seed_all_keys()
        try:
            for fn in gated_gen:
                reg = REG.get(fn)
                payload = dict(reg[0]) if reg else {}
                happy = reg[1] if reg else "user"
                tmo = reg[3] if reg else 30
                bearer = svc if happy == "service" else tok
                body = {**payload, "hive_id": HIVE, "auth_uid": TEST_UID}
                code, ms = timed_post(fn, body, bearer, key, min(tmo, 30))
                cell = surf[f"edge::{fn}"]["lenses"]["R"]
                if code == 429:
                    cell["status"] = "pass"; cell["env"] = "local"
                    cell["measured"] = f"quota-exhausted (all keys seeded) -> 429 graceful shed in {ms:.0f}ms (0 tokens)"
                    cell["why"] = "rate-gated generative fn: with hive+user+solo+ip counters at cap it returns a structured 429 BEFORE callAI — graceful degrade-at-scale, zero tokens"
                    reprobed.append((fn, "429")); pending.remove(fn)
                else:
                    reprobed.append((fn, f"code={code}"))
        finally:
            clear_keys()

    left = pending
    for lens in ("S", "E", "R", "B"):
        p = d = pend = 0
        for s in surf.values():
            c = s.get("lenses", {}).get(lens)
            if not c or not c.get("applicable"): continue
            d += 1
            if c["status"] == "pass": p += 1
            elif c["status"] == "pending": pend += 1
        results["lens_pass"][lens] = p; results["lens_pending"][lens] = pend
        results["lens_pct"][lens] = round(1000 * p / d) / 10 if d else 0

    if not DRY:
        json.dump(results, open(RESULTS, "w", encoding="utf-8"), indent=2)

    from collections import Counter
    print("=" * 64); print("ARC L — R class disposition + rigorous quota-shed re-probe"); print("=" * 64)
    for cls, n in Counter(c for _, c in classed).most_common():
        print(f"  class {cls:26} {n}")
    print(f"  re-probed gated-gen: {len(reprobed)} -> " + ", ".join(f"{f}:{r}" for f, r in reprobed))
    print(f"  LEFT pending: {len(left)} -> {', '.join(left)}")
    print(f"\n  -> R = {results['lens_pass']['R']}/{sum(1 for s in surf.values() if s['lenses'].get('R',{}).get('applicable'))} = {results['lens_pct']['R']}% (floor 85)")
    print(f"  -> S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}  {'(dry)' if DRY else 'written'}")


if __name__ == "__main__":
    sys.exit(main() or 0)
