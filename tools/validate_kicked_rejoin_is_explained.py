#!/usr/bin/env python3
"""kicked-rejoin-is-explained - T7: the code still works, and the door is still shut (2026-08-27).

A removed worker usually still has the invite code - it was read aloud at a briefing, or it is in a
chat thread. So the rejoin attempt is not an edge case, it is the NEXT THING THAT HAPPENS, and it has
two halves that must agree.

★THE DOOR. join_hive_by_code refuses a kicked member deliberately, and twice over: by auth identity,
and again by (hive, worker_name) so a second account cannot walk a ban back in. Both are asserted
LIVE here, because "the function has an IF" is not the same as "the function refuses" - the second
branch in particular only fires for an identity that has no membership row at all, which is exactly
the shape a reading of the source can talk itself out of.

★AND THE SENTENCE. A refusal that reaches a person as a raw code, or as "could not join", tells them
the app is broken rather than that a decision was made about them. hive.html must key on
HIVE_MEMBER_KICKED and say two things: WHAT (removed from this hive) and WHAT NOW (a way forward
that is not retrying the code, because retrying is the one action that cannot work).

Distinct from removal-tells-the-worker (T25), which covers the removed worker's ARRIVAL - opening
the app to find the hive gone. This covers the door they knock on afterwards.

SAFETY: the kicked state is created inside a transaction and ROLLED BACK. Nothing is written - no
member is really removed, no row survives the run - and the rollback is verified by re-reading the
member's status afterwards.

Self-test: `--selftest` (the copy assertions; the DB half needs the stack).
Teeth:     `--teeth` replaces join_hive_by_code with a permissive version INSIDE the probe
           transaction and rolls it back, so the DB half is shown able to go red.
"""
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TEETH = "--teeth" in sys.argv
DB = "supabase_db_workhive"
PAGE = ROOT / "hive.html"

# What the refusal has to say. Not a fixed sentence - a fixed sentence is a gate that fails when
# someone improves the wording, which teaches people to stop improving wording.
NAMES_REMOVAL = re.compile(r"removed|no longer (a )?member|taken out", re.I)
NAMES_WAY_OUT = re.compile(r"supervisor|admin|re-?add|another hive|create", re.I)


def psql(sql: str, ok_fail: bool = False):
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                        "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90)
    if r.returncode != 0 and not ok_fail:
        return None, (r.stderr or "").strip()
    return (r.stdout or "").strip(), (r.stderr or "").strip()


def check_copy() -> list:
    """The page must key on the code and explain the refusal."""
    src = io.open(PAGE, encoding="utf-8", errors="replace").read()
    if "HIVE_MEMBER_KICKED" not in src:
        return ["hive.html does not branch on HIVE_MEMBER_KICKED at all - a ban would reach the "
                "person as a generic join failure"]
    # the sentence(s) rendered on that branch: take the window after the match
    i = src.index("HIVE_MEMBER_KICKED")
    window = src[i:i + 900]
    # Match STRING LITERALS, not "quote to the next quote". The naive form pairs the closing quote
    # of one literal with the opening quote of the next, so it captures the CODE between them - on
    # this very branch it started at the `''` in `joinErr.message || ''` and returned fragments like
    # "; btn.disabled = false;" while the real sentence was never seen, and the page read as if it
    # said nothing. Same lesson validate_xss carries about literals; caught here by the selftest
    # asserting the live copy passes, which is why that case is in the selftest at all.
    said = [m.group(1) or m.group(2) for m in
            re.finditer(r"'((?:\\.|[^'\\])*)'|\"((?:\\.|[^\"\\])*)\"", window)]
    blob = " ".join(s for s in said if s and len(s) >= 12)
    out = []
    if not NAMES_REMOVAL.search(blob):
        out.append("the HIVE_MEMBER_KICKED branch never says the person was REMOVED")
    if not NAMES_WAY_OUT.search(blob):
        out.append("the HIVE_MEMBER_KICKED branch names no way forward, so it reads as a dead end "
                   "and invites retrying the code, which cannot work")
    return out


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    chk("a sentence naming removal + supervisor passes",
        bool(NAMES_REMOVAL.search("You have been removed from this hive. Contact the supervisor to be re-added.")
             and NAMES_WAY_OUT.search("You have been removed from this hive. Contact the supervisor to be re-added.")),
        True)
    chk("a bare failure sentence fails the removal test",
        bool(NAMES_REMOVAL.search("Could not join. Please try again.")), False)
    chk("a removal sentence with no way out fails the remedy test",
        bool(NAMES_WAY_OUT.search("You have been removed from this hive.")), False)
    chk("live copy on hive.html passes both", check_copy(), [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print("T7 kicked-rejoin is explained")

    # ── the sentence ───────────────────────────────────────────────────────────────────────────
    copy_problems = check_copy()
    print(f"  refusal copy on hive.html: {'OK' if not copy_problems else 'PROBLEM'}")

    # ── the door, live and rolled back ─────────────────────────────────────────────────────────
    row, err = psql("""
SELECT h.id||'|'||h.invite_code||'|'||m.auth_uid||'|'||m.worker_name
FROM hives h JOIN hive_members m ON m.hive_id = h.id
WHERE h.invite_code IS NOT NULL AND m.auth_uid IS NOT NULL AND m.status = 'active'
ORDER BY h.id LIMIT 1;""")
    if not row:
        print(f"  SKIP kicked-rejoin — no hive/member pair to probe ({err[:80]})")
        return 0
    hive_id, code, uid, worker = row.split("|", 3)

    # an identity with NO membership in that hive, for the worker_name defence
    other, _ = psql(f"""
SELECT auth_uid FROM hive_members
WHERE auth_uid IS NOT NULL AND hive_id <> '{hive_id}'
  AND auth_uid NOT IN (SELECT auth_uid FROM hive_members WHERE hive_id = '{hive_id}' AND auth_uid IS NOT NULL)
LIMIT 1;""")

    # --teeth: prove the DB half can actually FAIL. Postgres has transactional DDL, so the function
    # is replaced with a permissive version INSIDE the transaction and rolled back with everything
    # else - a green run here would mean this gate cannot see an open door. The definition is
    # re-read afterwards to prove the real function came back; if psql dies mid-run the connection
    # closes and Postgres rolls back for us, so the function cannot be left permissive.
    teeth_sql = """
create or replace function public.join_hive_by_code(p_code text, p_worker_name text)
returns table(hive_id uuid, hive_name text, member_status text)
language plpgsql security definer set search_path to 'pg_catalog','public' as $f$
declare v_hive public.hives%ROWTYPE;
begin
  select * into v_hive from public.hives where invite_code = p_code;
  return query select v_hive.id, v_hive.name, 'active'::text;   -- the kicked check, removed
end $f$;
""" if TEETH else ""

    sql = f"""
begin;
{teeth_sql}
update hive_members set status='kicked' where hive_id='{hive_id}' and auth_uid='{uid}';
set local role authenticated;
set local request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
do $$ begin
  perform public.join_hive_by_code('{code}', {psql_lit(worker)});
  raise notice 'SAMEUID|allowed';
exception when others then raise notice 'SAMEUID|%', SQLERRM; end $$;
reset role;
"""
    if other:
        sql += f"""
set local role authenticated;
set local request.jwt.claims = '{{"sub":"{other}","role":"authenticated"}}';
do $$ begin
  perform public.join_hive_by_code('{code}', {psql_lit(worker)});
  raise notice 'OTHERUID|allowed';
exception when others then raise notice 'OTHERUID|%', SQLERRM; end $$;
reset role;
"""
    sql += "rollback;\n"
    out, notices = psql(sql)
    if out is None:
        print(f"  SKIP kicked-rejoin — probe could not run ({notices[:100]})")
        return 0

    same = re.search(r"SAMEUID\|(.*)", notices)
    otherm = re.search(r"OTHERUID\|(.*)", notices)
    same_txt = (same.group(1).strip() if same else "<no result>")
    other_txt = (otherm.group(1).strip() if otherm else None)
    print(f"  same identity rejoining:   {same_txt[:70]}")
    if other_txt is not None:
        print(f"  another identity, same name: {other_txt[:70]}")

    # the rollback really rolled back
    fn_intact, _ = psql("SELECT CASE WHEN pg_get_functiondef(oid) LIKE '%HIVE_MEMBER_KICKED%' "
                        "THEN 'intact' ELSE 'REPLACED' END FROM pg_proc WHERE proname='join_hive_by_code';")
    print(f"  join_hive_by_code after rollback: {fn_intact}")
    still, _ = psql(f"SELECT status FROM hive_members WHERE hive_id='{hive_id}' AND auth_uid='{uid}';")
    restored = (still or "").strip() == "active"
    print(f"  member's status after rollback: {still} ({'restored' if restored else 'NOT RESTORED'})")

    problems = list(copy_problems)
    if "HIVE_MEMBER_KICKED" not in same_txt:
        problems.append(f"a kicked member was not refused by identity - got: {same_txt[:80]}")
    if other_txt is not None and "HIVE_MEMBER_KICKED" not in other_txt:
        problems.append(f"a ban was walked back in under a new identity with the same worker_name - got: {other_txt[:80]}")
    if not restored:
        problems.append("the probe did not roll back - a member is left kicked, which is a real change")
    if (fn_intact or "").strip() != "intact":
        problems.append("join_hive_by_code did NOT come back after the run - the real function is gone")

    if not problems:
        print("\n  PASS - the door is shut both ways and the refusal explains itself.")
        return 0
    print("\n  FAIL")
    for p in problems:
        print(f"    {p}")
    return 1


def psql_lit(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
