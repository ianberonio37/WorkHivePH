#!/usr/bin/env python3
"""SESSION DEATH IS NOT REMOVAL.

An expired session returns ZERO ROWS with NO ERROR under RLS. That is
indistinguishable from "you were removed from this hive" unless the session is
checked -- and on 2026-08-20 asset-hub and shift-brain did not check. Both fell
into the not-a-member branch, which DELETES the user's saved hive keys and shows
"needs a hive - join or create one". A lapsed session silently destroyed the
user's hive selection and told them to go re-join.

Every sibling page (pm-scheduler, project-manager, inventory, logbook,
dayplanner, hive) has gated on a resolved auth uid since PRODUCTION_FIXES.md #37.
Those two were left behind by that migration.

The rule, for any page that wipes the hive keys behind a membership check:
  1. an auth uid is resolved from db.auth into a variable,
  2. a gate `if (!<uid>)` routes to sign-in,
  3. the gate runs BEFORE the membership check, and
  4. the gate is at a brace depth <= the membership call's, so it cannot sit
     inside a conditional the call does not share.

(4) is the one that matters and the one indentation cannot express: the first
attempt at this fix placed the gate INSIDE `if (!WORKER_NAME && ...) {`, at the
same visual indent as the call, where it would only ever run for users who
needed identity restored -- i.e. never on a normal load. It read as correct.
Only brace depth distinguishes a live gate from one in a dead path.

A uid is identified as a variable assigned from `user?.id` / `user.id`, which is
the shape BOTH platform idioms end in:
    _authUid = session?.user?.id || null;                    (destructured getSession)
    _authUid = (await db.auth.getUser())?.data?.user?.id;    (direct)
Keying on the call site instead missed the destructured form on three pages and
reported four false failures -- the instrument, not the pages. It also correctly
excludes a variable holding a session OBJECT, which is a sentinel the caller
routes on rather than a gate in its own right.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIPE = "['wh_active_hive_id','wh_hive_id','wh_hive_role','wh_hive_name']"
CALL = 'await validateHiveMembership()'
# a variable that receives an auth user id, in either platform idiom
UID_ASSIGN = re.compile(r'(\w+)\s*=\s*[^;\n]*\buser\s*\??\s*\.\s*id\b')
SIGNIN = 'signin=1'


def strip_noise(src):
    """Blank out strings/comments so brace counting sees only real structure."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == '//':
            j = src.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i))
            i = j
        elif two == '/*':
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(''.join(ch if ch == '\n' else ' ' for ch in src[i:j]))
            i = j
        elif c in '"\'`':
            j, q = i + 1, c
            while j < n:
                if src[j] == chr(92):
                    j += 2
                    continue
                if src[j] == q:
                    j += 1
                    break
                j += 1
            out.append(''.join(ch if ch == '\n' else ' ' for ch in src[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def depth_at(clean, pos):
    return clean.count('{', 0, pos) - clean.count('}', 0, pos)


def audit(text):
    """Return (finding_or_None, applies) for one page's source."""
    if WIPE not in text:
        return None, False
    clean = strip_noise(text)
    # strip_noise replaces every blanked char 1:1 (newlines preserved), so offsets in
    # `clean` and `text` are the SAME. Search the RAW text and count depth on the clean
    # copy: searching `clean` silently dropped project-manager.html from the roster
    # entirely, because one quote inside a literal made the scanner blank the region
    # holding the call. A page missing from a roster reads exactly like a page that
    # passed, which is the worst failure a gate can have.
    assert len(clean) == len(text), 'strip_noise changed length; offsets no longer align'
    call = text.find(CALL)
    if call < 0:
        # the wipe is not behind a membership check here (e.g. a real sign-out)
        return None, False
    call_depth = depth_at(clean, call)

    uids = [(m.start(), m.group(1)) for m in UID_ASSIGN.finditer(text) if m.start() < call]
    if not uids:
        return 'no auth uid is resolved before the membership check', True

    reasons = []
    for pos, var in uids:
        gate = re.search(r'if\s*\(\s*!\s*%s\s*\)' % re.escape(var), text[pos:call])
        if not gate:
            reasons.append('`%s` is resolved but never gated on' % var)
            continue
        gpos = pos + gate.start()
        if SIGNIN not in text[gpos:gpos + 400]:
            reasons.append('gate on `%s` does not route to sign-in' % var)
            continue
        gdepth = depth_at(clean, gpos)
        if gdepth > call_depth:
            reasons.append(
                'gate on `%s` sits at brace depth %d but the membership check runs at depth %d '
                '- it is inside a block the check does not share, so it is a DEAD PATH'
                % (var, gdepth, call_depth))
            continue
        return None, True  # a live, correctly-scoped gate exists

    return '; '.join(reasons), True


def main():
    if '--teeth' in sys.argv:
        violator = (
            "async function init() {\n"
            "  if (!WORKER_NAME) {\n"
            "    var _u = (await db.auth.getUser()).data.user.id;\n"
            "    if (!_u) { window.location.href = 'index.html?signin=1'; return; }\n"
            "  }\n"
            "  await validateHiveMembership();\n"
            "}\n"
            "x = " + WIPE + ";\n")
        satisfier = (
            "async function init() {\n"
            "  if (!WORKER_NAME) { WORKER_NAME = restore(); }\n"
            "  var _u = (await db.auth.getUser()).data.user.id;\n"
            "  if (!_u) { window.location.href = 'index.html?signin=1'; return; }\n"
            "  await validateHiveMembership();\n"
            "}\n"
            "x = " + WIPE + ";\n")
        vf, vd = audit(violator)
        sf, sd = audit(satisfier)
        print('TEETH violator : caught=%s  %s' % (bool(vf), vf or 'NOT CAUGHT'))
        print('TEETH satisfier: clean=%s   %s' % (not sf, sf or ''))
        if not (vd and vf and sd and not sf):
            print('FAIL: teeth test did not discriminate - the check is vacuous')
            return 1
        print('PASS: teeth test discriminates')
        return 0

    checked, failures = [], []
    for page in sorted(f for f in os.listdir(ROOT) if f.endswith('.html')):
        try:
            text = open(os.path.join(ROOT, page), encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        finding, applies = audit(text)
        if not applies:
            continue
        checked.append(page)
        if finding:
            failures.append('%s: %s' % (page, finding))

    print('SESSION DEATH IS NOT REMOVAL - pages wiping hive keys behind a membership check: %d'
          % len(checked))
    print('  %s' % ', '.join(checked))
    if failures:
        print('FAIL: %d page(s) treat a dead session as removal:' % len(failures))
        for f in failures:
            print('  - %s' % f)
        return 1
    print('PASS: every such page gates on a live auth uid, at a depth the check shares')
    return 0


if __name__ == '__main__':
    sys.exit(main())
