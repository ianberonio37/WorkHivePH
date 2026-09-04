#!/usr/bin/env python3
"""glossary-registry - T177: the platform must teach its own vocabulary (2026-08-26).

WorkHive puts domain acronyms straight onto the glass - MTBF beside a number, OEE on a
card, SPI in a project summary. For a reliability engineer that is correct and
efficient. For the audience this platform explicitly courts - new graduates, workers
coming off paper - an unexplained acronym is a number they can neither act on nor
argue with, and "I did not understand the screen" is indistinguishable from "the
screen was wrong".

THE REGISTRY, and the rule it encodes: every term below that appears in an app page's
visible text must be EXPLAINED somewhere the reader can reach - either expanded in
place on a page, or taught in the learn cluster. Both count; a guide is a real answer
and so is a phrase in the sentence itself.

MEASURED 2026-08-26: eleven terms on the glass, and TEN were already taught properly -
MTBF, MTTR, OEE, RCM, FMEA, RPN, CPM, LOTO, SOP and P-F each have a learn guide that
spells them out. The platform's teaching habit is good.

★THE ONE THAT WAS NOT: project-manager showed supervisors
"EVM: SPI 0.87, CPI 1.02, status ... (BAC ₱..., EV ₱...)" - SIX acronyms in one line -
and nothing anywhere on the platform explained a single one. Earned value was the only
domain vocabulary the product used without teaching. Fixed at FIRST USE, in that line:
"Earned value (EVM): schedule performance SPI ..., cost performance CPI ..., ... (budget
at completion ₱..., earned value ₱...)". A glossary a reader has to go and find is a
glossary they do not read.

Usage: python tools/validate_glossary_registry.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"backup|test|^index-", re.I)

# term -> regex that counts as an explanation of it
GLOSSARY = {
    "MTBF": r"mean time between failures",
    "MTTR": r"mean time to repair",
    "OEE": r"overall equipment effectiveness",
    "RCM": r"reliability.cent(?:er|re)d maintenance",
    "FMEA": r"failure mode(?:s)? and effects",
    "RPN": r"risk priority number",
    "EVM": r"earned value",
    "SPI": r"schedule performance",
    "CPI": r"cost performance",
    "CPM": r"critical path",
    "LOTO": r"lock.?out",
    "SOP": r"standard operating procedure",
    "P-F": r"potential failure|p-f interval",
}


def visible(src: str) -> str:
    def blank(m):
        return " " * (m.end() - m.start())
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
    # scripts stay: user-facing strings live in template literals on this platform
    # (?!quote) below: accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    s = re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def main() -> int:
    # ★assistant.html IS EXCLUDED, AND THE REASON IS THE POINT. It carries a capability CATALOG that
    # describes every other page to the model - "Project Manager: ... Tracks scope (WBS), linked
    # logbook+PMs+parts, daily progress, EV/SPI/CPI, and sign-off". That text is model-facing, not
    # UI, and because it describes the OTHER pages it double-counts their vocabulary: the terms in it
    # belong to the pages it names, which this gate scans on their own. Flagging it would demand a
    # glossary inside a system prompt.
    app = [f for f in sorted(glob.glob(str(ROOT / "*.html")))
           if not SKIP.search(Path(f).name) and Path(f).name != "assistant.html"]
    learn = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    if not app:
        print("SKIP glossary-registry - no pages found")
        return 0

    learn_text = " ".join(visible(io.open(f, encoding="utf-8", errors="replace").read()) for f in learn)

    used, untaught = {}, []
    for f in app:
        name = Path(f).name
        text = visible(io.open(f, encoding="utf-8", errors="replace").read())
        for term, expansion in GLOSSARY.items():
            if not re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text):
                continue
            used.setdefault(term, []).append(name)
            if re.search(expansion, text, re.I):        # explained in place
                continue
            if re.search(expansion, learn_text, re.I):  # taught in the learn cluster
                continue
            untaught.append(f"{name}: shows \"{term}\" and nothing on the platform explains it")

    print(f"  glossary terms: {len(GLOSSARY)} | on the glass: {len(used)} | unexplained: {len(untaught)}")
    if untaught:
        print(f"FAIL glossary-registry - {len(untaught)} term(s) shown but never explained:")
        for x in sorted(set(untaught))[:12]:
            print("    - " + x)
        print("    Explain it where the reader meets it, or give it a learn guide. A number whose name")
        print("    the reader cannot decode is a number they can neither act on nor argue with - and")
        print("    'I did not understand the screen' is indistinguishable from 'the screen was wrong'.")
        return 1
    print(f"PASS glossary-registry - every one of the {len(used)} domain terms on the glass is explained "
          f"in place or taught in the learn cluster.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
