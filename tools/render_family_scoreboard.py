"""
render_family_scoreboard.py — regenerate FAMILY_UFAI_ROADMAP.md §16/§17 tables
from family_rubric_scoreboard.json (written by tools/family_rubric_sweep.mjs).

The §16/§17 boards were hand-built once (2026-07-15); every lens or page change
made them stale. This renders the SAME tables from the sweep's JSON so the
roadmap's scoreboard is always one command away from the measured truth.

USAGE:  python tools/render_family_scoreboard.py           # print to stdout
        python tools/render_family_scoreboard.py --write   # patch the roadmap in place
"""
import json
import re
import sys
from datetime import date

JSON_PATH = 'family_rubric_scoreboard.json'
ROADMAP = 'FAMILY_UFAI_ROADMAP.md'

DIM_NAMES = {}  # filled from the sweep JSON's perDim names


def bucket(pages):
    b = {'>=95': [], '90-94': [], '85-89': [], '80-84': [], '<80': []}
    for name, o in sorted(pages.items(), key=lambda kv: -(kv[1].get('overall') or 0)):
        v = o.get('overall')
        if v is None:
            continue
        label = f"{name.replace('.html', '')} **{v}**" if v >= 95 or v < 80 else f"{name.replace('.html', '')} {v}"
        key = '>=95' if v >= 95 else '90-94' if v >= 90 else '85-89' if v >= 85 else '80-84' if v >= 80 else '<80'
        b[key].append(label)
    return b


def render(d):
    s = d['summary']
    pages = d['pages']
    per = d['perDim']
    b = bucket(pages)
    lines = []
    lines.append(f"## 16. LIVE SCOREBOARD ({date.today().isoformat()} sweep) — mean **{s['mean']}** · "
                 f"{s['ge90']} pages ≥90 · {s['ge85']} ≥85 · {s['pageErrors']} errors")
    lines.append('')
    lines.append('| ≥95 | 90–94 | 85–89 | 80–84 | <80 |')
    lines.append('|---|---|---|---|---|')
    lines.append('| ' + ' | '.join(' · '.join(b[k]) or '—' for k in ['>=95', '90-94', '85-89', '80-84', '<80']) + ' |')
    lines.append('')
    lines.append(f"_Measured by `tools/family_rubric_sweep.mjs` (identity {s.get('identity','')}, mobile F1/K2 pass)._")
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append(f"## 17. THE COMPLETE PER-DIM BOARD ({date.today().isoformat()} sweep) — every class, every dim")
    lines.append('')
    lines.append('| Dim | Mean | Green | Fail | N/A | Judged | Failing pages |')
    lines.append('|---|---|---|---|---|---|---|')
    for dim in sorted(per):
        a = per[dim]
        mean = f"**{a['mean']}%**" if a['mean'] == 100 else (f"{a['mean']}%" if a['mean'] is not None else '–')
        fp = ', '.join(a['failPages'][:6]) + (' …' if len(a['failPages']) > 6 else '')
        lines.append(f"| {dim} {a.get('name','')} | {mean} | {a['green']} | {a['fail']} | {a['na']} | {a['judged']} | {fp} |")
    lines.append('')
    return '\n'.join(lines)


def main():
    d = json.load(open(JSON_PATH, encoding='utf-8'))
    out = render(d)
    if '--write' in sys.argv:
        md = open(ROADMAP, encoding='utf-8').read()
        # replace from '## 16.' to end of file's §17 table (the boards are the last two sections)
        m = re.search(r'^## 16\..*', md, re.M | re.S)
        if not m:
            print('could not find §16 anchor — printing instead')
            print(out)
            return
        md = md[:m.start()] + out + '\n'
        open(ROADMAP, 'w', encoding='utf-8').write(md)
        print(f'patched {ROADMAP} §16/§17 from {JSON_PATH}')
    else:
        print(out)


if __name__ == '__main__':
    main()
