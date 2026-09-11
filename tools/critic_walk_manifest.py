# -*- coding: utf-8 -*-
"""critic_walk_manifest.py - resolve each PENDING critic walk to a concrete cast, for batch walking.

Hand-walking the critic queue is ~12 tool calls per walk; 128 walks is infeasible in a session and
wasteful of tokens. This is the READ-ONLY first slice of a batch runner: it enumerates the distinct
in-motion walks the way tools/critic_walk_groups.py does (cell + pages + language + condition + moment;
the vertical does NOT split a walk), and for each one resolves the persona+vertical to a concrete
sign-in cast - an auth email + the real active hive_id - so a node runner can sign in, pin the hive
(the mis-pin lesson: set the hive from LIVE membership, never leave the previous persona's), set the
viewport, survey each page, and bank.

It writes a JSON manifest and BANKS NOTHING. Restricted by default to the tractable subset
(condition=normal, moment=present) - the condition walks (offline-3g/dependency-down/release-mid-way)
and moment walks (month-3/year-2) need browser network-emulation / the 5-year seeder and are out of
scope for the first runner.

Persona -> hive role, and vertical -> hive, are resolved against the LIVE db via docker psql (the
documented local substitute for the postgres MCP), so the cast is real, not guessed.
"""
import json
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRIT = os.path.join(HERE, 'critic_registry.json')
TRAJ = os.path.join(HERE, 'trajectory_registry.json')

# persona (from the cell) -> the hive_members.role to look for. solo-owner / anon / oversight are
# special (no ordinary hive membership); handled below.
PERSONA_ROLE = {
    'worker': 'worker',
    'supervisor': 'supervisor',
    'fleet-supervisor': 'supervisor',
    'new-user': 'supervisor',      # the onboarding cast creates the hive (J1 story)
    'returner': 'worker',
    'buyer': 'worker',             # a buyer is any hive member purchasing
    'machine-client': 'supervisor',
    'adversary': 'worker',
}
SOLO_PERSONAS = {'solo-owner', 'solo-tech', 'solo-rider'}
NOHIVE_PERSONAS = {'oversight', 'anon'} | SOLO_PERSONAS


def psql(sql):
    r = subprocess.run(['docker', 'exec', 'supabase_db_workhive', 'psql', '-U', 'postgres',
                        '-d', 'postgres', '-tA', '-c', sql],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return [ln for ln in (r.stdout or '').splitlines() if ln.strip()]


def rows(path):
    d = json.load(io.open(path, encoding='utf-8'))
    return d if isinstance(d, list) else d.get('rows', d.get('trajectories', []))


def main():
    only_normal = '--all' not in sys.argv
    crit = rows(CRIT)
    tmap = {x['id']: x for x in rows(TRAJ)}

    # cache: vertical(hive name) -> hive_id ; (hive_id, role) -> email
    hive_by_name = {}
    for ln in psql("SELECT id, name FROM hives;"):
        hid, name = ln.split('|', 1)
        hive_by_name[name.strip()] = hid.strip()
    # solo personas -> a fixed solo email
    solo_email = {}
    for ln in psql("SELECT email, raw_user_meta_data->>'worker_name' FROM auth.users "
                   "WHERE raw_user_meta_data->>'seed'='solo-persona-seed';"):
        parts = ln.split('|')
        solo_email[parts[0].strip()] = parts[1].strip() if len(parts) > 1 else ''

    def member_of(hive_id, role):
        out = psql("SELECT u.email FROM hive_members m JOIN auth.users u ON u.id=m.auth_uid "
                   "WHERE m.hive_id='%s' AND m.role='%s' AND m.status='active' LIMIT 1;" % (hive_id, role))
        return out[0].strip() if out else None

    seen = {}
    for x in crit:
        if x.get('status') != 'pending':
            continue
        t = tmap.get(x['id'], {})
        j = t.get('journey', {}) or {}
        cond = j.get('condition') or 'normal'
        moment = j.get('moment') or 'present'
        lang = j.get('language') or 'en'
        if only_normal and (cond != 'normal' or moment != 'present'):
            continue
        cell = x.get('cell') or ''
        parts = cell.split('|')
        device = t.get('device') or (parts[0] if parts else '')
        persona = t.get('persona') or (parts[1] if len(parts) > 1 else '')
        pages = t.get('pages') or x.get('pages') or []
        vertical = j.get('vertical') or ''
        key = (cell, tuple(pages), lang, cond, moment)
        if key in seen:
            seen[key]['ids'].append(x['id'])
            continue
        # resolve the cast
        email = hive_id = None
        note = ''
        if persona in NOHIVE_PERSONAS:
            if persona in SOLO_PERSONAS:
                email = next(iter(solo_email), None)
                note = 'solo (no hive)'
            elif persona == 'oversight':
                note = 'oversight - admin cast, ROUTE-only'
            elif persona == 'anon':
                note = 'anon - signed out'
        else:
            role = PERSONA_ROLE.get(persona, 'worker')
            vkey = vertical.strip()
            hid = hive_by_name.get(vkey)
            # ★MALFORMED VERTICAL FALLBACK: some journey.vertical fields carry prose with the hive name
            # buried in it ("the the pm month of Lucena Pharmaceutical Mfg."). Exact-match misses those;
            # fall back to the longest known hive name that appears as a SUBSTRING of the vertical.
            if not hid:
                cand = sorted((n for n in hive_by_name if n and n in vkey), key=len, reverse=True)
                if cand:
                    hid = hive_by_name[cand[0]]
                    vertical = cand[0]
            if hid:
                email = member_of(hid, role) or member_of(hid, 'supervisor') or member_of(hid, 'worker')
                hive_id = hid
                note = '%s of %s' % (role, vertical)
            else:
                note = 'UNRESOLVED vertical: %r' % vertical
        seen[key] = {
            'ids': [x['id']], 'device': device, 'persona': persona, 'language': lang,
            'condition': cond, 'moment': moment, 'vertical': vertical, 'pages': list(pages),
            'email': email, 'hive_id': hive_id, 'note': note,
        }

    manifest = list(seen.values())
    resolved = [w for w in manifest if w['email'] or w['persona'] == 'anon']
    out_path = os.path.join(HERE, '.tmp', 'critic_walk_manifest.json')
    io.open(out_path, 'w', encoding='utf-8').write(json.dumps(manifest, indent=1, ensure_ascii=False))
    print('walks: %d  (resolved cast: %d, unresolved: %d)  -> %s'
          % (len(manifest), len(resolved), len(manifest) - len(resolved), out_path))
    from collections import Counter
    print('by device:', dict(Counter(w['device'] for w in manifest)))
    print('by persona:', dict(Counter(w['persona'] for w in manifest)))
    print('UNRESOLVED:')
    for w in manifest:
        if not (w['email'] or w['persona'] == 'anon'):
            print('  ', w['ids'][0], w['persona'], '|', w['note'])


if __name__ == '__main__':
    main()
