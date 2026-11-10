#!/usr/bin/env python3
"""validate_reply_language_matches_persona.py - no shipped page promises an AI reply in a language the persona forbids
(gate reply-language-matches-persona, 2026-11-10).

★THE COMPANION REPLIES IN ENGLISH; SIX SURFACES SAID IT ANSWERS IN YOURS (found rewriting a learn guide, Wave CF M13).
Every AI voice on the platform is built from supabase/functions/_shared/persona.ts, and its language rule reads
"UNDERSTAND any of these. Always REPLY in English". The Voice Journal (conversational mode), the AI Assistant and the
companion all carry it. Yet voice-journal.html's own description said it "reflects back in any language you speak",
the companion's platform knowledge told the model the journal "reflects back in the same language", and three learn
guides said it "replies in the language you used" - one printed a Taglish reply as a worked example. A worker who reads
that and asks in Cebuano gets English back and concludes the product is broken, or that it ignored them.

The truth is checked at its source: while persona.ts holds the English-reply rule, any shipped sentence that promises a
reply in the speaker's language (or in Filipino, Taglish, Tagalog, Cebuano, "any language") fails. If the rule is ever
lifted, the gate passes those sentences again. Understanding other languages on input stays true and is never flagged.

    python tools/validate_reply_language_matches_persona.py [--self-test]
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PERSONA = ROOT / "supabase" / "functions" / "_shared" / "persona.ts"
SKIP_DIRS = ("tools/", "tests/", "test-data-seeder/", "_fixtures/", "node_modules/", ".claude/", "supabase/")
ENGLISH_RULE = re.compile(r"Always REPLY in English", re.I)

LANG = r"(?:the\s+same\s+language|the\s+language\s+you\s+(?:used|spoke|speak|chose)|your\s+(?:own\s+)?language|any\s+language|" \
       r"whatever\s+language|filipino|tagalog|taglish|cebuano|bisaya|ilocano|hiligaynon|kapampangan|waray|bikol)"
CLAIMS = [
    # the AI's verbs only - "talk in your own language" / "tap to talk in any language" is the PERSON speaking, and true
    re.compile(r"\b(?:repl(?:y|ies|ying)|respond(?:s|ing)?|answers?)\s+(?:back\s+)?in\s+" + LANG, re.I),
    re.compile(r"\b(?:speaks?|talks?)\s+back\s+in\s+" + LANG, re.I),
    re.compile(r"\breflects?\s+(?:it\s+)?back\s+in\s+" + LANG, re.I),
    re.compile(r"\b(?:gets?|returns?|gives?)\s+(?:you\s+)?an?\s+(?:Taglish|Filipino|Tagalog|Cebuano)\s+(?:reply|answer|response)", re.I),
    re.compile(r"\bAI\s+ASSISTANT\s+REPLY\s+\((?:Taglish|Filipino|Tagalog)\)", re.I),
    re.compile(r"\bSpeaks\s+Filipino\s+fluently\b", re.I),
]
NEGATION = re.compile(r"\b(?:not|never|no|n't|instead\s+of|rather\s+than)\b[^.<]{0,40}$", re.I)


def english_only() -> bool:
    try:
        return bool(ENGLISH_RULE.search(PERSONA.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def check_text(src: str) -> list[str]:
    out = []
    for rx in CLAIMS:
        for m in rx.finditer(src):
            before = src[max(0, m.start() - 60):m.start()]
            if NEGATION.search(before):
                continue
            out.append(repr(src[max(0, m.start() - 70):m.end() + 20].replace("\n", " ")))
    return out


def shipped() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "*.js", "*.md"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    keep = []
    for p in out:
        if p.startswith(SKIP_DIRS) or "survey_ufai_rubric" in p:
            continue
        if p.endswith(".md") and not p.endswith(".html.md"):
            continue                              # only the published markdown twins, not repo docs
        keep.append(ROOT / p)
    return keep


def _self_test() -> int:
    fails = []
    bad = [
        "Speak your day. WorkHive Voice Journal transcribes, remembers, and reflects back in any language you speak.",
        "Whisper auto-detects the language, the journal companion reflects back in the same language.",
        "It listens, works out which language you used, writes down what you said, and replies in the same language.",
        "The companion accepts English, Filipino and Taglish and replies in the language you used.",
        "'May tagas sa drain valve ng tank 3, anong dapat i-check?' gets a Taglish reply with specific checks.",
        "AI ASSISTANT REPLY (Taglish):",
        "<tr><td>Speaks Filipino fluently</td><td>Yes</td><td>Yes</td></tr>",
    ]
    for s in bad:
        if not check_text(s):
            fails.append("must fail: " + s[:60])
    good = [
        "It understands Filipino, Taglish and English, and it replies in English.",
        "Ask in Cebuano or Taglish; it does not reply in Taglish, it replies in English.",
        "Whisper works out which language you spoke and writes it down.",
        "You can type to it or just talk in your own language, and it reads the answer out.",
        "Private spoken journal. Tap to talk in any language (English, Filipino/Tagalog, Cebuano).",
    ]
    for s in good:
        if check_text(s):
            fails.append("must pass: " + s[:60])
    print("FAIL reply-language-matches-persona self-test - " + "; ".join(fails) if fails
          else f"self-test OK: {len(bad)} non-English reply promises fail, {len(good)} true sentences pass")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    if not english_only():
        print("PASS reply-language-matches-persona - persona.ts no longer holds the English-reply rule, so a reply in the "
              "speaker's language is not ruled out")
        return 0
    hits = {}
    for p in shipped():
        try:
            errs = check_text(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if errs:
            hits[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(hits.items()):
        for e in errs[:3]:
            print(f"  BAD {f}: {e[:220]}")
    if hits:
        print(f"FAIL reply-language-matches-persona - {sum(len(v) for v in hits.values())} sentence(s) in {len(hits)} file(s) "
              "promise an AI reply in the speaker's language, but persona.ts says 'Always REPLY in English'")
        return 1
    print("PASS reply-language-matches-persona - no shipped page promises a reply in another language "
          "(persona.ts: understand any Philippine language, always reply in English)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
