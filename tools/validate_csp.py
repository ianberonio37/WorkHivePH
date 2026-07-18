#!/usr/bin/env python3
"""
validate_csp.py -- CSP-hardening ratchet for the front door (CSP_HARDENING_ARC.md, I6a).

Ian chose the STRICT + nonce path. That build is multi-phase (server-side per-request
nonce + inline-handler->addEventListener + Tailwind-CDN->built-CSS + strict CSP). Until
it lands, this gate does two jobs:

  1. FORWARD-ONLY RATCHET (blocking): the count of inline event handlers (`onclick=`,
     `onsubmit=`, ...) and un-nonced inline <script> blocks on index.html must NEVER
     INCREASE beyond the recorded baseline. New inline handlers make the eventual strict
     CSP strictly harder, so we freeze the debt where it is and only allow it to shrink.

  2. TARGET REPORT (non-blocking): prints the remaining distance to strict-CSP-done
     (CSP present? inline handlers == 0? every inline <script> nonced? Tailwind CDN gone?),
     so the CSP arc has a measured scoreboard.

When the strict build lands, flip STRICT_ENFORCED=True to require: a CSP is present,
0 inline handlers, every inline <script> nonced, and the Tailwind CDN dropped.

Baseline is stored in `csp_baseline.json` (auto-created on first run).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "index.html")
BASELINE = os.path.join(ROOT, "csp_baseline.json")
STRICT_ENFORCED = False  # flip True when the strict-CSP build lands

INLINE_HANDLER_RE = re.compile(r"\son[a-z]+\s*=\s*\"", re.I)
INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.I)
NONCED_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*\bnonce=", re.I)
CSP_RE = re.compile(r"Content-Security-Policy", re.I)
TAILWIND_CDN_RE = re.compile(r"cdn\.tailwindcss\.com", re.I)


def measure(html):
    inline_handlers = len(INLINE_HANDLER_RE.findall(html))
    inline_scripts = len(INLINE_SCRIPT_RE.findall(html))
    nonced_scripts = len(NONCED_SCRIPT_RE.findall(html))
    return {
        "inline_handlers": inline_handlers,
        "inline_scripts": inline_scripts,
        "unnonced_scripts": inline_scripts - nonced_scripts,
        "csp_present": bool(CSP_RE.search(html)),
        "tailwind_cdn": bool(TAILWIND_CDN_RE.search(html)),
    }


def main():
    with open(TARGET, encoding="utf-8", errors="ignore") as f:
        html = f.read()
    m = measure(html)

    if not os.path.exists(BASELINE):
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        print("BASELINE  validate_csp.py -- recorded index.html CSP baseline:")
        for k, v in m.items():
            print("  %-18s %s" % (k, v))
        base = m
    else:
        with open(BASELINE, encoding="utf-8") as f:
            base = json.load(f)

    failures = []
    # RATCHET: inline handlers + un-nonced scripts must not INCREASE
    if m["inline_handlers"] > base.get("inline_handlers", m["inline_handlers"]):
        failures.append("inline event handlers increased %d -> %d (add addEventListener, not onclick=)"
                        % (base["inline_handlers"], m["inline_handlers"]))
    if m["unnonced_scripts"] > base.get("unnonced_scripts", m["unnonced_scripts"]):
        failures.append("un-nonced inline <script> blocks increased %d -> %d"
                        % (base["unnonced_scripts"], m["unnonced_scripts"]))

    # TARGET report
    print("validate_csp.py -- index.html CSP-readiness (target = strict CSP done):")
    print("  CSP present ............ %s   (target: True)" % m["csp_present"])
    print("  inline handlers ........ %-4d (target: 0; baseline %d)" % (m["inline_handlers"], base.get("inline_handlers", 0)))
    print("  un-nonced inline <script> %-4d (target: 0; baseline %d)" % (m["unnonced_scripts"], base.get("unnonced_scripts", 0)))
    print("  Tailwind CDN (eval) .... %s   (target: False -> built CSS)" % m["tailwind_cdn"])

    if STRICT_ENFORCED:
        if not m["csp_present"]:
            failures.append("STRICT: no Content-Security-Policy present")
        if m["inline_handlers"] > 0:
            failures.append("STRICT: %d inline event handlers remain (must be 0)" % m["inline_handlers"])
        if m["unnonced_scripts"] > 0:
            failures.append("STRICT: %d un-nonced inline scripts remain (must be 0)" % m["unnonced_scripts"])
        if m["tailwind_cdn"]:
            failures.append("STRICT: Tailwind CDN (eval surface) still present")

    if failures:
        print("FAIL  validate_csp.py:")
        for x in failures:
            print("  - " + x)
        sys.exit(1)
    done = (m["csp_present"] and m["inline_handlers"] == 0 and m["unnonced_scripts"] == 0 and not m["tailwind_cdn"])
    print("PASS  validate_csp.py -- ratchet held%s" % (" + STRICT CSP DONE ✅" if done else " (strict build still in progress)"))
    sys.exit(0)


if __name__ == "__main__":
    main()
