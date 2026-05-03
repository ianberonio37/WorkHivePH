"""Engineering BOM/SOW generator AI test."""
import json
import urllib.request


SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def _call_bom_sow(payload: dict, timeout: int = 60) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/functions/v1/engineering-bom-sow",
        data=body,
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
    log("BOM + SOW generator — HVAC split-type calc...")
    results = []

    payload = {
        "discipline": "Mechanical",
        "calc_type": "HVAC Cooling Load",
        "inputs": {
            "project_name": "Test Office Building",
            "floor_area": 120,
            "voltage": "230V/1Ph/60Hz",
        },
        "calc_results": {
            "q_design_kw": 12.5,
            "q_design_tr": 3.55,
            "recommended_units": 5,
            "ac_size_kw": 2.5,
        },
    }

    log("  calling /functions/v1/engineering-bom-sow...")
    status, resp = _call_bom_sow(payload)

    if status != 200:
        err = resp.get("error", f"HTTP {status}")
        results.append(("FAIL", f"BOM/SOW endpoint: {err}"))
        log(f"    FAIL — HTTP {status}: {str(err)[:120]}")
        return {"results": results}

    bom_items = resp.get("bom_items", [])
    sow_sections = resp.get("sow_sections", [])

    if isinstance(bom_items, list) and len(bom_items) >= 3:
        results.append(("PASS", f"BOM returned {len(bom_items)} line items"))
        log(f"    PASS — {len(bom_items)} BOM line items")
        # Sanity-check item shape
        sample = bom_items[0] if bom_items else {}
        if isinstance(sample, dict) and any(k in sample for k in ["description", "qty", "unit", "specification"]):
            results.append(("PASS", f"BOM line item shape valid: keys={list(sample.keys())[:5]}"))
        else:
            results.append(("WARN", f"BOM line item shape unexpected: {sample}"))
    else:
        results.append(("FAIL", f"BOM returned {len(bom_items) if isinstance(bom_items, list) else 0} items (expected >=3)"))

    if isinstance(sow_sections, list) and len(sow_sections) >= 1:
        results.append(("PASS", f"SOW returned {len(sow_sections)} section(s)"))
        log(f"    PASS — {len(sow_sections)} SOW sections")
    else:
        results.append(("WARN", f"SOW returned {len(sow_sections) if isinstance(sow_sections, list) else 0} sections"))

    return {"results": results}
