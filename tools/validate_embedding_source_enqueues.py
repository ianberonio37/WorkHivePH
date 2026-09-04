#!/usr/bin/env python3
"""embedding-source-enqueues - T31: a registered knowledge source must actually enqueue.

The RAG corpus is built by a mirror: `embedding_registry` names each source table and
the knowledge table it feeds (logbook -> fault_knowledge, pm_completions -> pm_knowledge,
skill_badges -> skill_knowledge), a trigger enqueues each new row into
`embedding_outbox`, and `embed-entry` drains it. Registering a source WITHOUT its
enqueue trigger produces the quietest possible failure: the config says the source is
active, the knowledge table simply never grows, and nothing anywhere reports a problem
because nothing errored.

THE ASSERTION: every active row in embedding_registry has a matching enqueue trigger on
its source table. Measured 2026-08-26: 3 of 3.

★WHAT THIS DELIBERATELY DOES NOT ASSERT, and why. The outbox currently holds 6,223
pending rows (logbook 4,617 of 8,058; pm_completions 1,606 of 1,611). That reads like a
broken pipeline and it is not: the drain is `embed-entry` called FROM THE BROWSER at
write time, so rows inserted by the SEEDER - with no browser present - enqueue and sit.
Last drain 2026-08-20, when someone last worked through the UI. Gating on backlog depth
would therefore be a permanent red against a fixture, which is how a gate teaches people
to ignore it.

★THE ARCHITECTURAL POINT IS RECORDED RATHER THAN GATED: the outbox has no drainer other
than a client. Any write that does not pass through a browser - a seeder, a CSV import,
the server-side PM mirror - enqueues and never drains, and no cron backstops it. Whether
to add a scheduled drain is a real decision (it costs embedding calls), so it belongs to
Ian, not to this gate.

Usage: python tools/validate_embedding_source_enqueues.py
"""
import io
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

SQL = """
SELECT r.source_table,
       r.target_table,
       (SELECT count(*) FROM pg_trigger t
          JOIN pg_class c ON c.oid = t.tgrelid
         WHERE NOT t.tgisinternal
           AND c.relname = r.source_table
           AND t.tgname ILIKE '%embed%') AS enqueue_triggers
FROM embedding_registry r
WHERE r.active
ORDER BY 1;
"""


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP embedding-source-enqueues - docker not available (the schema is the oracle)")
        return 0
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("SKIP embedding-source-enqueues - local stack down")
        return 0

    rows = [l.split("|") for l in r.stdout.strip().splitlines() if l.count("|") == 2]
    if not rows:
        print("SKIP embedding-source-enqueues - embedding_registry has no active rows")
        return 0

    missing = [(src, tgt) for src, tgt, n in rows if n.strip() in ("0", "")]
    print(f"  active knowledge sources: {len(rows)} | without an enqueue trigger: {len(missing)}")
    for src, tgt, n in rows:
        print(f"    {src} -> {tgt}  (enqueue triggers: {n})")
    if missing:
        print(f"FAIL embedding-source-enqueues - {len(missing)} registered source(s) never enqueue:")
        for src, tgt in missing:
            print(f"    - {src} is active in embedding_registry and feeds {tgt}, but no trigger puts "
                  f"its rows in embedding_outbox")
        print("    This is the quietest failure the RAG corpus can have: the config says active, the")
        print("    knowledge table never grows, and nothing errors. Add the enqueue trigger, or")
        print("    deactivate the row so the registry stops claiming a source it does not collect.")
        return 1
    print(f"PASS embedding-source-enqueues - all {len(rows)} active knowledge sources enqueue their "
          f"rows for embedding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
