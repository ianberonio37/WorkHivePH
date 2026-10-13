#!/usr/bin/env python3
"""Gate `queue-count-honours-refusal` - a queue you may not read has an UNKNOWN size, not a size of zero.

Found 2026-10-06 walking LXP223 (platform-actions) as a worker. RLS answers a non-admin by returning ZERO
ROWS AND NO ERROR, so every counter on this governance console computed 0 and printed it. Measured against
the database at that moment: `platform_feedback` held 10 rows with status 'new' while the page's New tab
read 0 - and it read 0 directly beside the page's own list saying "Not visible with this session. Sign in
as a platform admin to see what is waiting." The list was honest and the counters contradicted it on the
same screen.

★THE PAGE HAD ALREADY LEARNED THIS LESSON AND APPLIED IT TO HALF ITSELF. Its own comment, dated
2026-08-03, says it plainly: "Signed in as anyone who is not a platform admin, EVERY queue below returns 0
rows with NO error - so a top-up queue with a real provider waiting on PHP 300 renders exactly like an
empty one... a false all-clear is the most expensive empty state the platform can show. Name it instead."
That change introduced `_sessionLimited` and taught the LISTS. The COUNTERS were never taught. This gate
keeps both halves taught.

The guard lives in `setCount`, the one function every queue counter passes through, plus an explicit twin
for the five feedback tab pills (which are written directly, because routing them through setCount would
impose its `count` class on spans that have none).

VERIFIED IN BOTH DIRECTIONS, live: as a worker, all 11 counters read an em dash with no false zero; signed
in as Leandro Marquez (a seeded platform admin), the same counters read 10 new / 10 all / badge 10, exactly
the database's contents, with the "Not visible" sentence gone. A guard that only ever prints a dash would
have passed the first half and broken the console for the person it is for.

Static, so it runs in --fast with no DB and no browser.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bug_repro_inventory import _strip_comments_js  # noqa: E402  (blanks comments, preserving offsets)

PAGE = os.path.join(ROOT, "platform-actions.html")
FLAG = "_sessionLimited"


def main():
    if not os.path.exists(PAGE):
        print("FAIL queue-count-honours-refusal - platform-actions.html not found")
        return 1
    src = io.open(PAGE, encoding="utf-8").read()
    code = _strip_comments_js(src)
    failures = []

    # The signal itself must still exist and still be derived from admin-ness, not from an error.
    if FLAG not in code:
        failures.append(
            "%s is gone. It is the page's own name for 'this session may not read these queues', and it is "
            "what tells a refusal apart from an empty queue - RLS gives both the same shape (0 rows, no "
            "error)." % FLAG)
    elif not re.search(re.escape(FLAG) + r"\s*=\s*!\s*\w*[aA]dmin", code):
        failures.append(
            "%s is no longer derived from the admin check. Derived from an ERROR instead it would be false "
            "in exactly the case that matters: a refusal that returns 0 rows and no error." % FLAG)

    # setCount is the single funnel for the queue counters.
    m = re.search(r"function setCount\s*\([^)]*\)\s*\{", code)
    if not m:
        failures.append("setCount not found - if the counters moved to another function, re-point this "
                        "check rather than dropping it.")
    else:
        i = code.index("{", m.end() - 1)
        depth, j = 0, i
        while j < len(code):
            if code[j] == "{":
                depth += 1
            elif code[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = code[i:j + 1]
        if FLAG not in body:
            failures.append(
                "setCount no longer consults %s, so every queue counter on this console will print a 0 it "
                "cannot know - measured as a '0' beside 10 real rows in the database." % FLAG)
        else:
            # The guard must RETURN before the numeric write, or the dash is immediately overwritten.
            g = body.index(FLAG)
            w = body.find("el.textContent = n")
            if w != -1 and w < g:
                failures.append(
                    "setCount writes the numeric value BEFORE it consults %s, so the guard cannot take "
                    "effect." % FLAG)
            if "return" not in body[g:w if w != -1 else len(body)]:
                failures.append(
                    "the %s branch in setCount does not return, so the numeric write still happens and the "
                    "dash is overwritten." % FLAG)
            # ...and it must NOT dash unconditionally, or the console breaks for the admin it exists for.
            if re.search(r"el\.textContent\s*=\s*['\"]\\u2014['\"]\s*;\s*el\.className[^;]*;\s*return", body) \
                    and FLAG not in body[:body.index("el.textContent")]:
                failures.append(
                    "setCount appears to dash unconditionally. Verified live that an admin must still see "
                    "real figures (10 new / 10 all), so the dash has to be inside the %s branch." % FLAG)

    # The five feedback tab pills are written directly and need the same guard.
    # The window must look BACKWARD as well as forward: the guard is declared just above the loop, and
    # the gate's first run failed on its own correct code because it only searched ahead of the write.
    # ★EVERY WRITER, NOT THE FIRST (2026-10-13). The page gained a second fb-count-<k> writer - the read-FAILED
    # branch, which always writes "unknown" through whStatUnknown - and it sits ABOVE the normal one, so a search
    # for the first match graded the error path and failed correct code. Each writer must now either branch on the
    # refusal flag or write through whStatUnknown unconditionally; a writer with neither still fails.
    tabs = list(re.finditer(r"[\s\S]{0,400}getElementById\('fb-count-'\s*\+\s*k\)[\s\S]{0,240}", code))
    if not tabs:
        failures.append("the feedback tab-pill writer (fb-count-<status>) was not found.")
    # The WRITE must be conditional, not merely near the flag. The gate's teeth test removed the ternary
    # and still passed, because the guard's `const _unknown = ... _sessionLimited ...` declaration survived
    # in the same window - a flag that is computed and then ignored is the same defect with extra steps.
    for tab in tabs:
        w = tab.group(0)
        guarded = re.search(r"textContent\s*=\s*_unknown\s*\?", w) or re.search(r"if\s*\(\s*_unknown\b", w)
        always_unknown = re.search(r"whStatUnknown\(\s*_?el\s*,\s*'count'\s*\)", w) and "_unknown" not in w
        if not (guarded or always_unknown):
            failures.append(
                "the five feedback tab pills are written without consulting %s, so they will read 'New 0 / "
                "Triaged 0 / ...' for a reader the page has just told it cannot show the queue to." % FLAG)
            break

    if failures:
        print("FAIL queue-count-honours-refusal - %d problem(s):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1

    print("PASS queue-count-honours-refusal - %s is still derived from the admin check, setCount returns a "
          "dash for every queue counter while it is set (and only while it is set), and the five feedback "
          "tab pills carry the same guard. A refused read reads as unknown, not as an all-clear." % FLAG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
