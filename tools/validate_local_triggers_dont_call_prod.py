#!/usr/bin/env python3
"""validate_local_triggers_dont_call_prod.py — does a LOCAL write reach PRODUCTION?

FOUND 2026-07-31 while extending the S9-knowledge layer. Three `AFTER INSERT` triggers on the LOCAL database —
`embed-logbook` (logbook), `embed-pm-completions` (pm_completions), `embed-skill-badges` (skill_badges) —
call `supabase_functions.http_request()` against a **production** URL (`https://<ref>.supabase.co/functions/
v1/embed-entry`) with a **service-role bearer embedded in the trigger definition itself**.

WHY THAT IS NOT THEORETICAL. Three things were measured, not assumed:
  * the trigger definitions carry the production host and a service-role JWT (read from pg_trigger)
  * `net._http_response` holds delivered responses, including 200s from the same day — pg_net is live here
  * the DB container resolves the production host (`getent hosts` returns an address; external DNS works)

So every COMMITTED local insert into those tables POSTs the row to production. Seeding and manual testing are
constant on `logbook`, which means dev data flows into the production embedding store — the mirror image of
[[feedback_live_mcp_writes_pollute_test_db]], and worse, because embeddings are not obviously reversible.
Separately, a **service-role key bypasses RLS entirely** and this one is sitting in the local catalog, visible
to anyone who can read `pg_trigger` and to any `pg_dump` that gets shared — a secret in a place the secret
scanners never look, exactly the blind-spot class of [[feedback_pasted_keys_in_docs_leak_scanner_blindspot]].

WHAT THIS GATE ASSERTS: no trigger in the LOCAL database calls an EXTERNAL host, and no trigger definition
embeds a JWT. It is deliberately narrow — it does not judge production's own triggers, which are Ian's to
change; it keeps the local database from talking to them.

FIXING IT is a local migration that repoints the three triggers at the local functions URL (or drops them, if
embedding is not wanted locally). ROTATING the exposed production key is an outward action and Ian's call.

Usage:  python tools/validate_local_triggers_dont_call_prod.py [--selftest]
"""
import json
import re
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

# A JWT in a trigger body. Matched structurally (three base64url segments) rather than by the word
# "service_role", which is INSIDE the encoded payload and therefore invisible to a plain text search — the
# first cut of this check looked for that word and reported a clean result on a definition that carried a key.
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
EXTERNAL_HOST_RE = re.compile(r"https://[a-z0-9.-]*\.supabase\.co", re.I)

QUERY = """
-- tgenabled is "char", and `text || "char"` is ambiguous in Postgres, so it is cast explicitly.
-- Without the cast psql errors and this gate SKIPs — which it did, correctly, rather than reporting clean.
select c.relname || '|' || t.tgname || '|' || t.tgenabled::text || '|' || pg_get_triggerdef(t.oid)
from pg_trigger t
join pg_class c on c.oid = t.tgrelid
join pg_namespace n on n.oid = c.relnamespace
where not t.tgisinternal and n.nspname = 'public';
"""


def fetch():
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-c", QUERY],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:120]
    return [ln for ln in (r.stdout or "").splitlines() if "|" in ln], ""


def judge(rows):
    """-> (live, disabled, jwt). Definitions are never printed: they contain the key.

    ENABLED vs DISABLED is the difference between a live outbound path and a dormant one, and the gate
    must not blur them. A DISABLED trigger cannot fire, so local writes no longer reach production — that
    is the containment. But its definition still carries the key in the catalog, so the EXPOSURE stands
    either way and is reported separately. Blurring the two would either cry wolf after the containment
    or, worse, call the key handled because the trigger stopped firing.
    """
    live, disabled, jwt = [], [], []
    for ln in rows:
        parts = ln.split("|", 3)
        if len(parts) < 4:
            continue
        table, tg, enabled, defn = parts[0], parts[1], parts[2], parts[3]
        m = EXTERNAL_HOST_RE.search(defn)
        if m:
            (live if enabled != "D" else disabled).append((table, tg, m.group(0)))
        if JWT_RE.search(defn):
            jwt.append((table, tg))
    return live, disabled, jwt


def selftest():
    """A definition carrying a key must be CAUGHT, and a clean local one must PASS.

    The structural-JWT case is the one that matters: `service_role` lives in the ENCODED payload, so a
    text search for it returns clean on a definition that is leaking a key.
    """
    print("  selftest: an external host and an embedded JWT must both be caught")
    bad_host = ["logbook|embed-logbook|CREATE TRIGGER x AFTER INSERT ON public.logbook EXECUTE FUNCTION "
                "supabase_functions.http_request('https://abcdefgh.supabase.co/functions/v1/embed-entry')"]
    bad_key = ["logbook|embed-logbook|CREATE TRIGGER x ... '{\"Authorization\":\"Bearer "
               "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.abcdefghij\"}'"]
    good = ["logbook|t_local|CREATE TRIGGER t_local AFTER INSERT ON public.logbook EXECUTE FUNCTION "
            "supabase_functions.http_request('http://kong:8000/functions/v1/embed-entry')"]
    disabled_host = [bad_host[0].replace("|CREATE TRIGGER", "|D|CREATE TRIGGER", 1)]
    bad_host = [bad_host[0].replace("|CREATE TRIGGER", "|O|CREATE TRIGGER", 1)]
    bad_key = [bad_key[0].replace("|CREATE TRIGGER", "|O|CREATE TRIGGER", 1)]
    good = [good[0].replace("|CREATE TRIGGER", "|O|CREATE TRIGGER", 1)]
    ok = True
    if len(judge(bad_host)[0]) != 1:
        print(f"  {RED}FAIL{RST} — an ENABLED external supabase.co host was not caught"); ok = False
    if len(judge(disabled_host)[1]) != 1 or judge(disabled_host)[0]:
        print(f"  {RED}FAIL{RST} — a DISABLED external trigger must be reported as contained, not live"); ok = False
    if len(judge(bad_key)[2]) != 1:
        print(f"  {RED}FAIL{RST} — an embedded JWT was not caught (the word 'service_role' is inside the "
              f"ENCODED payload, so a text search for it misses this)"); ok = False
    live, dis, j = judge(good)
    if live or dis or j:
        print(f"  {RED}FAIL{RST} — a clean LOCAL trigger was flagged"); ok = False
    print(f"  {GREEN}PASS{RST} — catches the external host and the embedded key, accepts a local trigger"
          if ok else "")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Local triggers must not call production{RST}")
    if selftest() != 0:
        print(f"  {RED}FAIL{RST} — the detector failed its own self-test; its result means nothing.")
        return 1
    rows, err = fetch()
    if rows is None:
        print(f"  {YEL}SKIP{RST} local database unavailable ({err})")
        return 0
    live, disabled, jwt = judge(rows)
    print(f"  {len(rows)} public triggers inspected")
    for table, tg, host in live:
        print(f"  {RED}LIVE -> EXTERNAL{RST}  {table}.{tg} {DIM}-> {host}{RST}")
    for table, tg, host in disabled:
        print(f"  {YEL}contained{RST}       {table}.{tg} {DIM}-> {host} (DISABLED: cannot fire){RST}")
    for table, tg in jwt:
        print(f"  {YEL}embedded key{RST}    {table}.{tg} {DIM}(a JWT in the trigger body; not printed){RST}")

    if live:
        print(f"\n  {RED}FAIL{RST} — a LOCAL write reaches PRODUCTION. Every committed insert on these "
              f"tables POSTs the row to the production edge function, so seeding and manual testing flow "
              f"into the production embedding store.\n"
              f"  FIX (local, reversible): `ALTER TABLE <t> DISABLE TRIGGER <name>` stops it immediately; "
              f"repointing at the local functions URL restores the behaviour without the outbound call.")
        return 1
    if jwt:
        # Containment is not rotation. The trigger can no longer fire, but the key is still readable by
        # anyone with catalog access or a dump — and only Ian can rotate a production credential, so this
        # is reported every run as standing debt rather than being quietly counted as fixed.
        print(f"\n  {YEL}CONTAINED{RST} — no local trigger can reach production any more"
              f"{' (' + str(len(disabled)) + ' disabled)' if disabled else ''}, but "
              f"{len(jwt)} definition(s) still carry a service-role JWT in the catalog. That key bypasses "
              f"RLS and is visible to anyone who can read pg_trigger or a dump. ROTATING it is an outward "
              f"action and Ian's call; this line stays until the definitions no longer carry a key.")
        return 0
    print(f"  {GREEN}PASS{RST} — no local trigger calls an external host, and none carries a key")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
