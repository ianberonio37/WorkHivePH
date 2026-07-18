#!/usr/bin/env python3
"""verify_cmms_entity_sync_live.py — CMMS Integrations PDDA F-axis gate.

Locks the cmms-webhook-receiver entity handlers that were silent no-ops before this arc,
by driving REAL signed webhooks against the served edge and asserting the DB effect
(local substitute for a real CMMS). Self-contained (no external host), reseed-resilient.

  F1  asset.updated   -> tracked in external_sync (entity_type='asset')
  F2  inventory.updated -> external_sync (entity_type='inventory') + inventory_items,
      idempotent: a re-delivery UPDATES qty (no duplicate row)
  F1  pm.overdue      -> external_sync (entity_type='pm_schedule'), durable (not just logged)

USAGE: python tools/verify_cmms_entity_sync_live.py   (exit 0 = pass; needs the edge up)
"""
import hashlib, hmac, json, subprocess, time
DB="supabase_db_workhive"; EDGE="supabase_edge_runtime_workhive"
BASE="http://127.0.0.1:54321/functions/v1"
STAMP=str(int(time.time())); SECRET=f"entsync-{STAMP}"

def sql(q):
    r=subprocess.run(["docker","exec",DB,"psql","-U","postgres","-d","postgres","-qtA","-c",q],capture_output=True,text=True,timeout=30)
    if r.returncode!=0: raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()
def denv(v):
    r=subprocess.run(["docker","exec",EDGE,"sh","-c",f'printf "%s" "${v}"'],capture_output=True,text=True,timeout=20); return r.stdout.strip()
def hx(s,sig): return hmac.new(s.encode(),sig.encode(),hashlib.sha256).hexdigest()
def post(fn,body,hdrs,timeout=60):
    cmd=["curl","-s","-m",str(timeout),"-w","\n%{http_code}","-X","POST",f"{BASE}/{fn}"]
    for k,v in hdrs.items(): cmd+=["-H",f"{k}: {v}"]
    cmd+=["-d",body]; r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout+8)
    o=r.stdout.rsplit("\n",1); return int(o[-1].strip() or 0)

def main():
    anon=denv("SUPABASE_ANON_KEY")
    if not anon.startswith("eyJ"): print("  ! no anon key - edge up?"); return 2
    hive=sql("select id from hives order by created_at limit 1;")
    if not hive: print("  ! no hive"); return 2
    cfg=sql(f"insert into integration_configs (hive_id,system_type,label,auth_method,enabled,auth_token) values ('{hive}','sap_pm','ENTSYNC gate (transient)','hmac',true,'{SECRET}') returning id;")
    AST=f"ES-ASSET-{STAMP}"; PART=f"ES-PART-{STAMP}"; PM=f"ES-PM-{STAMP}"
    fails=[]
    def deliver(event,payload):
        body=json.dumps({"event":event,"cmms_type":"sap_pm","payload":payload})
        ts=str(int(time.time())); sig=hx(SECRET,f"{ts}.{body}")
        return post(f"cmms-webhook-receiver?config_id={cfg}",body,{"apikey":anon,"Content-Type":"application/json","X-WorkHive-Signature":f"sha256={sig}","X-WorkHive-Timestamp":ts})
    try:
        post(f"cmms-webhook-receiver?config_id={cfg}","{}",{"apikey":anon})  # warm
        c=deliver("asset.updated",{"EQUNR":AST,"EQKTX":"Feed Pump"})
        n=int(sql(f"select count(*) from external_sync where external_id='{AST}' and entity_type='asset' and hive_id='{hive}';") or 0)
        if not(c==200 and n==1): fails.append(f"asset.updated http={c} rows={n}")
        c=deliver("inventory.updated",{"MATNR":PART,"MENGE":50,"MINBE":10,"MAKTX":"Bearing 6204"})
        es=int(sql(f"select count(*) from external_sync where external_id='{PART}' and entity_type='inventory' and hive_id='{hive}';") or 0)
        iv=sql(f"select qty_on_hand from inventory_items where part_number='{PART}' and hive_id='{hive}';")
        if not(c==200 and es==1 and iv=="50"): fails.append(f"inventory.updated http={c} es={es} qty={iv}")
        deliver("inventory.updated",{"MATNR":PART,"MENGE":75,"MINBE":10,"MAKTX":"Bearing 6204"})
        ivn=int(sql(f"select count(*) from inventory_items where part_number='{PART}' and hive_id='{hive}';") or 0)
        ivq=sql(f"select qty_on_hand from inventory_items where part_number='{PART}' and hive_id='{hive}';")
        if not(ivn==1 and ivq=="75"): fails.append(f"inventory idempotency rows={ivn} qty={ivq} (want 1,75)")
        c=deliver("pm.overdue",{"AUFNR":PM,"EQUNR":AST})
        pmn=int(sql(f"select count(*) from external_sync where external_id='{PM}' and entity_type='pm_schedule' and hive_id='{hive}';") or 0)
        if not(c==200 and pmn==1): fails.append(f"pm.overdue http={c} rows={pmn}")
    finally:
        sql(f"delete from external_sync where hive_id='{hive}' and external_id in ('{AST}','{PART}','{PM}');")
        sql(f"delete from inventory_items where part_number='{PART}' and hive_id='{hive}';")
        sql(f"delete from integration_configs where id='{cfg}';")
    print("="*62)
    if fails:
        for f in fails: print(f"  [FAIL] {f}")
        print(f"  {len(fails)} entity-sync regression(s)"); return 1
    print("  [PASS] asset.updated + inventory.updated(+idempotent) + pm.overdue all land in DB")
    return 0
if __name__=="__main__": raise SystemExit(main())
