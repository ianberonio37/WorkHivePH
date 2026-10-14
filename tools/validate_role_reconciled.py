#!/usr/bin/env python3
"""validate_role_reconciled.py - a page that gates on the STORED role asks the server first (gate `role-reconciled`).

SL sub-layer AU2 (2026-10-14): "the platform decides what this person may do from the server's answer, never from a
role remembered on the device." `wh_hive_role` is a cache of one server fact - the person's hive_members.role - and it
goes stale on every demotion, promotion, removal or hive change made on another device. Walked live with the same
person in two states (server 'worker', device 'supervisor' and the reverse), seven pages decided from the cache:
alert-hub (Approve / Reject, Ack / Resolve), audit-log (the whole filtered log and CSV export), community (Mod Queue,
Pin / Delete / Make public), integrations (the CMMS console, for a solo owner too), plant-connections (the plant
console), index (supervisor actions, via a display mode DERIVED from the stale role) and analytics (Recompute risk,
behind a phase the at-rest read never opened). Each write then met an RLS refusal; the fix is utils.js
whReconcileHiveRole(db), awaited before the first role-gated render.

A page DEPENDS on the stored role when its code (comments stripped) both reads it - getItem('wh_hive_role') or a
WHRoles call, which reads the same key - and either compares a role (`*role* === 'supervisor'` and kin, or
WHRoles.isSupervisor()) or SHOWS it (a variable read from the key written into textContent / innerText / innerHTML:
resume's pill told a demoted person "supervisor"). Each such page must be RECONCILED, by one of:
  - a call to whReconcileHiveRole(...);
  - its own membership read that writes the answer back (from('hive_members') ... select(... role ...) AND
    setItem('wh_hive_role', ...)) - project-manager's and the hive board's precedent;
  - `role-reconcile-allow: <reason>` in the page, for a comparison that gates nothing a person can do.
The order (reconcile BEFORE the first gated render) is proven by the live AU2 walk; this gate holds the presence.

  python tools/validate_role_reconciled.py
  python tools/validate_role_reconciled.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# a real comment opener is never glued to a word character, a quote, '*', '/' or '=': `accept="image/*"` would
# otherwise open a "comment" that swallows real code up to the next */ - it hid resume's role read from this gate
# ([[feedback_accept_image_star_broke_comment_stripping]])
_BLOCK_C = re.compile(r"(?<![\w\"'*/=])/\*.*?\*/", re.S)
_LINE_C = re.compile(r"^\s*//.*$", re.M)
_HTML_C = re.compile(r"<!--.*?-->", re.S)

ROLE_READ = re.compile(r"getItem\(\s*['\"]wh_hive_role['\"]\s*\)|\bWHRoles\.\w+\s*\(")
# the same comparison validate_role_checks.py counts (an identifier naming a role, compared to a role literal)
ROLE_CMP = re.compile(
    r"\b[A-Za-z_]*[Rr][Oo][Ll][Ee][A-Za-z_]*\s*(?:===|!==|==|!=)\s*['\"](?:supervisor|engineer|field|worker|admin|owner)['\"]"
    r"|\bWHRoles\.isSupervisor\s*\(")
# ★SHOWING THE ROLE IS DEPENDING ON IT TOO (BRH-F resume, 2026-10-14). resume's context pill printed
# "Plant · supervisor" from the stored key alone - no comparison, so no gate saw it, yet it told a demoted person a role
# the server no longer gives. A variable read from the key and written into text on screen makes the page depend on it.
ROLE_VAR = re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*localStorage\.getItem\(\s*['\"]wh_hive_role['\"]\s*\)")


def _displays_role(code: str) -> bool:
    return any(re.search(r"(?:textContent|innerText|innerHTML)\s*\+?=[^;\n]*\b" + re.escape(v) + r"\b", code)
               for v in ROLE_VAR.findall(code))


RECONCILE = re.compile(r"\bwhReconcileHiveRole\s*\(")
# ★A MEMBERSHIP READ SOMEWHERE IN THE PAGE IS NOT A RECONCILE ON EVERY LOAD. The first version of this gate passed
# any page holding a hive_members role read plus a write-back - and so passed index.html as it stood, whose only such
# read is the resolver that runs when NO hive is stored, while the live walk had just shown index deciding from a stale
# role. Presence cannot prove the read runs, so a page that reconciles with its OWN read is named here with the walk
# that proved it (same person, server 'worker', device 'supervisor': identical controls at 390 and 1280), and the read
# must still be in the page.
OWN_READ_VERIFIED = {
    "asset-hub.html": "SL1355 AU2 walk 2026-10-14",
    "hive.html": "SL1357 AU2 walk 2026-10-14",
    "inventory.html": "SL1360 AU2 walk 2026-10-14",
    "logbook.html": "SL1361 AU2 walk 2026-10-14",
    "pm-scheduler.html": "SL1363 AU2 walk 2026-10-14",
    "project-manager.html": "SL1364 AU2 walk 2026-10-14 (rewrote the false role to the server's)",
    "shift-brain.html": "SL1366 AU2 walk 2026-10-14",
}
# the base table, or v_worker_truth - the canonical view over hive_members that shift-brain's gate reads (by auth_uid)
OWN_MEMBERSHIP_READ = re.compile(
    r"from\(\s*['\"](?:hive_members|v_worker_truth)['\"]\s*\)[\s\S]{0,600}?\.select\(\s*['\"][^'\"]*\brole\b")
ROLE_WRITE_BACK = re.compile(r"setItem\(\s*['\"]wh_hive_role['\"]")
ALLOW = re.compile(r"role-reconcile-allow:\s*\S")


def _code(text: str) -> str:
    return _LINE_C.sub("", _BLOCK_C.sub("", _HTML_C.sub("", text)))


def classify(text: str, name: str = "") -> tuple[bool, str]:
    """(role_gated, how_reconciled) - how is '' when a role-gated page is NOT reconciled."""
    code = _code(text)
    depends = bool(ROLE_READ.search(code) and (ROLE_CMP.search(code) or _displays_role(code)))
    if ALLOW.search(text):
        return depends, "allow"
    if not depends:
        return False, ""
    if RECONCILE.search(code):
        return True, "whReconcileHiveRole"
    if name in OWN_READ_VERIFIED and OWN_MEMBERSHIP_READ.search(code) and ROLE_WRITE_BACK.search(code):
        return True, f"own membership read + write-back, {OWN_READ_VERIFIED[name]}"
    return True, ""


def _first_line(text: str, rx: re.Pattern) -> int:
    m = rx.search(text)
    return text[:m.start()].count("\n") + 1 if m else 0


def self_test() -> int:
    own = ("let HIVE_ROLE = localStorage.getItem('wh_hive_role');\nconst { data } = await db.from('hive_members')"
           ".select('role').eq('hive_id', H).eq('auth_uid', U).maybeSingle();\nlocalStorage.setItem('wh_hive_role', data.role);\n"
           "if (HIVE_ROLE === 'supervisor') show();")
    cases = [
        # (name, page, text, expect_gated, expect_reconciled)
        ("cache-only gate (the defect)", "x.html",
         "const HIVE_ROLE = localStorage.getItem('wh_hive_role') || '';\nif (HIVE_ROLE === 'supervisor') show();", True, False),
        ("reconciled by the helper", "x.html",
         "let HIVE_ROLE = localStorage.getItem('wh_hive_role');\nconst r = await whReconcileHiveRole(db);\n"
         "if (HIVE_ROLE === 'supervisor') show();", True, True),
        ("a COMMENT naming the helper is not a call", "x.html",
         "const HIVE_ROLE = localStorage.getItem('wh_hive_role');\n// whReconcileHiveRole(db) would fix this\n"
         "/* whReconcileHiveRole(db) */\nif (HIVE_ROLE === 'supervisor') show();", True, False),
        ("own membership read on a page the walk verified", "project-manager.html", own, True, True),
        ("the SAME read on an unverified page is not proof it runs (index's no-hive resolver)", "index.html", own, True, False),
        ("the canonical membership view + write-back, verified", "shift-brain.html",
         "let HIVE_ROLE = localStorage.getItem('wh_hive_role');\nlet q = db.from('v_worker_truth').select('role, hive_status')"
         ".eq('hive_id', H);\nlocalStorage.setItem('wh_hive_role', membership.role);\nif (HIVE_ROLE === 'supervisor') show();",
         True, True),
        ("a verified page whose read is GONE fails", "shift-brain.html",
         "let HIVE_ROLE = localStorage.getItem('wh_hive_role');\nif (HIVE_ROLE === 'supervisor') show();", True, False),
        ("membership read WITHOUT the write-back is not enough", "project-manager.html",
         "let HIVE_ROLE = localStorage.getItem('wh_hive_role');\nconst { data } = await db.from('hive_members')"
         ".select('role').eq('hive_id', H);\nif (HIVE_ROLE === 'supervisor') show();", True, False),
        ("WHRoles gates on the same key", "x.html",
         "if (WHRoles.isSupervisor()) show();", True, False),
        ("a role SHOWN on screen is depended on (resume's pill)", "x.html",
         "const HIVE_ROLE = localStorage.getItem('wh_hive_role') || 'worker';\n"
         "p.textContent = '\\u{1F3ED} ' + HIVE_NAME + (HIVE_ROLE ? ' \\u00b7 ' + HIVE_ROLE : '');", True, False),
        ("...and reconciled before it paints", "x.html",
         "let HIVE_ROLE = localStorage.getItem('wh_hive_role') || 'worker';\nconst r = whReconcileHiveRole(db);\n"
         "p.textContent = HIVE_NAME + ' \\u00b7 ' + HIVE_ROLE;", True, True),
        ("a read never compared and never shown is not a dependence (marketplace-admin)", "x.html",
         "const HIVE_ROLE = localStorage.getItem('wh_hive_role') || '';\nconst ok = await isPlatformAdmin();", False, False),
        ("an accept=\"image/*\" attribute does not open a comment that hides the role read", "x.html",
         "<input type=\"file\" accept=\"image/*\">\n<script>\nconst HIVE_ROLE = localStorage.getItem('wh_hive_role');\n"
         "if (HIVE_ROLE === 'supervisor') show();\n/* a real comment */\n</script>", True, False),
        ("allow marker", "x.html",
         "// role-reconcile-allow: both branches are 'supervisor'\nvar HIVE_ROLE = localStorage.getItem('wh_hive_role');\n"
         "var v = HIVE_ROLE === 'supervisor' ? 'supervisor' : 'supervisor';", True, True),
    ]
    ok = True
    for name, page, text, g, rec in cases:
        gated, how = classify(text, page)
        good = gated == g and bool(how) == rec
        ok &= good
        print(f"  {'ok ' if good else 'BAD'} {name}: gated={gated} reconciled={how or '-'}")
    print("role-reconciled self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
    gated, bad = [], []
    for p in sorted(ROOT.glob("*.html")):
        text = io.open(p, encoding="utf-8", errors="replace").read()
        g, how = classify(text, p.name)
        if not g:
            continue
        gated.append((p.name, how))
        if not how:
            line = _first_line(text, ROLE_READ)
            bad.append(f"{p.name}:{line} gates on the stored role (wh_hive_role) and never asks the server - await "
                       f"whReconcileHiveRole(db) before the first role-gated render")
    print(f"role-reconciled: {len(gated)} page(s) gate on the stored role; "
          f"{len(gated) - len(bad)} reconcile it with the server.")
    for name, how in gated:
        if how:
            print(f"  ok   {name} ({how})")
    for b in bad:
        print(f"  FAIL {b}")
    if bad:
        print(f"role-reconciled: FAIL - {len(bad)} page(s) decide from a role the device remembers.")
        return 1
    print("role-reconciled: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
