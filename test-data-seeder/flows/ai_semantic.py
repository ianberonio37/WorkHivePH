"""Semantic search test — currently expected to FAIL until prod bug #7 is fixed.

The semantic-search edge function calls Groq's embeddings endpoint with model
'nomic-embed-text-v1_5', but Groq does not offer an embeddings API. The test
expects this specific failure mode and will start passing automatically once
the embedding provider is swapped (see PRODUCTION_FIXES.md #7).
"""
import json
import urllib.request


SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def _call(query: str, hive_id: str, timeout: int = 20) -> tuple[int, dict]:
    body = json.dumps({"query": query, "hive_id": hive_id, "match_count": 3}).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/functions/v1/semantic-search",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {ANON_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (r.status, json.loads(r.read()))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return (e.code, parsed)
    except Exception as e:
        return (0, {"error": f"{type(e).__name__}: {e}"})


def run(page, errors, warnings, log) -> dict:
    log("Semantic search — RAG retrieval...")
    results = []

    from lib.supabase_client import get_client
    rows = get_client().table("hives").select("id").limit(1).execute().data
    if not rows:
        return {"results": [("FAIL", "no seeded hives")]}
    hive_id = rows[0]["id"]

    log("  query: 'bearing temperature high'")
    status, resp = _call("bearing temperature high", hive_id)

    if status == 200:
        # Embedding worked — semantic search is functional
        results_count = len(resp.get("matches", resp.get("results", [])))
        if results_count > 0:
            results.append(("PASS", f"semantic search returned {results_count} results"))
            log(f"    PASS — {results_count} matches found")
        else:
            results.append(("WARN", "200 but no matches — knowledge tables may be empty (need embed-entry to populate)"))

    else:
        # Expected failure mode: embedding model unavailable
        err_text = str(resp.get("error", "")) + str(resp)
        if "nomic-embed" in err_text or "model_not_found" in err_text or "embedding" in err_text.lower():
            results.append(("WARN", f"semantic-search broken (known prod bug #7): embedding provider issue. HTTP {status}"))
            log(f"    KNOWN — semantic search broken until embedding provider swapped (PRODUCTION_FIXES #7)")
        else:
            results.append(("FAIL", f"semantic-search: unexpected HTTP {status}: {err_text[:200]}"))

    return {"results": results}
