#!/usr/bin/env python3
"""Gate `list-cap-not-a-total` - a row cap is not the size of a person's data, and a keyset cursor on a
non-unique column must be INCLUSIVE.

Both defects found 2026-10-06 by walking LXP215's HEALTHY control (logbook.html, Bryan Garcia, 2,277 own
entries). The healthy state is where they lived - no outage required, and no previous walk had looked.

  1. THE CAP PRINTED AS THE TOTAL. The mine-mode read is `.limit(200)`, and the label under the search box
     read "Showing 20 of 200 entries" - six centimetres below a header pill reading "2277". 200 is a fact
     about the FETCH. Worse, Load More tested only the loaded window (`_logbookDisplayCount >= filtered
     .length`), so it HID ITSELF at 200 and entries 201..2277 had no route to the screen: a technician
     looking for their repair from four months ago was told, in effect, that it does not exist.
     ★T9 HAD ALREADY FIXED THIS EXACT DEFECT ON THIS PAGE - for the progress strip, using _mineTrueTotal
     from a count:exact read - and the label beside it was never taught. Same page, same lesson, one of
     two consumers. That is the half this gate exists to keep taught.

  2. THE EXCLUSIVE CURSOR SKIPPED ROWS AT EVERY TIE. Both pagers stepped with `.lt('date', cursor)` while
     the declared ordering is `date desc, id asc` and `date` is NOT unique: 527 of this one worker's dates
     carry more than one row, the largest tie is 7 (12 table-wide). Checked against the database at every
     200-row boundary of the real logbook, boundary 600 silently dropped one entry - a repair that simply
     is not there, with nothing on screen to say so. An inclusive cursor re-reads the boundary ties and a
     dedupe set discards them, which is why the overlap is free; a termination guard keeps it finite if a
     single timestamp ever fills a whole page.
     Verified after the fix by walking to 640 loaded rows and hashing the id list: SHA-256 identical to
     the database's own `order by date desc, id` for the same 640 rows, with the previously-dropped row
     present at position 601.

Static, so it runs in --fast with no DB and no browser.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "logbook.html")


def main():
    if not os.path.exists(PAGE):
        print("FAIL list-cap-not-a-total - logbook.html not found")
        return 1
    src = io.open(PAGE, encoding="utf-8").read()
    failures = []

    # --- 1. the cap is a named constant, and the label knows the TRUE total ---------------------
    if not re.search(r"const\s+MINE_PAGE\s*=\s*\d+", src):
        failures.append(
            "MINE_PAGE is gone. The mine-mode cap must be a named constant, because three places have "
            "to agree about it: the .limit(), the has-more test, and the label. A literal 200 in the "
            "read is how the label came to print the fetch size as the person's entry count.")
    if re.search(r"\.limit\(\s*200\s*\)[^\n]*or\(_MINE", src) or re.search(
            r"\.or\(_MINE\(\)\)[\s\S]{0,400}?\.limit\(\s*200\s*\)", src):
        failures.append(
            "the mine-mode read is back to a literal .limit(200) instead of MINE_PAGE - see above.")
    if "_mineTrueTotal" not in src:
        failures.append(
            "_mineTrueTotal is gone. It is the count:exact figure the header pill already shows, and it "
            "is the ONLY honest denominator for an unfiltered view - the loaded window cannot exceed the "
            "cap, so printing its length after 'of' understates the person's logbook.")
    else:
        # The label block must consult the true total, not only the loaded window.
        lbl = re.search(r"const\s+_e2\s*=[\s\S]{0,2600}?lbl\.textContent", src)
        region = src[lbl.start():lbl.end() + 1200] if lbl else ""
        if "_mineTrueTotal" not in region:
            failures.append(
                "the mine-mode count label no longer consults _mineTrueTotal. This is exactly the state "
                "the walk found: the true total sat in memory on the same render that misreported it.")
        # ★THE TOKEN MUST BE IN THE DENOMINATOR POSITION, not merely somewhere nearby. This gate's own
        # teeth test caught it: swapping the printed denominator back to the capped window left every
        # _mineTrueTotal reference intact (the `_haveTrue` guard, the progress strip) and the gate went
        # green on the exact defect it exists to catch. Presence is not use.
        if not re.search(r"of \$\{_e2\(\s*_trueTotal\s*\)\}", src):
            failures.append(
                "the unfiltered label no longer prints _trueTotal after 'of'. Whatever it prints instead "
                "is bounded by MINE_PAGE, so a worker with 2,277 entries is told they have 200.")

    # --- 2. Load More may not hide while the server still has rows ------------------------------
    if not re.search(r"wrap\.classList\.toggle\(\s*['\"]hidden['\"]\s*,[^)]*_mineHasMore", src):
        failures.append(
            "Load More's visibility no longer considers _mineHasMore, so it will hide at the cap again "
            "and the rest of the person's own logbook becomes unreachable from the UI.")

    # --- 3. every keyset append is INCLUSIVE, deduped and terminating ---------------------------
    for cursor, pager in (("_mineLastDate", "mine"), ("_teamLastDate", "team")):
        if cursor not in src:
            failures.append("%s is gone - the %s pager has no cursor, so it cannot page at all."
                            % (cursor, pager))
            continue
        exclusive = re.search(r"\.lt\(\s*['\"]date['\"]\s*,\s*" + re.escape(cursor), src)
        inclusive = re.search(r"\.lte\(\s*['\"]date['\"]\s*,\s*" + re.escape(cursor), src)
        if exclusive:
            failures.append(
                "the %s pager steps with .lt('date', %s). `date` is not unique on this table (527 dates "
                "with ties on one worker's rows, largest 7), and the ordering is `date desc, id asc`, so "
                "an exclusive cursor SKIPS every row sharing the boundary timestamp - measured as a real "
                "dropped entry at boundary 600. Use .lte and let the dedupe discard the overlap."
                % (pager, cursor))
        elif not inclusive:
            failures.append(
                "the %s pager no longer applies %s to its append read at all, so Load More re-reads the "
                "same first page forever." % (pager, cursor))

    # The overlap an inclusive cursor creates is only free if duplicates are actually discarded,
    # and only finite if "nothing new arrived" ends the paging.
    # ★DECLARED **AND** APPLIED. The teeth test renamed only the declaration - leaving the uses behind,
    # which is a runtime ReferenceError - and a token-presence check passed it. Each dedupe therefore has
    # to be found twice: once where it is built, once where it actually filters the server page.
    if not (re.search(r"const\s+_heldIds\s*=\s*new Set\(", src)
            and re.search(r"!\s*_heldIds\.has\(", src)):
        failures.append(
            "the mine pager's _heldIds dedupe is not both declared and applied. An inclusive cursor "
            "re-reads the boundary ties by design; without the dedupe those become visibly duplicated "
            "entries in the feed (or a ReferenceError, if only the declaration went).")
    if not (re.search(r"const\s+_fresh\s*=\s*mapped\.filter\(", src)
            and re.search(r"!\s*_seen\.has\(", src)):
        failures.append(
            "the team pager's dedupe is not both declared and applied - same consequence as above, in "
            "the team feed.")
    # Matched on one statement rather than a parenthesis-counting pattern: the real conditions contain
    # nested calls (`!_srv.some(r => !_heldIds.has(r.id))`), and the gate's FIRST draft reported the
    # mine guard missing because its [^)]* stopped at the first inner ')'. A gate that cannot read the
    # code it guards reports the code as broken - the reader-manufactured finding, in miniature.
    for flag, pager in (("_mineHasMore", "mine"), ("_teamHasMore", "team")):
        stmt = re.compile(r"if\s*\(\s*append\s*&&.{0,160}?\)\s*\{?\s*" + flag + r"\s*=\s*false",
                          re.S)
        if not stmt.search(src):
            failures.append(
                "the %s pager has no 'appended nothing new -> stop' termination guard. An inclusive "
                "cursor cannot make progress if one timestamp ever fills a whole page, and the row count "
                "alone cannot tell you that." % pager)

    if failures:
        print("FAIL list-cap-not-a-total - %d problem(s):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1

    print("PASS list-cap-not-a-total - the mine-mode cap is the named MINE_PAGE, the count label states "
          "the count:exact total rather than the fetched window, Load More stays reachable while the "
          "server has more, and BOTH pagers step with an inclusive cursor plus a dedupe and a "
          "termination guard, so no row is skipped at a tied timestamp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
