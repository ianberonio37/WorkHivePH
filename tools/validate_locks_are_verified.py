#!/usr/bin/env python3
"""validate_locks_are_verified.py — a LOCK must be backed by a gate that actually RAN and PASSED.

WHY (found 2026-08-31, the first genuine full board). validate_trajectory_registry rule 5 holds a
`locked` trajectory to NAMING a gate that is REGISTERED. Registration is not execution, and execution
is not a PASS. The first full board (mode=full, 0 skip) exposed TWO rows locked at 100% whose gate was
red: T11 (stock-ripple — a Use deducts stock but the ops-home tile never moves) and T176
(error-taxonomy-ratchet, 19→20). Both had been locked on a fast board that SKIPPED their gate. A green
summary that omits its skip count is not coverage, and a lock resting on a gate nobody watched pass is a
false 100%.

WHAT IT ASSERTS:
  • HARD (exit 1): no `locked` row (a 100% claim) names a gate that failed/was absent on the last board.
    A locked row's whole meaning is "the gate passes"; if it does not, the 100% is a lie and must fall.
  • SOFT (reported, not failed): `locking` rows whose gate is red are in-flight WIP — locking means the
    gate is BUILT, not that it passes yet, so a red gate there is expected and only lists what still
    blocks the lock.

★IT REFUSES RATHER THAN PASSES WHEN IT CANNOT TELL. If the only board on disk is `mode: fast`, it returns
UNVERIFIABLE, never OK — "I could not check" must never render as "checked", which is the exact silence
this finding is about. Registered in run_platform_checks (skip_if_fast=False: it must see the full board).
"""
import argparse, io, json, os, sys

CHECK_NAMES = ["locks-are-verified"]

GREEN = {'PASS', 'OK', 'GREEN'}
G, R, Y, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='.')
    ap.add_argument('--strict', action='store_true',
                    help='exit 1 when the board is fast (cannot verify) instead of warning')
    a = ap.parse_args(argv)

    h = json.load(io.open(os.path.join(a.repo, 'platform_health.json'), encoding='utf-8'))
    d = json.load(io.open(os.path.join(a.repo, 'trajectory_registry.json'), encoding='utf-8'))
    mode = str(h.get('mode') or '')
    status = {r.get('id'): str(r.get('status', '')).upper() for r in (h.get('validators') or [])}
    skips = sum(1 for v in status.values() if v == 'SKIP')

    print("  board %s  mode=%s  gates=%d  skipped=%d"
          % (str(h.get('timestamp'))[:16], mode or '(full)', len(status), skips))

    if mode == 'fast':
        print("%sUNVERIFIABLE%s locks-are-verified: the only board on disk is mode='fast', which SKIPPED"
              " %d gates. A lock's gate cannot be confirmed from a board that did not run it, and"
              " reporting OK here would be the exact silence this check exists to break."
              % (Y, RST, skips))
        return 1 if a.strict else 0

    bad_locked, bad_locking = [], []
    for t in d['trajectories']:
        if t['status'] not in ('locked', 'locking'):
            continue
        gs = (t.get('artifacts') or {}).get('gates') or []
        # normalise the SAME way rule 5 does (split an 'name(annotation)' at '(' before resolving) —
        # two checkers reading one field by different rules will always eventually disagree.
        off = [(g, status.get(g.split('(')[0], 'ABSENT'))
               for g in gs if status.get(g.split('(')[0]) not in GREEN]
        if off:
            (bad_locked if t['status'] == 'locked' else bad_locking).append((t['id'], t['pct'], off))

    n = sum(1 for t in d['trajectories'] if t['status'] in ('locked', 'locking'))
    if bad_locking:
        print("%s  %d locking row(s) still owe a green gate (WIP, not a false 100%%):%s" % (Y, len(bad_locking), RST))
        for tid, pct, off in bad_locking[:25]:
            print("    %-5s %3d%%  %s" % (tid, pct, '; '.join('%s=%s' % x for x in off))[:150])
    if bad_locked:
        print("\n%sFAIL%s locks-are-verified: %d LOCKED row(s) at 100%% name a gate that did NOT pass on"
              " this full board — a false 100%%, correct it down or fix the gate:" % (R, RST, len(bad_locked)))
        for tid, pct, off in bad_locked[:25]:
            print("  %-5s %3d%%  %s" % (tid, pct, '; '.join('%s=%s' % x for x in off))[:150])
        return 1
    print("%sPASS%s locks-are-verified: every LOCKED row rests on a gate that PASSED on a full board "
          "(%d locked/locking checked)." % (G, RST, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
