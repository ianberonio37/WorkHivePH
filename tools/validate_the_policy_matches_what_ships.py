#!/usr/bin/env python3
"""The privacy policy must describe the analytics that actually ship (T165).

The policy said: "we do not run third-party analytics... when we add web analytics in the future,
this page will be updated." GA4 (wh-ga4.js) was already live on the public pages when it said that.

★A STALE SENTENCE ON A LEGAL SURFACE IS A DIFFERENT KIND OF DEFECT. Everywhere else on this
platform, drift means a number is wrong or a label is old. Here it means the document a regulator,
an enterprise buyer, or a worker reads to decide whether to trust us is making a false statement
about what we collect - and it was false in the direction that flatters us, which is the direction
nobody audits. Nothing on the page looked broken, because prose never looks broken.

The property is PARITY, checked in both directions so it cannot rot from either side:

  1. if wh-ga4.js loads on the public pages, the policy must NAME Google Analytics;
  2. the policy must not carry the future-tense denial ("when we add analytics", "we do not run
     third-party analytics") while it ships;
  3. and it must state the privacy-relevant configuration it actually runs - IP anonymization -
     since "we use GA4" without that is a thinner claim than the code supports.

★COMMENT-STRIPPED, AND THAT IS NOT A FORMALITY HERE. The fix left an HTML comment quoting the old
denial verbatim so the correction stays legible. A detector reading comments would find "when we
add web analytics in the future" in the FIXED file and report the defect as live - convicting the
page for documenting its own repair. This gate has already been caught by that on three other
subjects this session; the comment is the most reliable false positive in the whole family.

TEETH: synthetic negatives - the denial restored, the GA4 mention removed, the config claim dropped.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "privacy-policy" / "index.html"
GA4 = "wh-ga4.js"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

DENIALS = [
    r"when we add (web )?analytics",
    r"we do not (run|use) (any )?third-party analytics",
    r"no third-party analytics",
]


def _strip_comments(src: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def _ga4_pages() -> list:
    """Public pages that actually load the GA4 script."""
    out = []
    for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*/index.html")):
        try:
            if GA4 in io.open(p, encoding="utf-8", errors="replace").read():
                out.append(p.relative_to(ROOT).as_posix())
        except Exception:  # noqa: BLE001
            continue
    return sorted(out)


def audit(policy_src: str, ga4_pages: list) -> list:
    s = _strip_comments(policy_src)
    out = []
    ships = len(ga4_pages) > 0

    if ships:
        if not re.search(r"Google Analytics", s, re.I):
            out.append(f"privacy-policy: GA4 loads on {len(ga4_pages)} public page(s) "
                       f"(e.g. {ga4_pages[0]}) but the policy never names Google Analytics - the "
                       f"document people read to decide whether to trust us omits what we collect")
        for d in DENIALS:
            if re.search(d, s, re.I):
                out.append(f"privacy-policy: still carries the denial matching /{d}/ while GA4 ships on "
                           f"{len(ga4_pages)} page(s) - a false statement on a legal surface, false in "
                           f"the direction that flatters us, which is the direction nobody audits")
        if not re.search(r"anonymi[sz]", s, re.I):
            out.append("privacy-policy: names Google Analytics but not IP anonymization - the code runs "
                       "anonymize_ip, so the policy is claiming LESS privacy protection than ships, and "
                       "an under-claim on this surface is still a mismatch")
    else:
        # the mirror direction: GA4 gone but the policy still says it runs
        if re.search(r"Google Analytics", s, re.I) and not re.search(r"no longer|previously|used to", s, re.I):
            out.append("privacy-policy: describes Google Analytics but no page loads wh-ga4.js - the "
                       "policy now over-claims what is collected, which is the same drift in reverse")
    return out


def selftest() -> int:
    src = io.open(POLICY, encoding="utf-8", errors="replace").read()
    pages = _ga4_pages()
    cases = [("the real policy matches what ships", audit(src, pages), 0)]
    cases.append(("restoring the future-tense denial is caught",
                  audit(src + "<p>When we add web analytics in the future, this page will be updated.</p>", pages), 1))
    cases.append(("a 'no third-party analytics' claim is caught",
                  audit(src + "<p>We do not run third-party analytics.</p>", pages), 1))
    cases.append(("removing the Google Analytics mention is caught",
                  audit(re.sub(r"Google Analytics", "our tooling", src), pages), 1))
    cases.append(("dropping the anonymization claim is caught",
                  audit(re.sub(r"anonymi[sz]\w*", "configured", src, flags=re.I), pages), 1))
    cases.append(("...and the GA4 roster is not empty (the checks are not vacuous)",
                  [] if len(pages) > 0 else ["no page loads wh-ga4.js, so every clause above is inert"], 0))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not POLICY.exists():
        print("FAIL - privacy-policy/index.html is gone; re-point this gate")
        return 1
    pages = _ga4_pages()
    findings = audit(io.open(POLICY, encoding="utf-8", errors="replace").read(), pages)
    print("the-policy-matches-what-ships - the privacy policy describes the analytics that actually run")
    print(f"  pages loading {GA4}: {len(pages)}")
    if findings:
        print("\nFAIL - the policy and the code disagree about what is collected:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the policy names what ships, states its anonymization, and carries no stale denial.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
