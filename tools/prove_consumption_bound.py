#!/usr/bin/env python3
"""prove_consumption_bound.py — W3-AR layer RL: does this page bound what it loads, and SAY SO when it has?

Eleven pages carry this row. It has two halves and the second is the one that bites:

  BOUND   the page limits what it fetches — `.limit(n)`, `.range(a, b)`, a page size, a cap constant.
          An unbounded read of a table that grows is a page that gets slower every month and then stops.

  SAY SO  ★A CAP SHOWN AS A TOTAL IS A LIE THE PAGE TELLS QUIETLY. A page that fetches 200 rows and prints
          "200 items" tells a supervisor their hive has 200 when it has 4,000 - and every number computed
          from that list is wrong in the same direction. A bounded page owes the reader a word: "showing the
          most recent 200", "first 100 of 4,312", a "load more" control, a note beside the count.

Answered from the page and the scripts it loads, so it survives an outage and needs no identity.

  python tools/prove_consumption_bound.py
  python tools/prove_consumption_bound.py --json .tmp/consumption_bound.json
  python tools/prove_consumption_bound.py --self-test
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# the ONE static-document test every layer gate shares (tools/page_kind.py, the rubric's _noDataClient rule)
import sys as _sys
_sys.path.insert(0, str(ROOT / 'tools'))
from page_kind import is_static_doc as _is_static_doc  # noqa: E402

REGISTRY = ROOT / "trajectory_registry.json"
MARK = "bound what this page can consume"

# a real bound on what is fetched
BOUND = re.compile(r"\.limit\(\s*\d+|\.range\(\s*\d+\s*,|PAGE_SIZE|pageSize|LIMIT\s*=\s*\d+|"
                   r"MAX_ROWS|ROW_CAP|\blimit:\s*\d+|\?limit=\d+", re.I)
# telling the reader the list is bounded: a phrase, a control, or a note beside the count
SAYS = re.compile(r"(showing\s+(?:the\s+)?(?:first|most recent|latest|top)\b|first\s+\d+\s+of\b|"
                  r"most recent\s+\d+|load\s*more|show\s*more|see\s*all\b|view\s*all\b|"
                  r"newest\s+\d+|capped\s+at|up\s+to\s+\d+\s+(?:rows|items|entries)|"
                  r"only\s+the\s+(?:first|latest|most recent))", re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)
# the platform's own words for "this ceiling is insurance, not a display slice"
INSURANCE = re.compile(r"insurance cap|cap-ok|bounded-by-nature|bounded by nature|never truncates|"
                       r"limit-as-count-allow", re.I)


def rows() -> list[dict]:
    # ★THE ROSTER IS THE CLAIM, NOT ITS STATE. Filtering to `specced` meant that once a row was banked this
    # prover could never look at it again - so the twenty rows already banked on the file-only reading were
    # invisible to the very check that could tell whether their cap is being exceeded TODAY.
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"] if MARK in (t.get("title") or "")]


# ★"THE DAY THE DATA PASSES THE CAP" IS A DATE, AND IT MAY ALREADY HAVE PASSED. The file-only reading can
# see that a page caps at 200 and says nothing about it; it cannot see whether any hive already holds 4,000
# rows, which is the difference between a risk and a page that is lying to somebody this morning. That is
# why the live-walk ledger names postgres as the instrument these rows need.
CAP_CALL = re.compile(r"\.from\(\s*['\"`]([a-z0-9_]+)['\"`]\s*\)(.{0,900}?)\.limit\(\s*(\d+)\s*\)", re.S | re.I)
_biggest: dict = {}


def biggest_hive(table: str) -> int | None:
    """The largest number of rows any one hive holds in this table, or None if it cannot be read."""
    if table in _biggest:
        return _biggest[table]
    sql = (f"select coalesce(max(c), 0) from (select count(*) c from {table} "
           f"group by hive_id) t")
    val = None
    for _ in range(3):
        try:
            out = subprocess.run(
                ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres",
                 "-d", "postgres", "-tA", "-c", sql],
                capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            txt = (out.stdout or "").strip()
            if txt.isdigit():
                val = int(txt)
                break
        except Exception:
            pass
    _biggest[table] = val
    return val


# a filter that NARROWS the read to something a whole-table count cannot stand for
WINDOWED = re.compile(r"\.gte\(|\.lte\(|\.gt\(|\.lt\(|\.in\(|\.ilike\(|\.like\(|\.neq\(|\.or\(|"
                      r"\.eq\(\s*['\"`](?!hive_id)", re.I)


def capped_reads(src: str) -> list[tuple[str, int]]:
    """Every (table, cap) this page reads with an explicit row limit — and NOT narrowed to a window.

    ★COMPARE LIKE WITH LIKE, OR THE NUMBER MEANS NOTHING. `plant-connections.html` caps its request-audit
    panel at 50 and filters it to the LAST SEVEN DAYS. Measured against the whole table, one hive holds 164
    and the cap looked long since passed; measured inside the page's own window, the largest any hive holds
    is ZERO. The page had even said so in a comment ("cap-ok: rows only"), and the finding was still filed.
    A cap on a windowed read cannot be judged by a whole-table count, so those reads are not claimed about
    at all rather than claimed about wrongly.
    """
    out = []
    for m in CAP_CALL.finditer(COMMENT.sub(" ", src)):
        table, chain, cap = m.group(1), m.group(2), int(m.group(3))
        if cap > 0 and not WINDOWED.search(chain):
            out.append((table, cap))
    return sorted(set(out))


def summed_caps(src: str) -> list[tuple[str, int, str]]:
    """Capped reads whose rows are SUMMED — the case a window does not rescue.

    ★A CAP ON A LIST IS A SHORT LIST; A CAP ON A SUM IS A WRONG NUMBER. capped_reads() above deliberately
    skips windowed reads, and that is right for a LIST: judging a 7-day cap against a whole-table count is
    the compare-like-with-like error it was written to avoid. It is wrong for an AGGREGATE, because the
    window is exactly what the sum is taken over - so a `.gte(since).limit(1000)` feeding a `.reduce()`
    undercounts inside its own window and says nothing about it.

    Found on achievements.html 2026-09-09: the weekly-XP tile selected `xp_earned` under a 7-day window
    capped at 1000 and reduced it into the headline number. The page had already been bitten by the same
    shape once - the comment above the query explains the dedicated query exists BECAUSE deriving the week
    from a 30-row list undercounted a busy worker - and the replacement reintroduced it at 1000. This
    prover missed it twice over: BOUND matched the page's first cap (`.limit(3`) and the aggregate read was
    filtered out for being windowed.

    Matched by co-occurrence rather than by tracing dataflow: a capped read that SELECTS a column, and a
    `.reduce(` somewhere in the same file that reads that column off its accumulator argument. Narrow on
    purpose - it wants the column named in both places, so an unrelated reduce cannot raise it.
    """
    body = COMMENT.sub(" ", src)
    # `.{0,160}?` rather than `[^)]{0,120}?`: the accumulator's own parameter list closes a paren before
    # the column is ever reached - `.reduce((s, r) => s + (Number(r.xp_earned) || 0), 0)` - so a
    # no-close-paren scan stops at `(s, r` and finds nothing. It cost the detector its only real target.
    reduced = set(re.findall(r"\.reduce\s*\(.{0,160}?\b\w+\s*\.\s*([a-z0-9_]+)", body, re.I | re.S))
    if not reduced:
        return []
    out = []
    for m in re.finditer(
        r"\.from\(\s*['\"`]([a-z0-9_]+)['\"`]\s*\)\s*\.select\(\s*['\"`]([^'\"`]{1,200})['\"`]\s*\)(.{0,900}?)\.limit\(\s*(\d+)\s*\)",
        body, re.S | re.I,
    ):
        table, cols, _chain, cap = m.group(1), m.group(2), m.group(3), int(m.group(4))
        for col in (c.strip() for c in cols.split(",")):
            if col and col in reduced:
                out.append((table, cap, col))
                break
    return sorted(set(out))


def visible_text(page: str) -> str:
    """What a reader is actually told — the page's own markup with scripts, styles and tags removed.

    ★A CODE IDENTIFIER IS NOT A SENTENCE. Searching the concatenated JavaScript for "says so" phrases matched
    `viewall`, `loadMore` and `see all` inside variable names and i18n keys, and eleven of eleven pages passed
    on identifiers no reader will ever see. The bound lives in the code; the TELLING has to live where a
    person can read it, so the two halves are searched in two different places on purpose.
    """
    p = ROOT / page
    if not p.exists():
        return ""
    raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", p.read_text(encoding="utf-8", errors="replace"),
                 flags=re.I | re.S)
    raw = COMMENT.sub(" ", raw)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))


def source_of(page: str) -> str:
    """The page plus the local scripts it loads - the fetch usually lives in a sibling file."""
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
        if not BOUND.search("await db.from('logbook').select('*').limit(200)"):
            fails.append("a .limit() is not read as a bound")
        if not BOUND.search("const PAGE_SIZE = 50;"):
            fails.append("a page size is not read as a bound")
        if BOUND.search("element.limitations"):
            fails.append("an ordinary word containing 'limit' counts as a bound")
        if not SAYS.search("Showing the most recent 200 entries"):
            fails.append("a real cap note is not recognised")
        if not SAYS.search("Load more"):
            fails.append("a load-more control is not recognised")
        if SAYS.search("200 entries"):
            fails.append("a bare count is being read as a cap note")
        # (*)AN EMPTY ROSTER IS SUCCESS, NOT FAILURE. Asserting that open rows exist makes the gate go red
        # the moment its work is done. A teeth test proves the LENS can tell right from wrong; whether
        # anything is left to answer is a different question and not this one.
        print("FAIL consumption-bound self-test - " + "; ".join(fails) if fails
              else f"self-test OK: 6 mutations caught; {len(rows())} row(s) to answer")
        return 1 if fails else 0

    out, bad = [], 0
    for t in rows():
        page = (t.get("pages") or [""])[0]
        src = source_of(page)
        own_src = ""
        try:
            own_src = (ROOT / page).read_text(encoding="utf-8", errors="replace")
        except OSError:
            own_src = ""
        # ★A RETIRED PAGE CANNOT MISLEAD ANYBODY, BECAUSE NOBODY CAN READ IT. Four surfaces sit under a
        # fixed, full-screen "moved to Grafana" card; reporting that one of them shows a wrong total is a
        # finding against a page whose whole content is covered.
        if 'id="wh-retired-overlay"' in own_src:
            rec = {"verdict": "n/a", "line": f"{page} is retired behind the overlay - its content is not shown to anyone"}
        elif not src:
            rec = {"verdict": "n/a", "line": f"{page} could not be read from disk"}
        # ★A PAGE THAT LOADS NOTHING HAS NOTHING TO BOUND (Wave 4, 2026-09-14). The wave seeded a Rate-Limiting
        # story for every served page, and this lens - built for root pages - graded privacy-policy and
        # terms-of-service "no bound on what it loads ... grows until it stops": they ship no data client at
        # all. The rubric's own static-document rule (tools/page_kind.py, the `_noDataClient` test) is the
        # honest answer: a fixed document consumes a fixed document. A page with ANY client keeps being graded.
        elif _is_static_doc(page):
            rec = {"verdict": "n/a", "line": f"{page} ships no data client (no utils.js, no Supabase, no inline fetch) - a fixed document has nothing to bound"}
        else:
            # ★THE BOUND MUST BE THIS PAGE'S OWN. `source_of` folds in every script the page loads, and
            # `utils.js` carries reads for the whole platform - so analytics-report and status were reported
            # as capping their lists silently when neither contains a single `.limit()`. The cap belonged to
            # a shared file, which is its own subject. Third prover today to make this exact mistake.
            b = BOUND.search(COMMENT.sub(" ", own_src))
            s = SAYS.search(visible_text(page))
            # ★A PAGE THAT READS NO ROWS CANNOT CAP ROWS, AND ITS BOUND IS A DIFFERENT KIND (2026-09-09).
            # status.html was reported "sets no bound of its own" - true about `.limit()` and misleading as
            # a verdict, because it makes no database read at all: no .from(), no .rpc(), no invoke. Its
            # consumption is HEALTH PROBES, so the bound that fits is TIME, and it has one - every probe
            # goes through an AbortController set to PROBE_MS. It also does the SAY-SO half better than most
            # pages here: it announces the size of the run up front ("Checking N surfaces") and reports a
            # timeout AS a timeout, excluded from both the down count and the healthy numerator, rather than
            # folding silence into a verdict. Grading that as unresolvable asked the wrong question of it.
            _own_no_comments = COMMENT.sub(" ", own_src)
            _reads_rows = re.search(r"\.\s*(?:from|rpc)\s*\(|functions\s*\.\s*invoke\s*\(", _own_no_comments)
            _time_bound = re.search(r"AbortController|\bsignal\s*:|setTimeout\s*\(\s*function\s*\(\s*\)\s*\{\s*\w+\.abort", _own_no_comments)
            if not b and not _reads_rows and _time_bound and re.search(r"\bfetch\s*\(", _own_no_comments):
                out.append({"id": t["id"], "page": page, "wave": t.get("wave"), "verdict": "ok",
                            "line": "consumes no rows at all (no .from/.rpc/invoke of its own), so a row cap "
                                    "is the wrong bound to ask for; its reads are network probes and they ARE "
                                    "bounded, by an AbortController timeout on every one"})
                continue
            if not b and BOUND.search(COMMENT.sub(" ", src)):
                out.append({"id": t["id"], "page": page, "wave": t.get("wave"), "verdict": "n/a",
                            "line": "this page sets no bound of its own; the cap belongs to a shared script, "
                                    "which is graded as its own subject (W3-SC), not here"})
                continue
            if b and s:
                rec = {"verdict": "ok", "line": f'bounds what it loads ("{b.group(0)[:24]}") and tells the reader ("{s.group(0)[:30]}")'}
            elif b and not s:
                # is the cap being exceeded RIGHT NOW, in some hive, in this database?
                # ★ASK ABOUT THE CAPS THIS PAGE ITSELF WRITES. `source_of` folds in every script the page
                # loads, and `utils.js` carries reads for the whole platform - so a cap belonging to another
                # page would be measured against this one. The same shared-script trap that had eight pages
                # reported as leaking hives an hour ago.
                own = own_src
                caps = capped_reads(own)
                # ★A CAP OF ONE IS "THE LATEST ONE", NOT A TRUNCATED LIST. Nobody reads a single row as a
                # total, and "showing the most recent 1" is not a sentence any page should carry. The claim
                # is about a list whose size a reader could mistake for the whole; a single-row read cannot
                # make that mistake possible.
                if caps and all(c <= 1 for _, c in caps):
                    rec = {"verdict": "ok",
                           "line": f'its only bound is a single-row read ({caps[0][0]} limit {caps[0][1]}) - '
                                   'a lone row cannot be mistaken for a total, so there is nothing to say'}
                    out.append({"id": t["id"], "page": page, "wave": t.get("wave"), **rec})
                    continue
                over = []
                for table, cap in caps[:6]:
                    held = biggest_hive(table)
                    if held is not None and held > cap:
                        over.append(f"{table} holds {held} in one hive against a cap of {cap}")
                # ★THE DEFECT IS STRUCTURAL, NOT ABOUT TODAY'S ROW COUNT - BUT "TODAY" IS WORTH KNOWING. A
                # cap of 500 on a hive holding 40 misleads nobody this week; the day the hive passes 500 the
                # page starts showing a number that is wrong in one direction and says nothing, and nobody is
                # told the day it happens. Asking the database turns that from a risk into a date, and the
                # date may already have passed - which is a different sentence to hand somebody.
                # Verified against the JavaScript too - these pages carry no cap phrase anywhere, so the
                # note is not merely rendered late.
                # ★SAY ONLY WHAT THE READING SUPPORTS. A first version added "and this page renders a count
                # from what it fetched, so that number is wrong TODAY" whenever `.length` appeared anywhere
                # in the file. On report-sender every such count is about the CURRENT operation - "3 reports
                # saved", "2 recipients" - while the capped read feeds a separate history list. The claim was
                # louder than the evidence, which is the exact fault this whole wave has been correcting in
                # other people's lenses. What IS supported: the page caps, the cap is already exceeded in a
                # real hive, and the page says nothing about either.
                # ★THE CODEBASE ALREADY CLASSIFIES ITS OWN CAPS, AND SAYING SO IS PART OF SAYING SO. This
                # platform annotates a generous bound as an "insurance cap", "cap-ok" or "bounded-by-nature"
                # — a ceiling that exists so a read cannot grow without limit, not a slice a reader could
                # mistake for a total. A 500-row insurance cap on a table whose largest hive holds 30 hides
                # nothing from anybody, and demanding "showing the first 500" beside it would be noise. The
                # annotation ALONE is not enough (a comment cannot make a cap harmless), so it counts only
                # while the measurement agrees: nothing near the ceiling.
                # ★A BOUND I CANNOT ATTRIBUTE IS A BOUND I CANNOT JUDGE. `marketplace-seller-profile` and
                # `skillmatrix` carry a `.limit()` that no `.from('table')` resolves to within reach - built
                # through a helper, or narrowed by a filter this reading deliberately excludes. Whether that
                # ceiling is a display slice or insurance is exactly what cannot be told from here, and
                # calling it a defect would be asserting the half I could not measure.
                if not caps:
                    out.append({"id": t["id"], "page": page, "wave": t.get("wave"), "verdict": "n/a",
                                "line": f'bounds at "{b.group(0)[:18]}" but no table+cap could be resolved from '
                                        'its own source, so whether that ceiling hides anything is unmeasured here'})
                    continue
                annotated = INSURANCE.search(own)
                near = [tb for tb, cb in caps if (biggest_hive(tb) or 0) > cb * 0.6]
                if annotated and not over and not near:
                    rec = {"verdict": "ok",
                           "line": f'bounds at "{b.group(0)[:18]}" and its source classifies that as an insurance '
                                   f'cap ("{annotated.group(0)[:26]}"); measured, no hive is within 60% of it, '
                                   'so there is no slice for a reader to mistake for a total'}
                    out.append({"id": t["id"], "page": page, "wave": t.get("wave"), **rec})
                    continue
                rec = ({"verdict": "BAD",
                        "line": f'bounds at "{b.group(0)[:18]}" and never says so, and the cap is ALREADY '
                                f'exceeded in a real hive: {over[0]} - so this list is a slice today, and '
                                f'nothing on the page says it is one'}
                       if over else
                       {"verdict": "BAD",
                        "line": f'bounds at "{b.group(0)[:22]}" and never says so, in markup or in script - '
                                'the day the data passes the cap this page shows a wrong total silently'})
            elif s and not b:
                rec = {"verdict": "ok", "line": f'no cap found in its own source, and it still offers "{s.group(0)[:26]}" - nothing is hidden from the reader'}
            else:
                rec = {"verdict": "BAD", "line": "no bound on what it loads and nothing said about it - this page grows until it stops"}
        if rec["verdict"] == "BAD":
            bad += 1
        out.append({"id": t["id"], "page": page, "wave": t.get("wave"), **rec})

    print(f"pages asked whether they bound what they load: {len(out)}  ({len(out) - bad} hold, {bad} findings)")

    # ★THE SHAPE THAT DOES NOT SHOW UP IN THE VERDICTS ABOVE. A capped read that gets SUMMED is a wrong
    # number rather than a short list, and the windowing exemption that protects list caps from a
    # compare-like-with-like error hides exactly these. Reported every run so a new one is visible the
    # day it lands. NOT auto-failed, because whether a cap can bite depends on the read's OWN scope -
    # and getting that wrong is the same error twice: measured 2026-09-09, achievement_xp_log holds 573
    # rows for one WORKER, which says nothing about logbook's read, scoped .eq('source_id', entry.id),
    # where the largest any single source has ever paid is 4 against a cap of 20.
    seen_sums: list[str] = []
    for t in rows():
        page = (t.get("pages") or [""])[0]
        if not page:
            continue
        try:
            own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for table, cap, col in summed_caps(own):
            seen_sums.append(f"  SUMMED CAP  {page}: {table}.{col} summed from a read capped at {cap}")
    if seen_sums:
        print("capped reads whose rows are SUMMED (judge each against its own scope, not a table total):")
        for line in sorted(set(seen_sums)):
            print(line)
    for r in out:
        tag = "ok " if r["verdict"] == "ok" else r["verdict"]
        print(f"  {tag} {r['id']:8} {r['page'][:30]:32} {r['line'][:92]}")
    if "--json" in sys.argv:
        dest = sys.argv[sys.argv.index("--json") + 1]
        Path(dest).parent.mkdir(exist_ok=True)
        Path(dest).write_text(json.dumps({"results": out}, indent=1), encoding="utf-8")
        print(f"\n  {dest}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
