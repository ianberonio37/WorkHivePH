#!/usr/bin/env python3
"""presort_lifecycle_rows.py — W3-LC: sort the 64 lifecycle rows before any browser opens.

Each row asks whether a page holds up in a moment the program is thin on: a refused microphone, a person in
two hives, two years of history, leaving, two tabs, an export read back, a notification storm, a release
landing mid-session. Before a walk grades what a PERSON sees, this asks the cheaper question of the source:
does the page (and the scripts it loads) contain anything that could answer at all?

★THE PAGE IS THE PAGE PLUS ITS SCRIPTS. Reading a page alone once reported ten surfaces with no rate-limit
handling; all ten load utils.js, which carries it centrally. Shared chrome is part of the page.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

# what each lifecycle shape looks like in a page's own vocabulary
EVIDENCE = {
    "mic-camera-denied": r"getUserMedia|NotAllowedError|permission|microphone|camera|mic\b",
    "second-hive": r"wh_active_hive_id|hive_members|switch hive|another hive|membership",
    "year-2-aging": r"limit\(|range\(|since|period|from_date|older|archive",
    "leaving": r"export|download|remove(d)? from|no longer a member|delete",
    "two-tabs": r"updated_at|version|conflict|refresh|optimistic|OC\b|stale",
    "export-import": r"export|csv|download|import|\.json",
    "notification-storm": r"notification|alert|digest|quiet hours|mute|unread",
    "version-skew": r"serviceWorker|CACHE_NAME|reload|new version|update available",
}


def source_of(page: str) -> str:
    try:
        src = Path(page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for dep in re.findall(r'<script[^>]+src="([^"]+\.js)"', src):
        d = dep.split("?")[0].lstrip("/")
        if "/" in d:
            continue
        try:
            src += Path(d).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return src


def main() -> int:
    reg = json.loads(Path("trajectory_registry.json").read_text(encoding="utf-8"))
    rows = [t for t in reg["trajectories"] if t.get("wave") == "W3-LC"]
    has, absent = [], []
    for t in rows:
        page = (t.get("pages") or [None])[0]
        key = next((k for k in EVIDENCE if k in (t.get("story") or "")), None)
        if not page or not key:
            continue
        n = len(re.findall(EVIDENCE[key], source_of(page), re.I))
        (has if n else absent).append((t["id"], page, key, n))
    print(f"W3-LC rows: {len(rows)}")
    print(f"  the page has something that could answer this moment: {len(has)}")
    print(f"  nothing in the page or its scripts speaks to it: {len(absent)}")
    if absent:
        print("\n  shapes most often unanswerable:")
        for k, n in Counter(x[2] for x in absent).most_common():
            print(f"     {k:22} {n}")
        print("\n  the unanswerable ones (a walk here is asking a page a question it has no words for):")
        for i, p, k, _n in absent[:30]:
            print(f"     {i:<9} {p[:28]:30} {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
