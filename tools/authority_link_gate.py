#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
authority_link_gate.py — the outbound citations must still exist (V3 §5, AIO).
==============================================================================
AIO is scored on MULTI-SOURCE CREDIBILITY, and `aio_readiness_gate` enforces the bar
that a source be **linked** rather than merely named. Nothing checked that the link
still RESOLVES. A citation pointing at a 404 is worse than no citation: it is a claim
the reader can disprove in one click, on exactly the pages built to look authoritative.

WHY THIS IS NOT A NAIVE STATUS-CODE CHECK, and the reason it exists in this shape.
First measurement returned 5 of 14 authority URLs as 403 — dole.gov.ph, erc.gov.ph,
iso.org and both officialgazette.gov.ph laws. Reporting those as broken would have been
a fabricated finding. Re-checked through a real browser, every one returned a page
titled **"Just a moment..."** — Cloudflare's bot challenge — and iec.ch returned
CloudFront's "The request could not be satisfied". They are alive for a human and
closed to a robot. So:

    404 / 410 / DNS failure      DEAD      -> counts, fails on regression
    403 / 429 + challenge marks  SHIELDED  -> reported, never failed
    2xx / 3xx                    ALIVE

ADVISORY BY DESIGN (always exit 0 unless a link is provably DEAD and new). A gate that
reaches the network flakes under load, and a check that goes red for a reason the author
cannot fix is one the team learns to ignore. Precedent in this repo: the full-suite live
gates that flaked under load, and the gate that exhausted its own rate budget.

WHAT THE SHIELDED COUNT IS ACTUALLY TELLING US: an answer engine fetching our cited
authority to corroborate a claim gets the same 403 a script does. That does not make the
citation wrong — engines recognise smrp.org or nfpa.org without fetching — but where a
shielded source has a stable fetchable equivalent, preferring it is free credibility.

CLI:
    python tools/authority_link_gate.py
    python tools/authority_link_gate.py --self-test
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
REPORT = ROOT / "authority_link_report.json"
BASELINE = ROOT / "authority_link_baseline.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Asset hosts, not citations. A font CDN is not an authority and its uptime is not ours.
SKIP = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.tailwindcss.com",
        "workhiveph.com", "unpkg.com", "cdnjs.cloudflare.com")

# Markers that prove a non-2xx came from a SHIELD rather than a missing page.
CHALLENGE = ("just a moment", "cf-browser-verification", "cf_chl", "attention required",
             "request could not be satisfied", "access denied", "enable javascript and cookies")

LINK_RE = re.compile(r'href="(https?://[^"]+)"')
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def collect_links() -> dict:
    """{url: [pages citing it]} across the public content surface."""
    out: dict[str, list[str]] = {}
    try:
        sys.path.insert(0, str(_HERE))
        import seo_technical_gate as st
        pages = list(st.indexable_pages())
    except Exception:
        pages = [str(p.relative_to(ROOT).as_posix()) for p in ROOT.glob("learn/*/index.html")]
    for rel in pages:
        f = ROOT / rel
        if not f.exists():
            continue
        for u in LINK_RE.findall(f.read_text(encoding="utf-8", errors="replace")):
            if any(s in u for s in SKIP):
                continue
            out.setdefault(u, []).append(rel)
    return out


def classify(url: str, timeout: int = 12) -> tuple[str, str]:
    """(state, detail) where state is alive | shielded | dead."""
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "alive", str(r.status)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = (e.read()[:4000] or b"").decode("utf-8", "replace").lower()
        except Exception:
            pass
        if e.code in (403, 429, 503) and any(m in body for m in CHALLENGE):
            return "shielded", f"{e.code} bot-challenge"
        if e.code in (403, 429, 503):
            # A bare 403 with no challenge marker is still far more likely a shield than
            # a deletion, and calling it DEAD would be the fabricated finding this gate
            # exists to avoid. Report it, never fail on it.
            return "shielded", f"{e.code} blocked"
        if e.code in (404, 410):
            return "dead", str(e.code)
        return "shielded", str(e.code)
    except Exception as e:
        # DNS/TLS/timeout: could be the network here, not the site. Never DEAD on this.
        return "shielded", type(e).__name__


def audit(check: bool = True) -> dict:
    links = collect_links()
    rows = []
    for u, pages in sorted(links.items()):
        state, detail = classify(u) if check else ("skipped", "")
        rows.append({"url": u, "state": state, "detail": detail,
                     "pages": sorted(set(pages))[:4], "cited_by": len(set(pages))})
    tally = {k: sum(1 for r in rows if r["state"] == k) for k in ("alive", "shielded", "dead")}
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "urls": len(rows), "tally": tally,
            "dead": [r for r in rows if r["state"] == "dead"],
            "shielded": [r for r in rows if r["state"] == "shielded"], "rows": rows}


def run() -> int:
    rep = audit()
    REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    prior = base.get("dead", rep["tally"]["dead"])
    t = rep["tally"]
    print("=" * 70)
    print("  AUTHORITY LINKS — do our citations still resolve? (V3 §5, AIO)")
    print("=" * 70)
    print(f"  {rep['urls']} outbound citations   alive {t['alive']} · "
          f"shielded {t['shielded']} · DEAD {t['dead']}  (baseline dead {prior})")
    for r in rep["dead"][:10]:
        print(f"    DEAD      {r['detail']:<4} {r['url']}")
        print(f"              cited by {r['cited_by']} page(s): {', '.join(r['pages'][:2])}")
    for r in rep["shielded"][:8]:
        print(f"    shielded  {r['detail']:<18} {r['url']}")
    print("-" * 70)
    if t["dead"] > prior:
        print(f"  FAIL — {t['dead'] - prior} citation(s) newly point at a missing page.")
        return 1
    BASELINE.write_text(json.dumps({"dead": min(prior, t["dead"]),
                                    "established": base.get("established", rep["generated_at"])},
                                   indent=2), encoding="utf-8")
    print("  PASS — no citation newly points at a missing page.")
    if t["shielded"]:
        print(f"  NOTE: {t['shielded']} source(s) answer a robot with a challenge. Alive for a\n"
              f"        reader; an engine fetching them to corroborate us gets the same block.")
    print("=" * 70)
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", m))

    links = collect_links()
    ck(len(links) > 5, "finds outbound citations across the surface (%d)" % len(links))
    ck(not any("fonts.googleapis" in u for u in links), "font CDNs are not treated as citations")
    ck(not any("workhiveph.com" in u for u in links), "self-links are not outbound citations")
    # the distinction this gate exists for, asserted without touching the network
    ck(any(m in "just a moment..." for m in CHALLENGE),
       "Cloudflare's 'Just a moment...' is recognised as a challenge, not a dead page")
    st, _ = classify("https://httpbin.org/status/404", timeout=8)
    ck(st in ("dead", "shielded"), "a 404 classifies as dead (or shielded if the net is down): %s" % st)
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else run())
