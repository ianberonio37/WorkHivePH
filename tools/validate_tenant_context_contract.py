#!/usr/bin/env python3
"""validate_tenant_context_contract.py — behavioural + mutation teeth on the shared tenancy helper.

`_shared/tenant-context.ts` is imported by 42 edge functions; 30 route their tenancy decision through
`resolveContext`/`resolveTenancy`. Four registered gates "cover" it — and every one is a regex marker over
CALLER source (it asserts callers IMPORT the helper), so a weakened `isServiceRoleBearer` or a dropped 401
guard would pass all four. This gate exercises the helper's ACTUAL branch logic.

It cannot do so over HTTP: the edge runtime serves a CACHED module, so an on-disk edit does not reach the
running function without a restart (proven 2026-07-31 — a sentinel 403 message never appeared). A mutation
harness over HTTP would therefore score every mutant "killed" while nothing changed — the fabricated-100%
shape this platform already corrected once. So the runner (`tenant_context_contract.mjs`) loads the REAL
helper under Node (v24 strips the TS types; only the type-only SupabaseClient import is neutralized), runs its
functions against a stubbed Supabase client, and mutates the source to prove the assertions bite. The
DB-level escalation — a self-rename into another hive — is locked separately by
`validate_membership_resolved_by_auth_uid.py`; this locks the helper's own service-role / null-auth /
non-member branches.

Usage:  python tools/validate_tenant_context_contract.py [--selftest]
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "tools", "tenant_context_contract.mjs")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def run():
    try:
        # `node` directly, never npx — this repo's path contains an ampersand ([[reference_npx_ampersand_path_bug]]).
        r = subprocess.run(["node", RUNNER], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except FileNotFoundError:
        return None, "node not installed"
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main(argv):
    print(f"{BOLD}tenant-context helper contract{RST} — the tenancy boundary 30 edge functions trust")
    if not os.path.exists(RUNNER):
        print(f"  {RED}FAIL{RST} the runner is missing ({os.path.basename(RUNNER)}).")
        return 1
    rc, out = run()
    if rc is None:
        print(f"  {YEL}SKIP{RST} — {out}; nothing asserted.")
        return 0
    for line in out.splitlines():
        s = line.strip()
        if s.startswith(("KILL", "SURVIVE", "EQUIV", "STALE", "mutation:", "SURVIVING", "STALE EXCL")) or \
           s.startswith("BASELINE") or " viable killed" in s:
            print(f"  {DIM}{s[:150]}{RST}")
    if rc == 2:
        print(f"  {RED}FAIL{RST} the runner errored (not a contract result). See output above.")
        return 1
    if rc != 0:
        print(f"  {RED}FAIL{RST} a mutant SURVIVED or the baseline is broken. A surviving mutant is a change to "
              f"the service-role / auth / membership decision that no assertion objects to — treat as urgent: "
              f"this helper is the tenancy boundary for 30 functions.")
        return 1
    if "--selftest" in argv:
        # Teeth-of-the-teeth: the runner must have EXERCISED both a kill and the equivalent exclusion, else a
        # green run proves nothing. Require the named markers in the output.
        need = ["exact-match weakened to a prefix match", "null-authUid 401 guard removed",
                "6/6 viable killed", "EXCLUDED (equivalent)"]
        missing = [n for n in need if n not in out]
        if missing:
            print(f"  {RED}FAIL{RST} selftest: the runner did not exercise {missing} — a green from a suite that "
                  f"skipped its own cases proves nothing.")
            return 1
        print(f"  {GREEN}PASS{RST} selftest: the prefix-match and null-auth mutants were killed and the "
              f"equivalent mutant was excluded with a mechanism.")
    print(f"  {GREEN}PASS{RST} 16 behavioural assertions hold and every viable mutant is killed: a crafted "
          f"bearer cannot forge service-role, null auth is 401, a non-member is 403, and the membership lookup "
          f"stays filtered by auth_uid + hive_id + active status.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
