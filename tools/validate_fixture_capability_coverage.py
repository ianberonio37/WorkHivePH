#!/usr/bin/env python3
"""
validate_fixture_capability_coverage.py — HK2 gate: a shipped capability must be EXERCISABLE by the
data that actually exists, not merely by the seeder code that could create it.

WHY THIS EXISTS (the hive deepwalk, 2026-07-27). The hive switcher shipped, worked, and was
UNWALKABLE BY CONSTRUCTION: seeded data was strictly one worker to one hive, so the switcher list was
always length 1 and the switch path had never once been exercised. When a fixture was finally added,
the very first walk found a real defect in it (the member list was refreshed only when the user had
NO active hive, so a membership granted after sign-in stayed invisible until sign-out).

Then the class proved itself a second time, and this is the reason the gate queries the LIVE DB
rather than reading the seeder: walking H8 (remove a member) DELETED the platform's only multi-hive
membership. The seeder still contained the code to create one. The capability was silently unwalkable
again anyway. A gate that had read seeder source would have said PASS while the fixture was gone.

So the assertion is deliberately about live rows: for each capability below, does data exist RIGHT NOW
that can reach it? "The seeder can make one" is not the same claim and is not the one that failed.

FAILURE MODE THIS PREVENTS: a green test suite over a capability nobody can enter — the most
expensive kind of false confidence, because it looks exactly like coverage.

Skips clean when the local DB is down (this is a fixture check, not an uptime check) — same
convention as the other live gates. Self-test: `--selftest` (pure logic, no DB).
"""
from __future__ import annotations
import io, subprocess, sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# (id, capability in user terms, SQL returning ONE integer, minimum, why it matters / what breaks)
FIXTURES = [
    (
        "multi_hive_worker",
        "Hive switcher — a worker who belongs to 2+ hives",
        "select count(*) from (select worker_name from public.hive_members "
        "where status = 'active' group by worker_name having count(*) > 1) t;",
        1,
        "With every worker in exactly one hive the switch button is hidden by design (it renders only "
        "when the list length exceeds 1), so the entire switch path — re-deriving hive id, name AND "
        "role together — is unreachable. This is the fixture the H8 walk itself consumed.",
    ),
    (
        "supervisor_and_worker",
        "Role-split board — at least one supervisor and one non-supervisor",
        "select least("
        "  (select count(*) from public.hive_members where status='active' and role='supervisor'),"
        "  (select count(*) from public.hive_members where status='active' and role <> 'supervisor'));",
        1,
        "Supervisor-only chrome and the worker view can only be diffed against each other if both "
        "personas exist. With one role seeded, every role-boundary check silently tests one side.",
    ),
    (
        "multi_member_hive",
        "Member list / remove-member — a hive with 2+ members",
        "select count(*) from (select hive_id from public.hive_members where status='active' "
        "group by hive_id having count(*) > 1) t;",
        1,
        "A single-member hive cannot exercise the member list, role change, or removal flows: there "
        "is nobody to act upon.",
    ),
    (
        "kicked_membership",
        "Revocation / rejoin-blocked — a membership with status='kicked'",
        "select count(*) from public.hive_members where status = 'kicked';",
        1,
        "hive.html ships an explicit rejoin-blocked path — the initHive kicked check, and submitJoin's "
        "'You have been removed from this hive. Contact the supervisor to be re-added.' — but with no "
        "kicked row anywhere, that branch and that copy had never been exercised by anything except a "
        "hand-written UPDATE. Found by the HK2 sweep on 2026-07-27, the same shipped-but-unwalkable "
        "shape as the hive switcher. A kicked row is inert for every other query (membership reads "
        "filter status='active' or neq 'kicked'), so the fixture costs nothing elsewhere.",
    ),
]


def _psql(sql: str, timeout: int = 20):
    return subprocess.run(
        ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _db_up() -> bool:
    try:
        r = _psql("select 1;", timeout=10)
        return r.returncode == 0 and r.stdout.strip().startswith("1")
    except Exception:
        return False


def _scalar(sql: str) -> int:
    try:
        r = _psql(sql)
        return int((r.stdout or "").strip())
    except Exception:
        return -1


def evaluate(results: dict[str, int]) -> list[tuple[str, int, int]]:
    """Pure: given {fixture_id: observed}, return [(id, observed, minimum)] for every shortfall.

    A -1 means the query itself failed; that is a shortfall too, never a silent pass — the whole
    point of this gate is that "I could not tell" must not read as "covered"."""
    out = []
    for fid, _label, _sql, minimum, _why in FIXTURES:
        got = results.get(fid, -1)
        if got < minimum:
            out.append((fid, got, minimum))
    return out


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    full = {fid: 5 for fid, *_ in FIXTURES}
    chk("all fixtures present is clean", evaluate(full), [])

    # The exact H8 regression: the multi-hive membership was deleted by a walk.
    gone = dict(full, multi_hive_worker=0)
    chk("consumed multi-hive fixture is caught", evaluate(gone), [("multi_hive_worker", 0, 1)])

    # A failed query must NOT be read as coverage.
    unknown = dict(full, multi_member_hive=-1)
    chk("query failure counts as a shortfall", evaluate(unknown), [("multi_member_hive", -1, 1)])

    chk("exactly-at-minimum passes", evaluate({fid: 1 for fid, *_ in FIXTURES}), [])
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print(f"{BOLD}Fixture capability coverage (can the data that EXISTS reach the feature?){RESET}")
    if not _db_up():
        print(f"  {YELLOW}SKIP{RESET}  local DB unreachable — fixture coverage not assessed")
        return 0

    results = {fid: _scalar(sql) for fid, _label, sql, _min, _why in FIXTURES}
    short = evaluate(results)

    for fid, label, _sql, minimum, why in FIXTURES:
        got = results.get(fid, -1)
        mark = f"{GREEN}OK  {RESET}" if got >= minimum else f"{RED}FAIL{RESET}"
        shown = "query failed" if got < 0 else f"{got} found (need {minimum})"
        print(f"  {mark}  {label}: {shown}")
        if got < minimum:
            print(f"        {YELLOW}why it matters:{RESET} {why}")

    if short:
        print(f"\n  {RED}FAIL{RESET}  {len(short)} capability/ies cannot be exercised by current data.")
        print(f"  {YELLOW}Fix:{RESET} reseed (test-data-seeder), or restore the specific rows a walk consumed. "
              f"A walk that deletes a fixture must put it back — that is how this regressed on 2026-07-27.")
        return 1
    print(f"  {GREEN}PASS{RESET}  all {len(FIXTURES)} capability fixtures present in live data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
