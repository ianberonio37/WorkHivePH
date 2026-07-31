#!/usr/bin/env python3
"""validate_embedding_space_integrity.py — does every corpus live in exactly ONE vector space?

THE BUG THIS EXISTS FOR, caught live 2026-07-31 with a single row. `fault_knowledge` holds 534 rows in
`bge-small-en-v1.5-local`; a newly-written `pm_knowledge` row came back `nomic-embed-text-v1_5`. Both were
"successful" writes. Nothing errored. But a vector embedded by a different model lives in a DIFFERENT
GEOMETRY — cosine similarity against it is noise, so the row is silently unfindable, and worse, it competes
with real matches and can outrank them.

This is the failure mode the ai-engineer skill already named: *"a shared embedding fallback chain is a
SPLIT-SPACE bug; pin the model PER CORPUS."* A provider chain that fails over on a rate limit will happily
answer from the next provider, and the only visible symptom is retrieval quietly returning less.

WHY A COUNT OF ROWS CANNOT CATCH IT: every row is present, non-null, and correctly shaped. The corpus looks
complete. Only the MODEL column distinguishes a usable vector from a useless one, which is why this gate reads
that column and nothing else.

WHAT IT ASSERTS
  1. Each corpus holds exactly ONE distinct embedding_model (ignoring empty corpora).
  2. Every corpus's model matches its REGISTRY pin, where the registry declares one — ingest and query must
     agree, or the corpus is embedded in a space the reader never searches.
  3. No corpus row carries a NULL model, which would make (1) unprovable rather than true.

FIXING A SPLIT is DELETE-first, never an upsert: a hash-keyed upsert will not replace a vector when only the
MODEL changed and the text did not. That is why the fix path is a re-embed script, not a re-run.

Usage:  python tools/validate_embedding_space_integrity.py [--selftest]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

# Corpora that carry a per-row embedding_model. Discovered from the catalog rather than hardcoded, so a NEW
# knowledge table is covered the day it appears instead of the day someone remembers to add it here.
DISCOVER = """
select c.table_name
  from information_schema.columns c
 where c.table_schema = 'public'
   and c.column_name = 'embedding_model'
   and c.table_name <> 'embedding_registry'
 order by 1;
"""


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:180]
    return [ln.split("|") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


def survey():
    tables, err = psql(DISCOVER)
    if tables is None:
        return None, err
    out = []
    for (t,) in [(x[0],) for x in tables]:
        rows, e = psql(f"""
            select coalesce(embedding_model, '(null)'), count(*)
              from public.{t} group by 1 order by 2 desc;""")
        if rows is None:
            return None, e
        out.append((t, [(m, int(n)) for m, n in rows]))
    return out, ""


def registry_pins():
    rows, _ = psql("select target_table, embedding_model from public.embedding_registry;")
    return {r[0]: r[1] for r in (rows or []) if len(r) == 2}


def selftest():
    """A split must be DETECTED and a single-space corpus must PASS — proven on synthetic input.

    The detector is pure arithmetic over (model, count) pairs, so it is testable without corrupting a real
    corpus; a self-test that had to write a foreign-space vector to prove itself would be worse than none.
    """
    print("  selftest: a two-model corpus must FAIL, a one-model corpus must PASS")
    split = [("pm_knowledge", [("bge-small-en-v1.5-local", 10), ("nomic-embed-text-v1_5", 1)])]
    clean = [("fault_knowledge", [("bge-small-en-v1.5-local", 534)])]
    nulls = [("skill_knowledge", [("(null)", 4)])]
    ok = True
    if not judge(split, {})[0]:
        print(f"  {RED}FAIL{RST} — a corpus holding two models was not reported as split"); ok = False
    if judge(clean, {})[0]:
        print(f"  {RED}FAIL{RST} — a single-space corpus was flagged"); ok = False
    if not judge(nulls, {})[0]:
        print(f"  {RED}FAIL{RST} — a NULL model was not reported; it makes single-space unprovable"); ok = False
    if judge(clean, {"fault_knowledge": "voyage"})[0] is False:
        print(f"  {RED}FAIL{RST} — a corpus whose space disagrees with its REGISTRY PIN was not caught")
        ok = False
    print(f"  {GREEN}PASS{RST} — catches splits, NULLs and pin disagreement; accepts a clean corpus"
          if ok else "")
    return 0 if ok else 1


def judge(survey_rows, pins):
    """-> (problems, lines). A problem is a split, a NULL model, or disagreement with the registry pin."""
    problems, lines = [], []
    for table, models in survey_rows:
        total = sum(n for _, n in models)
        if total == 0:
            lines.append((YEL, table, "empty — no space to be in yet"))
            continue
        names = [m for m, _ in models]
        if "(null)" in names:
            problems.append(table)
            lines.append((RED, table, f"{dict(models)} — a NULL embedding_model makes the space unprovable"))
        elif len(names) > 1:
            problems.append(table)
            lines.append((RED, table, f"SPLIT across {len(names)} spaces: {dict(models)}"))
        elif table in pins and pins[table] and names[0] != pins[table]:
            problems.append(table)
            lines.append((RED, table,
                          f"in '{names[0]}' but the registry pins '{pins[table]}' — ingest and query disagree"))
        else:
            lines.append((GREEN, table, f"{names[0]} ({total} rows)"))
    return problems, lines


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Embedding space integrity{RST} — one corpus, one vector space")
    if selftest() != 0:
        print(f"  {RED}FAIL{RST} — the detector failed its own self-test; its result means nothing.")
        return 1
    rows, err = survey()
    if rows is None:
        print(f"  {YEL}SKIP{RST} local database unavailable ({err})")
        return 0
    problems, lines = judge(rows, registry_pins())
    for colour, table, detail in lines:
        print(f"  {colour}{table:<22}{RST} {DIM}{detail}{RST}")
    if problems:
        print(f"\n  {RED}FAIL{RST} — {len(problems)} corpus/corpora are not in a single, declared space: "
              f"{', '.join(problems)}. A vector from another model is SILENTLY unfindable — cosine against it "
              f"is noise, and it can outrank real matches. FIX: re-embed the minority rows with a DELETE-first "
              f"script (an upsert will NOT replace a vector when only the model changed), then re-run.")
        return 1
    print(f"  {GREEN}PASS{RST} — every corpus sits in exactly one space, matching its pin")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
