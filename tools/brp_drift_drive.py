"""brp_drift_drive.py - drive the open BRP class-A rows ("ownership asked by DISPLAY NAME where the table carries
auth_uid") through the Playwright MCP, with the postgres reading beside it (2026-10-12).

Each BRP-A row closes "only when the reproduction is made to FAIL on demand and a gate holds the fix, measured at
phone-390 and desktop-1280". The fix (auth_uid unioned in beside the name, never swapped) landed in the class-A wave and
is held by the gate bug-repro-ratchet; what the ledger lacks for 32 rows is the LIVE reading. This drive supplies both
halves:

  postgres  - for the row's cast and table: rows by identity (auth_uid), by the stored display name, and by the name
              drifted one character. The drifted-name count is what a name-only read would return.
  browser   - tools/brp_drift_walk.js signs in as the cast, walks the row's pages, and records every PostgREST read of
              the table on the row's page under the stored name and again after the one-character drift (client side,
              localStorage - nothing is written), at phone-390 and desktop-1280.

A row banks only when, at BOTH viewports, the page read the table, nothing it read shrank under the drift, no read
asked by name alone, and no "you were removed" notice appeared - with the postgres half showing the drift is real
(rows by identity > 0, rows by the drifted name = 0). Anything else is HELD and printed with its reason.

  python tools/brp_drift_drive.py --list               open BRP rows with their cast and postgres reading
  python tools/brp_drift_drive.py prep [--n N] [ids]   write .tmp/brp_args.json (default: the next 4 open A rows)
  (walk:  browser_run_code_unsafe { filename: tools/brp_drift_walk.js })
  python tools/brp_drift_drive.py bank                 judge the walk, record receipts, advance what holds

Nothing here signs in as `ianphone`; casts are seeded local workers, password test1234 (local only).
"""
import io
import json
import os
import subprocess
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, 'tools')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ARGS = os.path.join('.tmp', 'brp_args.json')
NEVER_USERS = {'ianphone'}
GATE = 'bug-repro-ratchet'

# the marketplace write rows' fixtures (2026-10-13), seeded by psql before the walk and gone after it: four saved searches
# for the saved-search delete (BRP75), four saves on PUBLISHED listings for the un-save (BRP77), and two saves on SOLD
# listings - unreadable to a buyer, so "no longer available" - for the cleanup (BRP78)
FX_SAVED_SEARCHES = ['b0750000-0000-4000-8000-00000000000%d' % i for i in range(1, 5)]
FX_WATCH_LIVE = ['25ea023f-d6d2-43ee-9c60-097e1690172e', '74213940-4ec1-48e8-9386-20f19a52fb87',
                 '53e588ba-37bd-4666-818a-10656bab2878', '5266ab4a-ef4a-4c1a-910c-ecde3adf0521']
FX_WATCH_GONE = ['a5141789-e8ae-4039-8dba-201d47130fa9', '685753cc-8768-4963-8378-f44ba53032f6']
ISIDRO = '58d71041-46eb-406b-85d8-5c9851c49b37'


def _in(ids):
    return '(' + ','.join("'%s'" % i for i in ids) + ')'


# ★THE PRESS A ROW'S READ SITS BEHIND (2026-10-13). Four rows held as "the page made no read of the table on load":
# their reads run only when the person opens something - logbook's asset detail (inventory_items) and an asset chosen in
# the entry form (its PM tasks, pm_assets), pm-scheduler's add-asset wizard (registered asset_nodes), a skillmatrix
# discipline (the last exam attempt). Each step is {click: css} or {wait: ms}; the walk runs them after the page loads,
# under the stored name and again under the drift, so the read is made both times. Nothing here saves: the presses open
# views and pickers, and the entry-form draft lives in the walk's own throwaway browser context.
ACTIONS = {
    # the asset whose stocked parts the read returns: Cummins QSK60-G4 carries 3 of Hector's linked parts (a first
    # asset with none read 0 -> 0, which proves nothing about the drift); the asset dialog opens for a SUPERVISOR only
    'BRP29': [{'click': '#open-asset-modal-btn'}, {'wait': 900}, {'click': '#asset-tab-manage'}, {'wait': 1800},
              {'click': 'button[aria-label="View Cummins QSK60-G4 details"]'}, {'wait': 2500}],
    # the pm_assets read is the SOLO path (a hive reads v_pm_compliance_truth) and runs only for a Preventive Maintenance
    # entry with a machine chosen in the picker. The only solo owners of PM assets are not on the seeded password, so a
    # marked fixture pair is seeded for Jun Salvador (a seeded solo van owner) - asset node + PM asset, tag BRP33-FX -
    # walked, and removed afterwards
    # (the entry form is a stepped wizard: choosing the asset in step 1 advances it to step 2, where the type lives, and
    # the type's change runs the PM loader once a machine is set)
    'BRP33': [{'click': '#asset-picker-btn'}, {'wait': 1500}, {'click': '[data-asset-name="BRP33 walk fixture van"]'},
              {'wait': 1500}, {'select': '#f-maint-type', 'value': 'Preventive Maintenance'}, {'wait': 2500}],
    'BRP40': [{'click': '#tab-add'}, {'wait': 2500}],
    # the profile drawer reads community_xp for whoever's presence chip is pressed. A chip's key is that person's DEVICE
    # name and its payload carries their auth_uid, so pressing my own "(you)" chip after the drift asks with the drifted
    # name beside my identity - the reproduction the row describes, through the page's own control
    'BRP14': [{'wait': 2500}, {'click': '#presence-bar .presence-chip:has-text("(you)")'}, {'wait': 2500}],
    # the delete guards: open a marked fixture part, press Remove, accept the confirm. Each phase removes the first
    # fixture still listed (four are seeded per row: two viewports x stored and drifted)
    'BRP16': [{'wait': 1500}, {'click': '.part-card:has-text("BRP16 walk fixture") button[aria-label="Open item details"]'},
              {'wait': 1200}, {'click': '[data-i="removefrominventory"]'}, {'wait': 800}, {'click': '[data-wh-modal-ok]'},
              {'wait': 2500}],
    'BRP17': [{'wait': 1500}, {'click': '.part-card:has-text("BRP17 walk fixture") button[aria-label="Open item details"]'},
              {'wait': 1200}, {'click': '[data-i="removefrominventory"]'}, {'wait': 800}, {'click': '[data-wh-modal-ok]'},
              {'wait': 2500}],
    # the machine-history read runs when a machine is chosen in the entry form, and only its SOLO branch asks by owner
    # (a hive's is hive-scoped). Jun Salvador's three history rows are on machine "Own unit", which no asset of his
    # carried, so a marked solo asset with that tag is seeded (external_ids fixture BRP70-FX), walked, and removed
    'BRP70': [{'click': '#asset-picker-btn'}, {'wait': 1500}, {'click': '[data-asset-name="BRP70 walk fixture van"]'},
              {'wait': 2500}],
    # marketplace: the saved-search list lives in a sheet; its delete asks a confirm. Fixture searches carry FIXED ids
    # so the press can never land on the person's own saved search (a text match on an outer container could)
    'BRP74': [{'click': '#btn-saved-searches'}, {'wait': 2500}],
    'BRP75': [{'click': '#btn-saved-searches'}, {'wait': 2500},
              {'click': ':is(' + ','.join('.btn-delete-search[data-id="%s"]' % i for i in FX_SAVED_SEARCHES) + ')'},
              {'wait': 800}, {'click': '[data-wh-modal-ok]'}, {'wait': 2500}],
    # the watchlist sheet's Remove un-saves through toggleWatchlist (the BRP-C delete); fixture saves are on four
    # published listings the cast had not saved, so the press can never take one of the person's own saves
    'BRP77': [{'click': '#btn-my-watchlist'}, {'wait': 2500},
              {'click': ':is(' + ','.join('.btn-watch-remove[data-id="%s"]' % i for i in FX_WATCH_LIVE) + ')'},
              {'wait': 2500}],
    # "remove every unavailable save" deletes ALL of them in one press, so the stored phase only opens the sheet and the
    # press is made after the drift; the row is walked one viewport at a time (prep --viewport) with a re-seed between
    'BRP78': [{'click': '#btn-my-watchlist'}, {'wait': 2500}, {'only': 'drifted', 'click': '#btn-clear-gone-saves'},
              {'wait': 2500}],
    # the cooldown read asks for the last attempt at the NEXT level, and only below the target: Romeo has passed
    # Production Lines 1, targets 5, and has tried level 2
    'BRP45': [{'click': '.disc-card[data-disc="Production Lines"]'}, {'wait': 2500}],
}

# ★A ROW WHOSE READ ONLY ONE KIND OF PERSON REACHES NAMES ITS CAST (2026-10-13). The default cast is the hive member who
# owns the most rows; that person cannot reach a solo-only read (BRP33) or owns no part linked to an asset (BRP29: Oscar's
# parts are linked to none, so his asset detail read 0 rows whatever the name said).
CAST = {'BRP29': 'hectorsalvador', 'BRP33': 'junvanowner', 'BRP45': 'romeobeltran',
        # BRP16 is the hive branch's guard, which binds only a NON-supervisor (a supervisor deletes hive-wide), so its
        # cast is a hive worker; BRP17 is the solo branch, so a solo owner
        'BRP16': 'driverben', 'BRP17': 'junvanowner',
        # BRP70's owner-scoped branch is the solo one, and every fleet hive's history is keyed by asset NAME where the
        # picker passes the TAG (seed data), so a hive cast reads 0 -> 0 and proves nothing
        'BRP70': 'junvanowner'}

# ★A ROW WHOSE SITE IS A WRITE (2026-10-13, BRP16/BRP17). The site is a DELETE guard, so the proof is the delete the
# page's own Remove button sends, on marked fixtures seeded for the cast: the drifted delete must carry the identity and
# not the name alone, and every fixture must be GONE in postgres afterwards - PostgREST answers 204 to a delete whose
# filter matched nothing, so the status alone proves nothing.
WRITES = {
    'BRP16': {'method': 'DELETE', 'fixture': "part_number like 'BRP16-FX-%'"},
    'BRP17': {'method': 'DELETE', 'fixture': "part_number like 'BRP17-FX-%'"},
    'BRP75': {'method': 'DELETE', 'fixture': 'id in %s' % _in(FX_SAVED_SEARCHES)},
    'BRP77': {'method': 'DELETE', 'fixture': "auth_uid = '%s' and listing_id in %s" % (ISIDRO, _in(FX_WATCH_LIVE))},
    'BRP78': {'method': 'DELETE', 'phases': ['drifted'],
              'fixture': "auth_uid = '%s' and listing_id in %s" % (ISIDRO, _in(FX_WATCH_GONE))},
}


def _actions_said(acts):
    return ' then '.join((s.get('click') or ('choosing "%s" in %s' % (s['value'], s['select'])))
                         + ((' (%s phase only)' % s['only']) if s.get('only') else '')
                         for s in acts if s.get('click') or s.get('select'))


def cast_override(t, user):
    """the named cast's reading for the row's table: rows by identity, by the stored display name, by the drifted name"""
    table = (t.get('brp') or {}).get('table')
    rc, out, err = psql("select u.id, coalesce((select m.worker_name from public.hive_members m where m.auth_uid = u.id "
                        "and m.status = 'active' order by m.worker_name limit 1), (select w.display_name from "
                        "public.worker_profiles w where w.auth_uid = u.id limit 1)), coalesce((select h.name from "
                        "public.hive_members m join public.hives h on h.id = m.hive_id where m.auth_uid = u.id and "
                        "m.status = 'active' order by h.name limit 1), '(no hive - solo)') from auth.users u "
                        "where split_part(u.email, '@', 1) = %s;" % q(user))
    if rc != 0 or not out:
        return None, 'postgres: no account %s (%s)' % (user, (err or '')[-120:])
    uid, name, hname = out.splitlines()[0].split('\t')
    d = drift(name)
    counts = []
    for where in ("auth_uid = %s" % q(uid), "worker_name = %s" % q(name), "worker_name = %s" % q(d)):
        rc2, o2, _ = psql("select count(*) from public.%s where %s;" % (table, where))
        counts.append(int(o2 or 0) if rc2 == 0 else None)
    return {'cast': name, 'user': user, 'uid': uid, 'byIdentity': counts[0], 'byName': counts[1], 'drifted': d,
            'byDrifted': counts[2], 'hive': hname}, ''


def psql(sql):
    r = subprocess.run(['docker', 'exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1',
                        '-tA', '-F', '\t'], input=sql, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


def open_brp(cls='A'):
    import live_walk_manifest as m
    b = m.build()
    opn = {r['id'] for r in b['rows'] if not m.row_closed(r)}
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    return [t for t in reg if t['id'] in opn and str(t.get('wave', '')) == 'BRP-' + cls]


def columns(table):
    rc, out, _ = psql("select column_name from information_schema.columns where table_schema='public' and table_name=%s;" % q(table))
    return set(out.split()) if rc == 0 else set()


def drift(name):
    """one character: the last letter's case flipped (a case drift is what a rename or a stale device presents, and
    postgres '=' is case-sensitive, so a name-only read misses it)"""
    for i in range(len(name) - 1, -1, -1):
        c = name[i]
        if c.isalpha():
            return name[:i] + (c.lower() if c.isupper() else c.upper()) + name[i + 1:]
    return name + '.'


def cast_and_reading(t, any_hive=False):
    """the hive member (with an account) who owns the most rows of the row's table, and the postgres reading;
    any_hive: a persona-'any' row may take its cast from any hive when its own holds no rows"""
    b = t.get('brp') or {}
    table = b.get('table')
    hive = (t.get('journey') or {}).get('vertical') or ''
    cols = columns(table)
    if 'auth_uid' not in cols:
        return None, 'the table carries no auth_uid (%s) - not a class-A relation' % table
    if 'worker_name' not in cols:
        return None, 'the table carries no worker_name column (%s) - the name key lives elsewhere' % table
    hive_f = ' and x.hive_id = h.id' if 'hive_id' in cols else ''
    sql = ("select m.worker_name, split_part(u.email,'@',1), m.auth_uid, "
           "(select count(*) from public.%s x where x.auth_uid = m.auth_uid%s), "
           "(select count(*) from public.%s x where x.worker_name = m.worker_name%s), h.name "
           "from hives h join hive_members m on m.hive_id = h.id join auth.users u on u.id = m.auth_uid "
           "where %s m.status = 'active' order by (h.name = %s) desc, 4 desc, m.worker_name limit 12;"
           % (table, hive_f, table, hive_f, '' if any_hive else 'h.name = %s and' % q(hive), q(hive)))
    rc, out, err = psql(sql)
    if rc != 0:
        return None, 'postgres: ' + err[-160:]
    for line in out.splitlines():
        name, user, uid, by_id, by_name, hname = line.split('\t')
        if user in NEVER_USERS or int(by_id) == 0:
            continue
        d = drift(name)
        rc2, out2, _ = psql("select count(*) from public.%s x join hives h on h.name = %s where x.worker_name = %s%s;"
                            % (table, q(hname), q(d), hive_f))
        return {'cast': name, 'user': user, 'uid': uid, 'byIdentity': int(by_id), 'byName': int(by_name),
                'drifted': d, 'byDrifted': int(out2 or 0) if rc2 == 0 else None, 'hive': hname}, ''
    return None, 'no active member of %s with an account owns a row of %s by identity' % (hive, table)


def _rls_count(table, uid):
    """the rows row-level security returns to this person, impersonated in a rolled-back transaction"""
    rc, out, err = psql("begin; set local role authenticated; "
                        "select set_config('request.jwt.claims', '{\"sub\":\"%s\",\"role\":\"authenticated\"}', true); "
                        "select count(*) from public.%s; rollback;" % (uid, table))
    nums = [ln for ln in (out or '').splitlines() if ln.strip().isdigit()]
    return int(nums[-1]) if rc == 0 and nums else None


def cast_and_reading_c(t):
    """class C: the relation carries NO identity column - ownership is only expressible as a name. The class-C fix
    removed the client's name filter and leans on row-level security (policies derived from auth.uid()), so the
    reading is: rows by the stored name, rows by the drifted name, and the rows RLS returns to the person when
    impersonated. The row's hive is preferred; any person holding rows of the table will do (persona 'any')."""
    b = t.get('brp') or {}
    table = b.get('table')
    hive = (t.get('journey') or {}).get('vertical') or ''
    cols = columns(table)
    if 'auth_uid' in cols:
        return None, 'the table now carries auth_uid (%s) - read it as class A' % table
    if 'worker_name' not in cols:
        return None, 'the table carries no worker_name column (%s)' % table
    sql = ("select m.worker_name, split_part(u.email,'@',1), m.auth_uid, h.name, "
           "(select count(*) from public.%s x where x.worker_name = m.worker_name) "
           "from hives h join hive_members m on m.hive_id = h.id join auth.users u on u.id = m.auth_uid "
           "where m.status = 'active' order by (h.name = %s) desc, 5 desc, m.worker_name limit 12;" % (table, q(hive)))
    rc, out, err = psql(sql)
    if rc != 0:
        return None, 'postgres: ' + err[-160:]
    for line in out.splitlines():
        name, user, uid, hname, by_name = line.split('\t')
        if user in NEVER_USERS or int(by_name) == 0:
            continue
        d = drift(name)
        rc2, out2, _ = psql("select count(*) from public.%s x where x.worker_name = %s;" % (table, q(d)))
        return {'cast': name, 'user': user, 'uid': uid, 'byIdentity': None, 'byName': int(by_name),
                'drifted': d, 'byDrifted': int(out2 or 0) if rc2 == 0 else None, 'hive': hname,
                'rls': _rls_count(table, uid), 'cls': 'C'}, ''
    return None, 'no active member with an account holds a row of %s by name' % table


def reading_for(t):
    """class A reads by identity; a class-C row whose relation has SINCE gained auth_uid (the class-C fix's migration
    landed) is read as class A too, marked so the basis says so; a still name-only relation is read as class C"""
    if t.get('id') in CAST:
        r, why = cast_override(t, CAST[t['id']])
        if r and str(t.get('wave')) == 'BRP-C':
            r['migrated'] = True        # seeded class C; its relation has since gained auth_uid, so it is read as A
        return r, why
    if str(t.get('wave')) == 'BRP-C':
        b = t.get('brp') or {}
        if 'auth_uid' in columns(b.get('table')):
            r, why = cast_and_reading(t, any_hive=True)
            if r:
                r['migrated'] = True
            return r, why
        return cast_and_reading_c(t)
    return cast_and_reading(t)


def cmd_list(cls='A'):
    rows = open_brp(cls)
    for t in rows:
        b = t.get('brp') or {}
        r, why = reading_for(t)
        if r and r.get('cls') == 'C':
            print('%-6s %-24s %-28s cast %s (%s, %s): %d by name, %s by "%s", %s through RLS as the person'
                  % (t['id'], b.get('page'), b.get('table'), r['cast'], r['user'], r['hive'], r['byName'],
                     r['byDrifted'], r['drifted'], r['rls']))
            continue
        print('%-6s %-24s %-22s %s' % (t['id'], b.get('page'), b.get('table'),
                                       ('cast %s (%s): %d by identity, %d by name, %s by "%s"' % (r['cast'], r['user'], r['byIdentity'], r['byName'], r['byDrifted'], r['drifted'])) if r else 'NO CAST: ' + why))
    print(len(rows), 'open BRP-%s rows' % cls)


VIEWPORT_SIZES = {'phone-390': [390, 844, 'phone-390'], 'desktop-1280': [1280, 800, 'desktop-1280']}


def merge_parts(a):
    """★A ROW WALKED ONE VIEWPORT AT A TIME (2026-10-13, BRP78). A bulk action that removes every fixture in one press
    cannot be walked at both viewports in one pass: the first viewport's press leaves the second nothing to act on. So it
    is walked per viewport (`prep --viewport`), the fixtures re-seeded between, and each part recorded as
    <id>__<viewport>. The parts merge into <id>.json / <id>.records.json ONLY when both exist and each was walked as THIS
    row's cast under THIS drift - the merge combines two real walks, it never fills a viewport nobody walked.
    Returns '' when merged (or nothing to merge), else why the parts were refused."""
    d = os.path.join('.tmp', 'w4_steps')
    parts = {v: (os.path.join(d, '%s__%s.json' % (a['id'], v)), os.path.join(d, '%s__%s.records.json' % (a['id'], v)))
             for v in VIEWPORT_SIZES}
    have = {v: p for v, p in parts.items() if os.path.exists(p[0]) and os.path.exists(p[1])}
    if not have:
        return ''
    whole = os.path.join(d, '%s.records.json' % a['id'])
    if os.path.exists(whole) and os.path.getmtime(whole) > max(os.path.getmtime(p[1]) for p in have.values()):
        return ''                         # a whole walk newer than every part: the parts are history, keep the walk
    if len(have) < len(VIEWPORT_SIZES):
        return 'walked one viewport at a time and only %s is on disk' % ', '.join(sorted(have))
    steps, merged = [], None
    for v, (sp, rp) in sorted(have.items()):
        rec = json.load(io.open(rp, encoding='utf-8'))
        if (rec.get('cast'), rec.get('stored'), rec.get('drifted')) != (a['cast'], a['stored'], a['drifted']):
            return 'the %s part was walked as %s / "%s" -> "%s", not as this row\'s cast' % (
                v, rec.get('cast'), rec.get('stored'), rec.get('drifted'))
        if v not in (rec.get('viewports') or {}):
            return 'the %s part holds no %s record' % (v, v)
        steps += json.load(io.open(sp, encoding='utf-8')) or []
        if merged is None:
            merged = dict(rec, viewports={})
        merged['viewports'][v] = rec['viewports'][v]
    io.open(os.path.join(d, '%s.json' % a['id']), 'w', encoding='utf-8', newline='\n').write(
        json.dumps(steps, indent=1, ensure_ascii=False))
    io.open(os.path.join(d, '%s.records.json' % a['id']), 'w', encoding='utf-8', newline='\n').write(
        json.dumps(merged, indent=1, ensure_ascii=False))
    return ''


def cmd_prep(ids, n, viewport=None):
    rows = open_brp('A') + open_brp('C')
    if ids:
        rows = [t for t in rows if t['id'] in ids]
    out, skipped = [], []
    for t in rows:
        if len(out) >= n:
            break
        r, why = reading_for(t)
        if not r:
            skipped.append((t['id'], why)); continue
        b = t.get('brp') or {}
        pages = list(t.get('pages') or [])
        out.append({'id': t['id'], 'page': b.get('page'), 'table': b.get('table'), 'pages': pages,
                    'cast': r['cast'], 'user': r['user'], 'pass': 'test1234', 'stored': r['cast'], 'drifted': r['drifted'],
                    'postgres': r, 'actions': ACTIONS.get(t['id'], []), 'write': WRITES.get(t['id'])})
        if viewport:
            out[-1]['post_id'] = '%s__%s' % (t['id'], viewport)
    doc = {'rows': out}
    if viewport:
        doc['viewports'] = [VIEWPORT_SIZES[viewport]]
    io.open(ARGS, 'w', encoding='utf-8', newline='\n').write(json.dumps(doc, ensure_ascii=False, indent=1))
    for a in out:
        p = a['postgres']
        print('armed %s %s.%s as %s (%s): %s by identity, %d by name, %s by "%s"%s'
              % (a['id'], a['page'], a['table'], a['cast'], a['user'], p['byIdentity'], p['byName'], p['byDrifted'], a['drifted'],
                 (', %s through RLS as the person' % p.get('rls')) if p.get('cls') == 'C' else ''))
    for rid, why in skipped:
        print('skipped %s: %s' % (rid, why))
    print('walk: browser_run_code_unsafe { filename: tools/brp_drift_walk.js }')


def judge(a, rec):
    """'' when the row holds at both viewports, else why it is held"""
    p = a['postgres']
    why = []
    if p.get('cls') == 'C':
        # class C: the name is the only key, so the drift must empty a name read while RLS still returns the
        # person's rows - the scoping the page now relies on instead of a client filter
        if not (p['byName'] > 0 and p['byDrifted'] == 0 and (p.get('rls') or 0) > 0):
            why.append('postgres: %s by name, %s by the drifted name, %s through RLS as the person' % (p['byName'], p['byDrifted'], p.get('rls')))
    elif not (p['byIdentity'] > 0 and p['byDrifted'] == 0):
        why.append('postgres: the drift is not real for this cast (%s by identity, %s by the drifted name)' % (p['byIdentity'], p['byDrifted']))
    vps = rec.get('viewports') or {}
    for vname in ('phone-390', 'desktop-1280'):
        v = vps.get(vname)
        if not v:
            why.append('%s: not walked' % vname); continue
        if v.get('problems'):
            why.append('%s: %s' % (vname, '; '.join(v['problems'])[:200]))
        if not v.get('signedIn'):
            why.append('%s: not signed in - nothing this viewport read describes the person' % vname); continue
        if a.get('write'):
            w = a['write']
            ws = [x for x in (v.get('writes') or []) if x['method'] == w['method']]
            wst = [x for x in ws if x['phase'] == 'stored']
            wdr = [x for x in ws if x['phase'] == 'drifted']
            need = w.get('phases') or ['stored', 'drifted']
            for key, ph, xs in (('stored', 'the stored name', wst), ('drifted', 'the drift', wdr)):
                if key in need and not xs:
                    why.append('%s: no %s of %s under %s after pressing %s' % (vname, w['method'], a['table'], ph, _actions_said(a['actions'])))
            if any(x['status'] >= 400 for x in ws):
                why.append('%s: a %s of %s failed (%s)' % (vname, w['method'], a['table'], sorted({x['status'] for x in ws if x['status'] >= 400})))
            # the defect is a write that asks by NAME ALONE. A write carrying the identity holds by its own filter; one
            # carrying neither (the BRP-C fix: the name filter removed, row-level security's auth_uid = auth.uid()
            # scoping it) holds by the policy - and either way the fixture count in postgres below is the proof
            if [x for x in wdr if x['byName'] and not x['byIdentity']]:
                why.append('%s: the drifted %s asked by name alone: %s' % (vname, w['method'], [x['q'] for x in wdr if x['byName'] and not x['byIdentity']][:2]))
            continue
        reads = v.get('reads') or []
        st = [x for x in reads if x['phase'] == 'stored']
        dr = [x for x in reads if x['phase'] == 'drifted']
        if not st:
            if a.get('actions'):
                why.append('%s: the page made no read of %s even after pressing %s' % (vname, a['table'], _actions_said(a['actions'])))
            else:
                why.append('%s: the page made no read of %s on load - the site is behind an action this walk does not take' % (vname, a['table']))
            continue
        if any(x['status'] >= 400 for x in st + dr):
            why.append('%s: a read of %s failed (%s)' % (vname, a['table'], sorted({x['status'] for x in st + dr if x['status'] >= 400})))
        if sum(x['n'] or 0 for x in dr) < sum(x['n'] or 0 for x in st):
            why.append('%s: rows shrank under the drift (%d -> %d)' % (vname, sum(x['n'] or 0 for x in st), sum(x['n'] or 0 for x in dr)))
        if [x for x in dr if x['byName'] and not x['byIdentity']]:
            why.append('%s: a read asked by name alone under the drift: %s' % (vname, [x['q'] for x in dr if x['byName'] and not x['byIdentity']][:2]))
        if (v.get('drifted') or {}).get('removed'):
            why.append('%s: a "you were removed" notice appeared under the drift' % vname)
    if a.get('write'):
        left = fixture_left(a)
        if left != 0:
            why.append('postgres: %s fixture row(s) still present after the walk - a delete matched nothing' % left)
    return '; '.join(why)


def fixture_left(a):
    """the marked fixture rows of a write row still in the table (None when postgres cannot say)"""
    rc, out, _ = psql("select count(*) from public.%s where %s;" % (a['table'], a['write']['fixture']))
    return int(out) if rc == 0 and out.strip().isdigit() else None


def basis_for_write(a, rec, ratchet):
    p, w = a['postgres'], a['write']
    parts = []
    for vname in ('phone-390', 'desktop-1280'):
        v = (rec.get('viewports') or {}).get(vname) or {}
        ws = [x for x in (v.get('writes') or []) if x['method'] == w['method']]
        wst = [x for x in ws if x['phase'] == 'stored']
        wdr = [x for x in ws if x['phase'] == 'drifted']
        parts.append('%s: %d %s(s) under the stored name (status %s) and %d under the drift (status %s), the drifted one '
                     'filtered %s' % (vname, len(wst), w['method'], sorted({x['status'] for x in wst}), len(wdr),
                                      sorted({x['status'] for x in wdr}), (wdr[0]['q'][:150] if wdr else '-')))
    drifted_only = (w.get('phases') or ['stored', 'drifted']) == ['drifted']
    split = all(os.path.exists(os.path.join('.tmp', 'w4_steps', '%s__%s.records.json' % (a['id'], v))) for v in VIEWPORT_SIZES)
    dws = [x for v in ((rec.get('viewports') or {}).values()) for x in (v.get('writes') or [])
           if x['method'] == w['method'] and x['phase'] == 'drifted']
    how = (('on %s the walk opened the view under the stored name WITHOUT pressing (one press removes every fixture), '
            'then drifted the display name ONE character on the device (localStorage wh_last_worker "%s" -> "%s"), '
            'reloaded and pressed %s' % (a['page'], a['stored'], a['drifted'], _actions_said(a['actions'])))
           if drifted_only else
           ('on %s the walk opened a marked fixture row (seeded for this walk, one per viewport and phase) and pressed %s - '
            'once under the stored name, then again after the display name was drifted ONE character on the device '
            '(localStorage wh_last_worker "%s" -> "%s")' % (a['page'], _actions_said(a['actions']), a['stored'], a['drifted'])))
    if split:
        how += ('; walked one viewport at a time with the fixtures re-seeded between, each part recorded as this cast '
                'under this drift and merged only after both matched')
    why_holds = ('its guard carries the identity' if dws and all(x['byIdentity'] for x in dws) else
                 'its request carries no name at all - row-level security (auth_uid = auth.uid()) scopes it'
                 if dws and not any(x['byName'] for x in dws) else 'no drifted write asked by name alone')
    return ('BRP drift walk, a WRITE site: signed in through the wall as %s (%s, a seeded local worker of %s) and walked %s; '
            '%s. %s. Postgres (docker exec psql) after the walk: %s fixture row(s) remain, so every %s removed its rows - '
            'PostgREST answers 204 to a delete that matched nothing, so the count, not the status, is the proof. Before the '
            'walk the cast held %d row(s) by identity (auth_uid), %d by the stored name and %d by the drifted name - what a '
            'name-guarded %s would have matched, so the reproduction is real and it FAILS on this page because %s. The '
            'site this row names (%s when it was seeded) is held statically by gate %s: re-run %s, it reads %d class-A '
            'site(s) in the live source (floor 0).'
            % (a['cast'], a['user'], p['hive'], ' -> '.join(a['pages']), how, '; '.join(parts), fixture_left(a),
               w['method'], p['byIdentity'], p['byName'], p['byDrifted'], w['method'], why_holds, site_of(a['id']), GATE,
               ratchet[2], ratchet[1]))


def ratchet_reading():
    """the bug-repro ratchet's report, re-run when it is not from today: (ok, class A count, generated)"""
    rp = 'bug_repro_ratchet_report.json'
    today = time.strftime('%Y-%m-%d')
    try:
        rep = json.load(io.open(rp, encoding='utf-8'))
    except Exception:
        rep = {}
    if not str(rep.get('generated', '')).startswith(today):
        subprocess.run([sys.executable, '-B', 'validate_bug_repro_ratchet.py'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
        rep = json.load(io.open(rp, encoding='utf-8'))
    # the relations the inventory still counts as class C (no identity column): a class-C row banks only when its
    # own table is not among them
    r = subprocess.run([sys.executable, '-B', 'tools/bug_repro_inventory.py', '--json'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    try:
        c_tables = {s['table'] for s in json.loads(r.stdout) if s.get('cls') == 'C'}
    except Exception:
        c_tables = {'(the inventory did not run)'}
    return (bool(rep.get('ok')), int((rep.get('by_class') or {}).get('A', 0)), str(rep.get('generated', ''))[:19],
            c_tables)


def site_of(rid):
    reg = json.load(io.open('trajectory_registry.json', encoding='utf-8'))['trajectories']
    b = next((t.get('brp') or {} for t in reg if t['id'] == rid), {})
    return '%s:%s' % (b.get('page'), b.get('line'))


def basis_for(a, rec, ratchet):
    p = a['postgres']
    parts = []
    held_by = []
    for vname in ('phone-390', 'desktop-1280'):
        v = (rec.get('viewports') or {}).get(vname) or {}
        reads = v.get('reads') or []
        st = [x for x in reads if x['phase'] == 'stored']
        dr = [x for x in reads if x['phase'] == 'drifted']
        ident = sorted({x['q'][:120] for x in dr if x['byIdentity']})[:1]
        unscoped = sorted({x['q'][:120] for x in dr if not x['byIdentity'] and not x['byName']})[:1]
        # ★SAY WHICH KIND OF READ HELD (2026-10-12, BRP39): a read scoped by NEITHER the name nor the identity (a
        # hive-wide read) cannot be reached by the drift at all - true, but it is not "the read carries the identity"
        parts.append('%s: %d read(s) of %s returned %d row(s) under the stored name and %d read(s) returned %d under the drift%s'
                     % (vname, len(st), a['table'], sum(x['n'] or 0 for x in st), len(dr), sum(x['n'] or 0 for x in dr),
                        (', the drifted read asking by identity (%s)' % ident[0]) if ident else
                        ((', the read scoped by neither the name nor the identity (%s), so the drift cannot reach it' % unscoped[0]) if unscoped else '')))
        held_by.append('identity' if ident else 'unscoped')
    if p.get('cls') == 'C':
        return ('BRP-C drift walk: %s carries NO identity column, so ownership is only expressible as a name; the fix '
                'removed the page\'s client name filter and leans on row-level security. Signed in through the wall as %s '
                '(%s, a seeded local worker of %s) and walked %s; on %s the display name was drifted ONE character on the '
                'device (localStorage wh_last_worker "%s" -> "%s", nothing written) and the page reloaded. %s. No read asked '
                'by name and no removal notice appeared. Postgres (docker exec psql) for the same person and table: %d '
                'row(s) by the stored name, %d by the drifted name - what a name-filtered read would have shown - and, '
                'impersonated as the person in a rolled-back transaction (role authenticated, jwt sub = their auth uid), '
                'row-level security returns %s row(s) of %s: the scoping the page now relies on. The reproduction FAILS on '
                'this page because its read no longer asks by name. The bug-repro inventory, re-run %s, still counts '
                'class-C site(s) only on %s - this row\'s %s (%s when seeded) is not among them; held by gate %s.'
                % (a['table'], a['cast'], a['user'], p['hive'], ' -> '.join(a['pages']), a['page'], a['stored'], a['drifted'],
                   '; '.join(parts), p['byName'], p['byDrifted'], p.get('rls'), a['table'], ratchet[2],
                   ', '.join(sorted(ratchet[3])) or 'no relation', a['table'], site_of(a['id']), GATE))
    pre = ('This row was seeded class C - %s carried no identity column, so ownership was only a name; the class-C fix\'s '
           'migration has since given it auth_uid, bound on insert, so it is walked and judged as class A. ' % a['table']
           ) if p.get('migrated') else ''
    pressed = (' The read sits behind a press, so on %s the walk pressed %s - once under the stored name and again after '
               'the drift.' % (a['page'], _actions_said(a['actions']))) if a.get('actions') else ''
    # the template is ONE string before % applies: `%` binds tighter than `+`, so the pieces are grouped first
    return pre + (('BRP drift walk: signed in through the wall as %s (%s, a seeded local worker of %s) and walked %s; on %s the '
            'display name was drifted ONE character on the device (localStorage wh_last_worker "%s" -> "%s", nothing '
            'written) and the page reloaded.' + pressed.replace('%', '%%') + ' %s. No read asked by name alone and no removal notice appeared. Postgres '
            '(docker exec psql) for the same person and table: %d row(s) by identity (auth_uid), %d by the stored name, '
            '%d by the drifted name - the count a name-only read would have shown, so the reproduction is real and it '
            'FAILS on this page %s. The site this row names (%s when it was seeded) '
            'is held statically by gate %s: re-run %s, it reads %d class-A site(s) in the live source (floor 0) - no read '
            'anywhere asks for an identity-carrying table by name alone. This walk is the runtime half, on the surface.')
            % (a['cast'], a['user'], p['hive'], ' -> '.join(a['pages']), a['page'], a['stored'], a['drifted'],
               '; '.join(parts), p['byIdentity'], p['byName'], p['byDrifted'],
               ('because its read carries the identity' if all(h == 'identity' for h in held_by) else
                'because its read of the table on load does not ask by name at all' if all(h == 'unscoped' for h in held_by) else
                'because no read of the table asks by name alone'),
               site_of(a['id']), GATE, ratchet[2], ratchet[1]))


def cmd_bank():
    A = json.load(io.open(ARGS, encoding='utf-8'))
    entries, held = [], []
    ratchet = ratchet_reading()
    if not ratchet[0] or ratchet[1] != 0:
        print('REFUSED: gate %s does not hold (ok=%s, class A=%s at %s) - no BRP-A row banks while a site is open'
              % (GATE, ratchet[0], ratchet[1], ratchet[2]))
        raise SystemExit(1)
    for a in A['rows']:
        rid = a['id']
        sp = os.path.join('.tmp', 'w4_steps', '%s.json' % rid)
        rp = os.path.join('.tmp', 'w4_steps', '%s.records.json' % rid)
        refused = merge_parts(a)
        if refused:
            held.append((rid, refused)); continue
        if not (os.path.exists(sp) and os.path.exists(rp)) or os.path.getmtime(rp) < os.path.getmtime(ARGS):
            held.append((rid, 'no walk on disk newer than the args')); continue
        rec = json.load(io.open(rp, encoding='utf-8'))
        why = judge(a, rec)
        if not why and a['postgres'].get('cls') == 'C' and (a['table'] in ratchet[3] or '(the inventory did not run)' in ratchet[3]):
            why = 'the bug-repro inventory still counts %s as an open class-C site' % a['table']
        if why:
            held.append((rid, why)); continue
        note = basis_for_write(a, rec, ratchet) if a.get('write') else basis_for(a, rec, ratchet)
        walked = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(os.path.getmtime(rp)))
        r = subprocess.run([sys.executable, 'tools/record_mcp_walk.py', '--id', rid, '--walked-at', walked,
                            '--instrument', 'playwright-mcp + postgres-mcp', '--cast', a['cast'], '--as-persona', 'returner',
                            '--steps', sp, '--note', note[:1800],
                            '--witness', ('postgres: %s by name, %s by the drifted name, %s through RLS as the person' % (
                                a['postgres']['byName'], a['postgres']['byDrifted'], a['postgres'].get('rls'))
                                if a['postgres'].get('cls') == 'C' else
                                'postgres: %s by identity, %s by name, %s by the drifted name%s' % (
                                a['postgres']['byIdentity'], a['postgres']['byName'], a['postgres']['byDrifted'],
                                (', %s fixture row(s) left after the walk' % fixture_left(a)) if a.get('write') else ''))],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            held.append((rid, 'record_mcp_walk refused: ' + (((r.stdout or '') + (r.stderr or '')).strip().splitlines() or [''])[-1][:200]))
            continue
        entries.append({'ids': rid, 'status': 'locking', 'pct': 60, 'gate': [GATE],
                        'basis': 'WALKED LIVE %s via playwright-mcp + postgres-mcp (tools/brp_drift_walk.js, tools/record_mcp_walk.py) - %s'
                                 % (walked[:10], note)})
    if entries:
        bf = os.path.join('.tmp', 'brp_bank.json')
        io.open(bf, 'w', encoding='utf-8', newline='\n').write(json.dumps(entries, ensure_ascii=False, indent=1))
        r = subprocess.run([sys.executable, 'tools/advance_trajectory.py', '--batch', bf], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        out = (r.stdout or '') + (r.stderr or '')
        print('advance:', ([l for l in out.splitlines() if 'advanced' in l or 'FAIL' in l or 'refus' in l] or [out.strip()[-300:]])[-1][:240])
    print('BANKED %d, HELD %d' % (len(entries), len(held)))
    for rid, why in held:
        print('  HELD %s: %s' % (rid, why))


if __name__ == '__main__':
    av = sys.argv[1:]
    if not av or av[0] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    if av[0] == '--list':
        cmd_list(av[1] if len(av) > 1 else 'A')
    elif av[0] == 'prep':
        n = 4
        if '--n' in av:
            n = int(av[av.index('--n') + 1]); av = [x for i, x in enumerate(av) if x != '--n' and (i == 0 or av[i - 1] != '--n')]
        vp = None
        if '--viewport' in av:
            vp = av[av.index('--viewport') + 1]
            if vp not in VIEWPORT_SIZES:
                print('--viewport is one of %s' % ', '.join(VIEWPORT_SIZES)); raise SystemExit(2)
            av = [x for i, x in enumerate(av) if x != '--viewport' and (i == 0 or av[i - 1] != '--viewport')]
        cmd_prep(set(av[1:]), n, vp)
    elif av[0] == 'bank':
        cmd_bank()
    else:
        print(__doc__); raise SystemExit(2)
