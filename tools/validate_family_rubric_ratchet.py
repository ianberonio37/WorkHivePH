"""
validate_family_rubric_ratchet.py — F7: the family-rubric ADOPTION RATCHET.
================================================================================
FAMILY_UFAI_ROADMAP.md §3: "no phase is done on vibes; each lands a % and a
ratchet so it cannot seesaw back." This gate locks the whole-family scoreboard
(written by tools/family_rubric_sweep.mjs) forward-only:

  FAIL when, vs family_rubric_baseline.json:
    - family mean drops below baseline mean
    - any page drops more than 2 points below its baseline score
    - a dim that was 100% family-wide (green==measured pages) gains a fail

  --accept  writes the current scoreboard as the new baseline (auto-tightens).

Run AFTER a fresh full sweep (the runner overwrites the JSON; a --page run
writes a 1-page board — this gate refuses boards with < 30 pages so a partial
run can never become the baseline or a false verdict).

USAGE:  python tools/validate_family_rubric_ratchet.py           # gate
        python tools/validate_family_rubric_ratchet.py --accept  # ratchet
EXIT:   0 pass · 1 regression (or unusable board)
"""
import json
import os
import sys

BOARD = 'family_rubric_scoreboard.json'
BASELINE = 'family_rubric_baseline.json'
MIN_PAGES = 30          # refuse partial (--page) boards
PAGE_TOLERANCE = 2      # live-render jitter allowance per page


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    if not os.path.exists(BOARD):
        print(f'FAIL: {BOARD} missing — run tools/family_rubric_sweep.mjs first')
        return 1
    cur = load(BOARD)
    pages = {k: v.get('overall') for k, v in cur['pages'].items() if v.get('overall') is not None}
    if len(pages) < MIN_PAGES:
        print(f'FAIL: board has only {len(pages)} pages (a --page run?) — full sweep required')
        return 1

    if '--accept' in sys.argv or not os.path.exists(BASELINE):
        json.dump({'summary': cur['summary'], 'pages': pages,
                   'greenDims': sorted(d for d, a in cur['perDim'].items()
                                       if a['fail'] == 0 and a['green'] > 0)},
                  open(BASELINE, 'w', encoding='utf-8'), indent=1)
        print(f"BASELINE {'accepted' if '--accept' in sys.argv else 'created'}: "
              f"mean {cur['summary']['mean']} · >=90 {cur['summary']['ge90']} · {len(pages)} pages")
        return 0

    base = load(BASELINE)
    fails = []
    if (cur['summary']['mean'] or 0) < (base['summary']['mean'] or 0):
        fails.append(f"family mean regressed {base['summary']['mean']} -> {cur['summary']['mean']}")
    for pg, sc in base['pages'].items():
        now = pages.get(pg)
        if now is None:
            fails.append(f'{pg}: missing from board')
        elif now < sc - PAGE_TOLERANCE:
            fails.append(f'{pg}: {sc} -> {now}')
    for dim in base.get('greenDims', []):
        a = cur['perDim'].get(dim)
        if a and a['fail'] > 0:
            fails.append(f'{dim}: was 100% family-wide, now {a["fail"]} fail(s)')

    if fails:
        print('FAIL — family rubric regression (fix, or --accept if intentional):')
        for f_ in fails:
            print('  -', f_)
        return 1
    print(f"PASS — mean {cur['summary']['mean']} (baseline {base['summary']['mean']}), "
          f"{len(pages)} pages within tolerance, green dims held.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
