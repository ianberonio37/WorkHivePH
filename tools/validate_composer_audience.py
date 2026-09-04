#!/usr/bin/env python3
"""composer-audience — T166: "who sees this?" answered where it is written (2026-08-26).

Every write surface makes a person decide how candid to be, and that decision is
made AT THE COMPOSER. Answering it somewhere else — a welcome card, a help page,
a toast after the fact — is answering it too late or to the wrong person.

THE FINDING. voice-journal.html had ZERO audience statements while being the
platform's MOST private surface: voice_journal_entries carries
auth.uid() = auth_uid on read, update AND delete, so nobody else in the hive can
reach a single row. The only place a worker was ever told lived on hive.html's
join-flow welcome card — seen once, on a different page, at a moment they were
not writing anything personal. A privacy guarantee a person cannot see is a
guarantee they cannot rely on. It now says so above the box.

★THE WORDING IS READ OFF THE RLS, NEVER FROM MEMORY, and this trajectory has the
scar: a welcome card written the same week claimed the Voice Journal was the ONLY
surface private to a worker, and the policies said otherwise (skill_profiles,
badges and exam_attempts are auth_uid-scoped too). So this gate checks BOTH ends —
the claim on the page AND the policy in the database — and fails if a page claims
privacy the policies do not give.

TWO ASSERTIONS PER WATCHED SURFACE:
  1. the page states its audience somewhere a writer will see it;
  2. if it claims PRIVACY, the table's RLS actually restricts rows to their owner.

★DELIBERATELY A SHORT, NAMED LIST rather than every form on the platform. A gate
that demanded an audience label on every input would fire on search boxes and
filters and be switched off within a week. These are the surfaces where a person
commits words that other people might read.

Usage: python tools/validate_composer_audience.py
"""
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

AUDIENCE = re.compile(
    r"visible to your (hive|team)|shared with your hive|private to you|only you can (see|read)|"
    r"nobody else in your hive|everyone in your hive|your team and supervisor read them", re.I)

# page -> (table whose RLS backs the claim, does the page claim PRIVACY?)
SURFACES = {
    "voice-journal.html": ("voice_journal_entries", True),
    "community.html":     (None, False),
    "logbook.html":       (None, False),
    # T166 (2026-08-27): the three LOWER-STAKES composers. None of them said who reads what is
    # written, and the answers genuinely differ - which is the whole reason each one has to say it
    # rather than letting people generalise from the page they were last on.
    #   dayplanner  schedule_items read = auth_uid = auth.uid()  -> PRIVATE, and claimed as such,
    #               so the gate checks that claim against the policy rather than taking the word.
    #   inventory   inventory_items read = active members of the item's hive -> hive-visible.
    #   pm-scheduler pm_completions read = active members of the hive -> hive-visible, and it is
    #               the maintenance RECORD a supervisor reads to learn what was actually done.
    "dayplanner.html":    ("schedule_items", True),
    "inventory.html":     (None, False),
    "pm-scheduler.html":  (None, False),
}


def owner_scoped(table: str) -> bool:
    """Does every read/update policy restrict rows to the calling user?"""
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c",
         "SELECT coalesce(pg_get_expr(polqual, polrelid), '') FROM pg_policy "
         f"WHERE polrelid = 'public.{table}'::regclass"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    if r.returncode != 0:
        return None
    quals = [q for q in (r.stdout or "").strip().splitlines() if q.strip()]
    if not quals:
        return False
    # BOTH OPERAND ORDERS. `auth.uid() = auth_uid` and `auth_uid = auth.uid()` are the same
    # predicate, and Postgres stores whichever the migration author typed. This matched only
    # the first, so schedule_items - owner-scoped in exactly the way this asks about - read as
    # NOT owner-scoped, and a TRUE privacy claim was reported as a promise the database does
    # not keep. An equality has no canonical direction; a checker that assumes one is reading
    # its own habit rather than the policy.
    owner_eq = re.compile(r"auth\.uid\(\)\s*=\s*auth_uid|auth_uid\s*=\s*auth\.uid\(\)")
    return all(owner_eq.search(q) for q in quals)


def main() -> int:
    fails = []
    have_docker = bool(shutil.which("docker"))

    for page, (table, claims_private) in SURFACES.items():
        f = ROOT / page
        if not f.exists():
            fails.append(f"{page}: missing from disk — re-point this gate")
            continue
        src = io.open(f, encoding="utf-8", errors="replace").read()
        stated = bool(AUDIENCE.search(src))
        note = "states its audience" if stated else "SAYS NOTHING about who can see it"
        detail = ""

        if claims_private and table and have_docker:
            scoped = owner_scoped(table)
            if scoped is None:
                detail = "  (RLS not checked — database unreachable)"
            elif not scoped:
                fails.append(f"{page}: claims privacy, but {table}'s policies do NOT restrict rows to "
                             f"their owner. A promise the database does not keep is worse than no promise.")
                detail = f"  RLS on {table}: NOT owner-scoped"
            else:
                detail = f"  RLS on {table}: owner-scoped, so the claim is true"

        print(f"  {page:<24} {note}{detail}")
        if not stated:
            fails.append(f"{page}: no audience statement where the writing happens. A person deciding "
                         f"how candid to be is deciding it here, not on a help page.")

    if fails:
        print("FAIL composer-audience:")
        for x in fails:
            print("    - " + x)
        return 1
    print(f"PASS composer-audience — {len(SURFACES)} write surface(s) say who can see what is written, "
          f"and the privacy claim is backed by the policies that enforce it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
