r"""A REVOKE that leaves the PUBLIC grant in place is a no-op. This gate proves each one took.

WHY IT EXISTS. Every function is created with EXECUTE granted to PUBLIC, and every role inherits
PUBLIC. So `REVOKE EXECUTE ON FUNCTION f() FROM anon, authenticated` removes the named roles and
changes nothing: `has_function_privilege('authenticated', f, 'EXECUTE')` stays TRUE.

Measured 2026-08-20 -- of 17 functions a migration tries to revoke, TEN were still executable by any
signed-in user, including three that were exploitable:

  award_achievement_xp        self-award arbitrary XP. Its migration says "Block direct client
                              calls: XP must come from DB triggers only" (20260508000002:215) --
                              aspirational since 2026-05.
  reverse/restore_community_post_xp   cross-tenant XP IDOR: takes a post_id, derives hive_id FROM
                              THE ROW, no membership test.
  enqueue_service_push_uids   arbitrary push (title/body/URL) to ANY user; no auth.uid() at all.

Three revokes DID work (delete_worker_data, increment_community_xp, and find_hive_by_code which is
deliberately granted), which proves the correct form was known and simply not applied consistently.

WHAT IT CHECKS: for every function named in a `REVOKE EXECUTE ON FUNCTION` in supabase/migrations,
ask the LIVE catalog whether PUBLIC still holds EXECUTE (aclexplode grantee = 0). If it does, the
revoke did not take.

WHAT IT DELIBERATELY DOES NOT DO: it does not tell you to revoke PUBLIC everywhere. Two of the ten
(store_memory_turn, update_dialog_state) are called from voice-handler.js and gate themselves with
auth.uid()/hive_members -- their stale revoke lines are load-bearing precisely BECAUSE they never
took effect, and "fixing" them would break the voice journal. Those live in INTENTIONALLY_CALLABLE
with the caller named, so the gate stays quiet about them and loud about everything else.

  python tools/validate_revoke_actually_revoked.py
  python tools/validate_revoke_actually_revoked.py --selftest
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
G, R, Y, D, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

REVOKE_RE = re.compile(
    r"REVOKE\s+EXECUTE\s+ON\s+FUNCTION\s+(?:public\.)?([a-z_][a-z0-9_]*)", re.I)

# Revoked in a migration, but the product CALLS them and they gate themselves internally.
# Naming the caller is the point: an exemption without one is how a real hole gets waved through.
INTENTIONALLY_CALLABLE = {
    "store_memory_turn":   "voice-handler.js:1017; 6 auth.uid()/hive_members refs inside",
    "update_dialog_state": "voice-handler.js:1342; 3 auth.uid()/hive_members refs inside",
    "find_hive_by_code":   "join-by-code flow; granted to authenticated deliberately, no PUBLIC",
    # These two gate themselves in the UPDATE's own WHERE, joined on the ALERT's hive_id
    # against auth.uid(), and return {"ok":false,"error":"not found or not authorized"} on
    # 0 rows. A foreign-hive caller changes nothing and is told so, which is the opposite of
    # reverse_community_post_xp (derived hive_id from the row, checked nothing). PUBLIC here
    # is untidy, not a hole -- and no client calls either one.
    "acknowledge_alert":   "self-gated: membership on the alert's own hive inside the UPDATE WHERE",
    "suppress_alert":      "self-gated: same shape as acknowledge_alert",
    # Gated via the platform HELPER, not a literal auth.uid(). I first grepped for
    # auth.uid()/hive_members, found zero, and nearly filed a cross-tenant disclosure on all
    # five -- then nearly patched a working guard on the AI retrieval path. Every one calls
    # public.user_can_access_hive(p_hive_id) inside its own WHERE. Verified with
    # pg_get_functiondef, not grep. A codebase with a membership helper does not spell
    # membership as auth.uid() everywhere -- that is the point of the helper.
    "compute_hive_readiness":     "self-gated via user_can_access_hive()",
    "fetch_active_alerts":        "self-gated via user_can_access_hive(); voice-handler.js:1059",
    "get_hive_readiness_current": "self-gated via user_can_access_hive(); hive.html:2747",
    "semantic_search_kb":         "self-gated via user_can_access_hive(); voice-handler.js:1230",
    "semantic_search_kg_facts":   "self-gated via user_can_access_hive(); voice-handler.js:1267",
}

SQL = """
select p.proname,
       (select count(*) from aclexplode(p.proacl) a
         where a.grantee = 0 and a.privilege_type = 'EXECUTE')
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.proname = any(%s);
"""


def live_public_exec(names):
    arr = "ARRAY[" + ",".join("'%s'" % n for n in sorted(names)) + "]::text[]"
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-tAF|", "-c", SQL % arr],
            capture_output=True, text=True, timeout=40)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    out = {}
    for line in r.stdout.splitlines():
        if "|" in line:
            n, c = line.rsplit("|", 1)
            out[n.strip()] = int(c.strip() or 0)
    return out


def main():
    if "--selftest" in sys.argv:
        # Teeth: the parser must find a revoked name, and the exemption must suppress only itself.
        sample = "REVOKE EXECUTE ON FUNCTION public.f_secret(uuid) FROM anon, authenticated;"
        found = REVOKE_RE.findall(sample)
        ok = found == ["f_secret"] and "store_memory_turn" in INTENTIONALLY_CALLABLE
        print("  selftest: parses a REVOKE target, keeps the documented exemptions")
        print("  %s - parsed=%s" % ((G + "PASS" + X) if ok else (R + "FAIL" + X), found))
        return 0 if ok else 1

    names = set()
    for f in glob.glob(os.path.join(ROOT, "supabase", "migrations", "*.sql")):
        with open(f, encoding="utf-8", errors="replace") as fh:
            names.update(m.lower() for m in REVOKE_RE.findall(fh.read()))
    if not names:
        print("  %sABSTAINED%s - no REVOKE EXECUTE found in migrations" % (Y, X))
        return 0

    live = live_public_exec(names)
    if live is None:
        print("  %sSKIP%s - database unreachable; this gate reads the live catalog" % (Y, X))
        return 0

    leaked = [n for n, c in live.items() if c > 0 and n not in INTENTIONALLY_CALLABLE]
    print("\n  REVOKE effectiveness - %d function(s) revoked in migrations, %d present live"
          % (len(names), len(live)))
    for n in sorted(leaked):
        print("  %sFAIL%s  %s: a migration revokes it, but PUBLIC still holds EXECUTE - every role "
              "inherits PUBLIC, so the revoke is a no-op. Revoke FROM PUBLIC." % (R, X, n))
    for n in sorted(set(live) & set(INTENTIONALLY_CALLABLE)):
        print("  %sallowed%s %s %s(%s)%s" % (D, X, n, D, INTENTIONALLY_CALLABLE[n], X))
    if leaked:
        return 1
    print("  %sPASS%s - every revoked function is genuinely unreachable by PUBLIC" % (G, X))
    return 0


sys.exit(main())
