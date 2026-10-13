"""w4_kind_drive.py - drive one wave-4 ACTION kind through the Playwright MCP, batch by batch (2026-10-08).

Generalises tools/w4_cta_drive.py / tools/w4_layer_ca_drive.py for the remaining action kinds the MCP walker
(tools/w4_action_walk.body.js) now lives: `compute` (a calculator guide -> its calculator -> run -> print). Rows that share
a path and a cast are walked once; every row is banked from its own receipt through tools/record_mcp_walk.py, and
advanced in ONE ledger pass per batch.

  python tools/w4_kind_drive.py compute --list
  python tools/w4_kind_drive.py compute batch [N]
  python tools/w4_kind_drive.py compute sweep      purge every throwaway account a compute walk was handed
  (walk:  python tools/browser_lock.py acquire main -> browser_run_code_unsafe { filename: tools/w4_action_batch.js }
          -> python tools/browser_lock.py release main)
"""
import io, json, os, re, subprocess, sys, tempfile, time, secrets

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, 'tools')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import w4_layer_ca_drive as lcd   # bank_group / advance_many / axis (kind-aware gate, one ledger pass)

BATCH = os.path.join('.tmp', 'w4_args_batch.json')
PREFIX = {'compute': 'KC'}
ACCOUNTS = os.path.join('.tmp', 'w4_compute_accounts.json')   # every throwaway account ever handed to a walk


# ★A STRANGER'S CALCULATOR IS BEHIND A FREE ACCOUNT (2026-10-08). The compute rows are anonymous people arriving from a
# search result; engineering-design.html sends a signed-out visitor to the sign-in wall, so the walk takes the wall's own
# Sign Up door under a throwaway name. The account is born on the walk and must leave nothing behind: every handed-out
# name is written to ACCOUNTS BEFORE the walk, purged after it (every public row keyed to its uid / username / name /
# e-mail, then the auth user, whose own sessions and identities cascade), and the purge is PROVEN before a row banks.
# An orphan (a walk that died mid-path) is swept by the next call. Names are 'w4kc' + hex - no seeded person carries one.

def _walked_at(gid):
    """the local ISO time the group's walk ran - its records file - for record_mcp_walk.py --walked-at (2026-10-12)"""
    import datetime as _dt
    p = os.path.join('.tmp', 'w4_steps', '%s.records.json' % gid)
    return _dt.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec='seconds') if os.path.exists(p) else ''

def new_account():
    mark = 'W4KC' + secrets.token_hex(3).upper()
    return {'user': mark.lower(), 'name': mark + ' Newcomer', 'pass': 'test1234'}


def _psql(sql):
    r = subprocess.run(['docker', 'exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1',
                        '-tA', '-F', '\t'], input=sql, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()


_KEYED = """select c.table_name, c.column_name, c.data_type from information_schema.columns c
  join information_schema.tables t on t.table_schema = c.table_schema and t.table_name = c.table_name and t.table_type = 'BASE TABLE'
  where c.table_schema = 'public' and ((c.data_type = 'uuid' and c.column_name ~ '(^|_)(auth_uid|uid|user_id)$')
     or (c.data_type in ('text', 'character varying') and c.column_name in ('worker_name', 'display_name', 'username', 'author_name',
         'email', 'created_by', 'submitted_by', 'client_worker_name', 'actor', 'actor_name')))"""


def purge_account(acct):
    """delete every trace of one throwaway account; return (clean, report)"""
    u = acct['user']
    if not re.fullmatch(r'w4kc[0-9a-f]{6}', u):
        return False, 'REFUSED: %r is not a throwaway compute account' % u
    email = '%s@auth.workhiveph.com' % u
    rc, uid, e = _psql("select id from auth.users where email = '%s';" % email)
    if rc != 0:
        return False, 'could not read the account: ' + e[-200:]
    uid = uid.strip()
    if uid and not re.fullmatch(r'[0-9a-f-]{36}', uid):
        return False, 'unexpected uid %r' % uid[:60]
    uidv = ("'%s'::uuid" % uid) if uid else 'null::uuid'
    keys = "array['%s', '%s', '%s']" % (acct['name'].replace("'", "''"), u, email)
    body = """for r in %(keyed)s loop
    if r.data_type = 'uuid' then
      if %(uid)s is null then continue; end if;
      execute format('%(verb)s from public.%%I where %%I = $1', r.table_name, r.column_name) %(into)s using %(uid)s;
    else
      execute format('%(verb)s from public.%%I where %%I = any($1)', r.table_name, r.column_name) %(into)s using %(keys)s;
    end if;
    %(after)s
  end loop;"""
    purge = body % {'keyed': _KEYED, 'uid': uidv, 'keys': keys, 'verb': 'delete', 'into': '',
                    'after': "get diagnostics n = row_count; if n > 0 then raise notice 'purged %.% x%', r.table_name, r.column_name, n; end if;"}
    check = body % {'keyed': _KEYED, 'uid': uidv, 'keys': keys, 'verb': 'select count(*)', 'into': 'into n',
                    'after': "if n > 0 then raise notice 'LEFT %.% x%', r.table_name, r.column_name, n; v_left := v_left + n; end if;"}
    # the public rows go under replica (no trigger writes a fresh audit/XP row while undoing); the auth user goes in a
    # NORMAL transaction, because replica also disables the foreign-key cascades that remove its sessions and identities
    # MEASURED (2026-10-08, signup_discovery on the first walk's account): a sign-up through the wall writes
    # auth.users/identities/sessions/refresh_tokens (one user row; the rest cascade from it), public.worker_profiles,
    # public.analytics_events (auth_uid + worker_name) - and auth.audit_log_entries, which name the user only inside
    # their JSON payload, so no foreign key removes them: they are deleted by the uid / e-mail they carry.
    aud = ("delete from auth.audit_log_entries where payload::text like '%%%s%%'" % email
           + (" or payload::text like '%%%s%%'" % uid if uid else '') + ";")
    aud_left = ("(select count(*) from auth.audit_log_entries where payload::text like '%%%s%%'" % email
                + (" or payload::text like '%%%s%%'" % uid if uid else '') + ")")
    sql = ("begin; set local session_replication_role = replica;\n"
           "do $p$ declare r record; n bigint; begin " + purge + " end $p$; commit;\n"
           "begin; " + aud + " delete from auth.users where email = '" + email + "'; commit;\n"
           "do $c$ declare v_left bigint := (select count(*) from auth.users where email = '" + email + "') + " + aud_left
           + (" + (select count(*) from auth.identities where user_id = " + uidv + ")"
              " + (select count(*) from auth.sessions where user_id = " + uidv + ")" if uid else '')
           + "; r record; n bigint; begin "
           + check + " raise notice 'leftover %', v_left; end $c$;")
    rc, o, e = _psql(sql)
    notes = [l.split('NOTICE:', 1)[1].strip() for l in e.splitlines() if 'NOTICE:' in l]
    left = next((n for n in notes if n.startswith('leftover ')), 'leftover ?')
    clean = rc == 0 and left == 'leftover 0'
    rest = '; '.join(n for n in notes if not n.startswith('leftover '))
    return clean, (rest or ('no account existed' if not uid else '')) + ('' if clean else ' | ' + left + (' | ' + e[-300:] if rc else ''))


def _load_accounts():
    return json.load(io.open(ACCOUNTS, encoding='utf-8')) if os.path.exists(ACCOUNTS) else {}


def _save_accounts(d):
    io.open(ACCOUNTS, 'w', encoding='utf-8', newline='\n').write(json.dumps(d, indent=1))


def sweep_accounts():
    """purge every recorded throwaway account; keep the ones that are not proven gone"""
    d = _load_accounts()
    for user, acct in list(d.items()):
        clean, rep_ = purge_account(acct)
        print('  purge %s: %s%s' % (user, 'clean' if clean else 'NOT CLEAN', (' - ' + rep_) if rep_ else ''))
        if clean:
            d.pop(user)
    _save_accounts(d)
    return d


def eligible(kind, t):
    a = ((t.get('w4') or {}).get('action') or {})
    if a.get('kind') != kind:
        return False
    if kind == 'compute':
        return str((t.get('pages') or [''])[0]).startswith('tools/')   # a calculator guide; the analytics rows differ
    return True


def groups(kind):
    import live_walk_manifest as m
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    opn = {r['id'] for r in rows if not m.row_closed(r)}
    g = {}
    for t in reg:
        if t['id'] in opn and eligible(kind, t):
            # ★THE ROW'S PERSONA IS PART OF THE GROUP (2026-10-09). The key was (path, hive, axis), and args_for took the
            # hive's worker when it had one - so "fleet-supervisor ... print or export this page - hive" walked as Ben
            # Ocampo, a WORKER there, and the supervisor-only export was rightly hidden from him. The cast now follows the
            # persona's role; a persona the hive cannot cast (buyer, new-user, machine-client) is not walked as someone else.
            who = 'anon' if t.get('persona') == 'anon' else '%s|%s' % ((t.get('journey') or {}).get('vertical') or '', role_of(t))
            g.setdefault(('>'.join(t.get('pages') or []), who, lcd.axis(t)), []).append(t)
    pre = PREFIX.get(kind, 'KX')
    return {(pre + v[0]['id']): (k, v) for k, v in sorted(g.items(), key=lambda kv: (kv[0][2], kv[1][0]['id']))}


def role_of(t):
    """the cast role a row's persona walks as: the hive's supervisor (owner) or its worker; anything else is itself"""
    p = t.get('persona') or ''
    if p in ('supervisor', 'fleet-supervisor', 'solo-owner'):
        return 'supervisor'
    if p in ('worker', 'driver-worker', 'assistive-tech', 'returner', 'any'):
        return 'worker'
    return p


def subject_page_of(t, pages):
    """The page a print/cta row's title names ("... - asset hub · narrow-320 en" -> asset-hub.html), when it is on the
    path. 2026-10-09: the walker pressed print on the path's LAST page, so "print or export this page - asset hub"
    looked for a control on logbook.html and "- hive" on audit-log.html. None keeps the walker's last-page fallback."""
    m = re.search(r' - ([^·]+?) · ', t.get('title') or '')
    if not m:
        return None
    slug = re.sub(r'\s+', '-', m.group(1).strip().lower())
    for want in (slug + '.html', slug + '/index.html'):   # "about" -> about/index.html, "learn" -> learn/index.html
        if want in pages:
            return want
    return None


def args_for(kind, gid, key, grp):
    pages, who, ax = key
    pg = json.load(io.open('.tmp/w4_action_pg.json', encoding='utf-8'))
    dev, lang = ax.split(' ')
    w, h = (320, 720) if dev == 'narrow-320' else (390, 844)
    plist = pages.split('>')
    a = {'id': gid, 'axis': ax, 'pages': plist, 'lang': lang, 'width': w, 'height': h,
         'origin': 'http://localhost:5000/workhive', 'api': 'http://127.0.0.1:54321',
         'anonKey': io.open('.tmp/local_anon_key.txt', encoding='utf-8').read().strip(),
         'actions': [dict({'id': t['id'], 'kind': kind, 'subject': t['w4']['action'].get('subject')},
                          **({'subjectPage': subject_page_of(t, plist)} if kind in ('print', 'cta') and subject_page_of(t, plist) else {}))
                     for t in grp],
         'sigs': {}, 'safeRpcs': {}, 'hiveId': None, 'anon': who == 'anon'}
    if who != 'anon':
        hive, _, role = who.partition('|')
        c = pg['cast'].get(hive) or {}
        person = c.get(role) if role in ('worker', 'supervisor') else None   # no stand-in for a persona it cannot cast
        # ★A MACHINE CLIENT HAS NO BROWSER (2026-10-12, W4592/W4593). The rows of the page that manages machine clients
        # (plant-connections, "Supervisor only") were seeded with the machine-client persona, which no person can play -
        # so they were never castable here. Their controls are pressed by the machine clients' OPERATOR, the hive's
        # supervisor; the receipt says so. The only persona mapped this way: a person persona still gets no stand-in.
        if person is None and role == 'machine-client':
            person = c.get('supervisor')
            if person:
                a['castNote'] = ('[a machine client has no browser: walked by its operator, %s, the hive\'s supervisor]'
                                 % person['name'])
        if not person or person['user'] == 'ianphone':
            return None
        a.update({'user': person['user'], 'pass': 'test1234', 'castName': person['name'], 'hiveId': c.get('hive_id')})
    if kind == 'compute' and who == 'anon':
        a['computeSignup'] = new_account()
    return a


# ★AN EDGE ROW'S EFFECT WAS NEVER PASSED ON (2026-10-12). The ledger holds every edge action to "the effect to its
# terminus" (live_walk_manifest._w4_missing: no persisted-effect receipt -> open), the walker measured that effect
# (the function, its status, the page it landed on, the provenance the person saw), and bank_group dropped it - so
# not one of the 138 edge rows had ever banked. The effect is now recorded, and where the function WRITES a row a
# person reads back, postgres names that row. Each query is the function's own write, read from its source:
# analytics-orchestrator upserts analytics_snapshots; shift-planner-orchestrator upserts shift_plans.
EDGE_PERSISTS = {
    'analytics-orchestrator': ("analytics_snapshots", "select to_char(max(computed_at) at time zone 'Asia/Manila', 'YYYY-MM-DD HH24:MI') "
                               "from public.analytics_snapshots where hive_id = '{HIVE}'"),
    'shift-planner-orchestrator': ("shift_plans", "select to_char(max(generated_at) at time zone 'Asia/Manila', 'YYYY-MM-DD HH24:MI') "
                                   "from public.shift_plans where hive_id = '{HIVE}'"),
}


def edge_effect(eff, hive_id):
    fn = eff.get('fn') or '?'
    txt = '%s answered %s on %s; the person saw it land with provenance "%s"' % (
        fn, eff.get('status'), eff.get('page'), (eff.get('provenance') or '')[:90])
    spec = EDGE_PERSISTS.get(fn)
    if spec and hive_id and re.fullmatch(r'[0-9a-f-]{36}', str(hive_id)):
        r = subprocess.run(['docker', 'exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-tA', '-c',
                            spec[1].replace('{HIVE}', str(hive_id))], capture_output=True, text=True, encoding='utf-8', errors='replace')
        when = (r.stdout or '').strip()
        if when:
            txt += '; postgres: the newest %s row for this hive is %s PHT' % (spec[0], when)
    return txt


def bank_group(args, pending):
    """lcd.bank_group passes --layer CA; an action row must not claim a layer, so record here"""
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
               # castNote (2026-10-12): who pressed it when the row's persona is not a person (a machine client's operator)
               '--steps', sp, '--note', ((args['castNote'] + ' ') if args.get('castNote') else '') + (ans.get('note') or '')[:1200]]
        if not ans.get('ok'):
            all_ok = False
            cmd += ['--unproven', '; '.join(ans.get('problems') or ['not lived clean'])[:300]]
        elif a.get('kind') == 'edge' and ans.get('effect'):
            cmd += ['--effect', edge_effect(ans['effect'], args.get('hiveId'))[:400]]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if not ans.get('ok'):
            print('  %s open: %s' % (rid, '; '.join(ans.get('problems') or [])[:300]))
        if r.returncode != 0:
            print('    record_mcp_walk FAILED: %s' % (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200])
            continue
        pending.append((rid, args['axis']))
    return all_ok


def advance_many(label, items):
    """lcd.advance_many gates on ('layer', axis); an action row is gated on ('action', axis)"""
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
            entries.append({'ids': rid, 'status': 'locking', 'pct': 60, 'gate': [bwp.GATES.get(('action', ax))],
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


def cmd_batch(kind, n):
    skipf = os.path.join('.tmp', 'w4_%s_skip.json' % kind)
    skip = json.load(io.open(skipf, encoding='utf-8')) if os.path.exists(skipf) else {}
    pre = PREFIX.get(kind, 'KX')
    pending = []
    if os.path.exists(BATCH):
        t0 = os.path.getmtime(BATCH)
        for args in json.load(io.open(BATCH, encoding='utf-8')):
            if not str(args.get('id', '')).startswith(pre):
                continue
            rp = os.path.join('.tmp', 'w4_steps', '%s.records.json' % args['id'])
            acct = args.get('computeSignup')
            if acct:
                clean, rep_ = purge_account(acct)
                print('  %s account %s: %s%s' % (args['id'], acct['user'], 'purged clean' if clean else 'NOT CLEAN', (' - ' + rep_) if rep_ else ''))
                if clean:
                    d = _load_accounts(); d.pop(acct['user'], None); _save_accounts(d)
                else:
                    print('  %s NOT banked: its throwaway account left data behind' % args['id'])
                    continue
            if os.path.exists(rp) and os.path.getmtime(rp) > t0:
                if not bank_group(args, pending):
                    skip[args['id']] = time.strftime('%Y-%m-%d %H:%M') + ' stayed open'
            else:
                print('%s was not walked since the batch was written' % args['id'])
        io.open(skipf, 'w', encoding='utf-8', newline='\n').write(json.dumps(skip, indent=1))
        if pending:
            advance_many('%s-batch' % kind, pending)
    if kind == 'compute' and _load_accounts():
        sweep_accounts()
    gs = groups(kind)
    batch = []
    for gid, (key, grp) in gs.items():
        if gid in skip:
            continue
        a = args_for(kind, gid, key, grp)
        if a:
            batch.append(a)
        if len(batch) >= n:
            break
    accts = _load_accounts()
    for a in batch:
        if a.get('computeSignup'):
            accts[a['computeSignup']['user']] = a['computeSignup']
    _save_accounts(accts)
    io.open(BATCH, 'w', encoding='utf-8', newline='\n').write(json.dumps(batch, ensure_ascii=False))
    print('%s: %d groups open (%d rows), %d skipped as stayed-open; batch of %d written' % (
        kind, len(gs), sum(len(v) for _, v in gs.values()), len(skip), len(batch)))


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    kind = sys.argv[1]
    if sys.argv[2] == '--list':
        for gid, (k, v) in groups(kind).items():
            print(gid, k[2], '|', k[1], '|', k[0], '|', len(v), 'rows')
    elif sys.argv[2] == 'batch':
        cmd_batch(kind, int(sys.argv[3]) if len(sys.argv) > 3 else 6)
    elif sys.argv[2] == 'sweep':
        print('left:', list(sweep_accounts()))
    else:
        print(__doc__); raise SystemExit(2)
