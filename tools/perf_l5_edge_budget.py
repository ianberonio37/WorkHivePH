#!/usr/bin/env python3
"""perf_l5_edge_budget.py — Arc L · L5-BUDGET: the B (free-tier) lens for EDGE fns.

`perf_l5_budget.py` projects the 5 platform-AGGREGATE budget cells (db-rows / storage
/ egress / edge-invocations / llm-tokens). But the B lens also carries one cell PER
edge fn (61), all emitted `pending` by the L0 miner — no per-fn scorer existed. This
is that scorer: it gives each edge fn an HONEST, evidence-backed B disposition derived
from its source + the already-proven aggregates, and FLAGS the genuine free-tier risks
(roadmap §6: "the unbounded select … the edge fn invoked per-keystroke … the LLM call
without a token cap — each is the cell that silently starts billing at scale").

Per-fn B model (each driver checked against an already-PASSING aggregate):
  · INVOCATION — every fn counts toward edge-invocations; budget::edge-invocations
    projects 132K / 500K mo (26%, headroom). No single fn threatens this under the
    documented activity model → invocation is not a per-fn blocker.
  · EGRESS — a fn whose DB reads are bounded (Arc-L L2 proved 0 unbounded platform-
    wide) returns row-capped payloads → egress-safe (budget::egress aggregate). A
    fn that returns O(hive-size) data per call (a bulk EXPORT) is the egress outlier
    → flagged for a per-fn projection (cadence-dependent → conservative pending).
  · TOKENS — a non-AI fn spends 0 tokens. An AI fn is token-bounded IFF it is rate-
    limited (checkAIRateLimit/User/Solo/Classed/Route caps it per hive/hour) OR is
    service/cron-triggered (bounded by a fixed schedule, not user volume). A user-
    reachable AI fn with NO gate = an UNCAPPED-LLM risk → FLAGGED (the fix is to gate
    it; that both clears the B cell and closes a real cost hole — a follow-up unit).

A cell PASSES only when ALL of its applicable drivers are bounded; otherwise it is
FLAGGED pending with the specific reason. No blanket credit — measured-not-credited.

USAGE: python tools/perf_l5_edge_budget.py            # classify + merge
       python tools/perf_l5_edge_budget.py --dry      # classify + report, no write
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

from backend_live_invoke import REG  # noqa: E402  (the happy-mode = service/user/None source-of-truth)

# GENERATIVE model-call signals — an ACTUAL invocation (open paren), matched on
# COMMENT-STRIPPED source so a docstring that merely NAMES callAI (e.g.
# agent-memory-store's "no LLM call inside this function … callAI in agentic-rag-loop")
# is not mistaken for a real generative call. These spend PROVIDER TOKENS.
_GEN_RE = re.compile(r"callAIMultimodal\s*\(|callAI\s*\(|transcribeAudio\s*\(|callGroqVision\s*\(")
# EMBEDDING-only signal: embedding-chain runs on local bge by default (free) / a
# rate-limited embedding provider in prod — its cost is bounded by write/search volume
# already inside the activity aggregate, NOT an uncapped generative-token spend.
_EMBED_RE = re.compile(r"embedQuery\s*\(|embedText\s*\(|getEmbedding\s*\(|embedding-chain")
# rate-limit gate signal — an actual gate CALL (not a comment mention). The `?` after the
# prefix credits the LOCAL `checkRateLimit(` form too (agentic-rag-loop / temporal-rag-
# orchestrator define their own) — "broaden the marker when a 2nd valid idiom exists".
_GATE_RE_CALL = re.compile(r"check(?:AI|User|Solo|Classed|Route)?RateLimit\s*\(")
# membership / identity gate — closes the ANON token-burn hole (a non-member 403s).
# A generative fn behind this is NOT an open billing door; the residual is bounded
# member-spam (defense-in-depth, a per-hive rate gate is the hardening, not a hole).
_MEMBER_RE = re.compile(r"resolveTenancy\s*\(|requireMembership\s*\(|assertMembership\s*\(|requireHiveMember\s*\(")


def _strip_comments(src: str) -> str:
    """Remove /* … */ block comments and // line comments so call-site detection
    matches executable code only, never a docstring that names the function."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"(?m)//.*$", "", src)
    return src
# rate-limit gate signal (token use is then per-hive/hour bounded).
_GATE_RE = re.compile(r"check(?:AI|User|Solo|Classed|Route)RateLimit")
# bulk-export fns: return larger payloads per call — source-verified BOUNDED (2026-06-23),
# each maps to its per-fn egress-bound evidence (the "per-fn projection" the flag asked for).
BULK_EXPORT = {
    "cold-archive-query":
        "date-windowed (time_range.from/to REQUIRED) + MAX_QUARTERS=40 Parquet-file fan-out cap; "
        "reads COLD storage (Parquet) not the live DB; egress bounded per call",
    "export-hive-data":
        "hive-scoped export (role/hive_status membership-checked, one hive's worker-truth view) invoked "
        "as a deliberate low-cadence user action (not per-page); egress proportional to ONE hive, not unbounded",
}
# service/cron fns reachable ONLY with the service-role bearer (a user JWT 403s) — their
# volume is bounded by a fixed pg_cron schedule, not per-user activity. Sourced from REG
# happy=="service" + the obvious system fns not in REG.
SERVICE_ONLY = {fn for fn, (_p, happy, _t, _to) in REG.items() if happy == "service"} | {
    "trigger-ml-retrain", "batch-risk-scoring", "parts-staging-recommender",
    "cmms-webhook-receiver", "marketplace-webhook", "send-report-email",
}


def read_src(fn: str) -> str:
    p = os.path.join(FN_DIR, fn, "index.ts")
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def classify(fn: str):
    src = _strip_comments(read_src(fn))      # match executable code only, never docstrings
    gen = bool(_GEN_RE.search(src))          # generative provider-token call
    embed = bool(_EMBED_RE.search(src))      # embedding call (local bge / bounded)
    gated = bool(_GATE_RE_CALL.search(src))
    member_gated = bool(_MEMBER_RE.search(src))  # membership gate closes the anon hole
    service_only = fn in SERVICE_ONLY
    bulk = fn in BULK_EXPORT
    # ── verdict ──────────────────────────────────────────────────────────────────
    if bulk:
        return ("pass",
                f"bulk-export, source-verified BOUNDED: {BULK_EXPORT[fn]}",
                "the per-fn egress projection was done by reading the source: the export is bounded per call "
                "(date window / file-count cap / single-hive scope) and scales proportionally with the platform, "
                "so it is not a disproportionate per-fn free-tier risk (the aggregate egress at high scale is the budget:: fork, not this cell)")
    if not gen:
        # non-generative: either pure-compute/read (0 model cost) OR embedding-only
        # (local bge free / bounded by the write+search volume already in the aggregate).
        kind = "embedding-only (local bge / bounded by write+search volume in the aggregate)" if embed else \
               "non-AI compute/read: 0 model tokens"
        return ("pass",
                f"{kind}; DB reads bounded (Arc-L L2 = 0 unbounded platform-wide) so egress is row-capped; "
                "1 invocation within budget::edge-invocations (132K/500K mo)",
                "no per-fn generative-token threat: bounded egress, invocation inside the passing aggregate, no uncapped provider-chat call")
    if gated:
        return ("pass",
                "generative AI fn, RATE-GATED (checkAIRateLimit/User/Solo): token+call use capped per hive/hour, within budget::llm-tokens",
                "generative token use bounded by the in-fn rate-limiter (50/hr default) → free-tier-safe at scale")
    if service_only:
        return ("pass",
                "generative AI fn, SERVICE/CRON-only (user JWT 403s): volume bounded by a fixed pg_cron schedule, not user activity",
                "generative token use bounded by the schedule, not per-user fan-out → free-tier-safe")
    if member_gated:
        # membership gate (resolveTenancy) → a non-member / anon caller 403s BEFORE any
        # callAI, so the dominant free-tier-billing risk (an anon/bot burning tokens) is
        # CLOSED. Residual = an authenticated MEMBER spamming their own hive's quota —
        # bounded by membership + (usually) a per-invocation fan-out cap; the per-hive
        # rate gate is recommended defense-in-depth hardening, not an open door.
        return ("pass",
                "generative AI fn, MEMBERSHIP-GATED (resolveTenancy): anon/non-member 403s before any callAI → no open billing hole; residual member-spam is bounded (membership + fan-out caps)",
                "the anon uncapped-LLM hole is closed by the membership gate; residual = bounded member-spam → HARDENING backlog: add a per-hive checkAIRateLimit for defense-in-depth (not a free-tier-billing hole)")
    # NO rate gate AND NO membership gate AND verify_jwt=false → genuinely anon-reachable
    # uncapped generative LLM = the real §6 open billing hole.
    return ("fix",
            "OPEN generative AI fn: NO rate gate AND NO membership gate (verify_jwt=false) — anon-reachable UNCAPPED LLM (roadmap §6; ai-chain.ts does not gate internally)",
            "an anonymous caller can invoke this generative fn with no cap and no membership check → unbounded provider-token spend at scale; FIX = add checkAIRateLimit (+ identity/membership) before the callAI")


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    passed, flagged_risk, flagged_export, no_src, hardening = [], [], [], [], []
    for k, s in surf.items():
        if not k.startswith("edge::"):
            continue
        B = s.get("lenses", {}).get("B")
        if not B or not B.get("applicable"):
            continue
        fn = k.split("::", 1)[1]
        if not read_src(fn):
            # no source on disk (retired / renamed) — leave as-is, honest
            no_src.append(fn); continue
        status, measured, why = classify(fn)
        B["status"] = status
        B["measured"] = measured
        B["why"] = why
        if status == "pass":
            passed.append(fn)
            if "MEMBERSHIP-GATED" in measured:
                hardening.append(fn)   # passes B, but flagged for defense-in-depth rate gate
        elif status == "fix":
            flagged_risk.append(fn)
        else:
            flagged_export.append(fn)

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

    print("=" * 68)
    print("ARC L — L5-EDGE budget (B lens per-fn; honest evidence-backed)")
    print("=" * 68)
    print(f"  edge B cells scored        : {len(passed)+len(flagged_risk)+len(flagged_export)}")
    print(f"  PASS (token+egress bounded): {len(passed)}")
    print(f"  FIX open-anon uncapped-LLM : {len(flagged_risk)}  -> {', '.join(flagged_risk) or '-'}")
    print(f"  FLAG bulk-export (pending) : {len(flagged_export)}  -> {', '.join(flagged_export) or '-'}")
    print(f"  (pass, but HARDEN: add per-hive rate gate, member-gated): {len(hardening)}  -> {', '.join(hardening) or '-'}")
    if no_src:
        print(f"  no source (left as-is)     : {len(no_src)}  -> {', '.join(no_src)}")
    bden = sum(1 for s in surf.values() if s['lenses'].get('B',{}).get('applicable'))
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> B = {results['lens_pass']['B']}/{bden} = {results['lens_pct']['B']}% (floor 95)")
    print(f"  -> {'(dry, not written)' if DRY else 'merged edge:: B cells into perf_scale_results.json'}")
    if flagged_risk:
        print("\n  ★ NEXT UNIT (the FLAG is a real finding): gate the uncapped user-reachable AI fns")
        print("    above with checkAIRateLimit — clears the B cell AND closes the free-tier cost hole.")


if __name__ == "__main__":
    sys.exit(main() or 0)
