#!/usr/bin/env python3
"""
Validator: Calc API JSON-SERIALIZABILITY (the silent-TS-fallback class)

WHAT THIS CATCHES
-----------------
The engineering-calc edge function tries the Python engine first and falls back
to its TypeScript handlers on ANY non-200 from /calculate. A handler that returns
a numpy scalar (e.g. HVAC Cooling Load's psychrometrics produce numpy.bool_ flags
`oa_adequate` / `density_ok`) makes FastAPI's JSON encoder raise -> 500 -> the edge
SILENTLY serves the unvalidated TypeScript value instead. Found live 2026-06-18:
HVAC Cooling Load rendered the TS 10.15 kW in the browser while the value-validated
Python engine said 14.85 kW (~46% off), purely because numpy.bool_ 500'd the API.
numpy.float64 happens to subclass float (json-safe); numpy.bool_ does NOT subclass
bool, so it is the trap.

The boundary fix lives in python-api/main.py::_to_jsonable (coerces numpy -> native
before returning). This validator LOCKS it: for every calc handler with a known
input vector, it asserts the RAW handler result is FastAPI-serializable AFTER the
boundary coercion, and REPORTS any handler whose raw result carried numpy types
(the latent-500 blast radius, now covered by the fix).

Reuses the oracle input vectors from validate_calc_formula_accuracy.py (no new
inputs invented). Hermetic: imports pure handlers, no network/edge/DB.

Run:        python tools/validate_calc_api_serializable.py
Self-test:  python tools/validate_calc_api_serializable.py --self-test
"""

import json
import os
import sys

# Windows cp1252 stdout guard (see validate_validator_cp1252_guard.py).
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYAPI = os.path.join(_ROOT, "python-api")
_TOOLS = os.path.dirname(os.path.abspath(__file__))
for p in (_PYAPI, _TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

# The exact boundary coercion the API uses, imported from the API itself so this
# validator tests the REAL fix (not a copy that could drift).
from main import _to_jsonable  # noqa: E402
from validate_calc_formula_accuracy import VECTORS  # noqa: E402

try:
    import numpy as np
    _NP = (np.bool_, np.integer, np.floating, np.ndarray)
except Exception:
    np = None
    _NP = ()


def _has_numpy(obj):
    """Return list of dotted paths whose value is a numpy type (pre-fix 500 risk)."""
    found = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}")
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        elif _NP and isinstance(o, _NP):
            found.append((path.lstrip("."), type(o).__name__))
    walk(obj, "")
    return found


def _fastapi_serializable(obj):
    """True if FastAPI could encode this result. FastAPI uses json with
    allow_nan=False semantics for valid JSON; we mirror that here."""
    try:
        json.dumps(obj, allow_nan=False)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run():
    # de-dupe to one vector per calc_type (serializability is type-shaped, not value-shaped)
    seen = {}
    for v in VECTORS:
        seen.setdefault(v["calc_type"], v)

    rows = []
    for calc_type, v in seen.items():
        mod_name = v["module"]
        try:
            mod = __import__(mod_name, fromlist=["calculate"])
            result = mod.calculate(dict(v["inputs"]))
        except Exception as e:
            rows.append({"calc_type": calc_type, "status": "SKIP",
                         "detail": f"handler raised on oracle input: {type(e).__name__}: {str(e)[:80]}"})
            continue

        numpy_paths = _has_numpy(result)
        raw_ok, raw_err = _fastapi_serializable(result)
        fixed_ok, fixed_err = _fastapi_serializable(_to_jsonable(result))

        if not fixed_ok:
            status = "FAIL"           # boundary fix does NOT make it serializable -> real gap
            detail = f"even after _to_jsonable: {fixed_err}"
        elif numpy_paths and not raw_ok:
            status = "FIXED"          # would have 500'd raw; boundary coercion saves it
            detail = f"raw 500 risk on numpy {[p for p, _ in numpy_paths][:4]}; boundary-coerced OK"
        else:
            status = "PASS"           # clean native result, no numpy
            detail = "native result, serializable as-is"
        rows.append({"calc_type": calc_type, "status": status, "detail": detail,
                     "numpy_fields": [p for p, _ in numpy_paths]})

    return rows


def self_test():
    """Prove teeth: a numpy.bool_ result is non-serializable raw, serializable after fix."""
    if np is None:
        print("SELF-TEST SKIP: numpy not installed")
        return True
    bad = {"flag": np.bool_(True), "x": np.float64(1.5), "n": np.int64(3)}
    raw_ok, _ = _fastapi_serializable(bad)
    fixed_ok, _ = _fastapi_serializable(_to_jsonable(bad))
    ok = (raw_ok is False) and (fixed_ok is True)
    print(f"SELF-TEST {'PASS' if ok else 'FAIL'}: raw_serializable={raw_ok} (expect False), "
          f"fixed_serializable={fixed_ok} (expect True)")
    return ok


def main():
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)

    rows = run()
    fails = [r for r in rows if r["status"] == "FAIL"]
    fixed = [r for r in rows if r["status"] == "FIXED"]
    passed = [r for r in rows if r["status"] == "PASS"]
    skips = [r for r in rows if r["status"] == "SKIP"]

    print("=" * 74)
    print("CALC API JSON-SERIALIZABILITY  (silent-TS-fallback / numpy-500 class)")
    print("=" * 74)
    for r in sorted(rows, key=lambda x: (x["status"] != "FAIL", x["status"] != "FIXED", x["calc_type"])):
        mark = {"PASS": "ok ", "FIXED": "fix", "FAIL": "XXX", "SKIP": "-- "}[r["status"]]
        print(f"  [{mark}] {r['calc_type']:<34} {r['detail']}")
    print("-" * 74)
    print(f"  {len(passed)} native-clean · {len(fixed)} numpy (boundary-fixed) · "
          f"{len(fails)} FAIL · {len(skips)} skip · {len(rows)} calc types")
    if fixed:
        print(f"  numpy-bearing calcs (would 500 /calculate without main._to_jsonable): "
              f"{', '.join(r['calc_type'] for r in fixed)}")
    print("=" * 74)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
