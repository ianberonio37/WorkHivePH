#!/usr/bin/env python3
"""validate_device_clock_day.py - a ratchet on DEVICE-CLOCK day boundaries (2026-10-13).

WorkHive's day is the Philippine day: whFmtDate pins Asia/Manila, and a day in the data is the Manila day (migration
20261009000066). On 2026-10-13 four critique rows found code computing "today", "now", a greeting or "since midnight"
from the DEVICE clock instead: dayplanner (8 sites), hive (3), pm-scheduler's daysLabel and a stored project-link
label, and project-report's PDF name. Ian's own host runs on New Zealand time, so this is the owner's machine, not a
hypothetical. validate_one_clock_per_string only catches two clocks glued into ONE string; nothing stopped a new
device-clock boundary from landing. This is that lock.

Counted, in code with comments stripped, on every production page and the root shared scripts:
  P1  .setHours(0, 0, 0, 0)                          the device's midnight
  P2  .toISOString().slice(0, 10) / .split('T')[0]   UTC's calendar date, read as "today"
  P3  toLocaleDateString(...) with no timeZone        the device zone's date
  P4  new Date().getHours() / .getDay() / .getDate()  the device's hour, weekday or date of NOW
A line carrying `device-clock-allow: <why>` is not counted - for a site that really means the viewer's clock, or
local-field math on a date already shifted to Manila.

The baseline (device_clock_baseline.json) is the count per file today; a file whose count RISES fails. A fall is
progress: `--update` writes the lower count so it cannot climb back. `--report` lists every site.

  python tools/validate_device_clock_day.py [--report | --update | --self-test]
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "device_clock_baseline.json"
CHECK_NAMES = ["device-clock-day"]

PATTERNS = {
    "P1 device midnight": re.compile(r"\.setHours\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\)"),
    "P2 UTC date as today": re.compile(r"\.toISOString\(\)\s*\.\s*(?:slice|substring|substr)\(\s*0\s*,\s*10\s*\)"
                                       r"|\.toISOString\(\)\s*\.\s*split\(\s*['\"]T['\"]\s*\)\s*\[\s*0\s*\]"),
    "P3 date in the device zone": re.compile(r"toLocaleDateString\(\s*\)"
                                             r"|toLocaleDateString\(\s*(?:'[^']*'|\"[^\"]*\"|undefined)\s*\)"
                                             r"|toLocaleDateString\(\s*(?:'[^']*'|\"[^\"]*\"|undefined|\[[^\]]*\])\s*,\s*\{(?![^}]*timeZone)[^}]*\}\s*\)"),
    "P4 device hour/weekday/date of now": re.compile(r"new Date\(\s*\)\s*\.\s*get(?:Hours|Day|Date)\(\s*\)"),
    # SL C1 (2026-10-16): the differential walk read alert-hub's brief as "composed live 10:00 AM" on a Manila device and
    # "10:00 PM" on a New York one - toLocaleTimeString with no timeZone prints the DEVICE's time. 12 sites, now 0.
    "P5 time in the device zone": re.compile(r"toLocaleTimeString\(\s*\)"
                                             r"|toLocaleTimeString\(\s*(?:'[^']*'|\"[^\"]*\"|undefined|\[[^\]]*\])\s*\)"
                                             r"|toLocaleTimeString\(\s*(?:'[^']*'|\"[^\"]*\"|undefined|\[[^\]]*\])\s*,\s*\{(?![^}]*timeZone)[^}]*\}\s*\)"),
    # ...and a DATE-TIME: platform-actions' queues read "7/29/2026, AM" on a Manila device and "7/28/2026, PM" on a New
    # York one. Only `new Date(...).toLocaleString(` - a bare x.toLocaleString() is just as often a number. 9 sites, now 0.
    "P6 date-time in the device zone": re.compile(r"new Date\([^()]*(?:\([^()]*\)[^()]*)*\)\s*\.toLocaleString\("
                                                  r"(?:\s*\)|\s*(?:'[^']*'|\"[^\"]*\"|undefined|\[[^\]]*\])\s*\)"
                                                  r"|\s*(?:'[^']*'|\"[^\"]*\"|undefined|\[[^\]]*\])\s*,\s*\{(?![^}]*timeZone)[^}]*\}\s*\))"),
}
ALLOW = "device-clock-allow:"


def _strip_comments(src: str) -> str:
    """blank /* */ and // comments to spaces, keeping newlines, so a line number still points at the line.
    Strings are respected: a '//' inside a quoted URL is not a comment."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1; continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j])); i = j; continue
        if src.startswith("//", i) and (i == 0 or src[i - 1] != ":"):
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j; continue
        out.append(c); i += 1
    return "".join(out)


def _scripts_of(page_src: str) -> str:
    """an HTML page's inline <script> bodies, everything else blanked (newlines kept)"""
    out = re.sub(r"[^\n]", " ", page_src)
    chars = list(out)
    for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", page_src, re.I):
        a, b = m.span(1)
        chars[a:b] = page_src[a:b]
    return "".join(chars)


def _files() -> list[Path]:
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from seed_expansion_wave4 import LX_NON_PRODUCTION
    except Exception:
        LX_NON_PRODUCTION = set()
    pages = [p for p in sorted(ROOT.glob("*.html"))
             if p.name not in LX_NON_PRODUCTION and not re.search(r"-test\.html$|\.backup", p.name)]
    shared = [p for p in sorted(ROOT.glob("*.js")) if p.name not in ("sw.js",) and not p.name.endswith(".min.js")]
    return pages + shared


def sites(sources: dict | None = None) -> list[dict]:
    out = []
    for f in _files():
        raw = (sources or {}).get(f.name)
        if raw is None:
            raw = f.read_text(encoding="utf-8", errors="replace")
        code = _scripts_of(raw) if f.suffix == ".html" else raw
        code = _strip_comments(code)
        raw_lines = raw.split("\n")
        for kind, rx in PATTERNS.items():
            for m in rx.finditer(code):
                line = code.count("\n", 0, m.start()) + 1
                if ALLOW in (raw_lines[line - 1] if line - 1 < len(raw_lines) else ""):
                    continue
                out.append({"file": f.name, "line": line, "kind": kind, "text": raw_lines[line - 1].strip()[:140]})
    return out


def counts(found: list[dict]) -> dict:
    c = {}
    for s in found:
        c[s["file"]] = c.get(s["file"], 0) + 1
    return dict(sorted(c.items()))


def check(found: list[dict]) -> list[str]:
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    if base is None:
        return ["no baseline - run with --update once to record today's counts"]
    now = counts(found)
    return ["%s: %d device-clock day site(s), baseline %d" % (f, n, base.get(f, 0))
            for f, n in now.items() if n > base.get(f, 0)]


def main() -> int:
    found = sites()
    if "--report" in sys.argv:
        for s in found:
            print("%-28s %5d  %-36s %s" % (s["file"], s["line"], s["kind"], s["text"]))
        print("%d site(s) in %d file(s)" % (len(found), len(counts(found))))
        return 0
    if "--update" in sys.argv:
        had = BASELINE.exists()
        base = json.loads(BASELINE.read_text(encoding="utf-8")) if had else {}
        now = counts(found)
        # keyed on the FILE existing, not on the baseline being non-empty: at {} (every site cleared) a truthiness test
        # would have let --update record any rise as the new floor - the one moment the ratchet must be tightest
        rose = [f for f, n in now.items() if had and n > base.get(f, 0)]
        if rose:
            print("REFUSED: --update only records a FALL; these rose: " + ", ".join(rose))
            return 1
        BASELINE.write_text(json.dumps(now, indent=1) + "\n", encoding="utf-8")
        print("baseline written: %d site(s) in %d file(s)" % (len(found), len(now)))
        return 0
    bad = check(found)
    if bad:
        print("FAIL device-clock-day - a new day boundary reads the DEVICE clock (WorkHive's day is Asia/Manila; "
              "use whFmtDate / Intl timeZone 'Asia/Manila', or mark a real viewer-clock site device-clock-allow: <why>):")
        for b in bad:
            print("    " + b)
        return 1
    print("PASS device-clock-day - %d device-clock day site(s), none above the baseline (it only falls)." % len(found))
    return 0


def _inject(page_src: str, js: str) -> str:
    """a NEW inline <script> before </body>. The first version injected before the first </script>, which on
    pm-scheduler belongs to an external <script src> tag whose body the gate rightly ignores - so the resurrection
    never reached the counted code and the self-test failed for the wrong reason."""
    i = page_src.lower().rfind("</body>")
    return page_src[:i] + "<script>\n" + js + "\n</script>\n" + page_src[i:]


def self_test() -> int:
    fails = []
    found = sites()
    if check(found):
        fails.append("HEAD should PASS against its own baseline")
    # resurrection: pm-scheduler's pre-fix daysLabel cut both dates at the device's midnight
    pm = (ROOT / "pm-scheduler.html").read_text(encoding="utf-8", errors="replace")
    pre_fix = _inject(pm, "function daysLabelOld(d){ const t = new Date(); t.setHours(0,0,0,0); "
                          "const due = new Date(d); due.setHours(0,0,0,0); return (due - t) / 864e5; }")
    if not check(sites({"pm-scheduler.html": pre_fix})):
        fails.append("the pre-fix device-midnight daysLabel must redden")
    # every pattern bites on its own shape, and the Manila-pinned forms do not
    for kind, shape in (("P2 UTC date as today", "const name = 'report-' + new Date().toISOString().slice(0, 10);"),
                        ("P3 date in the device zone", "lbl = d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' });"),
                        ("P4 device hour/weekday/date of now", "const h = new Date().getHours();"),
                        ("P5 time in the device zone", "const _hm = _now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });"),
                        ("P6 date-time in the device zone", "' · filed ' + e(new Date(r.created_at).toLocaleString())")):
        if not PATTERNS[kind].search(shape):
            fails.append(kind + " must match its own shape")
    for shape in ("d.toLocaleDateString('en-PH', { timeZone: 'Asia/Manila', month: 'short' })",
                  "d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Manila' })",
                  "new Date(r.created_at).toLocaleString('en-PH', { timeZone: 'Asia/Manila' })",
                  "'₱' + Number(v).toLocaleString()",
                  "const h = Number(new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila', hour: '2-digit', hourCycle: 'h23' }))"):
        if any(rx.search(shape) for rx in PATTERNS.values()):
            fails.append("a Manila-pinned form must NOT match: " + shape[:60])
    # a comment that quotes the bad shape is not code
    commented = _inject(pm, "// was: t.setHours(0,0,0,0) - the device's midnight")
    if check(sites({"pm-scheduler.html": commented})):
        fails.append("a comment quoting the shape must not count")
    # an allow-marked line is not counted
    allowed = _inject(pm, "const x = new Date(); x.setHours(0,0,0,0); // device-clock-allow: test")
    if check(sites({"pm-scheduler.html": allowed})):
        fails.append("an allow-marked line must not count")
    if fails:
        print("SELF-TEST FAIL: " + "; ".join(fails))
        return 1
    print("PASS validate_device_clock_day self-test (pre-fix shape reddens; each pattern bites; Manila-pinned, "
          "commented and allow-marked forms do not)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
