#!/usr/bin/env python3
"""python_api_live_invoke.py — Arc F live-subset ratchet: real happy-path POSTs.

Mirrors backend_live_invoke.py (Arc E). The B0 sweep proves reachability via GET
health probes; this drives a REAL valid-payload POST through each gated compute
route's FULL path (pydantic parse -> auth Depends -> handler -> _to_jsonable -> 200)
and spot-checks a value in the body. That flips F1/F5 cells from oracle/proof to
LIVE (the forward-only live-subset ratchet) — the value itself is still pinned by
the hermetic oracles; this proves the wire end-to-end on the running service.

The host port 8000 is unmapped, so we POST from INSIDE the container via
`docker exec workhive_python_api python -c`. PYTHON_API_KEY is unset on the running
container, so the gate ALLOWS (configure-to-enable) — which also live-proves the
keyless-allow branch of require_api_key.

USAGE: python tools/python_api_live_invoke.py   # writes python_api_live_invoke.json
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "python_api_live_invoke.json"
CONTAINER = "workhive_python_api"

# route -> (payload, body_key_that_must_be_present_for_a_happy_200)
# payloads are valid-schema and chosen to return 200 with a real result body.
CASES = {
    "/calculate": (
        {"calc_type": "Solar PV System",
         "inputs": {"voc_stc": 100, "tempCoeff_voc": -0.29, "t_min_c": 8,
                    "inverter_vdc_max": 1000, "system_kw": 5}},
        "results"),
    "/project/progress": (
        {"project": {"id": "p1", "budget_php": 100000},
         "items": [{"id": "A", "title": "A", "estimated_hours": 16, "predecessors": []},
                   {"id": "B", "title": "B", "estimated_hours": 24, "predecessors": ["A"]}],
         "links": [], "logs": []},
        "critical_path"),
    "/reliability/pf-interval": (
        {"readings": [{"ts": "2026-01-01T00:00:00Z", "value": 1.0},
                      {"ts": "2026-01-11T00:00:00Z", "value": 5.0}],
         "p_threshold": 2.0, "f_threshold": 4.0, "direction": "above"},
        "recommended_interval_days"),
    "/reliability/weibull": (
        {"failures": [10.0, 20.0, 30.0, 40.0, 55.0], "censored": [60.0]},
        "beta"),
    "/analytics": (
        {"phase": "descriptive",
         "inputs": {"logbook_entries": [], "pm_completions": [], "pm_scope_items": [],
                    "inv_transactions": [], "period_days": 30}},
        None),  # any 200 body is a happy path (descriptive of empty data)
    "/ml/predict": (
        {"features": {"days_since_last_fault": 30, "fault_count_90d": 0, "pm_overdue": 0,
                      "criticality": 1, "mtbf_days": 100, "stockout_count": 0}},
        "risk_score"),
    # P4 diagrams — browser-direct SVG route. A valid diagram_type returns {svg}; this proves the
    # full path (pydantic DiagramRequest -> handler -> SVG -> JSON) live end-to-end (U1/F3/F5/F1).
    "/diagram": (
        {"diagram_type": "Pump Sizing (TDH)",
         "inputs": {"flow_rate": 10, "static_head": 20, "project_name": "UFAI live probe"},
         "results": {}},
        "svg"),
    # P8 app-shell — /tts/speak is a real browser-direct compute route (Edge-TTS). A 200 with a
    # cache url proves the shell's pydantic+handler+backing-service path live (U1/F3).
    "/tts/speak": (
        {"text": "Arc F live probe", "persona": "zaniah"},
        "url"),
    # P7 sensors — the NEW pure-compute Z-score route (no DB). A 200 with a z proves the full path
    # (ZScoreRequest pydantic -> zscore_compute -> _to_jsonable) live end-to-end (U1/F1/F3/F5).
    "/sensors/zscore": (
        {"values": [10, 11, 9, 10, 10, 9, 11, 10], "latest": 50},
        "z"),
}


def run_invokes() -> dict:
    cases_json = json.dumps({k: v[0] for k, v in CASES.items()})
    keys_json = json.dumps({k: v[1] for k, v in CASES.items()})
    script = (
        "import urllib.request,json,urllib.error\n"
        f"CASES=json.loads({cases_json!r})\n"
        f"KEYS=json.loads({keys_json!r})\n"
        "out={}\n"
        "for path,payload in CASES.items():\n"
        "  body=json.dumps(payload).encode()\n"
        "  req=urllib.request.Request('http://127.0.0.1:8000'+path,data=body,\n"
        "      headers={'Content-Type':'application/json'},method='POST')\n"
        "  rec={}\n"
        "  try:\n"
        "    r=urllib.request.urlopen(req,timeout=30); rec['code']=r.getcode()\n"
        "    d=json.loads(r.read().decode('utf-8','replace'))\n"
        "    k=KEYS[path]\n"
        "    rec['has_key']=(k is None) or (isinstance(d,dict) and k in d)\n"
        "    rec['sample']=str({kk:d[kk] for kk in list(d)[:3]} if isinstance(d,dict) else d)[:160]\n"
        "  except urllib.error.HTTPError as e:\n"
        "    rec['code']=e.code; rec['has_key']=False; rec['sample']=e.read()[:140].decode('utf-8','replace')\n"
        "  except Exception as e:\n"
        "    rec['code']='ERR'; rec['has_key']=False; rec['sample']=str(e)[:140]\n"
        "  out[path]=rec\n"
        "print(json.dumps(out))\n"
    )
    try:
        proc = subprocess.run(["docker", "exec", CONTAINER, "python", "-c", script],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
        if proc.returncode == 0:
            return json.loads(proc.stdout.strip().splitlines()[-1])
        return {"_error": proc.stderr[-300:]}
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}


def main() -> int:
    res = run_invokes()
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("=" * 66)
    print("  Arc F — live happy-path POST round-trips (docker exec :8000)")
    print("=" * 66)
    if "_error" in res:
        print(f"  ERROR: {res['_error']}")
        return 1
    ok = 0
    for path, rec in res.items():
        happy = rec.get("code") == 200 and rec.get("has_key")
        ok += 1 if happy else 0
        mark = "OK " if happy else ".. "
        print(f"  [{mark}] POST {path:26} -> {rec.get('code')}  {rec.get('sample','')[:70]}")
    print(f"\n  {ok}/{len(res)} routes returned a happy 200 (live full-path: pydantic+auth-allow+handler)")
    print(f"  wrote {OUT.name}")
    return 0 if ok == len(res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
