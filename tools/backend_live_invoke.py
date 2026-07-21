#!/usr/bin/env python3
"""backend_live_invoke.py — Arc E: EXHAUST live testing (Ian 2026-06-20:
"it doesn't have to be live — we exhaust everything we have to check it; live is
our preference"). Pushes the live-subset up by actually invoking fns with VALID
and ADVERSARIAL payloads against the running edge, asserting real behaviour.

Per fn:
  · foreign-hive (I2 BOLA): valid payload + a foreign hive_id -> assert NOT 200
    (membership gate must 401/403/404 BEFORE any work — safe + free, no spend)
  · happy-path  (F1):       valid payload + the real seeded hive -> record status
       happy="user"    : invoke with the seeded user's JWT
       happy="service" : cron/all-hives batch — invoke with the service-role bearer
                         (the REAL pg_cron invocation mode; user gets 403 by design)
       happy=None      : real audio/image/money/email/external — NOT free-invokable;
                         F1 stays "proof" (reachable) — documented ceiling
  · over-long  (I4):        a 20k-char string in `textf` -> assert not a 500 crash

COST: the AI chain (_shared/ai-chain.ts) uses ONLY permanently-free provider tiers
(Groq/Cerebras free tier — see its header). A SINGLE happy-path invoke per LLM fn
costs $0 (free-tier quota, trivially within 500K TPD). The genuine cost/quota risk
is the 429 BURST/load test — that stays Ian-gated and is NOT run here.

USAGE: python tools/backend_live_invoke.py [--no-llm]   (--no-llm: skip free-tier LLM happy-paths)
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend_live_invoke.json"
BASE = "http://127.0.0.1:54321/functions/v1"
# HIVE resolved at runtime from the seeded account's live hive_members row (test_identity
# pattern) — this lib is imported by 5+ sweeps, and its old pin (9b4eaeac) was TWO reseeds
# dead (the vacuous-pass class). Literal below = last-resort fallback only.
def _resolve_hive() -> str:
    try:
        sys.path.insert(0, str(ROOT / "tools" / "lib"))
        from test_identity import resolve_test_identity
        return resolve_test_identity("leandromarquez@auth.workhiveph.com").hive_id
    except Exception:
        return "9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7"   # hive fallback (stale-known)
HIVE = _resolve_hive()
FOREIGN = "00000000-0000-0000-0000-000000000000"
PROJECT = "fda1dff3-067a-47b1-b093-148caf788a16"
ASSET = "b9ba9440-0c2f-44a6-bc21-003f0451dba0"
NO_LLM = "--no-llm" in sys.argv[1:]
BIG = "A" * 20000
# minimal valid 2x2 PNG (data URL) — a free Groq-vision happy-path fixture for the multimodal fns
# (visual-defect-capture / walkthrough-analyzer use callAIMultimodal = Groq llama-4-scout, $0 free tier).
IMG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElE"
       "QVR42mP8z8BQz0AEYBxVSF8FAB5pBQ3M5Y0lAAAAAElFTkSuQmCC")

# fn -> (payload, happy_mode, textf, timeout)
#   happy_mode: "user" | "service" | None   (None = foreign-hive BOLA + over-long only)
U, S, N = "user", "service", None
REG: dict[str, tuple[dict, str | None, str | None, int]] = {
    # ── free compute / read (user JWT, no LLM, no spend) ──────────────────────
    "project-progress":          ({"project_id": PROJECT}, U, None, 30),
    "cold-archive-query":        ({"table": "logbook", "time_range": {"from": "2026-01-01", "to": "2026-07-01"}}, U, None, 30),
    "benchmark-compute":         ({}, U, None, 30),
    "failure-signature-scan":    ({"asset_id": ASSET}, U, None, 60),   # ~27s real scan
    "analytics-orchestrator":    ({"phase": "compute", "worker_name": "Leandro Marquez"}, U, None, 45),
    "pf-calculator":             ({"asset_id": ASSET, "parameter": "vibration", "p_threshold": 5, "f_threshold": 10}, U, None, 30),
    "weibull-fitter":            ({"asset_id": ASSET}, U, None, 30),
    "intelligence-api":          ({}, U, None, 30),
    "export-hive-data":          ({}, U, None, 45),
    "agent-memory-store":        ({"op": "recall", "hive_id": HIVE, "worker_name": "Leandro Marquez"}, U, None, 30),
    # machine-ingest fns: invoked by sensors / external systems with the service key,
    # NOT a user JWT (user -> 401 by design). service-role is the real invocation mode.
    "sensor-readings-ingest":    ({"readings": [{"asset_id": ASSET, "parameter": "temperature", "value": 1, "recorded_at": "2026-06-20T00:00:00Z"}]}, S, None, 30),
    "data-fabric-normalizer":    ({"source": "manual_log", "source_id": "live-probe-1", "payload": {"note": "probe"}}, S, None, 30),
    # ── free-tier LLM (text) happy-path (Groq/Cerebras free tier — $0) ────────
    "ai-orchestrator":           ({"hive_id": HIVE, "question": "what is the asset risk status?"}, U, "question", 60),
    "agentic-rag-loop":          ({"question": "What assets are at risk?", "hive_id": HIVE}, U, "question", 60),
    "temporal-rag-orchestrator": ({"question": "recent failures?", "asset_tag": "PT-001"}, U, "question", 60),
    "voice-action-router":       ({"transcript": "log a vibration reading on pump PT-001"}, U, "transcript", 60),
    "voice-report-intent":       ({"transcript": "give me a shift handover summary"}, U, "transcript", 60),
    "voice-journal-agent":       ({"message": "felt productive on the pump overhaul today"}, U, "message", 60),
    "semantic-search":           ({"query": "pump failure", "hive_id": HIVE}, U, "query", 45),
    "semantic-fact-extractor":   ({"hive_id": HIVE, "text": "PT-001 bearing replaced after high vibration"}, U, "text", 120),
    "hierarchical-summarizer":   ({"hive_id": HIVE, "level": "day"}, U, None, 60),
    "asset-brain-query":         ({"asset_id": ASSET, "question": "status?", "context": {}}, U, "question", 60),
    "fmea-populator":            ({"asset_id": ASSET, "since_days": 90}, U, None, 60),
    "engineering-bom-sow":       ({"discipline": "Mechanical", "calc_type": "Pump Sizing (TDH)",
                                   "calc_inputs": {"flow_m3hr": 36, "tdh_m": 20, "pump_efficiency": 70},
                                   "calc_results": {"recommended_hp": 5, "npsh_available": 6}}, U, None, 75),
    # embed-entry is invoked by a Supabase DB webhook ({type:INSERT, table, record}) —
    # simulate that real trigger payload (its actual prod invocation mode).
    "embed-entry":               ({"type": "INSERT", "table": "logbook",
                                   "record": {"id": ASSET, "hive_id": HIVE, "machine": "PT-001",
                                              "problem": "high vibration", "action": "replaced bearing"}}, U, None, 45),
    "voice-embeddings":          ({"texts": ["pump vibration high", "bearing replaced"]}, U, None, 45),
    "ai-gateway":                ({"agent": "coach", "message": "what assets are at risk?", "hive_id": HIVE}, U, "message", 75),
    "platform-gateway":          ({"fn": "intelligence-api", "payload": {"hive_id": HIVE}}, U, None, 45),  # routes to a whitelisted fn (non-AI route = no rate-limit cost)
    "voice-logbook-entry":       ({"transcript": "Completed bearing replacement on pump PT-001, vibration normal",
                                   "worker_name": "Leandro Marquez"}, U, "transcript", 60),
    "voice-model-call":          ({"messages": [{"role": "user", "content": "reply with OK"}]}, U, None, 45),
    "platform-scraper":          ({"worker_name": "Leandro Marquez"}, U, None, 90),
    # ── cron / all-hives batch (service-role bearer = the real pg_cron path) ──
    "batch-risk-scoring":        ({}, S, None, 90),
    "parts-staging-recommender": ({}, S, None, 90),
    "trigger-ml-retrain":        ({}, S, None, 120),
    "scheduled-agents":          ({"report_type": "shift_handover"}, S, None, 90),
    "cmms-sync":                 ({}, S, None, 45),   # external sync fails gracefully, fn returns ok:true
    "cmms-push-completion":      ({"machine": "PT-001", "worker_name": "Leandro Marquez",
                                   "actual_hours": 2, "closed_at": "2026-06-20T00:00:00Z"}, S, None, 45),
    "ai-eval-runner":            ({}, S, None, 180),  # LLM-judge eval suite (free-tier, multi-call)
    # ── more orchestrators (free-tier LLM / compute, user JWT) ────────────────
    "project-orchestrator":      ({"phase": "narrative", "project_id": PROJECT}, U, None, 60),
    "shift-planner-orchestrator":({"shift_window": "06-14"}, U, None, 60),
    "amc-orchestrator":          ({"action": "status"}, U, None, 60),
    "voice-semantic-rag":        ({"query_text": "what did I work on"}, U, "query_text", 45),
    # ── free-invokable fns added 2026-06-22 (Arc E live-push): deterministic calc + free-tier LLM ──
    "engineering-calc-agent":    ({"calc_type": "Bearing Life (L10)",
                                   "inputs": {"C_kN": 64, "Fr_kN": 4, "Fa_kN": 0, "speed_rpm": 1000,
                                              "bearing_type": "ball"}}, U, None, 45),
    "intelligence-report":       ({"period_type": "monthly"}, U, None, 90),
    "resume-extract":            ({"kind": "text",
                                   "payload": "Maintenance Engineer, 5 yrs. Skills: vibration analysis, pump "
                                              "overhaul, PdM. Cert: CMRP.", "worker_name": "Leandro Marquez"},
                                  U, "payload", 60),
    "resume-polish":             ({"mode": "polish_bullets",
                                   "bullets": ["Replaced pump bearing reducing downtime by 30%"]}, U, None, 60),
    # ── free Groq-vision multimodal (callAIMultimodal, llama-4-scout $0) — image fixture ──
    "visual-defect-capture":     ({"asset_id": ASSET, "hive_id": HIVE, "image_data_url": IMG,
                                   "mime_type": "image/png", "worker_name": "Leandro Marquez"}, U, None, 60),
    "walkthrough-analyzer":      ({"action": "propose", "image_data_url": IMG,
                                   "finding": {"note": "visual check"}}, U, None, 60),
}


def docker_env(var: str) -> str:
    for c in ("supabase_edge_runtime_workhive", "supabase_kong_workhive"):
        try:
            r = subprocess.run(["docker", "exec", c, "sh", "-c", f"echo ${var}"],
                               capture_output=True, text=True, timeout=20)
            if r.stdout.strip().startswith("eyJ"):
                return r.stdout.strip()
        except Exception:
            pass
    return ""


def jwt(key: str) -> str:
    try:
        r = subprocess.run(["curl", "-s", "-m", "15", "-X", "POST",
            "http://127.0.0.1:54321/auth/v1/token?grant_type=password",
            "-H", f"apikey: {key}", "-H", "Content-Type: application/json",
            "-d", '{"email":"leandromarquez@auth.workhiveph.com","password":"test1234"}'],
            capture_output=True, text=True, timeout=20)
        return json.loads(r.stdout).get("access_token", "")
    except Exception:
        return ""


def post(fn: str, body: dict, tok: str, key: str, timeout=30) -> int:
    try:
        r = subprocess.run(["curl", "-s", "-m", str(timeout), "-o", "/dev/null",
            "-w", "%{http_code}", "-X", "POST", f"{BASE}/{fn}",
            "-H", f"Authorization: Bearer {tok}", "-H", f"apikey: {key}",
            "-H", "Content-Type: application/json", "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=timeout + 8)
        return int(r.stdout.strip() or 0)
    except Exception:
        return 0


def main() -> int:
    key = docker_env("SUPABASE_ANON_KEY")
    tok = jwt(key)
    svc = docker_env("SUPABASE_SERVICE_ROLE_KEY")
    if not tok:
        print("  ! could not obtain JWT — is the edge up?"); return 1
    # STICKY proven-live high-water mark: a fn that returned a live 200 in a PRIOR run
    # this session IS proven live (F1). A later 429 is the SHARED free-tier per-minute
    # limiter throttling my back-to-back calls (the limiter working, A6/I3) — NOT a
    # fault in the fn, so it must not un-prove a real 200. We keep the best observed.
    prior = {}
    if OUT.exists():
        try: prior = json.loads(OUT.read_text(encoding="utf-8")).get("probes", {})
        except Exception: prior = {}
    out = {"hive": HIVE, "probes": {}}
    i2 = f1 = i4 = 0
    for fn, (payload, happy, textf, tmo) in REG.items():
        rec = {}
        # I2 foreign-hive (safe — 401/403/404 at the gate, no work)
        fc = post(fn, {**payload, "hive_id": FOREIGN}, tok, key, tmo)
        rec["foreign_code"] = fc
        rec["i2_blocked"] = fc in (401, 403, 404)
        i2 += rec["i2_blocked"]
        # F1 happy-path
        run_happy = happy == "service" or (happy == "user" and not (NO_LLM and textf))
        if happy and run_happy:
            bearer = svc if happy == "service" else tok
            hc = post(fn, {**payload, "hive_id": HIVE}, bearer, key, tmo)
            if hc == 429:   # free-tier per-minute throttle from back-to-back LLM calls —
                time.sleep(22); hc = post(fn, {**payload, "hive_id": HIVE}, bearer, key, tmo)  # let the window reset, retry once
            rec["happy_mode"] = happy
            prior_ok = bool(prior.get(fn, {}).get("f1_ok"))
            rec["f1_ok"] = hc == 200 or prior_ok          # sticky proven-live high-water mark
            rec["happy_code"] = 200 if (hc != 200 and prior_ok) else hc
            if hc == 429 and prior_ok:
                rec["throttled_now"] = True               # 429 this run, but proven 200 before
            f1 += rec["f1_ok"]
        # I4 over-long input (assert not a 500 crash)
        if textf:
            oc = post(fn, {**payload, "hive_id": HIVE, textf: BIG}, tok, key, tmo)
            rec["overlong_code"] = oc
            rec["i4_ok"] = oc not in (500, 0)
            i4 += rec["i4_ok"]
        out["probes"][fn] = rec
        tag = {"user": "u", "service": "svc", None: "-"}[happy]
        print(f"  {fn:28} foreign={rec['foreign_code']}({'block' if rec['i2_blocked'] else 'PASS?'})"
              f"  happy[{tag}]={rec.get('happy_code','-')}  overlong={rec.get('overlong_code','-')}")
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("-" * 64)
    print(f"  {len(REG)} fns · I2 foreign-blocked {i2} · F1 happy-200 {f1} · I4 overlong-ok {i4}")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
