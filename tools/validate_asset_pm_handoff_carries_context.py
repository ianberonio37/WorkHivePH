#!/usr/bin/env python3
"""asset-pm-handoff-carries-context - T21: scheduling a PM must not lose the asset.

A supervisor approves a new asset and the next thing they do is give it a maintenance program. If
the link to the scheduler carries the asset, that is one tap; if it does not, they arrive at a list
of everything and have to find the asset they were just looking at - which on a phone, in a plant,
is where the task gets abandoned.

★BOTH ENDS ARE ASSERTED, because a parameter nobody reads is a promise the sender only thinks it is
keeping - the declared-but-never-wired class:
  1. every pm-scheduler link rendered where an ASSET is in hand carries its identity
     (?tag= / ?asset= / ?asset_id=);
  2. pm-scheduler actually CONSUMES those parameters.

★EMPTY-STATE LINKS ARE EXEMPT AND THAT IS NOT A LOOPHOLE: asset-hub's two bare links both sit under
"No approved assets in this hive yet", where there is no asset to name. Demanding a parameter there
would be demanding a lie. The exemption is decided by the surrounding text, not by an allowlist a
future edit could quietly join.

Re-drive: python tools/validate_asset_pm_handoff_carries_context.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ("tag=", "asset=", "asset_id=", "pm_id=")
EMPTY_HINTS = ("no approved assets", "empty", "list-empty", "yet.")


def main() -> int:
    failures = []
    src = io.open(ROOT / "asset-hub.html", encoding="utf-8", errors="replace").read()
    sched = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()

    carried, bare_empty, bare_bad = 0, 0, 0
    # Only real LINKS count. Matching the bare filename also hit a comment - "Canonical PM
    # frequencies (match pm-scheduler.html's FREQ registry)" - and reported it as a context-losing
    # link. A mention is not a navigation. [[feedback_grep_matched_the_comment_not_the_link]]
    LINK = re.compile(r"""(?:href\s*=\s*['"]|\.href\s*=\s*['"])pm-scheduler\.html([^'"]*)""")
    for m in LINK.finditer(src):
        qs = m.group(1)
        if any(p in qs for p in PARAMS):
            carried += 1
            continue
        # no parameter: allowed ONLY where there is no asset in hand
        around = src[max(0, m.start() - 700):m.start() + 200].lower()
        if any(h in around for h in EMPTY_HINTS):
            bare_empty += 1
        else:
            bare_bad += 1
            line = src[:m.start()].count("\n") + 1
            failures.append(f"asset-hub.html:{line}: a PM-scheduler link with an asset in hand carries "
                            f"no identity - the supervisor lands on the full list and has to re-find "
                            f"the asset they were just looking at")

    if carried == 0:
        failures.append("no context-carrying PM link found at all - the handoff this guards is gone, "
                        "so a pass here would mean nothing")

    # the receiving end must consume what the sender sends
    consumed = [p for p in ("asset_id", "asset", "pm_id", "tag")
                if re.search(rf"\.get\(\s*['\"]{p}['\"]", sched)]
    if not consumed:
        failures.append("pm-scheduler.html reads NONE of the parameters asset-hub sends - the asset "
                        "identity is written into the URL and then ignored, which is a promise only "
                        "the sender believes")

    if failures:
        print("FAIL asset-pm-handoff-carries-context:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"  PM links from asset-hub: {carried} carry the asset · {bare_empty} bare in empty states "
          f"(no asset to name) · pm-scheduler consumes: {', '.join(consumed)}")
    print("PASS asset-pm-handoff-carries-context - scheduling a PM from an asset keeps the asset, and "
          "the scheduler reads what it is sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
