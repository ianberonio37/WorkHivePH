"""Analytics orchestrator AI tests — exercises all 4 phases."""
import json
import urllib.request


SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def _call(phase: str, hive_id: str, worker_name: str, timeout: int = 45) -> dict:
    body = json.dumps({
        "phase": phase,
        "hive_id": hive_id,
        "worker_name": worker_name,
        "period_days": 90,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/functions/v1/analytics-orchestrator",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {ANON_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def run(page, errors, warnings, log) -> dict:
    log("Analytics orchestrator — all 4 phases...")
    results = []

    from lib.supabase_client import get_client
    rows = get_client().table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not rows:
        return {"results": [("FAIL", "no seeded hive_members")]}
    worker_name, hive_id = rows[0]["worker_name"], rows[0]["hive_id"]

    for phase in ["descriptive", "diagnostic", "predictive", "prescriptive"]:
        log(f"  phase: {phase}")
        resp = _call(phase, hive_id, worker_name)
        err_text = str(resp.get("error", ""))

        if "Python Analytics API not configured" in err_text or "PYTHON_API_URL" in err_text:
            results.append(("WARN", f"{phase}: Python API not configured locally (expected in test mode)"))
            log(f"    SKIP — Python API delegated to Render in production")
            continue
        if err_text:
            results.append(("FAIL", f"{phase}: {err_text}"))
            log(f"    FAIL — {err_text}")
            continue

        keys = list(resp.keys())
        if not keys:
            results.append(("FAIL", f"{phase}: empty response"))
        elif resp.get("error"):
            results.append(("FAIL", f"{phase}: {resp['error']}"))
        else:
            size = len(json.dumps(resp))
            if size > 200:
                results.append(("PASS", f"{phase}: returned {size} chars across keys {keys[:5]}"))
                log(f"    PASS — {size} chars, keys: {keys[:5]}")
            else:
                results.append(("WARN", f"{phase}: small response ({size} chars): {keys}"))

    return {"results": results}
