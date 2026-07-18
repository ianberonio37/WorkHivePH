#!/usr/bin/env python3
"""fb1_webhook_idempotency_live.py — Forward-Build FB1 (served-edge live round-trips).

Flips the F5 (at-least-once / idempotency) cells of the webhook receivers from
ATTRIBUTED (code-proof: validate_idempotency.py) -> LIVE by driving a REAL
duplicate-event round-trip against the SERVED edge functions and proving at the
DATA LAYER (docker exec psql) that a replayed event lands EXACTLY ONCE.

Cells flipped (backend_ufai_results.json, tier=attributed -> live):
  · cmms-webhook-receiver   F/F5  [E7 Integrations & Data Fabric]
  · marketplace-webhook     F/F5  [E6 Marketplace & Payments]   (when STRIPE_WEBHOOK_SECRET served)

Persona: the EXTERNAL SYSTEM (a CMMS / Stripe) delivering a webhook, then
re-delivering the SAME event (the at-least-once reality every webhook must survive).

Method per fn:
  1. Build the structure to make it live-able (seed a test integration_config w/ a
     known HMAC secret for cmms; detect the served STRIPE_WEBHOOK_SECRET for stripe).
  2. Forge a VALID signature, POST the event TWICE (and an UPDATE for cmms).
  3. postgres-verify the effect landed exactly once (idempotent).
  4. Clean up the test fixtures.

COST: $0 — no LLM, no external API (HMAC is local; cmms secret is DB-side; the
stripe path uses the LOCAL test webhook secret, never api.stripe.com).

USAGE: python tools/fb1_webhook_idempotency_live.py
Exit 0 = all probed cells idempotent-live; non-zero = a replay double-applied (real bug).
"""
from __future__ import annotations
import hashlib, hmac, json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "fb1_webhook_idempotency_live.json"
BASE = "http://127.0.0.1:54321/functions/v1"
HIVE = "9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7"
DB = "supabase_db_workhive"
EDGE = "supabase_edge_runtime_workhive"
STAMP = str(int(time.time()))
TEST_EXT_ID = f"FB1-LIVE-{STAMP}"        # unique -> isolated from real data
TEST_SECRET = f"fb1-test-secret-{STAMP}"  # known HMAC secret we control


def sql(q: str) -> str:
    r = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                        "-qtA", "-c", q], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr.strip()}")
    # -qtA suppresses the command tag; still strip any stray status line (e.g. "INSERT 0 1")
    lines = [ln for ln in r.stdout.strip().splitlines()
             if ln.strip() and not re.match(r"^(INSERT|UPDATE|DELETE|SELECT)\s+\d", ln.strip())]
    return lines[0].strip() if lines else ""


def docker_env(var: str) -> str:
    for c in (EDGE, "supabase_kong_workhive"):
        try:
            r = subprocess.run(["docker", "exec", c, "sh", "-c", f"printf '%s' \"${var}\""],
                               capture_output=True, text=True, timeout=20)
            if r.stdout.strip().startswith("eyJ"):
                return r.stdout.strip()
        except Exception:
            pass
    return ""


def post(fn: str, body: str, headers: dict[str, str], timeout=30):
    """POST raw body, return (http_code, response_text)."""
    cmd = ["curl", "-s", "-m", str(timeout), "-w", "\n%{http_code}", "-X", "POST", f"{BASE}/{fn}"]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    cmd += ["-d", body]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 8)
    out = r.stdout.rsplit("\n", 1)
    code = int(out[-1].strip() or 0)
    return code, (out[0] if len(out) > 1 else "")


def hmac_hex(secret: str, signed: str) -> str:
    return hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()


# ───────────────────────── cmms-webhook-receiver ─────────────────────────────
def probe_cmms(anon: str) -> dict:
    rec = {"fn": "cmms-webhook-receiver", "cell": "F5", "live": False, "steps": []}
    cfg_id = None
    try:
        # (1) build the structure: seed a test config with a known secret, enabled
        cfg_id = sql(
            "insert into integration_configs (hive_id, system_type, label, auth_method, "
            "enabled, auth_token) values ("
            f"'{HIVE}','generic','FB1 live-probe (transient)','hmac',true,'{TEST_SECRET}') "
            "returning id;")
        rec["config_id"] = cfg_id

        def deliver(event: str, status: str) -> tuple[int, str]:
            payload = {"work_order_no": TEST_EXT_ID, "asset_tag": "FB1-ASSET",
                       "status": status, "type": "Breakdown", "description": "FB1 idempotency probe",
                       "actual_hours": 2, "created_date": "2026-06-30T00:00:00Z"}
            body = json.dumps({"event": event, "cmms_type": "generic", "payload": payload})
            ts = STAMP
            sig = hmac_hex(TEST_SECRET, f"{ts}.{body}")
            hdrs = {"apikey": anon, "Content-Type": "application/json",
                    "X-WorkHive-Signature": f"sha256={sig}", "X-WorkHive-Timestamp": ts}
            return post(f"cmms-webhook-receiver?config_id={cfg_id}", body, hdrs)

        # warmup: the edge runtime compiles the fn on first hit (cold start) — prime it
        # so the timed deliveries below aren't measuring compile latency.
        post(f"cmms-webhook-receiver?config_id={cfg_id}", "{}", {"apikey": anon}, timeout=60)

        # (2) deliver work_order.created TWICE (at-least-once replay) + an UPDATE
        c1 = deliver("work_order.created", "Open")
        c2 = deliver("work_order.created", "Open")          # exact replay
        c3 = deliver("work_order.updated", "Closed")        # status change, same id
        rec["steps"] = [{"event": "created#1", "code": c1[0]}, {"event": "created#2(replay)", "code": c2[0]},
                        {"event": "updated", "code": c3[0]}]

        # (3) postgres-verify: external_sync EXACTLY ONE row; logbook EXACTLY ONE row
        es = int(sql(f"select count(*) from external_sync where external_id='{TEST_EXT_ID}' and hive_id='{HIVE}';") or 0)
        lb = int(sql(f"select count(*) from logbook where machine='FB1-ASSET' and hive_id='{HIVE}';") or 0)
        es_status = sql(f"select status from external_sync where external_id='{TEST_EXT_ID}' and hive_id='{HIVE}';")
        lb_status = sql(f"select status from logbook where machine='FB1-ASSET' and hive_id='{HIVE}';")
        rec["external_sync_rows"] = es
        rec["logbook_rows"] = lb
        rec["external_sync_status"] = es_status
        rec["logbook_status"] = lb_status
        all_ok = (c1[0] == 200 and c2[0] == 200 and c3[0] == 200)
        # F5 idempotency = at-least-once delivery collapses to an exactly-once effect:
        # 2 creates + 1 update of the same external_id -> EXACTLY ONE external_sync row
        # (onConflict upsert) AND EXACTLY ONE logbook row (new-work-order insert, deduped
        # on replay by the pre-upsert existence check). A replay must not duplicate either.
        idem_ok = (es == 1 and lb == 1)
        upsert_ok = (es_status == "Closed")           # the UPDATE flowed through the SAME row
        # F6 cross-surface: the work_order.updated(Closed) event must also flip the LINKED
        # logbook row's status to Closed (not leave it frozen at the created "Open").
        f6_ok = (lb_status == "Closed")
        rec["accepted_ok"] = all_ok
        rec["idempotent_ok"] = idem_ok
        rec["upsert_applied_ok"] = upsert_ok
        rec["logbook_status_synced_ok"] = f6_ok
        rec["live"] = bool(all_ok and idem_ok and upsert_ok and f6_ok)
    except Exception as e:
        rec["error"] = str(e)
    finally:
        # (4) cleanup the transient fixtures
        try:
            sql(f"delete from logbook where machine='FB1-ASSET' and hive_id='{HIVE}';")
            sql(f"delete from external_sync where external_id='{TEST_EXT_ID}' and hive_id='{HIVE}';")
            if cfg_id:
                sql(f"delete from integration_configs where id='{cfg_id}';")
            rec["cleaned_up"] = True
        except Exception as e:
            rec["cleanup_error"] = str(e)
    return rec


# ───────────────────────── marketplace-webhook ───────────────────────────────
def probe_marketplace(anon: str) -> dict:
    rec = {"fn": "marketplace-webhook", "cell": "F5", "live": False, "steps": []}
    # marketplace-webhook verifies a Stripe sig with STRIPE_WEBHOOK_SECRET (served env).
    # Detect whether the served fn has the secret; if absent, record the real attempt
    # (500 "Webhook secret not configured") so the cell stays attributed WITH a try on
    # record until the local test secret is served (build-the-structure, FB1 step 2).
    probe_body = json.dumps({"type": "checkout.session.completed", "data": {"object": {"id": "fb1-detect"}}})
    code, txt = post("marketplace-webhook", probe_body,
                     {"apikey": anon, "Content-Type": "application/json",
                      "stripe-signature": "t=1,v1=deadbeef"})
    rec["detect_code"] = code
    rec["detect_body"] = txt[:160]
    secret = (ROOT / ".stripe_webhook_test_secret").read_text().strip() \
        if (ROOT / ".stripe_webhook_test_secret").exists() else ""
    if code == 500 and "secret not configured" in txt.lower() and not secret:
        rec["status"] = "env-debt: STRIPE_WEBHOOK_SECRET not served — attempt-on-record"
        rec["attempt_on_record"] = True
        return rec
    if not secret:
        rec["status"] = "served secret present but local test secret unknown — cannot forge sig"
        rec["attempt_on_record"] = True
        return rec

    order_id = None
    try:
        sess = f"cs_fb1_{STAMP}"
        # seed a pending_payment order for a known session id
        listing = sql(f"select id from marketplace_listings where hive_id='{HIVE}' limit 1;")
        order_id = sql(
            "insert into marketplace_orders (hive_id, listing_id, buyer_name, price, status, stripe_session_id) "
            f"values ('{HIVE}', {('NULL' if not listing else chr(39)+listing+chr(39))}, 'FB1 Buyer', 100, "
            f"'pending_payment', '{sess}') returning id;")
        rec["order_id"] = order_id

        def deliver() -> tuple[int, str]:
            body = json.dumps({"type": "checkout.session.completed",
                               "data": {"object": {"id": sess, "payment_intent": f"pi_{STAMP}",
                                                    "amount_total": 10000}}})
            ts = STAMP
            sig = hmac_hex(secret, f"{ts}.{body}")
            return post("marketplace-webhook", body,
                        {"apikey": anon, "Content-Type": "application/json",
                         "stripe-signature": f"t={ts},v1={sig}"})

        w1 = deliver()
        w2 = deliver()    # exact replay
        rec["steps"] = [{"deliver": 1, "code": w1[0]}, {"deliver": 2, "code": w2[0]}]
        status = sql(f"select status from marketplace_orders where id='{order_id}';")
        transitions = int(sql(
            f"select count(*) from marketplace_orders where id='{order_id}' and status='escrow_hold';") or 0)
        rec["order_status"] = status
        rec["idempotent_ok"] = (status == "escrow_hold" and transitions == 1)
        rec["accepted_ok"] = (w1[0] == 200 and w2[0] == 200)
        rec["live"] = bool(rec["idempotent_ok"] and rec["accepted_ok"])
    except Exception as e:
        rec["error"] = str(e)
    finally:
        try:
            if order_id:
                sql(f"delete from marketplace_orders where id='{order_id}';")
            rec["cleaned_up"] = True
        except Exception as e:
            rec["cleanup_error"] = str(e)
    return rec


def main() -> int:
    # NOTE: the marketplace-webhook F5 cell was REMOVED 2026-06-30 (Stripe deleted
    # entirely — the marketplace is free + contact-only). The only surviving webhook
    # F5 idempotency cell is cmms-webhook-receiver.
    anon = docker_env("SUPABASE_ANON_KEY")
    if not anon:
        print("  ! could not obtain anon key — is the edge up?"); return 2
    # Resolve a REAL hive at runtime. The canonical test-hive UUID drifts on every reseed
    # (Supabase regenerates hive UUIDs), so a hardcoded constant FK-errors the seeded-config
    # insert and the gate silently stops exercising the webhook. Pick an existing hive so the
    # gate is reseed-resilient.
    global HIVE
    _h = sql("select id from hives order by created_at limit 1;")
    if _h:
        HIVE = _h
    results = [probe_cmms(anon)]
    out = {"stamp": STAMP, "results": results}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("=" * 68)
    live = 0
    for r in results:
        flag = "LIVE" if r.get("live") else ("attempt-on-record" if r.get("attempt_on_record") else "NOT-LIVE")
        live += bool(r.get("live"))
        extra = f"external_sync={r.get('external_sync_rows')} logbook={r.get('logbook_rows')} status={r.get('external_sync_status')}"
        print(f"  {r['fn']:26s} {r['cell']}  {flag:18s} {extra}")
        if r.get("error"):
            print(f"      error: {r['error']}")
    print("-" * 68)
    print(f"  {live}/1 webhook F5 cell proven idempotent-LIVE  ·  wrote {OUT.name}")
    bug = any((not r.get("live") and not r.get("attempt_on_record")) for r in results)
    return 1 if bug else 0


if __name__ == "__main__":
    raise SystemExit(main())
