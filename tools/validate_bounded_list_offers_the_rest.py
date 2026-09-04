#!/usr/bin/env python3
"""bounded-list-offers-the-rest - a capped list must say there IS more, and give a way to it (T129).

A long list has to be capped; the DOM cannot carry two thousand rows and stay usable. The danger is
not the cap, it is a SILENT one: rows 1-20 of 548 rendered with nothing on screen admitting the other
528 exist. That reads as "this is everything", and a reader planning against it plans against a
fifth of their own history. A row cap is not pagination unless the page says so and offers the rest.

MEASURED 2026-08-27 at two volumes, which is what this gate now holds in place. With the hive at 941
rows (314 for the signed-in worker) and again at 1641 (548): rows painted 20 -> 20, DOM nodes
1458 -> 1396, first rows 1125ms -> 1221ms. A 75% growth in the reader's own history cost 96ms and no
DOM weight at all, because the slice is CONSTANT - and logbook-load-more-wrap was offered, not
hidden, so the remainder was disclosed both times.

THE THREE-PART PROPERTY, because any one alone is not enough:
  1. the render SLICES by a display count - otherwise the page grows with the data,
  2. a control INCREASES that count - otherwise the cap is a wall, not a page,
  3. the control is REVEALED exactly when more rows exist - `toggle('hidden', count >= total)`.
Part 3 is the one that makes the cap honest: without it a list can slice, offer a hidden button, and
still tell the reader nothing.

★ITS TEETH ARE SYNTHETIC, AND THAT IS THE CORRECT SHAPE HERE - CHECKED, NOT ASSUMED. The usual bar
for a new gate is a resurrection: run it against the pre-fix world and require RED. There is no such
world for this one. Both surfaces were re-checked at HEAD (git show HEAD:logbook.html and
:inventory.html, scored through this module's own check()) and both come back CLEAN - the slice, the
increment and the reveal were all already in place, so this gate locks a property that was never
broken rather than a fix that repaired one. Demanding a git-history resurrection from a gate that
never had a violation to resurrect is how a good gate gets marked unfinishable (the same distinction
validate_status_survives_the_outage.py records for the same reason). So the teeth are SYNTHETIC
negatives instead: one per part, each mutating the source in memory and required to catch it, plus
both live pages required to stay green.

Re-drive: python tools/validate_bounded_list_offers_the_rest.py [--selftest]
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (page, display-count variable) — surfaces whose list is long enough to need a cap.
SURFACES = [
    ("logbook.html", "_logbookDisplayCount"),
    ("inventory.html", "_invDisplayCount"),
]

# The SECOND mechanism for the same property (T13, 2026-08-27). The surfaces above cap in the
# CLIENT and page past it. Some rails cap in the QUERY instead — a server-side .limit(N) — and
# then no amount of paging exists: the slice is all the page will ever have. Those must therefore
# ask for the true total (count:'exact') and STATE it, because the alternative is what dayplanner
# was doing: rendering `${plantWork.length} PMs` from a 30-row slice while 80 were due, so the
# rail's own header was off by fifty and disagreed with the hive board reading the same view.
# A capped list that names its length as if it were the total is worse than a short list; it is a
# wrong number a worker plans their shift against.
# (page, array variable, total variable)
SERVER_CAPPED = [
    ("dayplanner.html", "plantWork", "plantWorkTotal"),
]


def check_server_capped(src: str, arr: str, total: str) -> list:
    """A query-capped rail must know, and say, what it is a slice OF."""
    out = []
    a, t = re.escape(arr), re.escape(total)

    if not re.search(rf"\b(?:let|var|const)\s+{t}\s*=", src):
        out.append(f"{total} is never declared - the rail has no idea what it is a slice of")

    # it must ASK for the true count, not infer it from the slice it received
    if not re.search(r"count:\s*['\"]exact['\"]", src):
        out.append(f"no `count: 'exact'` - {arr} can only report its own length, which is the cap")

    if not re.search(rf"{t}\s*=\s*\(?\s*typeof\s+count|{t}\s*=\s*count", src):
        out.append(f"{total} is never assigned from the query's count")

    # and it must STATE the total, conditionally — a complete list must not cry wolf
    if not re.search(rf"{t}\s*>\s*{a}\.length", src):
        out.append(f"the header does not compare {total} to {arr}.length - it either always or "
                   f"never claims a cap, and only one of those can be true")

    if not re.search(rf"of\s*\$\{{{t}\}}|\$\{{{t}\}}\s*PMs|of\s+\$\{{\s*{t}", src):
        out.append(f"{total} is never rendered - the rail knows the real number and does not say it")
    return out


def check(src: str, var: str) -> list:
    """The three parts, as a pure function so each can be shown to FAIL."""
    out = []
    v = re.escape(var)

    if not re.search(rf"\b(?:let|var|const)\s+{v}\s*=\s*\d+", src):
        out.append(f"{var} is never declared with a starting cap - nothing bounds the first render")

    # 1. the render slices by it
    if not re.search(rf"\.slice\(\s*0\s*,\s*{v}\s*\)", src):
        out.append(f"no `.slice(0, {var})` - the list is not bounded by its own display count, so the "
                   f"DOM grows with the data")

    # 2. something increases it
    if not re.search(rf"{v}\s*\+=", src):
        out.append(f"nothing ever increases {var} - the cap is a wall with no way past it")

    # 3. and the control is revealed exactly when more rows exist
    if not re.search(rf"toggle\(\s*['\"]hidden['\"]\s*,\s*{v}\s*>=", src):
        out.append(f"the load-more control is not toggled on `{var} >= <total>` - a capped list that "
                   f"does not reveal the rest reads as the whole set")
    return out


def main() -> int:
    findings = []
    for page, var in SURFACES:
        p = ROOT / page
        if not p.exists():
            findings.append((page, [f"{page} is gone - re-point this gate rather than trusting its silence"]))
            continue
        bad = check(io.open(p, encoding="utf-8", errors="replace").read(), var)
        if bad:
            findings.append((page, bad))

    for page, arr, total in SERVER_CAPPED:
        p = ROOT / page
        if not p.exists():
            findings.append((page, [f"{page} is gone - re-point this gate rather than trusting its silence"]))
            continue
        bad = check_server_capped(io.open(p, encoding="utf-8", errors="replace").read(), arr, total)
        if bad:
            findings.append((page, bad))

    print("bounded-list-offers-the-rest - a capped list must admit the rest exists")
    print(f"  surfaces checked: {len(SURFACES)} client-capped + {len(SERVER_CAPPED)} server-capped")
    if findings:
        print("\nFAIL - a silent cap tells the reader they are looking at everything:")
        for page, bad in findings:
            for b in bad:
                print(f"    {page}: {b}")
        return 1
    print("\nPASS - every long list slices, offers the rest, and reveals the offer only when there IS a rest.")
    return 0


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    good = ("let _c = 20;\n"
            "const visible = filtered.slice(0, _c);\n"
            "function more(){ _c += 20; render(); }\n"
            "wrap.classList.toggle('hidden', _c >= filtered.length);\n")

    chk("a bounded list that offers the rest passes", check(good, "_c"), [])
    chk("an unsliced list fails", len(check(good.replace("filtered.slice(0, _c)", "filtered"), "_c")), 1)
    chk("a cap with no way past it fails", len(check(good.replace("_c += 20;", ""), "_c")), 1)
    chk("a cap that never reveals the rest fails",
        len(check(good.replace("wrap.classList.toggle('hidden', _c >= filtered.length);", ""), "_c")), 1)
    chk("an undeclared count fails", len(check(good.replace("let _c = 20;", ""), "_c")), 1)

    # The server-capped mechanism gets its own negatives, because its parts fail differently:
    # a rail can hold a total and never print it, or print it unconditionally and cry wolf on a
    # complete list. Neither is caught by the client-capped checks above.
    sgood = ("let plantWork = [];\nlet plantWorkTotal = 0;\n"
             "const { data, error, count } = await db.from('v').select('a', { count: 'exact' }).limit(30);\n"
             "plantWork = data || []; plantWorkTotal = (typeof count === 'number') ? count : plantWork.length;\n"
             "const h = `${plantWorkTotal > plantWork.length ? `${plantWork.length} of ${plantWorkTotal} PMs` : ''}`;\n")

    chk("a server-capped rail that states its total passes",
        check_server_capped(sgood, "plantWork", "plantWorkTotal"), [])
    chk("no count:'exact' fails",
        len(check_server_capped(sgood.replace(", { count: 'exact' }", ""), "plantWork", "plantWorkTotal")) >= 1, True)
    chk("a total that is never assigned fails",
        len(check_server_capped(sgood.replace("plantWorkTotal = (typeof count === 'number') ? count : plantWork.length;", ""),
                                "plantWork", "plantWorkTotal")) >= 1, True)
    chk("a total that is never rendered fails",
        len(check_server_capped(sgood.replace("${plantWork.length} of ${plantWorkTotal} PMs", "${plantWork.length} PMs"),
                                "plantWork", "plantWorkTotal")) >= 1, True)
    chk("an unconditional claim fails",
        len(check_server_capped(sgood.replace("plantWorkTotal > plantWork.length ? ", ""),
                                "plantWork", "plantWorkTotal")) >= 1, True)

    for page, var in SURFACES:
        p = ROOT / page
        if p.exists():
            chk(f"the live {page} still passes",
                check(io.open(p, encoding="utf-8", errors="replace").read(), var), [])
    for page, arr, total in SERVER_CAPPED:
        p = ROOT / page
        if p.exists():
            chk(f"the live {page} still passes",
                check_server_capped(io.open(p, encoding="utf-8", errors="replace").read(), arr, total), [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
