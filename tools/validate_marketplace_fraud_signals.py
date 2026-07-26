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

THREE SIGNALS (live DB, read-only):
  MK8.1 DUPLICATE / SPAM   same seller publishing the same normalized title, or the same part_number,
                           more than once. Listing-spam floods the grid and buries honest sellers.
  MK8.2 PRICE ANOMALY      a published listing priced absurdly far from its category median
                           (>= ANOMALY_FACTOR x). Usually a typo that will waste both sides' time,
                           occasionally bait. Needs >= MIN_PEERS peers before it will judge, so a
                           thin category never produces a false accusation.
  MK8.3 OFF-PLATFORM PUSH  listing copy pressuring payment before inspection ("downpayment first",
                           "send GCash before viewing"). On a no-escrow marketplace this is THE
                           scam-shaped ask, and it contradicts the safety guidance we now show buyers.

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


def _fetch():
    rows = _psql(
        "SELECT id, COALESCE(seller_name,''), COALESCE(title,''), COALESCE(description,''), "
        "COALESCE(category,''), COALESCE(part_number,''), COALESCE(price::text,'') "
        "FROM marketplace_listings WHERE status='published';")
    if rows is None:
        return None
    out = []
    for c in rows:
        if len(c) < 7:
            continue
        out.append({"id": c[0], "seller_name": c[1], "title": c[2], "description": c[3],
                    "category": c[4], "part_number": c[5],
                    "price": float(c[6]) if c[6] not in ("", None) else None})
    return out


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
    total = sum(len(v) for v in f.values())
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("total", 0) if BASELINE.exists() else 0

    print(f"  published listings scanned: {len(rows)}")
    for k, label in [("duplicate", "duplicate / spam listings"),
                     ("price_anomaly", f"price anomalies (>= {ANOMALY_FACTOR:g}x category median)"),
                     ("offplatform_push", "off-platform payment pressure in copy")]:
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
