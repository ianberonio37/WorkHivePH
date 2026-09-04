#!/usr/bin/env python3
"""noun-slot-takes-a-noun - whReadError's second argument is spliced mid-sentence (2026-08-27, T176).

whReadError(err, what) does not print `what`. It SPLICES it into a sentence:

    'Your session expired, so ' + thing + ' could not be loaded. Sign in again to see it.'

so `what` must be a noun phrase ('your equipment list', 'the audit log'). Four callsites passed a
whole SENTENCE, and what shipped to the user was:

    "Your session expired, so Could not load your equipment list. Check your connection. could not
     be loaded. Sign in again to see it. Nothing you did was lost."

Measured in the browser, not reasoned - the same call with a noun returns the sentence it should.

*THE MISTAKE HAD A GOOD MOTIVE, which is why it needs a gate rather than a scolding. Each site was
CONVERTED from a hand-rolled message to the taxonomy helper - the right move - and the old sentence
was passed straight through into the argument slot. logbook even carries a comment above it
explaining that the upstream sentence belongs in console.error and never in the notice: the author
understood the principle and still handed the helper a sentence. Converting to the taxonomy means
REPLACING the sentence with a noun, not forwarding it.

*AND IT IS INVISIBLE TO EVERY OTHER CHECK. The helper is present, so a "does this page use the
taxonomy?" sweep passes it. The string contains no raw error text, so the raw-echo ratchet passes
it. Nothing throws. Only reading the composed sentence shows it, and nobody reads a sentence that
only appears when a session expires mid-read.

THE RULE: the noun slot may not contain sentence punctuation, and may not open with a verb phrase
('Could not…', 'Failed to…', 'Check your…'). whWriteError and whAiError are NOT in scope - their
second argument IS a fallback message, by design.

Self-test: `--selftest`.
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# only whReadError: its second argument is a NOUN spliced into a sentence.
CALL = re.compile(r"whReadError\s*\(\s*[^,()]{1,40}\s*,\s*(['\"])(.*?)\1", re.S)
VERB_OPENER = re.compile(r"^(Could|Couldn|Can|Cannot|Failed|Unable|Check|Try|Sorry|We|There)\b")


def is_sentence(arg: str) -> bool:
    return ("." in arg) or bool(VERB_OPENER.match(arg.strip()))


def scan(src: str, label: str = "source") -> list:
    out = []
    for m in CALL.finditer(src):
        arg = m.group(2)
        if is_sentence(arg):
            line = src[:m.start()].count("\n") + 1
            out.append(f"{label}:{line} whReadError's noun slot holds a sentence "
                       f"(\"{arg[:60]}\") - it will be spliced mid-sentence and garble the notice")
    return out


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    chk("a sentence in the noun slot fails",
        len(scan("showToast(whReadError(error, 'Could not load your equipment list. Check your connection.'))")), 1)
    chk("a noun phrase passes",
        len(scan("showToast(whReadError(error, 'your equipment list'))")), 0)
    chk("a noun with an article passes",
        len(scan("showToast(whReadError(err, 'the audit log'))")), 0)
    chk("a verb opener without a period still fails",
        len(scan("showToast(whReadError(err, 'Failed to load the feed'))")), 1)
    # the helpers whose second argument IS a message must not be dragged in
    chk("whWriteError is out of scope",
        len(scan("showToast(whWriteError(e, 'Save failed. Nothing changed.'))")), 0)
    chk("whAiError is out of scope",
        len(scan("showToast(whAiError(e, 'The assistant is unavailable.'))")), 0)

    live = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))):
        live += scan(io.open(f, encoding="utf-8", errors="replace").read(), Path(f).name)
    chk("every live callsite passes a noun", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    problems, sites = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        sites += len(CALL.findall(src))
        problems += scan(src, Path(f).name)
    print("whReadError's noun slot must hold a noun")
    print(f"  callsites: {sites}  ·  holding a sentence: {len(problems)}")
    if not problems:
        print("\n  PASS - every noun slot holds a noun.")
        return 0
    print("\n  FAIL - these will be spliced mid-sentence:")
    for p in problems:
        print(f"    {p}")
    print("\n  Pass the THING that could not be read ('your equipment list'), not a sentence about it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
