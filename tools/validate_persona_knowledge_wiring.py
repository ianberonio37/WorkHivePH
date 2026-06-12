#!/usr/bin/env python3
"""validate_persona_knowledge_wiring.py — static guard for the L08 persona-knowledge
wire (companion wiring W7). Mirrors validate_skill_library_wiring style: asserts the
full chain is wired so the curated DOMAIN corpus actually reaches the conversational
launcher (the O11 gap) with persona scope isolation (O10) and a token cap (O9).

Checks (all static — runs in the offline gate):
  1. Migration declares persona_knowledge (persona_scope CHECK + vector(384)) + the
     match_persona_knowledge RPC with a server-side scope filter.
  2. _shared/persona-knowledge.ts: scopesForPersona maps hezekiah->technical+shared,
     zaniah->strategic+shared, default->shared; a token cap constant; best-effort
     (returns [] / "" on miss).
  3. ai-gateway imports loadPersonaKnowledge/formatPersonaKnowledge AND injects them
     for a PERSONA_KNOWLEDGE_AGENTS set that INCLUDES voice-journal (the launcher).

Exit 0 = wired; exit 1 = a break. Forward-only teeth. (companion wiring W7, 2026-06-12)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations" / "20260612000000_persona_knowledge.sql"
PK = ROOT / "supabase" / "functions" / "_shared" / "persona-knowledge.ts"
GW = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"


def main() -> int:
    fails: list[str] = []

    def need(cond: bool, msg: str):
        (print(f"  \033[92mok\033[0m {msg}") if cond else fails.append(msg))

    # 1. Migration
    if not MIG.exists():
        fails.append(f"migration {MIG.name} missing")
    else:
        m = MIG.read_text(encoding="utf-8", errors="ignore")
        need("create table" in m and "persona_knowledge" in m, "migration creates persona_knowledge")
        need("persona_scope" in m and "technical" in m and "strategic" in m and "shared" in m,
             "persona_scope CHECK covers technical|strategic|shared")
        need("vector(384)" in m, "embedding is vector(384)")
        need("match_persona_knowledge" in m, "match_persona_knowledge RPC defined")
        need("persona_scope = any(scopes)" in m.replace(" ", " "), "RPC filters persona_scope = any(scopes) (server-side O10)")

    # 2. _shared/persona-knowledge.ts
    if not PK.exists():
        fails.append(f"{PK.name} missing")
    else:
        s = PK.read_text(encoding="utf-8", errors="ignore")
        need("scopesForPersona" in s, "scopesForPersona exists")
        need(re.search(r'hezekiah["\']?\s*\)?\s*return\s*\[\s*["\']technical["\']\s*,\s*["\']shared["\']', s) is not None
             or ('"technical"' in s and '"shared"' in s and "hezekiah" in s),
             "Hezekiah -> technical+shared")
        need("zaniah" in s and '"strategic"' in s, "Zaniah -> strategic+shared")
        need('return ["shared"]' in s or "['shared']" in s, "unknown persona -> shared only (safe default)")
        need("PK_BLOCK_CHARS" in s, "token-cap constant PK_BLOCK_CHARS present (O9)")
        need("match_persona_knowledge" in s, "calls match_persona_knowledge RPC")
        need(re.search(r"return\s*\[\]\s*;", s) is not None, "best-effort: returns [] on miss (O12 graceful degrade)")

    # 3. ai-gateway wiring
    if not GW.exists():
        fails.append(f"{GW.name} missing")
    else:
        g = GW.read_text(encoding="utf-8", errors="ignore")
        need("loadPersonaKnowledge" in g and "formatPersonaKnowledge" in g, "gateway imports load/formatPersonaKnowledge")
        need("PERSONA_KNOWLEDGE_AGENTS" in g, "PERSONA_KNOWLEDGE_AGENTS set defined")
        mset = re.search(r"PERSONA_KNOWLEDGE_AGENTS[^=]*=\s*new Set\(\[(.*?)\]\)", g, re.S)
        need(mset is not None and "voice-journal" in mset.group(1),
             "PERSONA_KNOWLEDGE_AGENTS INCLUDES voice-journal (the launcher = O11 wire)")
        need(re.search(r"PERSONA_KNOWLEDGE_AGENTS\.has\(agent\)", g) is not None,
             "gateway gates the injection on PERSONA_KNOWLEDGE_AGENTS.has(agent)")
        need("memorySections.domain_knowledge = true" in g, "domain_knowledge section flag set on inject")

    print()
    if fails:
        print("\033[91m\033[1mPERSONA-KNOWLEDGE WIRING: FAIL\033[0m")
        for f in fails:
            print(f"  \033[91mx\033[0m {f}")
        return 1
    print("\033[92m\033[1mPERSONA-KNOWLEDGE WIRING: PASS\033[0m — corpus reaches the launcher, persona-scoped, capped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
