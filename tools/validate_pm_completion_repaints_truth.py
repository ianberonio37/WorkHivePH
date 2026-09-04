#!/usr/bin/env python3
"""validate_pm_completion_repaints_truth.py — T10's lock: completing a PM repaints the detail from
the TRUTH VIEW, never from stale in-memory state.

Walked live (T10): the worker completed a PM and the detail kept 'Last done Jul 18 - Next due
Jul 25 (39d overdue)' while v_pm_scope_items_truth — same session, same user — already said
completed-TODAY, is_overdue=false. The post-save flow called renderDetail(currentAsset) on the
IN-MEMORY object; the page's own doctrine (client date fallbacks WERE the bug, deleted 2026-05-20)
says the view is the only date source, so a WRITE must be followed by a READ of it. Fixed
2026-09-02: the completion flow awaits loadData(), re-finds currentAsset in the fresh assets, then
renders. Verified live: post-save the item read 'Last done: Sep 2, 2026 - Next due: Sep 9, 2026
(Due in 7d)' while genuinely-overdue siblings kept their honest states.

Lock: the post-completion block must await loadData() and re-find currentAsset BEFORE
renderDetail. Teeth: the pre-fix shape (renderDetail straight after closeSheet with no refetch)
reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["pm-completion-repaints-truth"]

REFRESH_RE = re.compile(
    r"closeSheet\(\);[\s\S]{0,1400}?await loadData\(\);[\s\S]{0,300}?assets\.find\([\s\S]{0,200}?renderDetail\(currentAsset\)")
# T10 a11y: same-model assets must carry DISTINCT accessible names (tag/location in the label) -
# walked live: 'Open PM details for Toyota 8FG25' twice, a screen-reader user cannot tell two
# physical units apart. (hive, tag) is unique, so the tag suffix disambiguates by construction.
LABEL_RE = re.compile(r'aria-label="Open PM details for \$\{escHtml\(asset\.asset_name\)\}\$\{asset\.tag_id')


def problems_for(src: str) -> list[str]:
    out = []
    if not REFRESH_RE.search(src):
        out.append("pm-scheduler.html: the post-completion flow no longer refetches (await loadData() + "
                "re-find currentAsset) before renderDetail — the detail repaints stale in-memory dates "
                "and keeps calling a just-completed PM overdue (the T10 defect)")
    if not LABEL_RE.search(src):
        out.append("pm-scheduler.html: the asset card's accessible name lost its tag suffix — "
                "same-model units become indistinguishable to a screen reader again (T10 Q2)")
    return out


def main() -> int:
    src = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL pm-completion-repaints-truth:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS pm-completion-repaints-truth — completing a PM refetches v_pm_scope_items_truth and "
          "repaints the detail from the fresh row (write -> read -> render).")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    m = REFRESH_RE.search(src)
    pre_fix = src[:m.start()] + m.group(0).replace("await loadData();", "/*no refetch*/") + src[m.end():]
    if not problems_for(pre_fix):
        fails.append("removing the refetch must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_pm_completion_repaints_truth self-test (missing refetch reddens; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
