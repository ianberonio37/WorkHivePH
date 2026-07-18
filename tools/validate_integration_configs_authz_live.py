#!/usr/bin/env python3
"""validate_integration_configs_authz_live.py — CMMS Integrations PDDA security gate.

Locks the three P0 authorization fixes against the SERVED local edge + PostgREST with
REAL user JWTs (reseed-resilient — resolves hives/identities at runtime):

  I1  cmms-sync cross-tenant BOLA via config_id override — a supervisor of hive A must
      NOT be able to sync hive B's config by passing {hive_id:A, config_id:<B's>}.
  I3  integration_configs role-scoped — a WORKER must NOT read the plaintext auth_token.
  I2  integration_configs role-scoped — a WORKER must NOT UPDATE a config (endpoint_url
      repoint = SSRF/token-exfil pivot).

Live-proven pre-fix 2026-07-10 (all HTTP 200 = VULN); post-fix all CLOSED. This gate
fails (non-zero exit) if any regresses. $0, local-only, self-cleans seeded configs.
"""
import json, subprocess, sys, time
DB = "supabase_db_workhive"; EDGE = "supabase_edge_runtime_workhive"
BASE = "http://127.0.0.1:54321"
PW = "test1234"
STAMP = str(int(time.time()))

def sql(q):
    r = subprocess.run(["docker","exec",DB,"psql","-U","postgres","-d","postgres","-qtA","-F","|","-c",q],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0: raise RuntimeError(r.stderr.strip())
    return [ln for ln in r.stdout.strip().splitlines() if ln.strip()]

def denv(var):
    r = subprocess.run(["docker","exec",EDGE,"sh","-c",f'printf "%s" "${var}"'],
                       capture_output=True, text=True, timeout=20)
    return r.stdout.strip()

def curl(method, path, headers, body=None, timeout=30):
    cmd = ["curl","-s","-m",str(timeout),"-w","\n%{http_code}","-X",method,f"{BASE}{path}"]
    for k,v in headers.items(): cmd += ["-H",f"{k}: {v}"]
    if body is not None: cmd += ["-d",body]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+8)
    out = r.stdout.rsplit("\n",1)
    return int(out[-1].strip() or 0), (out[0] if len(out)>1 else "")

def jwt(anon, email, pw):
    code, txt = curl("POST","/auth/v1/token?grant_type=password",
                     {"apikey":anon,"Content-Type":"application/json"},
                     json.dumps({"email":email,"password":pw}))
    if code != 200: raise RuntimeError(f"login {email} failed {code}: {txt[:120]}")
    return json.loads(txt)["access_token"]

def main():
    anon = denv("SUPABASE_ANON_KEY")
    if not anon.startswith("eyJ"):
        print("  ! no anon key — is the edge up?"); return 2

    # Resolve (reseed-resilient): hive A with BOTH a supervisor and a worker, and a
    # DISTINCT victim hive B.
    rows = sql("""select w.hive_id, w.role, u.email
                  from v_worker_truth w join auth.users u on u.id = w.auth_uid
                  where w.role in ('supervisor','worker') order by w.hive_id;""")
    byhive = {}
    for r in rows:
        h, role, email = r.split("|")
        byhive.setdefault(h, {}).setdefault(role, email)
    a_hive = next((h for h,m in byhive.items() if "supervisor" in m and "worker" in m), None)
    if not a_hive:
        print("  ! no hive with both a supervisor and worker — cannot probe"); return 2
    b_hive = next((h for h in byhive if h != a_hive), None)
    if not b_hive:
        print("  ! need a second (victim) hive for the BOLA probe"); return 2
    sup = jwt(anon, byhive[a_hive]["supervisor"], PW)
    wrk = jwt(anon, byhive[a_hive]["worker"], PW)

    a_cfg = b_cfg = None
    vulns = []
    try:
        a_cfg = sql("insert into integration_configs (hive_id,system_type,label,auth_method,enabled,auth_token,endpoint_url) "
            f"values ('{a_hive}','generic','AUTHZGATE-A (transient)','bearer',true,'SECRET-A-{STAMP}','https://a.example/WorkOrders') returning id;")[0]
        b_cfg = sql("insert into integration_configs (hive_id,system_type,label,auth_method,enabled,auth_token,endpoint_url) "
            f"values ('{b_hive}','generic','AUTHZGATE-B (transient)','bearer',true,'SECRET-B-{STAMP}','https://b.example/WorkOrders') returning id;")[0]

        # I1: supervisor of A targets B's config_id — must NOT process B's config.
        _, t1 = curl("POST","/functions/v1/cmms-sync",
            {"apikey":anon,"Authorization":f"Bearer {sup}","Content-Type":"application/json"},
            json.dumps({"hive_id":a_hive,"config_id":b_cfg,"test":True}))
        if b_hive in t1: vulns.append("I1 cross-tenant BOLA: supervisor synced a foreign hive's config")

        # I1 control: own config must still work (no over-block regression).
        _, t1c = curl("POST","/functions/v1/cmms-sync",
            {"apikey":anon,"Authorization":f"Bearer {sup}","Content-Type":"application/json"},
            json.dumps({"hive_id":a_hive,"config_id":a_cfg,"test":True}))
        own_ok = a_hive in t1c

        # I3: worker reads plaintext auth_token.
        _, t3 = curl("GET", f"/rest/v1/integration_configs?select=id,auth_token&hive_id=eq.{a_hive}",
                     {"apikey":anon,"Authorization":f"Bearer {wrk}"})
        if f"SECRET-A-{STAMP}" in t3: vulns.append("I3 token leak: worker read the plaintext auth_token")

        # I2: worker repoints endpoint_url.
        _, t2 = curl("PATCH", f"/rest/v1/integration_configs?id=eq.{a_cfg}",
            {"apikey":anon,"Authorization":f"Bearer {wrk}","Content-Type":"application/json","Prefer":"return=representation"},
            json.dumps({"endpoint_url":"https://attacker.example/steal"}))
        if "attacker.example" in t2: vulns.append("I2 worker write: worker repointed a config's endpoint_url")
    finally:
        for c in (a_cfg, b_cfg):
            if c: sql(f"delete from integration_configs where id='{c}';")

    print("=" * 64)
    print(f"  integration_configs authz gate  |  hive A={a_hive[:8]} victim B={b_hive[:8]}")
    print(f"  I1 own-config control: {'OK' if own_ok else 'BROKE (over-block regression!)'}")
    if vulns:
        for v in vulns: print(f"  [FAIL] {v}")
        print(f"  {len(vulns)} authz regression(s) - FAIL")
        return 1
    if not own_ok:
        print("  [FAIL] supervisor can no longer sync their OWN config (over-block)")
        return 1
    print("  [PASS] I1 BOLA closed | I3 token-read blocked | I2 worker-write blocked | own path intact")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
