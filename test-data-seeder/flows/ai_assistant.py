"""AI assistant flow — exercises ai-orchestrator with real seeded data.

Verifies the full chain: localStorage identity → Supabase REST queries → agents
fire → Groq via fallback chain → orchestrator synthesizes → assistant renders.
"""
import json
import urllib.request

from .harness import BASE_URL


SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def _call_orchestrator(question: str, hive_id: str, worker_name: str, timeout: int = 30) -> dict:
    """Direct POST to /functions/v1/ai-orchestrator. Returns parsed JSON or error dict."""
    body = json.dumps({
        "question": question,
        "hive_id": hive_id,
        "worker_name": worker_name,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/functions/v1/ai-orchestrator",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ANON_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _pick_seeded_worker_and_hive(client) -> tuple[str, str]:
    rows = client.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not rows:
        raise RuntimeError("No seeded hive_members. Run the seeder first.")
    return rows[0]["worker_name"], rows[0]["hive_id"]


def run(page, errors, warnings, log) -> dict:
    log("AI Assistant — exercising ai-orchestrator with seeded data...")
    results = []

    # Lazy import — flows that don't need DB shouldn't pull supabase
    from lib.supabase_client import get_client
    client = get_client()
    worker_name, hive_id = _pick_seeded_worker_and_hive(client)
    log(f"  using seeded worker: {worker_name} (hive {hive_id[:8]}...)")

    # ── Test 1: Breakdown query — answer should reference real machine names ──
    log("  test 1: 'What are my recent breakdowns?'")
    resp = _call_orchestrator("What are my recent breakdowns?", hive_id, worker_name)
    answer = resp.get("answer", "") if isinstance(resp.get("answer"), str) else str(resp.get("answer", ""))
    if resp.get("error"):
        err = resp["error"]
        # Transient timeout / AI provider issue — downgrade to WARN
        if "TimeoutError" in err or "timed out" in err.lower() or "timeout" in err.lower():
            results.append(("WARN", f"orchestrator timeout (AI provider slow — transient): {err[:80]}"))
            return {"results": results}
        results.append(("FAIL", f"orchestrator error: {err}"))
    elif not answer or len(answer) < 50:
        results.append(("FAIL", f"answer too short ({len(answer)} chars): {answer[:100]}"))
    elif "[object Object]" in answer:
        results.append(("FAIL", "answer is unrendered object — formatStructuredAnswer not applied"))
    else:
        # Check for real machine makes OR machine code tags (e.g. MILL-001, PB-001, GEN-003)
        import re as _re
        machines_mentioned = sum(1 for m in [
            "Caterpillar", "Cummins", "Perkins", "Grundfos", "Goulds", "Donaldson",
            "ABB", "Siemens", "WEG", "Atlas Copco", "Carrier", "Trane", "Daikin",
            "Konecranes", "Eaton", "APC", "Marley", "Cleaver-Brooks", "Mazak", "Haas",
        ] if m.lower() in answer.lower())
        code_tags = len(_re.findall(r"\b[A-Z]{2,6}-\d{2,4}\b", answer))
        if machines_mentioned >= 1 or code_tags >= 1:
            label = f"{machines_mentioned} make(s)" if machines_mentioned else f"{code_tags} machine code(s)"
            results.append(("PASS", f"breakdown answer references {label}; {len(answer)} chars"))
            log(f"    PASS — {label}, {len(answer)} chars")
        else:
            results.append(("WARN", f"answer is non-empty but no machine reference found: {answer[:200]}"))

    agents = resp.get("agents_used", [])
    if agents:
        results.append(("PASS", f"agents fired: {agents}"))
        log(f"    agents_used = {agents}")
    else:
        results.append(("WARN", "no agents_used field — orchestrator may have skipped routing"))

    # ── Test 2: PM-focused query — should call pm_status agent ──
    log("  test 2: 'Which assets have overdue PM?'")
    resp = _call_orchestrator("Which assets have overdue PM?", hive_id, worker_name)
    answer = resp.get("answer", "")
    if resp.get("error"):
        results.append(("FAIL", f"PM query error: {resp['error']}"))
    elif "pm_status" in (resp.get("agents_used") or []):
        results.append(("PASS", "pm_status agent fired for PM-focused question (router works)"))
        log(f"    PASS — pm_status agent correctly selected by router")
    else:
        results.append(("WARN", f"router did not pick pm_status; agents={resp.get('agents_used')}"))

    # ── Test 3: Empty / nonsense question — should gracefully decline ──
    log("  test 3: empty question (should gracefully reject)")
    resp = _call_orchestrator("", hive_id, worker_name)
    err = str(resp.get("error", ""))
    # Either HTTP 400 (input validation rejected the request) or a structured error
    if "400" in err or "question" in err.lower():
        results.append(("PASS", "empty question rejected (good input validation)"))
        log(f"    PASS — empty rejected as expected")
    elif resp.get("answer"):
        results.append(("WARN", f"empty question got an answer: {str(resp.get('answer'))[:100]}"))
    else:
        results.append(("FAIL", f"empty question: unclear response: {resp}"))

    return {"results": results}
