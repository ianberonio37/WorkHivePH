#!/usr/bin/env python3
"""validate_cmms_webhook_security_live.py — CMMS Integrations PDDA webhook-hardening gate.

Complements fb1_webhook_idempotency_live.py (which proves F5 exactly-once). This locks the
NON-idempotency webhook properties the replay/malformed fixes added to cmms-webhook-receiver:

  F1004/I6  REPLAY WINDOW — a validly-signed webhook with an OLD or FAR-FUTURE timestamp
            must be REJECTED (401 stale_timestamp). Live-proven pre-fix: 1h-old/30d-old/
            far-future all accepted 200.
  F1-b      MALFORMED body (valid sig, non-JSON) → 400, not a 500.
  control   wrong signature → 401; a FRESH signed delivery → 200 (no over-block).

Reseed-resilient (resolves a real hive). $0, local-only, self-cleans.
"""
import hashlib, hmac, json, subprocess, sys, time
DB = "supabase_db_workhive"; EDGE = "supabase_edge_runtime_workhive"
BASE = "http://127.0.0.1:54321/functions/v1"
STAMP = str(int(time.time()))
EXT = f"WHSEC-{STAMP}"; SECRET = f"whsec-secret-{STAMP}"

def sql(q):
    r = subprocess.run(["docker","exec",DB,"psql","-U","postgres","-d","postgres","-qtA","-c",q],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0: raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()

def denv(var):
    r = subprocess.run(["docker","exec",EDGE,"sh","-c",f'printf "%s" "${var}"'],
                       capture_output=True, text=True, timeout=20)
    return r.stdout.strip()

def post(fn, body, headers, timeout=60):
    cmd = ["curl","-s","-m",str(timeout),"-w","\n%{http_code}","-X","POST",f"{BASE}/{fn}"]
    for k,v in headers.items(): cmd += ["-H",f"{k}: {v}"]
    cmd += ["-d",body]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+8)
    out = r.stdout.rsplit("\n",1)
    return int(out[-1].strip() or 0)

def hx(secret, signed): return hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()

def main():
    anon = denv("SUPABASE_ANON_KEY")
    if not anon.startswith("eyJ"): print("  ! no anon key — edge up?"); return 2
    hive = sql("select id from hives order by created_at limit 1;")
    if not hive: print("  ! no hive"); return 2
    cfg = sql("insert into integration_configs (hive_id,system_type,label,auth_method,enabled,auth_token) "
              f"values ('{hive}','generic','WHSEC gate (transient)','hmac',true,'{SECRET}') returning id;")
    fails = []
    try:
        payload = {"work_order_no":EXT,"asset_tag":"WHSEC-ASSET","status":"Open","type":"Breakdown",
                   "description":"webhook security gate","actual_hours":1,"created_date":"2026-06-30T00:00:00Z"}
        body = json.dumps({"event":"work_order.created","cmms_type":"generic","payload":payload})
        def deliver(ts):
            h = {"apikey":anon,"Content-Type":"application/json",
                 "X-WorkHive-Signature":f"sha256={hx(SECRET, f'{ts}.{body}')}","X-WorkHive-Timestamp":str(ts)}
            return post(f"cmms-webhook-receiver?config_id={cfg}", body, h)
        post(f"cmms-webhook-receiver?config_id={cfg}", "{}", {"apikey":anon})  # warm cold-start
        now = int(time.time())
        fresh = deliver(now)                 # must be 200
        old1  = deliver(now - 3600)          # must be 401
        old30 = deliver(now - 2592000)       # must be 401
        fut   = deliver(now + 999999)        # must be 401
        bad = "not-json{{"
        mal = post(f"cmms-webhook-receiver?config_id={cfg}", bad,
                   {"apikey":anon,"Content-Type":"application/json",
                    "X-WorkHive-Signature":f"sha256={hx(SECRET, f'{now}.{bad}')}","X-WorkHive-Timestamp":str(now)})  # 400
        wrong = post(f"cmms-webhook-receiver?config_id={cfg}", body,
                     {"apikey":anon,"Content-Type":"application/json",
                      "X-WorkHive-Signature":"sha256=deadbeef","X-WorkHive-Timestamp":str(now)})  # 401
        if fresh != 200: fails.append(f"fresh signed delivery got {fresh}, expected 200 (over-block)")
        if old1  != 401: fails.append(f"1h-old replay got {old1}, expected 401 (replay window open)")
        if old30 != 401: fails.append(f"30d-old replay got {old30}, expected 401 (replay window open)")
        if fut   != 401: fails.append(f"far-future ts got {fut}, expected 401 (replay window open)")
        if mal   != 400: fails.append(f"malformed body got {mal}, expected 400")
        if wrong != 401: fails.append(f"wrong signature got {wrong}, expected 401")
    finally:
        sql(f"delete from logbook where machine='WHSEC-ASSET' and hive_id='{hive}';")
        sql(f"delete from external_sync where external_id='{EXT}' and hive_id='{hive}';")
        sql(f"delete from integration_configs where id='{cfg}';")
    print("=" * 64)
    print(f"  cmms-webhook-receiver security gate  |  hive={hive[:8]}")
    if fails:
        for f in fails: print(f"  [FAIL] {f}")
        print(f"  {len(fails)} webhook-security regression(s) - FAIL"); return 1
    print("  [PASS] replay window enforced (old/future->401) | malformed->400 | wrong-sig->401 | fresh->200")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
