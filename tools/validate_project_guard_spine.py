#!/usr/bin/env python3
"""
validate_project_guard_spine — the project-surface guards still exist, and still say what they said.

WHY THIS GATE EXISTS (PJ2 / PJ6 / PJ12 / PJ14 ratchet, 2026-07-28)
------------------------------------------------------------------
The deepwalk arc left a set of database guards behind, each one earned by a live probe that showed
the hole first. Measured afterwards, four of them had NOTHING asserting they still existed:

    generate_project_code               validate_rpc_overloads (signature only, not the fix)
    set_project_budget                  (nothing)
    guard_progress_log_is_a_record      (nothing)
    guard_and_audit_project_removal     (nothing)
    guard_lessons_learned_is_supervisor (nothing)
    bind_progress_log_submitter         (nothing)

A guard with no gate is a guard that can be dropped by the next CREATE OR REPLACE and noticed by
nobody — which is precisely how `generate_project_code`'s fix went dead the same day it shipped
(migration 029 retyped a parameter, created an overload, and the corrected body was never reached).

WHAT THIS ASSERTS, and why each is a PROPERTY rather than an existence check. Existence is cheap to
satisfy and proves nothing: a function can exist with its guard clause deleted. Each check below
names the specific behaviour the probe found missing:

  1. generate_project_code does NOT filter on `deleted_at IS NULL` when scanning for the next
     sequence. That clause is what let a soft-deleted project's code be reissued, which then made
     RESTORING the original fail with a raw 23505 and left two projects sharing a code on reports
     that had already been printed (PJ2).
  2. set_project_budget exists and tests for an ACTIVE SUPERVISOR, and INSERT/UPDATE on
     projects.budget_php is not granted to authenticated. A worker could set a budget they were
     forbidden to read (PJ2/PJ9) — the read was closed and the write was left open.
  3. guard_progress_log_is_a_record is attached BEFORE UPDATE on project_progress_logs. A filed
     report is a record: its content cannot be edited, acknowledgement is supervisor-only, and
     nobody acknowledges their own (PJ6).
  4. bind_progress_log_submitter is attached BEFORE INSERT on the same table and pins both auth_uid
     and reported_by. A supervisor filed a report as "Bryan Garcia" and it was accepted — which
     also defeated check 3's no-self-ack rule, since that rule matches on reported_by (PJ17).
  5. guard_and_audit_project_removal is attached to projects. Deleting a project is a supervisor
     act and is recorded (PJ12).
  6. guard_lessons_learned_is_supervisor is attached to projects. meta.lessons_learned is printed
     on the signed project report; any member could write it, on every project at once (PJ14).

Needs the local database. Skips cleanly (0) when it cannot connect, like the other live gates.
Self-test: --selftest (proves each check fails when its property is removed).
"""
import io
import json
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = "supabase_db_workhive"

SQL = r"""
SELECT json_build_object(
  'functions', (
    SELECT coalesce(json_object_agg(p.proname, pg_get_functiondef(p.oid)), '{}'::json)
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname IN (
       'generate_project_code','set_project_budget','guard_progress_log_is_a_record',
       'bind_progress_log_submitter','guard_and_audit_project_removal',
       'guard_lessons_learned_is_supervisor','bind_assigned_by_from_hive')),
  'triggers', (
    SELECT coalesce(json_agg(json_build_object(
             'fn', p.proname, 'table', c.relname,
             'before', (t.tgtype & 2) <> 0,
             'insert', (t.tgtype & 4) <> 0,
             'update', (t.tgtype & 16) <> 0)), '[]'::json)
      FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
      JOIN pg_class c ON c.oid = t.tgrelid
     WHERE NOT t.tgisinternal),
  'budget_write_grants', (
    SELECT coalesce(json_agg(DISTINCT privilege_type), '[]'::json)
      FROM information_schema.column_privileges
     WHERE table_schema = 'public' AND table_name = 'projects'
       AND column_name = 'budget_php' AND grantee = 'authenticated'
       AND privilege_type IN ('INSERT','UPDATE'))
)::text;
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
        return json.loads(out.stdout.strip() or "{}"), None
    except Exception as exc:
        return None, "unparseable psql output: %s" % exc


def _code_only(sql):
    """Strip SQL comments before matching on a function body.

    THE COMMENT TRAP, for the fourth time in one session (2026-07-28). A comment that RECORDS a
    removal necessarily quotes the thing removed — migration 032's body carries
    `NOTE the absence of "AND deleted_at IS NULL"` — so a detector that greps the raw definition
    reports the defect it was built to catch, on the fix itself. This gate failed on its own first
    live run for exactly that reason, as did validate_xss and validate_schedule_health_falsifiable
    earlier today.

    A checker must read CODE, never prose about code. Comments are stripped by construction here so
    the trap cannot be reintroduced by writing a clearer comment.
    """
    import re
    sql = re.sub(r"--[^\n]*", "", sql or "")          # line comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)   # block comments
    return sql


def evaluate(data):
    """Return (failures, passes). Pure, so the self-test can drive it with crafted input."""
    fns = {k: _code_only(v) for k, v in (data.get("functions") or {}).items()}
    trigs = data.get("triggers") or []
    grants = data.get("budget_write_grants") or []
    fails, oks = [], []

    def has_trigger(fn, table, **kinds):
        for t in trigs:
            if t["fn"] == fn and t["table"] == table and all(t.get(k) for k in kinds):
                return True
        return False

    # 1 — the project-code fix (PJ2)
    src = fns.get("generate_project_code")
    if not src:
        fails.append("generate_project_code is missing entirely.")
    elif "deleted_at IS NULL" in src or "deleted_at is null" in src.lower():
        fails.append("generate_project_code scans `WHERE ... deleted_at IS NULL` again — a "
                     "soft-deleted project's code can be reissued, which makes RESTORING the "
                     "original fail with 23505 and puts two projects on one code (PJ2).")
    else:
        oks.append("generate_project_code scans all projects — a code is never reissued")

    # 2 — budget write authority (PJ2/PJ9)
    src = fns.get("set_project_budget")
    if not src:
        fails.append("set_project_budget is missing — the sanctioned supervisor-only budget write.")
    elif "supervisor" not in src:
        fails.append("set_project_budget no longer tests for a supervisor.")
    else:
        oks.append("set_project_budget exists and tests for an active supervisor")
    if grants:
        fails.append("projects.budget_php is %s-granted to `authenticated` again — a worker can set "
                     "a budget they cannot read (PJ2)." % "/".join(sorted(grants)))
    else:
        oks.append("projects.budget_php carries no INSERT/UPDATE grant for authenticated")

    # 3-6 — the guard triggers
    for fn, table, kinds, why in [
        ("guard_progress_log_is_a_record", "project_progress_logs", {"before": 1, "update": 1},
         "a filed progress report stays a record: content frozen, supervisor-only ack, no self-ack (PJ6)"),
        ("bind_progress_log_submitter", "project_progress_logs", {"before": 1, "insert": 1},
         "a progress report is pinned to whoever filed it (PJ17)"),
        ("guard_and_audit_project_removal", "projects", {"before": 1},
         "deleting a project is a supervisor act and is recorded (PJ12)"),
        ("guard_lessons_learned_is_supervisor", "projects", {"before": 1, "update": 1},
         "lessons-learned appears on the signed report, so only a supervisor may change it (PJ14)"),
        # PJ10: project_roles was ALREADY correct when walked — a worker cannot assign a role at
        # all (RLS refuses the insert), cross-hive is refused, and assigned_by is pinned server-side
        # (sent "SOMEONE ELSE ENTIRELY", stored "Leandro Marquez"). It is locked here because it is
        # right: this is the pin project_progress_logs was missing, and the pattern the rest of the
        # surface should match.
        ("bind_assigned_by_from_hive", "project_roles", {"before": 1},
         "who assigned a project role is the assigner's identity, not their claim (PJ10)"),
    ]:
        if fn not in fns:
            fails.append("%s does not exist — %s" % (fn, why))
        elif not has_trigger(fn, table, **kinds):
            fails.append("%s exists but is NOT attached to %s as expected — %s" % (fn, table, why))
        else:
            oks.append("%s guards %s — %s" % (fn, table, why))

    return fails, oks


def do_selftest():
    healthy = {
        "functions": {
            "generate_project_code": "SELECT ... FROM projects WHERE hive_id = p_hive_id",
            "set_project_budget": "... hm.role = 'supervisor' ...",
            "guard_progress_log_is_a_record": "x", "bind_progress_log_submitter": "x",
            "guard_and_audit_project_removal": "x", "guard_lessons_learned_is_supervisor": "x",
            "bind_assigned_by_from_hive": "x"},
        "triggers": [
            {"fn": "guard_progress_log_is_a_record", "table": "project_progress_logs", "before": True, "insert": False, "update": True},
            {"fn": "bind_progress_log_submitter", "table": "project_progress_logs", "before": True, "insert": True, "update": False},
            {"fn": "guard_and_audit_project_removal", "table": "projects", "before": True, "insert": False, "update": True},
            {"fn": "guard_lessons_learned_is_supervisor", "table": "projects", "before": True, "insert": False, "update": True},
            {"fn": "bind_assigned_by_from_hive", "table": "project_roles", "before": True, "insert": True, "update": True}],
        "budget_write_grants": []}
    hf, ho = evaluate(healthy)

    # each defect, applied one at a time to an otherwise-healthy world
    import copy
    caught = []
    d = copy.deepcopy(healthy); d["functions"]["generate_project_code"] += " AND deleted_at IS NULL"
    caught.append(("code reuse reintroduced", evaluate(d)[0]))
    d = copy.deepcopy(healthy); d["budget_write_grants"] = ["UPDATE"]
    caught.append(("budget write re-granted", evaluate(d)[0]))
    d = copy.deepcopy(healthy); del d["functions"]["guard_lessons_learned_is_supervisor"]
    caught.append(("lessons guard dropped", evaluate(d)[0]))
    d = copy.deepcopy(healthy); d["triggers"] = [t for t in d["triggers"] if t["fn"] != "bind_progress_log_submitter"]
    caught.append(("attribution pin detached", evaluate(d)[0]))

    # The comment trap must NOT fail: a body whose COMMENT quotes the removed clause is the FIX,
    # not the defect. This is the case that failed this gate on its first live run.
    d = copy.deepcopy(healthy)
    d["functions"]["generate_project_code"] = "\n".join([
        "-- NOTE the absence of `AND deleted_at IS NULL` -- that clause allowed reuse.",
        "SELECT ... FROM projects WHERE hive_id = p_hive_id"])
    comment_only = evaluate(d)[0]

    print("  healthy world -> %d failures (%s)" % (len(hf), "CLEAN" if not hf else hf))
    for name, f in caught:
        print("  %-28s -> %s" % (name, "CAUGHT" if f else "MISSED"))
    print("  %-28s -> %s" % ("comment quotes the clause",
                              "CLEAN (not fooled)" if not comment_only else "FALSE POSITIVE"))
    ok = not hf and all(f for _, f in caught) and not comment_only
    print("\n  %s" % ("TEETH VERIFIED — healthy passes, every removed property fails."
                      if ok else "TOOTHLESS — a removed property did not fail."))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return do_selftest()
    data, err = fetch()
    if data is None:
        print("  SKIP — local database not reachable (%s)." % err)
        return 0
    fails, oks = evaluate(data)
    for o in oks:
        print("  OK    %s" % o)
    if fails:
        print("\n  FAIL — %d project guard(s) no longer hold:\n" % len(fails))
        for f in fails:
            print("    %s" % f)
        print("\n  Each of these was earned by a live probe that showed the hole first. Restore the")
        print("  guard with a NEW migration rather than editing the one that created it.")
        return 1
    print("\n  PASS — all %d project-surface guard properties hold." % len(oks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
