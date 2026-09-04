""" -*- coding: utf-8 -*-
A wall that promises to send you back must send you back - and only somewhere safe (T4).

An anon or hive-less visitor who taps into Community is bounced to the hive gate. Before the fix
that bounce dropped the destination, so a person who set out for one place arrived somewhere else
with no way back to what they wanted. Now community stamps `hive.html?return=community.html` and
the hive page renders a "Continue to Community" banner that honours it.

TWO HALVES, AND EITHER ALONE IS USELESS:

  1. the SENDER stamps where it came from;
  2. the RECEIVER renders a control that goes there.

A stamp nobody reads is a query string. A banner with nothing to read is dead markup. They are
gated together because they are one promise implemented in two files, and a fix to either side
alone silently breaks it with nothing erroring.

★AND THE THIRD CLAUSE IS THE ONE THAT MATTERS MOST, because it is a SECURITY property hiding inside
a usability feature. `?return=` is user-controllable, and a naive implementation does
`location.href = raw` - which is an open redirect: a link to our own trusted domain that lands the
person on an attacker's page, wearing our reputation. The guard must be a strict ALLOW-LIST of a
bare same-origin filename, never a blocklist of bad prefixes; a blocklist that rejects "http://"
and "//" still passes "/\\evil.com" and a dozen other encodings. Nothing about the feature LOOKS
security-sensitive, which is exactly why the shape has to be locked.

Fourth: the label is written with textContent, not innerHTML - the parameter reaches the DOM as a
string, so a crafted filename cannot inject markup.

TEETH: synthetic negatives - each half removed, the allow-list loosened to a blocklist, and the
label switched to innerHTML.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENDER = ROOT / "community.html"
RECEIVER = ROOT / "hive.html"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """The receiver's comment explains the whole contract, including the security reasoning."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(sender: str, receiver: str) -> list:
    s, r = _strip_comments(sender), _strip_comments(receiver)
    out = []

    # 1. the sender stamps its origin
    if not re.search(r"hive\.html\?return=community\.html", s):
        out.append("community.html: the hive bounce no longer stamps ?return= - a person who set out "
                   "for Community arrives at the hive gate with no way back to what they wanted, and "
                   "nothing on screen explains why they are there")

    # 2. the receiver honours it
    if not re.search(r"URLSearchParams\(location\.search\)\.get\(\s*['\"]return['\"]\s*\)", r):
        out.append("hive.html: nothing reads the ?return= parameter - the sender's stamp is now just a "
                   "query string nobody acts on, which is the same as not sending it")
    if not re.search(r"Continue to", r):
        out.append("hive.html: the Continue banner is gone - the return promise is made by the sender "
                   "and kept by nobody")

    # 3. ★the allow-list, not a blocklist
    allow = re.search(r"\.test\(\s*raw\s*\)", r)
    pattern = re.search(r"/\^\[a-z0-9\]\[a-z0-9_-\]\{0,\d+\}\\\.html\$/i", r)
    if not allow or not pattern:
        out.append("hive.html: the ?return= value is no longer validated against a strict same-origin "
                   "FILENAME allow-list - ?return= is user-controllable, so this becomes an OPEN "
                   "REDIRECT: a link to our own trusted domain that lands the person on an attacker's "
                   "page wearing our reputation. A blocklist is not a substitute - one that rejects "
                   "'http://' and '//' still passes '/\\\\evil.com' and a dozen encodings")

    # 4. the label cannot inject markup
    banner = ""
    m = re.search(r"var raw = new URLSearchParams[\s\S]{0,1400}", r)
    if m:
        banner = m.group(0)
    if banner and re.search(r"\.innerHTML\s*=", banner):
        out.append("hive.html: the return banner builds its label with innerHTML - the parameter is "
                   "user-controllable, so a crafted filename injects markup. textContent is what makes "
                   "the allow-list's job survivable if it is ever loosened")
    return out


def selftest() -> int:
    s = io.open(SENDER, encoding="utf-8", errors="replace").read()
    r = io.open(RECEIVER, encoding="utf-8", errors="replace").read()
    cases = [("the real pair is clean", audit(s, r), 0)]
    cases.append(("the sender dropping ?return= is caught",
                  audit(s.replace("hive.html?return=community.html", "hive.html"), r), 1))
    cases.append(("the receiver ignoring the param is caught",
                  audit(s, r.replace("new URLSearchParams(location.search).get('return')", "''")), 1))
    cases.append(("losing the Continue banner is caught",
                  audit(s, r.replace("'Continue to '", "''")), 1))
    cases.append(("loosening the allow-list to a blocklist is caught",
                  audit(s, re.sub(r"if \(!/\^\[a-z0-9\]\[a-z0-9_-\]\{0,48\}\\\.html\$/i\.test\(raw\)\) return;",
                                  "if (raw.indexOf('http') === 0) return;", r)), 1))
    cases.append(("building the label with innerHTML is caught",
                  audit(s, r.replace("a.textContent = 'Continue to ' + label;",
                                     "a.innerHTML = 'Continue to ' + label;")), 1))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    for p in (SENDER, RECEIVER):
        if not p.exists():
            print(f"FAIL - {p.name} is gone; re-point this gate")
            return 1
    findings = audit(io.open(SENDER, encoding="utf-8", errors="replace").read(),
                     io.open(RECEIVER, encoding="utf-8", errors="replace").read())
    print("the-return-promise-is-kept-safely - the wall sends you back, and only somewhere same-origin")
    if findings:
        print("\nFAIL - the return promise is broken, or it can be pointed somewhere it should not go:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the sender stamps, the receiver honours, the destination is allow-listed and the "
          "label cannot inject.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
