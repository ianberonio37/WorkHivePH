"""Bring every live calculator page's "Related calculators" list in line with the
generator, after ~W46330 fixed two defects in tools/build_calc_pages.py.

Why this sweep exists at all: build_calc_pages.py writes to
seo_assets/calc_pages_staging, NOT to tools/<slug>/index.html. Promoting that
staging directory is Ian's gate, so a generator fix alone changes nothing a reader
sees. The live pages are patched here, exactly as ~W46285 patched the skip link and
the <main> id on the same 60 files.

The two defects, both measured on the live pages during the audit walk of
tools/compressed-air-calculator/index.html (2026-09-20):

  1. ORPHANED FROM THEIR OWN FAMILY. `_siblings` returned `sibs[:2]` - the first two
     members of the discipline in CALC_DATA order. That is positional, not related,
     so every member past the second carried an IDENTICAL pair: 13 Electrical pages
     all pointed at wire-sizing + transformer-sizing, 12 Plumbing pages at pump-tdh
     + pipe-sizing, 8 HVAC pages at hvac-cooling-load + ventilation-ach. The
     consequence is the finding: 39 of the 60 calculators were never linked FROM any
     sibling block, so a reader who lands on one can reach the pillar but is never
     offered the neighbour that actually follows it, and a crawler walking internal
     links never reaches them from the family either.

  2. THE PILLAR LINK PRINTED TWICE. `rel` defaulted to PILLAR, so on 57 of 60 pages
     the same <ul> carried the pillar URL twice - same href, same anchor text,
     separated only by a "(pillar)" suffix on the first. Two list items, one
     destination, one name.

Both are fixed in the generator; this script makes the live pages agree with it.
The whole <ul> is rebuilt from CALC_DATA, so the sweep is idempotent by construction
and needs no marker comment: --check simply asserts the live block already equals
what the generator would emit.

    python tools/fix_calc_related_links.py --check
    python tools/fix_calc_related_links.py --apply
"""
from __future__ import annotations

import html
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location("_bcp", HERE / "build_calc_pages.py")
_bcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bcp)

CALC_DATA = _bcp.CALC_DATA
PILLAR = _bcp.PILLAR
_siblings = _bcp._siblings
e = html.escape  # the generator's own alias, local to _html_page

# the <ul> inside the Related section — the only thing this sweep owns
UL_RE = re.compile(
    r'(<section aria-labelledby="related">.*?<ul>)(.*?)(</ul>)', re.S)


def expected_items(slug: str, data: dict) -> str:
    """The <li> rows the generator emits for this page, in its exact formatting."""
    sibs = data.get("siblings") or _siblings(slug, data)
    rel = data.get("related_article")
    rows = [f'        <li><a href="{e(PILLAR[0])}">{e(PILLAR[1])}</a> (pillar)</li>']
    rows += [f'        <li><a href="{e(u)}">{e(t)}</a></li>' for u, t in sibs]
    if rel and rel[0] != PILLAR[0]:
        rows.append(f'        <li><a href="{e(rel[0])}">{e(rel[1])}</a></li>')
    return "\n" + "\n".join(rows) + "\n      "


def sweep(apply: bool) -> int:
    changed, ok, missing = [], 0, []
    for slug, data in CALC_DATA.items():
        p = ROOT / "tools" / slug / "index.html"
        if not p.exists():
            missing.append(slug)
            continue
        html = p.read_text(encoding="utf-8")
        m = UL_RE.search(html)
        if not m:
            missing.append(slug + " (no Related <ul>)")
            continue
        want = expected_items(slug, data)
        if m.group(2) == want:
            ok += 1
            continue
        changed.append(slug)
        if apply:
            p.write_text(html[:m.start(2)] + want + html[m.end(2):],
                         encoding="utf-8")

    if missing:
        print("  MISSING: " + ", ".join(missing))
    if apply:
        print(f"  rewrote {len(changed)} of {len(CALC_DATA)} Related lists "
              f"({ok} already correct)")
        return 0 if not missing else 1
    if changed:
        print(f"  FAIL: {len(changed)} calculator page(s) have a Related list that "
              f"does not match the generator")
        for s in changed[:8]:
            print(f"     - tools/{s}/index.html")
        if len(changed) > 8:
            print(f"     ... and {len(changed) - 8} more")
        print("  fix: python tools/fix_calc_related_links.py --apply")
        return 1
    print(f"  OK: all {ok} calculator Related lists match the generator")
    return 0 if not missing else 1


def graph_report() -> int:
    """The teeth: prove the link graph has no orphan and no repeated pair."""
    import collections
    inbound: collections.Counter = collections.Counter()
    pairs: collections.Counter = collections.Counter()
    for slug, data in CALC_DATA.items():
        sibs = data.get("siblings") or _siblings(slug, data)
        pairs[tuple(u for u, _ in sibs)] += 1
        for u, _ in sibs:
            inbound[u] += 1
    orphans = [s for s in CALC_DATA if f"/tools/{s}/" not in inbound]
    repeated = {k: c for k, c in pairs.items() if c > 1}
    print(f"  link graph: {len(CALC_DATA)} calculators, "
          f"{len(orphans)} orphan(s), {len(repeated)} repeated pair(s)")
    if orphans:
        print("  FAIL: never linked from a sibling block: " + ", ".join(orphans))
    if repeated:
        print(f"  FAIL: {len(repeated)} sibling pair(s) used by more than one page")

    # ★THE GUARANTEE A READER ACTUALLY GETS, which "0 orphans" does not give on its
    # own: a graph can have every node linked-from and still be split into islands.
    # Because the selection is cyclic, following the FIRST sibling repeatedly walks
    # the whole discipline - so a reader who lands anywhere can reach every
    # calculator in that discipline without going back to the pillar. Asserted by
    # traversal rather than trusted from the construction (observed live on the
    # plumbing ring: drainage -> domestic-water -> water-supply-pipe -> ...).
    unreachable = []
    by_disc: dict = {}
    for slug, data in CALC_DATA.items():
        by_disc.setdefault(data["discipline"], []).append(slug)
    for disc, members in by_disc.items():
        start = members[0]
        seen, cur = {start}, start
        while True:
            sibs = (CALC_DATA[cur].get("siblings")
                    or _siblings(cur, CALC_DATA[cur]))
            if not sibs:
                break
            nxt = sibs[0][0].strip("/").split("/")[-1]
            if nxt in seen:
                break
            seen.add(nxt)
            cur = nxt
        missed = sorted(set(members) - seen)
        if missed:
            unreachable.append((disc, start, missed))
    if unreachable:
        for disc, start, missed in unreachable:
            print(f"  FAIL: from {start} the '{disc}' ring does not reach "
                  f"{len(missed)}: {', '.join(missed)}")
    else:
        print(f"  first-sibling traversal reaches every member of all "
              f"{len(by_disc)} discipline ring(s)")
    return 1 if (orphans or repeated or unreachable) else 0


def main() -> int:
    args = sys.argv[1:]
    apply = "--apply" in args
    rc = graph_report()
    rc |= sweep(apply)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
