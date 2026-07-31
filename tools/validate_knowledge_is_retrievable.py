#!/usr/bin/env python3
"""validate_knowledge_is_retrievable.py — is the hive's written knowledge FINDABLE, or only stored?

The S9-knowledge layer's second question, and the one [[feedback_write_only_index_and_hidden_nav]] insists on:
*who READS this?* A logbook entry is the hive's memory of a failure — what broke, why, what fixed it. It earns
its keep only if someone can FIND it months later, which means it must reach `fault_knowledge` (the embedded,
semantically searchable copy, keyed `logbook_id`). A logbook row with no `fault_knowledge` row is written-only:
it is on the board and invisible to every search, every RAG answer, and every "has this happened before?".

MEASURED 2026-07-31: **3,811 logbook rows, 533 embedded — 3,278 (86%) not retrievable.**

The denominator is the honest one. `embed-entry` legitimately SKIPS an entry whose composed text is under 50
characters ("insufficient context for semantic retrieval"), so this gate composes the SAME text the function
does — Equipment / Problem / Root cause / Action taken / Lesson learned / Category — and counts only rows that
would actually qualify. On this database **zero** rows are short enough to be skipped, so the 86% is a real
gap and not an artifact of the filter. Reproducing the function's own rule rather than counting raw rows is
what stops this gate from inventing a backlog ([[feedback_short_denominator_is_a_false_100]] inverted).

WHY THE BACKLOG EXISTS, which matters for reading the number: the trigger that was supposed to embed these
rows POSTed them to a PRODUCTION url (see `local-triggers-dont-call-prod`), so the embeddings landed in
production while the local index stayed empty — and that trigger is now DISABLED. Backfilling means running
3,278 embeddings through the free-tier chain, which is a deliberate, costed decision, not something a gate
should do behind anyone's back. So this is a FORWARD-ONLY ratchet: the uncovered count may FALL, never rise.
A new write surface that skips the index makes it rise, and that is the regression worth catching.

Usage:  python tools/validate_knowledge_is_retrievable.py [--selftest] [--update-baseline]
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "knowledge_retrievability_baseline.json")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

# The SAME composition embed-entry uses, so the qualifying set matches the function's own rule.
COMPOSED = """concat_ws('. ',
      nullif('Equipment: '||coalesce(l.machine,''),'Equipment: '),
      nullif('Problem: '||coalesce(l.problem,''),'Problem: '),
      nullif('Root cause: '||coalesce(l.root_cause,''),'Root cause: '),
      nullif('Action taken: '||coalesce(l.action,''),'Action taken: '),
      nullif('Lesson learned: '||coalesce(l.knowledge,''),'Lesson learned: '),
      nullif('Category: '||coalesce(l.category,''),'Category: '))"""

QUERY = f"""
with composed as (
  select l.id, length({COMPOSED}) as tlen,
         exists(select 1 from public.fault_knowledge f where f.logbook_id = l.id) as embedded
  from public.logbook l)
select
  (select count(*) from composed where tlen >= 50) || '|' ||
  (select count(*) from composed where tlen >= 50 and embedded) || '|' ||
  (select count(*) from composed where tlen >= 50 and not embedded) || '|' ||
  (select count(*) from composed where tlen < 50);
"""


def measure():
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-c", QUERY],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:140]
    line = next((l for l in (r.stdout or "").splitlines() if l.count("|") == 3), "")
    if not line:
        return None, "query returned no row"
    q, e, u, short = (int(x) for x in line.split("|"))
    return {"qualifying": q, "embedded": e, "uncovered": u, "skipped_short": short}, ""


def selftest():
    """The composed-text rule must MATCH the function's, or the denominator is fiction.

    Asserts the SQL composition reproduces embed-entry's 50-char rule on a known pair: a rich entry
    qualifies, a bare one does not. Without this the gate could count every row and report a backlog the
    product would never have embedded anyway.
    """
    print("  selftest: the qualifying rule must reproduce embed-entry's own 50-char filter")
    probe = f"""
    with l as (select 'PUMP-207'::text machine, 'Seal leaking badly on the outboard side'::text problem,
                      'Worn mechanical seal'::text root_cause, 'Replaced seal and aligned shaft'::text action,
                      null::text knowledge, 'Breakdown / Corrective'::text category
               union all
               select null, 'x', null, null, null, null)
    select length({COMPOSED}) >= 50 from l;"""
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-c", probe],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        print(f"  {YEL}SKIP{RST} local database unavailable ({e})")
        return 0
    vals = [v.strip() for v in (r.stdout or "").splitlines() if v.strip() in ("t", "f")]
    if vals[:2] == ["t", "f"]:
        print(f"  {GREEN}PASS{RST} — a rich entry qualifies, a bare one is skipped, same as the function")
        return 0
    print(f"  {RED}FAIL{RST} — the composition does not reproduce the function's rule (got {vals[:2]}); "
          f"the qualifying denominator cannot be trusted.")
    return 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Knowledge retrievability{RST} — is a written logbook entry FINDABLE, or only stored?")
    if selftest() != 0:
        return 1
    m, err = measure()
    if m is None:
        print(f"  {YEL}SKIP{RST} local database unavailable ({err})")
        return 0

    pct = (100.0 * m["embedded"] / m["qualifying"]) if m["qualifying"] else 100.0
    print(f"  {m['qualifying']} qualifying logbook entries · {m['embedded']} retrievable "
          f"({pct:.1f}%) · {DIM}{m['skipped_short']} too short for the function to embed{RST}")
    if m["uncovered"]:
        print(f"  {YEL}{m['uncovered']} entries are WRITTEN-ONLY{RST} — on the board, invisible to every "
              f"search, RAG answer and 'has this happened before?'")

    base = None
    if os.path.exists(BASELINE):
        try:
            base = json.load(open(BASELINE, encoding="utf-8")).get("uncovered")
        except Exception:
            base = None

    def write():
        json.dump({"uncovered": m["uncovered"], "qualifying": m["qualifying"],
                   "embedded": m["embedded"],
                   "_doc": "FORWARD-ONLY: logbook entries that WOULD qualify for embedding (embed-entry's own "
                           "50-char rule) but have no fault_knowledge row. May only FALL. It does not fail on "
                           "the existing backlog, which needs 3,278 free-tier embedding calls and is a costed "
                           "decision; it fails when a NEW write surface skips the index."},
                  open(BASELINE, "w", encoding="utf-8"), indent=2)

    if "--update-baseline" in argv or base is None:
        write()
        print(f"  {DIM}baseline set to {m['uncovered']} uncovered{RST}")
        return 0
    if m["uncovered"] > base:
        print(f"  {RED}FAIL{RST} — written-only entries ROSE {base} -> {m['uncovered']}. A new write path is "
              f"putting knowledge on the board without indexing it, so it cannot be found again.")
        return 1
    if m["uncovered"] < base:
        write()
        print(f"  {GREEN}PASS{RST} — ratcheted {base} -> {m['uncovered']}")
        return 0
    print(f"  {GREEN}PASS{RST} — holds at {m['uncovered']} (forward-only; the backlog needs a costed backfill)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
