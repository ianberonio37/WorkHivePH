#!/usr/bin/env python3
"""
validate_landing.py -- ratchet gate for the Landing + Home-Dashboard Deep Arc
(LANDING_DASHBOARD_DEEP_ARC.md). Locks the confirmed-and-fixed front-door
defects so they cannot silently regress. Static-only (no browser/DB); pairs the
LIVE Playwright deepwalk which measures axe/CWV/RPC parity.

Each check maps to a spine sub-dimension + the arc's Phase-5 fix register.
Exit 0 = all locked invariants hold; exit 1 = a regression.

Run standalone:  python tools/validate_landing.py
Registered in run_platform_checks "AI Validation" (skip_if_fast).
"""
import re
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
SUBDIRS = ["about", "learn", "feedback", "privacy-policy", "terms-of-service"]

failures = []
checks = 0


def read(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def meta_content(html, attr, key):
    # attr is 'property' or 'name'; tolerant of attribute order + spacing
    m = re.search(
        r'<meta\s+[^>]*%s\s*=\s*"%s"[^>]*content\s*=\s*"([^"]*)"' % (attr, re.escape(key)),
        html, re.I)
    if m:
        return m.group(1)
    m = re.search(
        r'<meta\s+[^>]*content\s*=\s*"([^"]*)"[^>]*%s\s*=\s*"%s"' % (attr, re.escape(key)),
        html, re.I)
    return m.group(1) if m else None


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


idx = read(INDEX)

# ---- G6 (F4): social share titles must not drop the audience token -----------
# <title>, og:title, twitter:title must all agree (the arc found og/twitter
# silently dropped "Filipino" -> share cards lost the core audience token).
title = re.search(r"<title>([^<]*)</title>", idx, re.I)
title = title.group(1).strip() if title else None
og_title = meta_content(idx, "property", "og:title")
tw_title = meta_content(idx, "name", "twitter:title")
check(title and og_title and og_title == title,
      "G6: og:title != <title>  (og=%r title=%r)" % (og_title, title))
check(title and tw_title and tw_title == title,
      "G6: twitter:title != <title>  (twitter=%r title=%r)" % (tw_title, title))

# ---- AI3: no fabricated hard-percentage metric in the marketing copy ---------
# The arc found "98% precision" on the AI worker-matching claim with no source
# behind v_worker_assignment_truth. Ban any un-cited "NN% precision/accuracy".
fab = re.findall(r"\b\d{1,3}\s*%\s*(?:precision|accuracy)\b", idx, re.I)
check(not fab, "AI3: fabricated precision/accuracy metric in copy: %r" % (fab,))

# ---- F4/AI4: no account-less "open any tool right now" claim ------------------
# C4 removed account-less guest access; a cold visitor clicking a hero tool hits
# the sign-up wall (verified live). The FAQ + FAQPage JSON-LD used to advertise
# "Open any tool right now ... in Solo Mode without a hive" -- false, and
# double-broadcast to answer engines via schema. Ban the no-signup phrasing.
check("open any tool right now" not in idx.lower(),
      "F4/AI4: account-less 'open any tool right now' Solo-Mode claim (C4 removed guest access)")

# ---- F4: every landing subdir must carry a Twitter Card ----------------------
# feedback/ shipped without twitter:card while the other 4 subdirs had it.
for d in SUBDIRS:
    p = os.path.join(ROOT, d, "index.html")
    if not os.path.exists(p):
        failures.append("F4: subdir missing on disk: %s/index.html" % d)
        checks += 1
        continue
    sub = read(p)
    card = meta_content(sub, "name", "twitter:card")
    check(card is not None, "F4: %s/ missing twitter:card meta" % d)

# ---- I2/head hygiene: calm-dashboard contract meta still present -------------
check('name="calm-dashboard"' in idx.replace("'", '"') or "calm-dashboard" in idx,
      "index.html lost the calm-dashboard contract meta")

try:
    import json
    with open(os.path.join(ROOT, "landing_validation.json"), "w", encoding="utf-8") as f:
        json.dump({"checks": checks, "failures": failures,
                   "status": "FAIL" if failures else "PASS"}, f, indent=2)
except Exception:
    pass

if failures:
    print("FAIL  validate_landing.py -- %d/%d checks failed:" % (len(failures), checks))
    for f in failures:
        print("  - " + f)
    sys.exit(1)

print("PASS  validate_landing.py -- %d landing invariants hold" % checks)
sys.exit(0)
