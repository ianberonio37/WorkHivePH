"""w4_confusion_drive.py - drive the wave-4 CONFUSION rows (w4_confusions.json -> registry rows of kind 'confusion')
through the Playwright MCP.

The confusion rows were lived by tools/prove_w4_confusions.mjs (the Playwright LIBRARY) and retracted with every
library-banked row on 2026-09-15 ("I thought we are using relevant live MCPs?"). tools/w4_action_walk.body.js now lives
them in the MCP's own browser (2026-10-12): it evaluates the prover's own predicates - one source - on the row's page,
along the row's path, as a WORKER of the row's hive (the prover's cast rule), at the row's axis.

  python tools/w4_confusion_drive.py --list          every open group: gid, axis, path, hive, confusions
  python tools/w4_confusion_drive.py prep <gid>      write .tmp/w4_args.json for that group
  (walk:  browser_run_code_unsafe { filename: tools/w4_action_walk.js })
  python tools/w4_confusion_drive.py bank <gid>      record each row's receipt and advance what now passes
  python tools/w4_confusion_drive.py next [gid...]   bank the group just walked (if any), then prep the next open one

A group is the rows that share a path, a hive and an axis - one sign-in, one walk. C2 and C3 walk alone: they change
the sign-in itself (a 10 s login, a 503 outage), which no other row of the group should meet.
Nothing here writes to the `ianphone` account: the cast is a seeded local worker of the row's own hive.
"""
import io, json, os, subprocess, sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, 'tools')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import w4_write_drive as wd

NEVER_USERS = {'ianphone'}
SOLO = ('C2', 'C3')   # they change the sign-in itself


def open_rows():
    import live_walk_manifest as m
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    opn = {r['id'] for r in rows if not m.row_closed(r)}
    return [t for t in reg if t['id'] in opn and (t.get('w4') or {}).get('kind') == 'confusion']


def groups():
    g = {}
    for t in open_rows():
        cid = t['w4'].get('confusion') or ''
        hive = (t.get('journey') or {}).get('vertical') or ''
        key = ('>'.join(t.get('pages') or []), hive, wd.axis(t), cid if cid in SOLO else '')
        g.setdefault(key, []).append(t)
    return {('FG' + v[0]['id']): (k, v) for k, v in sorted(g.items(), key=lambda kv: (kv[0][2], kv[1][0]['id']))}


def cast_of(hive):
    """a WORKER of the row's hive with an account - the prover's cast rule, read through postgres"""
    rc, out, err = wd.psql(
        "select m.worker_name || '|' || split_part(u.email, '@', 1) from hives h join hive_members m on m.hive_id = h.id "
        "join auth.users u on u.id = m.auth_uid where m.status = 'active' and m.role = 'worker' and h.name = '%s' "
        "order by m.worker_name limit 1;" % hive.replace("'", "''"))
    line = (out or '').strip().splitlines()[0] if rc == 0 and (out or '').strip() else ''
    if '|' not in line:
        return None
    name, user = line.split('|', 1)
    return {'name': name, 'user': user}


def cmd_list():
    gs = groups(); n = 0
    for gid, (k, v) in gs.items():
        n += len(v)
        print(gid, k[2], '|', k[1], '|', k[0], '|', len(v), 'rows:', ','.join(t['w4']['confusion'] for t in v))
    print(len(gs), 'groups,', n, 'rows')


def cmd_prep(gid, gs=None, write=True):
    gs = gs or groups()
    if gid not in gs:
        print('no such open group', gid); raise SystemExit(2)
    (pages, hive, ax, _solo), grp = gs[gid]
    dev, lang = ax.split(' ')
    w, h = (320, 720) if dev == 'narrow-320' else (390, 844)
    who = cast_of(hive)
    if not who:
        print('NO CAST: no active worker with an account in', hive); raise SystemExit(2)
    if who['user'] in NEVER_USERS:
        print('REFUSED: never walk as', who['user']); raise SystemExit(2)
    ledger = {e['id']: e for e in json.load(io.open('w4_confusions.json', encoding='utf-8')).get('entries') or []}
    plist = pages.split('>')
    if plist[0] != 'index.html':
        plist.insert(0, 'index.html')   # the wall is where every confusion row begins (the prover's path rule)
    args = {'id': gid, 'axis': ax, 'pages': plist, 'lang': lang, 'width': w, 'height': h, 'device': dev,
            'origin': 'http://localhost:5000/workhive', 'api': 'http://127.0.0.1:54321',
            'anonKey': io.open('.tmp/local_anon_key.txt', encoding='utf-8').read().strip(),
            'actions': [{'id': t['id'], 'kind': 'confusion', 'subject': t['w4']['confusion'],
                         'entry': {k: ledger.get(t['w4']['confusion'], {}).get(k) for k in ('page', 'host')}} for t in grp],
            'sigs': {}, 'safeRpcs': {}, 'hiveId': None, 'anon': False,
            'user': who['user'], 'pass': 'test1234', 'castName': who['name']}
    if write:
        io.open(os.path.join('.tmp', 'w4_args.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(args, ensure_ascii=False))
    print('%s prepped: %d row(s) as %s (worker, %s) on %s: %s' % (gid, len(grp), who['name'], hive, ax,
                                                                  ','.join(a['subject'] for a in args['actions'])))
    return args


def cmd_bank(gid, args=None):
    args = args or json.load(io.open(os.path.join('.tmp', 'w4_args.json'), encoding='utf-8'))
    if args.get('id') != gid:
        print('REFUSED: .tmp/w4_args.json is for %s, not %s' % (args.get('id'), gid)); raise SystemExit(2)
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
    wrote = []
    for a in args['actions']:
        rid = a['id']; ans = answers.get(rid) or {}
        note = (ans.get('note') or '') + ' (the prover\'s own predicate, evaluated in the MCP\'s browser; the cast read through postgres)'
        cmd = [sys.executable, 'tools/record_mcp_walk.py', '--id', rid, '--walked-at', wd._walked_at(gid),
               '--instrument', 'playwright-mcp + postgres-mcp', '--cast', recs.get('cast') or args.get('castName'),
               '--axis', args['axis'], '--steps', sp, '--note', note[:1500]]
        if not ans.get('ok'):
            cmd += ['--unproven', '; '.join(ans.get('problems') or ['not lived clean'])[:300]]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print('  %s %-5s %s' % (rid, 'OK' if ans.get('ok') else 'open', (ans.get('note') or '')[:180]))
        if r.returncode != 0:
            print('    record_mcp_walk FAILED: %s' % (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200])
            continue
        wrote.append(rid)
    wd.advance_many(gid, [(r, args['axis']) for r in wrote], kind='confusion')
    return all((answers.get(a['id']) or {}).get('ok') for a in args['actions'])


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    if sys.argv[1] == 'next':
        try:
            last = json.load(io.open(os.path.join('.tmp', 'w4_args.json'), encoding='utf-8')).get('id', '')
            rp = os.path.join('.tmp', 'w4_steps', '%s.records.json' % last)
            if last.startswith('FG') and os.path.exists(rp) and os.path.getmtime(rp) > os.path.getmtime(os.path.join('.tmp', 'w4_args.json')):
                cmd_bank(last)
        except Exception as e:
            print('bank of the last group failed:', e)
        gs = groups()
        skip = set(sys.argv[2:])
        nxt = [g for g in gs if g not in skip]
        print(len(gs), 'groups open')
        if nxt:
            cmd_prep(nxt[0], gs)
        raise SystemExit(0)
    {'--list': lambda: cmd_list(), 'prep': lambda: cmd_prep(sys.argv[2]), 'bank': lambda: cmd_bank(sys.argv[2])}.get(
        sys.argv[1], lambda: (print(__doc__), sys.exit(2)))()
