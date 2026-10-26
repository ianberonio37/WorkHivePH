#!/usr/bin/env python3
"""identity-restore-reaches-routing - a page that decides from the cached name must hear the account's answer (2026-10-26).

Found walking the OWN AI failure-mode lens: assistant.html restored identity fire-and-forget and, in the same breath,
routed on the name CACHE (wh_last_worker). A signed-in worker whose device remembered no name stood on the setup screen
with an empty "YOUR NAME" box, and the records panel - which counted only `if (name)` - said "Could not read your
records" for a read that was never made. restoreIdentityFromSession announces the account's name (`wh-identity-changed`,
utils.js _whAnnounceName); the page now listens, and its counts read by account.

Two facts, static:
  1. every page that DISCARDS restoreIdentityFromSession's result (no `.then`, not awaited, not assigned) listens for
     `wh-identity-changed` - otherwise the restore fixes the cache and nothing on the page hears it;
  2. assistant.html's records counts are not gated on the cached name (`if (name)`), and setup routes on the event.

Teeth: the tree at 1045f447 (before the fix) fails both on assistant.html.
    python tools/validate_identity_restore_reaches_routing.py
    python tools/validate_identity_restore_reaches_routing.py --file <path-to-an-html>   (check one file, e.g. an old copy)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# a call whose value is thrown away: not awaited, not assigned, not chained with .then - `.catch(...)` alone or bare `;`
_DISCARDED = re.compile(r"(?<![=\w.])\s*(?<!await )restoreIdentityFromSession\([^)]*\)\s*(?:\.catch\([^;]*\))?\s*;")


def _code(text: str) -> str:
    """Drop // line comments and /* */ blocks so a sentence ABOUT the call is not read as the call."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'])//[^\n]*", r"\1", text)


def check(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    code = _code(src)
    bad = []
    for m in _DISCARDED.finditer(code):
        line = code[max(0, code.rfind("\n", 0, m.start()) + 1): code.find("\n", m.end())]
        if re.search(r"\b(await|then)\b|=\s*restoreIdentityFromSession", line):
            continue
        if "wh-identity-changed" not in code:
            bad.append(f"{path.name}: restoreIdentityFromSession's result is discarded and nothing listens for "
                       f"wh-identity-changed - the account's name reaches the cache and never the page")
        break
    if path.name == "assistant.html":
        body = re.search(r"async function _loadRecordsSummary\(\)\s*\{(.*?)\n    \}\n", code, re.S)
        if not body:
            bad.append("assistant.html: _loadRecordsSummary not found - the records-count check cannot run")
        elif re.search(r"\n\s*if \(name\) \{", body.group(1)):
            bad.append("assistant.html: the records counts wait for a cached name (`if (name)`) - a signed-in person "
                       "with none is told 'Could not read your records' for a read never made")
        if not re.search(r"addEventListener\('wh-identity-changed'[\s\S]{0,400}startChat\(\)", code):
            bad.append("assistant.html: setup does not route on the account's announced name (wh-identity-changed -> startChat)")
    return bad


def main() -> int:
    if "--file" in sys.argv:
        files = [Path(sys.argv[sys.argv.index("--file") + 1])]
    else:
        files = sorted(p for p in ROOT.glob("*.html") if p.is_file())
    bad = [b for f in files for b in check(f)]
    print(f"identity-restore-reaches-routing: {len(files)} page(s) read, {len(bad)} finding(s)")
    for b in bad:
        print("  - " + b)
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
