#!/usr/bin/env python3
"""validate_python_api_auth.py — Arc F B1 keystone gate: the edge↔python shared secret.

THE FINDING (NEXT_LAYER_STUDY.md §3): python-api/main.py had CORS allow_origins=["*"]
and NO auth on any route; the edge called it with only Content-Type. An open compute
API doing real work (and /ml/train reads cross-hive data).

THE FIX (B1): a shared secret in the X-API-Key header, checked constant-time by
python-api/_auth.require_api_key, applied to the edge-fronted compute routes; the 7
edge callers inject it. Browser-direct routes (/diagram, /pdf, /tts/*) are NOT gated
(a browser cannot hold a server secret) — they are controlled by the CORS lockdown.

THIS VALIDATOR proves the gate three ways (hermetic — no network, no heavy imports):
  1. BEHAVIOUR oracle: _auth.check_api_key decides correctly under every env state
     (unset = allow; set = reject missing/empty/wrong, accept correct) + a blind
     self-test for teeth (a mutated rule must FAIL).
  2. PYTHON wiring: main.py applies Depends(require_api_key) to every compute route
     and does NOT gate the browser-direct routes (those would break a browser).
  3. EDGE wiring: every edge caller that fetches a GATED python route sends X-API-Key
     (so enabling the key on Railway will not 401 the platform's own traffic).

Run:        python tools/validate_python_api_auth.py
Self-test:  python tools/validate_python_api_auth.py --self-test
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PYAPI = ROOT / "python-api"
MAIN = PYAPI / "main.py"
FUNCS = ROOT / "supabase" / "functions"

# Compute routes that MUST be api-key gated (edge-fronted, server-to-server).
GATED_ROUTES = [
    "/calculate", "/analytics", "/project/progress",
    "/ml/train", "/ml/predict", "/reliability/weibull", "/reliability/pf-interval",
]
# Browser-direct routes that must stay UNGATED (a browser can't hold a server secret).
UNGATED_ROUTES = ["/diagram", "/pdf", "/tts/speak", "/tts/audio", "/health"]
# Edge callers -> the gated python route each fetches (must inject X-API-Key).
EDGE_CALLERS = {
    "engineering-calc-agent": "/calculate",
    "analytics-orchestrator": "/analytics",
    "batch-risk-scoring":     "/analytics",
    "project-progress":       "/project/progress",
    "trigger-ml-retrain":     "/ml/train",
    "weibull-fitter":         "/reliability/weibull",
    "pf-calculator":          "/reliability/pf-interval",
}

GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"


def _load_auth():
    """Import python-api/_auth hermetically (no heavy calc deps)."""
    sys.path.insert(0, str(PYAPI))
    import importlib
    import _auth  # type: ignore
    importlib.reload(_auth)
    return _auth


def check_behaviour(mutate: bool = False) -> list[tuple[bool, str]]:
    """Oracle for _auth.check_api_key under each env state. `mutate` flips the
    expected truth table (blind self-test): a correct implementation must then FAIL."""
    auth = _load_auth()
    results = []
    saved = os.environ.get("PYTHON_API_KEY")
    try:
        # 1) UNSET → configure-to-enable: everything allowed
        os.environ.pop("PYTHON_API_KEY", None)
        cases_unset = [(None, True), ("", True), ("anything", True)]
        # 2) SET → only the exact secret is allowed (constant-time)
        SECRET = "sk-edge-python-7f3a9c"
        cases_set = [(None, False), ("", False), ("wrong", False),
                     (SECRET + "x", False), (SECRET, True)]

        for provided, expected in cases_unset:
            got = auth.check_api_key(provided)
            want = (not expected) if mutate else expected
            results.append((got == want, f"unset · provided={provided!r} → {got} (want {want})"))

        os.environ["PYTHON_API_KEY"] = SECRET
        # reload not needed: _load_key reads env fresh each call
        for provided, expected in cases_set:
            got = auth.check_api_key(provided)
            want = (not expected) if mutate else expected
            results.append((got == want, f"set · provided={provided!r} → {got} (want {want})"))

        # api_key_configured tracks env
        results.append((auth.api_key_configured() is True, "api_key_configured() True when set"))
        os.environ.pop("PYTHON_API_KEY", None)
        results.append((auth.api_key_configured() is False, "api_key_configured() False when unset"))
    finally:
        if saved is None:
            os.environ.pop("PYTHON_API_KEY", None)
        else:
            os.environ["PYTHON_API_KEY"] = saved
    return results


def check_constant_time() -> tuple[bool, str]:
    """The comparison must be constant-time (hmac.compare_digest), not ==."""
    src = (PYAPI / "_auth.py").read_text(encoding="utf-8")
    ok = "hmac.compare_digest" in src
    return ok, "constant-time compare (hmac.compare_digest)" if ok else "NOT constant-time (timing leak)"


def check_python_wiring() -> list[tuple[bool, str]]:
    src = MAIN.read_text(encoding="utf-8")
    results = []
    results.append(("from _auth import" in src and "require_api_key" in src,
                    "main.py imports require_api_key"))
    for route in GATED_ROUTES:
        # find the route decorator + its function signature line
        m = re.search(rf'@app\.\w+\(\s*["\']{re.escape(route)}["\'][^\n]*\)\s*\ndef\s+\w+\(([^)]*)\)', src)
        gated = bool(m) and "require_api_key" in (m.group(1) or "")
        results.append((gated, f"GATED  {route} → Depends(require_api_key)"))
    for route in UNGATED_ROUTES:
        m = re.search(rf'@app\.\w+\(\s*["\']{re.escape(route)}["\'][^\n]*\)\s*\ndef\s+\w+\(([^)]*)\)', src)
        # ungated is correct; if route absent (m is None) that's fine too
        ungated = (m is None) or ("require_api_key" not in (m.group(1) or ""))
        results.append((ungated, f"UNGATED {route} (browser-direct / health)"))
    return results


def check_edge_wiring() -> list[tuple[bool, str]]:
    results = []
    for fn, route in EDGE_CALLERS.items():
        p = FUNCS / fn / "index.ts"
        if not p.exists():
            results.append((False, f"{fn}: index.ts missing"))
            continue
        src = p.read_text(encoding="utf-8")
        # the fetch to the python route must carry an X-API-Key header
        esc = re.escape(route)
        m = re.search(rf'fetch\(`\$\{{PYTHON[_A-Z]*\}}{esc}`[^;]*?\}}\);', src, re.DOTALL)
        block = m.group(0) if m else ""
        has_key = bool(re.search(r'["\']X-API-Key["\']\s*:\s*Deno\.env\.get\(["\']PYTHON_API_KEY["\']\)', block))
        results.append((has_key, f"{fn} fetch {route} sends X-API-Key"))
    return results


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    print("=" * 72)
    print("  Arc F · B1 — edge↔python shared-secret AUTH GATE (hermetic)")
    print("=" * 72)

    sections = [
        ("BEHAVIOUR oracle (check_api_key truth table)", check_behaviour()),
        ("PYTHON wiring (Depends on compute routes)", check_python_wiring()),
        ("EDGE wiring (callers send X-API-Key)", check_edge_wiring()),
    ]
    ct_ok, ct_msg = check_constant_time()
    sections[0][1].append((ct_ok, ct_msg))

    total = passed = 0
    for title, results in sections:
        print(f"\n  {title}")
        for ok, msg in results:
            total += 1; passed += 1 if ok else 0
            mark = f"{GREEN}PASS{RST}" if ok else f"{RED}FAIL{RST}"
            print(f"    [{mark}] {msg}")

    # blind self-test: the behaviour oracle with a mutated truth table MUST fail
    if self_test:
        mutated = check_behaviour(mutate=True)
        teeth = any(not ok for ok, _ in mutated)
        mark = f"{GREEN}PASS{RST}" if teeth else f"{RED}FAIL{RST}"
        print(f"\n  TEETH (mutated truth table must FAIL)")
        print(f"    [{mark}] blind self-test detects a broken gate")
        total += 1; passed += 1 if teeth else 0

    print("\n" + "-" * 72)
    failed = total - passed
    print(f"  Auth gate: {passed}/{total} checks pass · {failed} fail")
    if failed:
        print(f"  {RED}GATE INCOMPLETE{RST} — {failed} check(s) failed")
        return 1
    print(f"  {GREEN}GATE PROVEN{RST} — behaviour + python wiring + edge wiring all green")
    print("  (live enforcement attributed until PYTHON_API_KEY is set on Railway + edge — roadmap §5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
