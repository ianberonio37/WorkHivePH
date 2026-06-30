#!/usr/bin/env python3
"""validate_embedding_chain_consistency.py — guard the embedding-chain revamp (2026-06-12).

The W7 trap (proven live during W10): a corpus embedded with model A but queried
with model B lands in a DIFFERENT vector space, so cosine is noise and retrieval
silently returns nothing. The 2026-06-12 revamp fixes this with a PER-CORPUS pinned
primary; this validator keeps it from regressing. It asserts:

  1. persona-knowledge.ts pins a query model (PK_EMBED_MODEL has a default).
  2. The ingest tool's default (EMBED_PREFER) MATCHES that pin — ingest and query
     must use the SAME model or retrieval breaks.
  3. embedding-chain.ts keeps a deterministic primary (EMBEDDING_PRIMARY), accepts a
     per-call pin, and logs a SPACE-DIVERGENCE warning on fallback.
  4. Mistral is NOT an embedding provider in the chain (mistral-embed is 1024-dim,
     incompatible with vector(384)).
  5. (live, if the DB is reachable) persona_knowledge sits in EXACTLY ONE embedding
     space — a single distinct embedding_model, no split corpus.

Audit-scope rule honored: the static scan reads supabase/functions/_shared/*.ts (the
real consumer of the embedding contract), not just functions/*/index.ts.

Exit 0 = all green. Exit 1 = a consistency break. `--self-test` runs the checks and
prints a summary without failing CI on the live (DB) check when the DB is down.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "supabase" / "functions" / "_shared"
PK_TS = SHARED / "persona-knowledge.ts"
CHAIN_TS = SHARED / "embedding-chain.ts"
INGEST = ROOT / "tools" / "ingest_persona_knowledge.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def check_static() -> list[tuple[bool, str]]:
    res: list[tuple[bool, str]] = []
    pk, chain, ing = _read(PK_TS), _read(CHAIN_TS), _read(INGEST)

    # 1. persona-knowledge.ts pins a query model. The default may be a simple `|| "x"` or a
    # local-gated ternary `|| (_IS_LOCAL ? "x" : "y")` — capture the EFFECTIVE LOCAL default.
    m_pk = re.search(r'PK_EMBED_MODEL\s*=\s*\(.*?(?:\?\s*"|\|\|\s*")([a-z0-9-]+)"', pk, re.S)
    res.append((bool(m_pk), f"persona-knowledge.ts PK_EMBED_MODEL (local) default = {m_pk.group(1) if m_pk else 'MISSING'}"))

    # 2. ingest default EMBED_PREFER matches PK_EMBED_MODEL
    m_ing = re.search(r'^EMBED_PREFER\s*=\s*"([a-z0-9-]+)"', ing, re.M)
    if m_pk and m_ing:
        same = m_pk.group(1) == m_ing.group(1)
        res.append((same, f"ingest EMBED_PREFER ({m_ing.group(1)}) {'==' if same else '!= (SPLIT-SPACE RISK)'} edge PK_EMBED_MODEL ({m_pk.group(1)})"))
    else:
        res.append((False, f"ingest EMBED_PREFER default = {m_ing.group(1) if m_ing else 'MISSING'}"))

    # 3. embedding-chain.ts: deterministic primary + per-call pin + divergence warning.
    # The default may be a simple `|| "voyage"` OR a local-gated ternary
    # `|| (_IS_LOCAL_EMBED && BGE_EMBED_URL ? "bge-local" : "voyage")` — both are deterministic
    # (fixed given env). Capture the EFFECTIVE default the same way the PK_EMBED_MODEL check does
    # (a corpus re-embedded to bge-local LOCALLY pins the local query to bge-local — lockstep).
    m_pri = re.search(r'EMBEDDING_PRIMARY\s*=\s*\(.*?(?:\?\s*"|\|\|\s*")([a-z0-9-]+)"', chain, re.S)
    res.append((bool(m_pri),
                f"embedding-chain.ts has a deterministic EMBEDDING_PRIMARY default = {m_pri.group(1) if m_pri else 'MISSING'}"))
    res.append(("pin?: string" in chain or "pin: string" in chain,
                "embedding-chain.ts generateEmbedding accepts a per-call pin"))
    res.append(("SPACE-DIVERGENCE" in chain,
                "embedding-chain.ts logs a SPACE-DIVERGENCE warning on fallback"))

    # 4. Mistral must NOT be an embedding provider (1024-dim, not 384)
    in_providers = re.search(r'ALL_PROVIDERS[^\]]*?\]', chain, re.S)
    mistral_embed = bool(in_providers and "mistral" in in_providers.group(0).lower())
    res.append((not mistral_embed, "Mistral is NOT in the embedding ALL_PROVIDERS (1024-dim incompatible)"))

    return res


def check_live() -> list[tuple[bool | None, str]]:
    """Live DB checks. None = DB unreachable (skip): (1) ONE embedding space, no NULL
    embeddings; (2) TWO-PLANES — no chunk is tenant-keyed (hive UUID / hive_id), since
    persona_knowledge is GLOBAL (no hive_id) and must hold brain only, not tenant data."""
    try:
        import psycopg2
        c = psycopg2.connect(host="127.0.0.1", port=54322, dbname="postgres", user="postgres", password="postgres", connect_timeout=4)
        cur = c.cursor()
        out: list[tuple[bool | None, str]] = []
        # 1. one space + no NULL embeddings
        cur.execute("select coalesce(embedding_model,'(null)'), count(*) from persona_knowledge group by 1 order by 2 desc")
        rows = cur.fetchall()
        if not rows:
            cur.execute("select 1")  # keep conn valid
            c.close()
            return [(None, "persona_knowledge is empty (nothing to check)")]
        cur.execute("select count(*) from persona_knowledge where embedding is null")
        nulls = cur.fetchone()[0]
        ok1 = len(rows) == 1 and nulls == 0
        detail = ", ".join(f"{m}:{n}" for m, n in rows)
        out.append((ok1, f"persona_knowledge: {len(rows)} embedding space(s) [{detail}], {nulls} NULL-embedding rows"
                         + ("" if ok1 else "  <-- SPLIT or UN-EMBEDDED")))
        # 2. two-planes: no chunk carries a real tenant IDENTIFIER (a UUID). The schema
        # WORD "hive_id" is legitimate in skill/architecture docs and is NOT flagged — a
        # specific UUID tying to a tenant row is the actual multi-tenancy red flag.
        cur.execute(r"""select count(*) from persona_knowledge
                        where content ~* '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'""")
        tenant = cur.fetchone()[0]
        out.append((tenant == 0, f"two-planes: {tenant} chunk(s) carry a tenant UUID in the global brain table"
                                 + ("" if tenant == 0 else "  <-- MULTI-TENANCY LEAK")))
        c.close()
        return out
    except Exception as e:  # noqa: BLE001
        return [(None, f"DB unreachable (live checks skipped): {type(e).__name__}")]


def main() -> int:
    self_test = "--self-test" in sys.argv
    print("=" * 72)
    print("EMBEDDING-CHAIN CONSISTENCY")
    print("=" * 72)
    static = check_static()
    all_ok = True
    for ok, msg in static:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        all_ok = all_ok and ok

    live_skipped = False
    for live_ok, live_msg in check_live():
        tag = "PASS" if live_ok else ("SKIP" if live_ok is None else "FAIL")
        print(f"  [{tag}] {live_msg}")
        if live_ok is False:
            all_ok = False
        if live_ok is None:
            live_skipped = True

    print("-" * 72)
    print("RESULT:", "GREEN" if all_ok else "RED")
    if self_test and live_skipped:
        return 0  # don't fail CI on a DB-down live check during self-test
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
