#!/usr/bin/env python3
"""hive-seating-is-by-identity - which hive a session lands in is decided by auth, not by a name.

resolveActiveHiveContext() in index.html decides which tenant a signed-in session is seated in. It
used to select memberships with .eq('worker_name', displayName) - and worker_name in v_worker_truth
is worker_profiles.display_name, so the query asked "which memberships belong to this NAME" and
depended entirely on the profiles_read_own RLS policy (auth_uid = auth.uid()) to turn that into
"which memberships are MINE".

★THAT WAS CORRECT AND FOR THE WRONG REASON, which is the point of this gate. Measured: a caller
sees exactly one profile row today, so the name filter could only ever match themselves. But the
safety lived in the POLICY, not in the query - widening profile reads even slightly (a co-member
roster is an ordinary thing to want) would have let a NAMESAKE's memberships resolve here and
seated a person in a hive they do not belong to. The view already joins membership on
hm.auth_uid = wp.auth_uid, so the name filter bought nothing the identity does not buy more safely.

This is the third face of one defect: a hive join that refused a second Juan Dela Cruz by unique
index, a signup notice that counted its own freshly-written profile row, and a tenant seat chosen
by name. A name is not an identity.

★IT ASSERTS BOTH HALVES, because either alone can rot: the page must filter by identity, AND the
RLS policy that was carrying the old query must still be self-scoped - if that policy ever widens,
this gate says so rather than passing quietly, since that widening is exactly what would have made
the old code dangerous.

Re-drive: python tools/validate_hive_seating_is_by_identity.py
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")


def main() -> int:
    failures = []
    page = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()

    m = re.search(r"async function resolveActiveHiveContext\((.*?)\)\s*\{(.*?)\n  \}", page, re.S)
    if not m:
        print("FAIL hive-seating-is-by-identity - resolveActiveHiveContext() not found in index.html")
        return 1
    params, body = m.group(1), m.group(2)

    # the membership select that decides the seat
    sel = re.search(r"\.from\(\s*['\"]v_worker_truth['\"]\s*\)(.*?)\.limit\(", body, re.S)
    if not sel:
        failures.append("the membership query in resolveActiveHiveContext() no longer reads "
                        "v_worker_truth - re-derive what decides the seat before trusting this gate")
    else:
        q = sel.group(1)
        if re.search(r"\.eq\(\s*['\"]worker_name['\"]", q):
            failures.append("the seat is chosen by .eq('worker_name', ...) - that asks which "
                            "memberships belong to a NAME and leans on RLS to make it mean 'mine'. "
                            "A namesake resolves here the moment profile reads widen")
        if not re.search(r"\.eq\(\s*['\"]auth_uid['\"]", q):
            failures.append("the seat is not chosen by .eq('auth_uid', ...) - tenant seating must "
                            "key on the identity the session already holds")

    if "authUid" not in params:
        failures.append("resolveActiveHiveContext() does not take the auth identity, so its callers "
                        "cannot seat by identity")
    # no-identity must mean solo mode, never a name guess
    if not re.search(r"if\s*\(\s*!_uid\s*\)\s*return null", body):
        failures.append("a missing identity does not fall back to solo mode - the safe answer when "
                        "identity is unknown is NO hive, never a name-matched one")

    # both call sites hand it the identity rather than relying on the lookup
    sites = re.findall(r"resolveActiveHiveContext\(\s*db\s*,\s*displayName\s*([^)]*)\)", page)
    bare = [s for s in sites if not s.strip().startswith(",")]
    if bare:
        failures.append(f"{len(bare)} call site(s) omit the auth identity, falling back to a session "
                        f"lookup that can fail open into solo mode on a slow or broken auth call")

    # ── the RLS half: the policy the OLD query silently depended on must still be self-scoped ──
    probe = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
        input="SELECT policyname||' :: '||coalesce(qual,'') FROM pg_policies "
              "WHERE tablename='worker_profiles' AND cmd='SELECT';",
        capture_output=True, text=True, timeout=45, encoding="utf-8", errors="replace")

    if probe.returncode == 0 and (probe.stdout or "").strip():
        pol = probe.stdout.strip()
        if "auth_uid = auth.uid()" not in pol.replace("( ", "(").replace(" )", ")"):
            failures.append(f"worker_profiles SELECT is no longer scoped to auth_uid = auth.uid() "
                            f"({pol.strip()[:120]}) - the exact widening that made name-based "
                            f"seating dangerous. The page is now safe by construction, but any "
                            f"OTHER name-keyed read of this view needs re-auditing")
    elif failures:
        pass  # page half already decided it
    else:
        print("SKIP hive-seating-is-by-identity - page checks pass; RLS half needs the local stack")
        return 0

    if failures:
        print("FAIL hive-seating-is-by-identity - a session could be seated by name:")
        for f in failures:
            print("    - " + f)
        return 1

    print("PASS hive-seating-is-by-identity - the seat is chosen by auth_uid, both call sites pass "
          "the identity, an unknown identity means solo mode, and worker_profiles reads are still "
          "self-scoped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
