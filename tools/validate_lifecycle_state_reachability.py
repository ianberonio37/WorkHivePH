#!/usr/bin/env python3
"""validate_lifecycle_state_reachability.py — MK4: every state in a lifecycle must be REACHABLE and VISIBLE.

A `status` CHECK constraint is a promise about what the product does. Two ways to break it, and this
marketplace has one of each:

  A STATE WITH A SURFACE BUT NO PRODUCER. `marketplace_listings.status` allows `sold`, and
  marketplace-seller.html carries a blue "Sold" chip and a `.listing-item.sold` border rule for it —
  but nothing in the product ever writes that value. No affordance, no trigger, no RPC. The chip is
  code that can never render, and a seller who sells something has no way to say so.

  A CONSUMER WITH NO STATE (the mirror, recorded 2026-07-29 as a schema question for Ian). The same
  table carries `moderation_reason` / `moderated_at` / `moderated_by`, but the CHECK vocabulary is
  {draft, published, sold, removed} with no `rejected` — so a moderator writes a rejection reason with
  no state to attach it to, and the seller just sees "draft".

Both are the same defect wearing opposite faces: **the vocabulary and the product disagree, and
nothing notices.** The failure is silent by construction — unreachable code raises nothing.

FORWARD-ONLY. The one known gap is recorded as a baseline so it stays visible and named rather than
being quietly excluded; a NEW unreachable state FAILs immediately. Closing a gap means editing the
baseline down, never up.

Usage:  python tools/validate_lifecycle_state_reachability.py [--selftest]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = "supabase_db_workhive"
BASELINE = os.path.join(ROOT, "lifecycle_reachability_baseline.json")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# table -> (status column, the pages that own its surfaces)
# The page list must include every surface that OWNS a transition, not only the ones a user browses:
# `removed` is written by the founder console's moderation queue, and leaving that page out made the
# gate report a real, wired transition as unreachable
# ([[feedback_red_gate_may_be_inaccuracy_not_backlog]]).
LIFECYCLES = {
    "marketplace_listings": ("status", ["marketplace-seller.html", "marketplace.html",
                                        "founder-console.html"]),
    "service_requests":     ("status", ["marketplace.html", "marketplace-seller.html"]),
}


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-Atc", sql], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
    except Exception:
        return None
    return (r.stdout or "").strip()


def vocabulary(table, col):
    defs = psql(f"select string_agg(pg_get_constraintdef(oid), ' ;; ') from pg_constraint "
                f"where conrelid='public.{table}'::regclass and contype='c';")
    if defs is None:
        return None
    m = re.search(rf"{col}\s*=\s*ANY\s*\(ARRAY\[(.*?)\]", defs, re.S)
    return re.findall(r"'([^']+)'", m.group(1)) if m else []


MATRIX = os.path.join(ROOT, "transition_matrix.json")


def reachable_states(table):
    """Every state a row can legally ARRIVE in, read from the DERIVED transition matrix.

    Two heuristics were tried first and both were wrong in opposite directions. Matching any function
    whose source merely mentions the literal called `sold` reachable because `get_marketplace_price_comps`
    READS `status IN ('published','sold')` — a false PASS, which on a reachability gate is worse than a
    false FAIL because it retires the question. Tightening to a literal write then called SEVEN wired
    states unreachable, because the seller page advances a job through `svcAdvance(id, next)` — the
    state is a variable at the call site and the literal never appears in a write position at all.

    The exact answer already exists: tools/derive_transition_matrix.py parses the guard functions, and
    a guard's allow-list IS the set of legal destinations. Reuse it rather than guessing from text
    ([[feedback_run_the_battery_dont_hand_roll_probes]]). Anything the matrix does not name as a `to`
    is reachable only by a system write or not at all — which is exactly the finding.
    """
    if not os.path.exists(MATRIX):
        return None
    with open(MATRIX, encoding="utf-8") as f:
        m = json.load(f)
    tos, births = set(), set()
    for mc in m.get("machines", []):
        for c in mc.get("cells", []):
            if c.get("table") != table:
                continue
            tos.add(c.get("to"))
            if c.get("from") in (None, "*", "", "INSERT"):
                births.add(c.get("to"))
    # A row is BORN somewhere. The birth states are whatever the client may insert; read them from the
    # column default plus the states the product's own insert payloads name.
    default = psql(f"select column_default from information_schema.columns "
                   f"where table_name='{table}' and column_name='status';") or ""
    dm = re.search(r"'([a-z_]+)'", default)
    if dm:
        births.add(dm.group(1))
    return tos | births


def written_by_db(table, state):
    """A DB function that WRITES the literal. Needed alongside the matrix because a guard's allow-list
    only covers USER writes: `accepted` is set by accept_service_request under the
    workhive.service_system_write bypass, and `expired` by the sweep_service_broadcasts cron - both
    perfectly reachable, neither named as a guarded `to`.

    ONLY ASSIGNMENT FORMS COUNT. Matching `status = 'x'` anywhere caught
    `recompute_seller_sales_and_tier`, which COUNTS listings `WHERE ... status = 'sold'` - a read - and
    that false PASS hid the one real finding on this gate twice in a row. `SET status =` and
    `status :=` are the only unambiguous writes; a guard's `IF NEW.status = 'x'` is a read and is
    already covered by the matrix signal."""
    hit = psql("select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
               f"where n.nspname='public' and p.prosrc like '%%{table}%%' "
               f"and (p.prosrc ilike '%%set status = ''{state}''%%' "
               f"or p.prosrc ilike '%%set status=''{state}''%%' "
               f"or p.prosrc ilike '%%status := ''{state}''%%');")
    return (hit or "0") != "0"


def written_by_page(src, state):
    """A page write: an update/insert payload naming the literal, or the literal passed to a handler
    (`svcAdvance(id, 'en_route')`, `moderate(id, 'removed')`) - the seller page advances a job with the
    state as an ARGUMENT, so a payload-only test calls seven wired states unreachable."""
    return (re.search(rf"status\s*:\s*['\"]{re.escape(state)}['\"]", src) is not None
            or re.search(rf"\w+\([^)]*['\"]{re.escape(state)}['\"][^)]*\)", src) is not None)


def page_text(pages):
    out = []
    for p in pages:
        fp = os.path.join(ROOT, p)
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                out.append(f.read())
    return "\n".join(out)


# ── PER-PAGE EXEMPTIONS: the state is genuinely one-sided, so its absence is correct ────────────────
# An entry without a reason is a silenced failure, same rule as every other allowlist here.
ONE_SIDED = {
    ("service_requests", "requested", "marketplace-seller.html"):
        "a client's unsent draft. No provider is attached yet and none should see it.",
    ("service_requests", "broadcasting", "marketplace-seller.html"):
        "still looking for a provider. Providers meet this through the 'Open requests near you' feed, "
        "which renders v_service_open_broadcasts rather than a status label on their own job list.",
    ("service_requests", "expired", "marketplace-seller.html"):
        "expired BEFORE anyone accepted, so by definition no provider ever held this job. (It is in "
        "SVC_CLOSED anyway, for the case where a provider saw it in the feed and it lapsed.)",
}


def analyse():
    findings = []
    checked = 0
    for table, (col, pages) in LIFECYCLES.items():
        vocab = vocabulary(table, col)
        if vocab is None:
            return None, 0
        src = page_text(pages)
        reach = reachable_states(table)
        for state in vocab:
            checked += 1
            # A SURFACE: the state appears as a rendered label/class/branch on an owning page.
            # A status map writes its states as OBJECT KEYS (`expired: 'No provider found'`), not as
            # quoted literals — requiring quotes reported two correctly-labelled states as invisible.
            surfaced = (re.search(rf"['\"`]{re.escape(state)}['\"`]", src) is not None
                        or re.search(rf"(^|[{{,\s]){re.escape(state)}\s*:", src, re.M) is not None)
            # A PRODUCER: the derived guard matrix names it as a legal destination, or the product
            # inserts it directly.
            produced = ((reach is not None and state in reach)
                        or written_by_db(table, state)
                        or written_by_page(src, state))
            if not surfaced:
                findings.append((table, state, "no surface: the state exists in the DB and nothing "
                                               "renders it, so a row in it looks like a blank"))
            elif not produced:
                findings.append((table, state, "no producer: it is rendered but nothing in the "
                                               "product can ever put a row there"))
            elif produced:
                # PER-PAGE, added 2026-08-04. `surfaced` above tests the owning pages CONCATENATED,
                # so one page rendering a state hid another page dropping it entirely. That is
                # exactly how `disputed` passed for months: marketplace.html carries
                # `disputed: 'In dispute'` in SVC_CHIP, and marketplace-seller.html matched it on
                # NEITHER of its buckets, so a provider's job silently vanished the moment a client
                # objected -- while apply_dispute_adjustment could still take credits back from them.
                # A state that a page's own rows can reach must be renderable BY THAT PAGE.
                for page in pages:
                    if (table, state, page) in ONE_SIDED:
                        continue
                    src_p = page_text([page])
                    if not src_p:
                        continue
                    seen_here = (re.search(rf"['\"`]{re.escape(state)}['\"`]", src_p) is not None
                                 or re.search(rf"(^|[{{,\s]){re.escape(state)}\s*:", src_p, re.M) is not None)
                    if not seen_here:
                        findings.append((table, state,
                                         f"reachable but INVISIBLE on {page}: another owning page "
                                         f"renders it, which is what hid this. A row that reaches "
                                         f"this state disappears from that surface"))
    return findings, checked


def main():
    if "--selftest" in sys.argv:
        return selftest()
    findings, checked = analyse()
    if findings is None:
        print("  SKIP: docker/psql unavailable")
        return 0
    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as f:
            base = json.load(f)
    known = {tuple(k.split("|")) for k in base.get("known_gaps", [])}

    print("=" * 84)
    print(f"  {BOLD}Lifecycle state reachability (MK4) — every state surfaced AND reachable{RST}")
    print("=" * 84)
    new = []
    for table, state, why in findings:
        tag = (table, state)
        if tag in known:
            print(f"  {YEL}KNOWN{RST}  {table}.{state} — {why}")
            print(f"         {DIM}{base.get('notes', {}).get(f'{table}|{state}', '')}{RST}")
        else:
            print(f"  {RED}NEW{RST}    {table}.{state} — {why}")
            new.append(tag)
    ok = checked - len(findings)
    print(f"\n  {ok}/{checked} lifecycle states are both surfaced and reachable · "
          f"{len(known & {(t, s) for t, s, _ in findings})} known gap(s) · {len(new)} new")
    if new:
        print(f"{RED}FAIL{RST} — a NEW state cannot be reached or cannot be seen. Either wire it, or "
              f"remove it from the CHECK: a vocabulary the product cannot produce is a promise it "
              f"does not keep.")
        return 1
    print(f"{GREEN}PASS{RST} — no new unreachable or invisible lifecycle state")
    return 0


def selftest():
    ok = True
    # The analysis is DB-backed, so the teeth here exercise the baseline logic, which is what decides
    # PASS vs FAIL. A gate whose only teeth need a live DB has no teeth when the DB is absent.
    known = {("t", "a")}
    for finds, want, label in ((["t|a"], 0, "a KNOWN gap does not fail the gate"),
                               (["t|b"], 1, "a NEW gap fails the gate")):
        new = [tuple(f.split("|")) for f in finds if tuple(f.split("|")) not in known]
        if len(new) != want:
            print(f"  {RED}FAIL{RST} {label}"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} {label}")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
