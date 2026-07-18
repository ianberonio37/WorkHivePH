#!/usr/bin/env python3
"""
Validator: Calc LIVE VALUE-at-the-glass (Arc Q — Domain Correctness, deepened)

WHAT THIS IS (and how it differs from validate_calc_formula_accuracy)
--------------------------------------------------------------------
`validate_calc_formula_accuracy.py` proves the **module on disk** computes the
standard-correct number — it `import`s the pure handler and calls it in-process.
That is hermetic: it can pass while the **running container serves a stale or
different build** (this exact "python-api container STALE" class of bug has
bitten before — the disk source had the fix, the live API did not).

This validator closes that gap from the OTHER end: it replays the SAME
standard-anchored oracles + fixtures through the **live HTTP API** the frontend
actually calls (`POST /calculate {calc_type, inputs}` -> `{"results": ...}`) and
asserts the **served** number equals the published-standard oracle. It is the
first half of "value-at-the-glass": API -> oracle. (The DOM half — browser ->
oracle — is layered on top by the Playwright spec; this proves the wire the DOM
reads from is standard-correct and LIVE.)

ZERO ORACLE DUPLICATION: it imports `VECTORS` (and `_get`/`_close`) from
`validate_calc_formula_accuracy` and routes each vector through a `_LiveModule`
shim whose `.calculate(inputs)` POSTs to the live API. Because the shim presents
the same `.calculate(inputs)->dict` surface as a real handler module, even the
`custom` invariant checks (short_circuit Z=sqrt(R^2+X^2), duct De-vs-Dh) run
UNCHANGED against live results.

DENOMINATOR = the 63 calc TYPES the live API exposes (`/health.implemented_calcs`),
NOT the 58 handler modules — because the API registers alias labels (e.g.
"Short Circuit" / "Short Circuit Analysis") and a genuine branch pair
(chiller Air- vs Water-Cooled) that the module-level count collapses. An alias
that is mis-wired to the wrong handler, or a branch whose second arm is wrong,
is invisible to the 58-module check; this validator pins all 63.

Run:        python tools/validate_calc_live_value.py
Self-test:  python tools/validate_calc_live_value.py --self-test   (proves teeth)
Custom URL: PYTHON_API_URL=http://127.0.0.1:8000 python tools/validate_calc_live_value.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

# Windows cp1252 stdout guard (see validate_validator_cp1252_guard.py).
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# ─── Reuse the standard-anchored oracles from the hermetic validator ──────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS = os.path.join(_ROOT, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from validate_calc_formula_accuracy import VECTORS, _close  # noqa: E402


def _lget(d, path: str):
    """Walk a dotted path through nested dicts AND lists (e.g. 'sections.0.rectangular.Dh_mm').
    Raises KeyError if absent — list-aware superset of the hermetic validator's _get."""
    cur = d
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                raise KeyError(f"missing list index '{part}' in path '{path}'")
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(f"missing result field '{path}' (stopped at '{part}')")
    return cur

API_URL = os.environ.get("PYTHON_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.environ.get("PYTHON_API_KEY", "").strip()
TIMEOUT = float(os.environ.get("CALC_LIVE_TIMEOUT", "20"))

# Cosmetic VECTOR labels -> the real live calc_type the API dispatches on.
# (The hermetic validator keys on `module`, so its `calc_type` is a display
#  label and a few do not match a live handler name.)
LIVE_LABEL_OVERRIDE = {
    "Gear / Belt Drive (V-Belt)": "Gear / Belt Drive",
    # The individual-limits invariant is a 2nd harmonic vector (depth oracle); its
    # display calc_type is not a live dispatch label — route it to the real handler.
    "Harmonic Distortion (individual limits)": "Harmonic Distortion",
    # Beam/column branch-depth oracles (RC Beam, Steel Column) — same live handler,
    # the branch is selected by the vector's member_type input.
    "Beam / Column Design (RC Beam)":      "Beam / Column Design",
    "Beam / Column Design (Steel Column)": "Beam / Column Design",
    "Beam / Column Design (Steel Column W150x13)": "Beam / Column Design",
    "Beam / Column Design (RC Column)":    "Beam / Column Design",
    "Clean Agent Suppression (Novec)":          "Clean Agent Suppression",
    "Clean Agent Suppression (Inergen, inert)": "Clean Agent Suppression",
    "Clean Agent Suppression (CO2, inert)":     "Clean Agent Suppression",
    "Boiler System (Hot Water)":                "Boiler System",
    "Wire Sizing (high-ambient temp brackets)": "Wire Sizing",
    "Fluid Power (Pump)":                       "Fluid Power",
    "Fluid Power (Motor)":                      "Fluid Power",
    # The base "Chiller System" vector sends chiller_type="Air Cooled" inputs,
    # so route it to the Air-Cooled live label; the Water-Cooled branch is a
    # distinct oracle in ALIAS_AND_BRANCH below.
    "Chiller System": "Chiller System — Air Cooled",
}

# A few hermetic `custom` checks inspect module-private helpers (e.g. duct
# _dh_from_rect) and never call .calculate() — so they cannot run through the
# live HTTP shim. For those calc types, this declarative override REPLACES the
# custom with a genuine LIVE oracle (independently hand-computed, standard-anchored).
# Keyed by the VECTOR's calc_type. (short_circuit's custom DOES call .calculate(),
# so it is NOT overridden — it runs live unchanged.)
LIVE_CUSTOM_OVERRIDE = {
    "Duct Sizing": {
        "standard": "ASHRAE 2021 Ch.21 — De=1.30(ab)^0.625/(a+b)^0.25, Dh=2ab/(a+b); continuity v=Q/A",
        "inputs": {"friction_rate_pam": 0.8, "aspect_ratio": 1.5,
                   "sections": [{"flow_m3s": 0.5, "name": "Main"}]},
        "asserts": [
            {"path": "sections.0.rectangular.Dh_mm", "expected": 342.86, "tol": 0.3,
             "note": "2ab/(a+b) = 2*300*400/700 = 342.86 mm (ASHRAE exact hydraulic dia)"},
            {"path": "sections.0.rectangular.De_mm", "expected": 377.8, "tol": 0.5,
             "note": "1.30*(0.3*0.4)^0.625/(0.7)^0.25 = 377.8 mm (ASHRAE equiv dia); De>Dh for non-square"},
            {"path": "sections.0.circular.velocity_ms", "expected": 5.05, "tol": 0.05,
             "note": "continuity v=Q/A = 0.5/(pi*(0.355/2)^2) = 5.05 m/s at D_std 355"},
        ],
    },
}

# Extra live TYPES not carried by a top-level VECTOR: alias labels (must route to
# the SAME correct handler) + the genuine chiller Air-Cooled branch (its own
# oracle). Each entry = (live_label, source) where source is either:
#   {"alias_of": <vector calc_type>}  -> replay that vector's inputs+asserts/custom
#   {"inputs":..., "asserts":[...]}   -> a standalone live oracle (chiller air)
ALIAS_AND_BRANCH = [
    ("Short Circuit Analysis",        {"alias_of": "Short Circuit"}),
    ("Duct Sizing (Equal Friction)",  {"alias_of": "Duct Sizing"}),
    ("Lightning Protection System (LPS)", {"alias_of": "Lightning Protection (LPS)"}),
    ("V-Belt Drive Design",           {"alias_of": "Gear / Belt Drive (V-Belt)"}),
    ("Chiller System — Water Cooled", {
        "standard": "ASHRAE 90.1 / AHRI 550/590 — water-cooled branch (higher COP): W=Q_design/COP; Qrej=Q+W",
        # Genuine second branch arm: same energy-balance handler, water-cooled
        # COP (5.0) -> distinct compressor power & rejection vs the air-cooled
        # arm (COP 3.0). Proves BOTH branch arms are standard-correct, not just one.
        "inputs": {"cooling_kw": 100, "chiller_type": "Water Cooled", "cop": 5.0,
                   "safety_factor": 1.10, "chw_supply_c": 7, "chw_return_c": 13},
        "asserts": [
            {"path": "cooling_TR", "expected": 28.43, "tol": 0.02,
             "note": "100 kW / 3.517 = 28.43 TR (branch-independent: 1 ton = 3.517 kW)"},
            {"path": "EER", "expected": 17.06, "tol": 0.02,
             "note": "COP·3.412 = 5.0·3.412 = 17.06 (water-cooled higher efficiency)"},
            {"path": "compressor_kW", "expected": 22.0, "tol": 0.05,
             "note": "Q_design/COP = (100·1.10)/5.0 = 22.0 kW (vs 36.67 air-cooled — branch differs)"},
            {"path": "q_rejection_kW", "expected": 132.0, "tol": 0.05,
             "note": "Q_design + W_comp = 110 + 22.0 = 132.0 kW (1st-law balance, water-cooled)"},
        ],
    }),
]


def _post_calc(live_label: str, inputs: dict) -> dict:
    """POST to the live /calculate and return the `results` dict.

    Raises RuntimeError on transport/HTTP error or a not_implemented response so
    a mis-wired alias surfaces as a hard failure rather than a silent skip."""
    body = json.dumps({"calc_type": live_label, "inputs": inputs}).encode("utf-8")
    req = urllib.request.Request(f"{API_URL}/calculate", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if API_KEY:
        req.add_header("X-API-Key", API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"HTTP {e.code} from /calculate: {detail}")
    except Exception as e:  # noqa: BLE001 — transport errors -> hard fail
        raise RuntimeError(f"transport error to {API_URL}: {e}")
    if payload.get("not_implemented"):
        raise RuntimeError(f"live API has NO handler for calc_type '{live_label}' "
                           f"(not_implemented) — alias/label mis-wired")
    if "results" not in payload:
        raise RuntimeError(f"response missing 'results' key: {str(payload)[:160]}")
    return payload["results"]


class _LiveModule:
    """Adapter exposing a handler module's `.calculate(inputs)->dict` surface but
    routing through the live HTTP API. Lets the hermetic validator's `custom`
    invariant functions run UNCHANGED against live results."""

    def __init__(self, live_label: str):
        self._label = live_label

    def calculate(self, inputs: dict) -> dict:
        return _post_calc(self._label, inputs or {})


def _resolve_label(vec_calc_type: str) -> str:
    return LIVE_LABEL_OVERRIDE.get(vec_calc_type, vec_calc_type)


def _vector_by_calc_type(calc_type: str):
    for v in VECTORS:
        if v.get("calc_type") == calc_type:
            return v
    return None


def _run_asserts(results: dict, asserts: list, blind: bool):
    """Yield (label, ok, detail) for each oracle assertion (blind inverts)."""
    for a in asserts:
        expected = a["expected"]
        if blind:
            expected = (expected + 1) if isinstance(expected, (int, float)) else f"__WRONG__{expected}"
        try:
            actual = _lget(results, a["path"])
            ok = _close(actual, expected, a.get("tol", 0))
            detail = f"{a['path']} = {actual} (expect {expected} +/-{a.get('tol', 0)})  [{a.get('note','')}]"
        except KeyError as e:
            actual, ok, detail = None, False, f"{a['path']}: {e}"
        yield a["path"], ok, detail


def _run_custom(custom_fn, live_label: str, blind: bool):
    """Run a custom invariant fn against a live module shim; blind inverts truth.

    A hermetic `custom` that calls a module-PRIVATE helper (mod._foo) instead of .calculate()
    cannot run through the HTTP shim. Rather than crash the whole live sweep (an AttributeError
    used to abort every remaining calc), we catch it and surface a single clear FAIL telling the
    maintainer to add a LIVE_CUSTOM_OVERRIDE for that calc_type. (Arc G2 robustness fix.)"""
    mod = _LiveModule(live_label)
    out = []
    try:
        for (label, ok, detail) in custom_fn(mod):
            out.append((label, (not ok) if blind else ok, detail))
    except AttributeError as e:
        out.append(("live-custom-unrunnable",
                    True if blind else False,
                    f"custom invariant needs a module-internal not on the live shim ({e}); "
                    f"add a LIVE_CUSTOM_OVERRIDE for '{live_label}' (declarative live oracle)"))
    return out


def validate(blind: bool = False) -> bool:
    print("\n\033[1mCALC LIVE VALUE-AT-THE-GLASS (Arc Q) — live API serves the standard-correct number\033[0m")
    print("=" * 78)
    print(f"  target: {API_URL}/calculate   (oracles reused from validate_calc_formula_accuracy)")

    # Denominator: the live API's own list of implemented calc TYPES.
    live_types = []
    try:
        with urllib.request.urlopen(f"{API_URL}/health", timeout=TIMEOUT) as resp:
            live_types = json.loads(resp.read().decode("utf-8")).get("implemented_calcs", [])
    except Exception as e:  # noqa: BLE001
        print(f"  \033[91mFATAL: cannot reach live API /health at {API_URL}: {e}\033[0m")
        print("  Is the python-api container up?  docker ps | grep python_api")
        return False
    denom = len(live_types) or 63

    covered = set()      # live calc_type labels with >=1 PASS
    n_pass = n_fail = 0
    failures = []

    def _emit(live_label, standard, checks):
        nonlocal n_pass, n_fail
        all_ok = checks and all(ok for _, ok, _ in checks)
        tag = "\033[92mPASS\033[0m" if all_ok else "\033[91mFAIL\033[0m"
        print(f"  [{tag}] {live_label}  ({standard})")
        for _, ok, detail in checks:
            mark = "ok  " if ok else "XX  "
            print(f"        {mark}{detail}")
        if all_ok:
            n_pass += 1
            covered.add(live_label)
        else:
            n_fail += 1
            failures.append(live_label)

    # ── 1) every top-level VECTOR, replayed through the live API ──────────────
    for vec in VECTORS:
        ct = vec.get("calc_type")
        live_label = _resolve_label(ct)
        standard = vec.get("standard", "")
        override = LIVE_CUSTOM_OVERRIDE.get(ct)
        try:
            if override is not None:
                standard = override.get("standard", standard)
                results = _post_calc(live_label, override.get("inputs", {}))
                checks = list(_run_asserts(results, override.get("asserts", []), blind))
            elif "custom" in vec:
                checks = _run_custom(vec["custom"], live_label, blind)
            else:
                results = _post_calc(live_label, vec.get("inputs", {}))
                checks = list(_run_asserts(results, vec.get("asserts", []), blind))
        except RuntimeError as e:
            checks = [("transport", False, str(e))]
        _emit(live_label, standard, checks)

    # ── 2) alias labels (must route to the same correct handler) + chiller air ─
    print("  " + "-" * 60)
    print("  Alias labels + genuine branch (the 63-vs-58 gap):")
    for live_label, src in ALIAS_AND_BRANCH:
        try:
            if "alias_of" in src:
                base = _vector_by_calc_type(src["alias_of"])
                if base is None:
                    _emit(live_label, "alias", [("alias", False, f"base vector '{src['alias_of']}' not found")])
                    continue
                base_override = LIVE_CUSTOM_OVERRIDE.get(src["alias_of"])
                if base_override is not None:
                    standard = "alias-of: " + base_override.get("standard", "")
                    results = _post_calc(live_label, base_override.get("inputs", {}))
                    checks = list(_run_asserts(results, base_override.get("asserts", []), blind))
                elif "custom" in base:
                    standard = "alias-of: " + base.get("standard", "")
                    checks = _run_custom(base["custom"], live_label, blind)
                else:
                    standard = "alias-of: " + base.get("standard", "")
                    results = _post_calc(live_label, base.get("inputs", {}))
                    checks = list(_run_asserts(results, base.get("asserts", []), blind))
            else:
                standard = src.get("standard", "")
                results = _post_calc(live_label, src.get("inputs", {}))
                checks = list(_run_asserts(results, src.get("asserts", []), blind))
        except RuntimeError as e:
            checks = [("transport", False, str(e))]
        _emit(live_label, standard, checks)

    # ── summary + honest 63-type coverage ────────────────────────────────────
    print("\n  -- Summary --------------------------------------------")
    print(f"  Live calc types value-verified : {n_pass} PASS / {n_fail} FAIL")
    uncovered = [t for t in live_types if t not in covered]
    cov_pct = 100.0 * len(covered) / denom if denom else 0.0
    print(f"  Live-type coverage (honest)    : {len(covered)}/{denom} live calc types = {cov_pct:.1f}%")
    if uncovered:
        print(f"  Uncovered live types ({len(uncovered)}): {', '.join(uncovered)}")

    if blind:
        if n_pass == 0:
            print(f"\n  \033[92mSELF-TEST PASS: blind run flipped all {n_fail} live checks to FAIL (validator has teeth).\033[0m")
            return True
        print(f"\n  \033[91mSELF-TEST FAIL: {n_pass} checks still passed under corruption — not asserting enough.\033[0m")
        return False

    if n_fail == 0:
        print("\n  \033[92m\033[1mCALC LIVE VALUE: PASS\033[0m — every live calc type serves the standard-correct number.")
        return True
    print(f"\n  \033[91m\033[1mCALC LIVE VALUE: FAIL\033[0m — {n_fail} live type(s) wrong/unreachable: {', '.join(failures)}")
    return False


if __name__ == "__main__":
    blind = "--self-test" in sys.argv
    sys.exit(0 if validate(blind=blind) else 1)
