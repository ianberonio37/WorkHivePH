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
    # founder-console.html is RETIRED THE SAME WAY and this table did not say so until 2026-08-03: a
    # #wh-retired-overlay (position:fixed, inset:0, z-index:100000) covers the ENTIRE page and nothing
    # removes it, so a walk here sees one "moved to Grafana" card and nothing else. The markup below it
    # is preserved for the ~35 static validators that scan the file, which is exactly what makes it
    # dangerous: querySelector finds every element, innerText reads every number, and a walk can report
    # confidently on a page no human can use. The credit-minting top-up queue lived here alone until it
    # was lifted to `admin`. Point a scenario at `founder` only to assert the RETIREMENT itself.
    "founder":    "/workhive/founder-console.html",
    # W-surface-breadth: a marketplace journey does not END at the marketplace. Verified present on
    # disk before being named here -- a surface key pointing at a file that does not exist would send
    # a walk to a 404 and let it report a page defect that is really a missing page.
    "community":    "/workhive/community.html",
    "achievements": "/workhive/achievements.html",
    "public_feed":  "/workhive/public-feed.html",
}

PERSONAS = {
    "anon":     "never signed in - the majority of arrivals, and the one most flows forget",
    "buyer":    "signed in, browsing and hiring",
    "seller":   "signed in, listing and answering",
    "provider": "signed in, taking service hails",
    "admin":    "platform moderator",
    # ── S-adversarial. The 500 simulations proved the ECONOMICS hold against these people; nothing has
    # yet proved the SCREEN refuses them legibly, and a guard that blocks in silence is a guard nobody
    # can learn from. Walked as PEOPLE, not as arithmetic.
    "spammer":       "floods listings to occupy the grid - capped at 3 live until one sells, plus a "
                     "2%/month holding fee; the question is whether the cap explains itself",
    "sybil":         "farms starter grants across fresh accounts - only ID verification touches this, so "
                     "the screen must not imply a remedy that does not exist",
    "scam_provider": "takes the job and the direct peso payment, never delivers. The platform holds no "
                     "money and CANNOT claw it back - the completion window is the only lever",
    "scam_buyer":    "receives the work then objects in bad faith to avoid settling",
    "colluder":      "a paired account trading credits with itself to extract value - structurally "
                     "impossible (every leg is a transfer, credits are non-withdrawable), so the oracle "
                     "is EXACTLY 0 extracted, proven not assumed",
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
    # `founder` -> `admin` across the four state-grids below (2026-08-04). The surface table above
    # already said "point a scenario at `founder` only to assert the RETIREMENT itself", but these
    # grids kept generating 30 populated/empty/edge/error scenarios against the retired console --
    # the doctrine was written and the code did not obey it. Walking those rows can only do one of
    # two things, and both are worthless: measure the "moved to Grafana" overlay, or reach THROUGH
    # it by calling handlers directly, which is the exact false-green that kept 5 specs passing
    # while the credit-minting top-up queue sat unreachable for two weeks.
    # The founder's money job now lives on platform-actions.html (top-up queue, receipts, feedback
    # triage and the credit position were all lifted there), so that is where these must be walked.
    # One consequence is deliberate: LM-E-money-founder-admin-populated was GREEN on evidence
    # reading "circulation 0 = issued_credits" -- measured while issued_credits was 0, which was
    # the defect migration 42 corrected to 1,500. It passed by comparing the screen to the view
    # while both read the same broken row: a tautological oracle. It drops out here and returns as
    # an owed row against the live surface, which is the honest state for it.
    "E-money": (
        "at the moment money moves, does every screen agree on the number?",
        ["market_svc", "seller", "admin"], ["buyer", "provider", "admin"], ["populated", "edge"]),
    "F-credits": (
        "does a person understand what credits are, what they hold, and what they will get back?",
        ["market", "seller", "admin"], ["anon", "buyer", "seller", "admin"], ["empty", "populated"]),
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
        ["market", "seller", "admin"], ["buyer", "seller", "admin"], ["populated"]),
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
        ["market_svc", "seller", "admin"], ["buyer", "provider", "admin"],
        ["populated", "empty", "edge", "error"]),
    "P-isolation": (
        "can one tenant see or touch another's rows, through any screen?",
        ["market", "seller", "profile", "admin"], ["buyer", "seller"], ["populated"]),

    # ── §8: the axes the first 17 categories genuinely do not reach ─────────────────────────────────
    # Chosen because they cross a NEW dimension, not because they add rows. Each one names a class of
    # defect the existing pile is structurally blind to.
    "S-adversarial": (
        "when a guard refuses someone, does the SCREEN teach them why - or just go quiet? The 500 "
        "simulations proved the economics hold; none of them looked at a page",
        # `colluder` added 2026-08-04. It was defined in PERSONAS with the sharpest oracle of the set
        # -- "EXACTLY 0 extracted, proven not assumed" -- and then never appeared in this list, so the
        # adversary the entire non-withdrawable design exists to defeat had no scenario at all. Found
        # while trying to bank a colluder walk and discovering the row did not exist. A persona
        # described but never crossed is a hole shaped exactly like the thing nobody thought to test.
        ["seller", "market_svc", "admin"],
        ["spammer", "sybil", "scam_provider", "scam_buyer", "colluder"],
        ["populated", "edge"]),
    "T-two-context": (
        "buyer and provider signed in AT THE SAME TIME, acting on one job. Every walk so far has been "
        "one identity at a time, so races, stale views and 'who sees the state change first' are "
        "invisible by construction",
        ["market_svc", "seller"], ["buyer", "provider"],
        ["populated", "edge", "error", "degraded"]),
    "U-recovery": (
        "the flywheel has walked STEADY states; almost every money defect this session lived in a "
        "TRANSITION - reload mid-flow, Back out of a sheet, a session that expires between typing an "
        "amount and pressing Confirm",
        ["market_svc", "seller"], ["buyer", "provider"],
        ["reload", "back_nav", "session_expiry", "double_submit", "offline_resume"]),
    "V-edge-content": (
        "boundary rendering, where truncation and overflow hide: the longest title, a zero price, 200% "
        "zoom, a 50-listing seller, a name in a non-Latin script",
        ["market", "profile"], ["anon", "buyer"],
        ["longest", "zero_price", "zoom200", "bulk50", "script_name"]),
    "W-surface-breadth": (
        "a marketplace user does not stop at the marketplace. Four categories touch only six surfaces; "
        "these are the pages a real journey reaches next and no walk has ever opened",
        ["community", "achievements", "public_feed", "profile"], ["anon", "buyer"],
        ["populated", "empty", "error"]),
}

# ── Explicitly-enumerated branches ──────────────────────────────────────────────────────────────────
# Not every category is a cross-product. A MONEY LIFECYCLE is a set of named branches, each with its
# own oracle: "the buyer holds less than 10%" is not a state of a surface, it is a specific fork in a
# specific flow, and crossing it against four personas would emit fifteen rows that mean nothing and
# one that matters. So these categories enumerate their rows directly.
#
# Most of these oracles are CROSS-SURFACE on purpose -- the ledger agreeing with the screen -- because
# this arc has already shipped one fix that was correct in the database and invisible to the person
# reading it. A branch is not walked until both halves are checked.
#
# (slug, surface, persona, branch, oracle)
BRANCH_CATEGORIES = {
    "R-money-lifecycle": (
        "does a peso that enters this system arrive where the ledger says it does, on EVERY branch?",
        [
            ("topup-verified", "admin", "admin",
             "provider tops up by GCash, the founder verifies it, credits appear",
             "wallet delta == the top-up amount, exactly one `topup` ledger row, and the provider's card "
             "shows it on a RELOAD rather than only after a hand-called refresh"),
            ("topup-queue-reachable", "admin", "admin",
             "the verify queue is reachable by a real click, not merely present in the DOM",
             "the Verify button is >=44px AND document.elementFromPoint at its centre returns the button "
             "itself (scroll it into view first) -- this queue mints every credit in the economy and lived "
             "on a fully-covered page until 2026-08-03, while five specs passed by calling its handler"),
            ("topup-false-allclear", "admin", "buyer",
             "a non-admin opens the console via the localhost bypass",
             "the page states that the queues read empty because of the session, rather than rendering "
             "'No top-ups waiting' while a real provider's money sits pending"),
            ("topup-rejected", "admin", "admin",
             "the founder rejects a top-up",
             "no credits minted, and it cannot later be flipped to verified"),
            ("spend-chosen", "market_svc", "buyer",
             "the buyer chooses to pay part of a job in credits",
             "buyer -X and provider +X, circulation delta EXACTLY 0, and no reward is also earned on "
             "that job -- earn or spend, never both"),
            ("earn-no-credits", "market_svc", "buyer",
             "the buyer holds no credits and pays the job in full",
             "the buyer's wallet gains exactly 10% of what they PAID, the provider's wallet falls by the "
             "same amount (funded, never minted), and circulation delta is 0. Resolved 2026-08-03 (mig "
             "37): this was briefly logged as an open fork, wrongly — services now reserve at ACCEPTANCE "
             "exactly as a listing reserves at publication, so the funding always exists"),
            ("accept-needs-10pct", "market_svc", "provider",
             "a provider without the 10% tries to take a job",
             "acceptance is REFUSED and the message names both the amount needed and the amount held, so "
             "the provider can act on it — 'no credits, no listing' applies to services too"),
            ("earn-declined", "market_svc", "buyer",
             "the buyer HAS credits and declines to spend them",
             "the spend field was offered and left empty, and the buyer earns the full 10% — declining to "
             "spend is not the same as having nothing to spend"),
            ("spend-partial", "market_svc", "buyer",
             "the buyer holds LESS than 10% of the price",
             "the offered cap is min(balance, 10%) -- a smaller field, never a refusal"),
            ("dispute-returns-credits", "market_svc", "buyer",
             "a job is disputed AFTER the buyer spent credits on it",
             "the spent credits return to the buyer (mig 29), bounded by what the provider still holds"),
            ("dispute-provider-spent", "market_svc", "admin",
             "the provider already spent what they received before the dispute",
             "the buyer is still made whole, the provider floors at 0, and the shortfall is recorded as "
             "absorbed rather than silently dropped"),
            ("supply-cap", "seller", "provider",
             "the 10,000,000 supply cap is reached mid-top-up",
             "the provider is told in a sentence they can act on, not a raw constraint error"),
            ("negative-balance", "seller", "provider",
             "a provider with a negative balance tries to list",
             "the listing is blocked WITH the reason and the amount needed -- never a bare 'Save failed'"),
            ("commission-zero", "market_svc", "buyer",
             "a job settles now that the platform takes no commission",
             "no `commission` ledger row is written AND the founder console shows no 'Earned revenue' "
             "tile -- gone, not sitting at zero"),
            ("cashback-zero", "market_svc", "buyer",
             "cashback is retired",
             "no `cashback` row AND the word 'cashback' appears nowhere user-facing; a buyer meets "
             "exactly ONE reward number"),
            ("ghost-retired", "founder", "admin",
             "the order/escrow/listing-dispute lifecycle is gone",
             "no console renders an order/escrow/listing-dispute queue, no orphaned loader survives, and "
             "MK13 stays at 0 -- assert the RETIREMENT, since this surface is overlay-covered"),
            ("window-buyer-told", "market_svc", "buyer",
             "the provider marks a job done",
             "a push fires to the BUYER, and the row states the deadline AND the consequence -- the date "
             "shown must equal v_service_request_truth.objection_deadline, never a client-side +3 days"),
            ("window-objection", "market_svc", "buyer",
             "the buyer reports a problem inside the window",
             "the job reaches `disputed` not `settled`, the reason is journalled, and a LATER sweep run "
             "leaves it alone -- prove the sweep RAN by settling a control job in the same pass"),
            ("window-autoconfirm", "market_svc", "buyer",
             "the buyer never responds and the window closes",
             "the sweep settles it, the payment row carries auto_confirmed_at with confirmed_by NULL, "
             "and a job with NO agreed price is NOT settled but counted as unpriced. The buyer earns "
             "their 10% exactly as a manual confirm would pay it (mig 37)"),
            ("ufai-touched-surfaces", "market_svc", "buyer",
             "the UFAI lens over every surface this arc touched",
             "contrast, tap targets, focus, SR names, i18n markers and CLS clean on the confirm sheet, "
             "the seller wallet and the admin queues -- mobile rows walked in the SPEC lane, never MCP "
             "(browser_resize(390) renders at 585 here)"),
            ("adversarial-personas", "market_svc", "buyer",
             "the §3b personas walked as people, not arithmetic",
             "the spammer is capped with a reason they can act on, the sybil is refused a second starter "
             "grant, a collusive pair extracts EXACTLY 0, and a scam provider's job cannot pass the "
             "window unnoticed"),
        ]),
}

# ── ADVERSARIAL ORACLES (2026-08-04) ────────────────────────────────────────────────────────────────
# Found while trying to bank S-adversarial rows against the persona probe: the rows did not ask the
# question the category exists to ask. `oracle` is keyed by STATE alone (ORACLES[state]), so all 24
# S-adversarial scenarios inherited "the surface renders real rows and every visible number matches
# its source of truth" -- a RENDERING oracle. The category was created because "the 500 simulations
# proved the ECONOMICS hold; nothing has yet proved the SCREEN refuses them legibly", and that intent
# was written down in PERSONAS right above and then never reached the success criterion.
#
# The tell was concrete: tools/probe_adversarial_personas.py passes all four personas (spam cap holds
# with an actionable sentence, second starter grant refused, circulation delta EXACTLY 0, scam
# provider's job yields a dated deadline plus a working objection) -- and none of that evidence could
# honestly be banked, because it answers containment while the row asked about layout. An oracle that
# does not match the claim makes a green row that proves nothing, which is worse than an owed one.
#
# So an adversarial persona now CONTRIBUTES to the oracle rather than being decoration on it. Both
# halves are kept: the state still governs what the surface must render, and the persona adds what
# the platform must refuse, and how legibly.
ADVERSARIAL_ORACLES = {
    "spammer":       "the 3-live-listing cap HOLDS, and the refusal names both the limit and the way "
                     "out ('sell one, or take one down to make room') - never a bare 'Save failed'",
    "sybil":         "the second starter grant is refused with a reason a person can read, and the "
                     "screen does NOT imply a remedy that does not exist (only ID verification touches "
                     "this, so 'try again later' would be a lie)",
    "scam_provider": "marking a job done does NOT settle it: the buyer gets a DATED deadline and an "
                     "objection control that actually reaches `disputed` - the platform holds no money "
                     "and cannot claw a peso payment back, so detection before settle is the only lever",
    "scam_buyer":    "a bad-faith objection is bounded - it must reach adjudication rather than "
                     "auto-refunding, and the provider must be able to see and answer it",
    "colluder":      "EXACTLY 0 extracted, proven from the ledger rather than assumed: circulation "
                     "delta is 0.00 across the pair, and the refusal explains that credits move only "
                     "on a purchase",
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

    # ── U-recovery: the transitions, where this session's money defects actually lived ──────────────
    "reload":         "reload MID-FLOW and the surface returns to a truthful state - a half-filled sheet "
                      "either survives intact or is gone, never restored into a state the person did not "
                      "leave it in",
    "back_nav":       "browser Back out of a sheet leaves no orphaned overlay and no write half-applied; "
                      "the underlying list reflects what actually happened",
    "session_expiry": "the session dies BETWEEN typing and submitting: the write is refused, the person is "
                      "told their session expired and that NOTHING was sent, and 'try again' is not "
                      "offered when retrying would fail identically",
    "double_submit":  "the second press changes nothing further and SAYS so - the expected human error on "
                      "a queue worked at speed, not an exotic one",
    "offline_resume": "offline the write is refused before it fires; coming back online does not silently "
                      "replay it, and the person can see which of their actions landed",

    # ── V-edge-content: boundary rendering ─────────────────────────────────────────────────────────
    "longest":     "the longest realistic title truncates visibly rather than overflowing its card or "
                   "pushing the price out of view",
    "zero_price":  "a zero or absent price renders as a deliberate state, never as PHP0 masquerading as a "
                   "real figure or a blank where a number belongs",
    "zoom200":     "at 200% browser zoom every control stays reachable and no text is clipped (WCAG 1.4.4)",
    "bulk50":      "a seller with 50 listings paginates or virtualises deterministically - a TOTAL order, "
                   "so no row appears on two pages",
    "script_name": "a name in a non-Latin script (Baybayin, Arabic) renders without mojibake and without "
                   "breaking the row's layout",
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
                        # STRICT, not .get(...) with a fallback: a new state whose oracle nobody wrote
                        # would otherwise inherit "populated" silently, and every scenario in it would
                        # be walked against the wrong success criterion while looking perfectly fine.
                        # An adversarial persona ADDS its containment clause rather than replacing the
                        # state's rendering clause -- both axes stay meaningful, and the row finally
                        # asks the question its category was created to ask.
                        "oracle": (ORACLES[state] + " -- AND, because this is the " + persona +
                                   ": " + ADVERSARIAL_ORACLES[persona]
                                   if persona in ADVERSARIAL_ORACLES else ORACLES[state]),
                        # walked live via the Playwright MCP; findings are appended by the flywheel
                        "status": "owed",
                        "findings": [],
                    })

    # Explicitly-enumerated branches. Same row shape as the crossed ones so the flywheel, the
    # merge-preserve and every consumer treat them identically -- only the way they are AUTHORED differs.
    for cat, (question, branches) in BRANCH_CATEGORIES.items():
        for slug, surface, persona, branch, oracle in branches:
            key = (cat, slug)
            if key in seen:
                raise SystemExit(f"duplicate branch slug in {cat}: {slug}")
            seen.add(key)
            rows.append({
                "id": f"LM-{cat}-{slug}",
                "category": cat,
                "question": question,
                "surface": surface,
                "url": SURFACES[surface],
                "persona": persona,
                "persona_note": PERSONAS[persona],
                "state": "branch",
                "branch": branch,
                "oracle": oracle,
                "status": "owed",
                "findings": [],
            })

    return {
        "_doc": ("LIVE-MCP scenario registry. Derived from marketplace_test_bank.json's journey lane by "
                 "tools/build_live_mcp_registry.py - do not hand-edit the rows, edit the CATEGORIES table "
                 "and regenerate. `status` moves owed -> walked -> green as the flywheel turns; findings "
                 "accumulate per scenario so a re-walk can prove a fix rather than re-discover it."),
        "derived_from": {"bank": "marketplace_test_bank.json", "journey_cells": len(journeys)},
        "categories": {**{k: v[0] for k, v in CATEGORIES.items()},
                       **{k: v[0] for k, v in BRANCH_CATEGORIES.items()}},
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
    # len(CATEGORIES) alone under-reported once BRANCH_CATEGORIES existed - a summary line that
    # disagrees with the rows beneath it is how a wrong number gets quoted into a roadmap.
    print(f"live-MCP registry: {reg['total']} scenarios across "
          f"{len(CATEGORIES) + len(BRANCH_CATEGORIES)} categories")
    for c, n in sorted(by_cat.items()):
        print(f"  {n:>4}  {c}")
    print(f"  -> {os.path.relpath(a.out, ROOT)}")


if __name__ == "__main__":
    main()
