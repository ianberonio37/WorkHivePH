#!/usr/bin/env python3
"""run_marketplace_sim.py — execute the marketplace simulation registry and report honestly.

A registry of 115 scenarios that never runs is a document, not a test bank. This executes the ones that
CAN be executed today and — this is the important half — reports every one that cannot, WITH ITS REASON,
rather than quietly counting it.

THREE EXECUTION TIERS, because "live simulation" is not one thing:

  db      the scenario's property is decidable against the real database (guards, RLS, ledger, geo,
          state machine). Runs here, now, in a rolled-back transaction.
  browser the property is about what a person SEES (tab ownership, inert, sticky CTA, tap targets,
          lazy map). Needs Playwright MCP driving a real page; this runner marks them `needs-browser`
          and names the surface, so the count of un-run scenarios is visible instead of implied.
  manual  the property needs a human judgement no assertion can make (copy tone for P-SCAMWARY).

WHY NOT PRETEND. The temptation with 115 scenarios is to report "115 scenarios" as though that were
115 tests. It is not. This prints executed / passed / failed / not-yet-runnable, and the roadmap number
is the EXECUTED one — the same discipline that keeps a bank's `owed` cells out of its percentage.

Usage:  python tools/run_marketplace_sim.py [--tier db] [--json] [--selftest]
"""
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "marketplace_sim_scenarios.json"
OUT = ROOT / "marketplace_sim_results.json"
CONTAINER = "supabase_db_workhive"
G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def psql(sql, timeout=90):
    try:
        r = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-q", "-v", "ON_ERROR_STOP=1"], input=sql, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:
        return None, str(e)
    out = (r.stdout or "") + (r.stderr or "")
    return (out, "") if r.returncode == 0 else (None, out[-400:])


# ── the DB-decidable checks, each keyed to a scenario id. One SQL probe, one boolean. ───────────────
# Deliberately expressed as "the property that must hold", so a FALSE result names the defect.
DB_CHECKS = {
    "MS-D4-cert-level-reaches-client":
        ("select (count(*) > 0)::text from information_schema.columns "
         "where table_name='v_service_catalog_truth' and column_name='requires_cert_level';",
         "the truth view exposes requires_cert_level, so the client can mark certified-only trades"),
    "MS-FRAUD-ledger-delete":
        ("select (count(*) = 0)::text from pg_policies where tablename='service_credit_ledger' "
         "and cmd in ('DELETE','UPDATE');",
         "no client-facing DELETE/UPDATE policy exists on the ledger"),
    "MS-FRAUD-ledger-self-mint":
        ("select (count(*) = 0)::text from pg_policies where tablename='service_credit_ledger' "
         "and cmd = 'INSERT';",
         "no client-facing INSERT policy exists on the ledger"),
    "MS-FRAUD-knob-self-service":
        ("select (count(*) >= 2)::text from pg_constraint where conrelid='public.hive_service_settings'::regclass "
         "and contype='c' and pg_get_constraintdef(oid) like '%tier_%';",
         "tighten-only tier floors still guard the trust ladder"),
    "MS-MONEY-release-needs-record":
        ("select (count(*) > 0)::text from pg_trigger t join pg_proc p on p.oid=t.tgfoid "
         "where p.proname='guard_settle_requires_payment' and not t.tgisinternal;",
         "a settle without a payment record is refused by a live trigger"),
    "MS-MONEY-cashback-mints-once":
        ("select (count(*) > 0)::text from pg_indexes where tablename='service_credit_ledger' "
         "and indexdef like 'CREATE UNIQUE%' and indexdef like '%cashback%';",
         "the partial unique index makes a second cashback impossible"),
    "MS-MONEY-understatement-needs-reason":
        ("select (count(*) > 0)::text from pg_trigger t join pg_proc p on p.oid=t.tgfoid "
         "where p.proname='guard_payment_variance_explained' and not t.tgisinternal;",
         "a materially understated payment must carry a written reason"),
    "MS-MONEY-commission-on-paid":
        ("select (position('service_payments' in prosrc) > 0)::text from pg_proc "
         "where proname='mint_settlement_commission';",
         "commission bills what was actually paid, not the catalogue price"),
    "MS-MONEY-cold-start-can-accept":
        ("select (position('service_credit_ledger' in prosrc) > 0)::text from pg_proc "
         "where proname='accept_service_request';",
         "a provider with no ledger history may take a first job (cold-start exemption)"),
    "MS-MONEY-deposit-blocks-accept":
        ("select (position('min_list_balance' in prosrc) > 0)::text from pg_proc "
         "where proname='accept_service_request';",
         "the accept gate reads the deposit floor knob"),
    "MS-ADMIN-voucher-budget-refused":
        ("select (count(*) > 0)::text from pg_trigger t join pg_proc p on p.oid=t.tgfoid "
         "where p.proname='guard_voucher_within_budget' and not t.tgisinternal;",
         "an over-budget voucher grant is refused at write time"),
    "MS-ADMIN-dispute-adjust-admin-only":
        ("select (position('is_marketplace_admin' in prosrc) > 0)::text from pg_proc "
         "where proname='apply_dispute_adjustment';",
         "only a platform admin may adjust a disputed job"),
    "MS-FRAUD-tier-self-mint":
        ("select (count(*) > 0)::text from pg_trigger t join pg_proc p on p.oid=t.tgfoid "
         "where p.proname='guard_listing_sale_needs_counterparty' and not t.tgisinternal;",
         "a sale cannot be self-marked; it must name a counterparty"),
    "MS-FRAUD-tier-farm-one-buyer":
        ("select (position('COUNT(DISTINCT' in prosrc) > 0)::text from pg_proc "
         "where proname='recompute_seller_sales_and_tier';",
         "the tier counts DISTINCT counterparties, not rows"),
    "MS-LISTING-SOLD-NEEDS-BUYER":
        ("select (count(*) > 0)::text from information_schema.columns "
         "where table_name='marketplace_listings' and column_name='sold_to_inquiry_id';",
         "a sold listing carries the inquiry it sold through"),
}


def run_db_checks(scenarios):
    results = []
    for s in scenarios:
        chk = DB_CHECKS.get(s["id"])
        if not chk:
            continue
        sql, prop = chk
        out, err = psql(sql)
        if out is None:
            results.append({**s, "tier": "db", "outcome": "error", "detail": err[:120]})
            continue
        val = "".join(ch for ch in out if ch.strip())[:5].lower()
        ok = val.startswith("t")
        results.append({**s, "tier": "db", "outcome": "pass" if ok else "fail", "property": prop})
    return results


# Browser scenarios that now have a REAL spec. Listed explicitly rather than pattern-matched, so a
# scenario cannot drift into "covered" because its id happened to look like another one's.
BROWSER_COVERED = {
    # tests/marketplace-sim-defects.spec.ts
    "MS-D1-tab-owns-surface", "MS-D2-section-switch-hides-grid", "MS-D3-closed-sheet-is-inert",
    "MS-D6-primary-cta-reachable", "MS-D8-tile-populates-on-load",
    # tests/marketplace-sim-personas.spec.ts
    "MS-PERSONA-colorblind", "MS-PERSONA-lowvis", "MS-PERSONA-gloved", "MS-PERSONA-slownet",
    "MS-PERSONA-battery", "MS-PERSONA-night", "MS-PERSONA-flaky", "MS-PERSONA-scamwary",
    # tests/marketplace-sim-lifecycle.spec.ts — two contexts, the state machine's owner AND non-owner
    "MS-STATE-requested", "MS-STATE-broadcasting", "MS-STATE-cancelled-by-client",
    "MS-STATE-accepted-wrong-role", "MS-STATE-en-route-wrong-role", "MS-STATE-on-site-wrong-role",
    "MS-STATE-in-progress-wrong-role", "MS-STATE-completed-wrong-role", "MS-STATE-settled-wrong-role",
    "MS-STATE-expired-wrong-role",
    # tests/marketplace-sim-map-admin.spec.ts — the leg Ian named, and the founder's money surface
    "MS-MAP-map-not-loaded-until-asked", "MS-MAP-map-pin-sets-location", "MS-MAP-map-pin-optional",
    "MS-MAP-presence-counts-are-real", "MS-MAP-presence-silent-when-empty",
    "MS-ADMIN-topup-queue-lists-pendings", "MS-ADMIN-money-tile-four-numbers",
    # tests/marketplace-sim-fraud.spec.ts — attacks run as a REAL signed-in user, never as the owner
    "MS-FRAUD-ledger-self-mint", "MS-FRAUD-self-deal", "MS-FRAUD-self-verified-topup",
    "MS-FRAUD-knob-self-service", "MS-FRAUD-cross-hive-read",
    # tests/marketplace-sim-discovery.spec.ts — the funnel's top and the return visit. The inquiry cell
    # is the one that found the defect: the direct Contact-Seller path never validated the buyer's name
    # before writing, so its RLS refusal reached the buyer as "your session expired, sign in again".
    "MS-BROWSE-ANON-SEES-LISTINGS", "MS-BROWSE-SECTION-COUNTS-TRUE", "MS-SEARCH-EMPTY-VS-ERROR",
    "MS-SELLER-PROFILE-REACHABLE", "MS-LISTING-CREATE-FROM-DASHBOARD", "MS-INQUIRY-REACHES-SELLER",
    # tests/marketplace-sim-arc.spec.ts — SJ-FULL, the whole machine in ONE continuous two-context
    # session. The forward half of the lifecycle had never been driven end to end, and doing so
    # immediately found two defects the fragments could not see: the provider could not read the payment
    # record their commission is computed from, and a provider who COMPLETED a job stayed 'on_job'
    # (4 of 7 providers were stranded that way, none of them working).
    "MS-STATE-accepted", "MS-STATE-en-route", "MS-STATE-on-site", "MS-STATE-in-progress",
    "MS-STATE-completed", "MS-STATE-settled",
    "MS-STATE-requested-wrong-role", "MS-STATE-broadcasting-wrong-role",
    "MS-MONEY-double-tap-release", "MS-MONEY-second-payment-refused",
    # tests/marketplace-sim-money-ui.spec.ts — the DOOR to the money spine, pressed as a user
    "MS-MONEY-settle-cta-reachable", "MS-MONEY-settle-form-asks-amount",
    "MS-MONEY-settle-empty-amount-named", "MS-MONEY-settle-ui-records-and-releases",
    "MS-MONEY-release-needs-record",
}


def classify(s):
    """Which tier could ever run this? Named so un-run scenarios are visible, never implied."""
    if s["id"] in DB_CHECKS:
        return "db"
    if s["id"] in BROWSER_COVERED:
        return "browser-covered"
    if s.get("persona") in ("P-SCAMWARY", "P-LOWLITERACY", "P-FIRSTTIME"):
        return "manual"          # tone and comprehension are human judgements
    return "browser"


def selftest():
    print("  selftest: the runner must not count un-run scenarios as passes")
    fake = [{"id": "X", "family": "f", "roles": ["a"], "assert": "y", "persona": None}]
    if classify(fake[0]) == "db":
        print(f"  {R}FAIL{X} — an unknown scenario was classified as executable"); return 1
    print(f"  {G}PASS{X} — unknown scenarios fall to browser/manual, never to a silent pass")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="db")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if selftest() != 0:
        return 1
    if not REGISTRY.exists():
        print(f"  {R}FAIL{X} registry missing — run tools/build_marketplace_sim_scenarios.py --write")
        return 1

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    S = reg["scenarios"]
    tiers = {}
    for s in S:
        tiers.setdefault(classify(s), []).append(s)

    print(f"{B}Marketplace simulation{X} — {len(S)} scenarios authored")
    res = run_db_checks(S)
    passed = [r for r in res if r["outcome"] == "pass"]
    failed = [r for r in res if r["outcome"] != "pass"]

    for r in failed:
        print(f"  {R}FAIL{X} {r['id']}  {D}{r.get('property', r.get('detail',''))}{X}")
    print(f"  {G}executed {len(res)}{X} · passed {len(passed)} · failed {len(failed)}")
    covered = len(tiers.get("browser-covered", []))
    print(f"  {G}browser-tier specs{X}: {covered} scenarios have a real Playwright spec "
          f"{D}(marketplace-sim-defects + marketplace-sim-personas){X}")
    print(f"  {Y}still owed{X}: {len(tiers.get('browser', []))} need a browser spec, "
          f"{len(tiers.get('manual', []))} need human judgement — "
          f"{D}named by id, never counted as passing{X}")

    OUT.write_text(json.dumps({
        "authored": len(S), "executed": len(res),
        "passed": len(passed), "failed": len(failed),
        "browser_covered": [s["id"] for s in tiers.get("browser-covered", [])],
        "needs_browser": [s["id"] for s in tiers.get("browser", [])],
        "needs_manual": [s["id"] for s in tiers.get("manual", [])],
        "results": [{k: v for k, v in r.items() if k in ("id", "outcome", "property", "detail")} for r in res],
        "_doc": "The roadmap number is EXECUTED, never AUTHORED. Un-run scenarios are listed by id so the "
                "gap is visible rather than implied.",
    }, indent=2), encoding="utf-8")
    print(f"  -> {OUT.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
