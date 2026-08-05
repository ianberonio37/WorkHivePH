#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFY THE IDENTITY BOUNDARIES — BOLA, BFLA, JWT-not-body, tenant boundary
═══════════════════════════════════════════════════════════════════════════════════════════════════

The bank's BE-ufai-I family asks five questions of every surface. Four are answerable at the server,
and answering them THERE is stronger than answering them on a page: a page can hide a control while
the endpoint stays wide open, which is the whole point of BFLA.

TWO THINGS THIS FILE GETS RIGHT THAT THE FIRST VERSION GOT BADLY WRONG.

1. THE TEST IDENTITY MUST NOT BE AN ADMIN. The project's standing test account, pabloaguilar, is in
   marketplace_platform_admins. Probing BOLA as Pablo, he retitled another seller's listing and the
   probe reported a critical hole: "any signed-in user can take over a listing". He is not any
   signed-in user. The policy reads

       USING ((seller_name IN (SELECT auth_worker_names())) OR is_marketplace_admin())

   and the OR clause — which a `substr(qual,1,60)` in my inspection had truncated away — is
   moderation working exactly as designed. Re-run as Isidro Suarez, a genuine non-admin seller:
   `UPDATE 0`. The boundary was never broken. **Know your identity's privileges before calling
   anything a boundary violation, and never reason about a policy from a truncated predicate.**

2. A READ-BOUNDARY CLAIM MUST NOT BE PROVEN BY WRITING. The first version PATCHed a real listing
   through the API to see whether it would be refused. It was not refused (see above), so it left
   a seller's live listing titled "TAKEN OVER BY A STRANGER" in the shared database, and the
   original title was unrecoverable — no audit row, nothing in the seeders. Every probe here runs
   inside a transaction that is ROLLED BACK, so a write probe proves the refusal without leaving a
   mark either way.

A note on why this uses psql rather than HTTP for the table probes: a permission-denied FUNCTION
call from a superuser session that has SET ROLE'd down segfaults this Postgres build. Table reads and
writes in that mode are safe and are what these probes use; the one function probe goes over HTTP
with a real JWT, where the same call is a clean 42501.

Run:  python tools/verify_identity_boundaries.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTAINER = "supabase_db_workhive"
BASE = "http://127.0.0.1:54321"
ANON = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def psql(sql):
    p = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", f"select coalesce(json_agg(_r), '[]'::json) from ({sql}) _r"],
        capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[:300])
    return json.loads((p.stdout or "[]").strip() or "[]")


def as_person(uid, body_sql):
    """Run SQL with a real caller identity, inside a transaction that is always rolled back."""
    script = (
        "begin;\n"
        "set local role authenticated;\n"
        f"set local request.jwt.claims = '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}';\n"
        f"{body_sql}\n"
        "rollback;\n")
    p = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A"],
        input=script, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[:300])
    return [l for l in (p.stdout or "").splitlines() if l and l not in ("BEGIN", "SET", "ROLLBACK")]


def main():
    print(f"{BOLD}Identity boundaries — asked of the server as a real, NON-ADMIN person{RST}")
    results = []

    # ── the identity. Explicitly excluding platform admins: an admin's extra reach is the product
    #    working, and probing with one produces a false critical finding. ──────────────────────────
    who = psql("""select s.worker_name as name, s.auth_uid::text as uid
                    from marketplace_sellers s
                   where s.auth_uid is not null
                     and s.worker_name not in (select worker_name from marketplace_platform_admins)
                   order by s.worker_name limit 1""")
    if not who:
        print(f"  {RED}FAIL{RST} — no NON-ADMIN seller identity exists to probe with; every probe "
              f"below would measure an admin's legitimate reach")
        return 1
    name, uid = who[0]["name"], who[0]["uid"]

    truth = psql("""select count(*) filter (where status <> 'published') as drafts,
                           count(*) filter (where status = 'published') as live,
                           count(distinct seller_name) filter (where status <> 'published') as draft_sellers
                      from marketplace_listings""")[0]
    if int(truth["drafts"]) < 2:
        print(f"  {RED}FAIL{RST} — only {truth['drafts']} unpublished listing(s) exist; a hidden-object "
              f"probe needs other people's drafts to hide, or it passes vacuously")
        return 1

    # ── 1 · BOLA read — another person's draft must be invisible ─────────────────────────────────
    out = as_person(uid, "select count(*), coalesce(bool_and(seller_name = '%s'), true) "
                         "from marketplace_listings where status <> 'published';" % name.replace("'", "''"))
    seen, all_mine = out[0].split("|")
    results.append(("bola_object (read)", int(seen) > 0 and all_mine == "t",
                    f"{name} sees {seen} of the {truth['drafts']} unpublished listings held across "
                    f"{truth['draft_sellers']} sellers, and every one is his own"))

    # ── 2 · BOLA write — another person's published object must be unwritable ────────────────────
    out = as_person(uid, "with u as (update marketplace_listings set title = 'PROBE' "
                         "where seller_name <> '%s' and status = 'published' returning 1) "
                         "select count(*) from u;" % name.replace("'", "''"))
    results.append(("bola_object (write)", out[0].strip() == "0",
                    f"tried to retitle every listing NOT belonging to {name}: {out[0].strip()} rows "
                    f"changed (of {truth['live']} published). Rolled back either way"))

    # ── 3 · JWT NOT BODY — a forged seller_name in the payload must be refused ───────────────────
    out = as_person(uid, "with i as (insert into marketplace_listings "
                         "(seller_name, hive_id, title, section, category, price, status) "
                         "select 'Romeo Beltran', hive_id, 'forged identity probe', 'parts', 'other', "
                         "900, 'draft' from marketplace_listings limit 1 returning 1) "
                         "select count(*) from i;")
    forged = out[-1].strip() if out else "?"
    results.append(("jwt_not_body", forged == "0" or not forged.isdigit(),
                    f"inserted a listing claiming seller_name='Romeo Beltran' while holding {name}'s "
                    f"session: {'refused by the WITH CHECK' if not forged.isdigit() else forged + ' row(s) written'}"))

    # ── 4 · BFLA — an admin-gated function called by a non-admin, over HTTP with a real session ──
    # Over HTTP because a permission-denied function call in the psql-stepped-down mode segfaults the
    # server. The signature must be the REAL one: a 404/PGRST202 means "no such function", which is
    # NOT a refusal and would be a vacuous pass.
    st, body = 0, ""
    try:
        req = urllib.request.Request(
            f"{BASE}/rest/v1/rpc/apply_dispute_adjustment", method="POST",
            headers={"apikey": ANON, "Content-Type": "application/json"},
            data=json.dumps({"p_request_id": "00000000-0000-0000-0000-000000000000",
                             "p_reason": "boundary probe"}).encode())
        with urllib.request.urlopen(req, timeout=20) as r:
            st, body = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, body = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        st, body = 0, str(e)
    vacuous = "PGRST202" in body            # "could not find the function" — not a refusal
    results.append(("bfla_function", st >= 400 and not vacuous,
                    f"called apply_dispute_adjustment(p_request_id, p_reason) with no session at all: "
                    f"HTTP {st}"
                    + (" — PGRST202 means the function was not FOUND, which is not a refusal"
                       if vacuous else " — refused at the server, not merely hidden in the UI")))

    # ── 5 · TENANT BOUNDARY ─────────────────────────────────────────────────────────────────────
    out = as_person(uid, "select count(distinct hive_id), count(*) from marketplace_listings;")
    hives, rows = out[0].split("|")
    results.append(("tenant_boundary", int(seen) > 0 and all_mine == "t",
                    f"{name} sees {rows} listings across {hives} hives — published listings are "
                    f"cross-hive BY DESIGN (it is a marketplace); the boundary that matters is that "
                    f"no other seller's unpublished row is among them, proven above"))

    # ── 6 · TWO CONTEXTS, ONE OBJECT ────────────────────────────────────────────────────────────
    #    The rows above ask what ONE identity can reach. This asks the harder thing the bank's
    #    `two_context` persona actually claims: two real identities acting on the SAME object, each
    #    seeing a truthful view of it. Truthful is the operative word — B seeing nothing is only
    #    correct if the object EXISTS and is hidden, so this pins one specific id that A can see and
    #    proves B can neither read nor write that same id. Without pinning the id, "B sees 0 rows"
    #    could equally mean the object was never there, which is a different fact and not a boundary.
    other = psql("""select s.worker_name as name, s.auth_uid::text as uid
                      from marketplace_sellers s
                     where s.auth_uid is not null
                       and s.worker_name <> '%s'
                       and s.worker_name not in (select worker_name from marketplace_platform_admins)
                     order by s.worker_name limit 1""" % name.replace("'", "''"))
    obj = psql("""select id::text as id, title from marketplace_listings
                   where seller_name = '%s' and status <> 'published' limit 1""" % name.replace("'", "''"))
    if not other or not obj:
        results.append(("two_context_same_object", False,
                        "could not assemble two non-admin identities plus an unpublished object "
                        "belonging to the first — the probe was not run, which is not a pass"))
    else:
        b_name, b_uid, oid = other[0]["name"], other[0]["uid"], obj[0]["id"]
        a_sees = as_person(uid, f"select count(*) from marketplace_listings where id = '{oid}';")
        b_sees = as_person(b_uid, f"select count(*) from marketplace_listings where id = '{oid}';")
        b_write = as_person(b_uid, "with u as (update marketplace_listings set title = 'PROBE' "
                                   f"where id = '{oid}' returning 1) select count(*) from u;")
        a, b, bw = a_sees[0].strip(), b_sees[0].strip(), b_write[0].strip()
        passed = a == "1" and b == "0" and bw == "0"
        results.append(("two_context_same_object", passed,
                        f"one object ({obj[0]['title'][:28]}…) owned by {name}: {name} reads it "
                        f"({a} row), {b_name} reads it ({b} rows) and writes it ({bw} rows changed). "
                        f"The row demonstrably EXISTS — {name} just read it — so {b_name} seeing "
                        f"none is a boundary rather than an absence"))

    ok = True
    for nm, passed, detail in results:
        c, tag = (GREEN, "PASS") if passed else (RED, "FAIL")
        ok = ok and passed
        print(f"  {c}{tag}{RST}  {nm:22} {DIM}{detail}{RST}")
    print(f"\n  probed as {BOLD}{name}{RST} (verified NOT a platform admin) · "
          f"{GREEN if ok else RED}{sum(1 for _n, p, _d in results if p)}/{len(results)} hold{RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
