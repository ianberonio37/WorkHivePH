# -*- coding: utf-8 -*-
"""Bank the 76 W3-SC (shared-component) critic rows against the prove_shared_components gate verdict.

W3-SC critic rows carry no UI surface ("no_ui_basis: critiqued against its contract"); they are graded
by tools/prove_shared_components.mjs (the shared-components gate), which prints one verdict line per
(lens, component): `  ok|n/a|BAD  <U|A|I|F> <component.js>  <detail>`. This reads those lines from the
gate log, matches each pending W3-SC critic row by its component (from the trajectory title) + lens
(from ufai), and marks it critiqued: clean for ok/n-a (the verdict detail as clean_note), a finding for
BAD. Deterministic, no browser. --apply to write.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(HERE, '.tmp', 'prove_sc.log')
CRIT = os.path.join(HERE, 'critic_registry.json')
TRAJ = os.path.join(HERE, 'trajectory_registry.json')
APPLY = '--apply' in sys.argv

# A-lens tap-target findings map to F1 (the 44px mobile tap-target dim); keep the vocabulary valid.
LENS_FAIL_DIM = {'A': 'F1', 'U': 'A1', 'I': 'I2', 'F': 'F2'}

verdict = {}  # (lens, component) -> (status, detail)
for ln in io.open(LOG, encoding='utf-8', errors='replace'):
    m = re.match(r'\s+(ok|n/a|BAD|FAIL)\s+([UAIF])\s+([\w.\-]+\.js)\s+(.*)', ln)
    if m:
        st, lens, comp, detail = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        verdict[(lens, comp)] = ('bad' if st in ('BAD', 'FAIL') else 'ok', detail)

print('parsed %d lens verdicts from the gate log' % len(verdict))

cr = json.load(io.open(CRIT, encoding='utf-8'))
crows = cr if isinstance(cr, list) else cr.get('rows', cr.get('trajectories', []))
tr = json.load(io.open(TRAJ, encoding='utf-8'))
tmap = {x['id']: x for x in (tr if isinstance(tr, list) else tr.get('rows', tr.get('trajectories', [])))}

banked = clean = flagged = unmatched = 0
for x in crows:
    if x.get('wave') != 'W3-SC' or x.get('status') != 'pending':
        continue
    t = tmap.get(x['id'], {})
    title = (t.get('title') or '') + ' ' + (t.get('story') or '')
    cm = re.search(r'([\w.\-]+\.js)', title)
    comp = cm.group(1) if cm else None
    ufai = (t.get('ufai') or [])
    lens = ufai[0] if ufai else None
    v = verdict.get((lens, comp))
    if not v:
        unmatched += 1
        print('  UNMATCHED %s: comp=%s lens=%s' % (x['id'], comp, lens))
        continue
    st, detail = v
    x['dims_graded'] = [lens]
    if st == 'ok':
        x['findings'] = []
        x['clean_note'] = ('W3-SC contract critique (prove_shared_components gate, %s lens on %s): %s. '
                           'No UI surface beyond the contract (no_ui_basis).' % (lens, comp, detail))
        clean += 1
    else:
        dim = LENS_FAIL_DIM.get(lens, 'A1')
        x['findings'] = [{
            'dim': dim, 'layer': 'heuristic', 'severity': 2,
            'evidence': '%s (%s lens, shared-components gate): %s' % (comp, lens, detail),
            'owner': 'Designer',
            'receipt': 'prove_shared_components.mjs contract gate',
        }]
        x['clean_note'] = 'W3-SC contract critique: %s %s lens FAILED - %s' % (comp, lens, detail)
        flagged += 1
    x['status'] = 'critiqued'
    banked += 1

print('W3-SC rows: banked %d (clean %d, flagged %d), unmatched %d' % (banked, clean, flagged, unmatched))
if APPLY and not unmatched:
    io.open(CRIT, 'w', encoding='utf-8').write(json.dumps(cr, indent=1, ensure_ascii=False))
    print('APPLIED to critic_registry.json')
elif unmatched:
    print('NOT applied - resolve unmatched rows first')
else:
    print('dry-run - pass --apply to write')
