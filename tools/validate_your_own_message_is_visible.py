#!/usr/bin/env python3
"""A person must be able to see the message THEY sent, answered or not (T96).

MEASURED 2026-08-27 with two signed-in buyers on the same code path: Romeo Beltran, whose
inquiry had been replied to, saw his thread; Pablo Aguilar, whose inquiry was still pending, saw
NOTHING - no message, no state, no acknowledgement he had ever asked. The cause was one clause:
marketplace.html's buyer panel read `.not('reply_text', 'is', null)`, so a thread appeared only
once the OTHER party had got round to answering it.

★AN INVISIBLE SENT MESSAGE IS INDISTINGUISHABLE FROM ONE THAT NEVER SENT. That is why this is
worse than a slow reply: the buyer cannot tell whether to follow up, ask a different seller, or
give up, and the platform is holding the record the entire time. It is the silence doing the
lying - the same shape as an empty list that means "read failed", or a refusal shown for zero
milliseconds.

THE GATE HOLDS THREE THINGS, each of which was individually broken or absent before the fix:

  1. the buyer's own read must NOT be filtered to answered threads only;
  2. the pending state must be RENDERED, not merely fetched (fetching a row and drawing nothing
     is the same silence with extra steps);
  3. the pending line must carry a DATE. "Waiting for a reply" with no date is the same silence
     one step quieter, because how long it has been IS the buyer's question.

Deliberately narrow: this checks the buyer's own-message panel, not every list on the page. The
property is "your own outgoing message is visible to you", and marketplace.html is where a person
sends one to a stranger.

TEETH: synthetic negatives - each clause reverted in turn, including the exact pre-fix filter.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "marketplace.html"
FN = "loadMyInquiryReplies"


BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^\s*//.*$", re.M)


def _strip_comments(src: str) -> str:
    """Prose ABOUT code is not code.

    ★THIS GATE'S FIRST RUN FAILED ON THE FIXED FILE. The T96 fix removed the
    .not('reply_text','is',null) filter and left a comment EXPLAINING that it had done so - which
    quotes the removed clause verbatim. The gate matched its own subject's explanation and
    reported the defect as still present. A detector that reads comments will always convict the
    best-documented fix, because the clearest fixes are the ones that quote what they removed.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", src))


def _fn_body(src: str) -> str:
    """The buyer's own-inquiry loader, or '' if it is gone."""
    src = _strip_comments(src)
    i = src.find("async function " + FN)
    if i < 0:
        return ""
    j = src.find("\n  }", i)
    return src[i:j] if j > i else src[i:i + 4000]


def audit(src: str) -> list:
    body = _fn_body(src)
    out = []
    if not body:
        return [f"marketplace.html: {FN}() is gone - the buyer has no panel for their own "
                f"inquiries at all, which is the original defect restored wholesale"]

    # 1. not filtered to answered-only
    if re.search(r"\.not\(\s*['\"]reply_text['\"]\s*,\s*['\"]is['\"]\s*,\s*null\s*\)", body):
        out.append("marketplace.html: the buyer's inquiry read filters .not('reply_text','is',null), "
                   "so a thread is invisible until the SELLER answers - the buyer cannot see the "
                   "message they sent (measured: pending buyer saw nothing, replied buyer saw all)")

    # 2. the pending branch is actually rendered
    if not re.search(r"waiting for a reply", body, re.I):
        out.append("marketplace.html: no pending branch renders - an unanswered inquiry is fetched "
                   "and then drawn as nothing, which is the same silence with extra steps")

    # 3. and it says WHEN it was sent
    has_sent_var = re.search(r"\bsent\s*=\s*r\.created_at", body)
    sent_used = re.search(r"waiting for a reply", body, re.I) and re.search(r"e\(sent\)", body)
    if not (has_sent_var and sent_used):
        out.append("marketplace.html: the pending line carries no sent DATE - 'waiting for a reply' "
                   "without one is the same silence one step quieter, since how long it has been is "
                   "the buyer's actual question")

    # 4. the read is still scoped to the person asking (a panel that showed OTHER buyers'
    #    messages would satisfy every clause above and be a privacy defect)
    if not re.search(r"\.eq\(\s*['\"]buyer_name['\"]\s*,\s*WORKER_NAME\s*\)", body):
        out.append("marketplace.html: the buyer panel is no longer scoped to .eq('buyer_name', "
                   "WORKER_NAME) - it would show other people's inquiries")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real marketplace.html is clean", src, 0)]
    # the exact pre-fix filter, restored
    cases.append(("the pre-fix answered-only filter is caught",
                  src.replace(".order('created_at', { ascending: false }).order('id')",
                              ".not('reply_text', 'is', null)\n        .order('created_at', { ascending: false }).order('id')"), 1))
    cases.append(("removing the pending branch is caught",
                  src.replace("waiting for a reply", "REMOVED"), 1))
    cases.append(("dropping the sent date is caught",
                  src.replace("var sent = r.created_at", "var sent = ''; var _unused = r.created_at"), 1))
    cases.append(("losing the buyer scope is caught",
                  src.replace(".eq('buyer_name', WORKER_NAME)", ".eq('hive_id', HIVE_ID)"), 1))
    cases.append(("deleting the whole panel is caught",
                  src.replace("async function " + FN, "async function _retired_" + FN), 1))
    bad = 0
    for label, s, want in cases:
        f = audit(s)
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not SRC.exists():
        print("FAIL - marketplace.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("your-own-message-is-visible - a buyer sees the inquiry they sent, answered or not")
    if findings:
        print("\nFAIL - a person cannot see their own sent message:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every inquiry the buyer sent is shown, pending ones say so and say when.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
