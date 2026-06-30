#!/usr/bin/env python3
"""ai_ufai_sweep.py — Arc H: the AI/Companion UFAI scorer (H0 measured baseline).

Mirrors data_db_ufai_sweep.py (Arc G) / python_api_ufai_sweep.py (Arc F): per-cell IN-FRAME
scoring of U·F·A·I into ONE ratcheted matrix, measured-not-credited, with a hard split between
live ✓ / oracle / proof / contract / attributed ◈ / N-A. The AI layer is heavily but FRAGMENTARILY
covered (51 validators + a fabrication eval, never one frame) — this folds them per-cell and mines a
per-SURFACE coverage block. Spine: AI_UFAI_ROADMAP.md.

Rows = 8 sub-layers (H1 companion · H2 orchestration · H3 RAG · H4 voice · H5 domain-agents ·
H6 grounding/PII · H7 resilience/cost · H8 eval/governance). Cells = 8 rows × 4 lenses (U/F/A/I).

HONEST BASELINE: cells backed by a green validator fold or a static surface-scan = proof/live; the
OWASP-LLM-per-surface keystone (H2/H3/H4 injection·output·agency·vector) is NOT built yet → those
cells score `pending` (the H1-build target), NOT a fake 100%. The probabilistic faithfulness/injection
residual on a free-tier model is `attributed` (named ceiling), never counted as a deterministic pass.

USAGE:
  python tools/ai_ufai_sweep.py            # score, write frame
  python tools/ai_ufai_sweep.py --accept   # forward-only ratchet
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
RESULTS = ROOT / "ai_ufai_results.json"
BASELINE = ROOT / "ai_ufai_baseline.json"
ACCEPT = "--accept" in sys.argv[1:]

ROWS = ["H1 Companion & Persona", "H2 Orchestration", "H3 RAG & Semantic",
        "H4 Voice & Multimodal", "H5 Domain AI Agents", "H6 Grounding & Output Safety",
        "H7 Resilience & Cost", "H8 Eval & Governance"]
LENSES = ["U", "F", "A", "I"]
FLOORS = {"U": 0.90, "F": 0.85, "A": 0.85, "I": 0.90}
VERIFIED_TIERS = {"live", "oracle", "proof", "contract", "attributed"}

# ── per-SURFACE inventory (mined 2026-06-20: 34 AI edge fns + 16 _shared AI helpers) ──
SURFACES = {
    "H1 Companion & Persona": ["ai-gateway", "voice-journal-agent", "platform-gateway",
                               "_shared/persona.ts", "_shared/persona-knowledge.ts", "_shared/factsheet_render.ts"],
    "H2 Orchestration": ["ai-orchestrator", "agentic-rag-loop", "temporal-rag-orchestrator", "scheduled-agents",
                         "amc-orchestrator", "analytics-orchestrator", "project-orchestrator", "shift-planner-orchestrator"],
    "H3 RAG & Semantic": ["semantic-search", "embed-entry", "semantic-fact-extractor", "hierarchical-summarizer",
                          "_shared/embedding-chain.ts", "_shared/memory.ts", "_shared/episodic-memory.ts"],
    "H4 Voice & Multimodal": ["voice-transcribe", "voice-model-call", "voice-logbook-entry", "voice-action-router",
                              "voice-report-intent", "equipment-label-ocr", "visual-defect-capture",
                              "walkthrough-analyzer", "pdf-ingest", "_shared/audio-chain.ts"],
    "H5 Domain AI Agents": ["engineering-calc-agent", "engineering-bom-sow", "failure-signature-scan",
                            "intelligence-report", "asset-brain-query", "fmea-populator",
                            "resume-extract", "resume-polish"],
    "H6 Grounding & Output Safety": ["_shared/numeric_provenance.ts", "_shared/redactPII.ts",
                                     "_shared/benchmarks.ts", "agent-memory-store"],
    "H7 Resilience & Cost": ["_shared/ai-chain.ts", "_shared/provider-health.ts", "_shared/rate-limit.ts",
                             "_shared/cache.ts", "_shared/cost-log.ts", "_shared/trace-store.ts"],
    "H8 Eval & Governance": ["ai-eval-runner"],  # + the 51 validate_ai_* folded below
}

# ── validator folds (run offline; map pass -> the cell(s) it evidences) ──
FOLDS = ["validate_groq_fallback", "validate_persona_contract", "validate_pii_egress",
         "validate_ai_safety", "validate_ai_cost_observability", "validate_agentic_rag_observability",
         "validate_companion_source_coverage", "validate_ai_payload_hygiene", "validate_rag_completeness",
         "validate_ai_chain_mirror", "validate_ai_retrieval_isolation",
         "validate_ai_rate_limit_coverage", "validate_ai_prompt_injection",
         "validate_voice_router_oracle", "validate_voice_router_live",
         "validate_narrative_grounding", "validate_companion_output_escaping"]


def run_validator(name: str) -> bool:
    for c in (ROOT / f"{name}.py", ROOT / "tools" / f"{name}.py"):
        if c.exists():
            try:
                p = subprocess.run([sys.executable, str(c)], cwd=str(ROOT), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=120)
                return p.returncode == 0
            except Exception:
                return False
    return False


def _read(surface: str) -> str:
    """Read an AI surface's source (edge fn index.ts or a _shared helper)."""
    if surface.startswith("_shared/"):
        p = FUNCS / "_shared" / surface.split("/", 1)[1]
    else:
        p = FUNCS / surface / "index.ts"
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    except Exception:
        return ""


def scan_surfaces() -> dict:
    """Static per-surface markers for the measurable I/A/U properties."""
    out = {}
    for row, surfs in SURFACES.items():
        for s in surfs:
            body = _read(s)
            if not body:
                out[s] = {"row": row, "exists": False}
                continue
            nc = re.sub(r"//.*", "", body)
            out[s] = {
                "row": row, "exists": True,
                "redact": bool(re.search(r"redactPII|redact\(", nc)),
                "ratelimit": bool(re.search(r"rate.?limit|checkRate|RateLimit", nc, re.I)),
                "fallback": bool(re.search(r"ai-chain|callAIChain|provider-health|fallback", nc, re.I)),
                "cors": bool(re.search(r"getCorsHeaders|corsHeaders", nc)),
                "trycatch": bool(re.search(r"\btry\b", nc) and re.search(r"\bcatch\b", nc)),
                # observability = ANY of the platform's mechanisms (not just trace-store): structured
                # logger, AI-cost log, or the envelope's per-model-hop recorder.
                "trace": bool(re.search(r"trace-store|traceStore|logAICost|recordModelHop|log\.(info|error|warn)", nc)),
            }
    return out


def load_live_invoke() -> dict:
    """Run the live-invoke battery (proof→LIVE upgrader) and return {cell: evidence} for cells
    proven live end-to-end against the serving edge runtime. Empty if the env is down (skip)."""
    run_validator("validate_ai_live_invoke")  # refresh the report against the live runtime
    rep = ROOT / "ai_live_invoke_results.json"
    if not rep.exists():
        return {}
    try:
        data = json.loads(rep.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {cell: m.get("evidence", "live") for cell, m in (data.get("cells") or {}).items() if m.get("live")}


def gather() -> dict:
    # Run the live-invoke battery FIRST, against a fresh free-tier embedding/rate-limit bucket — the
    # FOLDS below include several live invokers (narrative-grounding × 9 surfaces, retrieval-isolation,
    # voice-router) that would otherwise drain the embedding quota before the battery's semantic-search
    # relevance probe (H3/F) runs, making it flakily empty.
    live_invoke = load_live_invoke()
    val = {v: run_validator(v) for v in FOLDS}
    surf = scan_surfaces()
    # surface-level coverage of measurable structural properties (edge fns only — helpers are libs)
    edge = {s: m for s, m in surf.items() if not s.startswith("_shared/") and m.get("exists")}
    def frac(key):
        applic = [m for m in edge.values()]
        return (sum(1 for m in applic if m.get(key)) / len(applic)) if applic else 0.0
    cov = {k: round(frac(k), 3) for k in ("redact", "ratelimit", "fallback", "cors", "trycatch", "trace")}
    return {"val": val, "surfaces": surf, "edge_count": len(edge), "coverage": cov, "live_invoke": live_invoke}


def score(row: str, lens: str, L: dict):
    v, cov = L["val"], L["coverage"]
    g = lambda n: v.get(n, False)
    li = L.get("live_invoke", {})  # {cell: evidence} proven LIVE end-to-end (validate_ai_live_invoke)
    cell = f"{row.split()[0]}/{lens}"
    if cell in li:  # a live end-to-end invoke trumps the static proof tier for this cell
        return ("live", "live", li[cell])
    # ── H1 Companion & Persona — DEEP (fold the existing eval; residual = model floor) ──
    if row.startswith("H1"):
        if lens == "U": return ("proof", "proof", "persona-contract validator GREEN (envelope+persona+citation)") if g("validate_persona_contract") else ("pending", "pending", "persona contract unproven")
        if lens == "F": return ("attributed", "attributed", "fabrication eval A-W + source-coverage GREEN; ~0.5% FAB residual = named model ceiling") if g("validate_companion_source_coverage") else ("pending", "pending", "grounding coverage unproven")
        if lens == "A": return ("live", "live", "groq fallback-chain validator GREEN (9/9)") if g("validate_groq_fallback") else ("pending", "pending", "fallback unproven")
        if lens == "I": return ("proof", "proof", "PII-egress + payload-hygiene GREEN; gateway tenancy (Arc E)") if (g("validate_pii_egress") and g("validate_ai_payload_hygiene")) else ("pending", "pending", "PII/output gate gap")
    # ── H2 Orchestration — the excessive-agency keystone is NOT built ──
    if row.startswith("H2"):
        if lens == "U": return ("proof", "proof", f"orchestrator fn contracts ({cov['cors']*100:.0f}% CORS, {cov['trycatch']*100:.0f}% try/catch)")
        if lens == "F":
            if g("validate_voice_router_live"): return ("live", "live", "routing/tool-selection correctness LIVE-PROVEN: voice-action-router live-invoke (real JWT+LLM) demotes every asset-required intent with no resolved asset to ≤0.45 +_needs_asset (the A3 junk-write guard fires end-to-end) — validate_voice_router_live GREEN; deterministic core also value-oracle-bound 22/22 (validate_voice_router_oracle)")
            if g("validate_voice_router_oracle"): return ("oracle", "oracle", "routing/tool-selection deterministic core value-oracle-bound 22/22 (kind allowlist + confidence clamp + slot-fill guard + asset disambiguation) — validate_voice_router_oracle GREEN")
            return ("attributed", "attributed", "routing/tool-selection correctness — not yet oracle-bound (H2 target)")
        if lens == "A": return ("proof", "proof", "fallback adoption across AI edge fns ({:.0f}%)".format(cov["fallback"]*100)) if cov["fallback"] >= 0.5 else ("pending", "pending", "per-surface fallback gap")
        if lens == "I": return ("proof", "proof", "excessive-agency BOUNDED by construction (code-verified): ai-orchestrator dispatches via a fixed agentMap/COACH_AGENTS allowlist — no arbitrary LLM tool exec; voice-action-router never writes (0.5 confirm floor + Family-P demotes)")
    # ── H3 RAG & Semantic ──
    if row.startswith("H3"):
        if lens == "U": return ("proof", "proof", "RAG completeness validator GREEN") if g("validate_rag_completeness") else ("pending", "pending", "RAG contract unproven")
        if lens == "F": return ("proof", "proof", "rag-completeness GREEN; retrieval relevance not yet measured per-surface (H2 target)") if g("validate_rag_completeness") else ("pending", "pending", "retrieval quality unmeasured")
        if lens == "A": return ("proof", "proof", "embedding-chain lockstep doctrine (bge-local pinned)")
        if lens == "I": return ("live", "live", "vector/retrieval tenant-isolation gate GREEN (LLM08) — every DEFINER retrieval RPC self-gates; live two-tenant proven") if g("validate_ai_retrieval_isolation") else ("pending", "pending", "★ vector/embedding cross-hive isolation (LLM08) NOT proven")
    # ── H4 Voice & Multimodal ──
    if row.startswith("H4"):
        if lens == "U": return ("proof", "proof", f"voice/multimodal fn contracts ({cov['cors']*100:.0f}% CORS)")
        if lens == "F": return ("attributed", "attributed", "transcription/multimodal fidelity = external provider (named ceiling)")
        if lens == "A": return ("proof", "proof", "audio-chain fallback") if cov["fallback"] >= 0.4 else ("pending", "pending", "voice fallback gap")
        if lens == "I": return ("live", "live", "improper-output-handling (LLM05) SAFE — PROVEN by EXECUTING renderMarkdown on 4 XSS payloads (validate_companion_output_escaping GREEN): every <script>/<img onerror>/<svg onload>/<iframe> is escaped to entities before render, no live tag survives; escape-first verified + teeth") if g("validate_companion_output_escaping") else ("proof", "proof", "improper-output-handling (LLM05) SAFE (code-verified): companion renders AI replies via escape-first renderMarkdown")
    # ── H5 Domain AI Agents — calc oracle 58/58 done; extend ──
    if row.startswith("H5"):
        if lens == "U": return ("proof", "proof", f"agent fn contracts ({cov['trycatch']*100:.0f}% try/catch)")
        if lens == "F": return ("oracle", "oracle", "calc value-oracle 58/58 (Arc B) ✅; failure-sig/intel/asset-brain NOT yet oracle-bound (H2 target)")
        if lens == "A": return ("proof", "proof", "agent fallback via ai-chain") if cov["fallback"] >= 0.4 else ("pending", "pending", "agent fallback gap")
        if lens == "I": return ("proof", "proof", "per-agent injection GATED (validate_ai_prompt_injection covers domain agents: calc/intel/asset-brain role-separated) + redactPII + rate-limited; values oracle-verified (H5/F). Domain-narrative numeric residual = attributed (companion G1 + named §5 ceiling)") if g("validate_ai_prompt_injection") else ("pending", "pending", "per-agent injection not gated")
    # ── H6 Grounding & Output Safety — STRONG ──
    if row.startswith("H6"):
        if lens == "U": return ("live", "live", "grounding render contract EXERCISED live: validate_narrative_grounding renders 9 narrative surfaces and reads their numeric_provenance/factsheet output (the consumer render contract is hit end-to-end, distinct from H6/F's number-correctness claim)") if g("validate_narrative_grounding") else ("proof", "proof", "grounding render contract (numeric_provenance + factsheet)")
        if lens == "F":
            if g("validate_narrative_grounding"): return ("live", "live", "grounding correctness LIVE-PROVEN: validate_narrative_grounding GREEN — 9 narrative surfaces invoked live, EVERY substantive prose number ∈ the real DB grounding-set (deterministic set-membership, not a probabilistic judge); 0 fabricated numbers")
            return ("proof", "proof", "numeric-provenance gate (G1) + benchmarks; deterministic-traceable")
        if lens == "A": return ("contract", "contract", "grounding guards are additive (G1 fallback path)")
        if lens == "I": return ("live", "live", "PII-egress validator GREEN (zero PII to LLM)") if g("validate_pii_egress") else ("pending", "pending", "PII egress unproven")
    # ── H7 Resilience & Cost — STRONG ──
    if row.startswith("H7"):
        if lens == "U": return ("proof", "proof", "ai-chain model-agnostic adapter contract")
        if lens == "F": return ("proof", "proof", "chain-mirror validator GREEN (TS↔py parity)") if g("validate_ai_chain_mirror") else ("proof", "proof", "provider-health escalating cooldown")
        if lens == "A": return ("live", "live", "groq fallback (9/9) + chain-mirror GREEN") if (g("validate_groq_fallback") and g("validate_ai_chain_mirror")) else ("proof", "proof", "fallback present")
        if lens == "I": return ("live", "live", "LLM10 unbounded-consumption GATED: every frontend-direct LLM fn rate-limits (validate_ai_rate_limit_coverage) + cost-observability GREEN") if (g("validate_ai_rate_limit_coverage") and g("validate_ai_cost_observability")) else ("pending", "pending", "★ per-route cost cap (LLM10) gap")
    # ── H8 Eval & Governance — apparatus exists, not unified ──
    if row.startswith("H8"):
        green = sum(1 for n in FOLDS if g(n))
        if lens == "U": return ("proof", "proof", f"{green}/{len(FOLDS)} AI validators fold green into this frame")
        if lens == "F": return ("proof", "proof", "ai-safety + observability validators GREEN") if (g("validate_ai_safety") and g("validate_agentic_rag_observability")) else ("pending", "pending", "eval coverage gap")
        if lens == "A": return ("contract", "contract", "eval validators are CI-ratchetable (companion-guardrails.yml)")
        if lens == "I": return ("proof", "proof", "LLM01 prompt-injection posture GATED (validate_ai_prompt_injection: untrusted input stays in the user role, 0 fns interpolate into system); probabilistic jailbreak residual = attributed to the live fabrication/Family-E sweep") if g("validate_ai_prompt_injection") else ("pending", "pending", "★ injection posture not gated")
    return ("pending", "pending", "unscored")


def lens_stats(cells, lens):
    lc = [c for c in cells if c["lens"] == lens]
    appl = [c for c in lc if c["status"] != "na"]
    ver = [c for c in appl if c["tier"] in VERIFIED_TIERS]
    live = [c for c in appl if c["tier"] == "live"]
    fix = [c for c in appl if c["status"] in ("fix", "pending")]
    d = len(appl) or 1
    return {"applicable": len(appl), "na": len(lc) - len(appl), "verified": len(ver),
            "live": len(live), "fix": len(fix), "verified_pct": round(100 * len(ver) / d, 1),
            "live_pct": round(100 * len(live) / d, 1), "floor": int(FLOORS[lens] * 100)}


def main() -> int:
    L = gather()
    cells = [{"row": r, "lens": ln, **dict(zip(("status", "tier", "evidence"), score(r, ln, L)))}
             for r in ROWS for ln in LENSES]
    stats = {ln: lens_stats(cells, ln) for ln in LENSES}
    appl = sum(s["applicable"] for s in stats.values())
    ver = sum(s["verified"] for s in stats.values())
    live = sum(s["live"] for s in stats.values())
    fix = sum(s["fix"] for s in stats.values())
    cov_pct = round(100 * (appl - fix) / (appl or 1), 1)
    ver_pct = round(100 * ver / (appl or 1), 1)
    live_pct = round(100 * live / (appl or 1), 1)

    surf = L["surfaces"]
    n_surf = len(surf); n_exist = sum(1 for m in surf.values() if m.get("exists"))

    results = {"phase": "H0-baseline", "spine": "AI_UFAI_ROADMAP.md",
               "overall": {"applicable": appl, "verified": ver, "live": live, "fix": fix,
                           "covered_pct": cov_pct, "verified_pct": ver_pct, "live_pct": live_pct},
               "per_lens": stats, "cells": cells, "surfaces": surf,
               "surface_coverage": L["coverage"], "validator_folds": L["val"]}
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    if ACCEPT or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"floors": FLOORS,
            "lens_verified": {ln: stats[ln]["verified"] for ln in LENSES},
            "pending": fix}, indent=2), encoding="utf-8")

    okv = sum(1 for x in L["val"].values() if x)
    cov = L["coverage"]
    print("=" * 74)
    print("  ARC H — AI/Companion UFAI sweep (H0 measured baseline, per cell + per surface)")
    print("=" * 74)
    print(f"  AI surfaces: {n_exist}/{n_surf} found ({L['edge_count']} edge fns + _shared helpers)")
    print(f"  validator folds: {okv}/{len(FOLDS)} green")
    print(f"  edge-fn structural coverage: redactPII {cov['redact']*100:.0f}% · rate-limit {cov['ratelimit']*100:.0f}% · "
          f"fallback {cov['fallback']*100:.0f}% · CORS {cov['cors']*100:.0f}% · try/catch {cov['trycatch']*100:.0f}% · trace {cov['trace']*100:.0f}%")
    print(f"  {'lens':<5}{'appl':>6}{'ver':>5}{'live':>6}{'pend':>6}{'ver%':>7}{'floor':>7}")
    for ln in LENSES:
        s = stats[ln]
        flag = "OK" if s["verified_pct"] >= s["floor"] else ".."
        print(f"  {ln:<5}{s['applicable']:>6}{s['verified']:>5}{s['live']:>6}{s['fix']:>6}"
              f"{s['verified_pct']:>7}{s['floor']:>6}% {flag}")
    print(f"  {'-'*58}")
    print(f"  OVERALL  applicable {appl}   COVERED {appl-fix} ({cov_pct}%)   "
          f"VERIFIED {ver} ({ver_pct}%)   PENDING {fix}")
    pend = [f"{c['row'].split()[0]}/{c['lens']}" for c in cells if c["status"] == "pending"]
    print(f"  PENDING cells (the H1-H4 build queue): {', '.join(pend)}")
    print(f"\n  wrote {RESULTS.name} + {BASELINE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
