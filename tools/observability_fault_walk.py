"""
Observability Fault-Injection Walk (Arc T / T2 live proof, 2026-07-01).
======================================================================
Reproducible LIVE proof that the serveObserved() error net actually fires:
injects an unhandled throw into a served edge fn (via the auth-gated chaos hook)
and asserts a wh_traces error row lands with the SAME trace_id the client got
back -- i.e. error VISIBILITY (stderr) + AGGREGATION (wh_traces) + a clean,
non-leaky 500 envelope, end to end. Satisfies OBSERVABILITY_SLO_ROADMAP §exit
("proven to fire by a live fault-injection walk").

Also asserts prod-safety: an anon caller with the same header does NOT inject
(the chaos hook requires the service-role key OR WH_CHAOS=1).

Infra: local Supabase (edge runtime + db containers). If the edge runtime is
down it is started; if it still cannot serve, the walk SKIPS (exit 0) rather
than flaking a gate -- it is a live proof, not a static lock (that is
validate_edge_error_capture.py).

Env overrides: WH_EDGE_CONTAINER, WH_LOCAL_DB_CONTAINER, WH_FAULT_ROUTE.
Exit: 0 pass or skip(infra) ; 1 the net FAILED to capture (real regression).
"""
from __future__ import annotations
import io, json, os, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "observability_fault_walk_report.json"
EDGE = os.environ.get("WH_EDGE_CONTAINER", "supabase_edge_runtime_workhive")
DB = os.environ.get("WH_LOCAL_DB_CONTAINER", "supabase_db_workhive")
ROUTE = os.environ.get("WH_FAULT_ROUTE", "semantic-search")
BASE = "http://127.0.0.1:54321/functions/v1"
CHECK_NAMES = ["observability_fault_walk"]


def sh(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def container_running(name: str) -> bool:
    rc, out = sh(["docker", "ps", "--format", "{{.Names}}"])
    return rc == 0 and name in out.splitlines()


def psql(sql: str) -> str:
    rc, out = sh(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql])
    return out.strip() if rc == 0 else ""


def edge_env(key_substr: str) -> str:
    rc, out = sh(["docker", "exec", EDGE, "env"])
    if rc != 0:
        return ""
    for line in out.splitlines():
        if key_substr in line and "=" in line:
            return line.split("=", 1)[1].strip()
    return ""


def wait_ready(secs: int = 25) -> bool:
    for _ in range(secs):
        rc, out = sh(["docker", "logs", "--tail", "4", EDGE])
        if "Serving functions" in out:
            return True
        time.sleep(1)
    return False


def invoke(bearer: str, fault: bool) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}/{ROUTE}", data=b"{}", method="POST")
    req.add_header("Authorization", f"Bearer {bearer}")
    req.add_header("Content-Type", "application/json")
    if fault:
        req.add_header("x-wh-fault-inject", "1")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"_raw": body[:200]}
    except Exception as e:
        return -1, {"_err": str(e)}


def err_code(body: dict) -> str | None:
    """Safe extract of error.code; the envelope uses {error:{code,..}} but a
    plain handler may return {error:"<string>"} -- never assume a dict."""
    e = body.get("error") if isinstance(body, dict) else None
    return e.get("code") if isinstance(e, dict) else None


def finish(result: dict, code: int) -> int:
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "note") if k in result}))
    return code


def main() -> int:
    result: dict = {"route": ROUTE}
    if not container_running(DB):
        result.update(status="SKIP", note=f"db container {DB} not running")
        print(f"SKIP: db container {DB} not running (live proof needs local Supabase)")
        return finish(result, 0)
    if not container_running(EDGE):
        sh(["docker", "start", EDGE])
        if not wait_ready():
            result.update(status="SKIP", note="edge runtime unavailable after start")
            print("SKIP: edge runtime unavailable (started it, did not become ready)")
            return finish(result, 0)

    svc = edge_env("SERVICE_ROLE_KEY")
    anon = edge_env("ANON_KEY")
    if not svc:
        result.update(status="SKIP", note="service-role key not readable from edge env")
        print("SKIP: could not read SERVICE_ROLE_KEY from edge env")
        return finish(result, 0)

    before = psql("select count(*) from wh_traces where error_code is not null;") or "?"

    # 1) service-role fault inject -> expect clean 500 unhandled_error + a row.
    st, body = invoke(svc, fault=True)
    trace = body.get("trace_id") if isinstance(body, dict) else None
    result.update(svc_http=st, svc_body_code=err_code(body), svc_trace=trace)
    leaked = "chaos_fault_injection" in json.dumps(body)
    row = psql(f"select route,status,error_code from wh_traces where trace_id='{trace}';") if trace else ""
    result["row_landed"] = bool(row) and ROUTE in row and "unhandled_error" in row

    # 1b) T6 trace correlation: the SAME trace_id must thread the edge-runtime
    # LOG (trackError's console.error) -> wh_traces (checked above) -> the client
    # response (svc_trace). One id correlates all three observability surfaces.
    log_has_trace = False
    if trace:
        rc, logs = sh(["docker", "logs", "--tail", "120", EDGE])
        log_has_trace = (rc == 0) and (trace in logs)
    result["log_has_trace"] = log_has_trace

    # 2) prod-safety: anon + same header must NOT inject.
    anon_injected = False
    if anon:
        _, abody = invoke(anon, fault=True)
        anon_injected = err_code(abody) == "unhandled_error"
    result["anon_injected"] = anon_injected

    # cleanup injected rows
    psql("delete from wh_traces where error_code='unhandled_error';")
    after = psql("select count(*) from wh_traces where error_code is not null;") or "?"
    result.update(baseline_before=before, baseline_after_cleanup=after)

    ok = (st == 500 and result["svc_body_code"] == "unhandled_error"
          and result["row_landed"] and log_has_trace and not leaked and not anon_injected)
    if ok:
        result.update(status="PASS", note=f"unhandled throw on '{ROUTE}' -> log+wh_traces+response all correlate on trace {trace}; non-leaky; anon blocked")
        print(f"PASS: fault on '{ROUTE}' captured (trace {trace}); log<->wh_traces<->response correlate; non-leaky; anon cannot inject.")
        return finish(result, 0)
    fails = []
    if st != 500: fails.append(f"http={st}!=500")
    if result["svc_body_code"] != "unhandled_error": fails.append("body!=unhandled_error")
    if not result["row_landed"]: fails.append("no wh_traces row")
    if not log_has_trace: fails.append("trace_id NOT in edge log (T6 correlation broken)")
    if leaked: fails.append("LEAKED internal error to client")
    if anon_injected: fails.append("anon COULD inject (prod-unsafe)")
    result.update(status="FAIL", note="; ".join(fails))
    print(f"FAIL: {result['note']}")
    return finish(result, 1)


if __name__ == "__main__":
    sys.exit(main())
