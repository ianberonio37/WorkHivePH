"""prove_embed_dependency.py - an embedding provider misbehaving, met by the REAL code on index.html's two recall paths
(OWN55 api.jina.ai slow; reusable for any embedding dependency), 2026-10-27.

index.html's companion reaches embeddings two ways: ai-gateway (journal recall, proven procedures and the knowledge base
- three blocks that embed the SAME turn) and voice-semantic-rag (the voice companion's journal recall). This asks both, as
a signed-in worker, healthy and under each fault, with the request header `x-wh-embed-fault` (honoured only on a local
runtime: observability.ts -> model-calls.ts embed_fault -> embedding-chain.ts): the named providers' real request goes to
tools/fake_ai_provider.py (/<mode>/embeddings; "down" is a closed port), so each provider's own timeout, status and shape
check meets the failure.

What it measured before the fix (2026-10-27, primary down + Jina slow): one companion question 34 s against 12.5 s healthy
- two 15 s walks for one turn - and providers_tried saying '=101' (an OS errno read as a status) and '=threw' (a timeout);
voice-semantic-rag asked Jina v2-base for 768 dims to search a vector(384) corpus, so its semantic recall never worked.

Checks, per case:
  the person  - the reply's status and time; the gateway's turn leaves ONE embedding walk; a slow corpus embedder costs at
                most the 4 s budget (3 s for voice-semantic-rag); Jina is never asked by either path (both are strict: the
                corpus's own embedder only); voice-semantic-rag's semantic recall answers when healthy
  the founder - the ai_cost_log row each walk leaves (status, latency, providers_tried with honest outcomes), and the
                console's founder_model_providers read as a platform admin (pabloaguilar) counting them

  python tools/prove_embed_dependency.py            -> embed_dependency_report.json (exit 1 on any failed check)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"   # the LOCAL stack's publishable key (public by design)
FAKE_PORT = 8977
FAKE = f"http://host.docker.internal:{FAKE_PORT}"
OUT = ROOT / "embed_dependency_report.json"
QUESTION = "How do I troubleshoot a pump motor that keeps tripping on overload?"
PRIMARY = "bge-local"   # the local corpus embedder (production's is gemini; the code path is the same)

CASES = {
    "healthy": {},
    "jina-slow": {"jina": "slow"},
    "primary-slow": {PRIMARY: "slow", "jina": "slow"},
    "primary-down": {PRIMARY: "down", "jina": "slow"},
}


def psql(sql: str) -> str:
    p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-Atc", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return p.stdout.strip()


def token(email: str) -> str:
    r = requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password", timeout=20,
                      headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
                      json={"email": email, "password": "test1234"})
    return r.json()["access_token"]


def headers(tok: str, fault: dict) -> dict:
    h = {"Content-Type": "application/json", "apikey": ANON_KEY, "Authorization": f"Bearer {tok}"}
    if fault:
        h["x-wh-embed-fault"] = json.dumps({"fake": FAKE, "providers": fault})
    return h


def rows(fn: str, since: str) -> list:
    out = psql("select coalesce(json_agg(t order by t.created_at), '[]') from (select status, provider, latency_ms, providers_tried, "
               f"created_at from ai_cost_log where fn = '{fn}' and kind = 'embedding' and created_at >= '{since}') t")
    return json.loads(out or "[]")


def gateway(tok: str, hive: str, fault: dict) -> dict:
    since = psql("select now()")
    body = {"agent": "voice-journal", "message": QUESTION, "hive_id": hive,
            "context": {"persona": "zaniah", "page": "hive", "source": "floating-launcher"}}
    t0 = time.time()
    r = requests.post(f"{SUPABASE_URL}/functions/v1/ai-gateway", json=body, headers=headers(tok, fault), timeout=120)
    ms = int((time.time() - t0) * 1000)
    time.sleep(3)   # the cost rows are written after the reply (waitUntil)
    return {"status": r.status_code, "ms": ms, "answered": bool(((r.json() if r.ok else {}).get("data") or {}).get("answer")),
            "walks": rows("ai-gateway", since)}


def vsr(tok: str, fault: dict) -> dict:
    since = psql("select now()")
    t0 = time.time()
    r = requests.post(f"{SUPABASE_URL}/functions/v1/voice-semantic-rag", headers=headers(tok, fault), timeout=60,
                      json={"query_text": "pump overload trip", "limit": 5})
    ms = int((time.time() - t0) * 1000)
    time.sleep(2)
    d = r.json() if r.ok else {}
    d = d.get("data") or d
    return {"status": r.status_code, "ms": ms, "method": d.get("method"), "count": d.get("count"), "walks": rows("voice-semantic-rag", since)}


def tried(walks: list) -> list:
    return [t for w in walks for t in (w.get("providers_tried") or [])]


def main() -> int:
    fake = subprocess.Popen([sys.executable, str(ROOT / "tools" / "fake_ai_provider.py"), "--port", str(FAKE_PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rec = {"ran": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "question": QUESTION, "cases": {}, "checks": {}}
    ck = rec["checks"]
    try:
        time.sleep(1.5)
        psql("update ai_rate_limits set call_count = 0")
        tok = token("bryangarcia@auth.workhiveph.com")
        hive = psql("select hm.hive_id from hive_members hm join worker_profiles wp on wp.auth_uid = hm.auth_uid "
                    "where wp.username = 'bryangarcia' and hm.status = 'active' limit 1")
        started = psql("select now()")
        for name, fault in CASES.items():
            g = gateway(tok, hive, fault)
            v = vsr(tok, fault)
            rec["cases"][name] = {"fault": fault, "gateway": g, "voice_semantic_rag": v}
            print(f"  {name:13s} gateway {g['status']} in {g['ms']} ms, {len(g['walks'])} walk(s) {tried(g['walks'])} "
                  f"{[w['latency_ms'] for w in g['walks']]} ms | voice-rag {v['status']} {v['method']} x{v['count']} in {v['ms']} ms "
                  f"{tried(v['walks'])}")
            every = tried(g["walks"]) + tried(v["walks"])
            ck[f"{name}: the gateway answered"] = g["status"] == 200 and g["answered"]
            ck[f"{name}: one embedding walk for the gateway's turn"] = len(g["walks"]) == 1
            ck[f"{name}: Jina is never asked"] = not any(t.startswith("jina/") for t in every)
            ck[f"{name}: every outcome is a status, timeout or unreachable - never an errno or 'threw'"] = all(
                t.rsplit("=", 1)[1] in ("200", "timeout", "unreachable") for t in every)
            if name in ("healthy", "jina-slow"):
                ck[f"{name}: voice-semantic-rag recalls by meaning"] = v["status"] == 200 and v["method"] == "semantic" and (v["count"] or 0) > 0
            if name == "primary-slow":
                ck["primary-slow: the gateway's walk is cut at its 4 s budget"] = bool(g["walks"]) and g["walks"][0]["latency_ms"] <= 4500
                ck["primary-slow: voice-semantic-rag's walk is cut at 3 s and falls to recency - with the person's recent entries"] = (
                    bool(v["walks"]) and v["walks"][0]["latency_ms"] <= 3500 and v["method"] == "recency" and (v["count"] or 0) > 0)
            if name == "primary-down":
                ck["primary-down: no fallback walk - the corpus embedder's outage costs under a second"] = (
                    bool(g["walks"]) and g["walks"][0]["latency_ms"] < 1000)
                # the recency half had never run (.execute() on a supabase-js builder) - now it answers
                ck["primary-down: voice-semantic-rag answers from the person's recent entries"] = (
                    v["status"] == 200 and v["method"] == "recency" and (v["count"] or 0) > 0)
        # the founder's view of the same window, as the console reads it
        atok = token("pabloaguilar@auth.workhiveph.com")
        r = requests.post(f"{SUPABASE_URL}/rest/v1/rpc/founder_model_providers", timeout=30, json={"p_days": 1},
                          headers={"apikey": ANON_KEY, "Authorization": f"Bearer {atok}", "Content-Type": "application/json"})
        prov = {x["provider"]: x for x in (r.json() if r.ok else [])}
        rec["founder"] = prov.get(PRIMARY)
        p = prov.get(PRIMARY) or {}
        print(f"  founder_model_providers[{PRIMARY}]: asked {p.get('asked')} served {p.get('served')} timed_out {p.get('timed_out')} "
              f"did-not-answer {p.get('threw')} last {p.get('last_failure')}")
        ck["the founder's panel counts the slow walk as timed out and the outage as did-not-answer"] = (
            r.ok and (p.get("timed_out") or 0) >= 1 and (p.get("threw") or 0) >= 1)
        rec["window_started"] = started
    finally:
        fake.terminate()
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8")
    for k, v in ck.items():
        if not v:
            print("  FAIL " + k)
    ok = all(ck.values())
    print(("PASS" if ok else "FAIL") + f" embed-dependency - {sum(ck.values())}/{len(ck)} checks -> {OUT.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
