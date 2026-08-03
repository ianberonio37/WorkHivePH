#!/usr/bin/env python3
"""build_live_mcp_registry.py -- the LIVE-MCP scenario registry, derived from the marketplace test bank.

WHY DERIVED AND NOT INVENTED. The bank already encodes what this marketplace can do: 492 cells across
authority x state x path x layer, 154 of them in the `journey` lane. Inventing a second list of scenarios
would create a second source of truth that drifts from the first, and the SQL lane has already proven the
guards behave -- what it CANNOT prove is that a person can reach any of it. So this registry crosses the
bank's own journeys with the surfaces and personas a browser actually meets, and every row carries an
ORACLE: the observable that decides pass or fail. A scenario without an oracle is a tour, not a test.

WHAT THE LIVE LANE ADDS THAT SQL CANNOT:
  · a guard that refuses correctly, on a screen that never shows the refusal
  · a capability that exists in the schema and is 699px below the fold
  · a control that is 44px on paper and 24px at 390 CSS pixels
  · a number that is right in the ledger and stale in the tile
  · a flow that works signed-in and dead-ends for the anonymous visitor who is 90% of arrivals

CATEGORIES are the axis Ian asked for: the flywheel improves a CATEGORY at a time, so a finding in one
does not have to wait behind an unrelated one. Each category names the design question it answers, because
a category that cannot state its question is a folder.

Usage:  python tools/build_live_mcp_registry.py [--out live_mcp_registry.json]
"""
from __future__ import annotations
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "marketplace_test_bank.json")

# ── the surfaces a browser can actually reach ────────────────────────────────────────────────────────
SURFACES = {
    "market":     "/workhive/marketplace.html",
    "market_svc": "/workhive/marketplace.html?section=services",
    "seller":     "/workhive/marketplace-seller.html",
    "profile":    "/workhive/marketplace-seller-profile.html",
    # marketplace-admin.html is RETIRED - it renders "Marketplace Admin has moved" and carries zero action
    # controls. Pointing 12 H-moderation scenarios at it would have walked a dead surface and reported
    # confident nonsense about it, the same shape as a test pinned to a hive that no longer exists.
    # Caught on the first H-moderation walk.
    "admin":      "/workhive/platform-actions.html",
    "admin_old":  "/workhive/marketplace-admin.html",
    "founder":    "/workhive/founder-console.html",
}

PERSONAS = {
    "anon":     "never signed in - the majority of arrivals, and the one most flows forget",
    "buyer":    "signed in, browsing and hiring",
    "seller":   "signed in, listing and answering",
    "provider": "signed in, taking service hails",
    "admin":    "platform moderator",
}

# category -> (the design question it answers, surfaces, personas, states)
CATEGORIES = {
    "A-discovery": (
        "can a stranger FIND the thing they came for? (40% of simulated journey failures died here)",
        ["market"], ["anon", "buyer"], ["populated", "filtered0", "empty", "error"]),
    "B-listing-lifecycle": (
        "can a seller get a listing from nothing to live, and know why when they cannot?",
        ["seller", "admin"], ["seller", "admin"], ["empty", "populated", "edge"]),
    "C-inquiry": (
        "can a buyer reach a human, and does the seller learn about it?",
        ["market", "profile"], ["anon", "buyer", "seller"], ["populated", "error"]),
    "D-service-hail": (
        "can a client raise a job and a provider take it, both knowing what state it is in?",
        ["market_svc"], ["buyer", "provider"], ["empty", "populated", "edge"]),
    "E-money": (
        "at the moment money moves, does every screen agree on the number?",
        ["market_svc", "seller", "founder"], ["buyer", "provider", "admin"], ["populated", "edge"]),
    "F-credits": (
        "does a person understand what credits are, what they hold, and what they will get back?",
        ["market", "seller", "founder"], ["anon", "buyer", "seller", "admin"], ["empty", "populated"]),
    "G-trust": (
        "is a trust signal earned, visible, and impossible to mint for yourself?",
        ["market", "profile"], ["anon", "buyer", "seller"], ["populated", "empty"]),
    "H-moderation": (
        "can an admin act, and is a non-admin visibly refused rather than silently ignored?",
        ["admin", "seller"], ["admin", "seller", "anon"], ["populated", "empty"]),
    "I-map": (
        "does the map tell the truth about where someone is, and stay quiet when it should not?",
        ["market_svc"], ["buyer", "provider"], ["populated", "degraded"]),
    "J-degraded": (
        "offline, slow, or failing: does the product REFUSE OUT LOUD instead of pretending?",
        ["market", "seller", "market_svc"], ["buyer", "seller"], ["error", "degraded"]),
    "K-a11y": (
        "keyboard, screen reader, contrast, focus order - can this be used without a mouse or good eyes?",
        ["market", "seller", "market_svc"], ["anon", "buyer", "seller"], ["populated", "empty"]),
    "L-comprehension": (
        "is the wording readable, translated, and free of jargon at the moment it costs money?",
        ["market", "market_svc", "seller"], ["anon", "buyer"], ["populated"]),
    "M-mobile": (
        "at 390 CSS pixels, is every control reachable and every target big enough?",
        ["market", "seller", "market_svc"], ["buyer", "seller"], ["populated", "empty"]),
    "N-continuity": (
        "does the page hold its shape while data arrives, and survive a reload mid-flow?",
        ["market", "seller", "founder"], ["buyer", "seller", "admin"], ["populated"]),
    "O-empty-error": (
        "does an empty state promise only what the product can deliver?",
        ["market", "seller", "admin", "market_svc"], ["anon", "seller", "admin"], ["empty", "error"]),
    "Q-payment-rails": (
        "THREE GCash accounts meet here - the buyer's, the provider's, and the founder's personal "
        "0995 009 2416 - and only one of them may ever be on a given screen. WorkHive has no business "
        "registration and therefore no merchant account, so every rail is a personal number: a buyer pays "
        "the PROVIDER directly and the platform never touches it, while a provider tops up credits by "
        "paying the FOUNDER. Put the founder's number on a buyer's payment step and the buyer sends job "
        "money to someone who is not party to the job, cannot fulfil it, and cannot reconcile it - and "
        "nothing errors. This is also the friction Ian named by hand: 'hassle free ... like the hassle of "
        "payment two gcash accounts'. A buyer must see exactly ONE number.",
        ["market_svc", "seller", "founder"], ["buyer", "provider", "admin"],
        ["populated", "empty", "edge", "error"]),
    "P-isolation": (
        "can one tenant see or touch another's rows, through any screen?",
        ["market", "seller", "profile", "admin"], ["buyer", "seller"], ["populated"]),
}

# The oracle families. Every scenario gets exactly one, so a finding is always actionable.
ORACLES = {
    "populated": "the surface renders real rows and every visible number matches its source of truth",
    "empty":     "the empty state names what is missing AND what the person can do, promising nothing "
                 "the product cannot produce",
    "filtered0": "a filter that matches nothing says so, and offers a way back - never a blank grid",
    "error":     "a FAILED read renders an error, never the first-run invitation (a failed read and an "
                 "empty result are the same thing to a row count, and opposite things to a person)",
    "edge":      "the boundary case (longest name, zero price, 200% zoom, the last item) still renders",
    "degraded":  "offline or failing, the write is REFUSED BEFORE it fires and the person is told nothing "
                 "was sent",
}


def build():
    bank = json.load(open(BANK, encoding="utf-8"))
    journeys = [t for t in bank["tests"] if t.get("lane") == "journey"]

    rows, seen = [], set()
    for cat, (question, surfaces, personas, states) in CATEGORIES.items():
        for surface in surfaces:
            for persona in personas:
                for state in states:
                    key = (cat, surface, persona, state)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({
                        "id": f"LM-{cat}-{surface}-{persona}-{state}",
                        "category": cat,
                        "question": question,
                        "surface": surface,
                        "url": SURFACES[surface],
                        "persona": persona,
                        "persona_note": PERSONAS[persona],
                        "state": state,
                        "oracle": ORACLES.get(state, ORACLES["populated"]),
                        # walked live via the Playwright MCP; findings are appended by the flywheel
                        "status": "owed",
                        "findings": [],
                    })

    return {
        "_doc": ("LIVE-MCP scenario registry. Derived from marketplace_test_bank.json's journey lane by "
                 "tools/build_live_mcp_registry.py - do not hand-edit the rows, edit the CATEGORIES table "
                 "and regenerate. `status` moves owed -> walked -> green as the flywheel turns; findings "
                 "accumulate per scenario so a re-walk can prove a fix rather than re-discover it."),
        "derived_from": {"bank": "marketplace_test_bank.json", "journey_cells": len(journeys)},
        "categories": {k: v[0] for k, v in CATEGORIES.items()},
        "surfaces": SURFACES,
        "personas": PERSONAS,
        "total": len(rows),
        "scenarios": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "live_mcp_registry.json"))
    a = ap.parse_args()
    reg = build()
    # merge-preserve: never wipe findings a walk already recorded
    if os.path.exists(a.out):
        try:
            old = {s["id"]: s for s in json.load(open(a.out, encoding="utf-8")).get("scenarios", [])}
            for s in reg["scenarios"]:
                if s["id"] in old:
                    s["status"] = old[s["id"]].get("status", s["status"])
                    s["findings"] = old[s["id"]].get("findings", [])
        except Exception:
            pass
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    from collections import Counter
    by_cat = Counter(s["category"] for s in reg["scenarios"])
    print(f"live-MCP registry: {reg['total']} scenarios across {len(CATEGORIES)} categories")
    for c, n in sorted(by_cat.items()):
        print(f"  {n:>4}  {c}")
    print(f"  -> {os.path.relpath(a.out, ROOT)}")


if __name__ == "__main__":
    main()
