#!/usr/bin/env python3
"""flagged-post-tells-its-author - T24: a reported post must not vanish on the person who wrote it.

When a teammate reports a post, the platform hides it from the hive until a supervisor rules. The
easy way to build that is one predicate - hide every flagged post from every worker - and it is
wrong for exactly one person: the AUTHOR, who wrote something, saw it disappear, and is told nothing.
They re-post it, or conclude the app is broken, and either way the moderation the supervisor has not
yet done has already cost the platform their trust.

★THE THREE PARTIES, and the contract each is owed:
  1. the AUTHOR keeps seeing their own flagged post - the feed query must exempt their own rows, not
     just filter flagged=false;
  2. the AUTHOR is TOLD, in words: what happened, who decides, and that teammates cannot see it
     meanwhile. A post that reappears with no explanation is barely better than one that vanished;
  3. the SUPERVISOR sees the REPORTER'S REASON on the card - judging a flag without knowing why it
     was raised means tabbing to the audit log first, and a moderation queue that costs a tab is a
     moderation queue that waits.

★IT CHECKS THE QUERY PREDICATE, NOT JUST THE BADGE, because the badge is unreachable if the row was
already filtered out server-side - the render would be correct and the author would still never see
it. That is the half a page-level check would miss entirely.

Re-drive: python tools/validate_flagged_post_tells_its_author.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    failures = []
    src = io.open(ROOT / "community.html", encoding="utf-8", errors="replace").read()

    # 1. the feed query exempts the author's OWN flagged rows
    if not re.search(r"flagged\.eq\.false\s*,\s*author_name\.eq\.", src):
        failures.append("the feed query no longer exempts the author's own flagged posts - a worker "
                        "whose post is reported watches it disappear from their own feed with no word, "
                        "and the badge below can never render because the row never arrives")

    # 2. the author is told, in words, what is happening
    badge = re.search(r"UNDER REVIEW", src)
    if not badge:
        failures.append("no UNDER REVIEW state for the author - their post comes back with no "
                        "explanation of why it is hidden from everyone else")
    else:
        around = src[max(0, badge.start() - 700):badge.start() + 200]
        told = all(re.search(p, around, re.I) for p in
                   (r"reported", r"supervisor", r"cannot see|hidden|until it is cleared"))
        if not told:
            failures.append("the UNDER REVIEW state does not explain what happened, who decides, and "
                            "that teammates cannot see it meanwhile - three facts the author needs and "
                            "cannot infer from a badge")

    # 3. the supervisor judges with the reporter's reason in hand
    if not re.search(r"reportReasonLine|_reportReasons", src):
        failures.append("the supervisor's card no longer carries the reporter's reason - judging a "
                        "flag then means opening the audit log first, and a queue that costs a tab is "
                        "a queue that waits")

    # non-vacuity: there must still BE a report path, or none of this is reachable
    if not re.search(r"report_post|Report Post|flipped?\s*flagged|flagged", src):
        failures.append("no report path found at all; moderation moved and this gate no longer knows "
                        "what it guards")

    if failures:
        print("FAIL flagged-post-tells-its-author:")
        for f in failures:
            print("    - " + f)
        return 1

    print("  author keeps their own flagged post · told what happened, who decides, and that it is "
          "hidden meanwhile · supervisor sees the reporter's reason")
    print("PASS flagged-post-tells-its-author - a reported post does not vanish on its author, and "
          "the person judging it knows why it was raised.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
