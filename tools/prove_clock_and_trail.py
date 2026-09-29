#!/usr/bin/env python3
"""prove_clock_and_trail.py — two W3-AR questions a file can answer, so an outage does not block them.

Layer C — **which clock and which period do these figures belong to?** A number without a window is a claim
without a subject: "142 work orders" means nothing until the page says whether that is today, this month, or
since the hive opened, and in whose timezone. This reads the page for a stated PERIOD and a stated CLOCK.

Layer L — **does the page record who did what, in a trail somebody can read?** A page that writes anything a
colleague can see owes an entry somebody can go back to. This reads the page's own write paths and asks
whether they reach the audit trail.

★AND IT READS THE FILE, NOT THE BROWSER, DELIBERATELY. A rendered check was tried first and read the
SIGN-IN DOOR for every page that needs an identity - resume, skillmatrix and project-report all came back at
~14,700 characters carrying "this year" and "PHT", which are the door's words, not theirs. The three pages
that genuinely load (status, public-feed, marketplace) confirmed the static reading exactly. So the file is
the honest source here: it is the same bytes whether or not anyone is signed in. The known limit is a period
injected at runtime, which a static read cannot see - so a BAD verdict here HOLDS the row rather than closing
it, and the row waits for a walk with an identity.

★A KEYWORD IS NOT A CLAIM, which is the mistake this file is built to avoid. "Updated" in a sentence about a
supervisor reviewing a brief is not a freshness line; "today" inside the word "todays" is not a period; and a
page that merely mentions `audit_log` in a comment records nothing. So a period must appear with a figure or
a label near it, a clock must be named as a timezone rather than guessed from the word "time", and an audit
claim must come from a call, not a mention. Every verdict prints the exact text it matched.

  python tools/prove_clock_and_trail.py
  python tools/prove_clock_and_trail.py --json .tmp/clock_and_trail.json
  python tools/prove_clock_and_trail.py --self-test
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# the ONE static-document test every layer gate shares (tools/page_kind.py, the rubric's _noDataClient rule)
import sys as _sys
_sys.path.insert(0, str(ROOT / 'tools'))
from page_kind import is_static_doc as _is_static_doc  # noqa: E402

REGISTRY = ROOT / "trajectory_registry.json"
CLOCK_MARK = "which clock and which period"
TRAIL_MARK = "record who did what"

STRIP = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
TAGS = re.compile(r"<[^>]+>")

# a PERIOD names the span the figures cover - as a label a reader sees, not a stray word
PERIOD = re.compile(
    r"\b(last|past|previous|this|next)\s+(7|14|30|60|90|\d{1,3})?\s*(day|days|week|weeks|month|months|year|years|hours|hrs)\b"
    r"|\b(today|yesterday|this week|this month|this year|month[- ]to[- ]date|year[- ]to[- ]date|ytd|mtd)\b"
    r"|\b(since|between|from)\s+\w+\s+\d{1,2}\b"
    r"|\b(all[- ]time|lifetime|rolling\s+\d+)\b", re.I)
# a CLOCK names the timezone or the reference the times are given in
CLOCK = re.compile(
    r"\b(UTC|GMT|PHT|PST|Asia/Manila|Manila time|local time|your time|server time|"
    r"philippine (?:standard )?time|UTC[+\-]\d|GMT[+\-]\d)\b", re.I)
# an audit claim has to be a CALL, not a mention
TRAIL_CALL = re.compile(
    r"(audit_log|auditLog|writeAudit|logAudit|record_action|wh_audit)\s*[\(\.]"
    r"|from\(\s*['\"]audit_log['\"]\s*\)"
    r"|rpc\(\s*['\"][a-z_]*audit[a-z_]*['\"]", re.I)


def rows(mark: str) -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if t.get("status") == "specced" and mark in (t.get("title") or "")]


def page_text(page: str) -> str:
    p = ROOT / page
    if not p.exists():
        return ""
    raw = p.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", TAGS.sub(" ", STRIP.sub(" ", raw)))


def page_source(page: str) -> str:
    """The page and the scripts it loads from this repo - a write path usually lives in a sibling file."""
    p = ROOT / page
    if not p.exists():
        return ""
    raw = p.read_text(encoding="utf-8", errors="replace")
    out = [raw]
    for src in re.findall(r'<script[^>]+src="([^"]+\.js)"', raw):
        if src.startswith("http"):
            continue
        f = ROOT / src.split("?")[0].lstrip("/")
        if f.exists():
            out.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def main() -> int:
    if "--self-test" in sys.argv:
        fails = []
        if PERIOD.search("todays plan"):
            fails.append("'todays' is matching as the period 'today'")
        if not PERIOD.search("last 30 days"):
            fails.append("'last 30 days' is not read as a period")
        if not CLOCK.search("times shown in Asia/Manila"):
            fails.append("'Asia/Manila' is not read as a clock")
        if CLOCK.search("response time"):
            fails.append("the word 'time' alone is being read as a clock")
        if TRAIL_CALL.search("// writes to audit_log eventually"):
            fails.append("a comment mentioning audit_log counts as a trail")
        if not TRAIL_CALL.search("await db.from('audit_log').insert(row)"):
            fails.append("a real audit_log insert is not recognised")
        print("FAIL clock-and-trail self-test - " + "; ".join(fails) if fails
              else "self-test OK: 6 mutations, each caught - a keyword alone never counts as a claim")
        return 1 if fails else 0

    out = []
    for t in rows(CLOCK_MARK):
        page = (t.get("pages") or [""])[0]
        txt = page_text(page)
        per, clk = PERIOD.search(txt), CLOCK.search(txt)
        if not txt:
            v, line = "n/a", f"{page} could not be read from disk"
        # ★A STATIC DOCUMENT'S FIGURES ARE ILLUSTRATIONS, NOT MEASUREMENTS (Wave 4, 2026-09-14). The wave seeded
        # a Cloud & Compute story for every served page and this lens graded 54 learn articles "no stated
        # period/clock - its figures have no window a reader can check". An article's "MTBF 1,200 h" is a
        # worked example about nobody's plant; the period-and-clock claim belongs to LIVE figures. The rubric's
        # own static-document rule (tools/page_kind.py) draws the line; status.html and every DB page stay graded.
        elif _is_static_doc(page):
            v, line = "n/a", f"{page} ships no data client - its figures are illustrations, not a live window"
        # ★A PAGE WITH NO FIGURES HAS NO WINDOW TO STATE (2026-09-14, feedback/index.html under wave 4): a form
        # that collects feedback shows a reader no numbers, so "which period do these figures belong to" has
        # no subject. Measured on the visible text: fewer than five numeric tokens is a page without figures.
        elif len(re.findall(r"(?<![\w/.-])\d[\d,]*(?:\.\d+)?(?![\w/.-])", txt)) < 5:
            v, line = "n/a", f"{page} shows no figures (a form or a notice) - there is no window for a reader to check"
        elif per and clk:
            v, line = "ok", f'names its period ("{per.group(0)[:26]}") and its clock ("{clk.group(0)[:20]}")'
        else:
            miss = [x for x, ok in (("no stated period", per), ("no stated clock", clk)) if not ok]
            v, line = "BAD", f"{', '.join(miss)} - its figures have no window a reader can check"
        out.append({"id": t["id"], "page": page, "verdict": v, "line": line, "wave": t.get("wave")})

    for t in rows(TRAIL_MARK):
        page = (t.get("pages") or [""])[0]
        src = page_source(page)
        m = TRAIL_CALL.search(src)
        if not src:
            v, line = "n/a", f"{page} could not be read from disk"
        elif _is_static_doc(page):
            v, line = "n/a", f"{page} ships no data client - it writes nothing, so there is no trail to leave"
        elif m:
            v, line = "ok", f'writes to the trail ("{m.group(0)[:34]}")'
        # ★SOME WRITES ARE THEMSELVES THE RECORD (2026-09-14, feedback/index.html under wave 4): a page whose
        # only write is a feedback / vote / log row is leaving exactly the trail the lens asks for - the row
        # says who, what and when. Demanding a second audit row for the act of writing the first would be a
        # trail of the trail. Only self-recording tables qualify; a write to a working table still owes one.
        elif (sm := re.search(r"\.from\(\s*['\"]([a-z0-9_]*(?:feedback|_votes|_log|audit|_events|_attempts)[a-z0-9_]*)['\"]\s*\)"
                              r"[\s\S]{0,300}?\.(?:insert|upsert)\s*\(", src)
              or re.search(r"\.rpc\(\s*['\"]([a-z0-9_]*(?:vote|feedback|audit|_log)[a-z0-9_]*)['\"]", src)):
            v, line = "ok", f'its write is itself the record ("{sm.group(1)}")'
        else:
            v, line = "BAD", "nothing in this page or the scripts it loads writes to the audit trail"
        out.append({"id": t["id"], "page": page, "verdict": v, "line": line, "wave": t.get("wave")})

    bad = sum(1 for r in out if r["verdict"] == "BAD")
    print(f"rows answered from files: {len(out)}  ({len(out) - bad} hold, {bad} findings)")
    for r in out:
        print(f"  {'ok ' if r['verdict'] == 'ok' else r['verdict']} {r['id']:8} {r['page'][:32]:34} {r['line'][:88]}")
    if "--json" in sys.argv:
        dest = sys.argv[sys.argv.index("--json") + 1]
        Path(dest).parent.mkdir(exist_ok=True)
        Path(dest).write_text(json.dumps({"results": out}, indent=1), encoding="utf-8")
        print(f"\n  {dest}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
