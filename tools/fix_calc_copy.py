"""fix_calc_copy.py - the copy lens on the 60 calculator pages (2026-10-12, the W4 copy rows W46286 ...).

Read on tools/ahu-sizing-calculator/index.html through the Playwright MCP at phone-390 and desktop-1280, and then
measured across all 60 pages:

  1. THE FAQ'S FIRST QUESTION WAS THE SEO KEYWORD WITH A QUESTION MARK. "What is an air handling unit sizing calculator
     CFM?", "What is an electrical load demand calculator kVA?", "What is an elevator traffic analysis calculator
     interval?" - on every page whose FAQ is not hand-written. A keyword is a search string, not a sentence. A person,
     and an answer engine lifting the pair, reads "What is the AHU Sizing Calculator?" - which the answer under it
     already answers ("The AHU Sizing Calculator is a free online tool that...").
  2. ONE PAGE NAMED ITS STANDARDS TWO WAYS. The body printed what the calculation engine reported ("ASHRAE 62.1 |
     ASHRAE 90.1 | ASHRAE 2021 Ch.1 | SMACNA") while the how-to step, the FAQ answer and their JSON-LD twins printed
     the generator's hand-typed fallback ("ASHRAE 62.1 | 90.1 | Fundamentals"). Every sentence now carries the
     engine's standard - the one the worked example was actually computed under.
  3. THE STANDARDS WERE PIPE-SEPARATED INSIDE PROSE, a data dump in a sentence. They read as a list now: "ASHRAE 62.1,
     ASHRAE 90.1, ASHRAE 2021 Ch.1 and SMACNA".
  4. "HOW IT WORKS" OPENED "Computed from your inputs per ..." on a page that has no inputs - it teaches the method with
     a worked example, and the interactive calculator lives in Engineering Design. It now says which standard the
     calculator follows; the next sentence already says where the inputs live.

Why a sweep and not a rebuild: tools/build_calc_pages.py writes to seo_assets/calc_pages_staging/, promoting staging is
Ian's gate, and the staged pages are behind the live ones (tools/prove_calc_staging_not_stale.py). The generator is
fixed in the same change so a rebuild is born correct; this patches what a reader sees, live and staged alike.

SAFE BY FRAME, NOT BY STRING. A fallback standard can be a substring of the engine's ("ISO 281" in "ISO 281:2007"), so a
global replace would print "ISO 281:2007:2007". Each standard is rewritten only inside the sentence frames the
generator writes it into - "(per X)", "per X.", "following X.", "standard: X." - in the visible HTML and in the
JSON-LD strings together, so the FAQPage twin stays verbatim with the visible FAQ. Idempotent: a second run finds no
frame holding a pipe or a fallback, and changes nothing.

    python tools/fix_calc_copy.py            report what would change
    python tools/fix_calc_copy.py --apply    write it
"""
from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location("_bcp", HERE / "build_calc_pages.py")
_bcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bcp)

CALC_DATA = _bcp.CALC_DATA
STAGING = ROOT / "seo_assets" / "calc_pages_staging"
# the frames the generator writes a standard into: (prefix, suffix)
FRAMES = [("(per ", ")"), ("Computed from your inputs per ", "."), ("computed per ", "."), ("following ", "."),
          ("standard: ", ".")]


def _forms(text: str) -> set:
    """every way a string can sit in the page: HTML-escaped either way, and inside a JSON string"""
    return {text, html.escape(text, quote=True), html.escape(text, quote=False), json.dumps(text, ensure_ascii=False)[1:-1]}


def _fix_page(s: str, slug: str, data: dict, eng_std: str) -> tuple:
    changes = []
    # 1. the FAQ question, visible and in the JSON-LD twin
    if not data.get("faqs"):
        kw, title = data["keyword"], data["title"]
        old_q, new_q = f"What is {_bcp._article(kw)} {kw}?", f"What is the {title}?"
        for of in _forms(old_q):
            if of in s:
                nf = {old_q: new_q, html.escape(old_q, quote=True): html.escape(new_q, quote=True),
                      html.escape(old_q, quote=False): html.escape(new_q, quote=False)}.get(
                    of, json.dumps(new_q, ensure_ascii=False)[1:-1])
                n = s.count(of)
                s = s.replace(of, nf)
                changes.append("faq question x%d" % n)
    # 2 + 3 + 4. every standard frame -> the engine's standard, as prose
    prose = _bcp._std_prose(eng_std)
    if prose:
        raws = {x for x in (eng_std, data.get("standard", "")) if x}
        raws |= {x.rstrip(".") for x in raws}
        for raw in sorted(raws, key=len, reverse=True):
            if raw == prose:
                continue
            for pre, suf in FRAMES:
                for rf in _forms(raw):
                    old = pre + rf + suf
                    if old not in s:
                        continue
                    pf = {raw: prose, html.escape(raw, quote=True): html.escape(prose, quote=True),
                          html.escape(raw, quote=False): html.escape(prose, quote=False)}.get(
                        rf, json.dumps(prose, ensure_ascii=False)[1:-1])
                    n = s.count(old)
                    s = s.replace(old, pre + pf + suf)
                    changes.append("standard %r x%d" % (pre.strip(), n))
        # 4. the method line on a page with no inputs
        for pf in _forms(prose):
            old = "Computed from your inputs per " + pf + "."
            if old in s:
                s = s.replace(old, "The calculator follows " + pf + ".")
                changes.append("method line")
    return s, changes


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    total_pages, total_changes = 0, 0
    for slug, data in CALC_DATA.items():
        try:
            r = _bcp._run_calc(data)
        except Exception as e:      # noqa: BLE001 - a module that will not run is reported, not guessed at
            print(f"  SKIP {slug}: the engine did not run ({type(e).__name__}: {str(e)[:80]})")
            continue
        eng_std = r.get("standard") or data.get("standard", "")
        for path in (ROOT / "tools" / slug / "index.html", STAGING / slug / "index.html"):
            if not path.exists():
                continue
            # BYTES in, bytes out: Path.write_text on Windows turns every LF into CRLF, and the first --apply of this
            # sweep rewrote all 60 LF pages that way (2026-10-12). The frames hold no newline, so the file's own
            # line endings pass through untouched.
            s = path.read_bytes().decode("utf-8")
            new, changes = _fix_page(s, slug, data, eng_std)
            if new != s:
                total_pages += 1
                total_changes += len(changes)
                print(f"  {'fixed' if apply else 'would fix'} {path.relative_to(ROOT).as_posix()}: {', '.join(changes)}")
                if apply:
                    path.write_bytes(new.encode("utf-8"))
    print(f"{'fixed' if apply else 'would fix'} {total_pages} page(s), {total_changes} change(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
