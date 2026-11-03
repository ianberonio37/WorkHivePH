#!/usr/bin/env python3
"""replay_calc_oracle_on_prod.py - after a release, is the engine PRODUCTION serves the oracle-verified one? (M5, 2026-11-03)

validate_calc_formula_accuracy.py pins every calculator to hand-computed, standard-anchored vectors - but it imports the
python-api modules from THIS checkout. Wave ED's T1 rows ask the other half: does the engine a person is SERVED
(engineering-calc-agent on production -> Render's python-api) give those same answers? That is only true once Render has
deployed the push, so it is a post-release check, run against production by plain HTTP:

  each vector with plain inputs is POSTed to production's engineering-calc-agent as {calc_type, inputs}; the reply must
  come from the Python engine (source: python - not the unchecked TypeScript fallback) and every assertion must hold,
  resolved and compared by the ORACLE'S OWN functions (_get, _close, expected_expr) so this can never drift from it.

★PACED UNDER THE RATE LIMIT. Production's edge functions ceiling requests per address; at 0.3 s apart nine of 38 calls
came back 429 on the first run - the platform protecting itself, not a defect. Calls are spaced and a 429 is retried
after a back-off, and a vector that still cannot be asked is reported UNASKED, never counted as passing or failing.

  python tools/replay_calc_oracle_on_prod.py [--match "Wire Sizing,Duct"] [--pace 4]
  receipt: calc_oracle_prod_replay.json
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROD = "https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/engineering-calc-agent"
KEY = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"   # the publishable key the frontend ships (public by design)
RECEIPT = ROOT / "calc_oracle_prod_replay.json"
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


def oracle():
    spec = importlib.util.spec_from_file_location("vcfa", ROOT / "tools" / "validate_calc_formula_accuracy.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def calc_types() -> dict:
    """module -> the calc_type names python-api's main.py routes to it."""
    main = (ROOT / "python-api" / "main.py").read_text(encoding="utf-8")
    fn_by_type = dict(re.findall(r'handlers\["([^"]+)"\]\s*=\s*(\w+)', main))
    mod_by_fn = {fn: mod for mod, fn in re.findall(r"from\s+calcs\.(\w+)\s+import\s+\w+\s+as\s+(\w+)", main)}
    out: dict = {}
    for t, fn in fn_by_type.items():
        out.setdefault(mod_by_fn.get(fn, "?"), []).append(t)
    return out


def pick_type(vec: dict, types: list) -> str | None:
    for word in ("Air", "Water"):
        hit = [t for t in types if word in t and word in vec["calc_type"]]
        if hit:
            return hit[0]
    return types[0] if types else None


class Exhausted(Exception):
    """The caller's hourly/daily budget is spent; the server says when it resets."""


def ask(calc_type: str, inputs: dict, pace: float) -> tuple[dict | None, str]:
    body = json.dumps({"calc_type": calc_type, "inputs": inputs}).encode()
    for attempt in range(3):
        req = urllib.request.Request(PROD, data=body, method="POST", headers={
            "Content-Type": "application/json", "apikey": KEY, "Authorization": "Bearer " + KEY,
            "User-Agent": "workhive-release-verify/1.0"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=90).read()), ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # ★the server states its window: engineering-calc-agent allows 50 calls an hour and 300 a day per
                # caller (_shared/rate-limit.ts) and sends Retry-After. A short wait is waited out; a long one ends the
                # run with the reset time, instead of backing off blindly until a timeout kills the run unreported
                wait = int(e.headers.get("Retry-After") or 0)
                if 0 < wait <= 90 and attempt < 2:
                    time.sleep(wait + 1)
                    continue
                raise Exhausted(f"rate limit: the server's window resets in {wait or '?'} s") from None
            return None, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 - a network fault is UNASKED, never a verdict
            return None, type(e).__name__
    return None, "HTTP 429 after retries"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="", help="comma-separated substrings of the vectors' calc_type")
    ap.add_argument("--pace", type=float, default=4.0, help="seconds between calls (the edge's per-address ceiling)")
    a = ap.parse_args()
    m = oracle()
    types = calc_types()
    words = [w.strip().lower() for w in a.match.split(",") if w.strip()]
    vecs = [v for v in m.VECTORS if v.get("inputs") and "custom" not in v
            and (not words or any(w in v["calc_type"].lower() for w in words))]
    rows, held, stopped = [], 0, ""
    for i, v in enumerate(vecs):
        ct = pick_type(v, types.get(v["module"].replace("calcs.", ""), []))
        if stopped:
            rows.append({"vector": v["calc_type"], "calc_type": ct, "verdict": "UNASKED", "why": stopped})
            continue
        if i:
            time.sleep(a.pace)
        try:
            reply, err = ask(ct, v["inputs"], a.pace) if ct else (None, "no calc_type routes to this module")
        except Exhausted as e:
            stopped = str(e)
            rows.append({"vector": v["calc_type"], "calc_type": ct, "verdict": "UNASKED", "why": stopped})
            continue
        if reply is None:
            rows.append({"vector": v["calc_type"], "calc_type": ct, "verdict": "UNASKED", "why": err})
            continue
        out = reply.get("results") or {}
        fails = []
        for x in v["asserts"]:
            got = m._get(out, x["path"])
            if "expected_expr" in x:
                names = {k: val for k, val in out.items() if isinstance(val, (int, float)) and not isinstance(val, bool)}
                try:
                    exp = round(float(eval(x["expected_expr"], {"__builtins__": {}}, names)), 6)  # the oracle's own rule
                except Exception as e:  # noqa: BLE001
                    fails.append(f"{x['path']}: expected_expr could not be evaluated ({type(e).__name__})")
                    continue
            else:
                exp = x["expected"]
            if not m._close(got, exp, x["tol"]):
                fails.append(f"{x['path']} = {got} (expected {exp} +/-{x['tol']})")
        verdict = "PASS" if reply.get("source") == "python" and not fails else "FAIL"
        if reply.get("source") != "python":
            fails.insert(0, f"answered by {reply.get('source')!r}, not the python engine")
        held += verdict == "PASS"
        rows.append({"vector": v["calc_type"], "calc_type": ct, "verdict": verdict, "source": reply.get("source"),
                     "fails": fails})
    asked = [r for r in rows if r["verdict"] != "UNASKED"]
    RECEIPT.write_text(json.dumps({"_doc": "GENERATED by tools/replay_calc_oracle_on_prod.py - the oracle's vectors asked "
                                           "of PRODUCTION's engineering-calc-agent",
                                   "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "endpoint": PROD,
                                   "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print(f"production replay: {held}/{len(asked)} vectors hold on the served python engine "
          f"({len(rows) - len(asked)} unasked) -> {RECEIPT.name}")
    for r in rows:
        if r["verdict"] != "PASS":
            print(f"  {r['verdict']:8} {r['vector'][:70]}  {'; '.join(r.get('fails') or [r.get('why', '')])[:150]}")
    return 0 if asked and held == len(asked) and len(asked) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
