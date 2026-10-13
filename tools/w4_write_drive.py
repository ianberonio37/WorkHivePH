"""w4_write_drive.py - drive the wave-4 WRITE rows through the Playwright MCP, one group at a time (2026-10-08).

The W4 "write" rows (subject <table>.<op>) and the W4 "rpc" rows whose function MUTATES could not be lived by any
walker: a walk never writes through PostgREST or calls a mutating rpc itself (CLAUDE.md; memory
feedback_a_generic_caller_must_classify_before_it_calls). Each is lived instead by the PERSON'S OWN CONTROL, from a
recipe in tools/w4_write_recipes.json (gated by tools/validate_w4_write_recipes.py). tools/w4_action_walk.js runs
the recipe on the page that owns the write and records the request the press produced; this driver does the
postgres half around it:

  python tools/w4_write_drive.py --list              every open group: gid, axis, cast, pages, rows, recipe coverage
  python tools/w4_write_drive.py prep <gid> [--actor|--anon] [--only s1,s2] [--skip s1,s2]
                                                     seed, snapshot (before_sql), write .tmp/w4_args.json, note SINCE
                                                     (--anon: the signed-out rows, role 'anon'; --only/--skip: split a
                                                     group into several walks by subject)
  python tools/w4_write_drive.py install <gid>       re-install that group's args as .tmp/w4_args.json (under the lock)
  python tools/w4_write_drive.py settle <gid>        the postgres half only (read effects, reverse, prove), in seconds -
                                                     run it BEFORE releasing the lock when a walk locked out a shared
                                                     cast (deactivate_my_account); bank then reuses its result
  (walk:  browser_run_code_unsafe { filename: tools/w4_action_walk.js })
  python tools/w4_write_drive.py bank <gid>          read each row's persisted effect, REVERSE it, prove the reversal,
                                                     record the receipt with --effect, advance what now passes

Recipe features honoured (the catalog's _contract): `alternatives` (the first recipe whose page is on the row's path),
`actor` (an admin-only write: walked only with --actor, signed in as that account), `before_sql` (a snapshot the
reversal restores from: a row whose snapshot fails is NOT walked), `no_write` (an rpc that is VOLATILE by declaration
but writes nothing: lived by its request alone, no effect to reverse), `seed_sql` / `seed_cleanup_sql`.

The effect is found by this run's {MARK} (free text the recipe typed) or by the cast's hive/user and {SINCE}; the
reversal is the recipe's reverse_sql, and a row whose effect cannot be found or cannot be reversed stays OPEN.
Nothing here writes to the `ianphone` account: every cast is a seeded local persona from .tmp/w4_action_pg.json.
"""
import io, json, os, re, subprocess, sys, tempfile, time, secrets

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, 'tools')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

STATE = os.path.join('.tmp', 'w4_write_state.json')



def _walked_at(gid):
    """the local ISO time the group's walk ran - its records file - for record_mcp_walk.py --walked-at (2026-10-12)"""
    import datetime as _dt
    p = os.path.join('.tmp', 'w4_steps', '%s.records.json' % gid)
    return _dt.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec='seconds') if os.path.exists(p) else ''

def state_path(gid: str) -> str:
    """the per-group copy of the write state, so a later prep cannot orphan an earlier walk's reversal"""
    return os.path.join('.tmp', 'w4_write_state_%s.json' % gid)
RECIPES = os.environ.get('W4_WRITE_RECIPES') or os.path.join('tools', 'w4_write_recipes.json')   # override: a pilot file
NEVER_USERS = {'ianphone'}


def psql(sql: str) -> tuple:
    r = subprocess.run(['docker', 'exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1',
                        '-tA', '-F', '\t'], input=sql, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()


def fill(sql: str, ctx: dict) -> str:
    out = str(sql or '')
    for k, v in ctx.items():
        out = out.replace('{' + k + '}', str(v))
    return out


def load_recipes() -> dict:
    if not os.path.exists(RECIPES):
        return {}
    j = json.load(io.open(RECIPES, encoding='utf-8'))
    return j.get('recipes', j) if isinstance(j, dict) else {}


_SURFACES = None


def _surface_of(rid):
    """the surface a row's title names: 'Lived start to end: ... - marketplace · narrow-320 en' -> 'marketplace'"""
    global _SURFACES
    if _SURFACES is None:
        _SURFACES = {}
        for t in json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']:
            title = str(t.get('title') or '')
            if ' - ' in title:
                _SURFACES[t['id']] = re.split(r'\s+[\u00b7?]\s+', title.rsplit(' - ', 1)[1])[0].strip().lower()
    return _SURFACES.get(rid, '')


def pick_recipe(rec: dict, pages: list, rid=None) -> dict:
    """the recipe on the row's OWN surface (named in its title) when one exists; else the main recipe when its page is
    on the row's path, else the first alternative whose page is (2026-10-12, W4578: the path rule alone gave a
    marketplace row the hive coach, because nearly every path passes hive.html)"""
    if not rec:
        return {}
    alts = rec.get('alternatives') or []

    def merged(alt):
        # ★AN ALTERNATIVE INHERITED WHAT WAS NOT ITS OWN (2026-10-12, WGW4803). ai-gateway's alternatives took the main
        # recipe's seed (an asset node) without its cleanup - ten seeded assets leaked - and the journal alternative
        # took the main's `no_write`, so its saved note was never read or reversed. Write semantics and the expectation
        # are always the alternative's own (the gate checks each one as a full recipe), and a seed and its cleanup are a
        # PAIR: an alternative that defines either owns both. Other keys (role, before_sql, aliases ...) still inherit.
        base = {k: v for k, v in rec.items() if k != 'alternatives'}
        for k in ('no_write', 'effect_sql', 'reverse_sql', 'reverse_check_sql', 'expect'):
            base.pop(k, None)
        if 'seed_sql' in alt or 'seed_cleanup_sql' in alt:
            base.pop('seed_sql', None)
            base.pop('seed_cleanup_sql', None)
        base.update(alt)
        return base
    surface = _surface_of(rid) if rid else ''
    if surface and alts:
        stem = lambda pg: str(pg or '').rsplit('.', 1)[0].replace('-', ' ').lower()
        if stem(rec.get('page')) == surface and rec.get('page') in pages:
            return rec
        for alt in alts:
            if stem(alt.get('page')) == surface and alt.get('page') in pages:
                return merged(alt)
    if rec.get('page') in pages or not alts:
        return rec
    for alt in alts:
        if alt.get('page') in pages:
            return merged(alt)
    return rec


def open_rows():
    import live_walk_manifest as m
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    opn = {r['id'] for r in rows if not m.row_closed(r)}
    pg = json.load(io.open('.tmp/w4_action_pg.json', encoding='utf-8'))
    R_STEPS = {k: bool((v or {}).get('steps')) for k, v in load_recipes().items() if isinstance(v, dict)}
    out = []
    for t in reg:
        if t['id'] not in opn:
            continue
        a = ((t.get('w4') or {}).get('action') or {})
        if a.get('kind') == 'write':
            out.append(t)
        elif a.get('kind') == 'rpc' and not (pg.get('safe') or {}).get(a.get('subject')):
            out.append(t)   # a mutating rpc: lived by the control that calls it
        elif a.get('kind') == 'rpc' and (R_STEPS.get(a.get('subject')) if R_STEPS is not None else False):
            # ★A READ RPC POSTGRES CALLS VOLATILE IS LIVED BY ITS CONTROL TOO (2026-10-12). The kind walk calls a read
            # rpc itself only when pg_proc declares it STABLE/IMMUTABLE - the safe fence - so get_hive_readiness_current,
            # generate_change_order_number, generate_project_code and get_project_budget (read-only bodies, declared
            # VOLATILE) stayed open on every kind walk ("the page's own control must trigger it"), while this driver
            # skipped them as safe. A read rpc whose recipe names the control is walked here, by that control.
            out.append(t)
        elif a.get('kind') == 'upload' and R_STEPS.get(a.get('subject')):
            # ★AN UPLOAD OF A REAL FILE IS LIVED BY THE CONTROL THAT TAKES IT (2026-10-12): the row names a fixture kind;
            # its recipe hands the real file to the page's own input and reads where it landed, like any write.
            out.append(t)
        elif a.get('kind') == 'edge':
            # ★AN EDGE ACTION IS LIVED BY THE CONTROL THAT INVOKES IT (2026-10-12). "Invoke <function> and see the
            # answer land" - and most functions run only when a person presses something (Ask, Export, Polish, Run),
            # which the passive kind walk never does. Its recipe is keyed by the function name, its `expect` is the
            # function's own POST, and a function that writes server-side carries the effect/reverse SQL of any recipe.
            out.append(t)
    return out


def _local_service_key():
    """the LOCAL service-role key, read from the running edge runtime at call time - never stored, never printed
    (tools/drain_embedding_outbox.py's move)."""
    try:
        r = subprocess.run(['docker', 'exec', 'supabase_edge_runtime_workhive', 'printenv', 'SUPABASE_SERVICE_ROLE_KEY'],
                           capture_output=True, text=True, timeout=30)
        return (r.stdout or '').strip()
    except Exception:
        return ''


def _storage_remove(api, bucket, names):
    """remove objects through the Storage API (2026-10-12, listing photos): SQL cannot - storage.objects is guarded by
    protect_delete, and a replica-role delete would drop the row and leave the bytes. LOCAL API only."""
    import urllib.request
    if not re.match(r'^https?://(127\.0\.0\.1|localhost)(:\d+)?/?$', api or ''):
        return 1, 'refused: %r is not the local API' % api
    key = _local_service_key()
    if not key:
        return 1, 'no local service key (is supabase_edge_runtime_workhive running?)'
    req = urllib.request.Request(api.rstrip('/') + '/storage/v1/object/' + bucket, method='DELETE',
                                 data=json.dumps({'prefixes': names}).encode(),
                                 headers={'Authorization': 'Bearer ' + key, 'apikey': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return 0, '%d removed' % len(json.loads(r.read().decode() or '[]'))
    except Exception as e:
        return 1, str(e)[:160]


def _fixture_provenance(rec):
    """the real file an upload recipe handed to the page, from its kind's manifest: the file, its sha256, where it was
    fetched from and under what licence (2026-10-12). '' when the recipe uploads no fixture."""
    for st in (rec or {}).get('steps') or []:
        fx = st.get('fixture') if isinstance(st, dict) else None
        if not fx:
            continue
        kind, name = str(fx).split('/', 1)
        try:
            man = json.load(io.open(os.path.join('_fixtures', kind, 'manifest.json'), encoding='utf-8'))
        except (OSError, ValueError):
            return ''
        for f in man.get('files') or []:
            if f.get('file') == name:
                return '_fixtures/%s (%s bytes, sha256 %s) from %s - %s, fetched %s' % (
                    fx, f.get('bytes'), (f.get('sha256') or '')[:16], f.get('source_url'), f.get('license'), f.get('fetched'))
    return ''


def axis(t):
    return '%s %s' % (t['axis']['device'], t['axis']['language'])


# ★A READ RPC ON THE SAME PATH RIDES THE WRITE WALK (2026-10-08). Five rpcs the recipe author classified as writing
# turned out to write nothing (generate_change_order_number, generate_project_code, get_hive_readiness_current,
# get_pm_compliance_smrp, redeem_service_voucher) and moved to the safe map, so they became READ-rpc rows. Each one
# lives on the very path and cast of an open write group, and the write walk already seats the cast in the right
# hive (the read driver does not: a member of two hives would call it against the wrong one). So `prep --with-read`
# adds the group's open safe-rpc rows as kind 'rpc' actions; the walker answers them exactly as the read driver does
# (the page's own call on the path, else the person's own session calling it, never a mutating one), and `bank`
# records them without an effect - an rpc row's evidence is the call and its answer.
READ_RPC_CONTEXT = {'p_type': 'shutdown', 'p_year': int(time.strftime('%Y')), 'p_code': 'W4VOUCHER'}
# only the five reclassified ones: every other open read-rpc row belongs to the read driver's own walks, and a receipt
# written here would supersede (and could re-open) one written there
READ_RPC_SUBJECTS = {'generate_change_order_number', 'generate_project_code', 'get_hive_readiness_current',
                     'get_pm_compliance_smrp', 'redeem_service_voucher'}


def read_rpc_rows(key):
    import live_walk_manifest as m
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    opn = {r['id'] for r in rows if not m.row_closed(r)}
    pg = json.load(io.open('.tmp/w4_action_pg.json', encoding='utf-8'))
    out = []
    for t in reg:
        a = ((t.get('w4') or {}).get('action') or {})
        if t['id'] not in opn or a.get('kind') != 'rpc' or not (pg.get('safe') or {}).get(a.get('subject')) \
                or a.get('subject') not in READ_RPC_SUBJECTS:
            continue
        who = 'anon' if t.get('persona') == 'anon' else ((t.get('journey') or {}).get('vertical') or '')
        if ('>'.join(t.get('pages') or []), who, axis(t)) == key:
            out.append(t)
    return out


def groups():
    g = {}
    for t in open_rows():
        who = 'anon' if t.get('persona') == 'anon' else ((t.get('journey') or {}).get('vertical') or '')
        key = ('>'.join(t.get('pages') or []), who, axis(t))
        g.setdefault(key, []).append(t)
    return {('WG' + v[0]['id']): (k, v) for k, v in sorted(g.items(), key=lambda kv: (kv[0][2], kv[1][0]['id']))}


def cmd_list():
    R = load_recipes()
    gs = groups(); n = 0; have = 0
    for gid, (k, v) in gs.items():
        subs = [t['w4']['action']['subject'] for t in v]
        ok = [s for s in subs if (R.get(s) or {}).get('steps')]
        n += len(v); have += len(ok)
        print(gid, k[2], '|', k[1], '|', k[0], '|', len(v), 'rows,', len(ok), 'with a recipe:', ','.join(subs))
    print(len(gs), 'groups,', n, 'rows,', have, 'with a recipe')


def walk_mode(rec: dict) -> str:
    """which walk a recipe belongs to: 'actor' (a named non-cast admin), 'anon' (signed out), or the cast's own walk"""
    if rec.get('actor'):
        return 'actor'
    if rec.get('role') in ('anon', 'newcomer'):
        return rec['role']
    return 'cast'


def cmd_prep(gid, mode='cast', only=None, skip=None, with_read=False):
    gs = groups()
    if gid not in gs:
        print('no such open group', gid); raise SystemExit(2)
    (pages, who, ax), grp = gs[gid]
    plist = pages.split('>')
    R = load_recipes()
    pg = json.load(io.open('.tmp/w4_action_pg.json', encoding='utf-8'))
    c = pg['cast'].get(who) or {}
    mark = 'W4M' + secrets.token_hex(3).upper()
    rc, since, err = psql("select to_char(now() - interval '2 seconds', 'YYYY-MM-DD\"T\"HH24:MI:SS.MSOF');")
    picked, roles, actors = [], set(), set()
    for t in grp:
        subj = t['w4']['action']['subject']
        if only and subj not in only:
            print('  %s %s: not in --only - left out of this walk' % (t['id'], subj)); continue
        if skip and subj in skip:
            print('  %s %s: --skip - left out of this walk' % (t['id'], subj)); continue
        rec = pick_recipe(R.get(subj) or {}, plist, t['id'])
        if not rec.get('steps'):
            print('  %s %s: no recipe (%s) - left out' % (t['id'], subj, rec.get('no_ui')
                  or ('held by a standing rule, ' + str((rec.get('held') or {}).get('decides') or '?') + ' decides' if rec.get('held') else 'not authored'))); continue
        if walk_mode(rec) != mode:
            print('  %s %s: a %s row - left out of this %s walk' % (t['id'], subj, walk_mode(rec), mode)); continue
        if rec.get('page') not in plist:
            print('  %s %s: its recipe page %s is not on the path (%s) - walked anyway, the page is visited for it' % (t['id'], subj, rec.get('page'), pages))
        roles.add(rec.get('role') or 'worker')
        if rec.get('actor'):
            actors.add(json.dumps(rec['actor'], sort_keys=True))
        picked.append((t, subj, rec))
    if not picked:
        print('nothing to walk in', gid); raise SystemExit(2)
    if mode == 'actor':
        if len(actors) != 1:
            print('REFUSED: more than one actor in one walk'); raise SystemExit(2)
        a = json.loads(actors.pop()); person = {'user': a['user'], 'name': a['name']}; role = 'actor'
    elif mode == 'anon':
        # ★A SIGNED-OUT STORY IS WALKED SIGNED OUT (2026-10-08): the landing page's e-mail form and the sign-up form
        # exist only for a stranger - a signed-in visitor gets the home dashboard instead - so these rows are lived by
        # the anonymous reader the walker already knows (P.anon), never by a cast member pretending not to be one.
        person = {'user': '', 'name': 'anonymous reader'}; role = 'anon'
    elif mode == 'newcomer':
        # ★A NEWCOMER IS BORN ON THE WALK (2026-10-08): set_worker_display_name refuses anyone who already holds a hive
        # membership, and every cast member holds one. The walker creates this account through the sign-up form
        # (P.signup) under a name no row in the database carries, so the sign-up trigger links nothing; the recipe's
        # reversal deletes the account (auth user, profile, memberships) again.
        person = {'user': mark.lower(), 'name': mark + ' Newcomer'}; role = 'newcomer'
    else:
        role = 'supervisor' if 'supervisor' in roles else 'worker'
        person = c.get(role) or c.get('worker') or c.get('supervisor')
    if not person:
        print('NO CAST for %r' % who); raise SystemExit(2)
    if person['user'] in NEVER_USERS:
        print('REFUSED: never walk as', person['user']); raise SystemExit(2)
    ctx = {'MARK': mark, 'SINCE': since, 'HIVE': c.get('hive_id'), 'USER': person['user'], 'NAME': person['name']}
    acts, seeded = [], []
    # ★EVERY SNAPSHOT BEFORE ANY SEED (2026-10-08). A recipe whose reversal restores a whole hive slice (alert_dismissals,
    # amc_briefings, credit_treasury ...) must snapshot the hive as it was BEFORE this walk - not after a sibling row's
    # seed has already added to it, or the restore would put the sibling's seed back after its own cleanup.
    befores, marks = {}, {}
    for i, (t, subj, rec) in enumerate(picked):
        # ★ONE MARK PER ROW, NOT PER GROUP (2026-10-08). Two recipes in one walk seeded the SAME 'w4-{MARK}' row (the
        # dayplanner's delete and update both seed today's task), so the second seed died on a duplicate key and its
        # row was never walked; and a selector aimed at "the seeded W4M row" could press a sibling recipe's seed. Each
        # row now carries its own mark: its seed, its typed values, its selectors and its effect/reversal SQL all use
        # it, so no two rows of one walk can see - or reverse - each other's data.
        marks[t['id']] = mark if i == 0 else 'W4M' + secrets.token_hex(3).upper()
        if rec.get('before_sql'):
            rc, o, e = psql(fill(rec['before_sql'], dict(ctx, MARK=marks[t['id']])))
            befores[t['id']] = (rc, o, e)
    for i, (t, subj, rec) in enumerate(picked):
        rmark = marks[t['id']]
        rctx = dict(ctx, MARK=rmark)
        before = None
        if rec.get('before_sql'):
            rc, o, e = befores[t['id']]
            if rc != 0:
                print('  %s %s: its snapshot (before_sql) failed - NOT walked, the reversal would have nothing to restore: %s' % (t['id'], subj, e[:160])); continue
            before = o
        if rec.get('seed_sql'):
            rc, o, e = psql(fill(rec['seed_sql'], rctx))
            seeded.append({'id': t['id'], 'rc': rc, 'err': e[:200]})
            if rc != 0:
                print('  %s %s: seed FAILED - NOT walked: %s' % (t['id'], subj, e[:160])); continue
        acts.append({'id': t['id'], 'kind': 'write', 'subject': subj, 'subjectPage': rec.get('page'), 'mark': rmark,
                     'edge': ((t.get('w4') or {}).get('action') or {}).get('kind') == 'edge',
                     # `last` is an ORDER among the after-path writes (leave 1, join 2, create 3, deactivate 9); true = 1
                     'last': int(rec.get('last') or 0), 'stubModel': rec.get('stub_model') or '',
                     'permissions': rec.get('permissions') or [],
                     'noWrite': bool(rec.get('no_write')), 'before': before,
                     'recipe': {'page': rec.get('page'), 'steps': rec.get('steps'), 'expect': rec.get('expect') or {}}})
    if not acts:
        print('nothing walkable in', gid); raise SystemExit(2)
    rpc_acts, sigs, safe, rctx_vals = [], {}, {}, dict(READ_RPC_CONTEXT)
    if with_read and mode == 'cast':
        import hashlib
        def _md5uuid(s):
            h = hashlib.md5(s.encode('utf-8')).hexdigest()
            return '%s-%s-%s-%s-%s' % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])
        # a value the story itself gives: the project / request one of this walk's own seeds just created
        for a in acts:
            sd = pick_recipe(R.get(a['subject']) or {}, plist, a['id']).get('seed_sql') or ''
            if "md5('{MARK}pj')" in sd and 'p_project_id' not in rctx_vals:
                rctx_vals['p_project_id'] = _md5uuid(a['mark'] + 'pj')
            if 'service_requests' in sd and "md5('{MARK}')::uuid" in sd and 'p_request_id' not in rctx_vals:
                rctx_vals['p_request_id'] = _md5uuid(a['mark'])
        for t in read_rpc_rows((pages, who, ax)):
            subj = t['w4']['action']['subject']
            rpc_acts.append({'id': t['id'], 'kind': 'rpc', 'subject': subj})
            sigs[subj] = pg['sigs'].get(subj, [''])
            safe[subj] = True
        for r in rpc_acts:
            print('  %s %s: a read rpc on this path - rides this walk (the page\'s own call, else the person\'s session)' % (r['id'], r['subject']))
    dev = ax.split(' ')[0]
    w, h = (320, 720) if dev == 'narrow-320' else (390, 844)
    args = {'id': gid, 'axis': ax, 'pages': plist, 'lang': ax.split(' ')[1], 'width': w, 'height': h,
            'origin': 'http://localhost:5000/workhive', 'api': 'http://127.0.0.1:54321',
            'anonKey': io.open('.tmp/local_anon_key.txt', encoding='utf-8').read().strip(),
            'actions': [{k: v for k, v in a.items() if k not in ('before', 'noWrite')} for a in acts] + rpc_acts,
            'sigs': sigs, 'safeRpcs': safe, 'context': rctx_vals,
            'hiveId': c.get('hive_id'), 'anon': mode == 'anon', 'user': person['user'], 'pass': 'test1234',
            # the hive the walk seats the cast in before the path (a member of several hives lands in the first by name)
            'castHive': c.get('hive_id') if mode == 'cast' else None,
            'signup': mode == 'newcomer',
            # names the person may legitimately carry after a recipe renames them (identity is the person, not the name)
            'castAliases': sorted({fill(x, dict(ctx, MARK=a['mark'])) for a in acts
                                   for x in (pick_recipe(R.get(a['subject']) or {}, plist, a['id']).get('aliases') or [])}),
            'castName': person['name'], 'mark': mark,
            # a recipe that must reach a model (it lands only after a model reads the file) walks with the model on;
            # every other walk keeps the no-model switch (2026-10-13)
            'liveModel': any(bool(pick_recipe(R.get(a['subject']) or {}, plist, a['id']).get('live_model')) for a in acts)}
    io.open(os.path.join('.tmp', 'w4_args.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(args, ensure_ascii=False))
    # a private copy: the args file is shared with every other driver, so the walk re-installs this one under the lock
    io.open(os.path.join('.tmp', 'w4_args_%s.json' % gid), 'w', encoding='utf-8', newline='\n').write(json.dumps(args, ensure_ascii=False))
    state = json.dumps(
        {'gid': gid, 'ctx': ctx, 'mode': mode, 'acts': [{'id': a['id'], 'subject': a['subject'], 'before': a['before'], 'noWrite': a['noWrite'],
                                           'page': a['subjectPage'], 'mark': a['mark'], 'edge': a.get('edge', False)} for a in acts],
         'rpcActs': rpc_acts, 'seeded': seeded}, ensure_ascii=False, indent=1)
    io.open(STATE, 'w', encoding='utf-8', newline='\n').write(state)
    io.open(state_path(gid), 'w', encoding='utf-8', newline='\n').write(state)
    print('%s prepped: %d row(s) as %s (%s) on %s, marks %s' % (gid, len(acts), person['name'], role, ax, ','.join(a['mark'] for a in acts)))


def cmd_bank(gid, settle_only=False):
    st = json.load(io.open(state_path(gid) if os.path.exists(state_path(gid)) else STATE, encoding='utf-8'))
    if st.get('gid') != gid:
        print('REFUSED: the write state is for %s, not %s' % (st.get('gid'), gid)); raise SystemExit(2)
    ap = os.path.join('.tmp', 'w4_args_%s.json' % gid)
    args = json.load(io.open(ap if os.path.exists(ap) else os.path.join('.tmp', 'w4_args.json'), encoding='utf-8'))
    if args.get('id') != gid:
        print('REFUSED: the args are for %s, not %s' % (args.get('id'), gid)); raise SystemExit(2)
    rp = os.path.join('.tmp', 'w4_steps', '%s.records.json' % gid)
    if os.path.getmtime(rp) < os.path.getmtime(state_path(gid) if os.path.exists(state_path(gid)) else STATE):
        print('REFUSED: %s is older than this prep - the walk did not run (or wrote elsewhere)' % rp); raise SystemExit(2)
    recs = json.load(io.open(rp, encoding='utf-8'))
    steps = json.load(io.open(os.path.join('.tmp', 'w4_steps', '%s.json' % gid), encoding='utf-8'))
    if isinstance(steps, dict):
        steps = steps.get('steps') or []
    answers = recs.get('answers') or {}
    R = load_recipes()
    plist = args.get('pages') or []
    ctx = dict(st['ctx'])
    compact = [{'page': s.get('page'), 'chars': s.get('chars'), 'identityKept': s.get('identityKept', True),
                'loadError': s.get('loadError') or None, 'lang': s.get('lang'),
                'fit': {'findings': (s.get('fit') or {}).get('findings') or 0, 'occlusion': ((s.get('fit') or {}).get('occlusion') or [])[:4],
                        'overflowEl': ((s.get('fit') or {}).get('overflowEl') or [])[:2], 'wrapped': ((s.get('fit') or {}).get('wrapped') or [])[:2]}}
               for s in steps]
    sp = os.path.join('.tmp', 'w4_steps', '%s.compact.json' % gid)
    io.open(sp, 'w', encoding='utf-8', newline='\n').write(json.dumps(compact, ensure_ascii=False))
    wrote = []
    # ★READ EVERY EFFECT FIRST, REVERSE LAST-IN-FIRST-OUT, PROVE ON THE FINAL STATE (2026-10-08). One row at a time
    # (read, reverse, check, next) let an earlier row's reversal - a whole-slice restore - erase the evidence a later
    # row's effect_sql was about to read, and a later reversal could re-break a check that had already passed. And a
    # press that did NOT answer as expected was never reversed at all, though it may still have written: every row's
    # reversal is keyed to its own mark / window / snapshot, so it is run for every row and is a no-op where nothing
    # was written (a reversal that needs {ID}/{IDS} is skipped when no effect row was found to fill it).
    # ★SETTLE UNDER THE LOCK, RECORD AFTER IT (2026-10-08). A walk that deactivates the cast leaves a shared seeded
    # account locked out of every hive until its reversal runs; between this walker releasing the browser and the
    # bank restoring the account, another walker could sign in as that person and walk a stranger. `settle` runs
    # only the postgres half (read every effect, reverse, prove) in seconds, so it can run BEFORE the lock is
    # released; `bank` then reuses its result instead of reading effects that have already been reversed.
    settled_p = os.path.join('.tmp', 'w4_settled_%s.json' % gid)
    settled = None
    if os.path.exists(settled_p) and os.path.getmtime(settled_p) >= os.path.getmtime(rp):
        settled = json.load(io.open(settled_p, encoding='utf-8'))
    # ★A SEEDED HIVE TAKES ITS SHADOW ROWS WITH IT (2026-10-12). Recipes that seed a hive (join, deactivate, create,
    # switch) reverse the hive and the rows they NAME - but a hive grows rows by trigger and by being looked at:
    # hive_readiness + its audit when the walk computed readiness, an analytics_events page_view while it was the
    # active hive. Those outlived the hive as orphans (51 found today). Every hive whose name carries one of this
    # walk's marks is collected BEFORE the reversals; after them, every hive-keyed table is swept for those ids.
    _marks = sorted({a.get('mark') for a in st['acts'] if a.get('mark')} | {ctx.get('MARK')} - {None, ''})
    _rc, _hv, _e = psql("select id from public.hives where " + " or ".join("name like '%%%s%%'" % m for m in _marks)
                        + ";") if _marks else (1, '', '')
    marked_hives = [x.strip() for x in (_hv or '').splitlines() if re.fullmatch(r'[0-9a-f-]{36}', x.strip())]
    rows = []
    for a in st['acts']:
        rid, subj = a['id'], a['subject']
        rec = pick_recipe(R.get(subj) or {}, plist, rid)
        ans = answers.get(rid) or {}
        c2 = dict(ctx); c2['BEFORE'] = a.get('before') or ''
        c2['MARK'] = a.get('mark') or ctx['MARK']   # each row's own mark (see cmd_prep)
        row = {'a': a, 'rid': rid, 'subj': subj, 'rec': rec, 'ans': ans, 'c2': c2, 'found': [],
               'problems': list(ans.get('problems') or []), 'effect': '', 'rev': None}
        if settled is not None:
            s = settled.get(rid) or {}
            row.update({'found': s.get('found') or [], 'problems': s.get('problems') or row['problems'],
                        'effect': s.get('effect') or '', 'settled': True})
        elif ans.get('ok') and not a.get('noWrite'):
            rc, ids, err = psql(fill(rec.get('effect_sql'), c2)) if rec.get('effect_sql') else (1, '', 'no effect_sql')
            row['found'] = [x for x in ids.splitlines() if x.strip()] if rc == 0 else []
            if not row['found']:
                row['problems'].append('the press answered 2xx but no persisted %s was found (%s)' % (subj, err[:120] or 'effect_sql returned nothing'))
            else:
                c2['IDS'] = ','.join("'%s'" % x.split('\t')[0] for x in row['found'])
                c2['ID'] = row['found'][0].split('\t')[0]
        elif not a.get('noWrite') and rec.get('effect_sql'):
            # ★A PRESS THAT FAILED MAY STILL HAVE WRITTEN (2026-10-12, W4704). The project wizard created the project
            # and the walk then stopped at a confirm it never saw - so the row was not ok, its effect was never read,
            # and a reversal keyed to {IDS} was skipped: "SHD-2026-001 W4M… project" stayed in the cast's hive. The
            # effect is read here ONLY to undo it; the row is still not banked.
            rc, ids, err = psql(fill(rec['effect_sql'], c2))
            leaked = [x for x in ids.splitlines() if x.strip()] if rc == 0 else []
            if leaked:
                c2['IDS'] = ','.join("'%s'" % x.split('\t')[0] for x in leaked)
                c2['ID'] = leaked[0].split('\t')[0]
                print('  %s %s: the press did not answer as expected but wrote %d row(s) - reversing them' % (rid, subj, len(leaked)))
        rows.append(row)
    for row in reversed(rows):
        rec, c2 = row['rec'], row['c2']
        if row.get('settled') or row['a'].get('noWrite') or not rec.get('reverse_sql'):
            continue
        sql = fill(rec['reverse_sql'], c2)
        if '{ID}' in sql or '{IDS}' in sql:
            continue   # nothing found to name; the seed cleanup below still runs
        rs = rec.get('reverse_storage') or {}
        objs = []
        if rs:
            # the stored files are named BEFORE the SQL reversal, which may delete what the query joins on
            rcs, outs, errs = psql(fill(rs.get('names_sql') or '', c2))
            objs = [x.strip() for x in (outs or '').splitlines() if x.strip()] if rcs == 0 else []
        row['rev'] = psql(sql)
        if objs:
            rcr, msg = _storage_remove(args.get('api') or '', rs.get('bucket') or '', objs)
            row['storage'] = (rcr, msg, len(objs))
            if rcr != 0:
                row['problems'].append('the stored photo was not removed: ' + msg)
    for row in rows:
        rec, c2, ans, subj, found = row['rec'], row['c2'], row['ans'], row['subj'], row['found']
        if row['a'].get('noWrite') or not rec.get('reverse_sql') or row['rev'] is None:
            continue
        rc2, o2, e2 = row['rev']
        if rec.get('reverse_check_sql'):
            rc4, o4, e3 = psql(fill(rec['reverse_check_sql'], c2))
            reversed_ok = rc2 == 0 and rc4 == 0 and o4.strip().lower() in ('t', 'true', '1')
        else:
            rc3, left, e3 = psql(fill(rec.get('effect_sql'), c2))
            reversed_ok = rc2 == 0 and rc3 == 0 and not [x for x in left.splitlines() if x.strip()]
        if not (ans.get('ok') and found):
            if not reversed_ok:
                print('  WARNING %s %s: its cleanup reversal did not prove clean (%s) - check for data left behind' % (row['rid'], subj, (e2 or e3 or 'check false')[:140]))
            continue
        row['effect'] = '%s: %s via the page\'s own control on %s, %d row(s) %s carrying %s, %s' % (
            subj, (ans.get('effect') or {}).get('request') or '?', (ans.get('effect') or {}).get('page') or rec.get('page'),
            len(found), ', '.join(x.split('\t')[0][:12] for x in found[:3]), c2['MARK'],
            'reversed and re-checked' if reversed_ok else 'REVERSAL NOT PROVEN (%s)' % (e2 or e3)[:100])
        if row.get('storage') and row['storage'][0] == 0:
            row['effect'] += ', its %d stored file(s) removed through the Storage API' % row['storage'][2]
        if not reversed_ok:
            row['problems'].append('the reversal of %s was not proven: %s' % (subj, (e2 or e3 or 'rows remain')[:140]))
    for row in rows:
        if row['ans'].get('ok') and not row['a'].get('noWrite') and row['found'] and not row['effect'] \
                and not any('no reversal ran' in p for p in row['problems']):
            row['problems'].append('the effect of %s was found but no reversal ran for it' % row['subj'])
    # an EDGE row's effect is the answer landing where the person pressed: the function's own request and status, what
    # the person was told, and the provenance the page shows - plus, for a function that writes, the rows read and
    # reversed above. A no-write function leaves nothing to reverse, but the ledger still needs the effect recorded.
    # ★THE EDGE FLAG NEVER REACHED THE BANK (2026-10-12, W4104). prep put `edge` on the walk's actions but not on the
    # saved state the bank iterates, so `a.get('edge')` was always empty: no edge row could ever compose its effect,
    # and the ledger (which needs a persisted-effect receipt for an edge row) banked none - "1 recorded, 0 banked".
    # The state carries it now; a state written before that reads the row's kind from the registry.
    _edge_kind = {t['id']: ((t.get('w4') or {}).get('action') or {}).get('kind') == 'edge'
                  for t in json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']}
    for row in rows:
        a, ans = row['a'], row['ans']
        if not (a.get('edge') or _edge_kind.get(row['rid'])) or not ans.get('ok') or row.get('settled'):   # a settled row already carries it
            continue
        eff = ans.get('effect') or {}
        landed = '%s: %s via the page\'s own control on %s, the answer landed%s; provenance on the page: "%s"' % (
            row['subj'], eff.get('request') or '?', eff.get('page') or row['rec'].get('page'),
            ('; the person was told "%s"' % eff['told'][:90]) if eff.get('told') else '',
            (recs.get('provenance') or 'none shown')[:100])
        row['effect'] = landed + (('; ' + row['effect']) if row['effect'] else '')
    if settled is None:
        io.open(settled_p, 'w', encoding='utf-8', newline='\n').write(json.dumps(
            {r['rid']: {'found': r['found'], 'problems': r['problems'], 'effect': r['effect']} for r in rows}, ensure_ascii=False, indent=1))
    if settle_only:
        for r in rows:
            print('  settled %s %-5s %s' % (r['rid'], 'OK' if (r['ans'].get('ok') and not r['problems']) else 'open',
                                            (r['effect'] or '; '.join(r['problems']) or 'no write expected')[:200]))
        return
    for row in rows:
        rid, subj, ans, effect, problems = row['rid'], row['subj'], row['ans'], row['effect'], row['problems']
        note = (ans.get('note') or '') + (' Persisted effect read and reversed through postgres: ' + effect if effect else '')
        cmd = [sys.executable, 'tools/record_mcp_walk.py', '--id', rid, '--walked-at', _walked_at(gid), '--instrument', 'playwright-mcp + postgres-mcp',
               '--cast', recs.get('cast') or args.get('castName'), '--axis', args['axis'], '--steps', sp, '--note', note[:1500]]
        if effect and not problems:
            cmd += ['--effect', effect[:400]]
        prov = _fixture_provenance(row['rec'])
        if prov:
            cmd += ['--fixture-provenance', prov]
        if problems or not ans.get('ok'):
            cmd += ['--unproven', '; '.join(problems or ['not lived clean'])[:300]]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print('  %s %-5s %s' % (rid, 'OK' if (ans.get('ok') and not problems) else 'open', (note or '')[:220]))
        if r.returncode != 0:
            print('    record_mcp_walk FAILED: %s' % (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200])
            continue
        wrote.append(rid)
    # the read rpcs that rode this walk (prep --with-read): the call and its answer ARE the evidence, no effect
    for ra in st.get('rpcActs') or []:
        rid = ra['id']; ans = answers.get(rid) or {}
        note = (ans.get('note') or 'no answer recorded') + (' Walked in the write walk of its own path and cast, seated in the'
                                                             ' cast\'s hive; read-only status (pg_proc.provolatile / the safe map),'
                                                             ' the signature and the argument values read through the postgres MCP.')
        cmd = [sys.executable, 'tools/record_mcp_walk.py', '--id', rid, '--walked-at', _walked_at(gid), '--instrument', 'playwright-mcp + postgres-mcp',
               '--cast', recs.get('cast') or args.get('castName'), '--axis', args['axis'], '--steps', sp, '--note', note[:1500]]
        if not ans.get('ok'):
            cmd += ['--unproven', '; '.join(ans.get('problems') or ['not lived clean'])[:300]]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print('  %s %-5s %s' % (rid, 'OK' if ans.get('ok') else 'open', note[:200]))
        if r.returncode != 0:
            print('    record_mcp_walk FAILED: %s' % (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200])
            continue
        wrote.append(rid)
    # clean any seeded row the walk did not consume
    for a in st['acts']:
        rec = pick_recipe(R.get(a['subject']) or {}, plist, a['id'])
        if rec.get('seed_cleanup_sql'):
            # {BEFORE} too (2026-10-12): a read rpc lived by its control may need the page's OTHER call undone - the
            # readiness read runs only after hive.html recomputes a stale snapshot, so its cleanup restores the snapshot
            rc, o, e = psql(fill(rec['seed_cleanup_sql'], dict(ctx, MARK=a.get('mark') or ctx['MARK'], BEFORE=a.get('before') or '')))
            if rc != 0:
                print('  seed cleanup for %s FAILED: %s' % (a['id'], e[:160]))
    # the shadow rows of every marked hive that the reversals removed (see marked_hives above)
    gone = [h for h in marked_hives if not psql("select 1 from public.hives where id = '%s';" % h)[1].strip()]
    if gone:
        ids = ",".join("''%s''" % h for h in gone)   # doubled: they sit inside the single-quoted format() literal
        rc, o, e = psql(
            "begin; set local session_replication_role = replica; do $sweep$ declare r record; begin "
            "for r in select c.table_name from information_schema.columns c join information_schema.tables t "
            "on t.table_schema = c.table_schema and t.table_name = c.table_name where c.table_schema = 'public' "
            "and c.column_name = 'hive_id' and t.table_type = 'BASE TABLE' and c.table_name <> 'hives' loop "
            "execute format('delete from public.%%I where hive_id in (%s)', r.table_name); end loop; end $sweep$; commit;" % ids)
        print('  swept the shadow rows of %d removed seed hive(s)%s' % (len(gone), '' if rc == 0 else ' - FAILED: ' + e[:160]))
    advance(gid, wrote, args['axis'])


def advance(gid, wrote, ax):
    advance_many(gid, [(r, ax) for r in wrote])


def advance_many(label, items, kind='action'):
    """record-then-advance in ONE ledger pass for any number of rows: (rid, axis) pairs. `kind` picks the board gate
    the row locks under (bank_w4_passers.GATES: an action row's w4-actions*, a confusion row's w4-confusions*)."""
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
        if res.get('ok') and m._w4_missing(t, rec) == '' and 'playwright-mcp + postgres-mcp' in str(res.get('instrument')):
            entries.append({'ids': rid, 'status': 'locking', 'pct': 60, 'gate': [bwp.GATES.get((kind, ax))], 'basis': bwp._basis(t, res, ax)})
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
        n = 0
        for t in reg['trajectories']:
            if t['id'] not in banked:
                continue
            parts = re.split(r' · (?=\[\d{4}-\d{2}-\d{2}\])', t.get('basis') or '')
            last = parts[-1]
            if len(parts) > 1 and last.startswith('[%s]' % today) and ('WALKED LIVE %s via playwright-mcp + postgres-mcp' % today) in last:
                t['basis'] = last + ' || ' + ' · '.join(parts[:-1]); n += 1
        fd, tmp = tempfile.mkstemp(dir=PROJ, suffix='.tmp'); os.close(fd)
        io.open(tmp, 'w', encoding='utf-8', newline='\n').write(json.dumps(reg, ensure_ascii=False, indent=1) + '\n')
        os.replace(tmp, 'trajectory_registry.json')
        print('  promoted %d of %d' % (n, len(banked)))
    b = m.build(); rows = b['rows'] if isinstance(b, dict) else b
    ids = {r for r, _ in items}
    closed = [r['id'] for r in rows if r['id'] in ids and m.row_closed(r)]
    print('%s: %d recorded, %d banked, %d CLOSED in the ledger' % (label, len(items), len(banked), len(closed)))


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    def _opt(name):
        return set(sys.argv[sys.argv.index(name) + 1].split(',')) if name in sys.argv else None
    if sys.argv[1] == '--list':
        cmd_list()
    elif sys.argv[1] == 'prep':
        cmd_prep(sys.argv[2], mode=next((m for m in ('actor', 'anon', 'newcomer') if '--' + m in sys.argv), 'cast'),
                 only=_opt('--only'), skip=_opt('--skip'), with_read='--with-read' in sys.argv)
    elif sys.argv[1] == 'install':
        # re-install a prepped group's args as THE args file, immediately before its walk (under the browser lock):
        # .tmp/w4_args.json is shared with every other driver, so another prep may have replaced it since ours
        src = os.path.join('.tmp', 'w4_args_%s.json' % sys.argv[2])
        body = io.open(src, encoding='utf-8').read()
        io.open(os.path.join('.tmp', 'w4_args.json'), 'w', encoding='utf-8', newline='\n').write(body)
        print('installed', src)
    elif sys.argv[1] == 'settle':
        cmd_bank(sys.argv[2], settle_only=True)
    elif sys.argv[1] == 'bank':
        cmd_bank(sys.argv[2])
    else:
        print(__doc__); raise SystemExit(2)
