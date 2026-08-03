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
    # ?worker= is REQUIRED, not decoration (marketplace-seller-profile.html:335 reads it and bails
    # with "No seller specified" otherwise). Without it every probe against this surface measured an
    # instruction card instead of the page, and the error/empty walks were judging a screen that had
    # never issued a query. Found 2026-08-04 when the batch walker's error probe on this surface
    # reported "indistinguishable from empty" — both readings were of the same bail-out message.
    "profile":    "/workhive/marketplace-seller-profile.html?worker=Pablo%20Aguilar",
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

    # ── THE 500 (2026-08-04, Ian: "system design and full architecture layers, UFAI, UI, UX") ────────
    # The bank walked PAGES. These walk the STACK. A layer is not a URL, so each one is pinned to the
    # surface where that layer is actually OBSERVABLE from a browser — the walk still happens in a real
    # page, it just asks a question about the layer underneath it. Every file below was verified to
    # exist on disk before being named, because a surface key pointing at a missing page sends a walk
    # to a 404 and lets it report a page defect that is really a typo.
    "layer_client":   "/workhive/marketplace.html",
    "layer_gateway":  "/workhive/marketplace.html",
    "layer_edge":     "/workhive/platform-actions.html",
    "layer_db":       "/workhive/marketplace-seller.html",
    "layer_realtime": "/workhive/platform-actions.html",
    "layer_storage":  "/workhive/marketplace-seller.html",
    "layer_cron":     "/workhive/platform-actions.html",
    "layer_ai":       "/workhive/assistant.html",

    # The SEAMS. Every money defect found this month lived on a join, not inside a layer: a trigger
    # wrote a number the view never exposed; an edge fn returned 200 with an error body; a NULL that
    # meant "no cap" arrived as a zero. So the seams get their own scenarios.
    "seam_client_gateway":   "/workhive/marketplace.html",
    "seam_gateway_edge":     "/workhive/platform-actions.html",
    "seam_edge_db":          "/workhive/platform-actions.html",
    "seam_trigger_view":     "/workhive/marketplace-seller.html",
    "seam_realtime_client":  "/workhive/platform-actions.html",
    "seam_storage_client":   "/workhive/marketplace-seller.html",
    "seam_cron_db":          "/workhive/platform-actions.html",
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

    # ── THE 500. Architecture scenarios have no human persona: the subject is the STACK. Naming that
    # honestly beats pretending a buyer is the one exercising a trigger-to-view seam.
    "system":        "no human - the scenario exercises the stack itself and asserts against psql or "
                     "the network layer, never against another part of the screen",
    "two_context":   "two identities signed in at once on the same object - the races and stale views "
                     "that a single-identity walk cannot see by construction",
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

    # ==============================================================================================
    # THE 500 (2026-08-04) - Ian: "add 500 diverse live mcps in test banks, make it in categories of
    # system design and full architecture layers, UFAI, UI, UX, we will reiteratively improve the
    # entire marketplace."
    #
    # Four families. The existing A-W bank walks PAGES in their states; these walk the STACK, the four
    # UFAI dimensions the platform already grades itself on (U/F/A/I, per CROSS_ARC_UFAI_REVIEW), and
    # the UI/UX split that a page-state grid cannot express.
    #
    # Every state below has its own entry in ORACLES. That is enforced, not conventional: the lookup is
    # strict, so a state nobody wrote an oracle for raises at build time instead of silently inheriting
    # "populated" and being walked against the wrong success criterion forever.
    # ==============================================================================================

    # -- FAMILY 1 - SYSTEM DESIGN / ARCHITECTURE LAYERS --------------------------------------------
    "AX-layer-contract": (
        "does each layer honour its own contract at its own boundary - envelope, status/body "
        "agreement, idempotency, total ordering?",
        ["layer_client", "layer_gateway", "layer_edge", "layer_db", "layer_realtime", "layer_storage",
         "layer_cron", "layer_ai"],
        ["system"],
        ["envelope_shape", "status_body_agreement", "idempotency", "ordering_totality", "units_declared"]),

    "AY-seam": (
        "the joins between layers, where every money defect this month actually lived - does what one "
        "side writes arrive intact, named the same, on the other?",
        ["seam_client_gateway", "seam_gateway_edge", "seam_edge_db", "seam_trigger_view",
         "seam_realtime_client", "seam_storage_client", "seam_cron_db"],
        ["system", "two_context"],
        ["value_survives", "name_survives", "null_semantics", "partial_write"]),

    "AZ-failure-injection": (
        "each layer fails in turn - does the layer ABOVE degrade honestly, or invent a number?",
        ["market", "market_svc", "seller", "admin", "profile", "community"],
        ["system"],
        ["fail_500", "fail_401", "fail_timeout", "fail_partial", "fail_slow", "fail_offline",
         "fail_null_field"]),

    "BA-invariant": (
        "the cross-layer invariants that must hold at every instant, asserted from the ledger and the "
        "catalogue rather than from a screen",
        ["layer_db", "layer_edge", "layer_cron", "layer_realtime"],
        ["system"],
        ["credits_conserved", "reservation_matches_listing", "tenant_isolation_e2e", "no_orphan_ledger",
         "cap_respected", "terminal_states_frozen", "audit_trail_complete", "grant_matches_policy",
         "view_matches_base", "trigger_fires_once"]),

    # -- FAMILY 2 - UFAI, using the dimensions the platform already grades itself on ----------------
    "BB-ufai-U": (
        "UNDERSTANDABLE - one vocabulary per concept, and a claim on screen that matches the view it "
        "names",
        ["market", "market_svc", "seller", "admin", "profile", "community"],
        ["buyer"],
        ["one_vocabulary", "source_chip_true", "units_visible", "no_raw_enum", "number_explained"]),

    "BC-ufai-F": (
        "FUNCTIONAL - the happy-path EFFECT is correct, asserted against psql, never against another "
        "part of the same screen",
        ["market", "market_svc", "seller", "admin", "profile"],
        ["buyer"],
        ["effect_in_db", "effect_visible", "count_matches_source", "money_matches_ledger",
         "idempotent_repeat", "cross_surface_agreement"]),

    "BD-ufai-A": (
        "AVAILABLE / adaptable - fallback, retry, rate limits and degradation; the write refuses BEFORE "
        "it fires and says nothing was sent",
        ["market", "market_svc", "seller", "admin", "profile", "community"],
        ["buyer"],
        ["offline_refusal", "retry_path", "rate_limit_legible", "fallback_engaged", "slow_honest"]),

    "BE-ufai-I": (
        "IDENTITY / isolation - authN from the JWT not the body; a second identity meets a boundary, "
        "never data and never a false all-clear",
        ["market", "admin"],
        ["anon", "buyer", "two_context"],
        ["bola_object", "bfla_function", "tenant_boundary", "jwt_not_body", "boundary_not_emptiness"]),

    # -- FAMILY 3 - UI ------------------------------------------------------------------------------
    "BF-ui-layout": (
        "layout under real content at three VERIFIED widths - the requested viewport is never trusted, "
        "window.innerWidth is",
        ["market", "market_svc", "seller", "admin", "profile", "community", "public_feed"],
        ["buyer"],
        ["w390_overflow", "w641_overflow", "w1280_overflow", "tap_target_44", "safe_area"]),

    "BG-ui-state": (
        "every COMPONENT's six states, not every page's - loading, skeleton, empty, error, populated, "
        "disabled",
        ["market", "market_svc", "seller", "admin", "profile", "community", "public_feed"],
        ["buyer"],
        ["component_loading", "component_skeleton", "component_disabled", "component_busy",
         "component_populated"]),

    "BH-ui-visual": (
        "contrast, focus, motion and naming - the things a screenshot cannot confirm and a measurement "
        "can",
        ["market", "market_svc", "seller", "admin", "profile", "community", "public_feed"],
        ["buyer"],
        ["contrast_wcag", "contrast_apca", "focus_visible", "reduced_motion", "icon_only_name"]),

    # -- FAMILY 4 - UX ------------------------------------------------------------------------------
    "BI-ux-comprehension": (
        "can a person say what this number means, what happens next, and what it costs - the class the "
        "vanished credits chip belongs to",
        ["market", "market_svc", "seller", "admin", "profile", "community", "public_feed"],
        ["buyer"],
        ["what_is_this_number", "what_happens_next", "what_does_it_cost", "why_refused",
         "reward_explained"]),

    "BJ-ux-journey": (
        "multi-step flows end to end per persona, including the two-sided ones a single identity "
        "cannot walk",
        ["market", "market_svc", "seller", "admin"],
        ["buyer", "two_context"],
        ["first_run_to_value", "repeat_visit", "cross_surface_handoff", "two_sided_same_object",
         "abandon_resume"]),

    "BK-ux-recovery": (
        "mistakes, reversals and interruption - and the question every person asks after a slow tap: "
        "did my thing land?",
        ["market", "market_svc", "seller", "admin", "profile", "community", "public_feed"],
        ["buyer"],
        ["double_tap", "back_out", "session_died", "wrong_then_fix", "did_it_land"]),
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
    # ══ THE 500 (2026-08-04). Every oracle below names an OBSERVABLE, and deliberately names one that a
    # structural probe cannot fake. That is the whole lesson of the false 343: "the page rendered" is a
    # real property and it is not "the number is right", and the credits-back chip lived in the gap
    # between them for as long as nobody wrote the difference down. ══════════════════════════════════

    # ── FAMILY 1 · architecture ────────────────────────────────────────────────────────────────────
    "envelope_shape":        "the layer returns its declared envelope on BOTH paths - success and failure "
                             "- and a caller can tell which without parsing prose",
    "status_body_agreement": "the HTTP status and the body agree: no 200 carrying an error, no 4xx "
                             "carrying data. Disagreement is measured on the wire, not inferred",
    "idempotency":           "the same call twice produces ONE effect; the second is refused or absorbed, "
                             "and the count in the DB proves which",
    "ordering_totality":     "a paginated or sorted read has a TOTAL order - re-running it does not "
                             "reshuffle equal keys, so page 2 cannot repeat or skip a row from page 1",
    "units_declared":        "the value carries its unit at the boundary (pesos vs credits vs percent vs "
                             "whole-percent) - the class that made a knob of 10 mean 1000%",

    "value_survives":        "what one side of the seam WRITES is what the other side READS - compared "
                             "value-to-value against psql, never screen-to-screen",
    "name_survives":         "the field keeps its name and meaning across the seam; a rename on one side "
                             "that the other still reads by the old name is a silent null",
    "null_semantics":        "NULL means the SAME thing on both sides. The reward cap proved the cost: "
                             "NULL meant 'no cap' in the DB and arrived as a cap of ZERO in the client",
    "partial_write":         "a multi-row or multi-table write either lands whole or not at all; a "
                             "half-applied write is visible as an inconsistency in the ledger",

    "fail_500":              "the layer above renders a failure, never an emptiness, and offers a way back",
    "fail_401":              "an expired session says so AND says nothing was sent - never a bare retry, "
                             "and never a sign-in instruction to someone already signed in",
    "fail_timeout":          "a hung dependency ends in a stated timeout, not an indefinite skeleton",
    "fail_partial":          "when half the reads succeed, what loaded is kept and what did not is NAMED - "
                             "no silent blanks beside real data",
    "fail_slow":             "a slow response keeps the surface honest: a busy state that resolves, never a "
                             "control that looks ready while nothing is behind it",
    "fail_offline":          "the write is refused BEFORE it fires, the person is told nothing was sent, "
                             "and reconnecting does not silently replay it",
    "fail_null_field":       "a NULL field in an otherwise valid row renders as a stated gap, never as 0, "
                             "'undefined', or a fabricated default",

    "credits_conserved":     "sum of the ledger equals issued_credits, and no path creates value - proven "
                             "from the ledger, not from a tile",
    "reservation_matches_listing": "every published listing has exactly one live reservation and vice "
                             "versa - an orphan on either side is a defect",
    "tenant_isolation_e2e":  "a second tenant sees zero rows end to end - through the view, the RPC and "
                             "the realtime channel, not merely through the base table",
    "no_orphan_ledger":      "no ledger entry lacks its counterpart leg; a one-sided write is caught",
    "cap_respected":         "issued can never exceed authorised; the guard is proven by attempting to "
                             "exceed it in a rolled-back transaction",
    "terminal_states_frozen":"a decided record cannot be re-opened and re-decided - proven by attempting "
                             "the transition and reading the refusal",
    "audit_trail_complete":  "every money-moving action leaves an audit row naming who did it",
    "grant_matches_policy":  "the table grant and the RLS policy agree - a grant with no caller-aware "
                             "policy is public data whether or not anyone decided that",
    "view_matches_base":     "the view returns what the base table would, under the SAME identity - a "
                             "security_invoker mismatch is the tell",
    "trigger_fires_once":    "the trigger fires exactly once per qualifying change - not zero, not twice",

    # ── FAMILY 2 · UFAI ────────────────────────────────────────────────────────────────────────────
    "one_vocabulary":        "one concept, one word, across every surface that shows it - 'credits' is not "
                             "'points' three screens later",
    "source_chip_true":      "the source chip names the view the number actually came from, and that view "
                             "returns that number right now",
    "units_visible":         "the unit is on screen beside the number, not implied by position",
    "no_raw_enum":           "no lowercase_with_underscores status reaches a person",
    "number_explained":      "a person can say what the number MEANS without leaving the surface",

    "effect_in_db":          "the happy path's effect is present in the database, asserted by psql",
    "effect_visible":        "that same effect is visible to the person who caused it, on the surface "
                             "where they caused it",
    "count_matches_source":  "every count on screen equals the count its own predicate returns - measured "
                             "with the page's OWN filter, not a guess at it",
    "money_matches_ledger":  "every peso and credit figure equals the canonical view, to the centavo",
    "idempotent_repeat":     "repeating the action changes nothing further and the surface says so",
    "cross_surface_agreement":"the same fact reads the same on every surface that shows it",

    "offline_refusal":       "offline, the write is refused before firing and the person is told nothing "
                             "was sent",
    "retry_path":            "a failure offers a retry that actually re-attempts, and succeeds when the "
                             "cause is gone",
    "rate_limit_legible":    "a rate limit states what was limited and when it clears - never a bare error",
    "fallback_engaged":      "when the primary is down the fallback engages and the surface says which it "
                             "used, rather than pretending nothing happened",
    "slow_honest":           "under a slow dependency the surface stays honest: busy where busy, no "
                             "control that implies readiness it does not have",

    "bola_object":           "another person's object id is refused, and the refusal is legible",
    "bfla_function":         "a function above this role is refused at the server, not merely hidden in "
                             "the UI",
    "tenant_boundary":       "a foreign hive's row is invisible, and its absence is stated as a boundary "
                             "rather than shown as an emptiness",
    "jwt_not_body":          "identity comes from the JWT; a forged identity in the body changes nothing",
    "boundary_not_emptiness":"a permission boundary reads as 'not visible with this session', never as "
                             "'nothing here' - the difference between 'you may not look' and 'all clear'",

    # ── FAMILY 3 · UI ──────────────────────────────────────────────────────────────────────────────
    "w390_overflow":         "at a VERIFIED innerWidth of ~390 nothing overflows its container and the "
                             "document does not scroll sideways",
    "w641_overflow":         "at a VERIFIED innerWidth of ~641 (the 200%-zoom equivalent) the same holds",
    "w1280_overflow":        "at 1280 the same holds, with real content rather than seed-perfect content",
    "tap_target_44":         "every interactive control is at least 44x44 CSS px at the narrow width, "
                             "measured by rect and not by stylesheet intent",
    "safe_area":             "fixed bottom chrome clears the home indicator via env(safe-area-inset-bottom)",

    "component_loading":     "the component's loading state is distinguishable from its empty state",
    "component_skeleton":    "the skeleton reserves the space the content will take, so nothing jumps",
    "component_disabled":    "a disabled control looks disabled AND refuses activation - both, not either",
    "component_busy":        "an in-flight control is busy and cannot be re-fired",
    "component_populated":   "populated renders every field it promises, with no undefined/NaN",

    "contrast_wcag":         "text meets WCAG AA 4.5:1 against its ACTUAL composited background, alpha "
                             "included - the trap that made every tinted pill read 1.00",
    "contrast_apca":         "the same text passes the APCA perceptual threshold for its size and weight",
    "focus_visible":         "keyboard focus is visible on every interactive element, including custom ones",
    "reduced_motion":        "prefers-reduced-motion is honoured - no animation that ignores it",
    "icon_only_name":        "an icon-only control has an accessible name that says what it DOES",

    # ── FAMILY 4 · UX ──────────────────────────────────────────────────────────────────────────────
    "what_is_this_number":   "a person can state what the number means from the surface alone",
    "what_happens_next":     "after an action, the surface says what happens next and when",
    "what_does_it_cost":     "cost, hold and reward are stated before commitment, not after",
    "why_refused":           "a refusal names the rule AND the way out - never a remedy that cannot work",
    "reward_explained":      "the 10% reward is discoverable and correct for THIS item - the class the "
                             "vanished credits chip belongs to",

    "first_run_to_value":    "a first-time person reaches the first useful outcome without a dead end",
    "repeat_visit":          "a returning person resumes where it matters, without redoing setup",
    "cross_surface_handoff": "a flow that spans surfaces carries its context across the handoff",
    "two_sided_same_object": "two identities acting on the SAME object each see a truthful view of it - "
                             "the half a single-identity walk cannot see",
    "abandon_resume":        "abandoning midway and returning leaves no half-applied state",

    "double_tap":            "the second press changes nothing further and the surface says so",
    "back_out":              "browser Back leaves no orphaned overlay, no scroll lock, and no half-write",
    "session_died":          "a session that dies between typing and submitting refuses the write and says "
                             "nothing was sent, preserving what was typed",
    "wrong_then_fix":        "a wrong entry can be corrected without starting over",
    "did_it_land":           "after a slow action the person can tell whether it landed, without guessing",

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
                    # EVIDENCE MUST SURVIVE A REGENERATION. It is the thing that makes a green row
                    # green (validate_live_mcp_bank R1), so dropping it here would turn every earned
                    # walk into an INVALID row the moment anyone rebuilt the bank — a rebuild that
                    # silently destroys the proof is worse than one that destroys the status.
                    if old[s["id"]].get("evidence") is not None:
                        s["evidence"] = old[s["id"]]["evidence"]
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
