#!/usr/bin/env python3
"""
validate_leave_audit_ordering.py  --  LOCK for the "audit lost to a race with a permission-removing
self-delete" bug (found live 2026-07-07, deep-walk dim-6 destructive-action pass).

hive.html `performLeave` deletes the caller's OWN hive_members row. The hive_audit_log INSERT policy
(`hive_audit_log_hive_rw`) requires `hive_id IN user_hive_ids()` — active membership — so once that
delete commits, the audit insert is REJECTED. The code wrote the `member_left` audit FIRST, but via a
FIRE-AND-FORGET `writeAuditLog(...)` (no await) immediately followed by `await ...delete()`, so the two
raced: whenever the delete committed first, the member_left audit was silently lost. Fixed by making
`writeAuditLog` RETURN the insert promise and `await`-ing it before the delete.

Contract enforced (two static invariants in hive.html):
  1. writeAuditLog is AWAITABLE — it `return`s the hive_audit_log insert promise (so callers CAN await).
  2. performLeave AWAITS the member_left audit BEFORE the hive_members self-delete.

Usage:  python tools/validate_leave_audit_ordering.py [--json] [--selftest]
Exit 0 = clean, 1 = a violation (or self-test failure).
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent
HIVE = ROOT / "hive.html"

AWAITABLE_RE = re.compile(r"return\s+db\.from\(\s*['\"]hive_audit_log['\"]\s*\)\s*\.insert", re.I)
# performLeave body: from the function decl to its closing (bounded window).
PERFORMLEAVE_RE = re.compile(r"function\s+performLeave\s*\([^)]*\)\s*\{(.*?)\n\}", re.I | re.S)
AWAIT_AUDIT_RE = re.compile(r"await\s+writeAuditLog\(\s*['\"]member_left['\"]", re.I)
DELETE_RE = re.compile(r"\.from\(\s*['\"]hive_members['\"]\s*\)\s*\.delete\(", re.I)


def analyze(text):
    viols = []
    if not AWAITABLE_RE.search(text):
        viols.append("writeAuditLog does not RETURN the hive_audit_log insert promise -> callers cannot await it (the member_left audit will race a follow-on delete)")
    m = PERFORMLEAVE_RE.search(text)
    if not m:
        # If performLeave is renamed/removed, the specific check can't run; don't fail spuriously.
        return viols
    body = m.group(1)
    del_m = DELETE_RE.search(body)
    aud_m = AWAIT_AUDIT_RE.search(body)
    if del_m:
        if not aud_m:
            viols.append("performLeave deletes hive_members but does NOT `await writeAuditLog('member_left'...)` -> the audit races the delete and is lost when the delete wins")
        elif aud_m.start() > del_m.start():
            viols.append("performLeave awaits the member_left audit AFTER the hive_members delete -> too late; membership is gone so the audit insert is RLS-rejected")
    return viols


def selftest():
    good = (
        "function writeAuditLog(a){ return db.from('hive_audit_log').insert({}).then(()=>{}); }\n"
        "async function performLeave(){\n"
        "  await writeAuditLog('member_left','hive_members',null,W,{});\n"
        "  await db.from('hive_members').delete().eq('worker_name', W);\n}\n"
    )
    bug_noawait = (
        "function writeAuditLog(a){ return db.from('hive_audit_log').insert({}).then(()=>{}); }\n"
        "async function performLeave(){\n"
        "  writeAuditLog('member_left','hive_members',null,W,{});\n"
        "  await db.from('hive_members').delete().eq('worker_name', W);\n}\n"
    )
    bug_notawaitable = (
        "function writeAuditLog(a){ db.from('hive_audit_log').insert({}).then(()=>{}); }\n"
        "async function performLeave(){\n"
        "  await writeAuditLog('member_left','hive_members',null,W,{});\n"
        "  await db.from('hive_members').delete().eq('worker_name', W);\n}\n"
    )
    bug_afterdelete = (
        "function writeAuditLog(a){ return db.from('hive_audit_log').insert({}).then(()=>{}); }\n"
        "async function performLeave(){\n"
        "  await db.from('hive_members').delete().eq('worker_name', W);\n"
        "  await writeAuditLog('member_left','hive_members',null,W,{});\n}\n"
    )
    cases = [("fixed (await before delete)", good, 0), ("fire-and-forget race (the bug)", bug_noawait, 1),
             ("writeAuditLog not awaitable", bug_notawaitable, 1), ("audit awaited AFTER delete", bug_afterdelete, 1)]
    ok = True
    for name, text, expect in cases:
        n = len(analyze(text))
        status = "PASS" if n == expect else "FAIL"
        if n != expect:
            ok = False
        print(f"  selftest {status}: {name}  (expected {expect}, got {n})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("leave-audit-ordering selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    if not HIVE.exists():
        print(json.dumps({"skipped": True}) if as_json else "  SKIP: hive.html not found")
        return 0
    viols = analyze(HIVE.read_text(encoding="utf-8", errors="ignore"))
    if as_json:
        print(json.dumps({"violations": viols, "count": len(viols)}, indent=2))
    else:
        print("leave-audit-ordering (hive.html member_left audit is awaited before the self-delete)")
        if not viols:
            print("  PASS: writeAuditLog is awaitable and performLeave records the audit before the delete")
        else:
            print(f"  FAIL: {len(viols)} issue(s):")
            for v in viols:
                print(f"    {v}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
