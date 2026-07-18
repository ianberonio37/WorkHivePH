#!/usr/bin/env python3
"""
validate_migration_grant_regression.py - Arc R (Z/A01): a security lock must not silently REOPEN.
===================================================================================================
THE BUG CLASS (measured, live): 20260620000016_ai_retrieval_isolation.sql REVOKED anon/authenticated
EXECUTE on the edge-only DEFINER fn `match_procedural_memories` (a cross-tenant retrieval IDOR was
locked to service_role). Four days later 20260624000002_episodic_supersedes.sql - a FEATURE migration
adding a supersede penalty - ended with `GRANT EXECUTE ... TO anon, authenticated, service_role`,
silently RE-OPENING the lock (its own comment claimed "grants unchanged"; it had copied the pre-lock
grant). The board's P-lens fell 100% -> 66.7% and the platform shipped a cross-tenant leak until swept.

THE RULE (a security RATCHET on the migration files, deterministic + offline - safe for --fast):
when a migration EXPLICITLY revokes EXECUTE from `anon`/`authenticated` (a deliberate app-role
LOCK-OUT — not merely `REVOKE ... FROM public`, which just drops Postgres's over-broad default), no
LATER migration may re-GRANT that function to public/anon/authenticated. A genuine, intended re-opening
must carry an explicit `-- regrant-approved: <reason>` marker on/next to the GRANT (audited escape).

We replay every supabase/migrations/*.sql in filename (chronological) order via EXPLICIT GRANT/REVOKE
statements (CREATE OR REPLACE preserves privileges in Postgres, so only explicit grant/revoke moves the
boundary). A function is flagged iff: it was LOCKED OUT (anon/authenticated explicitly revoked) in some
file, a LATER file re-GRANTed it to public/anon/authenticated, its net public-execute state is still
granted, and the re-grant carried no approval marker. This precisely characterises the C2.1 shape (a
feature migration silently reverting an earlier security lock) while NOT flagging the legitimate
"revoke-default-from-public then grant-intended-roles" idiom (same migration) or a remediated fn whose
most-recent action was a re-lock (a later REVOKE correctly clears the flag).

USAGE:      python tools/validate_migration_grant_regression.py
Self-test:  python tools/validate_migration_grant_regression.py --self-test
Exit 0 = no un-approved lock re-opening. Exit 1 = a re-open regression (or self-test fail).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_migration_grant_regression"]

PUBLIC_ROLES = ("public", "anon", "authenticated")
# GRANT ... EXECUTE ... ON FUNCTION <name>(...) TO <roles>   /  REVOKE ... ON FUNCTION <name>(...) FROM <roles>
_GRANT = re.compile(r"\bgrant\b[^;]*?\bon\s+function\s+(?:public\.)?(\w+)\s*\([^)]*\)\s*to\s+([^;]+);", re.I | re.S)
_REVOKE = re.compile(r"\brevoke\b[^;]*?\bon\s+function\s+(?:public\.)?(\w+)\s*\([^)]*\)\s*from\s+([^;]+);", re.I | re.S)
_APPROVED = re.compile(r"--\s*regrant-approved", re.I)


def _roles(blob: str):
    lo = blob.lower()
    return {r for r in PUBLIC_ROLES if re.search(rf"\b{r}\b", lo)}


def _events(sql: str):
    """Yield (offset, action, fn, roles:set, approved) for each public-scoped grant/revoke, source order."""
    approved_spans = [m.start() for m in _APPROVED.finditer(sql)]
    for action, rx in (("grant", _GRANT), ("revoke", _REVOKE)):
        for m in rx.finditer(sql):
            fn, roles = m.group(1), _roles(m.group(2))
            if not roles:
                continue  # grant/revoke targets only service_role/named roles — not a public boundary move
            approved = any(0 <= (m.start() - a) <= 200 for a in approved_spans)
            yield (m.start(), action, fn, roles, approved)


def scan(files):
    """Flag a fn iff anon/authenticated were EXPLICITLY revoked (a deliberate app-role lock-out) in one
    file and re-granted to public/anon/authenticated in a STRICTLY LATER file, net still granted, no
    approval marker. Same-file 'revoke-default-from-public then grant-roles' and later re-locks are clean."""
    # per fn: last file idx of an explicit anon/auth lock-out; last file idx of a public re-grant (+approved);
    # net public-execute state (from the last public-targeting event in global order).
    lockout_file, regrant_file, regrant_appr, net_granted = {}, {}, {}, {}
    for idx, f in enumerate(files):
        sql = f.read_text(encoding="utf-8", errors="replace")
        for _off, action, fn, roles, approved in sorted(_events(sql), key=lambda e: e[0]):
            if action == "revoke":
                net_granted[fn] = False
                if roles & {"anon", "authenticated"}:      # deliberate app-role lock-out
                    lockout_file[fn] = idx
            else:  # grant to public/anon/authenticated
                net_granted[fn] = True
                regrant_file[fn] = idx
                regrant_appr[fn] = approved
    findings = []
    for fn, lf in lockout_file.items():
        rf = regrant_file.get(fn, -1)
        if rf > lf and net_granted.get(fn) and not regrant_appr.get(fn):
            findings.append(fn)
    return findings, lockout_file, regrant_file


def _self_test() -> int:
    import tempfile, os
    ok = True
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        # f_leak: revoked then re-granted (the C2.1 shape) -> MUST flag
        (dp / "001_lock.sql").write_text("revoke execute on function public.f_leak(uuid) from anon, authenticated;")
        (dp / "002_reopen.sql").write_text("grant execute on function public.f_leak(uuid) to anon, authenticated;")
        # f_fixed: revoked, re-granted, then re-revoked (remediated) -> must NOT flag
        (dp / "003_fix.sql").write_text(
            "revoke execute on function public.f_fixed(uuid) from anon, authenticated;\n"
            "grant execute on function public.f_fixed(uuid) to anon, authenticated;\n"
            "revoke execute on function public.f_fixed(uuid) from anon, authenticated;\n"
            "grant execute on function public.f_fixed(uuid) to service_role;")
        # f_ok_public: granted, never revoked (always-public) -> must NOT flag
        (dp / "004_pub.sql").write_text("grant execute on function public.f_ok_public(uuid) to anon;")
        # f_appr: locked out, then re-granted in a LATER file WITH approval marker -> must NOT flag
        (dp / "005_appr_lock.sql").write_text("revoke execute on function public.f_appr(uuid) from anon, authenticated;")
        (dp / "006_appr_grant.sql").write_text(
            "-- regrant-approved: became a public read after Ian's fork\n"
            "grant execute on function public.f_appr(uuid) to anon, authenticated;")
        # f_default: only ever `revoke from public` (drops default) + grant roles, same file -> must NOT flag
        (dp / "007_default.sql").write_text(
            "revoke all on function public.f_default(uuid) from public;\n"
            "grant execute on function public.f_default(uuid) to anon, authenticated, service_role;")
        # f_xfile_leak: anon/auth locked out in one file, re-granted in a LATER file, NO marker -> MUST flag
        (dp / "008_xlock.sql").write_text("revoke execute on function public.f_xfile(uuid) from public, anon, authenticated;")
        (dp / "009_xopen.sql").write_text("grant execute on function public.f_xfile(uuid) to anon, authenticated, service_role;")
        files = sorted(dp.glob("*.sql"))
        findings, _lf, _rf = scan(files)
        checks = [
            ("re-open (revoke->grant, cross-file) flagged",  "f_leak" in findings),
            ("remediated (revoke->grant->revoke) clean",     "f_fixed" not in findings),
            ("always-public not flagged",                    "f_ok_public" not in findings),
            ("approved cross-file re-grant not flagged",     "f_appr" not in findings),
            ("revoke-default-from-public idiom not flagged", "f_default" not in findings),
            ("cross-file anon/auth re-grant flagged",        "f_xfile" in findings),
        ]
        for name, passed in checks:
            print(f"  [{(G+'PASS'+X) if passed else (R+'FAIL'+X)}] {name}")
            ok = ok and passed
    print((G + "self-test PASS - grant-regression linter has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    if not MIG.is_dir():
        print(f"{R}FAIL{X}: {MIG} not found"); return 1
    files = sorted(MIG.glob("*.sql"))
    findings, lockout_file, regrant_file = scan(files)
    print(f"{B}Migration grant-regression linter (Arc R / Z, A01){X}")
    print(f"  migrations scanned: {len(files)} · functions with an explicit anon/auth lock-out: {len(lockout_file)}")
    if findings:
        for fn in findings:
            print(f"  {R}FAIL{X} {fn}: EXECUTE was revoked from public/anon/authenticated, then a LATER "
                  f"migration re-GRANTED it (net state = granted) with no `-- regrant-approved` marker "
                  f"— a security lock silently re-opened.")
        print(f"{R}FAIL: {len(findings)} re-opened security lock(s).{X}")
        return 1
    print(f"{G}PASS - no revoked function was silently re-granted to public/anon/authenticated.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
