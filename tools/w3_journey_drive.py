#!/usr/bin/env python3
"""w3_journey_drive.py - drive tools/w3_journey_walk.js (a W3-JN whole journey through the Playwright MCP) (2026-10-13).

The walker runs the retracted prover's own journey code inside the MCP's browser, and answers every database read the
prover makes from a CACHE whose values were read through the POSTGRES MCP (`.tmp/w3_args.json` -> psql). This drive is
the bookkeeping around that, so nothing is re-typed that a tool already holds:

  prep collect <id> [<id> ...]   args for a batch COLLECT pass: the walker casts every story and lists the SQL it needs
  need                           the needed SQL (from .tmp/w4_steps/<id>-collect.records.json) NOT yet in the cache,
                                 numbered - each is then asked through the postgres MCP, exactly as printed
  fill <answers.json>            store the answers: {"<n>": "<psql -tA text>" | null} keyed by the number `need` printed;
                                 null records a statement postgres refused (the prover's own psql answers null on error)
  prep walk <id>                 args for the WALK of one row, carrying the whole cache

The SQL text is the cache key, so it is always taken from the walker's own list, never typed. A value is the text
`psql -tA` would print: rows on new lines, columns joined by '|'. The walk then posts its steps as <id>, and the row is
recorded with tools/record_mcp_walk.py and banked with tools/bank_journey_walk.py, like every other W3-JN row.
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = os.path.join(ROOT, '.tmp', 'w3_args.json')
STEPS = os.path.join(ROOT, '.tmp', 'w4_steps')
NEED = os.path.join(ROOT, '.tmp', 'w3_need.json')


def _load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except Exception:
        return default


def _save(path, doc):
    tmp = path + '.tmp'
    io.open(tmp, 'w', encoding='utf-8', newline='\n').write(json.dumps(doc, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


def _files():
    """the pages and scripts the prover reads: every production page at the root, plus its three shared scripts"""
    keep = ['nav-hub.js', 'utils.js', 'wh-i18n-lite.js']
    pages = sorted(f for f in os.listdir(ROOT) if f.endswith('.html') and not f.endswith('-test.html') and '.backup' not in f)
    return keep + pages


def _rows(ids):
    reg = _load(os.path.join(ROOT, 'trajectory_registry.json'), {}).get('trajectories', [])
    rows = [t for t in reg if t['id'] in ids]
    missing = sorted(set(ids) - {t['id'] for t in rows})
    if missing:
        raise SystemExit('no such row(s): %s' % ', '.join(missing))
    return rows


def cmd_prep(mode, ids):
    old = _load(ARGS, {}) or {}
    doc = {'id': ids[0] if mode == 'walk' else 'JNBATCH', 'mode': mode, 'psql': old.get('psql') or {},
           'files': _files(), 'rows': _rows(ids)}
    if mode == 'collect':
        doc['ids'] = ids
    elif len(ids) != 1:
        raise SystemExit('a walk is one row')
    _save(ARGS, doc)
    print('%s args: %s (%d cached answer(s), %d file(s))' % (mode, ', '.join(ids), len(doc['psql']), len(doc['files'])))
    print('walk: browser_run_code_unsafe { filename: tools/w3_journey_walk.js }')


def cmd_need():
    doc = _load(ARGS, {}) or {}
    rec = _load(os.path.join(STEPS, '%s-collect.records.json' % doc.get('id', 'JNBATCH')), {}) or {}
    cache = doc.get('psql') or {}
    todo = [s for s in (rec.get('need') or []) if s not in cache]
    _save(NEED, todo)
    for i, s in enumerate(todo):
        print('[%d] %s' % (i, s))
    print('%d statement(s) to ask through the postgres MCP' % len(todo))


def cmd_fill(path):
    doc = _load(ARGS, {}) or {}
    todo = _load(NEED, []) or []
    answers = _load(path, None)
    if not isinstance(answers, dict):
        raise SystemExit('answers must be a JSON object {"<n>": text | null}')
    cache = doc.setdefault('psql', {})
    n = 0
    for k, v in answers.items():
        i = int(k)
        if i >= len(todo):
            raise SystemExit('answer %d has no statement (the need list holds %d)' % (i, len(todo)))
        if v is not None and not isinstance(v, str):
            raise SystemExit('answer %d is neither text nor null' % i)
        cache[todo[i]] = v
        n += 1
    _save(ARGS, doc)
    print('stored %d answer(s); the cache holds %d' % (n, len(cache)))


CHAIN_UNREAD = 'the chain could not be READ (the database did not answer)'


def cmd_complete(rid, effect):
    """★A STORY THAT PERFORMS AN ACTION IS JUDGED ON WHAT THE ACTION LEFT, READ AFTER THE WALK (2026-10-13, J13).
    The walker defers every statement about the walk's own mark once its browser has closed (it cannot be answered
    from a cache read before the walk). `effect` is the count the driver read through the POSTGRES MCP after the
    walk, by the exact deferred statement. The story holds only when that count is >= 1 AND the walk has no problem
    left once the deferred read's own placeholder ("the chain could not be READ") is set aside. The deferred reversal
    - the prover's own delete of the walk's mark - is then run here (the postgres MCP is read-only), and the count it
    removed is written beside the walk, so the receipt can say what was done and undone."""
    import subprocess
    rp = os.path.join(STEPS, '%s.records.json' % rid)
    rec = _load(rp, None)
    if not rec:
        raise SystemExit('no walk record for %s' % rid)
    res = rec.get('result') or {}
    deferred = res.get('deferred') or []
    reads = [s for s in deferred if not s.lstrip().lower().startswith('with d as (delete')]
    deletes = [s for s in deferred if s.lstrip().lower().startswith('with d as (delete')]
    if not reads:
        raise SystemExit('%s deferred no post-walk read - nothing to complete (judge it as walked)' % rid)
    left = [p for p in (res.get('problems') or []) if not p.startswith(CHAIN_UNREAD)]
    why = []
    if effect < 1:
        why.append('the post-walk read found %d row(s) carrying the walk mark - the action left nothing' % effect)
    if left:
        why.append('the walk itself has problems: ' + '; '.join(left)[:300])
    removed = None
    for sql in deletes:
        r = subprocess.run(['docker', 'exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-tA', '-v',
                            'ON_ERROR_STOP=1'], input=sql, capture_output=True, text=True, encoding='utf-8', errors='replace')
        nums = [ln for ln in (r.stdout or '').split() if ln.isdigit()]
        removed = (removed or 0) + (int(nums[-1]) if r.returncode == 0 and nums else 0)
        if r.returncode != 0:
            why.append('the reversal failed: ' + (r.stderr or '')[-160:])
    rec['completed'] = {'effect': effect, 'effect_read': 'postgres MCP, after the walk, by the deferred statement',
                        'reversed': removed, 'holds': not why, 'why': why}
    _save(rp, rec)
    print('%s %s - effect %d (read after the walk), reversed %s; %s' % (
        rid, 'HOLDS' if not why else 'HELD', effect, removed, '; '.join(why) or 'no problem left'))


if __name__ == '__main__':
    av = sys.argv[1:]
    if len(av) >= 3 and av[0] == 'prep' and av[1] in ('collect', 'walk'):
        cmd_prep(av[1], av[2:])
    elif av[:1] == ['need']:
        cmd_need()
    elif len(av) == 2 and av[0] == 'fill':
        cmd_fill(av[1])
    elif len(av) == 3 and av[0] == 'complete':
        cmd_complete(av[1], int(av[2]))
    else:
        print(__doc__)
        raise SystemExit(2)
