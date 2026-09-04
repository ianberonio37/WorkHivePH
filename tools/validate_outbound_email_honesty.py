#!/usr/bin/env python3
"""outbound-email-honesty — T111: comms held to the same bar as the glass (2026-08-26).

The DP dims (manipulation absence) are measured on PAGES. Email escapes them
entirely: it is the one surface that reaches a person who may not even have an
account, cannot be corrected once sent, and is where urgency-shaped copy is most
tempting and least visible to any UI test.

T111's census found ONE outbound template — send-report-email — and audited it
clean, then fixed its real gap: the footer said only "Sent via WorkHive Report
Sender", so the recipient of an outward irreversible email could not tell WHICH
PERSON sent it, nor how to stop receiving them. That fix shipped with no gate.

FOUR ASSERTIONS:

  1. ONE TEMPLATE. Exactly the known set of functions builds outbound email. This
     is the census made living rather than a one-time observation: a new
     marketing or re-engagement lane cannot appear un-audited, which is the
     scenario T111 is named for ("the re-engagement email that lies").
  2. THE FOOTER NAMES THE SENDER. A person, not just the product — an
     irreversible message from an unidentified sender is the shape a recipient
     cannot act on.
  3. THE FOOTER CARRIES A STOP PATH, and an ACCURATE one. Recipients live in the
     sender's own contact list, so "ask the sender to remove you" is the truthful
     instruction; a fake one-click unsubscribe would be a worse lie than none.
  4. NO MANIPULATION VOCABULARY in the template's own literals. Checked against
     the copy the TEMPLATE owns, never against report content — the reports carry
     real words like "overdue" and "risk", and a lint that policed those would be
     demanding the product misdescribe genuine urgency to satisfy a gate.

★WHY LITERALS ONLY. The dangerous copy is the copy a developer writes into the
template and every recipient then receives. Data-driven text is the report's own
truth, already governed by the grounding contract ("do NOT invent, change, or
recompute any number").

Usage: python tools/validate_outbound_email_honesty.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# the audited outbound lane. A new name here is a deliberate decision, not a drive-by.
KNOWN_SENDERS = {"send-report-email"}

# urgency / scarcity / guilt vocabulary — the DP classes, in the wording email actually uses
MANIPULATION = [
    r"act now", r"don'?t miss", r"last chance", r"limited time", r"expires? soon",
    r"only \d+ (left|remaining)", r"hurry", r"final notice", r"before it'?s too late",
    r"your (hive|team) needs you", r"you'?ve been missed", r"we miss you",
    r"don'?t let .* down", r"everyone else", r"others are", r"\bfomo\b",
]


def main() -> int:
    senders = set()
    for f in sorted(glob.glob(str(ROOT / "supabase" / "functions" / "*" / "index.ts"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        # a function that POSTs to an email provider is an outbound sender
        if re.search(r"api\.resend\.com|sendgrid|mailgun|postmark", src, re.I):
            senders.add(Path(f).parent.name)

    fails = []
    print(f"  outbound senders: {', '.join(sorted(senders)) or 'none'}")
    unknown = senders - KNOWN_SENDERS
    if unknown:
        fails.append(
            f"NEW outbound email lane(s): {', '.join(sorted(unknown))} — T111 audited exactly "
            f"{sorted(KNOWN_SENDERS)}. Audit the new template against the same bar (sender named, "
            f"accurate stop path, no urgency vocabulary), then add it to KNOWN_SENDERS here.")
    missing = KNOWN_SENDERS - senders
    if missing:
        fails.append(f"expected outbound sender(s) gone: {', '.join(sorted(missing))} — this gate is "
                     f"now measuring nothing; re-point it at the real template.")

    for name in sorted(senders & KNOWN_SENDERS):
        src = io.open(ROOT / "supabase" / "functions" / name / "index.ts", encoding="utf-8", errors="replace").read()

        if not re.search(r"Sent by \$\{", src):
            fails.append(f"{name}: the footer no longer names the SENDING PERSON — a recipient of an "
                         f"irreversible message cannot tell who sent it.")
        if not re.search(r"stop receiving these reports.*remove you", src, re.S | re.I):
            fails.append(f"{name}: the footer no longer carries the stop path. Recipients live in the "
                         f"sender's contact list, so 'ask the sender to remove you' is the ACCURATE "
                         f"instruction — a fake one-click unsubscribe would be a worse lie than none.")

        # literals the template itself owns: strings inside the HTML builder, minus interpolations
        literals = " ".join(re.findall(r'>([^<>{}]{4,120})<', src))
        for pat in MANIPULATION:
            m = re.search(pat, literals, re.I)
            if m:
                fails.append(f"{name}: template literal contains manipulation vocabulary "
                             f"\"{m.group(0)}\" — urgency the recipient cannot verify is the DP class "
                             f"this trajectory is named for.")

    if fails:
        print("FAIL outbound-email-honesty:")
        for f in sorted(set(fails)):
            print("    - " + f)
        return 1
    print("PASS outbound-email-honesty — one audited template, the sender is named, the stop path is "
          "there and accurate, and no urgency vocabulary in the copy the template owns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
