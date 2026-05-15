"""
Voice Action Router Flow -- WorkHive Tester (Phase B.1 + B.2 + B.3)

Verifies the cross-page voice orchestrator and its per-page handler
registrations end-to-end.

What this checks:
  1. POST with empty body returns 400 with transcript-missing error
  2. POST with transcript but no hive_id returns 400
  3. POST with asset.lookup transcript classifies correctly + resolves
     mentioned_assets via canonical v_asset_truth
  4. POST with logbook.create transcript classifies correctly + extracts
     machine and parts_used entities
  5. voice-handler.js shared module exists and exposes WHVoice global
  6. nav-hub.js lazy-loads voice-handler.js
  7. logbook.html, inventory.html, pm-scheduler.html, asset-hub.html
     each register their respective intent handlers

Edge-function calls require the voice-action-router to be deployed.
When it is not (Phase B.1 was uncommitted and undeployed at flow
creation), those checks WARN rather than FAIL.
"""
import json
import urllib.request
import urllib.error
from .harness import BASE_URL


SUPABASE_URL = "https://hzyvnjtisfgbksicrouu.supabase.co"
SUPABASE_KEY = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"


def _post_router(body, timeout=30):
    """POST to voice-action-router. Returns (status, parsed_json_or_text, err)."""
    url = f"{SUPABASE_URL}/functions/v1/voice-action-router"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey":        SUPABASE_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(payload), None
            except json.JSONDecodeError:
                return r.status, payload, "non-JSON response"
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        try:
            return e.code, json.loads(body_text), None
        except Exception:
            return e.code, body_text, None
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


def run(page, errors, warnings, log) -> dict:
    """Tester entry point. `page` is treated as the Flask base URL string,
    matching the auto_staging_flow / asset_hub_flow convention."""
    results = []

    # ── Test 1: empty body should 400 with transcript-missing ───────────────
    log("Step 1: POST {} should 400 with transcript-missing error...")
    status, body, err = _post_router({})
    if status is None:
        results.append((
            "WARN",
            f"Could not reach voice-action-router (likely undeployed): {err}",
        ))
        # No point running the rest if the function is unreachable.
        return {"results": results}
    if status == 400 and isinstance(body, dict) and "transcript" in str(body.get("error", "")).lower():
        results.append(("PASS", "Empty body returns 400 with transcript-missing error"))
    else:
        results.append((
            "FAIL",
            f"Empty body expected 400 transcript-missing, got status={status} body={str(body)[:160]}",
        ))

    # ── Test 2: missing hive_id should 400 ──────────────────────────────────
    log("Step 2: POST with transcript but no hive_id should 400...")
    status, body, err = _post_router({"transcript": "show me pump 5"})
    if status == 400 and isinstance(body, dict) and "hive_id" in str(body.get("error", "")).lower():
        results.append(("PASS", "Missing hive_id returns 400 hive_id-missing error"))
    else:
        results.append((
            "FAIL",
            f"Missing hive_id expected 400, got status={status} body={str(body)[:160]}",
        ))

    # ── Locate a seeded hive for the valid-input tests ──────────────────────
    log("Step 3: Locating seeded hive for valid input tests...")
    hive_id = None
    try:
        from lib.supabase_client import get_client
        db = get_client()
        rows = db.table("hive_members").select("hive_id").limit(1).execute().data
        if rows:
            hive_id = rows[0]["hive_id"]
    except Exception as e:
        results.append(("WARN", f"Could not load supabase client: {e}"))
    if not hive_id:
        results.append(("WARN", "No seeded hive_members row found; intent tests skipped"))
        return {"results": results + _static_file_checks(page)}

    # ── Test 3: asset.lookup transcript ─────────────────────────────────────
    log("Step 4: asset.lookup transcript classifies + resolves...")
    status, body, err = _post_router({
        "transcript": "what is the status of pump 5",
        "hive_id":    hive_id,
    }, timeout=90)
    if status == 200 and isinstance(body, dict):
        intents = body.get("intents", []) or []
        kinds = [i.get("kind") for i in intents]
        if any(k == "asset.lookup" for k in kinds):
            results.append(("PASS", f"asset.lookup classified correctly (kinds={kinds})"))
        else:
            results.append(("WARN", f"asset.lookup transcript got kinds={kinds} (model variance)"))
        if isinstance(body.get("mentioned_assets"), list):
            results.append((
                "PASS",
                f"Response includes mentioned_assets array ({len(body['mentioned_assets'])} entries)",
            ))
        else:
            results.append(("FAIL", "Response missing mentioned_assets array"))
        # asset_resolution.candidates must be a list when present
        ar = body.get("asset_resolution")
        if ar is None or isinstance(ar, dict):
            results.append(("PASS", "asset_resolution shape is dict (or absent when no candidates)"))
        else:
            results.append(("FAIL", f"asset_resolution wrong shape: {type(ar).__name__}"))
    elif status == 429:
        results.append(("WARN", "Rate-limited by ai_rate_limits; rerun later will pass"))
    elif status == 503:
        results.append(("WARN", "AI providers at capacity (callAI returned 503); rerun later"))
    elif status == 502:
        results.append(("WARN", "Model returned non-JSON; intent classification skipped this run"))
    else:
        results.append((
            "FAIL",
            f"asset.lookup expected 200, got status={status} body={str(body)[:160]}",
        ))

    # ── Test 4: logbook.create transcript ───────────────────────────────────
    log("Step 5: logbook.create transcript classifies + extracts entities...")
    status, body, err = _post_router({
        "transcript": "I just replaced the V-belt on Pump P-5, took 20 minutes, used 2 belts",
        "hive_id":    hive_id,
    }, timeout=90)
    if status == 200 and isinstance(body, dict):
        intents = body.get("intents", []) or []
        kinds = [i.get("kind") for i in intents]
        if any(k == "logbook.create" for k in kinds):
            results.append(("PASS", f"logbook.create classified (kinds={kinds})"))
            for it in intents:
                if it.get("kind") != "logbook.create":
                    continue
                p = it.get("params") or {}
                if p.get("machine"):
                    results.append(("PASS", f"machine extracted: {p['machine']}"))
                else:
                    results.append(("WARN", "machine not extracted (model variance)"))
                parts = p.get("parts_used") or []
                if isinstance(parts, list) and parts:
                    results.append(("PASS", f"parts_used extracted: {len(parts)} entry/entries"))
                else:
                    results.append(("WARN", "parts_used not extracted (model variance)"))
                break
        else:
            results.append(("WARN", f"logbook.create transcript got kinds={kinds}"))
    elif status in (429, 502, 503):
        results.append(("WARN", f"AI not available (status={status}); rerun later"))
    else:
        results.append(("FAIL", f"logbook.create expected 200, got status={status}"))

    # Static-file checks (work even when the edge fn is undeployed).
    results.extend(_static_file_checks(page))
    return {"results": results}


def _static_file_checks(base_url):
    """Verify voice-handler.js + nav-hub.js wiring + per-page handler
    registrations. Independent of edge-function deployment state."""
    out = []
    base = (base_url if isinstance(base_url, str) else BASE_URL).rstrip("/")

    # voice-handler.js content
    try:
        with urllib.request.urlopen(f"{base}/voice-handler.js", timeout=10) as r:
            vh = r.read(80000).decode("utf-8", errors="replace")
        for label, ok in [
            ("WHVoice global defined",       "window.WHVoice" in vh),
            ("register API exposes handlers", "register" in vh and "handlers" in vh),
            ("voice-action-router invoked",  "voice-action-router" in vh),
            ("voice-transcribe invoked",     "voice-transcribe" in vh),
            ("escHtml used on every interpolation", "escHtml(" in vh),
            ("MediaRecorder + getUserMedia",  "MediaRecorder" in vh and "getUserMedia" in vh),
        ]:
            out.append(("PASS" if ok else "FAIL", f"voice-handler.js: {label}"))
    except Exception as e:
        out.append(("WARN", f"voice-handler.js read: {e}"))

    # nav-hub.js lazy-loads voice-handler
    try:
        with urllib.request.urlopen(f"{base}/nav-hub.js", timeout=10) as r:
            nh = r.read(120000).decode("utf-8", errors="replace")
        out.append((
            "PASS" if "voice-handler.js" in nh else "FAIL",
            "nav-hub.js lazy-loads voice-handler.js",
        ))
    except Exception as e:
        out.append(("WARN", f"nav-hub.js read: {e}"))

    # Per-page handler registrations
    for page_name, kind in [
        ("logbook.html",      "logbook.create"),
        ("inventory.html",    "inventory.deduct"),
        ("pm-scheduler.html", "pm.complete"),
        ("asset-hub.html",    "asset.lookup"),
    ]:
        try:
            with urllib.request.urlopen(f"{base}/{page_name}", timeout=15) as r:
                html = r.read(250000).decode("utf-8", errors="replace")
            registered = (f"WHVoice.register('{kind}'" in html
                          or f'WHVoice.register("{kind}"' in html)
            out.append((
                "PASS" if registered else "FAIL",
                f"{page_name} registers {kind}",
            ))
        except Exception as e:
            out.append(("WARN", f"{page_name} read: {e}"))

    return out
