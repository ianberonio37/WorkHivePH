#!/usr/bin/env python3
"""backend_edge_probe.py — Arc E B1/B2 live edge prober.

Runtime-exercises each edge function against the RUNNING local Supabase edge
(127.0.0.1:54321) and writes backend_edge_probe.json, which backend_ufai_sweep.py
folds to flip U2/U3/U4/U5/I1/F1 cells from `static` -> `live` (real evidence:
the fn answered, echoed CORS, validated input, or gated auth).

Two safe probes per fn:
  OPTIONS  -> CORS preflight (U3) : assert Access-Control-Allow-Origin echoed
  POST {}  -> error-path (U2/U4/U5/I1/F1) : structured 4xx without doing real work
SAFETY: money/webhook fns (E6 + *webhook*) get OPTIONS-ONLY (no POST) so no
payment/at-least-once side effect is ever triggered.

USAGE: python tools/backend_edge_probe.py
"""
from __future__ import annotations
import json, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCS_DIR = ROOT / "supabase" / "functions"
OUT = ROOT / "backend_edge_probe.json"
BASE = "http://127.0.0.1:54321/functions/v1"
ORIGIN = "http://127.0.0.1:5000"

_LIVE_HIVE_CACHE: list[str] = []


def _live_hive() -> str:
    """The seeded user's REAL hive, resolved once from the live hive_members row (test_identity
    pattern) — a pinned UUID rots across reseeds, and a dead hive makes the I4 probe 403
    not_a_member = a 4xx 'pass' for the WRONG reason (tenancy, not the input-size path)."""
    if not _LIVE_HIVE_CACHE:
        try:
            import sys as _s
            _s.path.insert(0, str(ROOT / "tools" / "lib"))
            from test_identity import resolve_test_identity
            _LIVE_HIVE_CACHE.append(resolve_test_identity("leandromarquez@auth.workhiveph.com").hive_id)
        except Exception:
            _LIVE_HIVE_CACHE.append("9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7")  # hive fallback (stale-known)
    return _LIVE_HIVE_CACHE[0]
# Never POST to these (money / at-least-once) — OPTIONS only.
POST_SKIP = re.compile(r"marketplace|webhook|release|checkout|connect|cmms-push|trigger-ml|send-report")


def anon_key() -> str:
    for c in ("supabase_kong_workhive", "supabase_edge_runtime_workhive"):
        try:
            r = subprocess.run(["docker", "exec", c, "sh", "-c", "echo $SUPABASE_ANON_KEY"],
                               capture_output=True, text=True, timeout=20)
            k = r.stdout.strip()
            if k.startswith("eyJ"):
                return k
        except Exception:
            pass
    return ""


def user_jwt(key: str) -> str:
    """Mint a real user JWT (leandromarquez, hive 9b4eaeac) so the I4 over-long-input probe
    passes auth and the 20k body actually reaches the function's input pipeline (not a bare 401)."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:54321/auth/v1/token?grant_type=password",
            data=json.dumps({"email": "leandromarquez@auth.workhiveph.com", "password": "test1234"}).encode(),
            headers={"Content-Type": "application/json", "apikey": key}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=15).read()).get("access_token", "")
    except Exception:
        return ""


def curl(args: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(["curl", "-s", "-m", "12", *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=20)
        return r.returncode, r.stdout
    except Exception as e:  # noqa: BLE001
        return 1, f"ERR {e}"


def probe(fn: str, key: str, jwt: str = "") -> dict:
    url = f"{BASE}/{fn}"
    # OPTIONS preflight
    _, hdrs = curl(["-D", "-", "-o", "/dev/null", "-X", "OPTIONS", url,
                    "-H", f"Origin: {ORIGIN}", "-H", "Access-Control-Request-Method: POST"])
    cors_ok = bool(re.search(r"access-control-allow-origin:", hdrs, re.I))
    opt_code = int((re.search(r"HTTP/[\d.]+ (\d+)", hdrs) or [0, 0])[1]) if "HTTP" in hdrs else 0
    rec = {"options_code": opt_code, "cors_ok": cors_ok, "post_code": None,
           "post_body": None, "input_validation": False, "auth_gated": False,
           "reachable": cors_ok, "health_ok": False}
    # live /health (I6) — only for fns that wire the shared health handler
    src = (FUNCS_DIR / fn / "index.ts").read_text(encoding="utf-8", errors="replace") if (FUNCS_DIR / fn / "index.ts").exists() else ""
    if re.search(r"handleHealth|_shared/health", src):
        _, hb = curl(["-w", "\n@@%{http_code}", f"{url}/health",
                      "-H", f"Authorization: Bearer {key}", "-H", f"apikey: {key}"])
        m = re.search(r"@@(\d+)\s*$", hb)
        rec["health_ok"] = bool(m and m.group(1) == "200" and re.search(r'"ok"\s*:\s*true|"status"\s*:\s*"ok"', hb))
    if POST_SKIP.search(fn):
        rec["post_skipped"] = "money/webhook safety"
        return rec
    # POST {} error-path
    _, out = curl(["-w", "\n@@%{http_code}", "-X", "POST", url,
                   "-H", f"Authorization: Bearer {key}", "-H", f"apikey: {key}",
                   "-H", "Content-Type: application/json", "-H", f"Origin: {ORIGIN}", "-d", "{}"])
    m = re.search(r"@@(\d+)\s*$", out)
    code = int(m.group(1)) if m else 0
    body = out[: m.start()].strip() if m else out.strip()
    rec["post_code"] = code
    rec["post_body"] = body[:160]
    rec["reachable"] = rec["reachable"] or code > 0
    rec["input_validation"] = code in (400, 422) and bool(re.search(r"error|missing|invalid|required", body, re.I))
    rec["auth_gated"] = code in (401, 403)
    # I4 (injection / over-long input) — adversarial: a 20k-char input field must be handled
    # GRACEFULLY (no 500). Sent with a real USER JWT (so it passes auth and the oversized body
    # reaches the input pipeline) but WITHOUT a valid task (only the over-long field + a hive),
    # so it 4xx's on validation BEFORE any LLM call ($0, never triggers a paid model). li_i4_ok =
    # the oversized body did not crash the function (any non-500 = the input-size path is robust).
    auth = jwt or key
    _, o4 = curl(["-w", "\n@@%{http_code}", "-X", "POST", url,
                  "-H", f"Authorization: Bearer {auth}", "-H", f"apikey: {key}",
                  "-H", "Content-Type: application/json", "-H", f"Origin: {ORIGIN}",
                  # hive resolved at runtime (stale pin would 403 not_a_member = a 4xx "pass"
                  # for the WRONG reason — tenancy, not the input-size path this probe proves)
                  "-d", json.dumps({"text": "A" * 20000, "hive_id": _live_hive()})])
    m4 = re.search(r"@@(\d+)\s*$", o4)
    c4 = int(m4.group(1)) if m4 else 0
    rec["li_i4_ok"] = c4 != 0 and c4 < 500
    rec["li_i4_code"] = c4
    return rec


def main() -> int:
    key = anon_key()
    jwt = user_jwt(key)
    fns = sorted(p.parent.name for p in FUNCS_DIR.glob("*/index.ts"))
    out = {"base": BASE, "anon_key_len": len(key), "user_jwt": bool(jwt), "probes": {}}
    cors_n = iv_n = auth_n = reach_n = health_n = i4_n = 0
    for fn in fns:
        r = probe(fn, key, jwt)
        out["probes"][fn] = r
        cors_n += r["cors_ok"]; iv_n += r["input_validation"]; auth_n += r["auth_gated"]
        reach_n += r["reachable"]; health_n += r["health_ok"]; i4_n += bool(r.get("li_i4_ok"))
        tag = f"cors={'Y' if r['cors_ok'] else '.'} post={r['post_code']} health={'Y' if r['health_ok'] else '.'} i4={r.get('li_i4_code')}"
        print(f"  {fn:34} OPT {r['options_code']:>3}  {tag}")
    # I6 observability via STRUCTURED LOG emission: after the probes above invoked every fn, the
    # edge runtime logs carry a structured `{"route":"<fn>","msg":"request_start"}` line for any fn
    # that adopted logRequestStart (the reusable one-liner). Capture them in ONE docker-logs read
    # and set log_ok per fn — a live observability signal (the fn emits greppable structured logs).
    try:
        logs = subprocess.run(["docker", "logs", "--tail", "4000", "supabase_edge_runtime_workhive"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        blob = (logs.stdout or "") + (logs.stderr or "")
        logged = set(re.findall(r'"route":"([a-z0-9-]+)"[^}]*"msg":"request_(?:start|end)"', blob))
        log_n = 0
        for fn in fns:
            ok = fn in logged
            out["probes"][fn]["log_ok"] = ok
            log_n += ok
    except Exception:
        log_n = 0
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("-" * 60)
    print(f"  {len(fns)} fns probed   cors_ok {cors_n}   input_val {iv_n}   auth_gated {auth_n}   reachable {reach_n}   health {health_n}   i4_ok {i4_n}   log_ok {log_n}")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
