#!/usr/bin/env python3
"""companion-grounding - the companion's reply is grounded, and says what it was given (OWN AI failure-mode lens, 2026-10-26).

Walked live (a spoken question through voice-handler.js, the transcription stubbed, everything after it real) at phone-390
and desktop-1280. Five things were wrong on every turn, and each is held here:

  C1 the companion's documents, knowledge-graph facts and standards never reached a reply: voice-handler.js built them into
     context.platform_prompt, which NO server code reads (rightly - a client must not set a system prompt), and its
     _embedQuery returned null anyway. ai-gateway now retrieves them (_shared/hive-knowledge.ts) with the PERSON's client so
     each RPC's membership guard applies; voice-journal-agent is told the HIVE KNOWLEDGE section is reference material it
     may quote (its memory rules had it refuse the block); the browser's three lookups, which only fed the ignored prompt,
     stop running.
  C2 a teammate's document chunk or extracted fact is read, never obeyed: sanitizeUntrusted on every line of the block.
  C3 the reply names what it was given ("Given with this answer: 1 document (Pump Bearing Lubrication Guide)") from the
     gateway's grounded_on - what the server put in the prompt, never a browser string the model did not receive.
  C4 the platform snapshot read v_kpi_truth, which BRH-V made the service role's alone on 2026-10-21 - 42501 every turn,
     so MTBF / MTTR / downtime never reached the prompt. It reads hive_kpis() now.
  C5 platform-scraper was called with the publishable key as the bearer (401 "Sign-in required" every turn), and the
     learning-loop row to conversation_analytics carried no hive_id (42501 every turn).

Teeth: the tree at 1045f447 fails every check.
    python tools/validate_companion_grounding.py [--ref <git-ref>]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: str, ref: str | None) -> str:
    if ref:
        try:
            return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True, encoding="utf-8",
                                           errors="replace", stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return ""
    p = ROOT / path
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _patterns(text: str, start: str) -> list[str]:
    i = text.find(start)
    if i < 0:
        return []
    block = text[i:text.index("];", i)]
    return [m.group(1) for m in re.finditer(r"^\s*/(.+)/i,\s*$", block, re.M)]


def check(ref: str | None = None) -> list[str]:
    vh = _read("voice-handler.js", ref)
    ss = _read("supabase/functions/semantic-search/index.ts", ref)
    ut = _read("supabase/functions/_shared/untrusted.ts", ref)
    bad = []
    gw = _read("supabase/functions/ai-gateway/index.ts", ref)
    hk = _read("supabase/functions/_shared/hive-knowledge.ts", ref)
    vj = _read("supabase/functions/voice-journal-agent/index.ts", ref)
    # C1 the platform_prompt the browser assembles is read by no server, so retrieval lives in the gateway
    if "loadHiveKnowledge(authedClient" not in gw or "grounded_on: groundedOn" not in gw:
        bad.append("C1 ai-gateway: the hive's documents, facts and standards are not retrieved server-side with the person's client")
    if not all(f'rpc("{r}"' in hk for r in ("semantic_search_kb", "semantic_search_kg_facts", "semantic_search_industry_standards")):
        bad.append("C1 _shared/hive-knowledge.ts: missing a document, fact or standards lookup")
    if "HIVE KNOWLEDGE" not in vj or "It is NOT something the worker said" not in vj:
        bad.append("C1 voice-journal-agent: no rule lets the model use the HIVE KNOWLEDGE section (its memory rules make it refuse)")
    if re.search(r"_fetch(RAG|KG|Standards)Context\(db,[^)]*\)\.catch", vh):
        bad.append("C1 voice-handler.js: a browser retrieval still feeds the platform_prompt no server reads")
    # C2 other people's text is read, never obeyed
    if "sanitizeUntrusted(" not in hk:
        bad.append("C2 _shared/hive-knowledge.ts: a document chunk or a team fact reaches the prompt without sanitizeUntrusted")
    # C3 the reply names what the SERVER says it was given
    if "_renderGivenLine(_gatewayGivenParts(data && data.grounded_on))" not in vh or "Given with this answer: " not in vh:
        bad.append("C3 voice-handler.js: the reply does not say what the gateway gave it")
    if "_groundingParts(kg, rag, std)" in vh:
        bad.append("C3 voice-handler.js: the line is built from browser strings the model never received")
    if re.search(r"db\.from\('v_kpi_truth'\)", vh):
        bad.append("C4 voice-handler.js: the snapshot still reads v_kpi_truth (service-role only since 2026-10-21) - use hive_kpis()")
    # since BRH-AO (2026-10-27) the companion does not call platform-scraper at all - its result fed a prompt no server read;
    # absence passes, and a call that comes back must still carry the person's token
    m = re.search(r"/functions/v1/platform-scraper'[\s\S]{0,300}", vh)
    if m and "'Bearer ' + SUPABASE_KEY" in m.group(0):
        bad.append("C5 voice-handler.js: platform-scraper is asked with the publishable key as the bearer")
    if "hive_id: hiveId,\n        session_id: sessionId" not in vh:
        bad.append("C5 voice-handler.js: the conversation_analytics row carries no hive_id (refused by its policy)")
    # the long-horizon path (a "compare over the last 8 months" question) - walked live 2026-10-26
    ar = _read("supabase/functions/agentic-rag-loop/index.ts", ref)
    tr = _read("supabase/functions/temporal-rag-orchestrator/index.ts", ref)
    hs = _read("supabase/functions/hierarchical-summarizer/index.ts", ref)
    if "function relativeTimeScope(" not in ar or "relativeTimeScope(question, new Date())" not in ar:
        bad.append("C6 agentic-rag-loop: a relative window ('the last 8 months') is left to a router that is never told today's date")
    if "MONTH_GRAIN_MAX_DAYS" not in tr or re.search(r"spanDays >= 180\b", tr):
        bad.append("C7 temporal-rag-orchestrator: spans from 180 days read the quarter level, which nothing writes")
    if "functions/v1/hierarchical-summarizer" not in tr:
        bad.append("C7 temporal-rag-orchestrator: a period with no summary is reported empty instead of being rolled up once")
    if 'levels.push("quarter")' not in hs or 'levels.push("year")' not in hs:
        bad.append("C7 hierarchical-summarizer: the schedule never writes the quarter and year levels temporal reads")
    if "_renderGivenLine(_ragGivenParts(ragData))" not in vh:
        bad.append("C3 voice-handler.js: a long-horizon (agentic) answer does not say what it was given")
    # C6b/C8 (2026-10-27): the computed window must also decide the ROUTE - the cold-archive promotion ran on the model's
    # guessed from-date, so "the last 8 months" answered "not enough records" twice after C6 had fixed the dates - and the
    # temporal delegate must carry the counted-forward proof, or one question moves the hive's bucket twice.
    if "re-routed from cold_archive" not in ar:
        bad.append("C6 agentic-rag-loop: a recent computed window does not leave the cold archive the model's guessed date chose")
    if "gatewayForwardHeaders(`Bearer ${_WH_KEY}`)" not in ar or "isTrustedGatewayForward(req)" not in tr:
        bad.append("C8 agentic-rag-loop -> temporal-rag-orchestrator: the delegate is counted on the hive's bucket twice")
    # C9 (2026-10-27, two devices): the logbook block SELECTED problem and never printed it, so the desktop assistant
    # answered "the snapshot does not include a problem text" about an entry logged on the phone a minute earlier.
    reg = _read("supabase/functions/_shared/companion_source_registry.json", ref)
    if "Recent logbook entries" in reg and "{problem" not in reg:
        bad.append("C9 companion_source_registry.json: the logbook block selects problem and never prints it")
    if "(?:\\|(\\d+))?" not in gw:
        bad.append("C9 ai-gateway _fillSlots: free text has no {field|N} clip, so a printed problem is unbounded")
    return bad


def main() -> int:
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    bad = check(ref)
    print(f"companion-grounding{' @ ' + ref if ref else ''}: {len(bad)} finding(s)")
    for b in bad:
        print("  - " + b)
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
