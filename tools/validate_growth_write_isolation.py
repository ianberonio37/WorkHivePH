"""validate_growth_write_isolation.py — LIVE write-integrity gate for the Growth layer
(Skill Matrix + Achievements).

Locks the I/X-axis holes found + live-exploited in the Dayplanner/Growth PDDA arc (2026-07-12,
DAYPLANNER_GROWTH_DEEP_ARC.md), fixed by:
  20260712000015_skill_profiles_bola_fix.sql        (K6)
  20260712000016_skill_exam_server_grading.sql      (K1)

  K1 (confabulation vector, live-exploited): `skill_badges` + `skill_exam_attempts` were
  CLIENT-WRITABLE and the exam was scored CLIENT-side (passed = score>=7), so a worker could
  console-mint any discipline/level badge (+250 XP via trg_skill_badge_achievement_xp) with no real
  exam — forging BOTH the Skill-Matrix credential AND Achievements XP. Now client writes are locked
  (no write policy); only the SECURITY DEFINER grade_skill_exam() — grading against the write-locked
  skill_exam_keys — writes the attempt + badge.
  K6 (BOLA): `skill_profiles` WITH CHECK was only `auth.uid() IS NOT NULL` (didn't pin auth_uid) →
  a worker could INSERT/overwrite ANOTHER worker's competency profile. Now WITH CHECK + USING pin
  auth_uid = auth.uid().

Runs a ROLLED-BACK probe against the running DB (docker psql) AS a real authenticated member and
asserts:
  1. SKILL_BADGE_INSERT_BLOCKED  — a member's direct skill_badges INSERT is rejected (self-mint).
  2. SKILL_EXAM_INSERT_BLOCKED   — a member's direct skill_exam_attempts INSERT is rejected.
  3. SKILL_PROFILE_XATTR_BLOCKED — a member's skill_profiles INSERT attributed to a FOREIGN auth_uid
                                    is rejected (the K6 BOLA).
  4. GRADER_PRESENT              — grade_skill_exam() exists + is SECURITY DEFINER (the only earn path).
  5. SKILL_BADGE_READ_OK        — the member can still SELECT their own badges (no read regression).

Actor (an active member uid) is chosen dynamically from the DB, so the gate survives a reseed.
Skips cleanly (exit 0) when docker/db is absent, matching the other *_write_isolation live gates.

Exit 0 = all invariants hold (or skipped).  Exit 1 = an invariant failed (a reverted migration).
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "growth_write_isolation_report.json"


def _psql(sql: str, stdin_mode: bool = False):
    try:
        if stdin_mode:
            p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-q", "-v", "ON_ERROR_STOP=0"],
                               input=sql, capture_output=True, text=True, timeout=40)
        else:
            p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-A", "-t", "-c", sql],
                               capture_output=True, text=True, timeout=40)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


def _skip(reason: str) -> int:
    print(f"{YELLOW}  SKIP  {reason}{RESET}")
    REPORT.write_text(json.dumps({"validator": "growth_write_isolation", "skipped": True,
                                  "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    print(f"\n{BOLD}GROWTH WRITE ISOLATION (live, K1/K6){RESET}")
    print("─" * 46)

    pick = _psql("SELECT auth_uid, worker_name FROM hive_members "
                 "WHERE status='active' AND auth_uid IS NOT NULL AND worker_name IS NOT NULL LIMIT 1;")
    if pick is None:
        return _skip("docker psql unavailable")
    _, out = pick
    row = [ln for ln in out.splitlines() if "|" in ln]
    if not row:
        return _skip("no active member fixture (need an active hive_member with auth_uid)")
    uid, worker = [c.strip() for c in row[0].split("|")]

    probe = f"""
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims TO '{{"sub":"{uid}","role":"authenticated"}}';
DO $$
DECLARE n int;
BEGIN
  BEGIN
    INSERT INTO skill_badges(worker_name, auth_uid, discipline, level, exam_score)
    VALUES('{worker}', '{uid}', 'Electrical', 5, 100);
    RAISE NOTICE 'RESULT skill_badge_insert=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT skill_badge_insert=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT skill_badge_insert=OTHER:%', SQLSTATE; END;

  BEGIN
    INSERT INTO skill_exam_attempts(worker_name, auth_uid, discipline, level, score, passed, answers)
    VALUES('{worker}', '{uid}', 'Electrical', 5, 10, true, '[]'::jsonb);
    RAISE NOTICE 'RESULT skill_exam_insert=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT skill_exam_insert=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT skill_exam_insert=OTHER:%', SQLSTATE; END;

  BEGIN
    INSERT INTO skill_profiles(worker_name, auth_uid, primary_skill)
    VALUES('GATE-VICTIM', '00000000-0000-4000-8000-00000000dead', 'HACKED');
    RAISE NOTICE 'RESULT skill_profile_xattr=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT skill_profile_xattr=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT skill_profile_xattr=OTHER:%', SQLSTATE; END;

  BEGIN
    SELECT count(*) INTO n FROM skill_badges WHERE auth_uid='{uid}';
    RAISE NOTICE 'RESULT skill_badge_read=OK';
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT skill_badge_read=FAIL:%', SQLSTATE; END;
END $$;
ROLLBACK;
"""
    res = _psql(probe, stdin_mode=True)
    if res is None:
        return _skip("docker psql unavailable (probe)")
    _, pout = res
    results = {}
    for ln in pout.splitlines():
        if "RESULT " in ln:
            body = ln.split("RESULT ", 1)[1].strip()
            if "=" in body:
                k, v = body.split("=", 1)
                results[k.strip()] = v.strip()

    # grade_skill_exam must exist + be SECURITY DEFINER (the only earn path)
    grader = _psql("SELECT prosecdef FROM pg_proc WHERE proname='grade_skill_exam' LIMIT 1;")
    grader_ok = bool(grader and (grader[1] or "").strip().lower().startswith("t"))

    checks = [
        ("skill_badge_insert_blocked", results.get("skill_badge_insert"), "BLOCKED",
         "a member CANNOT self-mint a skill_badge (competence + 250 XP forgery)"),
        ("skill_exam_insert_blocked", results.get("skill_exam_insert"), "BLOCKED",
         "a member CANNOT write a forged skill_exam_attempt"),
        ("skill_profile_xattr_blocked", results.get("skill_profile_xattr"), "BLOCKED",
         "a member CANNOT write a skill_profile attributed to another worker (BOLA)"),
        ("grader_present", "YES" if grader_ok else "NO", "YES",
         "grade_skill_exam() exists + is SECURITY DEFINER (the only server-graded earn path)"),
        ("skill_badge_read_ok", results.get("skill_badge_read"), "OK",
         "a member can still SELECT their own badges (no read regression)"),
    ]
    fails = 0
    for name, got, want, desc in checks:
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {5 - fails} pass · {fails} fail  (actor uid={uid[:8]}… worker={worker})")
    REPORT.write_text(json.dumps({"validator": "growth_write_isolation", "skipped": False,
                                  "results": results, "grader_ok": grader_ok, "fail": fails}, indent=2),
                      encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
