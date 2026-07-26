#!/usr/bin/env python3
"""
validate_marketplace_deepwalk_classes.py — LOCK the Marketplace Deepwalk EXPANSION fixes.

The flywheel's ⑥ R-resolve spoke says a fix is not done until a GATE holds it. This is that gate for
the classes closed on 2026-07-24. Every check below encodes a defect that was live-found and fixed;
if any regresses, this FAILs the build instead of waiting for the next deepwalk to rediscover it.

  MK2 · moderation-state honesty
      Every moderation surface that flips a listing to 'removed' must capture moderation_reason.
      There are THREE surfaces over ONE authority (platform-actions is live; marketplace-admin and
      founder-console are retired-but-preserved) — fixing one and missing another is the exact J20
      divergence this arc was built to catch.
  MK7 · public/SEO surface truth
      No listing deep-link may be emitted in the `#listing-<id>` hash form: marketplace.html reads
      ONLY `URLSearchParams.get('listing')` and has no location.hash handling, so the hash form is a
      dead link (it silently dropped buyers onto the generic grid and advertised dead URLs to Google).
  MK3 · contact/disclosure staging
      The anon-facing public seller RPC must NEVER return contact PII or tenant/identity topology.
  MK1 · trust-signal integrity
      A rendered star rating must be guarded by a real review COUNT (no bare, unattributable score).

Static + offline (pure file parsing, no DB/network) so it runs in --fast and never flakes.
Self-test: `python tools/validate_marketplace_deepwalk_classes.py --selftest`
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# Surfaces that moderate listings (one authority, three surfaces — keep in lockstep).
MODERATION_SURFACES = ["platform-actions.html", "founder-console.html", "marketplace-admin.html"]
# Files that may emit a listing deep link.
LINK_EMITTERS = ["marketplace-seller-profile.html", "marketplace.html", "marketplace-seller.html"]
PUBLIC_SELLER_RPC_MIG = "supabase/migrations/20260724000004_marketplace_seller_public_profile.sql"
FORBIDDEN_PUBLIC_COLS = ["messenger_username", "hive_id", "auth_uid"]

# MK1: the client-side rating recompute. ONE constant, used by both the check and its self-test, so
# the self-test exercises the real detector instead of a copy that can drift away from it. (The first
# draft used `\([^)]*rating`, which can never match: the arrow-function's own `(s, r)` closes the class
# before `rating` is reached, so the gate silently passed everything. A gate that cannot fire is not a
# gate — the self-test is what caught it.)
RECOMPUTE_RE = re.compile(r"_reviews\s*\.\s*reduce\s*\(.{0,240}?\brating\b", re.S)


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def check_mk2_moderation_reason(results: list) -> None:
    """Every surface that writes status='removed' must also write moderation_reason."""
    for f in MODERATION_SURFACES:
        src = _read(f)
        if not src:
            results.append((f"MK2 {f}", None, "file absent — skipped"))
            continue
        rejects = "'removed'" in src or '"removed"' in src
        if not rejects:
            results.append((f"MK2 {f}", None, "no listing-reject path — skipped"))
            continue
        ok = "moderation_reason" in src
        results.append((f"MK2 {f} captures a rejection reason", ok,
                        "writes moderation_reason" if ok
                        else "flips a listing to 'removed' WITHOUT moderation_reason -> the seller "
                             "sees a bare 'Removed' chip with no reason and no way to fix it"))


def check_mk7_no_hash_deeplinks(results: list) -> None:
    """`marketplace.html#listing-<id>` is a dead link — the page only reads ?listing=."""
    bad = []
    for f in LINK_EMITTERS:
        src = _read(f)
        for m in re.finditer(r"marketplace\.html#listing-", src):
            line = src[:m.start()].count("\n") + 1
            bad.append(f"{f}:{line}")
    results.append(("MK7 no dead #listing- deep links", not bad,
                    "all listing links use ?listing=" if not bad
                    else "dead hash deep links at " + ", ".join(bad[:5])))


def check_mk3_public_rpc_pii(results: list) -> None:
    """The anon-granted seller RPC must not project contact PII / tenant topology."""
    src = _read(PUBLIC_SELLER_RPC_MIG)
    if not src:
        results.append(("MK3 public seller RPC exists", False,
                        f"missing {PUBLIC_SELLER_RPC_MIG} — the anon-visible profile depends on it"))
        return
    # Only inspect the RETURNS TABLE(...) projection, not the prose comments above it.
    m = re.search(r"RETURNS\s+TABLE\s*\((.*?)\)\s*LANGUAGE", src, re.S | re.I)
    body = m.group(1) if m else src
    leaked = [c for c in FORBIDDEN_PUBLIC_COLS if re.search(rf"\b{c}\b", body)]
    results.append(("MK3 public seller RPC leaks no PII", not leaked,
                    "returns public-safe columns only" if not leaked
                    else "anon-granted RPC projects " + ", ".join(leaked)))
    granted = re.search(r"GRANT\s+EXECUTE.*get_marketplace_seller_public.*\banon\b", src, re.I | re.S)
    results.append(("MK3 public seller RPC is anon-executable", bool(granted),
                    "GRANT EXECUTE ... TO anon present" if granted
                    else "not granted to anon -> the public profile + its JSON-LD stay invisible to crawlers"))


def check_mk1_attributable_rating(results: list) -> None:
    """A star rating must be gated on a real review count, never rendered bare."""
    src = _read("marketplace.html")
    has_guard = "rating_count" in src and "seller review" in src
    results.append(("MK1 detail-sheet rating is attributable", has_guard,
                    "rating renders with its review count / 'New seller' fallback" if has_guard
                    else "rating rendered without a count guard -> an unattributable score"))
    scoped = "No reviews for this listing yet" in src
    results.append(("MK1 listing reviews empty-state is scoped", scoped,
                    "listing-level empty state names its scope" if scoped
                    else "bare 'No reviews yet' beside a seller rating reads as a contradiction"))

    # J15 (2026-07-24): the seller profile used to recompute its headline star rating client-side from
    # the review list it had just fetched — which is UNFILTERED and .limit(20)'d. That gave a seller a
    # second, FORGEABLE path to a score (an unverified review moved the visible stars even though the
    # guarded rating_avg column, verified-only since 20260719000003, refused it) and it disagreed with
    # the aggregateRating we emit in JSON-LD from the canonical column. One source, or it is not a
    # trust signal. The regression shape is literal: averaging _reviews into the rating element.
    prof = _read("marketplace-seller-profile.html")
    recomputes = bool(RECOMPUTE_RE.search(prof))
    results.append(("MK1 profile rating is not client-recomputed", not recomputes,
                    "headline reads the canonical verified-only rating_avg" if not recomputes
                    else "profile averages the fetched review list -> an UNVERIFIED review moves the "
                         "visible stars, bypassing the verified-only trust column"))
    honest_empty = "Not rated" in prof and "No verified purchase has rated" in prof
    results.append(("MK1 unrated seller says so", honest_empty,
                    "renders 'Not rated' + explains why, instead of a bare '-'" if honest_empty
                    else "an unrated seller shows a bare '-' that reads as broken, not as unrated"))


def check_mk4_lifecycle_gone_surface(results: list) -> None:
    """A saved listing that goes sold/removed becomes RLS-unreadable to a normal buyer; the watchlist
    must SAY SO rather than silently render fewer cards."""
    src = _read("marketplace.html")
    ok = "no longer available" in src and ("_goneCount" in src or "ids.length - items.length" in src)
    results.append(("MK4 watchlist surfaces sold/withdrawn saves", ok,
                    "renders the saved-vs-readable difference" if ok
                    else "a saved listing that sells vanishes from the watchlist with no explanation"))


def check_mk8_safety_notice(results: list) -> None:
    """Contact-only marketplace, no escrow: the contact step must carry red-flag guidance (RA 11967)."""
    src = _read("marketplace.html")
    ok = "Before you pay" in src and "never holds your payment" in src
    results.append(("MK8 contact step carries safety guidance", ok,
                    "inspect / meet / avoid full advance payment / no escrow stated" if ok
                    else "the inquiry sheet takes a buyer off-platform with no red-flag guidance"))


def check_mk9_response_stats_computed(results: list) -> None:
    """response_rate/response_time_h must be COMPUTED from real inquiries, never left seed-only."""
    mig = _read("supabase/migrations/20260724000006_marketplace_response_stats_computed.sql")
    has_fn = "update_seller_response_stats" in mig
    has_trg = "trg_update_seller_response_stats" in mig and "marketplace_inquiries" in mig
    results.append(("MK9 response SLA is computed, not seeded", has_fn and has_trg,
                    "trigger recomputes rate + avg hours from marketplace_inquiries" if (has_fn and has_trg)
                    else "the buyer-facing responsiveness promise has no producer -> permanently stale"))


def check_mk10_ranking_disclosure(results: list) -> None:
    """A ranked list must explain itself (EU P2B Art.5 + plain honesty)."""
    src = _read("marketplace.html")
    ok = "newest first" in src and "cannot pay for placement" in src
    results.append(("MK10 grid discloses its ranking", ok,
                    "states the ordering parameter + no paid placement" if ok
                    else "the grid ranks silently, so a buyer cannot tell recency from paid placement"))


def check_mk5_anon_post_discloses_upfront(results: list) -> None:
    """A signed-out visitor must learn that posting needs an account BEFORE filling the form.

    J1/J7 (2026-07-24, walked signed out): #fab-post is visible to anonymous visitors, and
    openPostSheet had no session check, so an anon got the ENTIRE listing form (title, part number,
    category, condition, description, price, location, photo) and only discovered the requirement when
    the RLS-backed insert failed. Harvested rule (substrate/external/
    external-trustworthy-design-credibility-signals-ecommerce.md, nngroup.com/articles/trustworthy-design):
    gated content costs trust, and gating AFTER the effort costs far more than disclosing before it.
    AI assist already guarded on HIVE_ID; posting did not."""
    src = _read("marketplace.html")
    if not src:
        results.append(("MK5 anon post discloses upfront", None, "marketplace.html absent — skipped"))
        return
    m = re.search(r"function openPostSheet\s*\([^)]*\)\s*\{(.*?)\n  \}", src, re.S)
    body = m.group(1) if m else ""
    gated = bool(m) and "HIVE_ID" in body and "_authUid" in body and "return" in body
    results.append(("MK5 anon post discloses upfront", gated,
                    "openPostSheet routes a signed-out visitor to sign-in before the form" if gated
                    else "openPostSheet opens the full listing form with no session check -> an anon "
                         "fills every field and only hits the account wall at submit"))
    audience = "Sign in to list your own parts" in src
    results.append(("MK5 guest stats card is audience-correct", audience,
                    "the MY LISTINGS card addresses a guest instead of asserting they have an account"
                    if audience
                    else "'You have no live listings yet' is shown to visitors who have no account at all"))


def check_identity_reconcile_is_unconditional(results: list) -> None:
    """whWorker() reads a localStorage cache that can belong to a PRIOR user on a shared device, so it
    must be reconciled against the live session on EVERY page.

    J15 (2026-07-24) found that reconcile happening only as a side effect of the community-unread
    badge, which returns early when whHiveId() is empty. On such a page the reconcile never ran and
    whWorker() returned the previous user's name under a different account's JWT (measured: worker
    "Pablo Aguilar" under christinedizon's session). Identity must not be a feature's side effect."""
    src = _read("nav-hub.js")
    if not src:
        results.append(("IDENTITY reconcile runs on every page", None, "nav-hub.js absent — skipped"))
        return
    defined  = "async function reconcileIdentity" in src
    # It must be scheduled from init directly, NOT from inside the hive-gated community routine.
    scheduled = bool(re.search(r"setTimeout\(\s*reconcileIdentity\b", src))
    results.append(("IDENTITY reconcile runs on every page", defined and scheduled,
                    "nav-hub schedules reconcileIdentity unconditionally" if (defined and scheduled)
                    else "identity reconcile is not scheduled on its own -> pages without a hive id "
                         "keep a prior user's cached worker name under the current session"))


def run() -> int:
    results: list = []
    check_identity_reconcile_is_unconditional(results)
    check_mk5_anon_post_discloses_upfront(results)
    check_mk2_moderation_reason(results)
    check_mk7_no_hash_deeplinks(results)
    check_mk3_public_rpc_pii(results)
    check_mk1_attributable_rating(results)
    check_mk4_lifecycle_gone_surface(results)
    check_mk8_safety_notice(results)
    check_mk9_response_stats_computed(results)
    check_mk10_ranking_disclosure(results)

    print(f"{BOLD}Marketplace Deepwalk class locks (MK1/2/3/4/7/8/9/10){RESET}")
    n_pass = n_fail = n_skip = 0
    for label, ok, detail in results:
        if ok is None:
            n_skip += 1
            print(f"  {YELLOW}SKIP{RESET}  {label}: {detail}")
        elif ok:
            n_pass += 1
            print(f"  {GREEN}PASS{RESET}  {label}: {detail}")
        else:
            n_fail += 1
            print(f"  {RED}FAIL{RESET}  {label}: {detail}")
    print(f"Marketplace deepwalk classes: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    return 1 if n_fail else 0


def selftest() -> int:
    """Prove each detector FIRES on a synthetic regression (a gate that cannot fail is not a gate)."""
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN + 'PASS' + RESET if good else RED + 'FAIL' + RESET}  {label}: got {got}, want {want}")

    # MK7 detector fires on the hash form and not on the query form
    src_bad, src_good = 'href="marketplace.html#listing-abc"', 'href="marketplace.html?listing=abc"'
    chk("MK7 flags hash form", bool(re.search(r"marketplace\.html#listing-", src_bad)), True)
    chk("MK7 ignores query form", bool(re.search(r"marketplace\.html#listing-", src_good)), False)
    # MK3 detector fires on a leaked column inside a RETURNS TABLE projection
    leak = "RETURNS TABLE ( worker_name text, messenger_username text ) LANGUAGE sql"
    m = re.search(r"RETURNS\s+TABLE\s*\((.*?)\)\s*LANGUAGE", leak, re.S | re.I)
    chk("MK3 flags messenger_username", bool(re.search(r"\bmessenger_username\b", m.group(1))), True)
    # MK2 detector: a surface with 'removed' but no reason must fail
    chk("MK2 flags reason-less reject", ("moderation_reason" in "update({status:'removed'})"), False)
    # MK1 client-recompute detector: fires on the old shape, silent on the canonical read
    old = "const avg = _reviews.length ? (_reviews.reduce((s, r) => s + Number(r.rating || 0), 0) / n) : 0;"
    new = "const avg = Number(_seller?.rating_avg || 0);"
    chk("MK1 flags client-recomputed rating", bool(RECOMPUTE_RE.search(old)), True)
    chk("MK1 accepts canonical rating read", bool(RECOMPUTE_RE.search(new)), False)
    # ...and must not be fooled by the legitimate _reviews uses that remain on the page
    chk("MK1 ignores the review LIST render",
        bool(RECOMPUTE_RE.search("_reviews.map(rv => renderStars(rv.rating)).join('')")), False)
    chk("MK1 ignores the unverified-count filter",
        bool(RECOMPUTE_RE.search("_reviews.filter(rv => !rv.verified_purchase).length")), False)
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
