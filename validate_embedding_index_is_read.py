#!/usr/bin/env python3
"""
validate_embedding_index_is_read — an embedding table nothing retrieves from is dead weight.

WHY THIS GATE EXISTS (PJ15, 2026-07-28)
---------------------------------------
project-manager.html has embedded every scope item and every lessons-learned save into
`project_knowledge` since Phase 6.5, through the embed-entry edge function. Measured across the
whole platform, that table's readers were:

    writers of project_knowledge : embed-entry
    readers of project_knowledge : NONE
        - no database function referenced it (searched pg_get_functiondef over pg_proc)
        - no edge function referenced it
        - no page referenced it

So the page paid an embedding round-trip on every save, and a supervisor asking the assistant
"what went wrong on the last pump overhaul?" got an answer that could not see the lessons that
project had recorded — the exact content that was embedded for that question. `search_all_knowledge`
unions fault + skill + pm and simply never gained a project branch when the writer shipped.

WHY NOTHING CAUGHT IT. Every existing check was satisfied: the table has hive_id, RLS is enabled and
correctly scoped, the writer works, the vector-schema gate validated the search function's existing
branches. Nothing asserted that an index anyone WRITES is an index anyone READS. And the table holds
0 rows in every seeded environment — only a UI action populates it — so an isolation probe against
it passes vacuously and a row-count check reads as "not used yet" rather than "not readable".

WHAT THIS CHECKS. Every table carrying an `embedding` column must have at least one READER
somewhere: a database function of any name, an edge function, or a page.

The first cut of this gate only counted retrieval through a SEARCH-NAMED pg_proc
(search_*/semantic_*/match_*), because that is the pattern project_knowledge should have joined.
Run against the platform it failed four healthy tables — asset_embeddings is searched in TypeScript
inside asset-brain-query, agent_memory is read by fetch_session_memory, and
canonical_period_summaries and unified_events are read by the temporal-RAG and summarizer
functions. None of those is a defect; the detector was simply looking in one place.

So the rule matches the evidence that actually condemned project_knowledge — nothing read it
ANYWHERE, in any layer. That is a defect no matter which retrieval style a table uses, and it is
the only claim this gate can make without inventing an architecture rule the platform never
adopted.

Needs the local database. Skips cleanly (0) when it cannot connect, like the other live gates.
"""
import glob
import io
import json
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = "supabase_db_workhive"

# Tables that legitimately hold embeddings without a retrieval function of their own.
# Each needs a REASON, not just a name.
EXEMPT = {
    "embedding_cache":
        "a cache keyed by content hash, read by the embedder itself to avoid re-embedding — it is "
        "not a retrieval corpus and has no tenant content to search.",
}

SQL = r"""
WITH emb AS (
  SELECT c.relname AS tbl
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'embedding' AND a.attnum > 0
                       AND NOT a.attisdropped
   WHERE n.nspname = 'public' AND c.relkind = 'r'
),
readers AS (
  -- ANY database function, not only search-named ones: the platform retrieves through
  -- fetch_session_memory and through TypeScript in edge functions as well as through
  -- search_all_knowledge. Narrowing this to search_* failed four healthy tables.
  SELECT p.proname, pg_get_functiondef(p.oid) AS def
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public' AND p.prokind = 'f'
)
SELECT coalesce(json_agg(row_to_json(t)), '[]'::json)::text FROM (
  SELECT emb.tbl,
         coalesce((SELECT json_agg(r.proname ORDER BY r.proname)
                     FROM readers r WHERE r.def LIKE '%%' || emb.tbl || '%%'), '[]'::json) AS readers
    FROM emb ORDER BY emb.tbl
) t;
"""


def fetch():
    try:
        out = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", SQL],
            capture_output=True, text=True, timeout=120)
    except Exception as exc:
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or "psql failed").strip()[:200]
    try:
        return json.loads(out.stdout.strip() or "[]"), None
    except Exception as exc:
        return None, "unparseable psql output: %s" % exc


def main():
    rows, err = fetch()
    if rows is None:
        print("  SKIP — local database not reachable (%s)." % err)
        return 0

    # Code-side readers: an edge function or page that names the table.
    #
    # THE WRITER IS NOT A READER. embed-entry names every knowledge table it writes into, so
    # counting it here would mark project_knowledge as "read by code" on the strength of the very
    # insert that created the problem — the gate would have passed the exact defect it exists for.
    # Skipping the writer means a table is only credited when something OTHER than its producer
    # mentions it. This is the same trap as a self-referential test asserting its own fixture.
    WRITER_PATHS = ("embed-entry",)
    code_text = []
    for pattern in ("supabase/functions/**/*.ts", "*.html"):
        for path in glob.glob(pattern, recursive=True):
            if any(w in path.replace("\\", "/") for w in WRITER_PATHS):
                continue
            try:
                code_text.append(open(path, encoding="utf-8", errors="ignore").read())
            except Exception:
                pass
    blob = "\n".join(code_text)

    orphans, ok, exempted = [], [], []
    for r in rows:
        tbl, readers = r["tbl"], list(r["readers"])
        if tbl in EXEMPT:
            exempted.append(tbl)
            continue
        in_code = tbl in blob
        if readers or in_code:
            if in_code and not readers:
                readers = ["(edge function / page)"]
            elif in_code:
                readers = readers + ["(and code)"]
            ok.append((tbl, readers))
        else:
            orphans.append(tbl)

    for tbl, readers in ok:
        print("  OK    %-28s read by %s" % (tbl, ", ".join(readers)))
    for tbl in exempted:
        print("  EXEMPT %-27s %s" % (tbl, EXEMPT[tbl]))

    if orphans:
        print("\n  FAIL — %d embedding table(s) that nothing retrieves from:\n" % len(orphans))
        for tbl in orphans:
            print("    %s" % tbl)
        print("\n  Something is paying to embed into these and no retrieval function reads them, so")
        print("  the content can never reach an answer. Either add a branch to the relevant search")
        print("  function (search_all_knowledge is the platform's unified one) or add the table to")
        print("  EXEMPT in this file with the reason it holds embeddings nobody searches.")
        return 1

    print("\n  PASS — all %d embedding table(s) are reachable from a retrieval function."
          % (len(ok) + len(exempted)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
