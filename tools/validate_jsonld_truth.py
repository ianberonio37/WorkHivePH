#!/usr/bin/env python3
"""validate_jsonld_truth.py — MK7: structured data may not claim more than the canonical row.

The registered `seo-technical` gate reads JSON-LD that is WRITTEN INTO the HTML — retired @types,
malformed blocks, missing fields. It cannot see the other kind: structured data BUILT AT RUNTIME from
database values. `marketplace-seller-profile.html#injectJsonLd` composes a `Person` + `ItemList` from
whatever `_seller` and `_listings` happen to hold, and those are exactly the claims with something at
stake — a star rating and a listing count are what a buyer sees in the search result before they ever
reach the page.

Two failure modes, both already reasoned about correctly in that file and neither of them LOCKED:

  A FALSE STAR RATING. `aggregateRating` emitted for a seller with no reviews publishes a rating that
  stands on nothing — the marketplace equivalent of the seeded "3.9 stars, 1 completed" beside "No
  reviews yet" ([[feedback_trust_signal_needs_a_living_producer]]). Google treats fabricated
  AggregateRating as a structured-data violation, so it is a trust lie AND a ranking penalty.

  STRUCTURED DATA FOR AN ENTITY THAT DOES NOT EXIST. If the page body says "Seller not found", a
  `Person` schema describing that seller is a claim the page itself contradicts.

THE INVARIANT: in a runtime JSON-LD builder, every trust-bearing claim sits behind a condition that
tests the data backing it — a rating behind a COUNT, not merely behind a rating value (an average with
no reviews is precisely the defect), and the whole emitter behind an existence check on its subject.

Usage:  python tools/validate_jsonld_truth.py [--selftest]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

BUILDER = re.compile(r"function\s+(\w*[Jj]son[Ll]d\w*)\s*\(")


def body_of(src: str, start: int) -> str:
    i = src.find("{", start)
    if i < 0:
        return ""
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return src[i:]


def check_builder(name: str, body: str):
    """-> list of (ok, claim, detail)."""
    out = []

    # 1 — the emitter bails when its subject is absent.
    guarded = re.search(r"if\s*\(\s*!\s*_?\w+\s*\)\s*\{[^}]*return", body) is not None
    out.append((guarded, f"{name}: bails when the subject does not exist",
                "structured data would describe an entity the page's own body says is missing"))

    # 2 — a rating claim is behind a COUNT. Behind the average alone is the actual defect: an average
    #     can be non-null with zero reviews, which is how a trust signal ends up standing on nothing.
    if "aggregateRating" in body or "AggregateRating" in body:
        idx = min(i for i in (body.find("aggregateRating"), body.find("AggregateRating")) if i >= 0)
        window = body[max(0, idx - 320):idx]
        has_cond = re.search(r"if\s*\(", window) is not None
        has_count = re.search(r"(rating_count|reviewCount|review_count)\b", window) is not None
        out.append((has_cond and has_count,
                    f"{name}: the rating claim is gated on a review COUNT",
                    "an average with no reviews is a star rating standing on nothing — and Google "
                    "treats a fabricated AggregateRating as a structured-data violation"))

    # 3 — a truncated list must not advertise a total it is not emitting.
    m = re.search(r"numberOfItems\s*[:=]\s*([^,\n}]+)", body)
    if m:
        trunc = re.search(r"\.slice\(0,\s*(\d+)\)", body)
        claims_full = trunc is not None and trunc.group(1) not in m.group(1)
        out.append((not claims_full, f"{name}: numberOfItems agrees with what is emitted",
                    f"the list is truncated at {trunc.group(1) if trunc else '?'} while numberOfItems "
                    f"claims {m.group(1).strip()}"))
    return out


def scan_file(path: str):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    results = []
    for m in BUILDER.finditer(src):
        results += check_builder(m.group(1), body_of(src, m.end()))
    return results


def main():
    if "--selftest" in sys.argv:
        return selftest()
    pages = [p for p in os.listdir(ROOT) if p.endswith(".html")]
    print("=" * 84)
    print(f"  {BOLD}JSON-LD truth (MK7) — runtime structured data may not outrun the row{RST}")
    print("=" * 84)
    total, bad = 0, 0
    for p in sorted(pages):
        res = scan_file(os.path.join(ROOT, p))
        if not res:
            continue
        for ok, claim, detail in res:
            total += 1
            print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {p} · {claim}"
                  + (f"\n        {DIM}{detail}{RST}" if not ok else ""))
            bad += 0 if ok else 1
    print()
    if not total:
        print(f"  {YEL}SKIP{RST} no runtime JSON-LD builder found")
        return 0
    if bad:
        print(f"{RED}FAIL{RST} — {bad}/{total} structured-data claim(s) can outrun their backing row")
        return 1
    print(f"{GREEN}PASS{RST} — {total} runtime structured-data claim(s) are each gated on the data "
          f"that backs them")
    return 0


def selftest():
    ok = True
    good = ("function injectJsonLd(){ if (!_seller) { return; } "
            "if (_seller.rating_avg && _seller.rating_count) { s.aggregateRating = "
            "{'@type':'AggregateRating','ratingValue':1}; } }")
    avg_only = ("function injectJsonLd(){ if (!_seller) { return; } "
                "if (_seller.rating_avg) { s.aggregateRating = {'@type':'AggregateRating'}; } }")
    no_exist = ("function injectJsonLd(){ if (_seller.rating_avg && _seller.rating_count) "
                "{ s.aggregateRating = {'@type':'AggregateRating'}; } }")
    liar = ("function injectJsonLd(){ if (!_seller) { return; } "
            "var l = { numberOfItems: total, itemListElement: _listings.slice(0, 20) }; }")
    for src, want, label in ((good, 0, "a rating gated on a COUNT passes"),
                             (avg_only, 1, "a rating gated on the AVERAGE ALONE is caught"),
                             (no_exist, 1, "an emitter with no existence check is caught"),
                             (liar, 1, "numberOfItems disagreeing with a truncated list is caught")):
        m = BUILDER.search(src)
        res = check_builder(m.group(1), body_of(src, m.end()))
        got = len([r for r in res if not r[0]])
        if got != want:
            print(f"  {RED}FAIL{RST} {label} (found {got}, expected {want})"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} {label}")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
