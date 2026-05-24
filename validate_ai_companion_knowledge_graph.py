"""
AI Companion Knowledge Graph Validator (turns #185-#194)
=========================================================
T185 entity extract / T186 relation / T187 triple / T188 RAG /
T189 embedding hash / T190 chunking / T191 citation / T192 query
rewrite / T193 reasoning trace / T194 KB version.
"""
from __future__ import annotations
import os, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


SYMBOLS = {
    "entity":      ["_extractEntities"],
    "relation":    ["_extractRelations"],
    "triple":      ["_buildKgTriple", "'caused'", "'feeds'", "'requires'", "'isolates'"],
    "rag":         ["_buildRagBlock", "RAG CONTEXT"],
    "embed_hash":  ["_embeddingHash32", "_hashHamming", "0x811c9dc5"],
    "chunking":    ["_chunkDocument"],
    "citation":    ["_buildCitation", "_parseCitation"],
    "query_rw":    ["_rewriteQueryForRetrieval"],
    "reasoning":   ["_REASONING_TRACE_KEY", "_recordReasoningHop", "_getReasoningTrace"],
    "kb_version":  ["_KB_VERSION_KEY", "_setKbVersion", "_getKbVersion", "_isKbStale"],
}
LABELS = {
    "entity":      "T185 _extractEntities",
    "relation":    "T186 _extractRelations",
    "triple":      "T187 _buildKgTriple + caused/feeds/requires/isolates predicates",
    "rag":         "T188 _buildRagBlock + RAG CONTEXT header",
    "embed_hash":  "T189 _embeddingHash32 (FNV-1a) + _hashHamming",
    "chunking":    "T190 _chunkDocument",
    "citation":    "T191 _buildCitation + _parseCitation",
    "query_rw":    "T192 _rewriteQueryForRetrieval",
    "reasoning":   "T193 _REASONING_TRACE_KEY + record/get hop",
    "kb_version":  "T194 _KB_VERSION_KEY + set/get/isStale",
}


def main() -> int:
    print("\033[1m\nAI Companion Knowledge Graph Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    issues = []
    for k, syms in SYMBOLS.items():
        for s in syms:
            if s not in c:
                issues.append({"check": k, "reason": f"{s} missing."})
    n_pass, n_skip, n_fail = format_result(list(SYMBOLS.keys()), LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
