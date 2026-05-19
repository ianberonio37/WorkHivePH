"""Validator: KG facts scope split (HIVE vs PLATFORM).

Locks in the architectural correction shipped 2026-05-19 in migration
20260519000001_platform_knowledge_graph_facts.sql. Without these gates,
the broadcast-across-hives anti-pattern (4,605 rows where 1,533 sufficed)
would silently regress next time someone extracts triples from a new
standards corpus.

Four layers:

  L1  Migration present                                          [FAIL]
      platform_knowledge_graph_facts table is defined in a migration.
      Without it the platform-scoped store doesn't exist, voice-handler's
      semantic_search_platform_kg_facts RPC call returns "unknown function",
      and the only path back is to re-broadcast.

  L2  Platform RPC defined                                       [FAIL]
      semantic_search_platform_kg_facts function is defined in a migration.
      Catches a half-applied schema (table present, RPC missing or renamed).

  L3  voice-handler queries both stores                          [FAIL]
      If voice-handler.js references the hive RPC it must also reference
      the platform RPC. Stops a refactor from silently dropping canon
      citations.

  L4  No broadcast pattern in migrations                         [FAIL]
      No migration may INSERT INTO knowledge_graph_facts ... CROSS JOIN hives.
      Catches the regression where someone re-creates the broadcast workaround
      because they don't know about the platform table.

Skills consulted: architect (the kb_chunks vs. industry_standards_chunks
split precedent), multitenant-engineer (hive_id NOT NULL semantics —
genuinely hive-scoped vs. platform-canon), ai-engineer (voice-handler RAG
fan-out pattern).
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

def _row(passed: bool, name: str, detail: str) -> str:
    marker = "PASS" if passed else "FAIL"
    color  = "\033[92m" if passed else "\033[91m"
    return f"  [{color}{marker}\033[0m] {name:55s} -- {detail}"


MIGRATIONS_GLOB = os.path.join("supabase", "migrations", "*.sql")
VOICE_HANDLER   = "voice-handler.js"

PLATFORM_TABLE_RE = re.compile(
    r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(?:public\.)?platform_knowledge_graph_facts\s*\(",
    re.IGNORECASE,
)
PLATFORM_RPC_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?semantic_search_platform_kg_facts\b",
    re.IGNORECASE,
)
BROADCAST_RE = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?knowledge_graph_facts[\s\S]{0,400}?CROSS\s+JOIN\s+(?:public\.)?hives",
    re.IGNORECASE,
)


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def main() -> int:
    print("\n\033[1mKG Facts Scope Split (HIVE vs PLATFORM) Validator (4-layer)\033[0m")
    print("=" * 60)

    migration_files = sorted(glob.glob(MIGRATIONS_GLOB))
    migrations_text = "\n\n".join(f"-- {p}\n{read(p)}" for p in migration_files)
    voice_text = read(VOICE_HANDLER)

    findings: list[dict] = []
    pass_count = 0

    # L1: migration present
    has_table = bool(PLATFORM_TABLE_RE.search(migrations_text))
    findings.append({
        "layer": "L1", "name": "platform_knowledge_graph_facts table defined",
        "passed": has_table,
        "detail": ("found in migrations" if has_table
                   else "no CREATE TABLE platform_knowledge_graph_facts -- migration 20260519000001 missing or renamed"),
    })

    # L2: RPC defined
    has_rpc = bool(PLATFORM_RPC_RE.search(migrations_text))
    findings.append({
        "layer": "L2", "name": "semantic_search_platform_kg_facts RPC defined",
        "passed": has_rpc,
        "detail": ("found in migrations" if has_rpc
                   else "no CREATE FUNCTION semantic_search_platform_kg_facts -- voice-handler will get unknown-function errors"),
    })

    # L3: voice-handler queries both
    has_hive_rpc     = "semantic_search_kg_facts"          in voice_text
    has_platform_rpc = "semantic_search_platform_kg_facts" in voice_text
    voice_ok = (not has_hive_rpc) or has_platform_rpc
    if voice_ok and has_hive_rpc and has_platform_rpc:
        v_detail = "voice-handler.js calls both hive + platform RPCs"
    elif voice_ok and not has_hive_rpc:
        v_detail = "voice-handler.js does not query KG facts (vacuously OK)"
    else:
        v_detail = ("voice-handler.js references semantic_search_kg_facts (hive) but NOT "
                    "semantic_search_platform_kg_facts (platform) -- canon citations dropped silently")
    findings.append({"layer": "L3", "name": "voice-handler queries both KG stores",
                     "passed": voice_ok, "detail": v_detail})

    # L4: no broadcast pattern in any migration
    offenders = []
    for path in migration_files:
        text = read(path)
        if BROADCAST_RE.search(text):
            offenders.append(os.path.basename(path))
    broadcast_clean = not offenders
    findings.append({
        "layer": "L4", "name": "no broadcast-across-hives in migrations",
        "passed": broadcast_clean,
        "detail": ("clean" if broadcast_clean
                   else f"broadcast pattern found in: {', '.join(offenders)} -- use platform_knowledge_graph_facts instead"),
    })

    for f in findings:
        print(_row(f["passed"], f"{f['layer']}  {f['name']}", f["detail"]))
        if f["passed"]:
            pass_count += 1

    total = len(findings)
    color = "\033[92m" if pass_count == total else "\033[91m"
    print(f"\n{color}  {pass_count}/{total} checks passed.\033[0m")

    report_path = "kg_scope_split_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"total": total, "passed": pass_count, "findings": findings}, f, indent=2)

    return 0 if pass_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
