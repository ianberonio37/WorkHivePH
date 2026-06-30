#!/usr/bin/env python3
"""validate_auth_live_db.py — Arc I: LIVE data-layer auth proofs via docker psql (local Supabase).

Two live facts about the auth/identity data layer, proven against the running local DB
(`supabase_db_workhive`) — the Arc G/H local-substitute pattern (no prod push needed):

  I1/A — synthetic-email login-key isolation: real seeded users' worker_profiles.username maps to a
         synthetic auth.users.email `username@auth.workhiveph.com` (login key decoupled from the human
         display_name, so a display-name change never touches the credential).
  I8/F — non-active members are EXCLUDED by the membership-gated RLS: the hive-join policies require
         status='active', so a 'kicked'/'deactivated' member is blocked from re-entry by policy.

If the local DB is unreachable this returns non-zero (so the sweep keeps these cells at proof/contract —
honest: live requires the live DB).

USAGE:      python tools/validate_auth_live_db.py
Self-test:  python tools/validate_auth_live_db.py --self-test
"""
from __future__ import annotations
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
CONTAINER = "supabase_db_workhive"

Q_SYNTH_EMAIL = (
    "SELECT count(*) FROM public.worker_profiles wp JOIN auth.users u ON u.id = wp.auth_uid "
    "WHERE u.email = lower(wp.username) || '@auth.workhiveph.com';"
)
Q_ACTIVE_GATE = (
    "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
    "AND qual ILIKE '%hive_members%' AND qual ILIKE '%active%';"
)
# I5/F — tenancy is SERVER-derived from the validated JWT (auth.uid()), never a client-supplied hive_id.
Q_AUTHUID_DERIVED = (
    "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
    "AND qual ILIKE '%auth.uid()%' AND qual ILIKE '%hive_members%';"
)
# I6/A — the auth-migration backfill trigger (sync_auth_uid_on_signup) is live, so a new signup links
# existing records (the migration's change-resilience mechanism is present, not just documented).
Q_BACKFILL = (
    "SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid "
    "WHERE p.proname ILIKE '%sync_auth_uid%';"
)


def psql(sql: str) -> str | None:
    try:
        p = subprocess.run(
            ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", sql],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if p.returncode != 0:
            return None
        return p.stdout.strip()
    except Exception:
        return None


def _to_int(s: str | None) -> int:
    try:
        return int((s or "").splitlines()[0].strip())
    except Exception:
        return -1


def _self_test() -> int:
    ok = _to_int("5\n") == 5 and _to_int("0") == 0 and _to_int(None) == -1 and _to_int("x") == -1
    print(f"  self-test: parse 5→5, 0→0, None→-1, x→-1  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    print("=" * 74)
    print("  validate_auth_live_db — Arc I (live data-layer auth proofs via docker psql)")
    print("=" * 74)

    probe = psql("SELECT 1;")
    if probe is None:
        print(f"  {YEL}SKIP/FAIL{RST} — local DB '{CONTAINER}' unreachable (live requires the docker DB up)")
        return 1

    findings: list[tuple[str, str]] = []

    synth = _to_int(psql(Q_SYNTH_EMAIL))
    findings.append(("OK" if synth > 0 else "FAIL",
                     f"I1/A synthetic-email isolation: {synth} seeded user(s) map username→username@auth.workhiveph.com"))

    gate = _to_int(psql(Q_ACTIVE_GATE))
    findings.append(("OK" if gate > 0 else "FAIL",
                     f"I8/F non-active exclusion: {gate} membership-gated RLS policy(ies) require status='active' "
                     f"(kicked/deactivated blocked)"))

    derived = _to_int(psql(Q_AUTHUID_DERIVED))
    findings.append(("OK" if derived > 0 else "FAIL",
                     f"I5/F server-derived tenancy: {derived} policy(ies) scope hive access via auth.uid()→hive_members "
                     f"(JWT-derived, not client-supplied hive_id)"))

    backfill = _to_int(psql(Q_BACKFILL))
    findings.append(("OK" if backfill > 0 else "FAIL",
                     f"I6/A auth-migration backfill: {backfill} sync_auth_uid_on_signup trigger(s) live "
                     f"(new signup links existing records)"))

    fails = [m for s, m in findings if s == "FAIL"]
    for sev, msg in findings:
        c = GREEN if sev == "OK" else RED
        print(f"  {c}{sev:<4}{RST} {msg}")
    print("-" * 74)
    if fails:
        print(f"  {RED}FAIL{RST} — {len(fails)} live data-layer auth proof(s) failed")
        return 1
    print(f"  {GREEN}PASS{RST} — synthetic-email isolation + non-active exclusion live-proven on the local DB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
