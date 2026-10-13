"""w4_cta_drive.py - drive the wave-4 "follow the tool this guide is about" rows (learn-cta) through the Playwright MCP.

The learn-cta rows were lived by tools/prove_w4_actions.mjs (the Playwright LIBRARY) and retracted with every
library-banked row on 2026-09-15 ("I thought we are using relevant live MCPs?"). tools/w4_action_walk.body.js now
carries the same semantics inside the MCP's own browser (2026-10-08), so these rows are re-earned per group:

  python tools/w4_cta_drive.py --list          every open group: gid, axis, guide path, rows, subjects
  python tools/w4_cta_drive.py prep <gid>      write .tmp/w4_args.json for that group (anonymous reader)
  (walk:  browser_run_code_unsafe { filename: tools/w4_action_walk.js })
  python tools/w4_cta_drive.py bank <gid>      record each row's receipt and advance what now passes
"""
import io, json, os, subprocess, sys, time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, 'tools')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import w4_write_drive as wd



def _walked_at(gid):
    """the local ISO time the group's walk ran - its records file - for record_mcp_walk.py --walked-at (2026-10-12)"""
    import datetime as _dt
    p = os.path.join('.tmp', 'w4_steps', '%s.records.json' % gid)
    return _dt.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec='seconds') if os.path.exists(p) else ''

def open_rows():
    import live_walk_manifest as m
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    opn = {r['id'] for r in rows if not m.row_closed(r)}
    return [t for t in reg if t['id'] in opn and ((t.get('w4') or {}).get('action') or {}).get('kind') == 'learn-cta']


def groups():
    g = {}
    for t in open_rows():
        key = ('>'.join(t.get('pages') or []), wd.axis(t))
        g.setdefault(key, []).append(t)
    return {('CG' + v[0]['id']): (k, v) for k, v in sorted(g.items(), key=lambda kv: (kv[0][1], kv[1][0]['id']))}


def cmd_list():
    gs = groups(); n = 0
    for gid, (k, v) in gs.items():
        n += len(v)
        print(gid, k[1], '|', k[0], '|', len(v), 'rows:', ','.join(t['w4']['action']['subject'] for t in v))
    print(len(gs), 'groups,', n, 'rows')


def cmd_prep(gid, gs=None, write=True):
    gs = gs or groups()
    if gid not in gs:
        print('no such open group', gid); raise SystemExit(2)
    (pages, ax), grp = gs[gid]
    dev, lang = ax.split(' ')
    w, h = (320, 720) if dev == 'narrow-320' else (390, 844)
    args = {'id': gid, 'axis': ax, 'pages': pages.split('>'), 'lang': lang, 'width': w, 'height': h,
            'origin': 'http://localhost:5000/workhive', 'api': 'http://127.0.0.1:54321',
            'anonKey': io.open('.tmp/local_anon_key.txt', encoding='utf-8').read().strip(),
            'actions': [{'id': t['id'], 'kind': 'learn-cta', 'subject': t['w4']['action']['subject']} for t in grp],
            'sigs': {}, 'safeRpcs': {}, 'hiveId': None, 'anon': True}
    if write:
        io.open(os.path.join('.tmp', 'w4_args.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(args, ensure_ascii=False))
    print('%s prepped: %d row(s), anonymous reader, %s, from %s' % (gid, len(grp), ax, pages.split('>')[0]))
    return args


def cmd_bank(gid, args=None, defer=None):
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
        cmd = [sys.executable, 'tools/record_mcp_walk.py', '--id', rid, '--walked-at', _walked_at(gid), '--instrument', 'playwright-mcp + postgres-mcp',
               '--cast', recs.get('cast') or 'anonymous reader', '--axis', args['axis'], '--steps', sp,
               '--note', (ans.get('note') or '')[:1200]]
        if not ans.get('ok'):
            cmd += ['--unproven', '; '.join(ans.get('problems') or ['not lived clean'])[:300]]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print('  %s %-5s %s' % (rid, 'OK' if ans.get('ok') else 'open', (ans.get('note') or '')[:170]))
        if r.returncode != 0:
            print('    record_mcp_walk FAILED: %s' % (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200])
            continue
        wrote.append(rid)
    if defer is not None:
        defer.extend((r, args['axis']) for r in wrote)   # the batch advances every group in ONE ledger pass
    else:
        wd.advance(gid, wrote, args['axis'])
    return all((answers.get(a['id']) or {}).get('ok') for a in args['actions'])


BATCH = os.path.join('.tmp', 'w4_args_batch.json')
SKIP = os.path.join('.tmp', 'w4_cta_skip.json')


def cmd_batch(n):
    """bank every group of the last batch that was walked since it was written, then write the next n groups"""
    skip = json.load(io.open(SKIP, encoding='utf-8')) if os.path.exists(SKIP) else {}
    pending = []
    if os.path.exists(BATCH):
        t0 = os.path.getmtime(BATCH)
        for args in json.load(io.open(BATCH, encoding='utf-8')):
            rp = os.path.join('.tmp', 'w4_steps', '%s.records.json' % args['id'])
            if os.path.exists(rp) and os.path.getmtime(rp) > t0:
                try:
                    if not cmd_bank(args['id'], args, defer=pending):
                        skip[args['id']] = time.strftime('%Y-%m-%d %H:%M') + ' stayed open'
                except Exception as e:
                    print('bank of %s failed: %s' % (args['id'], e)); skip[args['id']] = 'bank failed: %s' % e
            else:
                print('%s was not walked since the batch was written' % args['id'])
        io.open(SKIP, 'w', encoding='utf-8', newline='\n').write(json.dumps(skip, indent=1))
        if pending:
            wd.advance_many('CTA-batch', pending)
    gs = groups()
    nxt = [g for g in gs if g not in skip][:n]
    print(len(gs), 'groups open,', len(skip), 'skipped as stayed-open:', ', '.join(sorted(skip))[:300])
    batch = [cmd_prep(g, gs, write=False) for g in nxt]
    io.open(BATCH, 'w', encoding='utf-8', newline='\n').write(json.dumps(batch, ensure_ascii=False))
    print('batch of', len(batch), 'written')


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    if sys.argv[1] == 'batch':
        cmd_batch(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
        raise SystemExit(0)
    if sys.argv[1] == 'next':   # bank the group just walked (if any), then prep the first still-open group
        try:
            last = json.load(io.open(os.path.join('.tmp', 'w4_args.json'), encoding='utf-8')).get('id', '')
            if last.startswith('CG') and os.path.exists(os.path.join('.tmp', 'w4_steps', '%s.records.json' % last)) and                     os.path.getmtime(os.path.join('.tmp', 'w4_steps', '%s.records.json' % last)) > os.path.getmtime(os.path.join('.tmp', 'w4_args.json')):
                cmd_bank(last)
        except Exception as e:
            print('bank of the last group failed:', e)
        gs = groups()
        skip = set(sys.argv[2:])
        nxt = [g for g in gs if g not in skip]
        print(len(gs), 'groups open')
        if nxt:
            cmd_prep(nxt[0])
        raise SystemExit(0)
    {'--list': lambda: cmd_list(), 'prep': lambda: cmd_prep(sys.argv[2]), 'bank': lambda: cmd_bank(sys.argv[2])}.get(
        sys.argv[1], lambda: (print(__doc__), sys.exit(2)))()
