#!/usr/bin/env python3
r"""no-eaten-escapes - a control character in source is a regex that cannot fire.

When source is written through nested quoting layers - a shell heredoc, a nested python -c, an
editor round-trip - a `\b` can arrive on disk as a literal BACKSPACE byte (0x08). The file still
parses, the regex still compiles, and the alternative it guards can never match anything, because
no real string contains a backspace. Nothing errors. The check just quietly stops checking.

MEASURED 2026-08-26, five instances in one session:
  * shift-brain.html (x2) and report-sender.html - `/\b429\b|rate.?limit|too many requests/i`
    had become `/<BS>429<BS>|.../`, so a bare "429" or "Request failed with status 429" was NOT
    recognised as rate limiting. Proven against the shipped file: "429" -> false before, true
    after. These are the pages that tell a person WHY their report or shift plan did not run.
  * tools/prove_route_numbers.mjs - the suffixed-unit branch could not fire, so the prover
    over-reported naked numbers.
  * two gates written the same day, whose own matchers were partly dead.
An earlier session found 28 more at once, including - exactly this - a `\b429\b` fix that was
itself dead and passed only because the text happened to say "Too Many Requests".

★A SNIPPET IS NOT THE ARTIFACT. That earlier session "proved" the boundary held by testing
`4290` against `429` in a separate snippet, never against the file, and shipped a dead regex. This
gate reads BYTES off disk for that reason: it cannot be fooled by a console that renders 0x08 as
nothing, which is precisely how the bug hides. (The same invisibility wasted several minutes here -
the repaired-looking line printed as `/429|.../` while still holding the control character.)

★WHY BYTES AND NOT A REGEX. Every other detector in this repo could itself be a victim of the bug
it hunts. A byte count has no matcher to break.

★SCOPE. Repo-wide over source we author. validate_page_ui_provers.py carries the same check scoped
to provers; this subsumes it - and the reason for the wider net is that the three shipped instances
here were all OUTSIDE that scope, the same too-narrow-scope failure this class keeps producing.

Usage: python tools/validate_no_eaten_escapes.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR = re.compile(r"node_modules|\.git|_bak|backup|\.tmp|__pycache__|_fixtures|dist|build", re.I)
SKIP_FILE = re.compile(r"maplibre|\.min\.|bundle", re.I)
EXTS = (".py", ".js", ".mjs", ".ts", ".html", ".sql", ".json", ".css", ".md")

# 0x08 backspace, 0x0B vertical tab, 0x0C form feed: all are eaten \b / \v / \f.
# \t (0x09), \n (0x0A), \r (0x0D) are legitimate whitespace and are NOT flagged.
EATEN = {0x08: r"\b", 0x0B: r"\v", 0x0C: r"\f"}


def main() -> int:
    scanned, findings = 0, []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if SKIP_DIR.search(rel) or SKIP_FILE.search(p.name):
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        scanned += 1
        for code, intended in EATEN.items():
            n = raw.count(bytes([code]))
            if n:
                line = raw[:raw.index(bytes([code]))].count(b"\n") + 1
                findings.append(f"{rel}:{line} - {n} literal 0x{code:02X}, written as {intended}")

    print(f"  files scanned: {scanned} | eaten escapes found: {len(findings)}")
    for f in findings[:10]:
        print("    - " + f)

    if findings:
        print("FAIL no-eaten-escapes - a control character sits where an escape was written. The regex")
        print("    around it compiles and can never match, so the check it belongs to silently stops")
        print("    checking - and a page that should say \"you have hit the rate limit\" says something")
        print("    generic instead. Repair in BYTES (0x08 -> backslash-b); a shell will eat it again.")
        return 1
    print(f"PASS no-eaten-escapes - {scanned} source files, no control character standing in for an escape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
