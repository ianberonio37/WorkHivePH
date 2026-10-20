#!/usr/bin/env python3
"""period-stated - SL C2 (2026-10-20): every figure states the period, window or moment it belongs to.

WHAT THE C2 WALK FOUND (receipts SL1671-SL1828: 155 pages - 27 production, 9 founder, 119 public - phone-390 and
desktop-1280, each as its row's cast; every visible figure read with its OWN statement - its sentence, its tile, the
heading over its card - and its per-figure reveal):
  * pm-scheduler counted "due soon" over the next 14 days (the view's is_due_soon) and the tile said "(14d)", but the
    line under it said "N assets need PM this week", the verdict said "due this week" and "to schedule this week", and
    the figure registry said "seven days" - a planner reading one week left the second out.
  * pm-scheduler's compliance figure is the SMRP figure over the rolling 90 days, or - when that read is unavailable -
    the share of assets on track right now; the verdict line never said which.
  * running totals read as if they were this period's: logbook's "Jobs closed out 2274 of 2277" (every entry you have
    logged), community's "Posts" and "Community XP", achievements' "jobs done" (the provider tier's lifetime count).
  * analytics' eleven tile figures said "over the period" and never named it; the 88 per-figure reveals (SL D1) said
    where a figure came from and never when.
  * design-system's specimens show numbers (27 open jobs, an MTBF of 6.4d) that are samples and never said so.

WHAT THIS HOLDS (static; the walk is the live floor):
  1. every figure_sources.json entry names its period (render_figure_sources.py refuses one without), and the reveal
     card shows it as a Period row; a tile drawn by the shared renderer carries data-wh-fig-period;
  2. analytics' tile figures carry the window the reader picked, rolling to now (and the two forecasts say "from today");
  3. pm-scheduler says "the next 14 days" wherever it counts due-soon, and names its compliance window;
  4. the running totals say "all time" / "so far"; design-system says its specimens' numbers are samples.

    python tools/validate_period_stated.py
    python tools/validate_period_stated.py --self-test
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

ANCHORS = [
    ("utils.js", r"\(entry\.period \? row\('Period', escHtml\(entry\.period\)\) : ''\)",
     "the per-figure reveal no longer says which period a figure belongs to"),
    ("utils.js", r"data-wh-fig-period=", "a tile drawn by the shared renderer cannot carry its period"),
    ("utils.js", r"period: box\.getAttribute\('data-wh-fig-period'\)", "the reveal ignores a tile's stated period"),
    ("tools/render_figure_sources.py", r'"period" in|e\.get\("period"\)', "the registry no longer refuses an entry without a period"),
    ("analytics.html", r"figure: \{ period: `The last \$\{_period\} days, rolling to now`",
     "analytics' tile figures say 'over the period' without naming it"),
    ("analytics.html", r"figure: \{ period: 'From today: counted forward from the last breakdown'",
     "the failure forecast does not say it counts forward from today"),
    ("pm-scheduler.html", r"PM in the next 14 days`", "the due-soon line no longer says the 14 days it counts"),
    ("pm-scheduler.html", r"const compWin = pmSmrpCompliance != null \? 'last 90 days' : 'on track now';",
     "the compliance figure no longer says whether it is the 90-day SMRP figure or the on-track share now"),
    ("pm-scheduler.html", r"\$\{duesoon\} due in the next 14 days", "the verdict's due-soon count lost its window"),
    ("logbook.html", r"whProgressStrip\('Jobs closed out, all time'", "logbook's closed-out strip reads as this period's"),
    ("logbook.html", r"whProgressStrip\('Team jobs closed out, all time'", "the team strip reads as this period's"),
    ("community.html", r">Posts so far</p>", "community's post count reads as this period's"),
    ("community.html", r">Community XP so far</p>", "community's XP reads as this period's"),
    ("achievements.html", r"'jobs done so far'", "the provider tier's job count reads as this period's"),
    ("design-system.html", r'id="ds-root" data-wh-sample=', "design-system's specimens do not mark their numbers as samples"),
    ("design-system.html", r"are sample values, not anyone's data", "design-system never says its specimens' numbers are samples"),
]
FORBIDDEN = [
    ("pm-scheduler.html", r"PM this week`", "the due-soon line says 'this week' for a 14-day window"),
    ("pm-scheduler.html", r"'BUSY WEEK'", "the due-soon pill says 'week' for a 14-day window"),
    ("pm-scheduler.html", r"\$\{duesoon\} due this week", "the verdict says 'due this week' for a 14-day window"),
    ("pm-scheduler.html", r"to schedule this week", "the verdict says 'this week' for a 14-day window"),
]


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


def registry_problems(reg: dict) -> list[str]:
    bad = []
    for page, ents in reg.items():
        if page.startswith("_"):
            continue
        for e in ents:
            if e.get("chrome"):
                continue
            if not str(e.get("period") or "").strip():
                bad.append(f"figure_sources.json: {page} {e.get('sel')!r} names no period")
            if re.search(r"next seven days", str(e.get("basedOn") or ""), re.I):
                bad.append(f"figure_sources.json: {page} {e.get('sel')!r} says seven days for a 14-day window")
    return bad


def tile_figures_without_period(name: str, src: str) -> list[str]:
    """Every figure a page hands the shared tile renderer (figure: { ... }) names its period - one dropped is a fail."""
    out = []
    for m in re.finditer(r"figure:\s*\{([^}]*)\}", _code(src)):
        if "period:" not in m.group(1):
            out.append(f"{name}: a tile figure names no period ({m.group(1).strip()[:60]})")
    return out


def problems(files: dict[str, str], reg: dict) -> list[str]:
    bad = []
    for f, src in files.items():
        if f.endswith(".html") and "figure: {" in src:
            bad.extend(tile_figures_without_period(f, src))
    for f, rx, why in ANCHORS:
        src = files.get(f, "")
        if not re.search(rx, _code(src) if f.endswith((".js", ".html")) else src):
            bad.append(f"{f}: {why}")
    for f, rx, why in FORBIDDEN:
        if re.search(rx, _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    return bad + registry_problems(reg)


def load():
    names = {a[0] for a in ANCHORS} | {b[0] for b in FORBIDDEN}
    names |= {q.name for q in ROOT.glob("*.html") if "figure: {" in q.read_text(encoding="utf-8", errors="replace")}
    files = {f: (ROOT / f).read_text(encoding="utf-8") for f in sorted(names)}
    reg = json.loads((ROOT / "figure_sources.json").read_text(encoding="utf-8"))
    return files, reg


def run() -> int:
    files, reg = load()
    bad = problems(files, reg)
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL period-stated - {len(bad)} problem(s)")
        return 1
    n = sum(1 for p, es in reg.items() if not p.startswith("_") for e in es if not e.get("chrome"))
    print(f"PASS period-stated - all {n} registered figures name their period and the reveal shows it; analytics names its "
          f"window, pm-scheduler its 14 days and its compliance window, the running totals say all time, and design-system "
          f"says its specimens are samples; {len(ANCHORS)} anchors hold")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    files, reg = load()
    expect("the real tree passes", not problems(files, reg))

    def mut(f, a, b):
        m = dict(files)
        assert a in m[f], (f, a[:60])
        m[f] = m[f].replace(a, b, 1)
        return bool([x for x in problems(m, reg) if x.startswith(f + ":")])
    expect("the reveal without its Period row fails", mut("utils.js",
        "(entry.period ? row('Period', escHtml(entry.period)) : '') +", ""))
    expect("'this week' back on the due-soon line fails", mut("pm-scheduler.html", "PM in the next 14 days`", "PM this week`"))
    expect("the compliance window removed fails", mut("pm-scheduler.html",
        "const compWin = pmSmrpCompliance != null ? 'last 90 days' : 'on track now';", "const compWin = '';"))
    expect("logbook's strip without 'all time' fails", mut("logbook.html",
        "whProgressStrip('Jobs closed out, all time'", "whProgressStrip('Jobs closed out'"))
    expect("community's posts without 'so far' fails", mut("community.html", ">Posts so far</p>", ">Posts</p>"))
    expect("analytics' window removed fails", mut("analytics.html",
        "figure: { period: `The last ${_period} days, rolling to now`, ", "figure: { "))
    expect("design-system's sample mark removed fails", mut("design-system.html", 'id="ds-root" data-wh-sample=', 'id="ds-root" data-x='))
    r2 = json.loads(json.dumps(reg))
    first = next(p for p in r2 if not p.startswith("_"))
    victim = next(e for e in r2[first] if not e.get("chrome"))
    victim.pop("period", None)
    expect("a registry entry without a period fails", bool(registry_problems(r2)))
    r3 = json.loads(json.dumps(reg))
    r3["pm-scheduler.html"][1]["basedOn"] = "scope items due within the next seven days"
    expect("'seven days' back in the registry fails", bool(registry_problems(r3)))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
