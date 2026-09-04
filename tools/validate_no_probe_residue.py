#!/usr/bin/env python3
"""no-probe-residue - T136: demo and probe content must never read as real.

★RECONSTRUCTED 2026-08-26 after I overwrote the original with Write on a path I had not checked.
The file was untracked, so git had no copy; it was rebuilt from its own registry label, which
recorded its scope and its findings in enough detail to restore the contract. Everything the label
documents is implemented below, plus the structural residue described at the end. The lesson is the
plain one: look at the target before writing to it, especially a path you did not create.

Every walk in this program writes marked rows and deletes them, but that discipline is per-walk and
per-author - it holds exactly as well as the last person's memory, and not at all when the process
is KILLED, because a cleanup in a `finally` does not survive SIGKILL and a suite timeout kills.

WHAT THE ORIGINAL FOUND (2026-08-26, a broad sweep): 245 marker rows surviving earlier sessions -
3 in voice_journal_entries (probe transcripts AND the AI's replies to them, in the platform's most
private surface, inside a worker's own journal); 1 in logbook.knowledge ("probe: checked, within
tolerance" in a real-looking entry, whose pm_completion twin an earlier pass had removed while
missing this copy: one probe, two homes); and 241 in hive_audit_log.

★THE AUDIT ROWS ARE THE LESSON: they were written BY a prover's own cleanup. A prover created probe
assets and deleted them, and the audit trigger honestly recorded every deletion - TRUE rows
describing objects that were never real, in a compliance-class table the retention gate correctly
forbids any scheduled job from purging. A probe that touches an AUDITED table leaves residue its own
cleanup cannot reach, because the residue lands in a DIFFERENT table than the one it wrote to.
Removing it needs a deliberate scoped delete, never a cron.

★AND IT EARNED ITS KEEP ON ITS FIRST RUN: after a targeted WH-T108B cleanup it still found 34 rows
under a DIFFERENT marker (WH-EFFECT-PROBE, dating to 2026-08-18) that the scoped delete had missed -
which is why the pattern is the marker CONVENTION rather than any one campaign's tag.

★STRUCTURAL RESIDUE, added 2026-08-26: a 'WH-T6T7-PROBE Plant' from prove_invite_code_round_trip had
sat in the database ~14 hours with a live membership - not because that prover is careless (its
cleanup is in a finally and it asserts leftBehind === 0) but because it had been killed. The damage
is MEASUREMENT, not storage: it made the shared test account look like it belonged to two hives, it
appeared in that account's switcher during an unrelated verification, and it inflated the member
counts read while sizing T61's fixture. Stale test data never announces itself.

★SCOPED TO THE MARKER AND DELIBERATELY NOT THE SEEDER'S FIXTURES: demo DATA is legitimate here, and
a gate that could not tell seeded plant data from probe residue would fire forever.

★REPORTS BY DEFAULT, deletes only under --clean: a gate that silently mutates the database it is
auditing cannot tell anyone what it found.

Re-drive: python tools/validate_no_probe_residue.py [--clean]
"""
import io
import os
import re
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
CLEAN = "--clean" in sys.argv

# The marker convention, not any one campaign's tag: WH-<anything>-PROBE, plus the "probe:" prefix
# the journal/logbook walks used. Kept as SQL regexes so the scan happens in the database.
MARK = r"WH-[A-Za-z0-9]+-PROBE"
MARK_TEXT = r"WH-[A-Za-z0-9]+-PROBE|(^|\s)probe:"

# (label, table, where-clause). User-facing surfaces only - what a person could read and mistake for
# their own plant's data.
TEXT_SCANS = [
    ("voice_journal_entries.transcript", "public.voice_journal_entries", f"transcript ~* '{MARK_TEXT}'"),
    ("voice_journal_entries.reply",      "public.voice_journal_entries", f"reply ~* '{MARK_TEXT}'"),
    ("logbook.knowledge",                "public.logbook",               f"knowledge ~* '{MARK_TEXT}'"),
    ("logbook.problem",                  "public.logbook",               f"problem ~* '{MARK}'"),
    ("logbook.action",                   "public.logbook",               f"action ~* '{MARK}'"),
    ("logbook.worker_name",              "public.logbook",               f"worker_name ~* '{MARK}'"),
    ("hive_audit_log.target_name",       "public.hive_audit_log",        f"target_name ~* '{MARK}'"),
    ("hive_audit_log.actor",             "public.hive_audit_log",        f"actor ~* '{MARK}'"),
    ("asset_nodes.name",                 "public.asset_nodes",           f"name ~* '{MARK}'"),
    ("community_posts.content",          "public.community_posts",       f"content ~* '{MARK}'"),
    ("pm_completions.notes",             "public.pm_completions",        f"notes ~* '{MARK_TEXT}'"),
    ("fault_knowledge.problem",          "public.fault_knowledge",       f"problem ~* '{MARK_TEXT}'"),
    # C10 (critic deepwalk, 2026-09-02): GATE BLIND SPOT FOUND BY WALKING. The supervisor's #1
    # daily callout was an ORPHAN TEST ROW — 'Centrifugal Pump CP-201 (alert-test)', risk 91%,
    # referencing an asset that never existed in asset_nodes — dead-ending on asset-hub. 70 such
    # rows purged; this scan keeps the class out: a risk score whose asset_name matches NO node
    # (by tag, name, 'tag (name)', or tag-prefix) in its own hive is residue on a command surface.
    ("asset_risk_scores.orphans",        "public.asset_risk_scores",
     "NOT EXISTS (SELECT 1 FROM asset_nodes a WHERE a.hive_id = asset_risk_scores.hive_id "
     "AND (a.tag = asset_risk_scores.asset_name OR a.name = asset_risk_scores.asset_name "
     "OR (a.tag || ' (' || a.name || ')') = asset_risk_scores.asset_name "
     "OR asset_risk_scores.asset_name LIKE a.tag || '%' "
     "OR asset_risk_scores.asset_name LIKE '%' || a.tag || '%'))"),
]

# Structural residue: whole objects a killed prover left standing. Children before parents.
STRUCTURAL = [
    ("hive_members in probe hives", "public.hive_members",
     f"hive_id IN (SELECT id FROM public.hives WHERE name ~ '{MARK}')"),
    ("hive_audit_log in probe hives", "public.hive_audit_log",
     f"hive_id IN (SELECT id FROM public.hives WHERE name ~ '{MARK}')"),
    ("hive_members by probe worker name", "public.hive_members", f"worker_name ~ '{MARK}'"),
    ("probe hives", "public.hives", f"name ~ '{MARK}'"),
    ("probe worker_profiles", "public.worker_profiles", f"display_name ~ '{MARK}'"),
    ("probe auth users", "auth.users", r"email ~* 'wh-t[0-9]+.*probe|wh\.probe|wh-probe'"),
]


def psql(sql: str):
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
        input=sql, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")


def count(table: str, where: str):
    r = psql(f"SELECT count(*) FROM {table} WHERE {where};")
    if r.returncode != 0:
        return None                      # table or column absent - report, never guess
    m = re.search(r"(\d+)", r.stdout or "")
    return int(m.group(1)) if m else None


def main() -> int:
    if psql("SELECT 1;").returncode != 0:
        print("SKIP no-probe-residue - local database not reachable (live gate)")
        return 0

    found, unknown = [], []
    for label, table, where in TEXT_SCANS + STRUCTURAL:
        n = count(table, where)
        if n is None:
            unknown.append(label)
        elif n:
            found.append((label, table, where, n))

    for label in unknown:
        print(f"  ? {label}: could not be counted (table or column moved) - not treated as clean")

    if not found and not unknown:
        print("PASS no-probe-residue - no WH-*-PROBE rows in any user-facing surface and no probe "
              "objects left standing; every prover that wrote rows removed them.")
        return 0

    total = sum(n for _, _, _, n in found)
    if found:
        print(f"  probe residue found ({total} rows):")
        for label, _, _, n in found:
            print(f"    {n:5}  {label}")
        names = psql(f"SELECT name || ' (' || invite_code || ', created ' || created_at::date || ')' "
                     f"FROM public.hives WHERE name ~ '{MARK}';")
        for line in (names.stdout or "").strip().splitlines():
            if line.strip():
                print(f"    hive: {line.strip()}")

    if not CLEAN:
        print("FAIL no-probe-residue - probe content is sitting in surfaces a person reads as their "
              "own plant's data, or a probe object is still standing. A cleanup in a finally does not "
              "survive SIGKILL, and rows written by an audit TRIGGER land in a different table than "
              "the probe wrote to, so its own cleanup could never reach them. Remove with: "
              "python tools/validate_no_probe_residue.py --clean")
        return 1 if found else 1

    # --clean DELETES ONLY WHOLE PROBE OBJECTS. A structural hit is an entire fake thing - a probe
    # hive, its memberships, a probe auth user - and removing the row is exactly right. A TEXT hit
    # is not: the marker sits in one FIELD of a row that may be perfectly real, and deleting it
    # destroys a person's record to tidy up a string. Learned the hard way, on this file: an earlier
    # version deleted on every scan, and a teeth test that wrote "probe: checked, within tolerance"
    # into a real seeded logbook entry then had that entry deleted by the clean it was testing. The
    # text hits are REPORTED for a human to judge, because whether a row is probe-CREATED or
    # real-with-probe-text is not something a pattern can decide.
    text_hits = [(l, t, w, n) for (l, t, w, n) in found if (l, t, w) in
                 {(a, b, c) for a, b, c in TEXT_SCANS}]
    struct_hits = [(l, t, w, n) for (l, t, w, n) in found if (l, t, w) in
                   {(a, b, c) for a, b, c in STRUCTURAL}]

    for _, table, where in [(l, t, w) for (l, t, w, _) in struct_hits]:
        psql(f"DELETE FROM {table} WHERE {where};")
    removed = sum(n for _, _, _, n in struct_hits)
    left = sum(count(t, w) or 0 for _, t, w, _ in struct_hits)
    if left:
        print(f"FAIL no-probe-residue - {left} probe-object rows survived the clean; a foreign key is "
              f"holding them or the pattern does not match what is actually there")
        return 1

    if text_hits:
        kept = sum(n for _, _, _, n in text_hits)
        print(f"  removed {removed} probe-object rows; LEFT {kept} text hits in place for a human:")
        for label, _, _, n in text_hits:
            print(f"    {n:5}  {label}  <- a marker inside a field of a possibly-REAL row")
        print("FAIL no-probe-residue - the probe OBJECTS are gone, but probe text is still sitting in "
              "surfaces a person reads as their own data. These are not auto-removed on purpose: "
              "deleting the row would destroy a real record to tidy a string, and only a human can "
              "tell a probe-created row from a real one that a probe wrote into. Inspect and clear "
              "the field by hand.")
        return 1

    print(f"PASS no-probe-residue - removed {removed} probe-object rows and re-counted 0; no probe "
          f"text left in any user-facing surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
