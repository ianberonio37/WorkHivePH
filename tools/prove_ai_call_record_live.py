"""
prove_ai_call_record_live.py - LIVE proof that a model call which ANSWERS leaves one ai_cost_log row carrying the
trace id the reply returned (LM-O, LM544, 2026-10-08). Local stack only; spends free-tier model calls, so it is NOT a
registered gate - run it deliberately.

  A  ai-gateway's auth-gated LOCAL fault probe (context.debug_fault_inject = {} : no simulated failure) - one tiny
     callAI ("Reply with the single word OK.", 16 tokens), no specialist forward, solo caller (no hive)
  B  analytics-orchestrator phase=prescriptive for the test user's hive - the exact LM544 path (alert-hub's ask):
     one synthesis callAI, plus one repair call only if the first answer fails its contract
  C  marketplace-listing-assist (solo, text path) - a function that ALSO calls logAICost after its callAI: proves
     the annotation path, i.e. still exactly ONE row for the call, carrying the real served model (not the
     function's hand-typed "chain") and the schema_compliance its logAICost decided

Hard cap: at most MAX_MODEL_REQUESTS model-invoking requests (each may spend at most 2 calls), checked BEFORE each
send. Every row the run creates is reversed at the end: its ai_cost_log + wh_traces rows (by trace id), the counter
increments it caused (ai_user_rate_limits / ai_rate_limits / hive_route_calls / ai_global_budget - decremented by
exactly this run's delta, never reset, so a concurrent walk's counts survive), the analytics_snapshots row the
prescriptive call overwrote (restored to its pre-image), and the auth session the sign-in minted.
Test account: leandromarquez@auth.workhiveph.com (never the ianphone account).

    python tools/prove_ai_call_record_live.py            # A + B
    python tools/prove_ai_call_record_live.py --only A   # just the gateway probe
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:54321"
EMAIL = "leandromarquez@auth.workhiveph.com"
PASSWORD = "test1234"
DB = "supabase_db_workhive"
EDGE = "supabase_edge_runtime_workhive"
MAX_MODEL_REQUESTS = 3          # per run; A (1 call) + B (<= 2 calls) + C (1 call); the task's ceiling is 6 calls
# the window each counter counts in (a counter whose window rolled over mid-run restarted at this run's calls)
WINDOW_OF = {"call_count": "window_start", "day_count": "day_window_start", "minute_count": "minute_window_start"}
_model_requests = 0


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1",
                        "-At", "-c", sql], capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr.strip()[:400]}")
    return r.stdout.strip()


def q(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def docker_env(name: str) -> str:
    r = subprocess.run(["docker", "exec", EDGE, "printenv", name], capture_output=True, text=True, timeout=20)
    return r.stdout.strip()


def curl(method: str, url: str, headers: dict, body: dict | None, timeout: int = 90) -> tuple[int, dict, dict]:
    args = ["curl", "-s", "-m", str(timeout), "-X", method, url, "-D", "-"]
    for k, v in headers.items():
        args += ["-H", f"{k}: {v}"]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=timeout + 10)
    raw = r.stdout.replace("\r\n", "\n")   # text mode on Windows already folds CRLF; normalise either way
    head, _, text = raw.partition("\n\n")
    while text.startswith("HTTP/"):          # a 100-continue preamble
        head, _, text = text.partition("\n\n")
    lines = head.split("\n")
    status = int(lines[0].split()[1]) if lines and lines[0].startswith("HTTP/") else 0
    hdrs = {}
    for l in lines[1:]:
        if ":" in l:
            k, v = l.split(":", 1)
            hdrs[k.strip().lower()] = v.strip()
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        data = {"_raw": text[:300]}
    return status, hdrs, data


def model_request(label: str):
    global _model_requests
    if _model_requests >= MAX_MODEL_REQUESTS:
        raise SystemExit(f"CAP: refusing {label} - {MAX_MODEL_REQUESTS} model-invoking requests already sent")
    _model_requests += 1
    print(f"  [model request {_model_requests}/{MAX_MODEL_REQUESTS}] {label}")


def jwt_claims(tok: str) -> dict:
    p = tok.split(".")[1]
    p += "=" * (-len(p) % 4)
    return json.loads(base64.urlsafe_b64decode(p))


def row(sql: str) -> dict | None:
    out = psql(f"select coalesce((select row_to_json(t)::text from ({sql}) t limit 1), '')")
    return json.loads(out) if out else None


def records(trace_id: str) -> list[dict]:
    out = psql("select coalesce(json_agg(r order by r.created_at)::text, '[]') from (select fn, trace_id, auth_uid, "
               "hive_id, worker_name, provider, model, prompt_tokens, output_tokens, tokens_estimated, latency_ms, "
               f"status, created_at from public.ai_cost_log where trace_id = {q(trace_id)}) r")
    return json.loads(out)


def wait_records(trace_id: str, want_min: int = 1, secs: float = 15.0) -> list[dict]:
    t_end = time.time() + secs
    got: list[dict] = []
    while time.time() < t_end:
        got = records(trace_id)
        if len(got) >= want_min:
            time.sleep(1.0)            # a second call of the same request may land a moment later
            return records(trace_id)
        time.sleep(0.5)
    return got


def main() -> int:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else "ABC"
    anon = docker_env("SUPABASE_ANON_KEY")
    if not anon:
        print("SKIP: the local edge runtime is not up")
        return 0
    t0_db = psql("select now()")
    t0_wall = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # sign in (the session, its audit row and the last_sign_in_at bump it causes are all reversed at the end)
    pre_sign_in = psql(f"select coalesce(last_sign_in_at::text, '') from auth.users where email = {q(EMAIL)}")
    t_si0 = psql("select now()")
    st, _, tokj = curl("POST", f"{BASE}/auth/v1/token?grant_type=password", {"apikey": anon},
                       {"email": EMAIL, "password": PASSWORD}, timeout=20)
    t_si1 = psql("select now()")
    tok = tokj.get("access_token", "")
    if st != 200 or not tok:
        print(f"FAIL: sign-in {st} {str(tokj)[:200]}")
        return 1
    claims = jwt_claims(tok)
    uid, session_id = claims["sub"], claims.get("session_id")
    hive = psql(f"select hive_id from public.hive_members where auth_uid = {q(uid)} and status = 'active' "
                "order by joined_at nulls last limit 1") if "B" in only else ""
    print(f"user {uid} (session {session_id}); hive for B: {hive or '-'}")

    # pre-images of everything the two requests can touch
    hour = psql("select date_trunc('hour', now())")
    pre = {
        "user_rl": row(f"select * from public.ai_user_rate_limits where user_id = {q(uid)}"),
        "hive_rl": row(f"select * from public.ai_rate_limits where hive_id = {q(hive)}") if hive else None,
        "route": row(f"select * from public.hive_route_calls where hive_id = {q(hive)} and route = 'analytics-orchestrator' "
                     f"and hour_bucket = {q(hour)}") if hive else None,
        "global": row("select * from public.ai_global_budget where id = 'global'"),
        "snapshot": row(f"select * from public.analytics_snapshots where hive_id = {q(hive)} and phase = 'prescriptive' "
                        f"and period_days = 90") if hive else None,
    }
    auth_h = {"Authorization": f"Bearer {tok}", "apikey": anon}
    traces: list[str] = []
    results = []

    if "A" in only:
        model_request("A ai-gateway local fault probe (no simulated failure)")
        st, h, body = curl("POST", f"{BASE}/functions/v1/ai-gateway", auth_h,
                           {"agent": "report-voice", "message": "LM-O record probe",
                            "context": {"debug_fault_inject": {}}})
        tid = body.get("trace_id") or h.get("x-wh-trace") or ""
        recs = wait_records(tid) if tid else []
        print(f"A  HTTP {st}  reply trace_id={tid}  header x-wh-trace={h.get('x-wh-trace')}  "
              f"answer_landed={((body.get('data') or {}).get('debug_fault') or {}).get('answer_landed')}")
        for r in recs:
            print(f"   ai_cost_log: fn={r['fn']} trace_id={r['trace_id']} auth_uid={r['auth_uid']} hive_id={r['hive_id']} "
                  f"provider={r['provider']} model={r['model']} tokens={r['prompt_tokens']}/{r['output_tokens']} "
                  f"(estimated={r['tokens_estimated']}) latency_ms={r['latency_ms']} status={r['status']}")
        ok = bool(tid) and len(recs) == 1 and recs[0]["trace_id"] == tid and recs[0]["fn"] == "ai-gateway" \
            and recs[0]["auth_uid"] == uid
        results.append(("A", ok, st, tid, len(recs)))
        if tid:
            traces.append(tid)

    if "B" in only and hive:
        model_request("B analytics-orchestrator phase=prescriptive (the LM544 path)")
        st, h, body = curl("POST", f"{BASE}/functions/v1/analytics-orchestrator", auth_h,
                           {"phase": "prescriptive", "hive_id": hive, "horizon": "today"}, timeout=150)
        tid = body.get("trace_id") or h.get("x-wh-trace") or ""
        recs = wait_records(tid) if tid else []
        has_plan = bool(body.get("action_plan")) or bool(body.get("answer"))
        print(f"B  HTTP {st}  reply trace_id={tid}  header x-wh-trace={h.get('x-wh-trace')}  synthesis_in_reply={has_plan}")
        for r in recs:
            print(f"   ai_cost_log: fn={r['fn']} trace_id={r['trace_id']} auth_uid={r['auth_uid']} hive_id={r['hive_id']} "
                  f"provider={r['provider']} model={r['model']} tokens={r['prompt_tokens']}/{r['output_tokens']} "
                  f"(estimated={r['tokens_estimated']}) latency_ms={r['latency_ms']} status={r['status']}")
        ok = bool(tid) and 1 <= len(recs) <= 2 and all(r["trace_id"] == tid and r["fn"] == "analytics-orchestrator"
                                                       and r["hive_id"] == hive and r["auth_uid"] == uid for r in recs)
        results.append(("B", ok, st, tid, len(recs)))
        if tid:
            traces.append(tid)

    if "C" in only:
        model_request("C marketplace-listing-assist (solo text path; the function also calls logAICost)")
        st, h, body = curl("POST", f"{BASE}/functions/v1/marketplace-listing-assist", auth_h,
                           {"section": "parts", "title": "SKF 6205-2RS deep groove ball bearing", "condition": "new"})
        tid = body.get("trace_id") or h.get("x-wh-trace") or ""
        recs = wait_records(tid) if tid else []
        full = json.loads(psql("select coalesce(json_agg(r)::text, '[]') from (select model, provider, status, "
                               f"schema_compliance from public.ai_cost_log where trace_id = {q(tid)}) r")) if tid else []
        print(f"C  HTTP {st}  reply trace_id={tid}  header x-wh-trace={h.get('x-wh-trace')}  "
              f"category={body.get('category')!r}")
        for r, f in zip(recs, full):
            print(f"   ai_cost_log: fn={r['fn']} trace_id={r['trace_id']} auth_uid={r['auth_uid']} hive_id={r['hive_id']} "
                  f"provider={r['provider']} model={r['model']} tokens={r['prompt_tokens']}/{r['output_tokens']} "
                  f"latency_ms={r['latency_ms']} status={r['status']} schema_compliance={f['schema_compliance']}")
        ok = bool(tid) and len(recs) == 1 and recs[0]["fn"] == "marketplace-listing-assist" \
            and recs[0]["model"] not in ("chain", "multimodal") and full and full[0]["schema_compliance"] is not None
        results.append(("C", ok, st, tid, len(recs)))
        if tid:
            traces.append(tid)

    # provider attempts the chain logged in this window (served + refused), for the call budget
    logs = subprocess.run(["docker", "logs", "--since", t0_wall, EDGE], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout + \
        subprocess.run(["docker", "logs", "--since", t0_wall, EDGE], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    chain = [l for l in logs.splitlines() if "[ai-chain" in l]
    served = [l for l in chain if "served by" in l]
    print(f"chain log lines since start: {len(chain)} ({len(served)} served, {len(chain) - len(served)} skipped/refused) "
          f"- includes any concurrent caller")
    for l in chain[:12]:
        print("   " + l.strip()[:200])

    # ── reverse everything this run created ──────────────────────────────────────────────────────────────────────
    print("reversal:")
    n_req_a = 1 if "A" in only else 0
    n_req_b = 1 if ("B" in only and hive) else 0
    for tid in traces:
        print(f"   ai_cost_log rows deleted for {tid}: "
              + psql(f"with d as (delete from public.ai_cost_log where trace_id = {q(tid)} returning 1) select count(*) from d"))
        print(f"   wh_traces rows deleted for {tid}: "
              + psql(f"with d as (delete from public.wh_traces where trace_id = {q(tid)} returning 1) select count(*) from d"))

    def undo_counter(table: str, where: str, pre_row: dict | None, n: int, cols: tuple[str, ...]):
        if n == 0:
            return
        now_row = row(f"select * from public.{table} where {where}")
        if now_row is None:
            print(f"   {table}: no row now - nothing to undo")
            return
        if pre_row is None:
            # the run created the row: delete it if every counter equals what this run alone would have made
            if all((now_row.get(c) or 0) <= n for c in cols):
                psql(f"delete from public.{table} where {where}")
                print(f"   {table}: row created by this run deleted")
            else:
                sets = ", ".join(f"{c} = greatest(0, {c} - {n})" for c in cols)
                psql(f"update public.{table} set {sets} where {where}")
                print(f"   {table}: row shared with a concurrent caller - decremented by {n}")
            return
        # a counter whose window rolled over during the run restarted at this run's calls: the new window holds them
        # (decrement it); a counter in the same window rose by them (decrement it). Never reset - a concurrent
        # caller's counts in either window survive.
        sets = []
        for c in cols:
            win = WINDOW_OF.get(c)
            rolled = bool(win) and now_row.get(win) != pre_row.get(win)
            rose = (now_row.get(c) or 0) >= (pre_row.get(c) or 0) + n
            if rose or (rolled and (now_row.get(c) or 0) >= n):
                sets.append(f"{c} = greatest(0, {c} - {n})")
        if sets:
            psql(f"update public.{table} set {', '.join(sets)} where {where}")
        print(f"   {table}: before={ {c: pre_row.get(c) for c in cols} } after-run={ {c: now_row.get(c) for c in cols} } "
              f"-> decremented by {n} ({', '.join(sets) or 'nothing of this run left to undo'})")

    # C (marketplace with no hive_id) is limited on the person's own bucket since 2026-10-08 - it used to write the
    # auth uid into ai_rate_limits.hive_id, a write the hive foreign key refused, so there was nothing to undo there
    undo_counter("ai_user_rate_limits", f"user_id = {q(uid)}", pre["user_rl"], n_req_a + (1 if "C" in only else 0),
                 ("call_count", "day_count"))
    if hive:
        undo_counter("ai_rate_limits", f"hive_id = {q(hive)}", pre["hive_rl"], n_req_b, ("call_count", "day_count"))
        undo_counter("hive_route_calls", f"hive_id = {q(hive)} and route = 'analytics-orchestrator' and hour_bucket = {q(hour)}",
                     pre["route"], n_req_b, ("call_count",))
    undo_counter("ai_global_budget", "id = 'global'", pre["global"], n_req_a, ("minute_count", "day_count"))
    if hive and n_req_b:
        snap = pre["snapshot"]
        if snap is None:
            print("   analytics_snapshots: rows created by this run deleted: " + psql(
                f"with d as (delete from public.analytics_snapshots where hive_id = {q(hive)} and phase = 'prescriptive' "
                f"and period_days = 90 and computed_at >= {q(t0_db)} returning 1) select count(*) from d"))
        else:
            psql("update public.analytics_snapshots s set payload = p.payload, computed_at = p.computed_at, "
                 "computed_by = p.computed_by from json_populate_record(null::public.analytics_snapshots, "
                 f"{q(json.dumps(snap))}::json) p where s.id = p.id")
            print(f"   analytics_snapshots: prescriptive row restored to its pre-image (computed_at {snap['computed_at']})")
    if session_id:
        print("   auth session deleted: " + psql(
            f"with d as (delete from auth.sessions where id = {q(session_id)} returning 1) select count(*) from d"))
    print("   auth login audit rows deleted: " + psql(
        f"with d as (delete from auth.audit_log_entries where payload->>'actor_id' = {q(uid)} and payload->>'action' = 'login' "
        f"and created_at between {q(t_si0)} and {q(t_si1)} returning 1) select count(*) from d"))
    if pre_sign_in:
        print("   auth.users.last_sign_in_at restored: " + psql(
            f"with u as (update auth.users set last_sign_in_at = {q(pre_sign_in)} where id = {q(uid)} "
            f"and last_sign_in_at between {q(t_si0)} and {q(t_si1)} returning 1) select count(*) from u"))

    # anything else this user/hive gained since the start (review list, nothing deleted blindly)
    notes = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-c",
                            f"""do $$ declare r record; n int; begin
        for r in select c.table_name, string_agg(c.column_name, ',') cols from information_schema.columns c
                 join information_schema.columns k on k.table_schema = c.table_schema and k.table_name = c.table_name
                   and k.column_name = 'created_at'
                 join information_schema.tables t on t.table_schema = c.table_schema and t.table_name = c.table_name
                   and t.table_type = 'BASE TABLE'
                 where c.table_schema = 'public' and c.column_name in ('auth_uid','user_id','hive_id')
                 group by c.table_name loop
          execute format('select count(*) from public.%I where created_at >= %L and (%s)', r.table_name, {q(t0_db)},
            (select string_agg(format('%I::text in (%L, %L)', x, {q(uid)}, {q(hive or uid)}), ' or ')
               from unnest(string_to_array(r.cols, ',')) x)) into n;
          if n > 0 then raise notice 'LEFT % %', r.table_name, n; end if;
        end loop; end $$;"""], capture_output=True, text=True, encoding="utf-8")
    left = [l for l in notes.stderr.splitlines() if "LEFT" in l]
    print("   rows still dated after the start for this user/hive: " + (", ".join(l.split("LEFT", 1)[1].strip() for l in left) or "none"))
    for tid in traces:
        rest = psql(f"select (select count(*) from public.ai_cost_log where trace_id = {q(tid)}) + "
                    f"(select count(*) from public.wh_traces where trace_id = {q(tid)})")
        print(f"   rows left carrying {tid}: {rest}")

    print("result:")
    bad = 0
    for label, ok, st, tid, n in results:
        print(f"   {label}: {'PASS' if ok else 'FAIL'} (HTTP {st}, trace {tid}, {n} record(s))")
        bad += 0 if ok else 1
    print(f"model-invoking requests sent: {_model_requests} (cap {MAX_MODEL_REQUESTS})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
