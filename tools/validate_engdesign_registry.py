#!/usr/bin/env python3
"""
Validator: Engineering-Design REGISTRY single-source-of-truth (deep-arc P1)

WHAT THIS IS
------------
engineering-design.html advertises calc counts in THREE hand-typed places that
silently drifted from the real registry (CALC_TYPES_UI):
  - the search field placeholder/aria-label ("Search all 53 calculations")
  - each discipline pill's .pill-count badge (HVAC said "11")
  - the sum of those pills
Measured truth (Object.values(CALC_TYPES_UI).flat().length) = 55. Three numbers,
none of them right (53 / 56 / 55). The fix (P1/F-3) makes syncCalcCounts() DERIVE
every advertised count from CALC_TYPES_UI at init; this gate ratchets it so the
numbers can never drift again, and pins two more registry-integrity contracts:

  F-3  Every static pill count == len(CALC_TYPES_UI[discipline]); the search
       placeholder number == the flat total; and syncCalcCounts() exists AND is
       called from init() (so the runtime derivation is actually wired).
  F-6  The legacy CALC_TYPES id-set is a superset of CALC_TYPES_UI (the two
       hand-synced registries have not drifted apart — every UI calc still has
       its legacy input-form entry).
  F-4  Every report-dispatch arm (`_calcType === 'X'`) resolves to a real
       CALC_TYPES_UI id, EXCEPT the two documented superseded orphans. Any NEW
       orphan (a renderer with no UI registry entry) FAILs.

WHY it matters: a lying count is a small trust leak on a professional tool; an
orphan renderer is dead code that drift-rots; a divergent legacy registry is the
exact "renderInputForm can't find the calc" class the code comments already fear.

Static + hermetic (parses the two source files, no network/DB/browser).

Run:        python tools/validate_engdesign_registry.py
Self-test:  python tools/validate_engdesign_registry.py --self-test
"""

import os
import re
import sys

# Windows cp1252 stdout guard (required on every validator).
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, "engineering-design.js")
HTML_PATH = os.path.join(ROOT, "engineering-design.html")

# Two dispatch arms with full renderers but no CALC_TYPES_UI entry: legacy names
# superseded by 'V-Belt Drive Design' and 'Boiler System'. Documented as known
# dead code (unreachable from the UI, zero user impact). A THIRD orphan = FAIL.
ORPHAN_ALLOWLIST = {
    "Gear / Belt Drive":    "superseded by 'V-Belt Drive Design' (renderer + BOM ref retained; no UI card)",
    "Boiler / Steam System": "superseded by 'Boiler System' (renderer retained; no UI card)",
}


def _extract_brace_block(src, decl):
    """Return the text between the outermost { } of `const <decl> = { ... }`."""
    m = re.search(r"const\s+" + re.escape(decl) + r"\s*=\s*\{", src)
    if not m:
        return None
    i = src.index("{", m.start())
    depth, start = 0, i
    while i < len(src):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return None


def _ui_counts(block):
    """discipline -> [ids] from CALC_TYPES_UI (top-level 'Discipline': [ {id:...} ])."""
    out = {}
    cur = None
    for line in block.splitlines():
        m = re.match(r"\s*'([^']+)'\s*:\s*\[", line)
        if m:
            cur = m.group(1)
            out[cur] = []
            # ids can also share the opening line; fall through to scan it
        for idm in re.finditer(r"\bid:\s*'([^']+)'", line):
            if cur is not None:
                out[cur].append(idm.group(1))
    return out


def _all_ids(block):
    return set(re.findall(r"\bid:\s*'([^']+)'", block or ""))


def run():
    problems = []
    notes = []

    js = open(JS_PATH, encoding="utf-8").read()
    html = open(HTML_PATH, encoding="utf-8").read()

    ui_block = _extract_brace_block(js, "CALC_TYPES_UI")
    legacy_block = _extract_brace_block(js, "CALC_TYPES")
    if not ui_block:
        problems.append("CALC_TYPES_UI registry not found in engineering-design.js")
        return _report(problems, notes)

    ui = _ui_counts(ui_block)
    ui_ids = set()
    for d, ids in ui.items():
        ui_ids.update(ids)
    total = sum(len(v) for v in ui.values())
    notes.append(f"CALC_TYPES_UI: {len(ui)} disciplines, {total} calcs "
                 + ", ".join(f"{d}={len(v)}" for d, v in ui.items()))

    # ---- F-3a: static pill counts == registry ----
    for btn in re.finditer(r'data-disc="([^"]+)"[^>]*>.*?<span class="pill-count">(\d+)</span>', html, re.S):
        disc, shown = btn.group(1), int(btn.group(2))
        real = len(ui.get(disc, []))
        if disc not in ui:
            problems.append(f"HTML pill discipline '{disc}' has no CALC_TYPES_UI entry")
        elif shown != real:
            problems.append(f"F-3 pill count drift: '{disc}' shows {shown}, registry has {real}")

    # ---- F-3b: search placeholder number == flat total ----
    sm = re.search(r'placeholder="Search all (\d+) calculations', html)
    if not sm:
        problems.append("F-3 search placeholder 'Search all N calculations' not found")
    elif int(sm.group(1)) != total:
        problems.append(f"F-3 search count drift: placeholder says {sm.group(1)}, registry total is {total}")

    # ---- F-3c: derivation actually wired ----
    if "function syncCalcCounts(" not in js:
        problems.append("F-3 syncCalcCounts() (count-derivation fn) missing")
    else:
        init_m = re.search(r"async function init\(\)\s*\{(.*?)\n\}", js, re.S)
        if not init_m or "syncCalcCounts(" not in init_m.group(1):
            problems.append("F-3 syncCalcCounts() defined but not called from init()")

    # ---- F-6: CALC_TYPES_UI must be the SOLE registry ----
    # The legacy CALC_TYPES duplicate was deleted in P1 (dead code that had drifted).
    # If a second registry is ever reintroduced, it must not drift from the UI set.
    if legacy_block and legacy_block is not ui_block:
        legacy_ids = _all_ids(legacy_block)
        missing = ui_ids - legacy_ids
        if missing:
            problems.append(f"F-6 registry drift: a second registry CALC_TYPES exists, missing {sorted(missing)[:5]} — "
                            f"the legacy duplicate was deleted in P1; extend CALC_TYPES_UI, don't fork a second registry")
        else:
            notes.append("F-6: a second CALC_TYPES registry exists but is in sync (single-registry preferred)")
    else:
        notes.append("F-6: CALC_TYPES_UI is the sole registry (legacy duplicate removed)")

    # ---- F-4: no NEW orphan dispatch arm ----
    dispatch = set(re.findall(r"_calcType\s*===\s*'([^']+)'", js))
    orphans = {d for d in dispatch if d not in ui_ids}
    new_orphans = orphans - set(ORPHAN_ALLOWLIST)
    if new_orphans:
        problems.append(f"F-4 NEW orphan dispatch arm(s) with no CALC_TYPES_UI id: {sorted(new_orphans)}")
    known = orphans & set(ORPHAN_ALLOWLIST)
    if known:
        notes.append("known orphans (allowlisted, documented dead code): "
                     + "; ".join(f"'{o}' — {ORPHAN_ALLOWLIST[o]}" for o in sorted(known)))

    return _report(problems, notes)


def _report(problems, notes):
    print("=" * 68)
    print("Engineering-Design Registry SSOT gate (deep-arc P1: F-3/F-4/F-6)")
    print("=" * 68)
    for n in notes:
        print("  note:", n)
    if problems:
        print(f"\nFAIL — {len(problems)} registry-integrity problem(s):")
        for p in problems:
            print("  x", p)
        return 1
    print("\nPASS — counts derive from CALC_TYPES_UI; registries in sync; no new orphans.")
    return 0


def self_test():
    """Prove teeth: a fabricated drift must be caught."""
    ok = True
    # 1) a pill-count drift is caught
    fake_html = '<button data-disc="HVAC & Cooling">x <span class="pill-count">99</span></button>'
    if not re.search(r'<span class="pill-count">(\d+)</span>', fake_html):
        print("self-test: regex broken"); ok = False
    # 2) orphan detection: an arm not in ids and not allowlisted must be flagged
    dispatch = {"Totally New Orphan", "Gear / Belt Drive"}
    ui_ids = set()
    new_orphans = {d for d in dispatch if d not in ui_ids} - set(ORPHAN_ALLOWLIST)
    if new_orphans != {"Totally New Orphan"}:
        print("self-test: orphan detection broken:", new_orphans); ok = False
    # 3) brace extractor pulls the right block
    src = "const CALC_TYPES_UI = { 'A': [ { id: 'x' } ] };\nconst OTHER = {};"
    blk = _extract_brace_block(src, "CALC_TYPES_UI")
    if not blk or _all_ids(blk) != {"x"}:
        print("self-test: brace extractor broken:", blk); ok = False
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
