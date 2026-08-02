#!/usr/bin/env python3
"""build_marketplace_sim_scenarios.py — author the marketplace live-simulation scenario registry.

Ian, 2026-08-02: *"we need around diverse 100+ live simulation tests, and from there we could iteratively
improve the entire marketplace."*

WHY A GENERATOR AND NOT A HAND-WRITTEN LIST. 100+ scenarios written by hand drift, duplicate, and quietly
skew toward whatever the author found interesting that day. Composing them from DECLARED DIMENSIONS makes
the coverage auditable: you can see which family, which role-pair, which persona and which defect class
every scenario came from, and you can prove no dimension was skipped. The dimensions below are not invented
here — each is already measured somewhere in this repo:

  · the 12 request states           service_requests' CHECK constraint
  · the 7 journey families          the money test bank's Tier-2 plan (A discovery … G unhappy)
  · the 25 personas                 tools/service_personas.mjs (runtime conditions, not comments)
  · the 8 defect classes            found on the live walks of 2026-08-01/02, every one user-facing
  · the money invariants            MARKETPLACE_CREDIT_SUSTAINABILITY §5 + the M1-M8 board

TWO RULES ENFORCED AT GENERATION TIME, both learned the hard way here:

  1. ROLE-PAIR. A marketplace journey has two sides, and a walk that drives one of them proves nothing about
     what the other sees. `feedback_two_sided_journeys_need_a_role_pair` measured FOURTEEN of 54 journeys as
     provably one-sided. Every scenario below that changes shared state declares BOTH roles, and the
     generator refuses to emit a state-changing scenario with a single role.
  2. EVERY SCENARIO ASSERTS SOMETHING FALSIFIABLE. Not "the page loads" — a specific observable that would
     be FALSE if the defect returned. A scenario with a vague assertion is worse than no scenario, because
     it reports green forever.

Usage:  python tools/build_marketplace_sim_scenarios.py [--write] [--stats]
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "marketplace_sim_scenarios.json"

# ── the surfaces, as they really are ───────────────────────────────────────────────────────────────
BROWSE, SELLER, CONSOLE, PROFILE = "marketplace.html", "marketplace-seller.html", "founder-console.html", "marketplace-seller-profile.html"

# ── the eight defect classes the live walks found. Each becomes a standing regression scenario, and
#    each is a LENS other scenarios are checked through. ────────────────────────────────────────────
DEFECT_CLASSES = [
    ("D1-shared-container", "a shared render target means last-writer-wins; the tab that owns the surface must be the only one to paint it"),
    ("D2-hidden-vs-display", "[hidden] loses to any explicit display, so a 'hidden' element stays on screen"),
    ("D3-opacity-not-inert", "opacity:0 hides from eyes only; the subtree stays in the tab order and the a11y tree"),
    ("D4-view-not-inheriting", "a truth view does not inherit new base columns, so the client reads undefined"),
    ("D5-seed-healthier-than-product", "seeded rows carry data the real form never captures, so a broken filter looks like it works"),
    ("D6-cta-below-fold", "the only path to transact sits below the fold with nothing suggesting it exists"),
    ("D7-stale-refusal-copy", "a threshold moved and its message did not, so the refusal states something false"),
    ("D8-built-never-called", "a loader exists and works when invoked, and nothing calls it on a real page load"),
]

# ── journey families (Tier-2 of the money bank plan) ───────────────────────────────────────────────
FAMILIES = {
    "A-discovery":   ("finding a provider or a listing at all", BROWSE),
    "B-map":         ("the map, presence and the pinned job site", BROWSE),
    "C-hail":        ("instant vs quote, broadcast, TTL, the accept race", BROWSE),
    "D-entrypoints": ("asset-context, alert->hail, PM auto-hail", BROWSE),
    "E-money":       ("release, commission, cashback, top-up, dispute", BROWSE),
    "F-aftermath":   ("review, tier, logbook writeback, showcase", SELLER),
    "G-unhappy":     ("cancel, expire, offline, refusal paths", BROWSE),
}

ROLES = {"client": "a person who needs work done", "provider": "a person who does the work",
         "admin": "the founder adjudicating money and trust", "stranger": "signed out, no identity"}

# The 12 real states, from the CHECK constraint — not a guess.
STATES = ["requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress",
          "completed", "settled", "cancelled_by_client", "cancelled_by_provider", "expired", "disputed"]

PERSONAS = ["P-COLORBLIND", "P-SCREENREADER", "P-LOWVIS", "P-GLOVED", "P-TREMOR", "P-ONEHANDED",
            "P-FILIPINO", "P-LOWLITERACY", "P-SLOWNET", "P-LOWEND", "P-FLAKY", "P-BATTERY",
            "P-FIRSTTIME", "P-SCAMWARY", "P-UNBANKED", "P-OLDER", "P-SUNLIGHT", "P-NIGHT",
            "P-IMPULSIVE", "P-HAGGLER", "P-NOSHOW", "P-DEAF", "P-NOISY", "P-DATACAP", "P-TAGLISH"]


def sc(sid, family, surface, roles, steps, assertion, why, oracle="db-truth", persona=None, state=None,
       mutates=False):
    """One scenario.

    `mutates` is DECLARED, never inferred. The first cut of the validator guessed "state-changing" from
    family + oracle and immediately flagged two read-only checks (does the picker carry data-cert? does the
    tile populate on load?) as needing a role-pair. Inferring a property that the author knows for certain
    produces exactly that kind of false rule — so the author states it.
    """
    return {"id": sid, "family": family, "surface": surface, "roles": roles, "persona": persona,
            "state": state, "steps": steps, "assert": assertion, "oracle": oracle, "why": why,
            "mutates": mutates, "status": "authored"}


def build():
    S = []

    # ── 1. THE EIGHT DEFECT CLASSES, as standing regressions (8) ──────────────────────────────────
    S += [
        sc("MS-D1-tab-owns-surface", "F-aftermath", SELLER, ["provider"],
           ["sign in as a seller with >=1 listing", "land on the Listings tab", "wait for all boot loads"],
           "#content-area shows the seller's LISTINGS, never another tab's empty state",
           DEFECT_CLASSES[0][1], "db-truth"),
        sc("MS-D2-section-switch-hides-grid", "A-discovery", BROWSE, ["client"],
           ["open Services", "read the grid and the services pane"],
           "exactly ONE of #listing-grid / #services-pane is displayed, never both",
           DEFECT_CLASSES[1][1], "db-truth"),
        sc("MS-D3-closed-sheet-is-inert", "F-aftermath", SELLER, ["stranger"],
           ["visit the seller dashboard SIGNED OUT", "focus #edit-title"],
           "focus does NOT land on the hidden edit form; the sheet carries [inert]",
           DEFECT_CLASSES[2][1], "refusal"),
        sc("MS-D4-cert-level-reaches-client", "C-hail", BROWSE, ["client"],
           ["open Services", "read the service picker options"],
           "cert-gated options carry data-cert, sourced from the truth VIEW not the base table",
           DEFECT_CLASSES[3][1], "db-truth"),
        # Both roles, and the validator was right to insist: a pinned hail is only meaningful if the
        # PROVIDER side changes with it — the whole point of the point is which providers it reaches.
        sc("MS-D5-ui-hail-carries-geo", "B-map", BROWSE, ["client", "provider"],
           ["hail via the real form WITH a pin", "read the row back",
            "confirm a NEAR provider is inside the radius and a FAR one is excluded"],
           "service_requests.location is NOT NULL and st_dwithin actually discriminates by distance",
           DEFECT_CLASSES[4][1], "db-truth", mutates=True),
        sc("MS-D6-primary-cta-reachable", "E-money", BROWSE, ["client"],
           ["open any listing detail", "measure the Contact Seller button"],
           "the primary CTA is within the viewport without scrolling (sticky action row)",
           DEFECT_CLASSES[5][1], "rubric"),
        sc("MS-D7-refusal-states-truth", "E-money", SELLER, ["provider"],
           ["be below the deposit floor", "attempt to accept a job"],
           "the refusal names the REAL balance and the REAL floor, never 'negative' when positive",
           DEFECT_CLASSES[6][1], "rubric"),
        sc("MS-D8-tile-populates-on-load", "E-money", CONSOLE, ["admin"],
           ["cold-load the founder console", "wait 7s without touching anything"],
           "the credit-economy tile populates on its OWN, with no manual invocation",
           DEFECT_CLASSES[7][1], "db-truth"),
    ]

    # ── 2. THE LIFECYCLE: every state reached, and reached by the RIGHT role (12 + 12 refusals) ────
    OWNER = {"requested": "client", "broadcasting": "client", "accepted": "provider",
             "en_route": "provider", "on_site": "provider", "in_progress": "provider",
             "completed": "provider", "settled": "client", "cancelled_by_client": "client",
             "cancelled_by_provider": "provider", "expired": "admin", "disputed": "client"}
    for st in STATES:
        owner = OWNER[st]
        other = "provider" if owner == "client" else "client"
        S.append(sc(f"MS-STATE-{st.replace('_','-')}", "C-hail", BROWSE, [owner, other],
                    [f"drive a job to '{st}' as the {owner}", "read it back from both sides"],
                    f"the job reaches '{st}' and BOTH parties' screens agree on it",
                    "a state one side cannot see is a state that did not happen for them",
                    "db-truth", state=st, mutates=True))
        S.append(sc(f"MS-STATE-{st.replace('_','-')}-wrong-role", "G-unhappy", BROWSE, [other, owner],
                    [f"attempt '{st}' as the {other}, who does not own that transition"],
                    f"the transition to '{st}' is REFUSED for the non-owning role",
                    "every state change has exactly one legitimate mover",
                    "refusal", state=st))

    # ── 3. MONEY INVARIANTS, walked rather than queried (10) ──────────────────────────────────────
    money = [
        ("commission-on-paid", "commission bills what was PAID, not the catalogue or the budget"),
        ("cashback-mints-once", "exactly one cashback per settled job, to the CONSUMER"),
        ("double-tap-release", "a double-tapped Release mints exactly one commission"),
        ("release-needs-record", "settling without a payment record is refused"),
        ("second-payment-refused", "the price cannot be restated after commission is billed"),
        ("understatement-needs-reason", "a materially low payment requires a written reason"),
        ("dispute-reverses-both", "an adjustment reverses commission and claws back cashback, deleting nothing"),
        ("deposit-blocks-accept", "a provider below the floor cannot accept, and is told the real numbers"),
        ("cold-start-can-accept", "a provider with NO ledger history may take a first job"),
        ("topup-verify-mints", "a founder-verified GCash top-up mints credits to the right wallet"),
        # The DOOR to all of the above. Added after the money spine shipped with its interface missing:
        # migration 15 made a payment record mandatory, svcSettle kept writing only status='settled', and
        # every press of "Mark as paid" raised the guard's exception into a toast. The data layer was
        # green the whole time. A backend nobody can reach is not a working feature, and only a cell that
        # presses the real button can tell the two apart.
        ("settle-cta-reachable", "a completed job offers a tappable way to confirm payment"),
        ("settle-form-asks-amount", "the form asks what was actually paid, and says the platform holds nothing"),
        ("settle-empty-amount-named", "submitting with no amount names the amount and writes nothing"),
        ("settle-ui-records-and-releases", "one press writes the payment record AND releases the job"),
    ]
    for k, why in money:
        S.append(sc(f"MS-MONEY-{k}", "E-money", BROWSE, ["client", "provider"],
                    ["run the money step live through the UI", "read the ledger back"],
                    why, "money is the one subsystem where a false green costs pesos",
                    "db-truth", mutates=True))

    # ── 4. PERSONA × the surfaces where each is most likely to BREAK (25) ──────────────────────────
    PERSONA_TARGET = {
        "P-COLORBLIND": ("C-hail", "every status is distinguishable without colour"),
        "P-SCREENREADER": ("A-discovery", "a text-equivalent provider list exists behind the map"),
        "P-LOWVIS": ("E-money", "at 200% zoom the money screen reflows and nothing is clipped"),
        "P-GLOVED": ("C-hail", "every primary control clears 44px"),
        "P-TREMOR": ("E-money", "a double tap cannot double-charge"),
        "P-ONEHANDED": ("E-money", "the primary action sits in the bottom third"),
        "P-FILIPINO": ("E-money", "money words carry translation markers and resolve"),
        "P-LOWLITERACY": ("E-money", "the release screen avoids untranslated jargon"),
        "P-SLOWNET": ("B-map", "the hail screen is usable before the map library loads"),
        "P-LOWEND": ("A-discovery", "the grid renders at 360px without horizontal scroll"),
        "P-FLAKY": ("G-unhappy", "a mid-job disconnect refuses the write AND says so"),
        "P-BATTERY": ("B-map", "no affordance depends on animation"),
        "P-FIRSTTIME": ("A-discovery", "nothing assumes a convention they have never met"),
        "P-SCAMWARY": ("E-money", "the release screen says who gets what and that we hold nothing"),
        "P-UNBANKED": ("E-money", "the deposit refusal explains it is spendable, not a fee"),
        "P-OLDER": ("C-hail", "at 150% zoom the hail form is still completable"),
        "P-SUNLIGHT": ("C-hail", "contrast holds at APCA 60 for primary text"),
        "P-NIGHT": ("A-discovery", "dark mode keeps every status legible"),
        "P-IMPULSIVE": ("C-hail", "a double-tapped Hail creates ONE request"),
        "P-HAGGLER": ("C-hail", "the quote path accepts a counter-offer without losing the thread"),
        "P-NOSHOW": ("G-unhappy", "abandoning mid-flow leaves no half-written row"),
        "P-DEAF": ("C-hail", "an arriving hail is signalled visually, never by sound alone"),
        "P-NOISY": ("C-hail", "same as P-DEAF: no audio-only signal"),
        "P-DATACAP": ("B-map", "the map is not fetched unless asked for"),
        "P-TAGLISH": ("A-discovery", "search works with mixed-language terms"),
    }
    for p, (fam, why) in PERSONA_TARGET.items():
        S.append(sc(f"MS-PERSONA-{p[2:].lower()}", fam, FAMILIES[fam][1], ["client"],
                    [f"apply the {p} runtime conditions from service_personas.mjs",
                     "attempt the family's core task end to end"],
                    why, f"{p} is the persona most likely to break {fam}",
                    "task-success", persona=p))

    # ── 5. TRUST & FRAUD, the adversary (10) ──────────────────────────────────────────────────────
    fraud = [
        ("self-deal", "a provider cannot accept their own request"),
        ("tier-self-mint", "51 self-marked sales reach BRONZE, not gold"),
        ("tier-farm-one-buyer", "many sales to one buyer count as ONE counterparty"),
        ("ledger-delete", "no user can DELETE or UPDATE a ledger row"),
        ("ledger-self-mint", "no user can INSERT credits for themselves"),
        ("self-verified-topup", "nobody may verify their own GCash top-up"),
        ("knob-self-service", "a hive cannot lower its own gold bar"),
        ("cashback-farm-cycle", "settle/dispute/settle does not mint cashback twice"),
        ("review-without-purchase", "a review requires a real completed job"),
        ("cross-hive-read", "a hive cannot read another hive's requests or ledger"),
    ]
    for k, why in fraud:
        S.append(sc(f"MS-FRAUD-{k}", "G-unhappy", BROWSE, ["client", "provider"],
                    ["attempt the attack as a real authenticated user, not as the table owner"],
                    why, "an attack is either refused or detected-and-named, never silently absorbed",
                    "refusal"))

    # ── 6. DISCOVERY, LISTING & AFTERMATH (18) ────────────────────────────────────────────────────
    misc = [
        ("A-discovery", "browse-anon-sees-listings", ["stranger"], "an anonymous visitor can browse and is told plainly how to act"),
        ("A-discovery", "browse-section-counts-true", ["client"], "each section tab's count equals the rows it actually renders"),
        ("A-discovery", "search-empty-vs-error", ["client"], "a failed search shows an ERROR, never a first-run empty state"),
        ("A-discovery", "seller-profile-reachable", ["client"], "the seller profile opens from the listing detail"),
        ("A-discovery", "ranking-transparency", ["client"], "the ordering rule is stated where results are ranked"),
        ("F-aftermath", "listing-create-from-dashboard", ["provider"], "a seller can start a listing from the page where they manage listings"),
        ("F-aftermath", "listing-edit-persists", ["provider"], "an edit round-trips and the card reflects it"),
        ("F-aftermath", "listing-sold-needs-buyer", ["provider", "client"], "marking sold requires a linked inquiry for THAT listing"),
        ("F-aftermath", "inquiry-reaches-seller", ["client", "provider"], "a buyer inquiry appears on the seller's Inquiries tab"),
        ("F-aftermath", "review-bidirectional", ["client", "provider"], "both sides can review after completion"),
        ("F-aftermath", "tier-reflects-distinct-buyers", ["provider"], "the tier chip matches distinct confirmed counterparties"),
        ("F-aftermath", "job-writes-back-to-logbook", ["provider"], "a completed job produces a retrievable logbook entry"),
        ("D-entrypoints", "asset-context-hail", ["client"], "hailing from an asset carries the asset context through"),
        ("D-entrypoints", "alert-to-hail", ["client"], "an alert can raise a hail without retyping the problem"),
        ("D-entrypoints", "pm-auto-hail", ["admin"], "a due PM files its own hail without a human pressing anything"),
        ("G-unhappy", "offline-hail-refused", ["client"], "an offline hail is REFUSED and says nothing was sent"),
        ("G-unhappy", "ttl-expiry-visible", ["client"], "an expired hail tells the client why, not just that it ended"),
        ("G-unhappy", "accept-race-loser-told", ["provider", "provider"], "the losing provider is told someone else took it"),
    ]
    for fam, k, roles, why in misc:
        S.append(sc(f"MS-{k.upper()}", fam, FAMILIES[fam][1], roles,
                    ["walk the flow live end to end"], why,
                    "a flow nobody walks is a flow nobody knows works", "db-truth"))


    # ── 7. THE REALTIME MAP, in depth — Ian asked for this leg specifically and it was the thinnest (12)
    #    The map is TRACKING-ONLY by design (lazy-loaded on first Track press, 800KB kept off the listings
    #    critical path) and presence is text. These scenarios hold that design honest rather than assuming
    #    a discovery map that does not exist.
    mapsc = [
        ("map-not-loaded-until-asked", ["client"], False,
         "maplibregl is UNDEFINED on a fresh services view; the 800KB bundle loads only on demand"),
        ("map-pin-sets-location", ["client", "provider"], True,
         "tapping the pin map writes a real SRID=4326 point onto the request"),
        ("map-pin-optional", ["client"], False,
         "a hail sent WITHOUT pinning still succeeds, exactly as before the feature"),
        ("map-degrades-offline", ["client"], False,
         "if the map library cannot load, the typed address still sends and says so"),
        ("map-pin-adjustable", ["client"], False,
         "tapping again MOVES the pin rather than adding a second marker"),
        ("map-track-shows-provider", ["client", "provider"], False,
         "Track plots the provider position for an ACTIVE job and nobody else's"),
        ("map-track-shows-site", ["client", "provider"], False,
         "with a pinned hail the tracking map also shows the client's own site marker"),
        ("map-track-stops-honestly", ["client", "provider"], False,
         "when the job leaves the active window tracking STOPS and says why, not silently"),
        ("map-track-privacy", ["client", "stranger"], False,
         "a non-party cannot read v_service_job_tracking for someone else's job"),
        ("presence-counts-are-real", ["client", "provider"], False,
         "the 'N providers online' line matches providers actually marked online"),
        ("presence-silent-when-empty", ["client"], False,
         "with nobody online the presence line stays silent rather than printing a discouraging zero"),
        ("radius-widens-over-rounds", ["client", "provider"], True,
         "an unanswered hail widens its radius across broadcast rounds, up to the hive cap"),
    ]
    for k, roles, mut, why in mapsc:
        S.append(sc(f"MS-MAP-{k}", "B-map", BROWSE, roles,
                    ["drive the map leg live at a real viewport"], why,
                    "the map is the leg a user trusts most and can verify least", "db-truth",
                    mutates=mut))

    # ── 8. THE ADMIN / FOUNDER SURFACE — money oversight was one scenario (8) ──────────────────────
    adminsc = [
        ("topup-queue-lists-pendings", "the GCash queue lists every pending top-up with payer, ref and filed time"),
        ("topup-verify-mints-once", "verifying mints credits exactly once; a second press changes nothing"),
        ("topup-reject-mints-nothing", "rejecting mints no credits and says so"),
        ("topup-self-verify-refused", "an admin cannot verify a top-up they themselves filed"),
        ("money-tile-four-numbers", "earned, liability, cover and cashback all render real values"),
        ("money-tile-cover-rag", "the RAG dot turns amber/red as liability cover falls below 1.0"),
        ("voucher-budget-refused", "a voucher grant beyond commission earned is refused at write time"),
        ("dispute-adjust-admin-only", "only a platform admin may adjust, and never their own job"),
    ]
    for k, why in adminsc:
        S.append(sc(f"MS-ADMIN-{k}", "E-money", CONSOLE, ["admin", "provider"],
                    ["act as the founder on the real console"], why,
                    "the founder's console is where money is decided; it must not lie", "db-truth",
                    mutates=True))

    return S


def validate(scenarios):
    """The two generation-time rules. A registry that cannot be trusted is worse than none."""
    problems = []
    seen = set()
    for s in scenarios:
        if s["id"] in seen:
            problems.append(f"duplicate id {s['id']}")
        seen.add(s["id"])
        if len(s["assert"]) < 25:
            problems.append(f"{s['id']}: assertion too vague to falsify")
        # ROLE-PAIR: anything that CHANGES shared state needs both sides present, because a walk that
        # drives one side proves nothing about what the other sees (14 of 54 journeys were one-sided).
        if s.get("mutates") and len(s["roles"]) < 2:
            problems.append(f"{s['id']}: changes shared state with a single role — role-pair required")
    return problems


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)

    S = build()
    problems = validate(S)
    if problems:
        print("REFUSING TO EMIT — the registry did not validate:")
        for p in problems[:10]:
            print("  ·", p)
        return 1

    if a.stats or not a.write:
        from collections import Counter
        print(f"scenarios: {len(S)}")
        print("by family :", dict(Counter(s['family'] for s in S)))
        print("by oracle :", dict(Counter(s['oracle'] for s in S)))
        print("by surface:", dict(Counter(s['surface'] for s in S)))
        print("role-pairs:", sum(1 for s in S if len(s['roles']) > 1), "of", len(S))
        print("personas  :", sum(1 for s in S if s['persona']))
        print("states     :", len({s['state'] for s in S if s['state']}), "of 12")

    if a.write:
        OUT.write_text(json.dumps({
            "_doc": "Marketplace live-simulation scenarios. GENERATED by "
                    "tools/build_marketplace_sim_scenarios.py — edit the generator, never this file, so "
                    "coverage stays auditable by dimension rather than by whoever last had an idea.",
            "generated_count": len(S), "scenarios": S}, indent=2), encoding="utf-8")
        print(f"wrote {OUT.name} ({len(S)} scenarios)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
