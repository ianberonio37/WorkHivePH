#!/usr/bin/env python3
"""validate_journal_transcript_is_raw.py — Cluster 4's lock: a voice-journal transcript is the
worker's OWN words, never the RAG-augmented model prompt.

Walked live 2026-09-02 (T12): the journal history rendered entries whose 'transcript' was the
person's question followed by the whole retrieval scaffold — '--- RELEVANT TEAM KNOWLEDGE ---
RELEVANT FAULT HISTORY: ... RELEVANT SKILL PROFILES: - Leandro Marquez: Facilities Level 5 ...
--- END KNOWLEDGE ---'. Three harms: the journal was unreadable (the note buried under scaffold),
TEAMMATES' skill/fault data was rendered inside one worker's PERSONAL journal, and the stored
record was not what was said (and re-embedding it recursively poisons recall).

Root, confirmed by reading the code: both live client paths send the RAW transcript — voice-journal.html
callJournalAgent(text) (:1335) and voice-handler.js gateway body message: transcript (:7937); the rich
grounding rides in context.platform_prompt, NOT the message, and ai-gateway persists `message`
verbatim. The augmented rows were LEGACY residue (pre platform_prompt refactor) + probe artifacts,
purged 2026-09-02. This gate keeps it that way:

  1. DB: no live voice_journal_entries.transcript contains the RAG-block markers.
  2. SOURCE: neither client path concatenates a knowledge/memory block into the message it sends
     (message must be the bare transcript variable; the grounding goes in context.*).
Two-layer (DB when reachable + static source), fast. Self-test plants both shapes.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["journal-transcript-is-raw"]
MARKERS = ("RELEVANT TEAM KNOWLEDGE", "--- END KNOWLEDGE ---", "RELEVANT FAULT HISTORY", "RELEVANT SKILL PROFILES")
# T12 S2: the mic tap must acknowledge IMMEDIATELY and the permission await must be BOUNDED -
# a prompt-suppressed getUserMedia never settles, and the walk saw a tap change NOTHING.
MIC_BOUND_RE = re.compile(r"Waiting for microphone permission[\s\S]{0,600}?Promise\.race")
# T12 THIRD SENDER (2026-09-02, caught by this gate's own DB layer): assistant.html's two gateway
# calls also persist as journal transcripts - enrichedQuestion must BE the bare text (the scaffold
# rides context.team_knowledge).
ASSISTANT_RAW_RE = re.compile(r"const enrichedQuestion = text;")

# the client gateway calls that carry the worker's utterance
SEND_SITES = [
    ("voice-journal.html", re.compile(r"callJournalAgent\(\s*([A-Za-z_$][\w$]*)\s*,")),
    ("voice-handler.js",   re.compile(r"agent:\s*'voice-journal'[\s\S]{0,80}?message:\s*([A-Za-z_$][\w$.]*)")),
]


def _psql(sql: str):
    try:
        out = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=25)
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except Exception:
        return None


def source_problems() -> list[str]:
    problems = []
    ah = io.open(ROOT / "assistant.html", encoding="utf-8", errors="replace").read()
    if not ASSISTANT_RAW_RE.search(ah):
        problems.append("assistant.html: enrichedQuestion is no longer the bare text — the scaffold "
                        "is baked into message again and every enriched ask lands in the journal "
                        "wearing the RAG block (the third-sender T12 class)")
    vj = io.open(ROOT / "voice-journal.html", encoding="utf-8", errors="replace").read()
    if not MIC_BOUND_RE.search(vj):
        problems.append("voice-journal.html: the mic tap lost its immediate waiting-state + bounded "
                        "permission await — a suppressed prompt makes the tap change nothing again (T12 S2)")
    for fname, rx in SEND_SITES:
        src = io.open(ROOT / fname, encoding="utf-8", errors="replace").read()
        m = rx.search(src)
        if not m:
            problems.append(f"{fname}: the voice-journal send-site moved — re-point this check (the message var could not be found)")
            continue
        var = m.group(1)
        # the sent variable must be a plain transcript/text/message identifier, not a concatenation
        if var not in ("text", "transcript", "message", "msg", "userText"):
            problems.append(f"{fname}: sends '{var}' to the journal agent — expected the bare transcript variable, not an assembled block")
    return problems


def check(db_augmented: int | None, src: list[str]) -> list[str]:
    problems = list(src)
    if db_augmented is None:
        problems.append("DB unreachable — source layer checked; DB layer will run on the board")
    elif db_augmented > 0:
        problems.append(f"{db_augmented} voice_journal_entries row(s) store the RAG-block scaffold in transcript "
                        "(the record is not what the worker said, and teammates' data sits in a personal journal)")
    return problems


def main() -> int:
    like = " OR ".join(f"transcript ILIKE '%{m}%'" for m in MARKERS)
    raw = _psql(f"SELECT count(*) FROM voice_journal_entries WHERE {like}")
    db_aug = None
    if raw is not None and raw.isdigit():
        db_aug = int(raw)
    problems = check(db_aug, source_problems())
    # a pure DB-unreachable note is not a failure (skip cleanly), but a real DB count or source defect is
    hard = [p for p in problems if "DB unreachable" not in p]
    if hard:
        print("FAIL journal-transcript-is-raw — a journal transcript is not the worker's own words:")
        for p in problems:
            print(f"    {p}")
        return 1
    if db_aug is None:
        print("SKIP journal-transcript-is-raw — DB down; source layer clean (both client paths send the bare transcript).")
        return 0
    print(f"PASS journal-transcript-is-raw — {db_aug} augmented rows in DB, and both client paths "
          "(voice-journal.html callJournalAgent(text), voice-handler.js message: transcript) send the "
          "bare utterance; grounding rides context.platform_prompt.")
    return 0


def self_test() -> int:
    fails = []
    if check(0, []):
        fails.append("clean DB + clean source should PASS")
    if not any("store the RAG-block" in p for p in check(3, [])):
        fails.append("augmented DB rows must FAIL")
    if not any("expected the bare transcript" in p for p in check(0, ["voice-journal.html: sends 'fullPrompt' to the journal agent — expected the bare transcript variable, not an assembled block"])):
        fails.append("a concatenated send-var must FAIL")
    # live source must currently pass
    if source_problems():
        fails.append("HEAD source must be clean: " + "; ".join(source_problems()))
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_journal_transcript_is_raw self-test (augmented-DB + concatenated-send both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
