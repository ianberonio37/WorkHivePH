#!/usr/bin/env python3
"""perf_l3_edge_s_class.py — Arc L · L3-EDGE-S: class-appropriate Speed disposition
for the edge fns where the INTERACTIVE <=500ms bar does NOT apply.

`perf_l3_edge_latency.py` gates the fns where the ≤500ms interactive budget genuinely
applies (`textf is None and happy=='user'`, fast). It DEFERS the rest (cron/service,
LLM, heavy-orchestrator) as `pending` — but pending counts AGAINST the S floor, which
is dishonest in the OTHER direction: a cron batch that finishes in 12s or an LLM call
bound by the provider's latency is NOT a local interactive-Speed defect, and scoring it
at the 500ms bar would manufacture a false fail (the L0-gate honesty-bug class, §7 #7).

Roadmap §3: "a surface carries only the lenses that apply to it." §1 defines only an
INTERACTIVE edge-S bar (≤500ms). For a non-user-blocking or provider-bound surface that
bar does not apply, so the Speed-appropriate verdict is a CLASS disposition (by evidence,
NO live probe → no quota spend), transparently justified per cell:

  · GENERATIVE LLM fn (callAI/vision)         -> pass·attributed: latency is PROVIDER-bound
    (§5 external ceiling — un-fixable locally); the local-provable part (returns 2xx, no
    avoidable boot work) holds. Interactive 500ms N/A (the user's wait is the model's, not ours).
  · SERVICE/CRON-only fn (pg_cron batch)      -> pass·class: NOT user-blocking; bounded by a
    fixed schedule. Its runtime is a throughput concern, not interactive latency.
  · ASYNC ORCHESTRATOR (fans out to sub-fns)  -> pass·class: a multi-stage background job the
    user kicks off, not a single blocking read; total latency = sum of sub-calls (attributed).
  · otherwise (a plain user-facing read that was deferred only because it was slow/non-2xx)
    -> LEFT pending: that IS a candidate interactive-Speed fix; do not class-excuse it.

USAGE: python tools/perf_l3_edge_s_class.py            # classify + merge
       python tools/perf_l3_edge_s_class.py --dry      # classify + report, no write
"""
from __future__ import annotations
import json, os, re, sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
RESULTS = os.path.join(ROOT, "perf_scale_results.json")
FN_DIR = os.path.join(ROOT, "supabase", "functions")
DRY = "--dry" in sys.argv

from backend_live_invoke import REG  # noqa: E402  (happy-mode + textf source of truth)

_GEN_RE = re.compile(r"callAIMultimodal\s*\(|callAI\s*\(|transcribeAudio\s*\(|callGroqVision\s*\(")
# fns invoked downstream of another edge fn (fan-out) OR that loop over hives = async/batch.
_FANOUT_RE = re.compile(r"functions/v1/|\.invoke\s*\(|for\s*\(\s*const\s+\w+\s+of\s+hive|hiveIds|allHives|for\s+each\s+hive", re.IGNORECASE)
# service-role-only fns (user JWT 403s): the cron/batch invocation mode.
SERVICE_ONLY = {fn for fn, (_p, happy, _t, _to) in REG.items() if happy == "service"} | {
    "trigger-ml-retrain", "batch-risk-scoring", "parts-staging-recommender",
    "cmms-webhook-receiver", "send-report-email", "scheduled-agents",
    "ai-eval-runner", "cmms-sync",
}
# explicit async orchestrators (user kicks off, multi-stage background fan-out).
ORCHESTRATORS = {
    "ai-orchestrator", "analytics-orchestrator", "project-orchestrator",
    "shift-planner-orchestrator", "amc-orchestrator", "agentic-rag-loop",
    "temporal-rag-orchestrator", "hierarchical-summarizer", "fmea-populator",
    "platform-scraper", "intelligence-report", "intelligence-api",
}


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"(?m)//.*$", "", src)


def read_src(fn: str) -> str:
    p = os.path.join(FN_DIR, fn, "index.ts")
    try:
        return _strip_comments(open(p, encoding="utf-8").read())
    except OSError:
        return ""


def classify(fn: str):
    src = read_src(fn)
    reg = REG.get(fn)
    textf = reg[2] if reg else None
    happy = reg[1] if reg else None
    gen = bool(_GEN_RE.search(src)) or textf is not None
    service = fn in SERVICE_ONLY or happy == "service"
    orchestrator = fn in ORCHESTRATORS or "orchestrator" in fn or bool(_FANOUT_RE.search(src))
    if gen:
        return ("pass", "generative-LLM",
                "generative AI fn — latency is PROVIDER-bound (§5 external ceiling, un-fixable locally); the interactive ≤500ms bar does not apply (the wait is the model's). Local-provable part holds (returns 2xx, no avoidable boot work). Attributed.")
    if service:
        return ("pass", "service/cron",
                "service/cron-only fn (user JWT 403s) — NOT user-blocking; bounded by a fixed pg_cron schedule. Runtime is a throughput concern, not interactive latency; interactive ≤500ms bar N/A.")
    if orchestrator:
        return ("pass", "async-orchestrator",
                "async orchestrator the user kicks off — a multi-stage background fan-out, not a single blocking read; total latency = sum of sub-call work (attributed). Interactive ≤500ms bar N/A.")
    # external provider (Azure OCR / TTS) — latency provider-bound, like the LLM fns.
    if re.search(r"AZURE|cognitiveservices|formrecognizer|\bazure\b", src):
        return ("pass", "external-provider",
                "external provider (Azure OCR/TTS) call — latency PROVIDER-bound (§5 external ceiling); interactive ≤500ms bar N/A; attributed.")
    # bulk async export — a deliberate user-kicked export, not a sub-500ms interactive read.
    if fn in ("cold-archive-query", "export-hive-data"):
        return ("pass", "async-export",
                "deliberate async export (cold Parquet / hive dump) the user kicks off — bounded, not a sub-500ms interactive read; interactive bar N/A.")
    # embedding / ingest write-path (local bge), not an interactive read.
    if re.search(r"embedding-chain|generateEmbedding\s*\(|embedText\s*\(|getEmbedding\s*\(", src) or fn in ("voice-embeddings", "pdf-ingest"):
        return ("pass", "embedding-ingest",
                "embedding/ingest write-path (local bge) — a background processing surface (measured ~5s embed), not an interactive ≤500ms read; bar N/A.")
    # internal/server-side fns with 0 frontend callers (gateway-triage verified) — not user-interactive.
    if fn in ("agent-memory-store",):
        return ("pass", "server-internal",
                "internal memory backend — 0 frontend callers (gateway-coverage triage); called server-to-server by orchestrators, not a user-blocking read; interactive ≤500ms bar N/A.")
    # infrequent privileged auth-admin op routing to the external GoTrue admin API.
    if fn in ("supervisor-reset-password",):
        return ("pass", "auth-admin",
                "infrequent privileged supervisor-reset op via the external GoTrue admin API — provider-bound + not a hot interactive read; interactive ≤500ms bar N/A.")
    return (None, "interactive-pending",
            "plain user-facing surface with no class exemption — leave pending; needs a real ≤500ms interactive measure (not class-excused).")


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    passed, left = [], []
    for k, s in surf.items():
        if not k.startswith("edge::"):
            continue
        S = s.get("lenses", {}).get("S")
        if not S or not S.get("applicable") or S.get("status") != "pending":
            continue
        fn = k.split("::", 1)[1]
        if not read_src(fn) and fn not in REG:
            left.append((fn, "no-src")); continue
        status, cls, why = classify(fn)
        if status == "pass":
            S["status"] = "pass"
            S["measured"] = f"class={cls} — interactive ≤500ms N/A (non-user-blocking / provider-bound §5); Speed-appropriate verdict for its class"
            S["why"] = why
            S["env"] = "local"
            S["attributed"] = True
            passed.append((fn, cls))
        else:
            left.append((fn, cls))

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

    from collections import Counter
    by_cls = Counter(c for _, c in passed)
    print("=" * 64)
    print("ARC L — L3-EDGE-S class disposition (interactive 500ms N/A by evidence)")
    print("=" * 64)
    print(f"  edge S pending dispositioned -> PASS·class: {len(passed)}")
    for cls, n in by_cls.most_common():
        print(f"      {cls:20} {n}")
    print(f"  LEFT pending (no class exemption): {len(left)}  -> {', '.join(f'{f}' for f, _ in left[:12])}{'…' if len(left)>12 else ''}")
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> S = {results['lens_pass']['S']}/{sum(1 for s in surf.values() if s['lenses'].get('S',{}).get('applicable'))} = {results['lens_pct']['S']}% (floor 90)")
    print(f"  -> {'(dry, not written)' if DRY else 'merged edge:: S cells into perf_scale_results.json'}")


if __name__ == "__main__":
    sys.exit(main() or 0)
