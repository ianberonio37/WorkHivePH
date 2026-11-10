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

# ★AND THE LOGBOOK'S SPEAK TO FILL HEARS ONE LANGUAGE (same walk). startSmartVoice() in logbook.html is the browser's
# SpeechRecognition with rec.lang = 'en-PH' (Chrome); the eight Philippine languages are the companion mic's Whisper path
# (voice-handler.js -> voice-transcribe). The capabilities guide's HowTo told readers to describe a work order to Speak to
# Fill "in Bisaya, Ilocano or any of the eight Philippine languages". Checked from logbook.html: for each "Speak to Fill",
# the text up to the next mention of the companion's mic / Voice Journal must not promise another language.
LOGBOOK = ROOT / "logbook.html"
FILL_SUBJECT = re.compile(r"Speak to Fill", re.I)
FILL_BOUNDARY = re.compile(r"companion'?s mic|companion mic|floating (?:helper|companion)|Voice Journal|voice-handler", re.I)
FILL_LANG = re.compile(r"\b(?:Bisaya|Cebuano|Ilocano|Hiligaynon|Kapampangan|Waray|Bikol|Pangasinan|Tagalog|"
                       r"eight\s+(?:Philippine\s+)?languages|any\s+(?:Philippine\s+)?language|your\s+own\s+language)\b", re.I)


def logbook_voice_lang() -> str:
    try:
        src = LOGBOOK.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    i = src.find("function startSmartVoice")
    m = re.search(r"rec\.lang\s*=\s*'([A-Za-z-]+)'", src[i:i + 4000]) if i >= 0 else None
    return m.group(1) if m else ""


def check_fill_text(src: str) -> list[str]:
    out = []
    for m in FILL_SUBJECT.finditer(src):
        tail = src[m.end():m.end() + 420]
        b = FILL_BOUNDARY.search(tail)
        if b:
            tail = tail[:b.start()]
        lm = FILL_LANG.search(tail)
        if lm and not NEGATION.search(tail[max(0, lm.start() - 60):lm.start()]):
            out.append("Speak to Fill is said to hear another language: "
                       + repr(src[m.start():m.end() + lm.end() + 20].replace("\n", " ")[:200]))
    return out


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
    fill_bad = ('{ "@type": "HowToStep", "position": 1, "name": "Open Speak to Fill on the Logbook", "text": "Go to the Logbook." }, '
                '{ "@type": "HowToStep", "position": 2, "text": "Say what happened in one plain sentence, in English, Taglish, '
                'Bisaya, Ilocano or any of the eight Philippine languages it understands." }')
    if not check_fill_text(fill_bad):
        fails.append("the old HowTo (Speak to Fill + eight languages) must fail")
    fill_good = ("On the Logbook, Speak to Fill takes one sentence in Philippine English and fills the problem. From the "
                 "companion's mic on any page, you can speak an action in any of the eight languages.")
    if check_fill_text(fill_good):
        fails.append("Speak to Fill in Philippine English, then the companion mic in eight languages, must pass")
    print("FAIL reply-language-matches-persona self-test - " + "; ".join(fails) if fails
          else f"self-test OK: {len(bad)} non-English reply promises fail, {len(good)} true sentences pass, "
               "Speak to Fill language claims checked both ways")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    reply_rule = english_only()
    fill_lang = logbook_voice_lang()
    fill_rule = fill_lang.lower().startswith("en")
    hits = {}
    for p in shipped():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        errs = (check_text(text) if reply_rule else []) + (check_fill_text(text) if fill_rule else [])
        if errs:
            hits[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(hits.items()):
        for e in errs[:3]:
            print(f"  BAD {f}: {e[:220]}")
    if hits:
        print(f"FAIL reply-language-matches-persona - {sum(len(v) for v in hits.values())} claim(s) in {len(hits)} file(s) "
              f"promise a language the code does not use (persona.ts English-reply rule: {reply_rule}; "
              f"Speak to Fill rec.lang: {fill_lang or '?'})")
        return 1
    print(f"PASS reply-language-matches-persona - no shipped page promises a language the code does not use "
          f"(replies: English per persona.ts = {reply_rule}; Speak to Fill hears {fill_lang or '?'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
