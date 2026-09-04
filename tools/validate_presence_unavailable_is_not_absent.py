#!/usr/bin/env python3
"""A fact about the NETWORK must not be rendered as a claim about PEOPLE (T141).

hive.html's presence bar answers "who is here right now". When the realtime link failed, its
fallback said "Members offline" and painted every member with a solid offline dot - a positive
claim about people made entirely from a fact about the websocket. Presence unavailable is NOT
everyone-absent: the teammate you decide not to call may be standing at the machine.

★THE COST IS A DECISION, NOT A PIXEL. Nobody reads a presence bar for fun - they read it to decide
whether to walk over, phone someone, or handle it alone. A bar that says "offline" when it means
"I cannot see" sends that decision the wrong way while looking perfectly healthy, and the person
who acted on it has no way to know the bar was guessing.

It is the same shape as a failed read rendering as an empty list, and it needs its own gate for the
same reason that one did: the honest state and the alarming state are both quiet, so nothing
downstream can tell them apart.

THE FOUR CLAUSES, and the fourth is the one that keeps the other three honest:

  1. the fallback names the LINK, not the people - it says the live link is down;
  2. it does NOT assert offline/absent about members;
  3. the dot renders UNKNOWN (hollow - a transparent fill with an outline), never the solid dot
     that means a person is away, because the dot is what people actually read at a glance;
  4. renderPresence()'s genuine "No one online yet" MUST REMAIN DISTINCT. That state is TRUE when
     the link is UP and nobody is present, and collapsing the two into one message would trade
     this defect for its mirror image - reporting a real empty room as a network problem. Two
     notices, two truth conditions.

Bilingual: both strings carry EN and FIL, because a Filipino-language worker reading a stale
English fallback is not told anything.

TEETH: synthetic negatives - each clause reverted in turn, including the exact pre-fix wording.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "hive.html"
FN = "renderPresenceFallback"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """The fix's own comment quotes the pre-fix wording it removed.

    Every gate in this family that skipped this step convicted its own subject's explanation - the
    clearest fixes are the ones that quote what they deleted.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def _fn_body(src: str, name: str) -> str:
    s = _strip_comments(src)
    # ★THE OPEN PAREN IS LOAD-BEARING. Without it, find("function renderPresence") matches
    # renderPresenceFallback - which is DEFINED FIRST in this file - so the gate audited the
    # fallback against the live path's rules and produced two confident false findings about the
    # real, correct code. The same prefix-matching class as 'end' inside 'trend'. The clean-file
    # selftest case is what caught it, which is the entire reason that case exists.
    i = s.find("function " + name + "(")
    if i < 0:
        return ""
    j = s.find("\n}", i)
    return s[i:j] if j > i else s[i:i + 3000]


def audit(src: str) -> list:
    out = []
    body = _fn_body(src, FN)
    if not body:
        out.append(f"hive.html: {FN}() is gone - the realtime-down path has no honest renderer at all")
        return out

    # 1. it names the LINK
    if not re.search(r"live link down", body, re.I):
        out.append("hive.html: the presence fallback no longer says the LIVE LINK is down - it must "
                   "report the thing that is actually known (the network), not infer a state for people")

    # 2. it does not assert people are offline/absent
    if re.search(r">\s*(Members offline|Everyone offline|All offline|No one here)\s*<", body, re.I) \
       or re.search(r"_t\(\s*['\"]Members offline", body, re.I):
        out.append("hive.html: the fallback asserts members are OFFLINE - a positive claim about "
                   "people made from a fact about the websocket. The teammate you decide not to call "
                   "may be standing at the machine")

    # 3. the dot is UNKNOWN (hollow), not the solid away-dot
    dot = re.search(r"presence-dot[^>]*style=\"([^\"]*)\"", body)
    if not dot:
        out.append("hive.html: the fallback renders no presence-dot style - it falls back to the "
                   "default dot, which is the solid one that reads as 'this person is away'")
    else:
        style = dot.group(1)
        hollow = "background:transparent" in style.replace(" ", "") and "border" in style
        if not hollow:
            out.append("hive.html: the fallback's dot is not the hollow UNKNOWN dot (transparent fill "
                       "with an outline) - the dot is what people read at a glance, so a solid one "
                       "says 'away' no matter what the text beside it says")

    # 4. bilingual
    if not re.search(r"live link down['\"]\s*,\s*['\"][^'\"]+", body, re.I):
        out.append("hive.html: the unavailable string has no FIL half - a Filipino-language worker "
                   "reading an English-only fallback is told nothing")

    # 5. ★the honest empty state must stay DISTINCT
    live = _fn_body(src, "renderPresence")
    if live and not re.search(r"No one online yet", live):
        out.append("hive.html: renderPresence() no longer has its own 'No one online yet' state - "
                   "link-up-and-empty and link-down are DIFFERENT truths, and collapsing them trades "
                   "this defect for its mirror image (a real empty room reported as a network fault)")
    if live and re.search(r"live link down", live, re.I):
        out.append("hive.html: renderPresence() - the LINK-UP path - now claims the live link is down, "
                   "which reports a genuinely empty room as a network problem")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real hive.html is clean", src, 0)]
    cases.append(("the pre-fix 'Members offline' wording is caught",
                  src.replace("_t('Presence unavailable - live link down', 'Hindi makita ang presence - down ang live link')",
                              "_t('Members offline', 'Offline ang mga miyembro')"), 1))
    cases.append(("a solid dot in the fallback is caught",
                  src.replace("background:transparent;border:1px solid rgba(255,255,255,0.45);",
                              "background:rgba(255,255,255,0.35);"), 1))
    cases.append(("dropping the FIL half is caught",
                  src.replace("_t('Presence unavailable - live link down', 'Hindi makita ang presence - down ang live link')",
                              "'Presence unavailable - live link down'"), 1))
    cases.append(("retiring the whole fallback is caught",
                  src.replace("function renderPresenceFallback", "function _retired_renderPresenceFallback"), 1))
    cases.append(("collapsing the honest empty state into the fault message is caught",
                  src.replace("_t('No one online yet', 'Wala pang naka-online')",
                              "_t('Presence unavailable - live link down', 'x')"), 1))
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
        print("FAIL - hive.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("presence-unavailable-is-not-absent - a dead websocket is not a report about people")
    if findings:
        print("\nFAIL - the presence bar makes a claim it cannot support:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - link-down says the link is down, and the genuinely-empty room still says so itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
