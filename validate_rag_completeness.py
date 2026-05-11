"""
RAG Completeness -- WorkHive Platform
========================================
Catches the silent-quality-loss bug class: AI agents that retrieve
vector neighbors via cosine distance, then concatenate them straight
into the prompt without a reranker pass or a context-budget cap.

The reranker fixes "top-K by cosine != top-K by relevance" -- a
30-50 percent quality lift on RAG answers at near-zero cost. The
context budget prevents an unbounded retrieval set from blowing past
the model's context window.

Layer 1 -- rerank() helper present in embedding-chain                    [WARN]
  _shared/embedding-chain.ts must export a rerank() fn. Without it,
  no agent can call the reranker even if it wanted to.

Layer 2 -- context-budget helper present                                 [WARN]
  _shared/context-budget.ts must export budgetContext() or equivalent.
  Without it the prompt can grow unboundedly with retrieval volume.

Layer 3 -- Every retrieval-using AI fn calls rerank                      [WARN]
  AI edge fns that import the embedding chain AND build a prompt should
  also call rerank(). Forward-looking ratchet -- DEFERRED until adoption.

Layer 4 -- Retrieval adoption inventory (informational)                  [INFO]
  Per-fn map: does it embed? does it rerank? does it budget context?

Skills consulted: ai-engineer (RAG quality engineering, reranker
patterns), performance (context-window economics).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR      = os.path.join("supabase", "functions")
EMBED_CHAIN_FILE   = os.path.join(FUNCTIONS_DIR, "_shared", "embedding-chain.ts")
CONTEXT_BUDGET_FILE = os.path.join(FUNCTIONS_DIR, "_shared", "context-budget.ts")

# Per-fn opt-outs. Each entry needs a justification.
RAG_RERANK_OK = {
    "ai-gateway":          "Router only -- specialist agents call rerank downstream",
    "ai-eval-runner":      "Eval harness -- bypasses retrieval, hits gateway directly",
    "semantic-search":     "Provides the retrieval surface; reranker is called BY consumers",
    "embed-entry":         "Embedding write path, not a retrieval consumer",
    "pdf-ingest":          "Embedding write path, not a retrieval consumer",
}

# Forward-looking ratchet -- baseline 2026-05-11: rerank adoption is zero.
RERANK_DEFERRED = True

EMBED_IMPORT_RE = re.compile(
    r"""from\s+['"]\.\.\/_shared\/(?:embedding-chain|memory)['"]""",
)
RERANK_CALL_RE  = re.compile(r"""\brerank\s*\(""")
SEMANTIC_SEARCH_INVOKE_RE = re.compile(
    r"""\.functions\.invoke\(\s*['"]semantic-search['"]""",
)
EMBED_TEXT_CALL_RE = re.compile(r"""\bembedText\s*\(""")
CALLAI_RE = re.compile(r"""\bcallAI\s*\(""")
BUDGET_IMPORT_RE = re.compile(
    r"""from\s+['"]\.\.\/_shared\/context-budget['"]""",
)
BUDGET_CALL_RE = re.compile(r"""\bbudgetContext\s*\(""")


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _retrieves_context(src: str) -> bool:
    """Heuristic: the fn either calls embedText OR invokes semantic-search."""
    return bool(EMBED_TEXT_CALL_RE.search(src) or SEMANTIC_SEARCH_INVOKE_RE.search(src))


# -- Layer 1: rerank() helper present ------------------------------------

def check_rerank_helper() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    src = read_file(EMBED_CHAIN_FILE) or ""
    has_export = bool(re.search(
        r"""export\s+(?:async\s+)?function\s+rerank\s*(?:<[^>]+>)?\s*\(""",
        src,
    ))
    report = [{"rerank_export_present": has_export}]
    if not has_export:
        issues.append({
            "check": "rerank_helper", "skip": False,
            "reason": (
                "_shared/embedding-chain.ts does not export a rerank() "
                "function. Apply the Phase 1.2 helper -- cosine-only "
                "retrieval misses true relevance ranking."
            ),
        })
    return issues, report


# -- Layer 2: context-budget helper present ------------------------------

def check_budget_helper() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    src = read_file(CONTEXT_BUDGET_FILE) or ""
    # Allow generic type params: `export function budgetContext<T extends Foo>(...)`
    has_export = bool(re.search(
        r"""export\s+function\s+budgetContext\s*(?:<[^>]+>)?\s*\(""",
        src,
    ))
    report = [{"budget_export_present": has_export}]
    if not has_export:
        issues.append({
            "check": "budget_helper", "skip": False,
            "reason": (
                "_shared/context-budget.ts does not export budgetContext(). "
                "RAG retrieval has no bound on context tokens."
            ),
        })
    return issues, report


# -- Layer 3: rerank adoption per fn -------------------------------------

def check_rerank_adoption(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in RAG_RERANK_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        # Only fns that BOTH retrieve context AND build an AI prompt are
        # candidates for reranker enforcement.
        if not _retrieves_context(src):
            continue
        if not CALLAI_RE.search(src):
            continue
        has_rerank = bool(RERANK_CALL_RE.search(src))
        report.append({"fn": name, "calls_rerank": has_rerank})
        if not has_rerank:
            issues.append({
                "check": "rerank_adoption", "skip": RERANK_DEFERRED,
                "reason": (
                    f"{name}: retrieves context + builds an AI prompt but "
                    f"never calls rerank(). Add a rerank pass between "
                    f"retrieval and prompt construction."
                ),
            })
    return issues, report


# -- Layer 4: Retrieval adoption inventory (informational) --------------

def check_inventory(fns) -> tuple[list[dict], list[dict]]:
    report: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        embeds   = bool(EMBED_TEXT_CALL_RE.search(src))
        searches = bool(SEMANTIC_SEARCH_INVOKE_RE.search(src))
        reranks  = bool(RERANK_CALL_RE.search(src))
        budgets  = bool(BUDGET_CALL_RE.search(src))
        ai       = bool(CALLAI_RE.search(src))
        if not (embeds or searches or reranks or budgets):
            continue
        report.append({
            "fn":       name,
            "embeds":   embeds,
            "searches": searches,
            "reranks":  reranks,
            "budgets":  budgets,
            "ai":       ai,
        })
    return [], report


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "rerank_helper",
    "budget_helper",
    "rerank_adoption",
    "inventory",
]
CHECK_LABELS = {
    "rerank_helper":   "L1  rerank() helper exported from embedding-chain                 [FAIL]",
    "budget_helper":   "L2  budgetContext() helper exported from context-budget          [FAIL]",
    "rerank_adoption": "L3  Retrieval-using AI fns call rerank() before prompt           [WARN]",
    "inventory":       "L4  Retrieval / rerank / budget adoption per fn                  [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nRAG Completeness (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s), RAG_RERANK_OK={len(RAG_RERANK_OK)}.\n")

    l1_issues, l1_report = check_rerank_helper()
    l2_issues, l2_report = check_budget_helper()
    l3_issues, l3_report = check_rerank_adoption(fns)
    l4_issues, l4_report = check_inventory(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('RETRIEVAL ADOPTION PER FN (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:12]:
            flags = []
            if r["embeds"]:   flags.append("embed")
            if r["searches"]: flags.append("search")
            if r["reranks"]:  flags.append("rerank")
            if r["budgets"]:  flags.append("budget")
            if r["ai"]:       flags.append("ai")
            print(f"  {r['fn']:<32}  [{'+'.join(flags)}]")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":       "rag_completeness",
        "total_checks":    total,
        "passed":          n_pass,
        "warned":          n_warn,
        "failed":          n_fail,
        "n_fns":           len(fns),
        "rerank_helper":   l1_report,
        "budget_helper":   l2_report,
        "rerank_adoption": l3_report,
        "inventory":       l4_report,
    }
    try:
        with open("rag_completeness_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
