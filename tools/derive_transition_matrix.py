#!/usr/bin/env python3
"""derive_transition_matrix.py - the marketplace test bank's DENOMINATOR, derived from the database.

WHY DERIVE INSTEAD OF ENUMERATE. A hand-written list of "the journeys we should test" is an opinion,
and it silently stops being true the day someone adds a transition. The marketplace's state machines
already exist as guard functions, and each guarded transition NAMES ITS AUTHORISED ACTOR - so the set
of things a test bank owes can be computed. When a migration adds a transition, the denominator grows
by itself and the bank reports an untested cell instead of a false 100
([[feedback_short_denominator_is_a_false_100]]).

This is all-transitions coverage in the model-based-testing sense: the guards ARE the automaton, and
the bank is the abstract test suite derived from it.

THE GUARDS COME IN TWO SHAPES, and conflating them would fabricate coverage:

  ALLOW-LIST  (`guard_service_request_status`)
      or (v_is_client and old.status = 'requested' and new.status = 'broadcasting')
    Every permitted (actor, from, to) triple is spelled out. Anything not listed is refused.
    -> a cell per triple, plus a refusal cell for every OTHER actor.

  DENY-RULE   (listing / order / topup guards)
      IF NEW.status = 'published' AND <caller is not admin> THEN raise
    Only the DANGEROUS target states are named; everything else is permitted by omission.
    -> a cell for the authorised actor, plus a refusal cell for the blocked ones. It does NOT
       license claiming coverage of the unnamed transitions - those are reported separately as
       UNGOVERNED, which is a finding, not a pass.

Output: `transition_matrix.json` + a human-auditable table. The parser PRINTS the source line behind
every cell it derives, because an instrument that cannot be eyeballed gets trusted when it is wrong
([[feedback_verify_the_instrument_before_the_page]]).

Usage:  python tools/derive_transition_matrix.py [--json] [--selftest]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "transition_matrix.json")
DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# (table, guard function, shape). Shape decides how the source is read - never guessed.
MACHINES = [
    ("service_requests",      "guard_service_request_status",     "allow"),
    ("marketplace_listings",  "guard_marketplace_listing_status", "deny"),
    ("marketplace_orders",    "guard_marketplace_order_status",   "deny"),
    ("service_credit_topups", "guard_service_topup_status",       "deny"),
]

# Actor tokens as the guards spell them -> the bank's authority partition.
ACTOR_MAP = {
    "v_is_client":           "owner",         # the request's client
    "v_is_matched_provider": "counterparty",  # the accepted provider
    "v_is_admin":            "admin",
    "v_is_founder":          "admin",
    "is_admin":              "admin",
}

# The temporal negatives every guarded transition owes. Each has already bitten this platform, which
# is why they are obligations and not ideas: replay -> the partial unique indexes exist because of it;
# concurrency -> the first-accept race was proven live; session-switch -> the identity-cache root.
SNEAK_PATHS = ["replay", "concurrency", "out-of-order", "session-switch"]


def psql(sql: str, timeout: int = 60):
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return (r.stdout or "").strip() if r.returncode == 0 else None


def vocabulary(table: str):
    """The declared status domain, from the CHECK constraint - the state space of the automaton."""
    out = psql(
        "select pg_get_constraintdef(k.oid) from pg_constraint k join pg_class c on c.oid=k.conrelid "
        f"where c.relname='{table}' and k.contype='c' and pg_get_constraintdef(k.oid) ilike '%status%'")
    if not out:
        return []
    return re.findall(r"'([a-z_]+)'::text", out)


def guard_src(fn: str):
    return psql(f"select prosrc from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
                f"where n.nspname='public' and p.proname='{fn}'") or ""


# A permission clause may WRAP across lines - the cancel rules do exactly that:
#     or (v_is_client and old.status in ('requested','broadcasting','accepted','en_route','on_site')
#                     and new.status = 'cancelled_by_client')
# A line-by-line reader silently loses those and then reports the target as "ungoverned", which is
# worse than missing it: it invents an architectural finding. So the source is FLATTENED first and
# matched as one clause. Caught by reading the tool's own evidence output against the guard.
TO_ANCHOR = re.compile(r"new\.status\s*=\s*'([a-z_]+)'", re.I)


def parse_allow(src: str):
    """(actor, from, to, evidence) for every permitted triple.

    Anchored on each `new.status = 'X'`, then reading BACKWARD over that clause. Two shapes in the
    real guard, both of which a naive reader gets wrong:

      wrapped     the clause spans lines -> flatten before matching, or the transition is lost and
                  its target is then falsely reported "ungoverned" (a phantom architectural finding).
      multi-actor `((v_is_client or v_is_matched_provider) and old.status in (…) and new.status='disputed')`
                  -> BOTH parties may dispute. Capturing only the first actor token made the bank
                  demand that the provider be REFUSED, and the bank's own run failed on live
                  behaviour that was correct. Every actor in the clause gets a cell.
    """
    flat = re.sub(r"\s+", " ", src)
    found = []
    anchors = list(TO_ANCHOR.finditer(flat))
    for i, m in enumerate(anchors):
        to = m.group(1)
        start = anchors[i - 1].end() if i else max(0, m.start() - 400)
        clause = flat[start:m.start()]
        # a `raise`/`if` boundary means this anchor is not a permission clause
        if re.search(r"raise\s+exception", clause, re.I):
            clause = clause[re.search(r"raise\s+exception", clause, re.I).end():]
        actors = [ACTOR_MAP[t.lower()] for t in re.findall(r"v_is_[a-z_]+", clause, re.I)
                  if t.lower() in ACTOR_MAP]
        froms = re.findall(r"old\.status\s*=\s*'([a-z_]+)'", clause, re.I)
        m_in = re.search(r"old\.status\s+in\s*\(([^)]*)\)", clause, re.I)
        if m_in:
            froms += re.findall(r"'([a-z_]+)'", m_in.group(1))
        if not actors or not froms:
            continue
        ev = (clause[-90:] + " new.status='" + to + "'").strip()
        for actor in dict.fromkeys(actors):          # dedupe, keep order
            for fr in dict.fromkeys(froms):
                found.append((actor, fr, to, ev))
    return found


def parse_deny(src: str):
    """(blocked_target, required_authority, evidence) for each dangerous state the guard defends."""
    found = []
    for raw in src.split("\n"):
        line = raw.strip()
        if not re.search(r"new\.status", line, re.I):
            continue
        if not re.search(r"=\s*'|in\s*\(", line, re.I):
            continue
        targets = re.findall(r"new\.status\s*=\s*'([a-z_]+)'", line, re.I)
        m_in = re.search(r"new\.status\s+in\s*\(([^)]*)\)", line, re.I)
        if m_in:
            targets += re.findall(r"'([a-z_]+)'", m_in.group(1))
        if not targets:
            continue
        # who is allowed through: the guard names admin/founder, else it is a system/service-role path
        auth = "admin" if re.search(r"admin|founder|moderat", line, re.I) else "admin-or-system"
        for t in targets:
            found.append((t, auth, line[:110]))
    return found


def build():
    machines = []
    for table, fn, shape in MACHINES:
        src = guard_src(fn)
        vocab = vocabulary(table)
        if not src:
            machines.append({"table": table, "guard": fn, "shape": shape,
                             "error": "guard not found in this database", "vocabulary": vocab})
            continue

        cells, governed_pairs = [], set()

        if shape == "allow":
            triples = parse_allow(src)
            # A transition may be permitted to MORE THAN ONE party - the dispute rule reads
            # `(v_is_client or v_is_matched_provider)`. Negatives must therefore exclude EVERY
            # authorised actor for that (from,to), not just this cell's own. Deriving negatives
            # per-cell instead made the bank demand a refusal from a party the guard permits, and the
            # live run failed on correct behaviour - the bank accusing the product.
            authorised = {}
            for actor, fr, to, _ in triples:
                authorised.setdefault((fr, to), set()).add(actor)
            for actor, fr, to, ev in triples:
                governed_pairs.add((fr, to))
                others = [a for a in ("anon", "member", "owner", "counterparty", "admin", "cross-tenant")
                          if a not in authorised[(fr, to)]]
                cells.append({
                    "id": f"TB-{table}-{fr}__{to}-{actor}",
                    "table": table, "from": fr, "to": to,
                    "authority": actor, "expect": "allowed",
                    "negatives": [{"authority": a, "expect": "refused"} for a in others],
                    "sneak_paths": SNEAK_PATHS,
                    "evidence": ev, "shape": "allow",
                })
        else:
            for to, auth, ev in parse_deny(src):
                governed_pairs.add(("*", to))
                cells.append({
                    "id": f"TB-{table}-any__{to}-{auth}",
                    "table": table, "from": "*", "to": to,
                    "authority": auth, "expect": "allowed",
                    "negatives": [{"authority": a, "expect": "refused"}
                                  for a in ("member", "owner", "counterparty", "cross-tenant")],
                    "sneak_paths": SNEAK_PATHS,
                    "evidence": ev, "shape": "deny",
                })

        # Everything the vocabulary permits that no guard clause mentions. NOT auto-defects: most are
        # nonsensical (settled -> requested). Reported so a human dispositions them, because an
        # UNGOVERNED reachable transition is exactly the class that produced the self-publish bypass.
        governed_targets = {t for _, t in governed_pairs}
        ungoverned = sorted(s for s in vocab if s not in governed_targets)

        machines.append({
            "table": table, "guard": fn, "shape": shape,
            "vocabulary": vocab,
            "state_space": len(vocab) * (len(vocab) - 1) if vocab else 0,
            "cells": cells,
            "ungoverned_targets": ungoverned,
        })
    return {"_doc": "Derived denominator for the marketplace test bank. DO NOT hand-edit - "
                    "re-run tools/derive_transition_matrix.py.",
            "machines": machines}


def report(m):
    total_pos = total_neg = total_sneak = 0
    print("=" * 84)
    print(f"  {BOLD}Marketplace test bank - DERIVED transition matrix{RST}")
    print("=" * 84)
    for mc in m["machines"]:
        if mc.get("error"):
            print(f"\n  {RED}{mc['table']}{RST}: {mc['error']}")
            continue
        cells = mc["cells"]
        pos = len(cells)
        neg = sum(len(c["negatives"]) for c in cells)
        sneak = sum(len(c["sneak_paths"]) for c in cells)
        total_pos += pos; total_neg += neg; total_sneak += sneak
        print(f"\n  {BOLD}{mc['table']}{RST}  ({mc['guard']}, {mc['shape']}-shape)")
        print(f"    vocabulary  : {len(mc['vocabulary'])} states -> {mc['state_space']} ordered transitions possible")
        print(f"    governed    : {pos} positive · {neg} authority-negative · {sneak} sneak-path")
        for c in cells[:6]:
            print(f"      {DIM}{c['from']:>14} -> {c['to']:<22} by {c['authority']:<14}{RST}")
            print(f"        {DIM}src: {c['evidence'][:88]}{RST}")
        if len(cells) > 6:
            print(f"      {DIM}… +{len(cells) - 6} more{RST}")
        if mc["ungoverned_targets"]:
            print(f"    {YEL}ungoverned target states (no guard clause names them): "
                  f"{', '.join(mc['ungoverned_targets'])}{RST}")
    print("\n" + "-" * 84)
    print(f"  {BOLD}BANK DENOMINATOR{RST}: {total_pos} positive + {total_neg} authority-negative "
          f"+ {total_sneak} sneak-path = {BOLD}{total_pos + total_neg + total_sneak}{RST} obligations")
    print(f"  {DIM}Each is matched against the registered gates next; anything already locked becomes"
          f" covered_by:<gate-id> and is NOT rebuilt.{RST}")
    return 0


def selftest():
    ok = True
    # The 2nd clause WRAPS mid-expression, exactly as the real cancel rules do - the case a
    # line-by-line reader lost, turning a governed transition into a phantom "ungoverned" finding.
    # Clause 2 WRAPS mid-expression (the real cancel rules do). Clause 3 has TWO actors joined by OR
    # (the real dispute rule does) - reading only the first made the bank demand a refusal for a party
    # the guard actually permits, and the bank's own live run caught it.
    src = ("or (v_is_client and old.status = 'requested' and new.status = 'broadcasting')\n"
           "or (v_is_client and old.status in ('accepted','en_route')\n"
           "                and new.status = 'cancelled_by_client')\n"
           "or ((v_is_client or v_is_matched_provider) and old.status in ('in_progress')\n"
           "                and new.status = 'disputed')\n"
           "raise exception 'Not allowed: illegal transition % -> %', old.status, new.status")
    got = parse_allow(src)
    exp = {("owner", "requested", "broadcasting"),
           ("owner", "accepted", "cancelled_by_client"),
           ("owner", "en_route", "cancelled_by_client"),
           ("owner", "in_progress", "disputed"),
           ("counterparty", "in_progress", "disputed")}
    if {(a, f, t) for a, f, t, _ in got} != exp:
        print(f"  {RED}FAIL{RST} allow-parse lost a WRAPPED clause, mis-expanded `in (...)`, "
              f"or dropped the 2nd actor of an `(A or B)` clause: {sorted({(a,f,t) for a,f,t,_ in got})}"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} allow-shape: wrapped clauses + `in (...)` + BOTH actors of `(A or B)`")

    d = parse_deny("IF NEW.status = 'published' AND NOT is_admin THEN\n"
                   "IF TG_OP='UPDATE' AND NEW.status IN ('released','refunded') THEN")
    if {t for t, _, _ in d} != {"published", "released", "refunded"}:
        print(f"  {RED}FAIL{RST} deny-parse missed a target: {d}"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} deny-shape: finds both `= 'x'` and `IN (...)` targets")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if psql("select 1") is None:
        print("  SKIP: docker/psql unavailable")
        return 0
    m = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0
    rc = report(m)
    print(f"  wrote {os.path.basename(OUT)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
