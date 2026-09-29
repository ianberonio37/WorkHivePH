#!/usr/bin/env python3
"""prove_calc_pages_match_engine.py - a calculator page must print what its engine computes (2026-09-16).

The 60 `/tools/<calc>/` pages are STATIC: their worked example was computed once, at build time, and baked into
the HTML in two places - the one-sentence lede ("... Design density = 6.12 mm/min, ...") and the result table
(`<td>Design density</td><td>6.12 mm/min</td>`). Nothing re-checks them afterwards. `validate_calc_pages.py`
validates the JSON-LD's structure and never looks at a number, so a page whose printed values have drifted from
the module that produced them passes every gate on the board.

That drift is not hypothetical. Four calculations were corrected in one day by the W4 design lens, and each one
changed what the page should say:

  * fire-sprinkler   a hazard class passed through a building-type lookup silently defaulted, and the page
                     published a Light Hazard design for an Ordinary Hazard Group 1 example - 4.08 mm/min where
                     the code requires 6.12, a system designed at two thirds of the density (W46383)
  * hoist-capacity   rope tension was divided by the number of rope parts without multiplying rope travel, so
                     the motor was sized at 1/n of the real duty - 3 HP for a 7.5 HP lift (W46408)
  * heat-exchanger   the example over-specified duty AND temperatures, and effectiveness came from unstated
                     flows, so 0.25 was printed where the page's own temperatures give 0.50 (W46403)
  * load-schedule    NEC 430.24's 125% motor allowance was charged twice, so demand read 30.5 kW against a
                     correct 26.75, with a panel power factor of 0.986 for loads at 0.9 and 0.85 (W46443)

Every one of those needed the page rewritten by hand alongside the module, and remembering to do both is exactly
the kind of step that does not happen ([[feedback_a_step_that_depends_on_remembering_does_not_happen]]). Twice in
that day a label was changed in the table and left stale in the lede, which is the same failure in miniature.

So this gate runs each calculator's module with the `example_inputs` its own CALC_DATA carries, builds the
headline rows with the generator's own `_headline_rows`, and requires the live page to state every one of them -
label, value AND unit - in BOTH places. It compares what the engine says now against what the page says now, so
it fails the moment either moves without the other, whichever way the drift runs.

  python tools/prove_calc_pages_match_engine.py --check
  python tools/prove_calc_pages_match_engine.py --self-test
"""
from __future__ import annotations

import html
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _rows_for(B, slug, data):
    """(label, value, unit) triples the engine produces for this calculator's own example."""
    r = B._run_calc(data)
    rows, missing = B._headline_rows(data, r)
    return rows, missing


def _states(page: str, label: str, value: str, unit: str) -> list[str]:
    """Which of the two renderings state this row; a page must do both."""
    where = []
    lede = "%s = %s%s" % (label, value, (" " + unit) if unit else "")
    cell = "<td>%s</td><td>%s%s</td>" % (html.escape(label), html.escape(str(value)),
                                         (" " + html.escape(unit)) if unit else "")
    if lede in page:
        where.append("lede")
    if cell in page:
        where.append("table")
    return where


def check(verbose: bool = True) -> int:
    import build_calc_pages as B

    fails, checked, skipped = [], 0, []
    for slug, data in sorted(B.CALC_DATA.items()):
        f = ROOT / "tools" / slug / "index.html"
        if not f.exists():
            skipped.append((slug, "no live page"))
            continue
        try:
            rows, missing = _rows_for(B, slug, data)
        except Exception as e:
            fails.append("%s: the engine could not run its own example - %s" % (slug, str(e)[:90]))
            continue
        if missing:
            skipped.append((slug, "engine did not return %s" % ", ".join(missing[:2])))
        page = io.open(f, encoding="utf-8").read()
        for label, value, unit in rows:
            where = _states(page, label, value, unit)
            if len(where) < 2:
                fails.append("%s: the page does not state %r = %s%s in the %s"
                             % (slug, label, value, (" " + unit) if unit else "",
                                " and ".join(x for x in ("lede", "table") if x not in where)))
            else:
                checked += 1

    if verbose:
        for s in fails:
            print("   - " + s)
        for slug, why in skipped[:4]:
            print("   skip %-34s %s" % (slug[:33], why))
    if fails:
        print("FAIL calc-pages-match-engine: %d printed value(s) disagree with the engine that produced them, "
              "across %d page(s)." % (len(fails), len({s.split(':')[0] for s in fails})))
        return 1
    print("PASS calc-pages-match-engine: %d printed value(s) across %d calculator page(s) match a fresh run of "
          "their own module, in both the lede and the result table." % (checked, len(B.CALC_DATA) - len(skipped)))
    return 0


def self_test() -> int:
    """A page whose printed value is edited must FAIL; restored, it must PASS."""
    import build_calc_pages as B

    slug = "bolt-torque-calculator"
    f = ROOT / "tools" / slug / "index.html"
    before = io.open(f, encoding="utf-8", newline="").read()
    rows, _m = _rows_for(B, slug, B.CALC_DATA[slug])
    label, value, unit = rows[0]
    cell = "<td>%s</td><td>%s %s</td>" % (html.escape(label), html.escape(value), html.escape(unit))
    if before.count(cell) != 1:
        print("SELF-TEST INCONCLUSIVE: could not find %r exactly once to perturb." % cell[:50])
        return 1
    bad = before.replace(cell, cell.replace(value, "999.9"), 1)
    try:
        io.open(f, "w", encoding="utf-8", newline="").write(bad)
        rc_bad = check(verbose=False)
    finally:
        io.open(f, "w", encoding="utf-8", newline="").write(before)
    rc_good = check(verbose=False)
    ok = (rc_bad == 1 and rc_good == 0)
    print("SELF-TEST %s: perturbed page -> %s, restored page -> %s"
          % ("PASS" if ok else "FAIL",
             "FAIL (correct)" if rc_bad else "PASS (WRONG - the gate has no teeth)",
             "PASS (correct)" if rc_good == 0 else "FAIL (WRONG)"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    raise SystemExit(check())
