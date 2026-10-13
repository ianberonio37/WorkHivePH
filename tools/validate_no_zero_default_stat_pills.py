#!/usr/bin/env python3
"""Gate `no-zero-default-stat-pills` - a counter that comes from a READ may not ship `0` as its markup.

Found 2026-10-06 walking LXP213 (inventory.html) with PostgREST genuinely stopped. The three header pills
read "0 parts / 0 low / 0 out" from first paint until the read resolved at ~51-83s, with no failure
language on screen until ~30s. On a spare-parts register that is the worst available reading: a storeman
concludes the register is empty and that nothing needs reordering.

★THE PAGE'S ERROR HANDLING WAS ALREADY CORRECT, which is why no previous walk caught this. Once the read
resolves with an error, inventory.html dashes those pills and prints an exemplary verdict - "Stock levels
are unknown right now, not zero... Do not order or issue parts from these numbers." The lie lived in the
MARKUP DEFAULT, in the window BEFORE any error exists, and it is equally a lie on a healthy-but-slow load.
A gate that only reads error branches cannot see it; this one reads the static default.

The honest default for a read-backed figure is "unknown", and the em dash is this platform's own word for
it (logbook's _dashPill, inventory's own failure branch). The setter overwrites it when data lands; if the
data never lands, it stays honest instead of becoming a confident zero.

CLIENT-STATE COUNTERS ARE EXEMPT, and the exemption is explicit rather than inferred: compare-count and
rfq-count (a compare basket, an RFQ cart) and rev-count (a wizard's included items) are not read from
anywhere - they begin genuinely empty, so "0 selected" is true at first paint. Each exemption below names
the variable that proves it. A new id is NOT exempt by default: the gate fails closed, so adding a
read-backed pill with a 0 default reddens until it is either fixed or justified here.

Static, so it runs in --fast with no DB and no browser.
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# id -> the client-side expression that proves nothing is read to know it
CLIENT_STATE_EXEMPT = {
    "compare-count": "marketplace.html syncCompareBar(): _compareSet.size (a compare basket)",
    "rfq-count":     "marketplace.html RFQ sheet: _compareSet-derived selection (an RFQ cart)",
    "rev-count":     "pm-scheduler.html review step: wizardItems.filter(included) (the user's own wizard)",
    "rfq-count-plural": "marketplace.html: the pluralising twin of rfq-count",
}

# A counter-ish id shipping a literal 0 inside its own span
PILL = re.compile(
    r'<span[^>]*id="(?P<id>[a-z0-9_-]*(?:stat|count|total|low|out|open|overdue|due)[a-z0-9_-]*)"[^>]*>'
    r'\s*0\s*</span>', re.I)


def main():
    offenders, exempt_seen = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        rel = os.path.basename(path)
        src = io.open(path, encoding="utf-8").read()
        for m in PILL.finditer(src):
            pid = m.group("id")
            line = src[:m.start()].count("\n") + 1
            if pid in CLIENT_STATE_EXEMPT:
                exempt_seen.append("%s:%d %s" % (rel, line, pid))
                continue
            offenders.append(
                "%s:%d - #%s ships `0` as its default. If this figure comes from a read, the page is "
                "asserting a count it does not have yet - measured as ~50s of \"0 parts / 0 low / 0 out\" "
                "on the spare-parts register during an outage. Default it to an em dash and let the "
                "setter overwrite it. If it is genuinely client-side selection state, add it to "
                "CLIENT_STATE_EXEMPT in this gate NAMING the expression that proves it."
                % (rel, line, pid))

    if offenders:
        print("FAIL no-zero-default-stat-pills - %d read-backed pill(s) ship a confident zero:"
              % len(offenders))
        for o in offenders:
            print("  - %s" % o)
        return 1

    print("PASS no-zero-default-stat-pills - no read-backed counter ships `0` as its markup default; the "
          "%d exempt pill(s) are client-side selection state, each justified by name (%s)."
          % (len(exempt_seen), ", ".join(sorted({e.split()[-1] for e in exempt_seen})) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
