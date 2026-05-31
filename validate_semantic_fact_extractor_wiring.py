"""
semantic-fact-extractor-wiring — L0 ratchet for the Semantic layer (layer 03)
of the AI Agent Memory Stack (Turn 4 of the memory-stack flywheel).

Asserts the per-hive logbook entity extractor is genuinely wired: it reads the
hive's logbook, extracts typed S-P-O triples through the free-tier AI chain,
embeds them, and idempotently upserts into knowledge_graph_facts (source_type
'ai_extraction') against the Turn-4 dedupe index. Sibling to
episodic-memory-wiring / verified-state-wiring / cold-archive-wiring.
Forward-only: baseline 0 issues.

  W01  _shared/semantic-facts.ts exists + exports the pure helpers
  W02  edge fn imports callAI + generateEmbedding + the semantic-facts helpers
  W03  edge fn reads v_logbook_truth, hive-scoped
  W04  edge fn writes knowledge_graph_facts with source_type 'ai_extraction'
  W05  edge fn upserts idempotently (onConflict dedupe key) + dedupe migration present
  W06  edge fn bounds fan-out (ROW_CAP / MAX_GROUPS / TRIPLE_CAP) + caps embeddings (EMBED_CAP)
  W07  edge fn returns ok:true on the empty/success path (no 200+ok:false)
  W08  4-place sync: config.toml + deploy-functions.ps1 + ALL_FUNCTIONS + REQUIRED_FIELDS
"""
from __future__ import annotations
import os, sys, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

EDGE_FN = os.path.join("supabase", "functions", "semantic-fact-extractor", "index.ts")
MODULE  = os.path.join("supabase", "functions", "_shared", "semantic-facts.ts")
MIG_DIR = os.path.join("supabase", "migrations")


def _read_fn() -> str:  return read_file(EDGE_FN) or ""
def _flat(s: str) -> str: return s.replace(" ", "").replace("\n", "")


def check_module() -> list[dict]:
    if not os.path.isfile(MODULE):
        return [{"check": "module", "reason": f"{MODULE} not found"}]
    src = read_file(MODULE) or ""
    issues = []
    for fn in ("sanitizeType", "parseTriples", "validateTriple", "formatEntriesForPrompt"):
        if f"export function {fn}" not in src:
            issues.append({"check": "module", "reason": f"semantic-facts.ts must export {fn}"})
    if "ALLOWED_PREDICATES" not in src or "TYPE_CHECK_RE" not in src:
        issues.append({"check": "module", "reason": "semantic-facts.ts must define the CHECK vocabulary (ALLOWED_PREDICATES + TYPE_CHECK_RE)"})
    return issues


def check_imports(src: str) -> list[dict]:
    issues = []
    if "callAI" not in src or "ai-chain.ts" not in src:
        issues.append({"check": "imports", "reason": "edge fn must import callAI from _shared/ai-chain.ts"})
    if "generateEmbedding" not in src or "embedding-chain.ts" not in src:
        issues.append({"check": "imports", "reason": "edge fn must import generateEmbedding from _shared/embedding-chain.ts"})
    if "semantic-facts.ts" not in src or "validateTriple" not in src:
        issues.append({"check": "imports", "reason": "edge fn must import the pure helpers from _shared/semantic-facts.ts"})
    return issues


def check_logbook_read(src: str) -> list[dict]:
    issues = []
    if "v_logbook_truth" not in src:
        issues.append({"check": "logbook_read", "reason": "edge fn must read the canonical v_logbook_truth view"})
    if '.eq("hive_id"' not in src and ".eq('hive_id'" not in src:
        issues.append({"check": "logbook_read", "reason": "edge fn must scope the logbook read by hive_id"})
    return issues


def check_writes(src: str) -> list[dict]:
    issues = []
    if "knowledge_graph_facts" not in src:
        issues.append({"check": "writes", "reason": "edge fn must write to knowledge_graph_facts"})
    if '"ai_extraction"' not in src and "'ai_extraction'" not in src:
        issues.append({"check": "writes", "reason": "facts must carry source_type 'ai_extraction'"})
    if "source_ref" not in src or "logbook:" not in src:
        issues.append({"check": "writes", "reason": "facts must carry source_ref 'logbook:<entry_id>' for provenance + dedupe"})
    return issues


def check_idempotent(src: str) -> list[dict]:
    issues = []
    flat = _flat(src)
    if "onConflict" not in flat or "subject_ref" not in flat or "object_ref" not in flat:
        issues.append({"check": "idempotent", "reason": "edge fn must upsert ON CONFLICT against the (hive_id,subject_ref,predicate,object_ref,source_ref) dedupe key"})
    # The dedupe migration that creates uq_kgf_triple_source must exist.
    mig_hit = any("uq_kgf_triple_source" in (read_file(p) or "")
                  for p in glob.glob(os.path.join(MIG_DIR, "*knowledge_graph_facts_dedup*.sql")))
    if not mig_hit:
        issues.append({"check": "idempotent", "reason": "dedupe migration creating uq_kgf_triple_source not found"})
    return issues


def check_bounds(src: str) -> list[dict]:
    issues = []
    for const in ("ROW_CAP", "MAX_GROUPS", "TRIPLE_CAP", "EMBED_CAP"):
        if const not in src:
            issues.append({"check": "bounds", "reason": f"edge fn must define {const} to bound fan-out / row / embedding budget"})
    return issues


def check_contract(src: str) -> list[dict]:
    flat = _flat(src)
    issues = []
    # Uses the shared envelope: ok() is always 200 (ok:true), fail(status>=400)
    # is always ok:false -> structurally satisfies the status/body contract.
    if '"../_shared/envelope.ts"' not in src:
        issues.append({"check": "contract", "reason": "edge fn must use the shared response envelope (ok/fail)"})
    if "ok(ctx" not in flat:
        issues.append({"check": "contract", "reason": "edge fn must return ok(ctx, ...) on the success path"})
    if "fail(ctx" not in flat:
        issues.append({"check": "contract", "reason": "edge fn must return fail(ctx, ...) on the error path"})
    # Empty / nothing-new must be a SUCCESS (ok()), not an error.
    if "nonewlogbookentries" not in flat.lower():
        issues.append({"check": "contract", "reason": "empty extraction must return an ok() success (no new logbook entries), not fail()"})
    return issues


def check_sync() -> list[dict]:
    issues = []
    cfg = read_file(os.path.join("supabase", "config.toml")) or ""
    if "[functions.semantic-fact-extractor]" not in cfg:
        issues.append({"check": "sync", "reason": "config.toml missing [functions.semantic-fact-extractor]"})
    dep = read_file("deploy-functions.ps1") or ""
    if "semantic-fact-extractor" not in dep:
        issues.append({"check": "sync", "reason": "deploy-functions.ps1 missing semantic-fact-extractor deploy line"})
    ec = read_file("validate_edge_contracts.py") or ""
    if '"semantic-fact-extractor"' not in ec:
        issues.append({"check": "sync", "reason": "validate_edge_contracts.py ALL_FUNCTIONS/REQUIRED_FIELDS missing semantic-fact-extractor"})
    return issues


CHECKS = [
    ("module",       "W01 semantic-facts.ts exists + exports helpers",         check_module),
    ("imports",      "W02 imports callAI + generateEmbedding + helpers",       lambda: check_imports(_read_fn())),
    ("logbook_read", "W03 reads v_logbook_truth, hive-scoped",                 lambda: check_logbook_read(_read_fn())),
    ("writes",       "W04 writes knowledge_graph_facts (ai_extraction)",       lambda: check_writes(_read_fn())),
    ("idempotent",   "W05 idempotent upsert + dedupe migration",              lambda: check_idempotent(_read_fn())),
    ("bounds",       "W06 ROW_CAP/MAX_GROUPS/TRIPLE_CAP/EMBED_CAP bounds",     lambda: check_bounds(_read_fn())),
    ("contract",     "W07 ok:true empty-success path (no 200+ok:false)",       lambda: check_contract(_read_fn())),
    ("sync",         "W08 4-place sync (config/deploy/contracts)",             check_sync),
]


def main() -> int:
    print("\033[1m\nsemantic-fact-extractor-wiring — Turn 4 (Semantic / layer 03, logbook -> KG facts)\033[0m")
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
