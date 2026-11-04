#!/usr/bin/env python3
"""bank_od_rows.py - bank the open-source design lens's rows on what the instruments now read (OD, 2026-11-04).

The OD wave (seed_expansion_wave4.py --add-open-design, OD1..) was seeded from tools/open_design_census.py's measured
cells. A row closes on the SAME instrument that opened it - never on a claim:

  OD-D  <unit> · <class>   the unit's own CSS reads 0 literals of that class (prove_design_source_drift's measure:
                           colour = exact + tint + off, type = raw font sizes, stacking = raw z-indexes). A generated
                           family is read across ALL its members - one member at 0 is not the family at 0.
  OD-S  --wh-x-rgb         the triplet is declared in tokens.css AND no served file types a tint of that colour by hand.
  OD-S  #rrggbb            the census no longer finds that off-palette cluster on >= 5 units (it became a token, or its
                           uses were retired onto one).
  OD-S  a scale            the scale's tokens are declared AND the raw uses it replaces read 0 (type / stacking / overlay).
  OD-P  <unit>             penpot_comps_report.json holds the unit at BOTH widths with pass: true.

Banked rows go to locking (pct 60) with a one-sentence basis naming the reading, and gate design-source-drift (OD-D/OD-S)
or penpot-comps (OD-P). --check re-reads every banked row: a row whose reading regressed fails the gate.

  python tools/bank_od_rows.py            # dry run: what each open OD row reads today
  python tools/bank_od_rows.py --apply
  python tools/bank_od_rows.py --check
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

GATE_D = "design-source-drift"
GATE_P = "penpot-comps"
TOOL = "tools/bank_od_rows.py"
COMPS = ROOT / "penpot_comps_report.json"
CLASS_KEYS = {"colour": ("exact", "tint", "off"), "type": ("fontSizes",), "stacking": ("zIndexes",)}


def readings():
    import open_design_census as odc
    import prove_design_source_drift as dsd
    files = dsd.design_files(ROOT)
    m = dsd.measure(ROOT, files)["files"]
    members = defaultdict(list)
    for f in files:
        members[odc.unit_of(f)].append(f)
    tokens_css = (ROOT / "tokens.css").read_text(encoding="utf-8")
    census = odc.census(ROOT)
    tints = odc.tint_by(ROOT, files)
    return m, members, tokens_css, census, tints


def _near(a, b) -> bool:
    import math
    import open_design_census as odc
    return math.dist(odc._lab(a), odc._lab(b)) < 3


def _token_rgbs(tokens_css: str) -> list:
    import fix_token_literals as ftl
    out = []
    for v in ftl.token_values(tokens_css).values():
        c = ftl.rgba(v) if ftl.COLOUR.fullmatch(v.strip()) else None
        if c:
            out.append(list(c[:3]))
    return out


_LIT_CACHE: dict = {}


def _literal_uses(lead) -> int:
    """Colour literals within delta-E 3 of `lead`, typed in any served file's own CSS, NOT inside a var() fallback."""
    import fix_token_literals as ftl
    import prove_design_source_drift as dsd
    if "texts" not in _LIT_CACHE:
        texts = []
        for f in dsd.design_files(ROOT):
            t = (ROOT / f).read_text(encoding="utf-8", errors="replace")
            texts.append(t if f.endswith(".css") else dsd.page_css(t))
        _LIT_CACHE["texts"] = texts
    n = 0
    for css in _LIT_CACHE["texts"]:
        for m in ftl.COLOUR.finditer(css):
            if ftl._in_var_fallback(css, m.start()):
                continue
            c = ftl.rgba(m.group(0))
            if c and _near(lead, list(c[:3])):
                n += 1
    return n


def _overlay_literals() -> int:
    """White at alpha <= 0.20 or black at any alpha above 0, typed by hand outside a var() fallback."""
    import fix_token_literals as ftl
    _literal_uses([0, 0, 0])  # fills the shared text cache
    n = 0
    for css in _LIT_CACHE["texts"]:
        for m in ftl.COLOUR.finditer(css):
            if ftl._in_var_fallback(css, m.start()):
                continue
            c = ftl.rgba(m.group(0))
            if c and 0 < c[3] < 1 and ((c[:3] == (255, 255, 255) and c[3] <= 0.20) or c[:3] == (0, 0, 0)):
                n += 1
    return n


def class_count(m, members, unit, cls) -> int:
    return sum(sum(m[f].get(k, 0) for k in CLASS_KEYS[cls]) for f in members.get(unit, []))


def verdict(row, m, members, tokens_css, census, tints, comps) -> tuple[bool, str]:
    od = row["od"]
    key, unit, lens = od["key"], od["unit"], od["lens"]
    if key == "D":
        cls = next(c for c, w in (("colour", "colours"), ("type", "font sizes"), ("stacking", "z-indexes")) if w in lens)
        n = class_count(m, members, unit, cls)
        span = f" across its {len(members.get(unit, []))} members" if len(members.get(unit, [])) > 1 else ""
        return n == 0, f"{unit} reads {n} hand-typed {cls} literal(s){span} (prove_design_source_drift)"
    if key == "S":
        tm = re.fullmatch(r"(--wh-[\w-]+)-rgb", unit)
        if tm:
            declared = re.search(re.escape(unit) + r"\s*:", tokens_css) is not None
            hand = tints.get(tm.group(1), 0)
            return declared and hand == 0, (f"{unit} {'declared' if declared else 'NOT declared'} in tokens.css; "
                                            f"{hand} hand-typed tint(s) of {tm.group(1)} remain")
        if unit.startswith("#"):
            # ★THE ROW SAYS "no unit types the literal or a near-twin" - not "the census stopped calling it off-palette".
            # Declaring the token moves its literals from 'off' to 'exact', so the census forgets the cluster the moment
            # the token exists, while pages still type it (print blocks the codemod leaves alone). Count the literals.
            lead = [int(unit[i:i + 2], 16) for i in (1, 3, 5)]
            declared = any(_near(lead, v) for v in _token_rgbs(tokens_css))
            uses = _literal_uses(lead)
            return declared and uses == 0, (f"{unit}: a token {'holds' if declared else 'does NOT hold'} it; "
                                            f"{uses} literal use(s) of it or a near-twin remain")
        if unit == "the neutral overlay + shadow scale":
            # ★the scale is --wh-white-NN / --wh-black-NN (2026-11-04); "its uses read from it" means no OVERLAY-range
            # alpha typed by hand - white <= 0.20 or any black - while rgba(0,0,0,0) is "transparent", not an overlay,
            # and white text alphas (.60-.92) sit on APCA decisions outside this scale
            declared = re.search(r"--wh-white-\d+\s*:", tokens_css) and re.search(r"--wh-black-\d+\s*:", tokens_css)
            n = _overlay_literals()
            return bool(declared) and n == 0, (f"overlay scale {'declared' if declared else 'NOT declared'}; "
                                               f"{n} overlay-range alpha(s) still typed by hand")
        scale_tokens = {"the type scale": r"--wh-fs-", "the stacking (z-index) scale": r"--wh-z-"}
        pat = scale_tokens.get(unit)
        raw = {"the type scale": "fontSizes", "the stacking (z-index) scale": "zIndexes",
               "the neutral overlay + shadow scale": "neutral"}.get(unit)
        declared = bool(pat and re.search(pat, tokens_css))
        n = sum(v.get(raw, 0) for v in m.values()) if raw else -1
        return declared and n == 0, f"{unit}: tokens {'declared' if declared else 'not declared'}; {n} raw use(s) remain"
    if key == "P":
        rec = (comps.get("pages") or {}).get(od["page"]) or {}
        both = all((rec.get(vp) or {}).get("pass") for vp in ("390", "1280"))
        return both, f"penpot_comps_report: {od['page']} at 390 {(rec.get('390') or {}).get('pass')}, at 1280 {(rec.get('1280') or {}).get('pass')}"
    return False, "unknown OD key"


def instrument_of(row, comps) -> str:
    """The instrument that took the reading, by name - the row's declared od.instrument is what the ledger
    (live_walk_manifest) routes it by, so a basis that names only this banker is a claim no instrument stands behind.
    ★(2026-11-04) The first 173 bases named tools/bank_od_rows.py and nothing else; the ledger read them as prose."""
    key = row["od"]["key"]
    if key == "D":
        return "the Wallace css-analyzer (tools/prove_design_source_drift.py, over the served files' own CSS)"
    if key == "S":
        return ("the open-design census (tools/open_design_census.py) over the Wallace css-analyzer's file set "
                "(tools/prove_design_source_drift.py) and tokens.css")
    rec = (comps.get("pages") or {}).get(row["od"]["page"]) or {}
    readers = sorted({(rec.get(vp) or {}).get("live_reader") or "the Playwright library" for vp in ("390", "1280")})
    return (f"the Penpot MCP (tools/penpot_comp_from_page.mjs drew each board) against a full-page screenshot of the "
            f"live page taken by {' and '.join(readers)}, compared by odiff")


def stamp(row, why, today, comps) -> str:
    gate = GATE_P if row["od"]["key"] == "P" else GATE_D
    return f"[{today}] pct -> 60. MEASURED by {instrument_of(row, comps)}; banked by {TOOL}: {why}. HELD BY gate {gate}."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--restamp", action="store_true",
                    help="re-read every banked OD row and append a segment naming the instrument (only rows that still read closed)")
    a = ap.parse_args()
    import registry_io
    doc = registry_io.load_doc()
    rows = [r for r in doc["trajectories"] if (r.get("od") or {}).get("kind") == "open-design"]
    m, members, tokens_css, census, tints = readings()
    comps = json.loads(COMPS.read_text(encoding="utf-8")) if COMPS.exists() else {}
    today = date.today().isoformat()
    if a.check:
        bad = []
        for r in rows:
            if r.get("status") in ("locking", "locked") and TOOL in (r.get("basis") or ""):
                ok, why = verdict(r, m, members, tokens_css, census, tints, comps)
                if not ok:
                    bad.append(f"{r['id']} ({r['od']['unit']}): {why}")
        if bad:
            print(f"FAIL od-rows-hold: {len(bad)} banked OD row(s) no longer read what they were banked on:")
            for b in bad[:20]:
                print("  " + b)
            return 1
        print(f"PASS od-rows-hold - every banked OD row still reads closed")
        return 0
    if a.restamp:
        done, held_open = 0, []
        for r in rows:
            if r.get("status") not in ("locking", "locked") or TOOL not in (r.get("basis") or ""):
                continue
            ok, why = verdict(r, m, members, tokens_css, census, tints, comps)
            if not ok:
                held_open.append(r["id"])
                continue
            seg = stamp(r, why, today, comps)
            if seg not in (r.get("basis") or ""):
                r["basis"] = (r.get("basis") or "") + " || " + seg      # newest LAST (see --apply)
                done += 1
        _save(doc)
        print(f"RESTAMPED {done} OD row(s); {len(held_open)} no longer read closed: {held_open[:10]}")
        return 1 if held_open else 0
    can, by = [], Counter()
    for r in rows:
        if r.get("status") in ("locking", "locked", "descoped"):
            continue
        ok, why = verdict(r, m, members, tokens_css, census, tints, comps)
        by[(r["wave"], ok)] += 1
        if ok:
            can.append((r, why))
    for (w, ok), n in sorted(by.items()):
        print(f"  {w:6} {'bankable' if ok else 'open    '} {n}")
    if not a.apply:
        for r, why in can[:12]:
            print(f"  would bank {r['id']:6} {why[:110]}")
        print(f"(dry run - {len(can)} bankable)")
        return 0
    for r, why in can:
        gate = GATE_P if r["od"]["key"] == "P" else GATE_D
        if TOOL not in (r.get("basis") or ""):
            # append-only, newest LAST, as bank_sl_walk._bank does: the registry gate reads the LAST "pct -> N" as the
            # row's account of itself (SL3121, 2026-10-22)
            r["basis"] = ((r.get("basis") or "") + " || " + stamp(r, why, today, comps)).strip(" |")
        r["status"], r["pct"] = "locking", 60
        r.setdefault("artifacts", {}).setdefault("gates", [])
        if gate not in r["artifacts"]["gates"]:
            r["artifacts"]["gates"].append(gate)
    _save(doc)
    print(f"BANKED {len(can)} OD row(s) -> locking 60")
    return 0


def _save(doc) -> None:
    import registry_io
    # at the main file's own indent (the bank_tenant_refusal_rows pattern) - a save must never reformat the registry
    with io.open(ROOT / "trajectory_registry.json", encoding="utf-8") as fh:
        fh.readline()
        second = fh.readline()
    registry_io.save_doc(doc, indent=max(1, len(second) - len(second.lstrip(" "))) if second.strip() else 2)


if __name__ == "__main__":
    sys.exit(main())
