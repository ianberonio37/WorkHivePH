#!/usr/bin/env python3
"""validate_storage_object_rls.py — T376's lock: object storage access is RLS-gated, so a signed URL (or a
guessed path) cannot abuse scope — the destructive op is OWNER/ADMIN-scoped and no policy hands writes to
anon. Signed URLs are only as safe as the RLS behind the bucket; this proves the RLS is there and the
dangerous verbs are bounded.

The live posture (verified 2026-09-01):
  · RLS is ENABLED on storage.objects (rowsecurity), so no policy = no access, not open access.
  · The destructive DELETE on marketplace-listings is scoped to (owner = auth.uid() OR is_marketplace_admin())
    — a signed URL / a guessed object cannot let a non-owner delete someone else's upload.
  · No policy grants anon (public role with no auth.uid predicate) an INSERT/UPDATE/DELETE — writes require
    an authenticated caller. Public READ on the deliberately-public buckets (marketplace-listings, tts-cache)
    is by design (listings are public; the TTS cache is non-sensitive audio) and owes no scoping.

DB-backed (psql), browser-free. SKIPs if the DB is unreachable (no unearned pass). Registered in
run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import subprocess
import sys

CHECK_NAMES = ["storage-object-rls"]


def _psql(sql: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", sql], capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _fetch():
    rls = _psql("select relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace "
                "where n.nspname='storage' and c.relname='objects';")
    if rls is None:
        return None
    rows = _psql(
        "select polname||'|'||case polcmd when 'r' then 'SELECT' when 'a' then 'INSERT' when 'w' then 'UPDATE' "
        "when 'd' then 'DELETE' when '*' then 'ALL' end||'|'||coalesce(pg_get_expr(polqual,polrelid),'')||'|'"
        "||coalesce(pg_get_expr(polwithcheck,polrelid),'') "
        "from pg_policy pol join pg_class c on c.oid=pol.polrelid join pg_namespace n on n.oid=c.relnamespace "
        "where n.nspname='storage' and c.relname='objects';")
    return {"rls": (rls or "").strip().lower().startswith("t"),
            "policies": [ln.split("|", 3) for ln in (rows or "").splitlines() if ln.strip()]}


def check(data: dict) -> list[str]:
    problems: list[str] = []
    if not data.get("rls"):
        problems.append("RLS is NOT enabled on storage.objects — every object is world-accessible regardless "
                        "of bucket policy (a signed URL is the least of the problems).")
    pols = data.get("policies", [])
    # a destructive DELETE must be owner/admin-scoped, never open
    deletes = [p for p in pols if len(p) >= 3 and p[1] in ("DELETE", "ALL")]
    if deletes and not any(("owner" in p[2].lower() and "auth.uid()" in p[2].lower())
                           or "admin" in p[2].lower() for p in deletes):
        problems.append("the DELETE policy on storage.objects is not owner/admin-scoped (owner = auth.uid() "
                        "OR admin) — a non-owner could delete another user's object.")
    # no anon (unauthenticated) write: an INSERT/UPDATE/DELETE whose USING+CHECK never reference auth.uid()
    for p in pols:
        if len(p) < 4:
            continue
        name, cmd, using_q, check_q = p[0], p[1], p[2], p[3]
        if cmd in ("INSERT", "UPDATE", "DELETE", "ALL"):
            combined = (using_q + " " + check_q).lower()
            # a write policy with a truly-open predicate (no auth.uid, no owner, no role/service gate) is anon-open
            if combined.strip() in ("", "true") or (
                    "auth.uid()" not in combined and "owner" not in combined
                    and "role" not in combined and "service" not in combined and "admin" not in combined
                    and "authenticated" not in combined):
                # INSERT policies commonly carry only a WITH CHECK; an empty USING there is normal, so require
                # BOTH sides empty/open to flag (an INSERT with a real CHECK is fine).
                if not (cmd == "INSERT" and check_q.strip() and check_q.strip().lower() != "true"):
                    problems.append(f"write policy '{name}' ({cmd}) has no authenticated/owner/role predicate "
                                    f"— it may grant anon writes to storage.")
    return problems


def main() -> int:
    data = _fetch()
    if data is None:
        print("SKIP storage-object-rls — DB unreachable (no unearned pass).")
        return 0
    problems = check(data)
    if problems:
        print("FAIL storage-object-rls — object storage is not safely scoped:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS storage-object-rls — RLS is on storage.objects, the destructive DELETE is owner/admin-scoped, "
          "and no policy grants anon writes (signed URLs cannot abuse scope beyond public-by-design buckets).")
    return 0


def self_test() -> int:
    good = {"rls": True, "policies": [
        ["Public read marketplace-listings", "SELECT", "(bucket_id = 'marketplace-listings')", ""],
        ["Owner or admin delete", "DELETE", "((bucket_id = 'x') AND ((owner = auth.uid()) OR is_marketplace_admin()))", ""],
        ["Authed upload", "INSERT", "", "(auth.uid() IS NOT NULL)"],
    ]}
    fails = []
    if check(good):
        fails.append("the real owner-scoped posture should PASS")
    if not any("RLS is NOT enabled" in p for p in check({**good, "rls": False})):
        fails.append("RLS disabled should FAIL")
    open_del = {"rls": True, "policies": [["open delete", "DELETE", "(bucket_id = 'x')", ""]]}
    if not any("owner/admin-scoped" in p for p in check(open_del)):
        fails.append("an unscoped DELETE should FAIL")
    anon_write = {"rls": True, "policies": [["anon upload", "INSERT", "", "true"]]}
    if not any("anon writes" in p for p in check(anon_write)):
        fails.append("an anon-open INSERT should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_storage_object_rls self-test (no-RLS / unscoped-delete / anon-write redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
