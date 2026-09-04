#!/usr/bin/env python3
"""A password must arrive masked, and revealing it must ANNOUNCE that it is revealed (T170).

Two halves, and each is useless without the other.

MASKED BY DEFAULT: every password field ships `type="password"`, and the shared whPrompt honours
`inputType:'password'` end to end. That second one had a real gap - _mount read inputType, but
whPrompt built its own options object and never forwarded it, so a caller that asked for a masked
prompt got a plain text box and typed a secret in the clear on a shared plant tablet. The caller
was correct; the plumbing dropped it silently, which is the worst way for this to fail because
nothing looks wrong to anyone.

REVEAL MUST SPEAK: a show/hide toggle is a usability necessity - people mistype passwords on
phones - but a control that silently changes whether a secret is visible is a shoulder-surfing
hazard for the person who cannot see the screen state. So the toggle must flip BOTH `aria-label`
(what pressing it will do next) and `aria-pressed` (what state it is in now). This platform's
togglePwd already does; the gate exists so it keeps doing it.

★AND THE REASON THIS GATE READS aria-label RATHER THAN THE TOGGLE'S CODE SHAPE: when I searched
for controls that flip an input's type, I found ZERO - twice. The pattern I wrote expected a
quoted literal, and togglePwd assigns a TERNARY (`input.type = showing ? 'password' : 'text'`).
The only thing that proved the toggles existed at all was the three aria-labels reading "Show
password". The accessible name was the evidence my code-shape search could not see, so it is what
this gate anchors on.

TEETH: synthetic negatives - each half removed in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
UTILS = ROOT / "utils.js"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """The T170 fix's comment quotes the bug it removed; prose about a gap is not the gap."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit_index(src: str) -> list:
    out = []
    s = _strip_comments(src)

    # 1. every password field ships masked
    for m in re.finditer(r"<input\b[^>]*id=\"(si-password|su-password|su-confirm)\"[^>]*>", s):
        tag = m.group(0)
        if not re.search(r"type=\"password\"", tag):
            out.append(f"index.html: #{m.group(1)} does not ship type=\"password\" - the secret is "
                       f"typed in the clear on a device that may be shared")

    # 2. the toggle announces BOTH what it will do and what state it is in
    body = ""
    i = s.find("function togglePwd(")
    if i >= 0:
        j = s.find("\n  }", i)
        body = s[i:j] if j > i else s[i:i + 900]
    if not body:
        out.append("index.html: togglePwd() is gone - either the reveal affordance went with it "
                   "(people mistype passwords on phones) or it now flips visibility silently")
    else:
        if not re.search(r"setAttribute\(\s*['\"]aria-label['\"]", body):
            out.append("index.html: togglePwd no longer updates aria-label - a screen-reader user is "
                       "not told what pressing the control will do next")
        if not re.search(r"setAttribute\(\s*['\"]aria-pressed['\"]", body):
            out.append("index.html: togglePwd no longer updates aria-pressed - a screen-reader user "
                       "cannot tell whether their password is currently VISIBLE on screen, which is "
                       "exactly the person who cannot check by looking")
        if not re.search(r"\.type\s*=", body):
            out.append("index.html: togglePwd no longer changes the input type - the control "
                       "announces a reveal it does not perform")

    # 3. the toggles are actually wired to the fields
    if len(re.findall(r"togglePwd\('(si-password|su-password|su-confirm)'", s)) < 3:
        out.append("index.html: fewer than three password fields carry a reveal toggle - one of the "
                   "sign-in / sign-up / confirm fields has lost its affordance")
    return out


def audit_utils(src: str) -> list:
    out = []
    s = _strip_comments(src)
    # whPrompt must FORWARD inputType, not just accept it
    i = s.find("function whPrompt")
    seg = s[i:i + 2600] if i >= 0 else ""
    if not seg:
        out.append("utils.js: whPrompt() is gone - re-point this gate")
        return out
    if not re.search(r"inputType:\s*opts\.inputType", seg):
        out.append("utils.js: whPrompt no longer forwards inputType to the mount - a caller asking "
                   "for a masked prompt silently gets a plain text box, and types a secret in the "
                   "clear while everything looks correct")
    # and the mount must allow-list it rather than trusting the caller
    if not re.search(r"\['text','password','email','number','tel','url'\]", s):
        out.append("utils.js: the inputType allow-list is gone - an arbitrary caller-supplied type "
                   "reaches the DOM")
    return out


def selftest() -> int:
    idx = io.open(INDEX, encoding="utf-8", errors="replace").read()
    utl = io.open(UTILS, encoding="utf-8", errors="replace").read()
    cases = [("the real index.html is clean", audit_index(idx), 0),
             ("the real utils.js is clean", audit_utils(utl), 0)]
    cases.append(("an unmasked password field is caught",
                  audit_index(idx.replace('id="si-password" type="password"', 'id="si-password" type="text"')), 1))
    cases.append(("losing aria-pressed on the toggle is caught",
                  audit_index(idx.replace("btn.setAttribute('aria-pressed', showing ? 'false' : 'true');", "")), 1))
    cases.append(("losing aria-label on the toggle is caught",
                  audit_index(idx.replace("btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');", "")), 1))
    cases.append(("retiring togglePwd is caught",
                  audit_index(idx.replace("function togglePwd(", "function _retired_togglePwd(")), 1))
    cases.append(("whPrompt dropping inputType again is caught",
                  audit_utils(utl.replace("inputType:    opts.inputType || 'text',", "")), 1))
    cases.append(("losing the inputType allow-list is caught",
                  audit_utils(utl.replace("['text','password','email','number','tel','url']", "[]")), 1))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    for p in (INDEX, UTILS):
        if not p.exists():
            print(f"FAIL - {p.name} is gone; re-point this gate")
            return 1
    findings = audit_index(io.open(INDEX, encoding="utf-8", errors="replace").read())
    findings += audit_utils(io.open(UTILS, encoding="utf-8", errors="replace").read())
    print("a-secret-stays-masked - passwords arrive hidden, and revealing one says so out loud")
    if findings:
        print("\nFAIL - a secret is exposed, or revealed without announcing it:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every password ships masked, the prompt honours inputType, and reveal announces "
          "both its action and its state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
