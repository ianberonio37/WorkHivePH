"""
prove_ai_call_record_followups_live.py - LIVE proof of the LM-O follow-ups (2026-10-08) against the local stack.
Can spend free-tier model calls, so it is NOT a registered gate - run it deliberately, after the edge runtime has
loaded the current source.

  X  ai-gateway's auth-gated LOCAL fault probe with failAll: the chain walks every slot, each one fault-injected (no
     network call), and degrades to "{}". Item 2: exactly ONE generation row, status failed, provider chain, model
     exhausted, providers_tried naming every slot (=fault-inject), the reply's trace id.
  E  semantic-search for the test user's hive: one query embedding on the self-hosted embed-server (bge-local, not a
     free-tier provider). Item 3: a kind=embedding row - provider bge-local, its model, latency, the reply's trace id.
  L  marketplace-listing-assist with NO hive_id (the hive-less path) while the person's bucket is AT its daily cap.
     Item 1: refused 429 by the per-person limiter BEFORE any model call - no ai_cost_log row, bucket not advanced.
  T  voice-transcribe with a 2.6 s synthesized WAV and no language (the 2-model multilingual Whisper chain; no
     self-hosted ASR is running, so Groq serves). Item 3: a kind=transcription row with audio_seconds.
  H  the same person's listing request WITH their hive_id while that bucket is still full: served by the hive limiter
     (a different bucket). Sent only if its WORST case fits the budget - a callAI walk can ask every chain entry on
     each of two passes, so the harness normally refuses it and says so; the hive-member half of item 1 is then
     carried by tools/psql_probes/marketplace__hiveless_person_is_counted.sql.

THE BUDGET (enforced here, before every send): at most 4 free-tier provider calls in total. X, E and L can spend none
by construction (fault-injected slots, the self-hosted embedder, a refusal before the chain). A request that can reach
a free-tier provider is sent only if the calls already spent (counted from the records' providers_tried, which name
every slot asked) plus its worst case stays <= 4.

Every row the run creates is reversed: ai_cost_log + wh_traces rows (by trace id); every counter it moved -
ai_user_rate_limits (the person's bucket and the ip: ceiling buckets), ai_rate_limits[hive], hive_route_calls,
ai_global_budget - put back by exactly this run's delta (a concurrent caller's counts survive); the person's bucket,
which L seeds to its cap, restored to its pre-image plus anything a concurrent caller added meanwhile; embedding_cache
rows the run created; the auth session, its login audit row and last_sign_in_at.
Test account: leandromarquez@auth.workhiveph.com (never the ianphone account).

    python tools/prove_ai_call_record_followups_live.py --wav probe.wav [--only XELTH]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prove_ai_call_record_live as P  # noqa: E402  (psql, q, curl, docker_env, jwt_claims, row)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE, EMAIL, PASSWORD, DB, EDGE = P.BASE, P.EMAIL, P.PASSWORD, P.DB, P.EDGE
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_PROVIDER_CALLS = 4
psql, q, row = P.psql, P.q, P.row

_spent = 0          # free-tier provider calls this run has made (from the records' providers_tried)
_SENT: dict = {"traces": [], "moves": []}   # what an abort must still reverse


def budget_before(label: str, worst_case: int) -> bool:
    if _spent + worst_case > MAX_PROVIDER_CALLS:
        print(f"  BUDGET: NOT sending {label} - {_spent} spent + worst case {worst_case} > {MAX_PROVIDER_CALLS}")
        return False
    print(f"  [budget] sending {label}: {_spent} spent, worst case +{worst_case} (cap {MAX_PROVIDER_CALLS})")
    return True


def chain_worst_case() -> int:
    """Every PROVIDER_CHAIN entry, asked on each of callAI's two passes."""
    src = open(os.path.join(ROOT, "supabase", "functions", "_shared", "ai-chain.ts"), encoding="utf-8").read()
    m = re.search(r"const PROVIDER_CHAIN[^=]*=\s*\[([\s\S]+?)\];", src)
    return 2 * len(re.findall(r"\bprovider\s*:", m.group(1))) if m else 99


def recs(tid: str) -> list[dict]:
    out = psql("select coalesce(json_agg(r order by r.created_at)::text, '[]') from (select fn, kind, trace_id, auth_uid, "
               "hive_id, provider, model, prompt_tokens, output_tokens, tokens_estimated, latency_ms, status, "
               f"providers_tried, audio_seconds, late, created_at from public.ai_cost_log where trace_id = {q(tid)}) r")
    return json.loads(out)


def wait_recs(tid: str, want: int = 1, secs: float = 12.0) -> list[dict]:
    end = time.time() + secs
    got: list[dict] = []
    while time.time() < end:
        got = recs(tid)
        if len(got) >= want:
            time.sleep(1.5)
            return recs(tid)
        time.sleep(0.5)
    return got


def show(rs: list[dict]) -> None:
    for r in rs:
        print(f"     ai_cost_log: fn={r['fn']} kind={r['kind']} provider={r['provider']} model={r['model']} "
              f"status={r['status']} late={r['late']} tokens={r['prompt_tokens']}/{r['output_tokens']} "
              f"(est={r['tokens_estimated']}) latency_ms={r['latency_ms']} audio_s={r['audio_seconds']} "
              f"tried={r['providers_tried']} trace={r['trace_id']} auth_uid={r['auth_uid']} hive={r['hive_id']}")


def provider_calls(rs: list[dict]) -> int:
    """Free-tier provider requests the records say were made: every providers_tried entry that reached a provider (a
    fault-injected slot made no request; the self-hosted embed / ASR / LLM servers are not free-tier providers)."""
    n = 0
    for r in rs:
        for t in (r.get("providers_tried") or []):
            if t.endswith("=fault-inject") or t.startswith(("bge-local/", "asr-local/", "wh-llm-local/")):
                continue
            n += 1
    return n


def bucket(key: str) -> dict | None:
    return row(f"select call_count, window_start, day_count, day_window_start from public.ai_user_rate_limits "
               f"where user_id = {q(key)}")


def ip_buckets() -> dict:
    return {r["user_id"]: r for r in json.loads(psql(
        "select coalesce(json_agg(t)::text, '[]') from (select user_id, call_count, day_count from "
        "public.ai_user_rate_limits where user_id like 'ip:%') t"))}


def curl_multipart(url: str, tok: str, anon: str, wav: str) -> tuple[int, dict, dict]:
    args = ["curl", "-s", "-m", "90", "-D", "-", "-X", "POST", url, "-H", f"Authorization: Bearer {tok}",
            "-H", f"apikey: {anon}", "-F", f"audio=@{wav};type=audio/wav;filename=probe.wav"]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
    raw = r.stdout.replace("\r\n", "\n")
    head, _, text = raw.partition("\n\n")
    while text.startswith("HTTP/"):
        head, _, text = text.partition("\n\n")
    st = int(head.split()[1]) if head.startswith("HTTP/") else 0
    hdr = {l.split(":", 1)[0].strip().lower(): l.split(":", 1)[1].strip() for l in head.split("\n")[1:] if ":" in l}
    try:
        body = json.loads(text)
    except ValueError:
        body = {"_raw": text[:200]}
    return st, hdr, body


def main() -> int:
    global _spent
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else "XELTH"
    wav = sys.argv[sys.argv.index("--wav") + 1] if "--wav" in sys.argv else ""
    anon = P.docker_env("SUPABASE_ANON_KEY")
    if not anon:
        print("SKIP: the local edge runtime is not up")
        return 0
    t0_db = psql("select now()")
    t0_wall = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    pre_sign_in = psql(f"select coalesce(last_sign_in_at::text, '') from auth.users where email = {q(EMAIL)}")
    t_si0 = psql("select now()")
    st, _, tokj = P.curl("POST", f"{BASE}/auth/v1/token?grant_type=password", {"apikey": anon},
                         {"email": EMAIL, "password": PASSWORD}, timeout=20)
    t_si1 = psql("select now()")
    tok = tokj.get("access_token", "")
    if st != 200 or not tok:
        print(f"FAIL: sign-in {st} {str(tokj)[:200]}")
        return 1
    claims = P.jwt_claims(tok)
    uid, session_id = claims["sub"], claims.get("session_id")

    def undo_sign_in() -> None:
        if session_id:
            print("   auth session deleted: " + psql(
                f"with d as (delete from auth.sessions where id = {q(session_id)} returning 1) select count(*) from d"))
        print("   auth login audit rows deleted: " + psql(
            f"with d as (delete from auth.audit_log_entries where payload->>'actor_id' = {q(uid)} "
            f"and payload->>'action' = 'login' and created_at between {q(t_si0)} and {q(t_si1)} returning 1) "
            "select count(*) from d"))
        if pre_sign_in:
            print("   auth.users.last_sign_in_at restored: " + psql(
                f"with u as (update auth.users set last_sign_in_at = {q(pre_sign_in)} where id = {q(uid)} "
                f"and last_sign_in_at between {q(t_si0)} and {q(t_si1)} returning 1) select count(*) from u"))

    try:
        return _run(uid, tok, anon, t0_db, t0_wall, undo_sign_in)
    except BaseException:
        print("ABORTED - reversing what was sent, then the sign-in, before re-raising")
        for tid in _SENT["traces"]:
            print(f"   rows deleted for {tid}: " + psql(
                f"with a as (delete from public.ai_cost_log where trace_id = {q(tid)} returning 1), "
                f"w as (delete from public.wh_traces where trace_id = {q(tid)} returning 1) "
                "select (select count(*) from a) + (select count(*) from w)"))
        if _SENT["traces"]:
            print("   COUNTERS NOT REVERSED by the abort path - undo by hand: " + json.dumps(_SENT["moves"]))
        undo_sign_in()
        raise


def _run(uid: str, tok: str, anon: str, t0_db: str, t0_wall: str, undo_sign_in) -> int:
    global _spent
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else "XELTH"
    wav = sys.argv[sys.argv.index("--wav") + 1] if "--wav" in sys.argv else ""
    hive = psql(f"select hive_id from public.hive_members where auth_uid = {q(uid)} and status = 'active' "
                "order by joined_at nulls last limit 1")
    hour = psql("select date_trunc('hour', now())")
    rl_hour = int(P.docker_env("WH_RATE_LIMIT_OVERRIDE") or 50)
    rl_day = int(P.docker_env("WH_RATE_LIMIT_PER_DAY_OVERRIDE") or 300)
    print(f"user {uid}; hive {hive}; marketplace budget {rl_hour}/h, {rl_day}/day")
    pre_user = bucket(uid)
    pre_ip = ip_buckets()
    pre_hive = row(f"select call_count, day_count from public.ai_rate_limits where hive_id = {q(hive)}")
    pre_route = row(f"select call_count from public.hive_route_calls where hive_id = {q(hive)} "
                    f"and route = 'marketplace-listing-assist' and hour_bucket = {q(hour)}")
    pre_global = row("select minute_count, minute_window_start, day_count, day_window_start from public.ai_global_budget "
                     "where id = 'global'")
    pre_cache = set(psql("select coalesce(string_agg(query_hash || '|' || model, ','), '') from public.embedding_cache")
                    .split(",")) - {""}
    auth_h = {"Authorization": f"Bearer {tok}", "apikey": anon}
    traces: list[str] = _SENT["traces"]   # shared with main()'s abort path
    results: list[tuple[str, bool, str]] = []
    own_user = 0         # this run's increments of the person's bucket
    own_ip = 0           # ... of the ip: ceiling bucket
    own_hive = own_route = own_global = 0
    seeded = None

    # ── X: an exhausted walk is ONE failed row (item 2) ─────────────────────────────────────────────────────────────
    if "X" in only:
        print("X  ai-gateway fault probe, failAll (every slot fault-injected; no provider request)")
        st, h, body = P.curl("POST", f"{BASE}/functions/v1/ai-gateway", auth_h,
                             {"agent": "report-voice", "message": "LM-O exhausted walk probe",
                              "context": {"debug_fault_inject": {"failAll": True}}})
        tid = body.get("trace_id") or h.get("x-wh-trace") or ""
        if tid:
            traces.append(tid)
        _SENT["moves"].append("X: person bucket +1, ai_global_budget +1")
        rs = wait_recs(tid) if tid else []
        gen = [r for r in rs if r["kind"] == "generation"]
        print(f"   HTTP {st} trace={tid} debug_fault={(body.get('data') or {}).get('debug_fault')}")
        show(rs)
        ok = (st == 200 and len(gen) == 1 and gen[0]["status"] == "failed" and gen[0]["provider"] == "chain"
              and gen[0]["model"] == "exhausted" and gen[0]["trace_id"] == tid and gen[0]["auth_uid"] == uid
              and bool(gen[0]["providers_tried"]) and all(t.endswith("=fault-inject") for t in gen[0]["providers_tried"])
              and gen[0]["prompt_tokens"] is None and gen[0]["latency_ms"] is not None)
        _spent += provider_calls(rs)
        results.append(("X exhausted walk = exactly one failed generation row", ok, tid))
        if st not in (429, 401, 403):
            own_user += 1
            own_global += 1

    # ── E: an embedding is recorded (item 3) ──────────────────────────────────────────────────────────────────────
    if "E" in only:
        print("E  semantic-search (query embedding on the self-hosted embed-server)")
        st, h, body = P.curl("POST", f"{BASE}/functions/v1/semantic-search", auth_h,
                             {"query": "bearing overheating on pump 2", "hive_id": hive, "sources": ["fault"],
                              "match_count": 1})
        tid = body.get("trace_id") or h.get("x-wh-trace") or ""
        if tid:
            traces.append(tid)
        rs = wait_recs(tid) if tid else []
        emb = [r for r in rs if r["kind"] == "embedding"]
        print(f"   HTTP {st} trace={tid}")
        show(rs)
        ok = (st == 200 and len(emb) == 1 and emb[0]["status"] == "success" and emb[0]["provider"] == "bge-local"
              and emb[0]["model"] == "bge-small-en-v1.5" and emb[0]["trace_id"] == tid and emb[0]["output_tokens"] is None
              and emb[0]["latency_ms"] is not None and emb[0]["auth_uid"] == uid)
        _spent += provider_calls(rs)
        results.append(("E embedding recorded (kind embedding)", ok, tid))
        if st == 200:
            own_user += 1
            own_ip += 1

    # ── L: the hive-less path refuses at the cap, before any model call (item 1) ─────────────────────────────────
    if "L" in only:
        print(f"L  marketplace-listing-assist, NO hive_id, the person's bucket seeded to its daily cap ({rl_day})")
        cur = bucket(uid)
        psql("insert into public.ai_user_rate_limits (user_id, hive_id, call_count, window_start, day_count, day_window_start) "
             f"values ({q(uid)}, null, {rl_hour}, now(), {rl_day}, now()) on conflict (user_id) do update set "
             f"call_count = {rl_hour}, window_start = now(), day_count = {rl_day}, day_window_start = now()")
        seeded = {"before": cur, "set": {"call_count": rl_hour, "day_count": rl_day}}
        st, h, body = P.curl("POST", f"{BASE}/functions/v1/marketplace-listing-assist", auth_h,
                             {"section": "parts", "title": "SKF 6205-2RS deep groove ball bearing", "condition": "new"})
        tid = body.get("trace_id") or h.get("x-wh-trace") or ""
        if tid:
            traces.append(tid)
        time.sleep(2.0)
        rs = recs(tid) if tid else []
        after = bucket(uid) or {}
        print(f"   HTTP {st} trace={tid} error={body.get('error')!r} scope={body.get('scope')!r} "
              f"retry_after={body.get('retry_after')} bucket after={after.get('call_count')}/{after.get('day_count')}")
        show(rs)
        ok = (st == 429 and not rs and after.get("call_count") == rl_hour and after.get("day_count") == rl_day
              and body.get("scope") == "solo" and "limit" in str(body.get("error", "")).lower())
        results.append(("L hive-less person refused at the cap, before any model call, bucket not advanced", ok, tid))

    # ── T: a transcription is recorded (item 3) ───────────────────────────────────────────────────────────────────
    if "T" in only and wav and budget_before("T voice-transcribe (2 Whisper models at most)", 2):
        if seeded is not None:
            # T's own limiter is the same person bucket L filled: let it through for this one call (restored below)
            psql(f"update public.ai_user_rate_limits set call_count = 0, day_count = 0 where user_id = {q(uid)}")
            seeded["set"] = {"call_count": 0, "day_count": 0}
        print("T  voice-transcribe (Groq Whisper; no self-hosted ASR is running)")
        st, hdr, body = curl_multipart(f"{BASE}/functions/v1/voice-transcribe", tok, anon, wav)
        tid = body.get("trace_id") or hdr.get("x-wh-trace") or ""
        if tid:
            traces.append(tid)
        rs = wait_recs(tid) if tid else []
        tr = [r for r in rs if r["kind"] == "transcription"]
        print(f"   HTTP {st} trace={tid} text={body.get('text')!r}")
        show(rs)
        ok = (st == 200 and len(tr) == 1 and tr[0]["status"] == "success" and tr[0]["trace_id"] == tid
              and tr[0]["audio_seconds"] is not None and float(tr[0]["audio_seconds"]) > 0
              and tr[0]["prompt_tokens"] is None and tr[0]["auth_uid"] == uid)
        _spent += provider_calls(rs)
        results.append(("T transcription recorded (kind transcription, audio seconds)", ok, tid))
        if st == 200:
            if seeded is None:
                own_user += 1
            else:
                seeded["set"] = {"call_count": 1, "day_count": 1}
            own_ip += 1

    # ── H: the hive path while the person's bucket is full - only if its worst case fits the budget ──────────────
    if "H" in only:
        worst = chain_worst_case()
        if budget_before(f"H marketplace with hive_id (callAI worst case: {worst} provider requests)", worst):
            st, h, body = P.curl("POST", f"{BASE}/functions/v1/marketplace-listing-assist", auth_h,
                                 {"hive_id": hive, "section": "parts", "title": "SKF 6205-2RS bearing", "condition": "new"})
            tid = body.get("trace_id") or h.get("x-wh-trace") or ""
            if tid:
                traces.append(tid)
            rs = wait_recs(tid) if tid else []
            show(rs)
            _spent += provider_calls(rs)
            results.append(("H hive member served while the person's bucket is full", st == 200 and len(rs) == 1, tid))
            own_hive += 1
            own_route += 1
        else:
            print("   H not sent: the hive-member half of item 1 is carried by the psql recipe "
                  "(member's person and hive buckets untouched; the member cannot see the other bucket)")

    # ── chain / provider log lines in this window (includes any concurrent caller) ──────────────────────────────
    logs = subprocess.run(["docker", "logs", "--since", t0_wall, EDGE], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    lines = [l for l in (logs.stdout + logs.stderr).splitlines()
             if any(k in l for k in ("[ai-chain", "[audio-chain", "[embedding]", "rate_limiter_unavailable",
                                     "model_call_record"))]
    print(f"chain/embedding/audio/record log lines since start: {len(lines)} (includes any concurrent caller)")
    for l in lines[:24]:
        print("   " + l.strip()[:190])

    # ── reverse everything this run created ──────────────────────────────────────────────────────────────────────
    print("reversal:")
    for tid in traces:
        print(f"   ai_cost_log rows deleted for {tid}: " + psql(
            f"with d as (delete from public.ai_cost_log where trace_id = {q(tid)} returning 1) select count(*) from d"))
        print(f"   wh_traces rows deleted for {tid}: " + psql(
            f"with d as (delete from public.wh_traces where trace_id = {q(tid)} returning 1) select count(*) from d"))
    nu = bucket(uid)
    if seeded is not None:
        # restore the pre-image, plus what a concurrent caller added before the seed and after it
        before = seeded["before"] or {"call_count": 0, "day_count": 0}
        base_h = (pre_user or {}).get("call_count", 0) or 0
        base_d = (pre_user or {}).get("day_count", 0) or 0
        conc_pre_h = max(0, (before.get("call_count") or 0) - base_h - own_user)
        conc_pre_d = max(0, (before.get("day_count") or 0) - base_d - own_user)
        conc_post_h = max(0, (nu or {}).get("call_count", 0) - seeded["set"]["call_count"])
        conc_post_d = max(0, (nu or {}).get("day_count", 0) - seeded["set"]["day_count"])
        if pre_user is None and not (conc_pre_h or conc_post_h):
            psql(f"delete from public.ai_user_rate_limits where user_id = {q(uid)}")
            print(f"   ai_user_rate_limits[{uid}]: did not exist before this run - deleted")
        else:
            ws = (pre_user or {}).get("window_start")
            dws = (pre_user or {}).get("day_window_start")
            psql(f"update public.ai_user_rate_limits set call_count = {base_h + conc_pre_h + conc_post_h}, "
                 f"day_count = {base_d + conc_pre_d + conc_post_d}"
                 + (f", window_start = {q(ws)}" if ws else "") + (f", day_window_start = {q(dws)}" if dws else "")
                 + f" where user_id = {q(uid)}")
            print(f"   ai_user_rate_limits[{uid}]: restored to its pre-image {base_h}/{base_d} "
                  f"(+ concurrent {conc_pre_h + conc_post_h}/{conc_pre_d + conc_post_d}; this run's own "
                  f"{own_user} + the seed discarded)")
    elif nu and own_user:
        if pre_user is None and (nu.get("call_count") or 0) <= own_user:
            psql(f"delete from public.ai_user_rate_limits where user_id = {q(uid)}")
            print(f"   ai_user_rate_limits[{uid}]: created by this run - deleted")
        else:
            psql(f"update public.ai_user_rate_limits set call_count = greatest(0, call_count - {own_user}), "
                 f"day_count = greatest(0, day_count - {own_user}) where user_id = {q(uid)}")
            print(f"   ai_user_rate_limits[{uid}]: decremented by {own_user}")
    left_ip = own_ip
    for k, r in ip_buckets().items():
        if left_ip <= 0:
            break
        p = pre_ip.get(k)
        if p is None:
            if (r["call_count"] or 0) <= left_ip:
                psql(f"delete from public.ai_user_rate_limits where user_id = {q(k)}")
                print(f"   ai_user_rate_limits[{k}]: created by this run - deleted")
                left_ip -= r["call_count"] or 0
            continue
        rise = min(left_ip, max(0, (r["call_count"] or 0) - (p["call_count"] or 0)))
        if rise:
            psql(f"update public.ai_user_rate_limits set call_count = greatest(0, call_count - {rise}), "
                 f"day_count = greatest(0, day_count - {rise}) where user_id = {q(k)}")
            print(f"   ai_user_rate_limits[{k}]: {p['call_count']} -> {r['call_count']} -> decremented by {rise}")
            left_ip -= rise
    if left_ip:
        print(f"   ip: ceiling buckets: {left_ip} increment(s) not found to undo (window rolled or not counted)")
    if own_hive:
        if pre_hive is None:
            psql(f"delete from public.ai_rate_limits where hive_id = {q(hive)} and call_count <= {own_hive}")
        else:
            psql(f"update public.ai_rate_limits set call_count = greatest(0, call_count - {own_hive}), "
                 f"day_count = greatest(0, day_count - {own_hive}) where hive_id = {q(hive)}")
        print(f"   ai_rate_limits[{hive}]: this run's {own_hive} undone")
    if own_route:
        if pre_route is None:
            psql(f"delete from public.hive_route_calls where hive_id = {q(hive)} and route = 'marketplace-listing-assist' "
                 f"and hour_bucket = {q(hour)} and call_count <= {own_route}")
        else:
            psql(f"update public.hive_route_calls set call_count = greatest(0, call_count - {own_route}) "
                 f"where hive_id = {q(hive)} and route = 'marketplace-listing-assist' and hour_bucket = {q(hour)}")
        print(f"   hive_route_calls: this run's {own_route} undone")
    now_global = row("select minute_count, minute_window_start, day_count, day_window_start from public.ai_global_budget "
                     "where id = 'global'")
    if own_global and now_global and pre_global:
        sets = []
        for c, w in (("minute_count", "minute_window_start"), ("day_count", "day_window_start")):
            moved = (now_global.get(c) or 0) >= (pre_global.get(c) or 0) + own_global
            rolled = now_global.get(w) != pre_global.get(w) and (now_global.get(c) or 0) >= own_global
            if moved or rolled:
                sets.append(f"{c} = greatest(0, {c} - {own_global})")
        if sets:
            psql(f"update public.ai_global_budget set {', '.join(sets)} where id = 'global'")
        print(f"   ai_global_budget: {', '.join(sets) or 'nothing of this run left to undo'}")
    new_cache = set(psql("select coalesce(string_agg(query_hash || '|' || model, ','), '') from public.embedding_cache "
                         f"where created_at >= {q(t0_db)}").split(",")) - {""} - pre_cache
    if new_cache:
        print("   embedding_cache rows created during the run deleted: " + psql(
            "with d as (delete from public.embedding_cache where query_hash || '|' || model in ("
            + ",".join(q(x) for x in new_cache) + ") returning 1) select count(*) from d"))
    undo_sign_in()
    for tid in traces:
        print(f"   rows left carrying {tid}: " + psql(
            f"select (select count(*) from public.ai_cost_log where trace_id = {q(tid)}) + "
            f"(select count(*) from public.wh_traces where trace_id = {q(tid)}) + "
            f"(select count(*) from public.ai_reply_feedback where trace_id = {q(tid)})"))
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
            (select string_agg(format('%I::text in (%L, %L)', x, {q(uid)}, {q(hive)}), ' or ')
               from unnest(string_to_array(r.cols, ',')) x)) into n;
          if n > 0 then raise notice 'LEFT % %', r.table_name, n; end if;
        end loop; end $$;"""], capture_output=True, text=True, encoding="utf-8")
    left = [l for l in notes.stderr.splitlines() if "LEFT" in l]
    print("   rows still dated after the start for this user/hive: "
          + (", ".join(l.split("LEFT", 1)[1].strip() for l in left) or "none"))
    final = bucket(uid)
    print(f"   person bucket now {(final or {}).get('call_count')}/{(final or {}).get('day_count')} "
          f"(before the run {(pre_user or {}).get('call_count')}/{(pre_user or {}).get('day_count')})")

    print("result:")
    bad = 0
    for label, ok, tid in results:
        print(f"   {'PASS' if ok else 'FAIL'}  {label}  (trace {tid})")
        bad += 0 if ok else 1
    print(f"free-tier provider calls this run (from providers_tried): {_spent} (cap {MAX_PROVIDER_CALLS})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
