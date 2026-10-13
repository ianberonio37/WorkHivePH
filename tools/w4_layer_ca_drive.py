"""w4_layer_ca_drive.py - drive the wave-4 CA-layer rows through the Playwright MCP, batch by batch (2026-10-08).

"The platform must speak, on this page, the words a Philippine maintenance crew uses, lived start to end." The bar is
tools/prove_w4_layer_ca.mjs's (a Playwright LIBRARY prover, so it cannot bank - memory feedback_a_library_batch_is_not_an_mcp_walk):
the row's path walked as its person at its axis, identity kept, at least 4 pages, no overlapping control on any step,
and on the SUBJECT page the platform's language stamps plus at least 4 of the crew's own words. The reading now runs in
tools/w4_action_walk.body.js (kind `layer-ca`), so the receipt's instrument is the MCP walk.

  python tools/w4_layer_ca_drive.py --list
  python tools/w4_layer_ca_drive.py batch [N]   # bank the last batch's walked groups (one ledger pass), write the next N
  (walk:  python tools/browser_lock.py acquire main  ->  browser_run_code_unsafe { filename: tools/w4_action_batch.js }
          ->  python tools/browser_lock.py release main)
"""
import io, json, os, re, subprocess, sys, tempfile, time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, 'tools')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BATCH = os.path.join('.tmp', 'w4_args_batch.json')
SKIP = os.path.join('.tmp', 'w4_layer_ca_skip.json')



def _walked_at(gid):
    """the local ISO time the group's walk ran - its records file - for record_mcp_walk.py --walked-at (2026-10-12)"""
    import datetime as _dt
    p = os.path.join('.tmp', 'w4_steps', '%s.records.json' % gid)
    return _dt.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec='seconds') if os.path.exists(p) else ''

def short_of(t):
    m = re.search(r' - ([^·]+) · ', t.get('title') or '')
    return m.group(1).strip() if m else ''


def subject_page(t):
    if t.get('persona') == 'anon':
        return (t.get('pages') or [None])[0]
    s = short_of(t).lower()
    for p in t.get('pages') or []:
        if re.sub(r'[-_/]', ' ', p.replace('.html', '')).lower() == s:
            return p
    return (t.get('pages') or [None])[-1]


def axis(t):
    return '%s %s' % (t['axis']['device'], t['axis']['language'])


def groups():
    import live_walk_manifest as m
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    opn = {r['id'] for r in rows if not m.row_closed(r)}
    g = {}
    for t in reg:
        w4 = t.get('w4') or {}
        if t['id'] not in opn or w4.get('kind') != 'layer' or w4.get('layer') != 'CA':
            continue
        who = 'anon' if t.get('persona') == 'anon' else ((t.get('journey') or {}).get('vertical') or '')
        g.setdefault(('>'.join(t.get('pages') or []), who, axis(t)), []).append(t)
    return {('LG' + v[0]['id']): (k, v) for k, v in sorted(g.items(), key=lambda kv: (kv[0][2], kv[1][0]['id']))}


def args_for(gid, key, grp):
    pages, who, ax = key
    pg = json.load(io.open('.tmp/w4_action_pg.json', encoding='utf-8'))
    dev, lang = ax.split(' ')
    w, h = (320, 720) if dev == 'narrow-320' else (390, 844)
    a = {'id': gid, 'axis': ax, 'pages': pages.split('>'), 'lang': lang, 'width': w, 'height': h,
         'origin': 'http://localhost:5000/workhive', 'api': 'http://127.0.0.1:54321',
         'anonKey': io.open('.tmp/local_anon_key.txt', encoding='utf-8').read().strip(),
         'actions': [{'id': t['id'], 'kind': 'layer-ca', 'subject': 'CA', 'subjectPage': subject_page(t)} for t in grp],
         'sigs': {}, 'safeRpcs': {}, 'hiveId': None, 'anon': who == 'anon'}
    if who != 'anon':
        c = pg['cast'].get(who) or {}
        person = c.get('worker') or c.get('supervisor')   # a hive whose only account is its supervisor is lived by them
        if not person:
            return None
        if person['user'] == 'ianphone':
            return None
        a.update({'user': person['user'], 'pass': 'test1234', 'castName': person['name'], 'hiveId': c.get('hive_id')})
    return a


def bank_group(args, pending):
    gid = args['id']
    recs = json.load(io.open(os.path.join('.tmp', 'w4_steps', '%s.records.json' % gid), encoding='utf-8'))
    steps = json.load(io.open(os.path.join('.tmp', 'w4_steps', '%s.json' % gid), encoding='utf-8'))
    if isinstance(steps, dict):
        steps = steps.get('steps') or []
    answers = recs.get('answers') or {}
    compact = [{'page': s.get('page'), 'chars': s.get('chars'), 'identityKept': s.get('identityKept', True),
                'loadError': s.get('loadError') or None, 'lang': s.get('lang'),
                'fit': {'findings': (s.get('fit') or {}).get('findings') or 0, 'occlusion': ((s.get('fit') or {}).get('occlusion') or [])[:4],
                        'overflowEl': ((s.get('fit') or {}).get('overflowEl') or [])[:2], 'wrapped': ((s.get('fit') or {}).get('wrapped') or [])[:2]}}
               for s in steps]
    sp = os.path.join('.tmp', 'w4_steps', '%s.compact.json' % gid)
    io.open(sp, 'w', encoding='utf-8', newline='\n').write(json.dumps(compact, ensure_ascii=False))
    all_ok = True
    for a in args['actions']:
        rid = a['id']; ans = answers.get(rid) or {}
        cmd = [sys.executable, 'tools/record_mcp_walk.py', '--id', rid, '--walked-at', _walked_at(gid), '--instrument', 'playwright-mcp + postgres-mcp',
               '--cast', recs.get('cast') or args.get('castName') or 'anonymous reader', '--axis', args['axis'],
               '--layer', 'CA', '--steps', sp,
               # castNote (2026-10-12): who pressed it when the row's persona is not a person (a machine client's operator)
               '--note', ((args['castNote'] + ' ') if args.get('castNote') else '') + (ans.get('note') or '')[:1200]]
        if not ans.get('ok'):
            all_ok = False
            cmd += ['--unproven', '; '.join(ans.get('problems') or ['not lived clean'])[:300]]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if not ans.get('ok'):
            print('  %s open: %s' % (rid, '; '.join(ans.get('problems') or [])[:240]))
        if r.returncode != 0:
            print('    record_mcp_walk FAILED: %s' % (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200])
            continue
        pending.append((rid, args['axis']))
    return all_ok


def advance_many(label, items):
    import importlib
    import bank_w4_passers as bwp
    import live_walk_manifest as m
    importlib.reload(m)
    rec = m._w4_receipts()
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))
    byid = {t['id']: t for t in reg['trajectories']}
    entries, banked = [], []
    for rid, ax in items:
        t = byid[rid]; res = rec.get(rid) or {}
        if res.get('ok') and m._w4_missing(t, rec) == '' and 'playwright-mcp' in str(res.get('instrument')):
            entries.append({'ids': rid, 'status': 'locking', 'pct': 60, 'gate': [bwp.GATES.get(('layer', ax))],
                            'basis': bwp._basis(t, res, ax)})
            banked.append(rid)
        elif res.get('ok'):
            print('  held %s: %s' % (rid, m._w4_missing(t, rec)))
    if entries:
        bf = os.path.join('.tmp', 'w4_bank_%s.json' % label)
        io.open(bf, 'w', encoding='utf-8', newline='\n').write(json.dumps(entries, ensure_ascii=False, indent=1))
        r = subprocess.run([sys.executable, 'tools/advance_trajectory.py', '--batch', bf], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        out = (r.stdout or '') + (r.stderr or '')
        print('  advance:', ([l for l in out.splitlines() if 'advanced' in l or 'FAIL' in l or 'refus' in l] or [out.strip()[-200:]])[-1][:200])
        if r.returncode != 0:
            raise SystemExit(1)
        today = time.strftime('%Y-%m-%d')
        reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))
        for t in reg['trajectories']:
            if t['id'] not in banked:
                continue
            parts = re.split(r' · (?=\[\d{4}-\d{2}-\d{2}\])', t.get('basis') or '')
            last = parts[-1]
            if len(parts) > 1 and last.startswith('[%s]' % today) and ('WALKED LIVE %s via' % today) in last:
                t['basis'] = last + ' || ' + ' · '.join(parts[:-1])
        fd, tmp = tempfile.mkstemp(dir=PROJ, suffix='.tmp'); os.close(fd)
        io.open(tmp, 'w', encoding='utf-8', newline='\n').write(json.dumps(reg, ensure_ascii=False, indent=1) + '\n')
        os.replace(tmp, 'trajectory_registry.json')
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    ids = {r for r, _ in items}
    print('%s: %d recorded, %d banked, %d CLOSED in the ledger' % (label, len(items), len(banked),
          sum(1 for r in rows if r['id'] in ids and m.row_closed(r))))


def cmd_batch(n):
    skip = json.load(io.open(SKIP, encoding='utf-8')) if os.path.exists(SKIP) else {}
    pending = []
    if os.path.exists(BATCH):
        t0 = os.path.getmtime(BATCH)
        for args in json.load(io.open(BATCH, encoding='utf-8')):
            if not str(args.get('id', '')).startswith('LG'):
                continue
            rp = os.path.join('.tmp', 'w4_steps', '%s.records.json' % args['id'])
            if os.path.exists(rp) and os.path.getmtime(rp) > t0:
                if not bank_group(args, pending):
                    skip[args['id']] = time.strftime('%Y-%m-%d %H:%M') + ' stayed open'
            else:
                print('%s was not walked since the batch was written' % args['id'])
        io.open(SKIP, 'w', encoding='utf-8', newline='\n').write(json.dumps(skip, indent=1))
        if pending:
            advance_many('LAYERCA-batch', pending)
    gs = groups()
    batch = []
    for gid, (key, grp) in gs.items():
        if gid in skip:
            continue
        a = args_for(gid, key, grp)
        if a:
            batch.append(a)
        if len(batch) >= n:
            break
    io.open(BATCH, 'w', encoding='utf-8', newline='\n').write(json.dumps(batch, ensure_ascii=False))
    print('%d groups open (%d rows), %d skipped as stayed-open; batch of %d written' % (
        len(gs), sum(len(v) for _, v in gs.values()), len(skip), len(batch)))


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    if sys.argv[1] == '--list':
        for gid, (k, v) in groups().items():
            print(gid, k[2], '|', k[1], '|', k[0], '|', len(v), 'rows, subject', subject_page(v[0]))
    elif sys.argv[1] == 'batch':
        cmd_batch(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    else:
        print(__doc__); raise SystemExit(2)
