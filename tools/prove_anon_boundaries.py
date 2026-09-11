#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANON identity boundaries, asked over the REAL gateway with the anon key and NO session.

verify_identity_boundaries.py answers the BE-ufai-I questions as a signed-in NON-ADMIN, which
covers the buyer/two_context personas. It cannot cover the ANON persona: anon and authenticated
are DIFFERENT Postgres roles with different policy sets, and an RLS probe needs the ROLE
(feedback_rls_probe_needs_the_role_not_just_claims) - inferring "anon has strictly less" from an
authenticated probe is an inference, not a measurement. So this asks as anon, over HTTP, the way
a stranger actually would:

  1. bola_object   - another person's UNPUBLISHED listing, fetched by its real id: zero rows.
                     The id demonstrably exists (read via psql first), so an empty answer is a
                     boundary, not an absence. The refusal is LEGIBLE: an empty 200 array (RLS
                     row-filtering, PostgREST's contract) or an explicit 4xx, never a 5xx.
  2. jwt_not_body  - an anon INSERT claiming a real seller's name in the body: refused with a
                     stated reason (401/403 + a message naming the rule), and proven unwritten
                     by re-reading the table.
  3. tenant_boundary - unpublished rows across ALL hives: anon sees zero of them, stated as a
                     count over the whole table rather than one lucky id.

Every probe is read-only or refused; nothing is rolled back because nothing is ever written.
Writes a per-run artifact (anon_boundaries_report.json) so bank rows can re-earn on re-runs.

Run:  python tools/prove_anon_boundaries.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:54321"
ANON = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"
GREEN, RED, DIM, RST = "\033[92m", "\033[91m", "\033[2m", "\033[0m"


def psql(sql):
    p = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[:200])
    return (p.stdout or "").strip()


def http(method, path, body=None):
    req = urllib.request.Request(
        f"{BASE}{path}", method=method,
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    results = {}

    # fixture: a real unpublished listing id + the size of the hidden set (asked of the DB, so the
    # "zero rows" answers below are boundaries over a demonstrably non-empty set, never vacuous)
    draft_id = psql("select id from marketplace_listings where status <> 'published' limit 1")
    hidden = int(psql("select count(*) from marketplace_listings where status <> 'published'") or 0)
    seller = psql("select worker_name from marketplace_sellers where auth_uid is not null limit 1")
    if not draft_id or hidden < 2:
        print(f"  {RED}FAIL{RST} - fixture missing: need >=2 unpublished listings to probe against")
        return 1

    # EX-HP H2 (20260907000004): anon no longer holds SELECT on the base table at all - a stranger browses through
    # v_marketplace_listings_public. So the base table answers with a GRANT-level refusal (401/403, code 42501, no rows),
    # which is a refusal with zero rows, and the legible-empty-array question moves to the VIEW the stranger reads.
    st, body = http("GET", f"/rest/v1/marketplace_listings?id=eq.{draft_id}&select=id,title,status")
    rows = json.loads(body) if st == 200 else None
    refused = st in (401, 403) and "42501" in (body or "")
    stv, bodyv = http("GET", f"/rest/v1/v_marketplace_listings_public?id=eq.{draft_id}&select=id,title,status")
    rowsv = json.loads(bodyv) if stv == 200 else None
    ok1 = ((st == 200 and rows == []) or refused) and stv == 200 and rowsv == []
    results["bola_object"] = {
        "status": "pass" if ok1 else "fail",
        "detail": f"an unpublished listing that EXISTS ({draft_id[:8]}..., one of {hidden}) fetched "
                  f"by id as anon: base table HTTP {st} ({'grant-level refusal, no rows' if refused else (0 if rows == [] else 'LEAKED')}), "
                  f"public view HTTP {stv}, {0 if rowsv == [] else 'LEAKED'} rows. An empty 200 array on the view "
                  f"the stranger actually reads is PostgREST's legible RLS refusal shape - filtered, not erred"}

    st2, body2 = http("POST", "/rest/v1/marketplace_listings",
                      {"seller_name": seller, "title": "anon forged identity probe",
                       "section": "parts", "category": "other", "price": 1, "status": "draft"})
    wrote = psql("select count(*) from marketplace_listings where title = 'anon forged identity probe'")
    ok2 = st2 >= 400 and wrote == "0"
    reason = ""
    try:
        reason = (json.loads(body2).get("message") or "")[:120]
    except Exception:
        reason = body2[:120]
    results["jwt_not_body"] = {
        "status": "pass" if ok2 else "fail",
        "detail": f"anon INSERT claiming seller_name='{seller}' in the body: HTTP {st2} "
                  f"('{reason}'), and re-reading the table finds {wrote} such row(s) - identity "
                  f"cannot be asserted by a request body with no JWT behind it"}

    st3, body3 = http("GET", "/rest/v1/marketplace_listings?status=neq.published&select=id")
    rows3 = json.loads(body3) if st3 == 200 else None
    refused3 = st3 in (401, 403) and "42501" in (body3 or "")
    st3v, body3v = http("GET", "/rest/v1/v_marketplace_listings_public?status=neq.published&select=id")
    rows3v = json.loads(body3v) if st3v == 200 else None
    ok3 = ((st3 == 200 and rows3 == []) or refused3) and st3v == 200 and rows3v == []
    results["tenant_boundary"] = {
        "status": "pass" if ok3 else "fail",
        "detail": f"every unpublished listing across ALL hives asked for in one anon query: base table HTTP "
                  f"{st3} ({'grant-level refusal' if refused3 else (len(rows3) if isinstance(rows3, list) else '?')}), "
                  f"public view HTTP {st3v}, {len(rows3v) if isinstance(rows3v, list) else '?'} of {hidden} visible. "
                  f"The whole hidden set is invisible as a set, not one lucky id"}

    ok = True
    for name, r in results.items():
        c, tag = (GREEN, "PASS") if r["status"] == "pass" else (RED, "FAIL")
        ok = ok and r["status"] == "pass"
        print(f"  {c}{tag}{RST}  {name:16} {DIM}{r['detail'][:150]}{RST}")
    with open(os.path.join(ROOT, "anon_boundaries_report.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(f"\n  {GREEN if ok else RED}{sum(1 for r in results.values() if r['status'] == 'pass')}"
          f"/{len(results)} hold{RST} - anon_boundaries_report.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
