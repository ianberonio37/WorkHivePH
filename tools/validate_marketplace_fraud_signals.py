#!/usr/bin/env python3
"""
validate_marketplace_fraud_signals.py — MK8 marketplace safety: detect the adversarial-USER signals
that no input-validation gate can see.

WHY: every other marketplace gate models adversarial INPUT (XSS, injection, RLS). None models
adversarial BEHAVIOUR. This is a contact-only marketplace with no escrow (Stripe was removed
deliberately), so a buyer's entire risk sits at the off-platform meet-and-pay step, and the platform's
only real lever is to SPOT the patterns early. The PH Internet Transactions Act (RA 11967, harvested
2026-07-24 -> substrate/external/external-ph-internet-transactions-act-ra11967.md) also puts
takedown of prohibited/regulated listings and consumer red-flag education on the platform.

SIX SIGNALS (live DB, read-only). MK8.1-3 model adversarial BEHAVIOUR; MK8.4-6 model the quieter and,
as it turned out, far more common failure: a trust signal the record cannot support. All three of those
were found in one deepwalk, and all three shared a shape worth naming — a badge or number whose
producer either never fired or never existed, left standing by seed data that no user action could have
created. When adding a trust display, ask what maintains it and what happens when nothing does.
  MK8.1 DUPLICATE / SPAM   same seller publishing the same normalized title, or the same part_number,
                           more than once. Listing-spam floods the grid and buries honest sellers.
  MK8.2 PRICE ANOMALY      a published listing priced absurdly far from its category median
                           (>= ANOMALY_FACTOR x). Usually a typo that will waste both sides' time,
                           occasionally bait. Needs >= MIN_PEERS peers before it will judge, so a
                           thin category never produces a false accusation.
  MK8.3 OFF-PLATFORM PUSH  listing copy pressuring payment before inspection ("downpayment first",
                           "send GCash before viewing"). On a no-escrow marketplace this is THE
                           scam-shaped ask, and it contradicts the safety guidance we now show buyers.
  MK8.4 UNBACKED RATING    a seller displaying rating_avg / rating_count with NO verified-purchase
                           review behind it. Added 2026-07-24 after the J15 walk found 13 of 13
                           sellers in exactly this state: the verified-only recompute trigger is
                           correct but only fires on review INSERT, so a seeded or imported score
                           was never revisited. A star rating is the strongest trust claim on the
                           page; unbacked, it is a fabricated one. Backfilled by migration
                           20260724000007; this keeps it at zero.
  MK8.5 TIER MISMATCH      a tier badge that violates the thresholds the platform itself documents
                           (gold >= 51, silver >= 11 in update_seller_tier). The seeded data had gold
                           at 16 sales, silver at 8, and silver at 0. Worse, the ladder's only
                           producer was a trigger on marketplace_orders, which is vestigial since the
                           Stripe removal and will never receive a row, so no seller could ever
                           advance. Given a real producer + backfilled by 20260724000008.
  MK8.6 UNBACKED CERT      cert_verified true with an empty certifications list, i.e. a "Certified"
                           badge covering nothing, with no verification date either. Both moderation
                           surfaces already refuse to verify an empty list, so this could only be
                           seeded; the badge render trusted the flag alone. Cleared by 20260724000009,
                           and all three render sites now require the list too.

FORWARD-ONLY: baseline in marketplace_fraud_signals_baseline.json; a RISE fails. Seeded/clean data
should sit at 0, so this is an integrity-at-zero gate, not a backlog counter.
Self-test: --selftest (proves each detector fires on synthetic bad data).
Skips cleanly (exit 0) when the local DB is unreachable, like the other live gates.
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "marketplace_fraud_signals_baseline.json"
REPORT   = ROOT / "marketplace_fraud_signals_report.json"
CONTAINER = "supabase_db_workhive"

ANOMALY_FACTOR = 20.0   # >= 20x the category median is not a pricing opinion, it is a mistake or bait
MIN_PEERS      = 4      # never judge a price without a real peer group

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# Payment-before-inspection pressure. Deliberately narrow: these are ASKS, not merely the words
# "gcash" or "deposit", which appear in honest listings ("GCash accepted on pickup").
PUSH_PATTERNS = [
    r"\b(down\s*payment|dp)\s*(first|before)",
    r"\bpay\s+(?:me\s+)?(?:first|before)\b",
    r"\bsend\s+(?:the\s+)?(?:money|gcash|payment)\s+(?:first|before)",
    r"\bno\s+(?:viewing|inspection|meet\s*up)\b",
    r"\bdeposit\s+(?:first|before|required\s+before)",
    r"\bship(?:ping)?\s+only\s*,?\s*no\s+meet",
]


def _psql(sql: str):
    """Run read-only SQL, return rows as lists. Returns None when the DB is unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-F", "\x1f", "-c", sql],
            capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return [ln.split("\x1f") for ln in r.stdout.strip().splitlines() if ln.strip()]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


TIER_GOLD_MIN   = 51   # thresholds as documented in update_seller_tier / 20260724000008
TIER_SILVER_MIN = 11


def _expected_tier(sales: int) -> str:
    if sales >= TIER_GOLD_MIN:
        return "gold"
    return "silver" if sales >= TIER_SILVER_MIN else "bronze"


def detect_tier_mismatch(sellers):
    """MK8.5 — a tier badge must satisfy the thresholds the platform itself defines.

    J16 (2026-07-24): the seeded data carried gold at 16 sales, silver at 8, and silver at 0, against
    documented thresholds of 51 and 11. The badge contradicted the only definition of it in the code,
    so a buyer reading "Gold seller" was reading nothing. Backfilled by 20260724000008; this holds it."""
    out = []
    for s in sellers:
        sales = s.get("total_sales") or 0
        want  = _expected_tier(sales)
        have  = (s.get("tier") or "").strip().lower()
        if have and have != want:
            out.append({"seller": s["worker_name"], "tier": have, "total_sales": sales, "expected": want})
    return out


def detect_unbacked_cert_badges(sellers):
    """MK8.6 — a "Certified" badge must cover an actual certifications list.

    J11/J16 (2026-07-24): 3 sellers rendered the violet Certified badge with certifications NULL and
    cert_verified_at NULL, so it asserted an admin verification of nothing. No admin action could
    produce that state (both moderation surfaces require a non-empty list before offering to verify),
    so it was seeded, and the badge render trusted the flag alone. Cleared by 20260724000009."""
    out = []
    for s in sellers:
        if s.get("cert_verified") and not str(s.get("certifications") or "").strip():
            out.append({"seller": s["worker_name"], "certifications": None})
    return out


def detect_unbacked_ratings(sellers):
    """MK8.4 — pure function over seller rows. A displayed score must have verified reviews behind it.

    Deliberately NOT symmetric: verified reviews with no score is the trigger lagging by a moment and
    self-heals on the next INSERT; a score with no reviews is a claim the record cannot support."""
    out = []
    for s in sellers:
        shows_score = s["rating_avg"] is not None or (s["rating_count"] or 0) > 0
        if shows_score and (s["verified_reviews"] or 0) == 0:
            out.append({"seller": s["worker_name"],
                        "rating_avg": s["rating_avg"], "rating_count": s["rating_count"]})
    return out


def detect(rows):
    """Pure function over listing rows -> findings. Unit-testable without a DB."""
    findings = {"duplicate": [], "price_anomaly": [], "offplatform_push": []}

    # MK8.1 duplicates: same seller + same normalized title, or same seller + same part_number
    seen_title, seen_pn = {}, {}
    for r in rows:
        lid, seller, title, pn = r["id"], r["seller_name"] or "", r["title"] or "", (r["part_number"] or "")
        kt = (seller.lower(), _norm(title))
        if kt[1]:
            seen_title.setdefault(kt, []).append(lid)
        if pn.strip():
            kp = (seller.lower(), pn.strip().lower())
            seen_pn.setdefault(kp, []).append(lid)
    for k, ids in list(seen_title.items()) + list(seen_pn.items()):
        if len(ids) > 1:
            findings["duplicate"].append({"seller": k[0], "key": k[1][:40], "count": len(ids)})

    # MK8.2 price anomaly vs category median (only with a real peer group)
    by_cat = {}
    for r in rows:
        if r["price"] is None:
            continue
        by_cat.setdefault(r["category"] or "(none)", []).append((r["id"], float(r["price"])))
    for cat, items in by_cat.items():
        if len(items) < MIN_PEERS:
            continue
        prices = sorted(p for _, p in items)
        mid = len(prices) // 2
        median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
        if median <= 0:
            continue
        for lid, p in items:
            if p >= median * ANOMALY_FACTOR:
                findings["price_anomaly"].append(
                    {"id": lid[:8], "category": cat, "price": p, "median": median})

    # MK8.3 off-platform payment pressure in the copy
    for r in rows:
        blob = f"{r['title'] or ''} {r['description'] or ''}".lower()
        for pat in PUSH_PATTERNS:
            if re.search(pat, blob):
                findings["offplatform_push"].append({"id": r["id"][:8], "pattern": pat})
                break
    return findings


def _fetch_json(sql: str):
    """Fetch rows as JSON.

    NOT delimiter-parsed on purpose: `psql -A -F <sep>` still terminates a record at a NEWLINE, so a
    listing whose description contains a line break silently vanished from the scan (caught 2026-07-24
    when the gate reported 20 of 21 published listings). A long multi-line description is exactly where
    scam copy lives, so that blind spot sat over the highest-risk rows. json_agg has no such ambiguity.
    """
    out = _psql(f"SELECT COALESCE(json_agg(t), '[]'::json) FROM ({sql}) t;")
    if out is None:
        return None
    blob = "".join("".join(parts) for parts in out).strip()
    try:
        return json.loads(blob) if blob else []
    except json.JSONDecodeError:
        return None


def _fetch():
    rows = _fetch_json(
        "SELECT id, COALESCE(seller_name,'') AS seller_name, COALESCE(title,'') AS title, "
        "COALESCE(description,'') AS description, COALESCE(category,'') AS category, "
        "COALESCE(part_number,'') AS part_number, price "
        "FROM marketplace_listings WHERE status='published'")
    if rows is None:
        return None
    for r in rows:
        r["price"] = float(r["price"]) if r.get("price") is not None else None
    return rows


def _fetch_sellers():
    """Seller trust columns joined to their ACTUAL verified-review count."""
    rows = _fetch_json(
        "SELECT s.worker_name, s.rating_avg, COALESCE(s.rating_count,0) AS rating_count, "
        "  s.tier, COALESCE(s.total_sales,0) AS total_sales, "
        "  s.cert_verified, s.certifications, "
        "  (SELECT COUNT(*) FROM marketplace_reviews r "
        "     JOIN marketplace_listings l ON l.id = r.listing_id "
        "    WHERE l.seller_name = s.worker_name AND r.verified_purchase) AS verified_reviews "
        "FROM marketplace_sellers s")
    if rows is None:
        return None
    for r in rows:
        r["rating_avg"] = float(r["rating_avg"]) if r.get("rating_avg") is not None else None
        r["rating_count"] = int(r.get("rating_count") or 0)
        r["verified_reviews"] = int(r.get("verified_reviews") or 0)
        r["total_sales"] = int(r.get("total_sales") or 0)
    return rows


def selftest() -> int:
    """A gate that cannot fire is not a gate: prove each detector on synthetic bad data."""
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    bad = [
        {"id": "a1", "seller_name": "Spammer", "title": "Bearing 6310", "description": "x",
         "category": "Bearings", "part_number": "", "price": 100.0},
        {"id": "a2", "seller_name": "spammer", "title": "BEARING  6310", "description": "x",
         "category": "Bearings", "part_number": "", "price": 100.0},
        {"id": "b1", "seller_name": "S", "title": "Valve", "description": "Send GCash first, no viewing.",
         "category": "Valves", "part_number": "", "price": 100.0},
        {"id": "c1", "seller_name": "S", "title": "Pump", "description": "ok", "category": "Pumps", "part_number": "", "price": 100.0},
        {"id": "c2", "seller_name": "S", "title": "Pump2", "description": "ok", "category": "Pumps", "part_number": "", "price": 100.0},
        {"id": "c3", "seller_name": "S", "title": "Pump3", "description": "ok", "category": "Pumps", "part_number": "", "price": 100.0},
        {"id": "c4", "seller_name": "S", "title": "Pump4", "description": "ok", "category": "Pumps", "part_number": "", "price": 100.0},
        {"id": "c5", "seller_name": "S", "title": "TYPO", "description": "ok", "category": "Pumps", "part_number": "", "price": 999999.0},
    ]
    f = detect(bad)
    chk("duplicate detected (case/spacing-insensitive)", len(f["duplicate"]), 1)
    chk("off-platform push detected", len(f["offplatform_push"]), 1)
    chk("price anomaly detected", len(f["price_anomaly"]), 1)

    clean = [{"id": "x", "seller_name": "Honest", "title": "Bearing", "description": "GCash accepted on pickup.",
              "category": "Bearings", "part_number": "BRG-1", "price": 100.0}]
    fc = detect(clean)
    chk("clean listing yields nothing", sum(len(v) for v in fc.values()), 0)
    thin = [{"id": "t1", "seller_name": "S", "title": "A", "description": "", "category": "Rare", "part_number": "", "price": 1.0},
            {"id": "t2", "seller_name": "S", "title": "B", "description": "", "category": "Rare", "part_number": "", "price": 100000.0}]
    chk("thin category is not judged", len(detect(thin)["price_anomaly"]), 0)

    # MK8.4 — the J15 defect, as data
    chk("unbacked rating detected (score, 0 verified reviews)",
        len(detect_unbacked_ratings([
            {"worker_name": "Ghost", "rating_avg": 3.93, "rating_count": 5, "verified_reviews": 0}])), 1)
    chk("count-only unbacked rating detected",
        len(detect_unbacked_ratings([
            {"worker_name": "Ghost2", "rating_avg": None, "rating_count": 5, "verified_reviews": 0}])), 1)
    chk("earned rating passes",
        len(detect_unbacked_ratings([
            {"worker_name": "Earned", "rating_avg": 4.5, "rating_count": 2, "verified_reviews": 2}])), 0)
    chk("genuinely-new seller passes",
        len(detect_unbacked_ratings([
            {"worker_name": "New", "rating_avg": None, "rating_count": 0, "verified_reviews": 0}])), 0)

    # MK8.5 — the J16 defect, as data (gold at 16, silver at 0, both against 51/11)
    chk("over-claimed gold detected",
        len(detect_tier_mismatch([{"worker_name": "G", "tier": "gold", "total_sales": 16}])), 1)
    chk("silver with zero sales detected",
        len(detect_tier_mismatch([{"worker_name": "S", "tier": "silver", "total_sales": 0}])), 1)
    # MK8.6 — the J11 defect, as data
    chk("cert badge with no certifications detected",
        len(detect_unbacked_cert_badges([{"worker_name": "C1", "cert_verified": True, "certifications": None}])), 1)
    chk("cert badge with blank certifications detected",
        len(detect_unbacked_cert_badges([{"worker_name": "C2", "cert_verified": True, "certifications": "   "}])), 1)
    chk("real certified seller passes",
        len(detect_unbacked_cert_badges([{"worker_name": "C3", "cert_verified": True, "certifications": "PRC ME License"}])), 0)
    chk("unverified seller with certs passes",
        len(detect_unbacked_cert_badges([{"worker_name": "C4", "cert_verified": False, "certifications": "TESDA HVAC NC II"}])), 0)
    chk("correctly-earned tiers pass",
        len(detect_tier_mismatch([{"worker_name": "A", "tier": "bronze", "total_sales": 3},
                                  {"worker_name": "B", "tier": "silver", "total_sales": 11},
                                  {"worker_name": "C", "tier": "gold",   "total_sales": 51}])), 0)
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    rows = _fetch()
    print(f"{BOLD}Marketplace fraud signals (MK8){RESET}")
    if rows is None:
        print(f"  {YELLOW}SKIP{RESET}  local DB unreachable (same policy as the other live gates)")
        return 0

    f = detect(rows)
    sellers = _fetch_sellers() or []
    f["unbacked_rating"] = detect_unbacked_ratings(sellers)
    f["tier_mismatch"]   = detect_tier_mismatch(sellers)
    f["unbacked_cert"]   = detect_unbacked_cert_badges(sellers)
    total = sum(len(v) for v in f.values())
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("total", 0) if BASELINE.exists() else 0

    print(f"  published listings scanned: {len(rows)}   sellers scanned: {len(sellers)}")
    for k, label in [("duplicate", "duplicate / spam listings"),
                     ("price_anomaly", f"price anomalies (>= {ANOMALY_FACTOR:g}x category median)"),
                     ("offplatform_push", "off-platform payment pressure in copy"),
                     ("unbacked_rating", "ratings shown with no verified review behind them"),
                     ("tier_mismatch", f"tier badges violating their own thresholds ({TIER_GOLD_MIN}/{TIER_SILVER_MIN})"),
                     ("unbacked_cert", "Certified badges with no certifications on file")]:
        n = len(f[k])
        mark = GREEN + "OK  " + RESET if n == 0 else RED + "HIT " + RESET
        print(f"  {mark}  {label}: {n}")
        for item in f[k][:3]:
            print(f"          {item}")
    REPORT.write_text(json.dumps({"total": total, "findings": f, "scanned": len(rows)}, indent=2), encoding="utf-8")

    if "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")
        print(f"  {GREEN}ACCEPTED{RESET}  baseline -> {total}")
        return 0
    if total > base:
        print(f"  {RED}FAIL{RESET}  fraud signals rose {base} -> {total}")
        return 1
    print(f"  {GREEN}PASS{RESET}  {total} signal(s), baseline {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
