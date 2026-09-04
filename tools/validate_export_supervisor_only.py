#!/usr/bin/env python3
"""validate_export_supervisor_only.py — T380's lock: the whole-hive data export (export-hive-data, a PDPA
right-to-access dump of everything the hive holds) is gated to an ACTIVE SUPERVISOR, and that gate runs
BEFORE the export — so a worker or an anonymous caller cannot exfiltrate the entire hive.

export-hive-data is verify_jwt=false (it does its own auth) and returns a complete tenant dump. Three things
must hold or a low-role walks off with everything:
  1. SUPERVISOR-ONLY — the auth helper requires role === 'supervisor' AND an active membership (a removed or
     worker-role member is refused).
  2. REFUSE WITH 403 — a failed auth check returns 403, not a fall-through to the export.
  3. AUTH BEFORE EXPORT — the supervisor check is called BEFORE the export_hive_data RPC, not after (the
     'the cure runs too late' / ordering-defect class: a check that runs after the dump has already been
     computed protects nothing).

Static source lock (browser-free; the live 403-probe is the board's job and goes dark when the edge runtime
is down). Read-only. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "export-hive-data" / "index.ts"

CHECK_NAMES = ["export-supervisor-only"]


def check(src: str) -> list[str]:
    problems: list[str] = []
    # 1. supervisor-only: role === 'supervisor' AND active membership required
    if not re.search(r"role\s*!==\s*['\"]supervisor['\"]|role\s*===\s*['\"]supervisor['\"]", src):
        problems.append("no role === 'supervisor' requirement — the whole-hive export is not supervisor-gated.")
    if not re.search(r"hive_status\s*!==\s*['\"]active['\"]|status\s*===\s*['\"]active['\"]", src):
        problems.append("no active-membership requirement — a removed member could still export the hive.")
    # 2. refuse with 403
    if not re.search(r"checkSupervisor\s*\(", src):
        problems.append("no checkSupervisor() auth helper is called — the export is not gated at all.")
    if not re.search(r"!\s*\w*[Rr]es\.ok[\s\S]{0,120}status:\s*403", src) and "status: 403" not in src and "status:403" not in src:
        problems.append("a failed auth check does not return 403 — a non-supervisor is not refused.")
    # 3. AUTH BEFORE EXPORT — the awaited checkSupervisor CALL precedes the export_hive_data RPC CALL.
    #    Match the call sites, not any string occurrence (the docstring names both — 'my grep matched the
    #    comment, not the link' class), so a comment mention cannot flip the ordering verdict.
    auth_call = re.search(r"await\s+checkSupervisor\s*\(", src)
    export_call = re.search(r"\.rpc\(\s*['\"]export_hive_data['\"]", src)
    if auth_call and export_call and auth_call.start() > export_call.start():
        problems.append("the supervisor check runs AFTER the export_hive_data RPC — the dump is computed "
                        "before the caller is authorized (the cure runs too late).")
    elif auth_call and not export_call:
        problems.append("no export_hive_data RPC call found — the export path may have moved (re-anchor the gate).")
    return problems


def main() -> int:
    if not FN.exists():
        print("FAIL export-supervisor-only: export-hive-data/index.ts not found"); return 1
    problems = check(FN.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL export-supervisor-only — the whole-hive export is not safely gated:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS export-supervisor-only — export-hive-data requires an ACTIVE SUPERVISOR (checkSupervisor), "
          "refuses others with 403, and runs the auth check BEFORE the export RPC (no low-role exfil).")
    return 0


def self_test() -> int:
    good = ('const authRes = await checkSupervisor(db, jwt, hive_id);\n'
            'if (member.hive_status !== "active" || member.role !== "supervisor") { return { ok:false }; }\n'
            'if (!authRes.ok) { return new Response(x, { status: 403 }); }\n'
            'const exportP = db.rpc("export_hive_data", { p_hive_id: hive_id });')
    fails = []
    if check(good):
        fails.append("the real supervisor-gated fn should PASS")
    if not any("supervisor-gated" in p for p in check(good.replace('role !== "supervisor"', 'false'))):
        fails.append("dropping the supervisor requirement should FAIL")
    if not any("removed member" in p for p in check(good.replace('hive_status !== "active"', 'false'))):
        fails.append("dropping the active requirement should FAIL")
    if not any("not refused" in p for p in check(good.replace("status: 403", "status: 200"))):
        fails.append("no 403 refusal should FAIL")
    # order swap: export computed before the auth check
    swapped = ('const exportP = db.rpc("export_hive_data", { p_hive_id: hive_id });\n'
               'const authRes = await checkSupervisor(db, jwt, hive_id);\n'
               'if (member.role !== "supervisor") {} if (member.hive_status !== "active"){}\n'
               'if (!authRes.ok) { return new Response(x, { status: 403 }); }')
    if not any("cure runs too late" in p for p in check(swapped)):
        fails.append("auth-after-export ordering should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_export_supervisor_only self-test (no-supervisor / no-active / no-403 / auth-after-export redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
