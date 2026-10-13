"""prove_memory_identity.py - WHO may read or write a person's durable AI memory (2026-10-13, LIVE, local stack).

THE DEFECT, PROVEN LIVE BEFORE THE FIX: agent-memory-store (verify_jwt = false) checked tenancy ONLY when a hive was
claimed. With nothing but the public anon key, {op:"recall", worker_name:"<anyone>"} and no hive returned that person's
durable memories from EVERY hive (HTTP 200, a marker row came back), and {op:"store"} wrote memories under any name
(HTTP 200, one row). agentic-rag-loop forwarded the body's worker_name to it WITH THE SERVICE KEY, and its solo logbook
lane read v_logbook_truth by that name with no hive filter. recallEpisodic treated "no hive" as "every hive".

THE CONTRACT (each a live REST call; marker rows only, deleted at the end; no model is called):
  agent-memory-store  anonymous recall / store                      -> 401, nothing returned or written
                      (durable memory is the ACCOUNT's: a row under the person's name that no account owns never
                      comes back; their own store writes their account; RLS shows them their own row over REST)
                      a member naming someone else (recall / store) -> 403 not_your_memory, nothing written
                      a member's own recall                         -> 200 WITH their own marker (positive control:
                                                                       the refusals cannot pass on a missing marker)
                                                                       and never the other person's
  agentic-rag-loop    an anonymous question naming someone          -> no memory-store call at all
                      a signed-in question                          -> a memory-store call (the oracle can see one)

The loop oracle is the runtime's own log line ("serving the request with supabase/functions/agent-memory-store"),
COUNTED before and after each call - never a --since window, which compares the host clock with the Docker VM's.

  python tools/prove_memory_identity.py        # SKIP (exit 0) when the local stack is not up
"""
import base64
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:54321"
PERSON = "davidvelasco@auth.workhiveph.com"   # a seeded worker (password test1234 is the seed's, never changed)
EDGE_CANDIDATES = ("supabase_edge_runtime_workhive", "wh_edge_resend2")


def _role(jwt: str) -> str:
    try:
        part = jwt.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("role", "")
    except Exception:
        return ""


def _key() -> str:
    """The local ANON key - and PROVEN anon by its own claims. The first version took the key in tests/_db-cleanup.ts,
    which is the SERVICE-ROLE key: every "anonymous" call was a trusted internal call, the function rightly answered
    200, and three checks failed for the instrument's identity, not the product's. A caller called anonymous must be."""
    cands = []
    f = ROOT / ".tmp" / "local_anon_key.txt"
    if f.is_file():
        cands.append(f.read_text(encoding="utf-8").strip())
    for t in sorted((ROOT / "tests").glob("*.ts")):
        try:
            cands += re.findall(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", t.read_text(encoding="utf-8"))
        except Exception:
            continue
    return next((k for k in cands if _role(k) == "anon"), "")


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-tA", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "").strip()


def post(path: str, body: dict, key: str, bearer: str, extra: dict | None = None):
    h = {"Content-Type": "application/json", "apikey": key, "Authorization": f"Bearer {bearer}", **(extra or {})}
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(body).encode(), method="POST", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def edge_container() -> str:
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    return next((c for c in EDGE_CANDIDATES if c in out), "")


def store_calls(container: str) -> int:
    out = subprocess.run(["docker", "logs", "--since", "60m", container], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (out.stdout + out.stderr).count("serving the request with supabase/functions/agent-memory-store")


def main() -> int:
    key = _key()
    c, _ = post("/functions/v1/agent-memory-store", {}, key, key) if key else (0, "")
    container = edge_container()
    if not key or c == 0 or not container:
        print("  SKIP  memory identity: the local stack (kong + edge runtime) is not up")
        return 0
    c, tok = post("/auth/v1/token?grant_type=password", {"email": PERSON, "password": "test1234"}, key, key)
    if c != 200:
        print(f"  FAIL  could not sign the seeded person in (HTTP {c})")
        return 1
    jwt = json.loads(tok)["access_token"]
    row = psql(f"select hm.hive_id || '|' || hm.worker_name from public.hive_members hm join auth.users u on u.id = hm.auth_uid "
               f"where u.email = '{PERSON}' and hm.status = 'active' order by hm.joined_at limit 1;")
    if "|" not in row:
        print("  FAIL  the seeded person has no active hive membership to test in")
        return 1
    hive, own = row.split("|", 1)
    uid = psql(f"select id from auth.users where email = '{PERSON}';")
    mark = "W4M-PROBE-" + secrets.token_hex(3).upper()
    own_sql = own.replace("'", "''")
    # the other person's marker; the person's own marker, stamped with their ACCOUNT as every write now is; and a row
    # under the person's NAME with no account (what a freed name leaves behind) - durable memory is the account's
    psql(f"insert into public.agent_episodic_memory (hive_id, worker_name, auth_uid, memory_type, content, importance) values "
         f"('{hive}', '{mark}', null, 'factual', 'other marker {mark}', 0.5), "
         f"('{hive}', '{own_sql}', '{uid}', 'factual', 'own marker {mark}', 1.0), "
         f"('{hive}', '{own_sql}', null, 'factual', 'name-only marker {mark}', 1.0);")
    results = []

    def check(name, ok, detail):
        results.append(bool(ok))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  ({detail[:200]})"))

    try:
        c, b = post("/functions/v1/agent-memory-store", {"op": "recall", "worker_name": mark}, key, key)
        check("anonymous recall by name -> 401, nothing returned", c == 401 and mark not in b, f"HTTP {c} {b}")
        c, b = post("/functions/v1/agent-memory-store", {"op": "recall", "worker_name": own}, key, key)
        check("anonymous recall of a real member's name -> 401", c == 401 and f"own marker {mark}" not in b, f"HTTP {c} {b}")
        c, b = post("/functions/v1/agent-memory-store", {"op": "store", "worker_name": mark,
                    "memories": [{"memory_type": "factual", "content": f"anon wrote {mark}"}]}, key, key)
        n = psql(f"select count(*) from public.agent_episodic_memory where content = 'anon wrote {mark}';")
        check("anonymous store -> 401, nothing written", c == 401 and n == "0", f"HTTP {c} rows={n} {b}")
        c, b = post("/functions/v1/agent-memory-store", {"op": "recall", "hive_id": hive, "worker_name": mark}, key, jwt)
        check("a member naming someone else -> 403 not_your_memory", c == 403 and "not_your_memory" in b and mark not in b, f"HTTP {c} {b}")
        c, b = post("/functions/v1/agent-memory-store", {"op": "store", "hive_id": hive, "worker_name": mark,
                    "memories": [{"memory_type": "factual", "content": f"as other {mark}"}]}, key, jwt)
        n = psql(f"select count(*) from public.agent_episodic_memory where content = 'as other {mark}';")
        check("a member writing under someone else's name -> 403, nothing written", c == 403 and n == "0", f"HTTP {c} rows={n}")
        c, b = post("/functions/v1/agent-memory-store", {"op": "recall", "hive_id": hive, "limit": 20}, key, jwt)
        check("a member's own recall -> 200 WITH their own marker (positive control)", c == 200 and f"own marker {mark}" in b, f"HTTP {c} {b}")
        check("... and never the other person's marker", f"other marker {mark}" not in b, b)
        check("... nor a row under their NAME that no account owns (a freed name inherits nothing)",
              f"name-only marker {mark}" not in b, b)
        c, b = post("/functions/v1/agent-memory-store", {"op": "store", "hive_id": hive,
                    "memories": [{"memory_type": "factual", "content": f"own write {mark}"}]}, key, jwt)
        stamped = psql(f"select auth_uid from public.agent_episodic_memory where content = 'own write {mark}';")
        check("a member's own store is written with their account", c == 200 and stamped == uid, f"HTTP {c} auth_uid={stamped!r}")
        req = urllib.request.Request(f"{BASE}/rest/v1/agent_episodic_memory?select=content&content=like.*{mark}*",
                                     headers={"apikey": key, "Authorization": f"Bearer {jwt}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                rest = r.read().decode()
            rc = 200
        except urllib.error.HTTPError as e:
            rc, rest = e.code, e.read().decode()
        check("the RLS read policy shows a person their own durable memory, and only theirs (plain REST)",
              rc == 200 and f"own marker {mark}" in rest and f"other marker {mark}" not in rest and f"name-only marker {mark}" not in rest,
              f"HTTP {rc} {rest}")

        nm = {"x-wh-walk-no-model": "1"}   # honoured only on the local runtime: no model is called
        k0 = store_calls(container)
        c, b = post("/functions/v1/agentic-rag-loop", {"question": "What do you remember about my pump work?", "worker_name": mark}, key, key, nm)
        time.sleep(3)
        k = store_calls(container) - k0
        check("agentic-rag-loop: an anonymous question naming someone recalls nothing (0 memory-store calls)", k == 0 and mark not in b, f"HTTP {c} calls={k}")
        k1 = store_calls(container)
        c, b = post("/functions/v1/agentic-rag-loop", {"question": "What do you remember about my pump work?", "hive_id": hive, "worker_name": mark}, key, jwt, nm)
        time.sleep(3)
        k = store_calls(container) - k1
        check("agentic-rag-loop: a signed-in question DOES recall (the oracle can see one)", k >= 1 and f"other marker {mark}" not in b, f"HTTP {c} calls={k}")
    finally:
        psql(f"delete from public.agent_episodic_memory where worker_name = '{mark}' or content like '%{mark}%';")
    left = psql(f"select count(*) from public.agent_episodic_memory where worker_name = '{mark}' or content like '%{mark}%';")
    if left != "0":
        print(f"  FAIL  {left} marker row(s) were left behind")
        return 1
    ok = all(results)
    print(f"{'PASS' if ok else 'FAIL'}: memory identity - {sum(results)}/{len(results)} live checks (marker rows cleaned)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
