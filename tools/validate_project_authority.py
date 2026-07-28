#!/usr/bin/env python3
"""
validate_project_authority.py — PJK3: authority is enforced where the DATA is, not in the renderer.

THE CLASS. project-manager.html carried three claims that only its renderer believed. Each was
probed live as an ordinary worker and each was true of the screen and false of the database:

  budget            renderBudget() printed "Budget visibility is restricted to supervisors" while
                    projects_hive_rw granted every active member SELECT. A worker read
                    CAP-2026-001's PHP 1,850,000 straight off the table. Worse, budget_php was in
                    the MAIN list select for everyone, so the figure was already in the browser
                    before any pane decided whether to show it.
  project removal   the Delete button carried no role check and neither did the database — a worker
                    soft-deleted a shutdown project they did not own, and hive_audit_log held ZERO
                    rows for projects, so it vanished with nothing able to say it had existed.
  acknowledgement   ackLog() wrote acknowledged_by = WORKER_NAME with no role check, so any member
                    could acknowledge any progress report — including their own.

A UI-only gate is not a control; it is a label. This gate asserts that each of those three is now
enforced in the DATABASE, where a client cannot route around it.

WHY IT CHECKS MECHANISMS AND NOT JUST NAMES: the budget one is enforced by COLUMN PRIVILEGES, and a
column-level REVOKE is a NO-OP while a table-level GRANT stands — that is how the first attempt
failed silently, with information_schema still listing authenticated on budget_php while the page
looked fixed. So the check is "authenticated must NOT hold SELECT on budget_php", asked of the
catalog, not "a migration mentions REVOKE".

Live tier SKIPS cleanly (exit 0) without docker. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent

# (label, SQL returning exactly one value, expected, why it matters if it flips)
CHECKS = [
    ("budget withheld from authenticated",
     "SELECT count(*) FROM information_schema.column_privileges "
     "WHERE table_name='projects' AND column_name='budget_php' "
     "AND grantee IN ('authenticated','anon') AND privilege_type='SELECT'",
     "0",
     "a client role can read budget_php again — and note a column REVOKE alone will NOT achieve "
     "this while a table-wide GRANT stands, which is exactly how the first fix silently failed"),

    ("budget absent from v_project_truth",
     "SELECT count(*) FROM information_schema.columns "
     "WHERE table_name='v_project_truth' AND column_name='budget_php'",
     "0",
     "the truth view is security_invoker, so re-adding the column both re-opens the read and breaks "
     "every select('*') caller the moment the base column is revoked"),

    ("supervisor-only budget RPC exists",
     "SELECT count(*) FROM pg_proc WHERE proname='get_project_budget' AND prosecdef",
     "1",
     "the sanctioned path is gone, so supervisors lose the figure entirely"),

    ("project removal guarded + audited",
     "SELECT count(*) FROM pg_trigger WHERE tgname='trg_project_removal_guard_audit' "
     "AND NOT tgisinternal AND tgenabled <> 'D'",
     "1",
     "any member can soft-delete any project again, and nothing records it"),

    ("progress report is a record",
     "SELECT count(*) FROM pg_trigger WHERE tgname='trg_progress_log_is_a_record' "
     "AND NOT tgisinternal AND tgenabled <> 'D'",
     "1",
     "a worker can rewrite another worker's report and self-acknowledge it again"),

    ("change-order terms immutable",
     "SELECT count(*) FROM pg_trigger WHERE tgname='trg_change_order_terms_immutable' "
     "AND NOT tgisinternal AND tgenabled <> 'D'",
     "1",
     "a pending contract amendment becomes editable by anyone in the hive again"),
]

# The renderer claims that must stay TRUE now that the database backs them. If a claim is removed
# while its enforcement stands the page silently under-promises, which is far less bad — so these
# are advisory, and only the DB checks fail the gate.
PAGE_CLAIMS = [
    ("project-manager.html", "Budget visibility is restricted to supervisors"),
]


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
        return None if p.returncode != 0 else (p.stdout or "").strip().splitlines()[0].strip()
    except Exception:
        return None


def selftest():
    probs = []
    if len(CHECKS) < 6:
        probs.append("CHECKS shrank — a UI-only-gate fix lost its database assertion")
    if not any("column_privileges" in c[1] for c in CHECKS):
        probs.append("the budget check must ask the CATALOG about privileges, not grep a migration")
    if not all(c[2] in ("0", "1") for c in CHECKS):
        probs.append("every check must be a single scalar with an exact expected value")
    if probs:
        print("SELFTEST FAIL:")
        for x in probs:
            print("  " + x)
    else:
        print("SELFTEST PASS")
    return 1 if probs else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print(f"\n{BOLD}PROJECT AUTHORITY (enforced at the DATA, not in the renderer){RESET}")
    print("-" * 74)

    for page, claim in PAGE_CLAIMS:
        f = ROOT / page
        if f.exists() and claim in f.read_text(encoding="utf-8", errors="replace"):
            print(f"  {GREEN}INFO{RESET}  {page} still tells the user: \"{claim}\"")
        else:
            print(f"  {YELLOW}INFO{RESET}  {page} no longer makes that claim (enforcement below still applies)")

    if psql("SELECT 1;") is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable")
        return 0

    fails = 0
    report = {}
    for label, sql, want, why in CHECKS:
        got = psql(sql)
        report[label] = got
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {label} (got {got!r}, want {want!r}) — {why}")

    print(f"\n  Summary: {len(CHECKS) - fails} pass · {fails} fail")
    (ROOT / "project_authority_report.json").write_text(
        json.dumps({"validator": "project_authority", "results": report, "fail": fails}, indent=2),
        encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
