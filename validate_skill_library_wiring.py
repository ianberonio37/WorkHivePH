"""
skill-library-wiring — L0 ratchet for the Procedural layer (layer 04) of the
AI Agent Memory Stack (Turn 5 of the memory-stack flywheel).

Asserts the runtime skill library + matcher is genuinely wired end to end: the
procedural memories in agent_episodic_memory are EMBEDDED at write time, a
cosine RPC retrieves them, the matcher module wraps it, and ai-gateway injects
the top matches for fix-oriented agents. Sibling to episodic/verified-state/
cold-archive/semantic-fact wiring. Forward-only: baseline 0 issues.

  W01  _shared/skill-library.ts exists + exports matchProcedures + formatProcedures
  W02  matcher imports generateEmbedding + calls the match_procedural_memories RPC
  W03  migration creates match_procedural_memories RPC + idx_aem_embedding index
  W04  persistEpisodic EMBEDS procedural memories at write time (else library is unsearchable)
  W05  ai-gateway imports the matcher, declares PROCEDURAL_SKILL_AGENTS, injects the block
  W06  matcher is hive-scoped + best-effort (returns [] on no-scope / error)
"""
from __future__ import annotations
import os, sys, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MODULE   = os.path.join("supabase", "functions", "_shared", "skill-library.ts")
EPISODIC = os.path.join("supabase", "functions", "_shared", "episodic-memory.ts")
GATEWAY  = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
MIG_DIR  = os.path.join("supabase", "migrations")


def _flat(s: str) -> str: return s.replace(" ", "").replace("\n", "")


def check_module() -> list[dict]:
    if not os.path.isfile(MODULE):
        return [{"check": "module", "reason": f"{MODULE} not found"}]
    src = read_file(MODULE) or ""
    issues = []
    for fn in ("matchProcedures", "formatProcedures"):
        if f"export function {fn}" not in src and f"export async function {fn}" not in src:
            issues.append({"check": "module", "reason": f"skill-library.ts must export {fn}"})
    return issues


def check_matcher_calls() -> list[dict]:
    src = read_file(MODULE) or ""
    issues = []
    if "generateEmbedding" not in src or "embedding-chain.ts" not in src:
        issues.append({"check": "matcher_calls", "reason": "matcher must import generateEmbedding from _shared/embedding-chain.ts"})
    if "match_procedural_memories" not in src or ".rpc(" not in src:
        issues.append({"check": "matcher_calls", "reason": "matcher must call the match_procedural_memories RPC via db.rpc(...)"})
    return issues


def check_migration() -> list[dict]:
    hit = False
    for p in glob.glob(os.path.join(MIG_DIR, "*procedural_skill_matcher*.sql")):
        src = read_file(p) or ""
        if "match_procedural_memories" in src and "idx_aem_embedding" in src:
            hit = True
    if not hit:
        return [{"check": "migration", "reason": "migration creating match_procedural_memories RPC + idx_aem_embedding index not found"}]
    return []


def check_persist_embeds() -> list[dict]:
    src = read_file(EPISODIC) or ""
    flat = _flat(src)
    issues = []
    if "generateEmbedding" not in src:
        issues.append({"check": "persist_embeds", "reason": "episodic-memory.ts must import generateEmbedding to embed procedural memories"})
    # The embed must be gated to the procedural type (cost bound) inside persist.
    if 'memory_type==="procedural"' not in flat and "memory_type===\"procedural\"" not in flat:
        issues.append({"check": "persist_embeds", "reason": "persistEpisodic must embed only memory_type === 'procedural' rows"})
    return issues


def check_gateway() -> list[dict]:
    src = read_file(GATEWAY) or ""
    flat = _flat(src)
    issues = []
    if "skill-library.ts" not in src or "matchProcedures" not in src or "formatProcedures" not in src:
        issues.append({"check": "gateway", "reason": "ai-gateway must import matchProcedures + formatProcedures from _shared/skill-library.ts"})
    if "PROCEDURAL_SKILL_AGENTS" not in src:
        issues.append({"check": "gateway", "reason": "ai-gateway must declare PROCEDURAL_SKILL_AGENTS"})
    if "matchProcedures(" not in flat or "formatProcedures(" not in flat:
        issues.append({"check": "gateway", "reason": "ai-gateway must call matchProcedures + formatProcedures in the recall path"})
    if "PROCEDURAL_SKILL_AGENTS.has(" not in flat:
        issues.append({"check": "gateway", "reason": "ai-gateway must gate the procedure injection on PROCEDURAL_SKILL_AGENTS membership"})
    return issues


def check_best_effort() -> list[dict]:
    src = read_file(MODULE) or ""
    flat = _flat(src)
    issues = []
    # Hive/worker scoping guard + empty-on-miss contract.
    if "if(!hiveId&&!workerName)return[]" not in flat:
        issues.append({"check": "best_effort", "reason": "matchProcedures must require a hive or worker scope (return [] otherwise)"})
    if "catch" not in src or "return [];" not in src:
        issues.append({"check": "best_effort", "reason": "matchProcedures must be best-effort (catch embedding/RPC errors and return [])"})
    return issues


CHECKS = [
    ("module",        "W01 skill-library.ts exists + exports matchProcedures/formatProcedures", check_module),
    ("matcher_calls", "W02 imports generateEmbedding + calls match_procedural_memories RPC",     check_matcher_calls),
    ("migration",     "W03 migration: RPC + idx_aem_embedding index",                            check_migration),
    ("persist_embeds","W04 persistEpisodic embeds procedural memories",                          check_persist_embeds),
    ("gateway",       "W05 ai-gateway imports matcher + PROCEDURAL_SKILL_AGENTS + injects",       check_gateway),
    ("best_effort",   "W06 matcher hive-scoped + best-effort ([] on miss)",                       check_best_effort),
]


def main() -> int:
    print("\033[1m\nskill-library-wiring — Turn 5 (Procedural / layer 04, skill library + matcher)\033[0m")
    print("=" * 70)
    all_issues = []
    keys = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}
    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)
    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
