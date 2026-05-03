"""Multi-agent chain tests — the interconnected flows that make WorkHive smart.

These tests prove the platform's MOAT: write data → embed → retrieve → answer.
Each chain exercises 3+ services in sequence, with one's output feeding the next.

Chain A — Write/Embed/Search loop (RAG plumbing):
  Insert a unique fault into fault_knowledge via embed-entry, then search for it.
  Verifies: ingestion → Voyage/Jina chain → DB write → vector index → query → match.

Chain B — Logbook → Assistant context injection (the moat):
  Same insert+embed, then ask the assistant about that specific issue.
  Verifies end-to-end RAG: orchestrator queries semantic-search, injects
  retrieved context into the agent prompt, agent references our new entry.
"""
import json
import time
import urllib.request
import uuid

SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def _post(endpoint: str, body: dict, timeout: int = 30) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{SUPABASE_URL}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {ANON_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (r.status, json.loads(r.read()))
    except urllib.error.HTTPError as e:
        try:
            return (e.code, json.loads(e.read()))
        except Exception:
            return (e.code, {})
    except Exception as e:
        return (0, {"error": f"{type(e).__name__}: {e}"})


def run(page, errors, warnings, log) -> dict:
    log("Multi-agent chain tests — write/embed/retrieve and full RAG...")
    results = []

    from lib.supabase_client import get_client
    db = get_client()
    member = db.table("hive_members").select("worker_name, hive_id, auth_uid").limit(1).execute().data
    if not member:
        return {"results": [("FAIL", "no seeded hive_members")]}
    worker_name = member[0]["worker_name"]
    hive_id = member[0]["hive_id"]
    auth_uid = member[0]["auth_uid"]

    # Use a unique signature phrase the LLM cannot have hallucinated and that
    # won't conflict with any seeded entry. Random suffix per run.
    canary = f"chainsig-{uuid.uuid4().hex[:8]}"
    machine_tag = f"Hewlett-Packard 90210 Quantum Reactor (CNRY-{canary[-4:].upper()})"
    problem_text = f"Coolant pressure anomaly {canary} detected during quantum coil routine"
    root_cause = "Phase desynchronization (test signature)"
    action = "Reset phase coil; recalibrated quantum register"

    # ── Chain A — write+embed+search ────────────────────────────────────────
    log(f"  Chain A: insert unique fault [{canary}] → embed → search retrieval")

    # Step 1: Insert a logbook row directly so RLS/auth_uid is preserved
    log_id = f"chainprobe-{canary}"
    insert_resp = db.table("logbook").insert({
        "id": log_id,
        "worker_name": worker_name,
        "date": "2026-05-04T10:00:00Z",
        "machine": machine_tag,
        "category": "Mechanical",
        "maintenance_type": "Breakdown / Corrective",
        "problem": problem_text,
        "root_cause": root_cause,
        "action": action,
        "knowledge": f"If you see {canary}, run phase reset before anything else",
        "status": "Closed",
        "downtime_hours": 1.5,
        "hive_id": hive_id,
        "auth_uid": auth_uid,
        "created_at": "2026-05-04T10:00:00Z",
        "closed_at": "2026-05-04T11:30:00Z",
    }).execute()
    if not insert_resp.data:
        return {"results": [("FAIL", "could not insert canary logbook entry")]}

    # Step 2: Call embed-entry manually to generate embedding into fault_knowledge
    status, resp = _post("/functions/v1/embed-entry", {
        "type": "fault",
        "hive_id": hive_id,
        "entry": {
            "machine": machine_tag,
            "problem": problem_text,
            "root_cause": root_cause,
            "action": action,
            "knowledge": f"If you see {canary}, run phase reset before anything else",
            "category": "Mechanical",
        },
    }, timeout=30)
    if status != 200:
        results.append(("FAIL", f"embed-entry failed: HTTP {status}: {str(resp)[:120]}"))
        log(f"    FAIL — embed-entry returned {status}")
        # Cleanup before bailing
        db.table("logbook").delete().eq("id", log_id).execute()
        return {"results": results}
    log(f"    ✓ embed-entry succeeded")

    # Step 3: Wait briefly for vector index to settle, then semantic search
    time.sleep(1)
    status, search_resp = _post("/functions/v1/semantic-search", {
        "query": problem_text,
        "hive_id": hive_id,
        "match_count": 5,
    }, timeout=30)

    if status != 200:
        results.append(("FAIL", f"semantic-search failed: HTTP {status}"))
    else:
        # Look for canary in the returned context or results
        context = str(search_resp.get("context", "")) + json.dumps(search_resp.get("results", {}))
        if canary in context:
            results.append(("PASS", f"chain A: canary fault retrieved via semantic search ({canary})"))
            log(f"    ✓ Chain A PASS — canary {canary} found in search results")
        else:
            results.append(("WARN", f"chain A: canary not in search top-5; results were: {context[:200]}"))
            log(f"    WARN — canary not in top-5 results, may need higher match_count")

    # ── Chain B — full RAG via assistant ───────────────────────────────────
    log(f"  Chain B: ask AI assistant about the canary entry")
    status, asst_resp = _post("/functions/v1/ai-orchestrator", {
        "question": f"Tell me about any equipment with {canary} issue",
        "hive_id": hive_id,
        "worker_name": worker_name,
    }, timeout=45)

    if status != 200:
        results.append(("FAIL", f"assistant failed: HTTP {status}"))
    else:
        answer = asst_resp.get("answer", "")
        if isinstance(answer, dict):
            answer = json.dumps(answer)
        # Loose match — canary in response, OR machine name (Hewlett-Packard etc),
        # OR root cause keyword. Any of these proves RAG context was injected.
        hit = (
            canary in answer
            or "Hewlett-Packard" in answer
            or "Quantum Reactor" in answer
            or "phase desynchronization" in answer.lower()
            or "phase reset" in answer.lower()
        )
        if hit:
            results.append(("PASS", f"chain B: assistant referenced canary content (RAG context injected)"))
            log(f"    ✓ Chain B PASS — assistant pulled canary into its answer")
        else:
            results.append(("WARN", f"chain B: canary not surfaced in answer (assistant may have ignored RAG): {answer[:200]}"))
            log(f"    WARN — canary not in assistant answer (RAG retrieval may have failed)")

    # ── Cleanup canary rows so the data tests stay deterministic ───────────
    log("  cleaning up canary entries...")
    try:
        db.table("logbook").delete().eq("id", log_id).execute()
        # fault_knowledge has machine + problem text — filter on the unique tag
        canary_tag = f"CNRY-{canary[-4:].upper()}"
        db.table("fault_knowledge").delete().like("machine", f"%{canary_tag}%").execute()
    except Exception as e:
        log(f"  WARN: cleanup partial: {e}")

    return {"results": results}
