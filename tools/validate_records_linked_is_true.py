#!/usr/bin/env python3
"""records-linked-is-true - the signup notice may only claim what was actually linked (2026-08-26).

After creating an account, index.html could show:

    "Account secured! Your existing records as <name> are now linked to your account."

It decided that by COUNTING v_worker_truth rows matching the display name. But that view exposes
worker_profiles.display_name and is security_invoker, so under RLS a brand-new user can see exactly
one row - the profile the very same flow inserted moments earlier. The count was therefore always
>= 1, and every new signup was told their existing records had been linked. For someone who had
none that is simply false; for a namesake it claims another person's work history.

★THE CHECK AND THE ACTION READ DIFFERENT ROWS: the reassurance was computed from profile rows while
the actual linking is done by resolveActiveHiveContext(), which reads MEMBERSHIP. A claim has to
rest on the thing it claims, so the notice is now gated on that function's return value - non-null
exactly when a hive membership was found and linked - and it NAMES the hive it landed in.

★WHY THIS GATE RUNS THE DB HALF LIVE: the page assertion alone would not explain itself. Seeding a
fresh identity with no membership and measuring the old count reproduces the trap directly - if that
count ever stops returning 1, the RLS shape changed and this gate's reasoning needs revisiting
rather than silently passing.

Re-drive: python tools/validate_records_linked_is_true.py
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

UID = "e1851850-0000-4000-8000-00000000c001"
NAME = "WH-T185-PROBE Newcomer"


def psql(sql: str, timeout: int = 60):
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
        input=sql, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def main() -> int:
    failures = []

    # ── the page half: the claim must rest on the linking, not on a name count ──────────────
    page = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()

    m = re.search(r"const\s+_linkedHive\s*=\s*await\s+resolveActiveHiveContext", page)
    if not m:
        failures.append("index.html's signup flow does not capture resolveActiveHiveContext()'s "
                        "result, so the records-linked notice has nothing truthful to rest on")
    if not re.search(r"if\s*\(\s*_linkedHive\s*\)", page):
        failures.append("the records-linked panel is not gated on _linkedHive - it fires on "
                        "something other than whether records were actually linked")
    # the specific regression: counting v_worker_truth by display name to decide the notice
    if re.search(r"count:\s*['\"]exact['\"][^)]*\}\s*\)\s*\.\s*eq\(\s*['\"]worker_name['\"]\s*,\s*displayName",
                 page, re.S):
        failures.append("index.html again decides the notice by COUNTING v_worker_truth rows "
                        "matching displayName - under RLS that count includes the profile this very "
                        "flow just inserted, so it is >= 1 for every brand-new user")
    if "are now linked to your account" in page and not re.search(r"_linkedHive\.name", page):
        failures.append("the notice does not name the hive the records were linked into - a claim "
                        "this strong has to say what it rests on")

    # ── the DB half: reproduce the trap that makes a count-based check unusable ─────────────
    probe = psql("SELECT 1;", timeout=25)
    if probe.returncode != 0 or "1" not in (probe.stdout or ""):
        if failures:
            print("FAIL records-linked-is-true:")
            for f in failures:
                print("    - " + f)
            return 1
        print("SKIP records-linked-is-true - page checks pass; DB half needs the local stack")
        return 0

    seed = f"""
BEGIN;
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                        email_confirmed_at, created_at, updated_at)
VALUES ('{UID}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',
        'wh-t185-probe-c1@example.com','x', now(), now(), now())
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.worker_profiles (auth_uid, username, display_name, email)
VALUES ('{UID}','wht185probec1','{NAME}','wh-t185-probe-c1@example.com')
ON CONFLICT DO NOTHING;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{{"sub":"{UID}","role":"authenticated"}}';
SELECT 'C2COUNT=' || count(*) FROM public.v_worker_truth WHERE worker_name = '{NAME}';
SELECT 'LINKABLE=' || count(*) FROM public.v_worker_truth
  WHERE worker_name = '{NAME}' AND hive_id IS NOT NULL;
ROLLBACK;
"""
    out = psql(seed)
    text = (out.stdout or "") + (out.stderr or "")
    c2 = re.search(r"C2COUNT=(\d+)", text)
    linkable = re.search(r"LINKABLE=(\d+)", text)

    if not c2 or not linkable:
        failures.append(f"the DB probe produced no counts (stack shape changed?): {text.strip()[:200]}")
    else:
        if int(c2.group(1)) == 0:
            failures.append("a brand-new identity no longer self-matches in v_worker_truth. That is "
                            "not a failure of the fix but of this gate's premise - the RLS or view "
                            "shape changed, so re-derive why the count-based check was unusable")
        if int(linkable.group(1)) != 0:
            failures.append(f"a membership-less identity reported {linkable.group(1)} linkable hive "
                            "rows - resolveActiveHiveContext's basis is no longer trustworthy")

    if failures:
        print("FAIL records-linked-is-true - the signup notice claims more than it knows:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"PASS records-linked-is-true - the notice rests on the hive actually linked and names it; "
          f"a fresh identity self-matches {c2.group(1)} row in v_worker_truth (which is why a count "
          f"could never answer the question) and has 0 linkable memberships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
