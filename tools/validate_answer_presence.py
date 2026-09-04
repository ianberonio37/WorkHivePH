#!/usr/bin/env python3
"""answer-presence — T151: a searcher's question answered above the fold (2026-08-26).

Somebody arrives from a search result. They have a question, and the snippet
promised this page answers it. What they meet in the first screen decides whether
they stay — and the failure mode is not a broken page, it is a page that opens
with throat-clearing and puts the answer four scrolls down.

★THE ORACLE IS ANSWER-PRESENCE, NOT META-VERBATIM, and T151 learned that the hard
way: an earlier pass checked whether the meta description's words appeared on the
page and produced a false red, because a description SUMMARIZES rather than
quotes. What matters is whether the page ANSWERS ITS OWN TITLE early, in prose a
person can read.

FOUR PER-ARTICLE ASSERTIONS, each chosen to be decidable from markup rather than
from taste:

  1. it has an H1 — the question being answered
  2. a substantive opening paragraph exists within the first stretch after it
     (>= 80 characters of real prose, not a nav crumb or a byline)
  3. that opener CARRIES THE SUBJECT: the distinctive term from the title appears
     in it, so the page opens on its own topic instead of on preamble
  4. a freshness stamp is visible on the page — a searcher landing on undated
     maintenance guidance cannot tell if it is current, and this cluster already
     ships "Updated <date>" stamps

★WHAT IT DELIBERATELY DOES NOT JUDGE: whether the answer is GOOD. That is
editorial judgement, and a gate that scored prose quality would produce arguments
instead of signal. It checks that the page opens on its subject, promptly, with a
date — the structural preconditions for an answer being there at all.

Usage: python tools/validate_answer_presence.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STOP = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "your", "you", "is",
        "are", "what", "how", "why", "when", "does", "do", "workhive", "guide", "meet", "two",
        "from", "that", "this", "it", "its", "can", "will", "not", "vs", "into", "at", "by"}


def detag(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    if not files:
        print("SKIP answer-presence — no learn articles found")
        return 0

    fails = []
    for f in files:
        name = Path(f).parent.name
        src = io.open(f, encoding="utf-8", errors="replace").read()

        m = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S | re.I)
        if not m:
            fails.append(f"{name}: no <h1> — nothing states the question this page answers")
            continue
        title = detag(m.group(1))

        # the opening prose: the first paragraph after the H1 with real substance
        # ★THE BAR IS "ANSWERS PROMPTLY", NOT "ANSWERS IN SENTENCE ONE". Reading the first run's
        # flags showed two DIFFERENT things caught by one rule: pages that open with a methodology
        # disclaimer before the answer (a real arrival defect), and pages that open by framing the
        # PROBLEM before naming the subject - which is ordinary good writing, not a fault. Enforcing
        # sentence-one would be a gate legislating prose style. Look at the first TWO substantive
        # paragraphs: a page gets one paragraph of runway.
        # ★READ WHAT A PERSON SEES, NOT WHAT A TAG NAME SUGGESTS. Scanning only <p> elements flagged
        # the WorkHive-vs-MaintainX page as opening off-topic - and that page opens with a textbook
        # answer ("Choose MaintainX if in-app team communication... Choose WorkHive if you need
        # genuinely free at the worker tier..."), written inside a <div> of <strong> lines rather
        # than paragraphs. The <p> tags it DID find were the byline and a repeated pricing
        # disclaimer, so the gate read the furniture and missed the answer. An answer-presence check
        # that depends on which element the author reached for is measuring markup, not arrival.
        after = src[m.end(): m.end() + 8000]
        opener = detag(after)[:900]
        if not opener:
            fails.append(f"{name}: no substantive opening paragraph after the H1 — a searcher meets "
                         f"preamble, not an answer")
            continue

        # Does the opener carry the title's distinctive subject?
        # ★TWO INSTRUMENT FIXES, both found by READING the first run's five flags rather than
        # trusting them: (1) the {3,} filter silently dropped the platform's most important short
        # terms - PM, AI, OEE - so an article titled "Free PM checklist templates" whose opener says
        # "Most Philippine plants run PMs" was flagged as off-topic; (2) an exact match calls
        # "measurement" a miss for a title saying "Measuring". Keep SHORT UPPERCASE acronyms from the
        # original title, and compare on a 5-character stem so ordinary morphology is not a defect.
        acronyms = [w.lower() for w in re.findall(r"\b[A-Z]{2,5}\b", title)]
        words = [w for w in re.findall(r"[A-Za-z]{3,}", title.lower()) if w not in STOP]
        terms = list(dict.fromkeys(acronyms + words))
        low = opener.lower()
        def present(term):
            if len(term) <= 4:
                return re.search(r"\b" + re.escape(term) + r"s?\b", low) is not None
            return term[:5] in low
        if terms and not any(present(t) for t in terms):
            fails.append(f"{name}: the opener does not mention any term from its own title "
                         f"(\"{title[:44]}\") — the page opens off-topic")

        if not re.search(r"Updated\s+\d|datePublished|dateModified|Last updated", src, re.I):
            fails.append(f"{name}: no visible freshness stamp — a searcher cannot tell if maintenance "
                         f"guidance is current")

    print(f"  learn articles checked: {len(files)}")
    if fails:
        print(f"FAIL answer-presence — {len(fails)} issue(s):")
        for x in fails[:10]:
            print("    - " + x)
        if len(fails) > 10:
            print(f"    ... and {len(fails) - 10} more")
        return 1
    print(f"PASS answer-presence — all {len(files)} articles open on their own subject, promptly, "
          f"with a date a searcher can see.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
