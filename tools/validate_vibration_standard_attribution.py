#!/usr/bin/env python3
"""vibration-standard-attribution - the Class I-IV zones are ISO 10816-1's, never ISO 10816-3's (2026-10-27).

FOUND refreshing the KA-R learn pages: the Vibration Analysis calculator, its report, its drawing legend, the
BOM/SOW prompts, the public calculator page and three learn articles all labelled the Class I-IV severity table
"ISO 10816-3". The NUMBERS were right (Class II 1.12 / 2.8 / 7.1 mm/s is ISO 10816-1's legacy annex, ex ISO 2372);
the SOURCE was wrong. ISO 10816-3 never held those classes: it grouped industrial machines above 15 kW into
Group 1 / Group 2 by foundation with its own limits (Group 2 rigid 1.4 / 2.8 / 4.5), and since 2022 it is
ISO 20816-3. An engineer checking a report against the cited standard would find a different table there.

ASSERTION: every surviving mention of "ISO 10816-3" is a HISTORICAL one - within reach of its successor
("20816-3"), the word "formerly"/"replaced", or the Group scheme it actually uses. A bare "ISO 10816-3" next to
a class or a zone is the misattribution coming back.

    python tools/validate_vibration_standard_attribution.py
    python tools/validate_vibration_standard_attribution.py --self-test
"""
from __future__ import annotations

import glob
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["engineering-design.js", "python-api/calcs/vibration_analysis.py",
         "supabase/functions/engineering-bom-sow/index.ts", "tools/build_calc_pages.py"]
GLOBS = ["learn/*/index.html", "tools/*/index.html"]
HIST = re.compile(r"20816-3|formerly|replaced|Group 1|Group 2|use groups|groups machines", re.I)
WINDOW = 140


def offenders(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"10816-3", text):
        win = text[max(0, m.start() - WINDOW): m.end() + WINDOW]
        if not HIST.search(win):
            out.append(re.sub(r"\s+", " ", text[max(0, m.start() - 70): m.end() + 50]))
    return out


def scan() -> dict[str, list[str]]:
    paths = [ROOT / f for f in FILES]
    for g in GLOBS:
        paths += [Path(p) for p in glob.glob(str(ROOT / g))]
    found = {}
    for p in paths:
        if not p.exists():
            continue
        hits = offenders(p.read_text(encoding="utf-8", errors="replace"))
        if hits:
            found[p.relative_to(ROOT).as_posix()] = hits
    return found


def self_test() -> int:
    bad = "Machine class: Class II (per ISO 10816-3 Annex) zone B"
    good = "ISO 20816-3:2022 (formerly ISO 10816-3) groups machines above 15 kW"
    ok = bool(offenders(bad)) and not offenders(good) and not offenders("no standard here")
    print(("PASS" if ok else "FAIL") + " vibration-standard-attribution self-test")
    return 0 if ok else 1


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        return self_test()
    found = scan()
    print("vibration-standard-attribution - the Class I-IV zones are ISO 10816-1's; ISO 10816-3 appears only as ISO 20816-3's predecessor")
    if not found:
        print("PASS - no surface attributes the class zones to ISO 10816-3")
        return 0
    for f, hits in found.items():
        for h in hits[:3]:
            print(f"  {f}: ...{h}...")
    print(f"FAIL - {sum(len(h) for h in found.values())} bare 'ISO 10816-3' mention(s) in {len(found)} file(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
