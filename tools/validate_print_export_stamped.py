#!/usr/bin/env python3
"""print-export-stamped - SL C3 (2026-10-20): what a page prints or exports carries the time it was made and the period it
covers.

WHAT THE C3 WALK FOUND (receipts SL1829-SL1917: 88 pages - 27 production, 7 founder, 54 public - phone-390 and
desktop-1280, each as its row's cast; the page printed the way the browser prints - beforeprint, then print media - and
every Export / Download / CSV / Save as PDF / Print control pressed and its file, popup or printout read):
  * a page printed with Ctrl+P (or Share, then Print) carried no time and no period: the screen's "as of" line sits in the
    collapsed Sources area, and no page had a print header except logbook and audit-log - whose own stamp wrote
    "Printed:" with the time the page LOADED, so a printout made after lunch named the morning.
  * the CSV exports said "Exported: Oct 20, 2026, 02:55 PM" and never which clock (whFmtDate is Manila time); the skill
    matrix export and the project report export never said what period they covered.
  * the analytics report printed "Report Date: Oct 20, 2026" and asset-hub's reliability report "Generated: Oct 20,
    2026" - a day, never the moment - and the reliability report named its 365-day window only deep in its body.

WHAT THIS HOLDS (static; the walk is the live floor):
  1. one print stamp, in utils.js (app pages) and wh-feedback-fab.js (public pages), guarded to one per page, written at
     the MOMENT of printing (beforeprint and the print media query): the title, the hive and who printed it when signed
     in, "Printed: <date time> PHT", and "Covers:" - a guide's latest dated byline (Updated before Published), a
     calculator's inputs, or the moment the page's figures were last read (utils.js records it on every good read);
     a layout with its own header ([data-wh-print-own]) keeps it; logbook and audit-log no longer stamp the load time;
  2. every served page loads one of the two scripts (promo-poster excepted: a poster is printed as artwork);
  3. the exports say "PHT"; skill matrix says what it covers; the project export carries the project's period; the
     analytics report and the reliability report print the time they were generated, and the reliability report what
     it covers.

    python tools/validate_print_export_stamped.py
    python tools/validate_print_export_stamped.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STAMP_FILES = ("utils.js", "wh-feedback-fab.js")
# the stamp's load-bearing lines, each required in BOTH shared scripts
STAMP_ANCHORS = [
    (r"\(function whPrintStamp\(\) \{", "the print stamp is gone"),
    (r"window\.__whPrintStamp\) return;\s*window\.__whPrintStamp = true;", "two copies of the stamp can both install on one page"),
    (r"window\.addEventListener\('beforeprint', write\);", "the stamp is no longer written at the moment of printing"),
    (r"window\.matchMedia && window\.matchMedia\('print'\)", "the stamp misses a print that fires only the print media query"),
    (r"bits\.push\('Printed: ' \+ PHT\(new Date\(\)\)\);", "the stamp no longer names the time of printing (in PHT)"),
    (r"if \(c\) bits\.push\('Covers: ' \+ c\);", "the stamp no longer says what the printout covers"),
    (r"\\\\b\(Last updated\|Last reviewed\|Updated\)\\\\b", "a revised guide prints its first publication date instead of its latest revision"),
    (r"return at \? 'figures as of ' \+ PHT\(new Date\(at\)\)", "an app page's printout no longer says when its figures were read"),
    (r"var own = document\.querySelector\('\[data-wh-print-own\]'\);", "a formal report's own header is duplicated by the stamp"),
]
ANCHORS = [
    ("utils.js", r"window\.__whLastReadAt = Date\.now\(\);", "the stamp cannot know when the page's figures were last read"),
    ("logbook.html", r'<div id="wh-print-stamp" style="display:none;"></div>', "logbook lost the stamp's place at the top of the page"),
    ("audit-log.html", r'<div id="wh-print-stamp" style="display:none;"></div>', "audit-log lost the stamp's place at the top of the page"),
    ("logbook.html", r"`Exported: \$\{whFmtDate\(new Date\(\)\.toISOString\(\), \{ time: true \}\)\} PHT`", "logbook's export does not name its clock"),
    ("skillmatrix.html", r"'Covers: levels and targets as they stand at the export time; badges earned all time'", "the skill matrix export does not say what it covers"),
    ("project-report.html", r"'Period: ' \+ \(p\.start_date && p\.end_date", "the project export does not carry the project's period"),
    ("project-report.html", r'class="doc-cover" data-wh-print-own', "the project report's cover is duplicated by the shared stamp"),
    ("analytics-report.html", r"function fmtDateTime\(d\)", "the analytics report cannot print a time"),
    ("analytics-report.html", r"'<div><b>Generated:</b> ' \+ escHtml\(fmtDateTime\(", "the analytics report's cover prints a day, never the moment"),
    ("asset-hub.html", r"<div><strong>Generated:</strong> \$\{esc\(today\.toLocaleString\('en-PH', \{ timeZone: 'Asia/Manila', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' \}\)\)\} PHT</div>",
     "the reliability report prints a day, never the moment"),
    ("asset-hub.html", r"<div><strong>Covers:</strong> corrective events of the last 365 days", "the reliability report's header does not say what it covers"),
]
# a page-local stamp that writes the LOAD time as "Printed:" must not come back
FORBIDDEN = [
    ("logbook.html", r"var when = new Date\(\)\.toLocaleString\('en-PH'", "logbook stamps the load time as 'Printed:' again"),
    ("audit-log.html", r"var when = new Date\(\)\.toLocaleString\('en-PH'", "audit-log stamps the load time as 'Printed:' again"),
]
EXPORTERS = ("analytics-report.html", "asset-hub.html", "integrations.html", "inventory.html", "project-report.html", "skillmatrix.html")
EXPORT_LINE = re.compile(r"'Exported: ' \+ \(typeof whFmtDate === 'function' \? whFmtDate\(new Date\(\)\.toISOString\(\), \{ time: true \}\)( \+ ' PHT')? :")
NO_STAMP_OK = {"promo-poster.html": "a marketing poster is printed as artwork - a 'Printed:' header would deface it"}


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


def served_pages(root: Path) -> list[Path]:
    pages = list(root.glob("*.html")) + list(root.glob("*/index.html")) + list((root / "learn").glob("*/index.html")) + list((root / "tools").glob("*/index.html"))
    return sorted(set(pages))


def problems(files: dict[str, str], pages: dict[str, str]) -> list[str]:
    bad = []
    for f in STAMP_FILES:
        code = _code(files.get(f, ""))
        for rx, why in STAMP_ANCHORS:
            if not re.search(rx, code):
                bad.append(f"{f}: {why}")
    for f, rx, why in ANCHORS:
        if not re.search(rx, files.get(f, "") if rx.startswith("<div id") or "class=" in rx else _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    for f, rx, why in FORBIDDEN:
        if re.search(rx, _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    for f in EXPORTERS:
        for m in EXPORT_LINE.finditer(_code(files.get(f, ""))):
            if not m.group(1):
                bad.append(f"{f}: an export stamps its time without naming the clock (PHT)")
    for name, src in pages.items():
        if name in NO_STAMP_OK:
            continue
        if "utils.js" not in src and "wh-feedback-fab.js" not in src:
            bad.append(f"{name}: loads neither utils.js nor wh-feedback-fab.js - its printout carries no stamp")
    return bad


def load():
    names = set(STAMP_FILES) | {a[0] for a in ANCHORS} | {b[0] for b in FORBIDDEN} | set(EXPORTERS)
    files = {f: (ROOT / f).read_text(encoding="utf-8") for f in sorted(names)}
    pages = {str(p.relative_to(ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8", errors="replace") for p in served_pages(ROOT)}
    return files, pages


def run() -> int:
    files, pages = load()
    bad = problems(files, pages)
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL print-export-stamped - {len(bad)} problem(s)")
        return 1
    print(f"PASS print-export-stamped - one print stamp written at the moment of printing (time in PHT and what it covers) "
          f"on all {len(pages) - len(NO_STAMP_OK)} served pages, the exports name their clock and their period, and the two "
          f"formal reports print their generation time; {len(STAMP_ANCHORS)}x2 + {len(ANCHORS)} anchors hold")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    files, pages = load()
    expect("the real tree passes", not problems(files, pages))

    def mut(f, a, b, prefix=None):
        m = dict(files)
        assert a in m[f], (f, a[:60])
        m[f] = m[f].replace(a, b, 1)
        return bool([x for x in problems(m, pages) if x.startswith((prefix or f) + ":")])
    expect("the stamp written at load instead of at print fails", mut("utils.js",
        "window.addEventListener('beforeprint', write);", "write();"))
    expect("the public copy losing its print time fails", mut("wh-feedback-fab.js",
        "bits.push('Printed: ' + PHT(new Date()));", "bits.push('Printed');"))
    expect("the stamp losing what it covers fails", mut("utils.js", "if (c) bits.push('Covers: ' + c);", ""))
    expect("the read moment no longer recorded fails", mut("utils.js",
        "window.__whLastReadAt = Date.now();", "void 0;"))
    expect("an export without PHT fails", mut("inventory.html",
        "whFmtDate(new Date().toISOString(), { time: true }) + ' PHT' :", "whFmtDate(new Date().toISOString(), { time: true }) :"))
    expect("the reliability report back to a bare day fails", mut("asset-hub.html",
        "year: 'numeric', hour: '2-digit', minute: '2-digit' }))} PHT</div>", "year: 'numeric' }))}</div>"))
    expect("the project export without its period fails", mut("project-report.html",
        "'Period: ' + (p.start_date && p.end_date", "'X: ' + (p.start_date && p.end_date"))
    m = dict(files)
    m["logbook.html"] = m["logbook.html"].replace('<div id="wh-print-stamp" style="display:none;"></div>',
        '<div id="wh-print-stamp" style="display:none;"></div>\n<script>var when = new Date().toLocaleString(\'en-PH\');</script>', 1)
    expect("a load-time page stamp coming back fails", any(x.startswith("logbook.html:") for x in problems(m, pages)))
    p2 = dict(pages)
    p2["new-page.html"] = "<html><body><script src='other.js'></script></body></html>"
    expect("a NEW page with neither stamp script fails", any(x.startswith("new-page.html:") for x in problems(files, p2)))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
