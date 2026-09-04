#!/usr/bin/env python3
"""validate_no_dead_feature_remnants.py — T60's lock instrument: a retired feature leaves no orphaned
function behind, and dead code cannot silently accrete.

T60 verified the guest-era remnants were fully removed (#panel-guest, submitGuest gone — only
retirement comments remain). This gate LOCKS that: it finds top-level inline functions that are
DEFINED but referenced NOWHERE — the 'declared but never wired' class, which is both dead weight and,
for a half-removed feature, a door that still opens onto nothing.

CONSERVATIVE BY DESIGN (the units_at_boundary / clone-debt lesson: an over-eager static lint cries
wolf). A function is flagged ORPHAN only when ALL hold, so a real-but-indirect caller is never
convicted:
  • it is defined as `function NAME(` at low indentation (a top-level page function, not a nested
    closure whose name is local);
  • NAME appears NOWHERE else in the file — not `NAME(` (call), not `onclick="NAME`, not
    `addEventListener(..., NAME`, not `'NAME'`/\"NAME\" (a string handler / dynamic dispatch), not
    `window.NAME` (an export);
  • NAME is not an event-handler idiom the browser calls by name (on*), nor a framework lifecycle.
Forward-only ratchet against a frozen baseline: the count may fall (and the baseline auto-lowers),
never rise. Removing the LAST caller of a function without removing the function is exactly the
regression this guards.

Registered in run_platform_checks (Platform). Read-only; no browser.
"""
from __future__ import annotations

import glob
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tools" / "dead_feature_baseline.json"

CHECK_NAMES = ["no-dead-feature-remnants"]

# a top-level function definition: `function NAME(` with <=6 leading spaces (page scope, not a deep
# nested closure whose name would be local and legitimately referenced only inside its parent)
_DEF = re.compile(r"^\s{0,6}(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)
# names the browser may invoke by string/attribute even with no in-file textual reference
_BROWSER_CALLED = re.compile(r"^(on[a-z]+|gtag|dataLayer)$")


def orphans_in(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    # strip block + line comments so a retirement comment mentioning the old name is not a "reference"
    stripped = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    stripped = re.sub(r"//[^\n]*", " ", stripped)
    stripped = re.sub(r"<!--.*?-->", " ", stripped, flags=re.S)
    out = []
    for m in _DEF.finditer(stripped):
        name = m.group(1)
        if _BROWSER_CALLED.match(name):
            continue
        # every textual occurrence of the bare identifier, minus the definition itself
        refs = len(re.findall(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", stripped))
        if refs <= 1:                       # only the definition — nothing calls it, no string, no export
            out.append(name)
    return out


def scan() -> dict[str, list[str]]:
    found = {}
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        p = Path(f)
        if any(t in p.name for t in ("-test", "backup", "index-")) or p.name == "symbol-gallery.html":
            continue
        orph = orphans_in(p)
        if orph:
            found[p.name] = orph
    return found


def main() -> int:
    found = scan()
    total = sum(len(v) for v in found.values())
    baseline = None
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8")).get("count")
    if baseline is None:
        BASELINE.write_text(json.dumps({"count": total, "established": "2026-09-01"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {total} orphaned top-level function(s) (forward-only)")
        return 0
    if total > baseline:
        print(f"FAIL no-dead-feature-remnants — orphaned functions GREW {baseline} -> {total}:")
        for f, names in list(found.items())[:8]:
            print(f"    {f}: {', '.join(names[:6])}")
        print("    A function defined but referenced nowhere is dead weight (or a half-removed "
              "feature's door). Delete it, or wire the caller back.")
        return 1
    if total < baseline:
        BASELINE.write_text(json.dumps({"count": total, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"PASS no-dead-feature-remnants — improved {baseline} -> {total}; ratchet lowered.")
        return 0
    print(f"PASS no-dead-feature-remnants — held at {total} orphaned function(s) (baseline {baseline}).")
    return 0


def self_test() -> int:
    import tempfile, os
    fails = []
    def orphans_of(text):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(text); tmp = Path(f.name)
        try:
            return orphans_in(tmp)
        finally:
            os.unlink(tmp)
    # real files put top-level functions on their own line; the definition regex requires that.
    # wired: defined AND called -> not orphan
    if orphans_of("<script>\nfunction foo(){}\nfoo();\n</script>"):
        fails.append("a called function must not be flagged")
    # onclick attribute counts as a reference
    if orphans_of("<button onclick=\"bar()\"></button>\n<script>\nfunction bar(){}\n</script>"):
        fails.append("an onclick-referenced function must not be flagged")
    # a retirement COMMENT is not a reference -> orphan
    if "gone" not in orphans_of("<script>\n/* gone() was removed */\nfunction gone(){}\n</script>"):
        fails.append("a function only named in a comment should be flagged orphan")
    # truly dead -> orphan
    if "dead" not in orphans_of("<script>\nfunction dead(){ return 1; }\n</script>"):
        fails.append("a defined-but-unreferenced function should be flagged")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_no_dead_feature_remnants self-test (called/onclick spared; comment-only & "
          "truly-dead flagged)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
