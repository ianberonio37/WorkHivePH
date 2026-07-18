#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D13
r"""validate_ai_fabrication_contract.py — D13 action-faithfulness (no invented action).

THE FABRICATION CLASS (CL10, live-caught 2026-07-08 on assistant.html): an advisory AI answer
that asserts a COMPLETED system write — "Log entry added to CT-001 maintenance history",
"Updated maintenance record", "I've scheduled the follow-up", "Logged: PB-002 bearing replaced" —
when the READ-ONLY brain wrote nothing. In a safety-adjacent maintenance context that is a
confident false "I did X": the worker believes the system recorded something it did NOT.

THE SHARED RAIL: _shared/action_provenance.ts `stripFalseActionClaims()` strips only COMPLETED-
write sentences (past-tense / passive-done), preserving recommendations, acknowledgements, and
drafting offers. The CALLER appends ACTION_HONEST_CLARIFIER when anything was stripped.

This is the STABLE-RULER D13 oracle: deterministic, $0, no deno / DB / model. It does not
re-prove the rail's regex behaviour (action_provenance.test.ts does that live) — it asserts the
STRUCTURE that makes every generative AI fn's action-fabrication surface guarded, and FAILs the
moment that structure regresses:

  1. RAIL INTEGRITY — action_provenance.ts still exports stripFalseActionClaims +
     ACTION_HONEST_CLARIFIER and still defines the completed-write pattern battery
     (isCompletedWriteClaim + LABEL_DONE / FP_DONE / VERB_FIRST_DONE / NOMINAL_DONE). A gutting
     to a no-op FAILs. Its .test.ts must exist.

  2. GATEWAY CENTRALIZATION — ai-gateway wires stripFalseActionClaims gated to
     ADVISORY_ANSWER_AGENTS, applied on the answer BEFORE persist + return. Every advisory
     conversational route in AGENT_ROUTES (i.e. every route that is NOT an action-executor) is
     covered by that set. A NEW advisory route added without rail coverage FAILs. The action-
     executor routes (voice-action / logbook-voice / report-voice / voice-journal) are DELIBERATELY
     excluded — they genuinely persist, so their confirmations are TRUE, not fabricated.

  3. PER-FN RESOLUTION — every generative (non-infra) AI fn resolves to exactly one fabrication
     guard: self-railed (imports the rail) / gateway-advisory (behind the gateway rail) /
     numeric-railed / structured-producer (emits structured intents/records/artifact, not a free-
     form completed-action answer). An unclassified fn — e.g. a newly deployed generative fn —
     FAILs, forcing an explicit classification decision (mirrors the engine's auditable
     INFRA_AI_FNS list rather than a fuzzy runtime classifier).

Exit 0 = PASS, 1 = FAIL. No file is ever edited.
"""
from __future__ import annotations
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = ROOT / "supabase" / "functions"
RAIL = FN_DIR / "_shared" / "action_provenance.ts"
RAIL_TEST = FN_DIR / "_shared" / "action_provenance.test.ts"
GATEWAY = FN_DIR / "ai-gateway" / "index.ts"
SEAMS = ROOT / "ai_seams_catalog.json"

GRN, RED, YEL, BLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# Mirror deepwalk_flywheel.py: infra fns generate no NL prose → D13 is n/a for them.
INFRA_AI_FNS = {
    "batch-risk-scoring", "cold-archive-query", "data-fabric-normalizer",
    "embed-entry", "equipment-label-ocr", "pdf-ingest", "voice-embeddings",
}

# The gateway routes that are ACTION-EXECUTORS: they genuinely perform the write they report, so
# the action rail must NOT strip their confirmations. Auditable list (the structural counterpart
# of the gateway's ADVISORY_ANSWER_AGENTS). Every AGENT_ROUTES agent_id must be in exactly ONE of
# {executor, advisory}; a route in neither FAILs check 2.
EXECUTOR_AGENT_IDS = {"voice-action", "logbook-voice", "report-voice", "voice-journal"}

# Per-fn D13 guard classification (explicit + auditable). Union must cover every generative fn.
SELF_RAILED = {"ai-orchestrator"}                       # imports stripFalseActionClaims itself
NUMERIC_RAILED = {"voice-journal-agent"}                # imports numeric_provenance (gateNumericProvenance)
GATEWAY_ADVISORY = {                                     # behind the gateway advisory rail (route -> fn)
    "asset-brain-query", "analytics-orchestrator", "project-orchestrator",
    "shift-planner-orchestrator", "temporal-rag-orchestrator",
}
# Structured/executor producers: user-facing output is intents / records / artifact / report, NOT
# a free-form conversational answer claiming a completed action. Their invented-NUMBER surface is
# D10 grounding's job (validate_grounding_contract / narrative_grounding / artifact_alignment); the
# invented-ACTION surface is structurally absent. Verified NOT to be an unguarded advisory route.
STRUCTURED_PRODUCER = {
    "agent-memory-store", "agentic-rag-loop", "ai-eval-runner", "ai-gateway", "amc-orchestrator",
    "engineering-bom-sow", "engineering-calc-agent", "failure-signature-scan", "fmea-populator",
    "hierarchical-summarizer", "intelligence-report", "scheduled-agents", "semantic-fact-extractor",
    "visual-defect-capture", "voice-action-router", "voice-logbook-entry", "voice-report-intent",
    "voice-semantic-rag", "walkthrough-analyzer",
}


def _fail(msg, fails):
    fails.append(msg)


def load_generative_fns():
    """Generative (non-infra) AI fns = ai_seams_catalog.ai_fns ∩ deployed − INFRA_AI_FNS."""
    try:
        declared = set(json.loads(SEAMS.read_text(encoding="utf-8")).get("ai_fns", []))
    except Exception:
        declared = set()
    deployed = {p.name for p in FN_DIR.glob("*") if p.is_dir() and p.name != "_shared"}
    fns = (declared & deployed) if deployed else declared
    return sorted(f for f in fns if f not in INFRA_AI_FNS)


def parse_set_members(src, name):
    """Members of `const NAME: Set<string> = new Set([...])` (string literals)."""
    m = re.search(rf"{name}\s*:\s*Set<string>\s*=\s*new Set\(\[(.*?)\]\)", src, re.S)
    if not m:
        m = re.search(rf"{name}\s*=\s*new Set\(\[(.*?)\]\)", src, re.S)
    if not m:
        return None
    return set(re.findall(r"""["']([^"']+)["']""", m.group(1)))


def parse_agent_routes(src):
    """agent_id -> fn from the AGENT_ROUTES map literal."""
    # Anchor after the `= {` so the `{` inside the `Record<string, { fn: ... }>` type
    # annotation is skipped, then take up to the top-level `\n};`.
    decl = re.search(r"const AGENT_ROUTES.*?=\s*\{", src, re.S)
    if not decl:
        return {}
    tail = src[decl.end():]
    end = tail.find("\n};")
    block = tail[:end] if end != -1 else tail
    routes = {}
    # each entry: "agent-id": { fn: "target-fn", description: ... }
    for m in re.finditer(r"""["']([a-z0-9\-]+)["']\s*:\s*\{[^}]*?\bfn\s*:\s*["']([a-z0-9\-]+)["']""",
                         block, re.S | re.I):
        routes[m.group(1)] = m.group(2)
    return routes


def check_rail_integrity(fails):
    if not RAIL.is_file():
        _fail(f"rail missing: {RAIL.relative_to(ROOT)}", fails)
        return
    src = RAIL.read_text(encoding="utf-8", errors="replace")
    required = [
        ("export function stripFalseActionClaims", "stripFalseActionClaims export"),
        ("ACTION_HONEST_CLARIFIER", "honest clarifier constant"),
        ("function isCompletedWriteClaim", "isCompletedWriteClaim gate"),
        ("LABEL_DONE", "LABEL_DONE pattern"),
        ("FP_DONE", "FP_DONE pattern"),
        ("VERB_FIRST_DONE", "VERB_FIRST_DONE pattern"),
        ("NOMINAL_DONE", "NOMINAL_DONE pattern"),
        ("ADVICE_FRAME", "advice-frame carve-out (preserves recommendations)"),
    ]
    for needle, label in required:
        if needle not in src:
            _fail(f"rail gutted — missing {label} in action_provenance.ts", fails)
    # the gate must actually consult the patterns (not stubbed to `return false`)
    if re.search(r"function isCompletedWriteClaim[^{]*\{\s*return false", src):
        _fail("isCompletedWriteClaim stubbed to `return false` (rail is a no-op)", fails)
    if not RAIL_TEST.is_file():
        _fail("action_provenance.test.ts missing (rail behaviour unproven)", fails)


def check_gateway_centralization(fails):
    if not GATEWAY.is_file():
        _fail("ai-gateway/index.ts missing", fails)
        return
    src = GATEWAY.read_text(encoding="utf-8", errors="replace")
    if "stripFalseActionClaims" not in src:
        _fail("ai-gateway does not import/apply stripFalseActionClaims", fails)
    advisory = parse_set_members(src, "ADVISORY_ANSWER_AGENTS")
    if advisory is None:
        _fail("ai-gateway: ADVISORY_ANSWER_AGENTS set not found", fails)
        advisory = set()
    # the rail must be APPLIED gated to that set (not merely imported)
    if not re.search(r"ADVISORY_ANSWER_AGENTS\.has\(agent\)[^;]*\n?[^;]*stripFalseActionClaims\(",
                     src) and not (
            "ADVISORY_ANSWER_AGENTS.has(agent)" in src and "stripFalseActionClaims(" in src):
        _fail("ai-gateway: rail not applied gated to ADVISORY_ANSWER_AGENTS", fails)
    # every advisory route (not an executor) must be covered by the rail set
    routes = parse_agent_routes(src)
    if not routes:
        _fail("ai-gateway: could not parse AGENT_ROUTES", fails)
    for agent_id in sorted(routes):
        if agent_id in EXECUTOR_AGENT_IDS:
            if agent_id in advisory:
                _fail(f"executor route '{agent_id}' wrongly in ADVISORY_ANSWER_AGENTS "
                      f"(its true confirmations would be stripped)", fails)
            continue
        if agent_id not in advisory:
            _fail(f"advisory route '{agent_id}' -> {routes[agent_id]} NOT covered by the "
                  f"action rail (add it to ADVISORY_ANSWER_AGENTS or EXECUTOR_AGENT_IDS)", fails)
    return routes, advisory


def check_per_fn_resolution(fails):
    gen = load_generative_fns()
    classified = SELF_RAILED | NUMERIC_RAILED | GATEWAY_ADVISORY | STRUCTURED_PRODUCER
    for fn in gen:
        if fn not in classified:
            _fail(f"generative fn '{fn}' is UNCLASSIFIED for D13 — assign it a fabrication "
                  f"guard bucket in validate_ai_fabrication_contract.py", fails)
    # a stale classification entry (fn retired) is a soft warning, not a fail
    stale = classified - set(gen) - {"ai-gateway"}  # ai-gateway self-guards; may not be in seams
    # verify the wiring each bucket CLAIMS actually exists in code
    for fn in sorted(SELF_RAILED & set(gen)):
        p = FN_DIR / fn / "index.ts"
        if p.is_file() and "stripFalseActionClaims" not in p.read_text(encoding="utf-8", errors="replace"):
            _fail(f"SELF_RAILED '{fn}' no longer imports stripFalseActionClaims", fails)
    for fn in sorted(NUMERIC_RAILED & set(gen)):
        p = FN_DIR / fn / "index.ts"
        if p.is_file() and "numeric_provenance" not in p.read_text(encoding="utf-8", errors="replace"):
            _fail(f"NUMERIC_RAILED '{fn}' no longer imports numeric_provenance", fails)
    return gen, stale


def main():
    fails: list[str] = []
    print(f"{BLD}AI FABRICATION CONTRACT (D13) — action-faithfulness rail is structurally wired{RST}")
    print("=" * 80)

    check_rail_integrity(fails)
    gw = check_gateway_centralization(fails)
    gen, stale = check_per_fn_resolution(fails)

    routes, advisory = gw if isinstance(gw, tuple) else ({}, set())
    print(f"  generative fns (non-infra): {len(gen)}  ·  gateway routes: {len(routes)}  ·  "
          f"advisory-railed agents: {len(advisory)}")
    print(f"  guard buckets: self-railed {len(SELF_RAILED)} · gateway-advisory {len(GATEWAY_ADVISORY)} · "
          f"numeric-railed {len(NUMERIC_RAILED)} · structured-producer {len(STRUCTURED_PRODUCER)}")
    if stale:
        print(f"  {YEL}note{RST}: classification lists {len(stale)} fn(s) not in the live seam set "
              f"(retired?) — {', '.join(sorted(stale))}")

    if fails:
        print(f"\n{RED}FAIL{RST}: {len(fails)} D13 action-faithfulness contract breach(es):")
        for f in fails:
            print(f"  {RED}✗{RST} {f}")
        return 1
    print(f"\n{GRN}PASS{RST}: rail intact · gateway centralizes it over every advisory route · "
          f"all {len(gen)} generative fns resolve to a fabrication guard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
