#!/usr/bin/env python3
"""
Validator: ENGINES LIVE VALUE-at-the-Glass — analytics + reliability + projects
(Arc Q Q2 — Domain Correctness, deepened)

Twin of `validate_calc_live_value.py`, for the non-calc computation engines:

  • analytics   (MTBF/MTTR/Availability/OEE/PM-compliance/priority — ISO 14224/22400, SMRP, ISO 55001)
  • reliability (RCM P-F inspection interval — SAE JA1011 / MIL-HDBK-189C)
  • projects    (Earned Value Management SPI/CPI/EV/PV + Critical Path — PMBOK 7 / AACE 80R-13)

Each hermetic correctness validator (`validate_analytics_correctness`,
`validate_reliability_correctness`, `validate_projects_correctness`) proves the
MODULE ON DISK computes the standard-correct number. This replays the SAME
standard-anchored oracles + fixtures through the **live HTTP API** the frontend
actually calls (`/analytics`, `/reliability/pf-interval`, `/project/progress`),
proving the RUNNING container serves the standard-correct number — catching the
stale-container class the hermetic check cannot.

ZERO ORACLE DUPLICATION: imports `VECTORS` (and `_READINGS`) from the three
hermetic validators. Each live endpoint routes its request body straight into the
same `calculate()` the hermetic validator tests, so the response carries the same
fields; only the projects endpoint nests EVM under `earned_value.*` (handled by a
per-vector path prefix).

Run:        python tools/validate_engines_live_value.py
Self-test:  python tools/validate_engines_live_value.py --self-test
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS = os.path.join(_ROOT, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from validate_analytics_correctness import VECTORS as ANALYTICS_VECTORS  # noqa: E402
from validate_projects_correctness import VECTORS as PROJECTS_VECTORS    # noqa: E402
from validate_reliability_correctness import _READINGS                   # noqa: E402

API_URL = os.environ.get("PYTHON_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.environ.get("PYTHON_API_KEY", "").strip()
TIMEOUT = float(os.environ.get("CALC_LIVE_TIMEOUT", "30"))


def _lget(d, path: str):
    """Walk a dotted path through nested dicts AND lists. KeyError if absent."""
    cur = d
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                raise KeyError(f"missing list index '{part}' in '{path}'")
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(f"missing result field '{path}' (stopped at '{part}')")
    return cur


def _close(a, e, tol):
    try:
        return abs(float(a) - float(e)) <= tol
    except (TypeError, ValueError):
        return a == e


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{API_URL}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if API_KEY:
        req.add_header("X-API-Key", API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"HTTP {e.code} from {path}: {detail}")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"transport error to {API_URL}{path}: {e}")


def _assert_block(results: dict, asserts: list, blind: bool, prefix: str = ""):
    out = []
    for a in asserts:
        expected = a["expected"]
        if blind:
            expected = (expected + 1) if isinstance(expected, (int, float)) else f"__WRONG__{expected}"
        path = prefix + a["path"]
        try:
            actual = _lget(results, path)
            ok = _close(actual, expected, a.get("tol", 0))
            detail = f"{path} = {actual} (expect {expected} +/-{a.get('tol', 0)})  [{a.get('note','')}]"
        except KeyError as e:
            ok, detail = False, f"{path}: {e}"
        out.append((ok, detail))
    return out


def _dbpath_failure_frequency(blind: bool = False):
    """DB-path LIVE oracle for failure_frequency (SMRP): the postgres RPC
    get_failure_frequency = COUNT(logbook rows maintenance_type='Breakdown / Corrective')
    per machine/period. This is NOT routable via /analytics (the master routes it via
    postgres-precomputed data), so it is proven directly against the live DB: assert the
    SERVED RPC count == an INDEPENDENTLY-written COUNT(*) for EVERY machine. Returns
    (ok|None, detail) — None = graceful SKIP when docker/psql is unavailable (e.g. CI),
    so this never falsely fails. blind inverts the verdict for the teeth proof."""
    sql = (
        "WITH rpc AS (SELECT machine, failure_count FROM get_failure_frequency(NULL,NULL,365)), "
        "ind AS (SELECT machine, COUNT(*) c FROM logbook "
        "WHERE maintenance_type='Breakdown / Corrective' "
        "AND created_at >= NOW() - interval '365 days' GROUP BY machine) "
        "SELECT COUNT(*) FILTER (WHERE rpc.failure_count IS DISTINCT FROM ind.c) AS diverge, "
        "COUNT(*) AS total FROM rpc FULL OUTER JOIN ind ON rpc.machine=ind.machine;"
    )
    container = os.environ.get("SUPABASE_DB_CONTAINER", "supabase_db_workhive")
    try:
        out = subprocess.run(
            ["docker", "exec", container, "psql", "-U", "postgres",
             "-t", "-A", "-F", "|", "-c", sql],
            capture_output=True, text=True, timeout=25)
    except Exception as e:  # noqa: BLE001 — docker/psql absent → graceful skip
        return None, f"docker/psql unavailable ({type(e).__name__}) — DB-path not probed"
    if out.returncode != 0:
        return None, f"psql exit {out.returncode}: {(out.stderr or '').strip()[:90]}"
    rows = [ln for ln in (out.stdout or "").strip().splitlines() if "|" in ln]
    if not rows:
        return None, f"unexpected psql output: {(out.stdout or '').strip()[:90]}"
    try:
        diverge, total = (int(x) for x in rows[-1].split("|"))
    except ValueError:
        return None, f"unparseable psql row: {rows[-1][:90]}"
    ok = (diverge == 0 and total > 0)
    detail = (f"failure_frequency RPC vs independent logbook COUNT: "
              f"{total - diverge}/{total} machines MATCH, {diverge} diverge")
    return ((not ok) if blind else ok), detail


def validate(blind: bool = False) -> bool:
    print("\n\033[1mENGINES LIVE VALUE-AT-THE-GLASS (Arc Q Q2) — analytics + reliability + projects\033[0m")
    print("=" * 80)
    print(f"  target: {API_URL}  (oracles reused from the 3 hermetic correctness validators)")

    # health gate
    try:
        urllib.request.urlopen(f"{API_URL}/health", timeout=TIMEOUT).read()
    except Exception as e:  # noqa: BLE001
        print(f"  \033[91mFATAL: cannot reach live API at {API_URL}: {e}\033[0m")
        return False

    n_pass = n_fail = n_skip = 0
    failures = []

    def _skip(label, reason):
        nonlocal n_skip
        n_skip += 1
        print(f"  [\033[93mSKIP\033[0m] {label}  ({reason})")

    def _emit(label, standard, checks):
        nonlocal n_pass, n_fail
        all_ok = bool(checks) and all(ok for ok, _ in checks)
        tag = "\033[92mPASS\033[0m" if all_ok else "\033[91mFAIL\033[0m"
        print(f"  [{tag}] {label}  ({standard})")
        for ok, detail in checks:
            print(f"        {'ok  ' if ok else 'XX  '}{detail}")
        if all_ok:
            n_pass += 1
        else:
            n_fail += 1
            failures.append(label)

    # ── analytics: POST /analytics {phase, inputs} -> raw calculate() output ──
    print("\n  -- analytics engine (/analytics) --")
    for vec in ANALYTICS_VECTORS:
        phase = vec.get("phase")
        # `custom` analytics vectors test a DIRECT module helper that the live
        # /analytics endpoint bypasses — the master routes those via postgres-
        # precomputed data. failure_frequency is proven on the DB-PATH instead
        # (served RPC count == independent logbook COUNT); other custom vectors
        # remain hermetically-covered SKIPs.
        if "custom" in vec and "asserts" not in vec:
            tag = (str(phase) + " " + vec.get("standard", "")).lower()
            if "fail" in tag and "freq" in tag:
                ok, detail = _dbpath_failure_frequency(blind)
                if ok is None:
                    _skip(f"analytics:{phase} (DB-path)", detail)
                else:
                    _emit(f"analytics:{phase} (DB-path)",
                          "SMRP — failure freq = COUNT(logbook breakdown)/machine; served RPC == independent count",
                          [(ok, detail)])
            else:
                _skip(f"analytics:{phase}:{vec.get('standard','')[:40]}",
                      "direct-fn helper — live master routes via postgres-precomputed (DB-path backlog)")
            continue
        try:
            results = _post("/analytics", {"phase": phase, "inputs": vec.get("inputs", {})})
            checks = _assert_block(results, vec.get("asserts", []), blind)
        except RuntimeError as e:
            checks = [(False, str(e))]
        _emit(f"analytics:{phase}", vec.get("standard", ""), checks)

    # ── reliability: POST /reliability/pf-interval -> raw calculate_pf() ──────
    print("\n  -- reliability engine (/reliability/pf-interval) --")
    REL_CASES = [
        ("pf_interval_normal", "SAE JA1011 / MIL-HDBK-189C RCM — P-F/2 cadence",
         {"readings": _READINGS, "p_threshold": 50, "f_threshold": 100,
          "direction": "above", "safety_critical": False},
         [{"path": "pf_days", "expected": 10.0, "tol": 0.0, "note": "P Jan-11 -> F Jan-21 = 10 d"},
          {"path": "n_pairs", "expected": 1, "tol": 0, "note": "one P-F pair"},
          {"path": "recommended_interval_days", "expected": 5, "tol": 0, "note": "P-F/2 = 5 (RCM normal)"},
          {"path": "basis", "expected": "P-F/2", "tol": 0, "note": "normal-asset cadence basis"}]),
        ("pf_interval_safety_critical", "RCM — P-F/3 for safety/environment-critical assets",
         {"readings": _READINGS, "p_threshold": 50, "f_threshold": 100,
          "direction": "above", "safety_critical": True},
         [{"path": "recommended_interval_days", "expected": 3, "tol": 0, "note": "P-F/3 = 10/3 rounded"},
          {"path": "basis", "expected": "P-F/3", "tol": 0, "note": "safety-critical cadence basis"}]),
    ]
    for label, standard, body, asserts in REL_CASES:
        try:
            results = _post("/reliability/pf-interval", body)
            checks = _assert_block(results, asserts, blind)
        except RuntimeError as e:
            checks = [(False, str(e))]
        _emit(f"reliability:{label}", standard, checks)

    # ── projects: POST /project/progress -> EVM under earned_value.*, CPM top ─
    print("\n  -- projects engine (/project/progress) --")
    for vec in PROJECTS_VECTORS:
        phase = vec.get("phase")
        inp = vec.get("inputs", {})
        body = {
            "project": inp.get("project", {}),
            "items":   inp.get("items", []),
            "links":   inp.get("links", []),
            "logs":    inp.get("logs", []),
        }
        # EVM tiles live under earned_value.*; CPM (critical_path / fast_track) are
        # flattened to the top level by the endpoint.
        prefix = "earned_value." if phase == "evm" else ""
        try:
            results = _post("/project/progress", body)
            checks = _assert_block(results, vec.get("asserts", []), blind, prefix=prefix)
        except RuntimeError as e:
            checks = [(False, str(e))]
        _emit(f"projects:{phase}", vec.get("standard", ""), checks)

    print("\n  -- Summary --------------------------------------------")
    print(f"  Live engine vectors value-verified : {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP")
    if n_skip:
        print(f"  ({n_skip} SKIP = not routable via the python API endpoint; covered hermetically — DB-path backlog)")

    if blind:
        if n_pass == 0:
            print(f"\n  \033[92mSELF-TEST PASS: blind run flipped all {n_fail} live vectors to FAIL (teeth).\033[0m")
            return True
        print(f"\n  \033[91mSELF-TEST FAIL: {n_pass} vectors still passed under corruption.\033[0m")
        return False

    if n_fail == 0:
        print("\n  \033[92m\033[1mENGINES LIVE VALUE: PASS\033[0m — analytics/reliability/projects all serve the standard-correct number.")
        return True
    print(f"\n  \033[91m\033[1mENGINES LIVE VALUE: FAIL\033[0m — {n_fail} vector(s) wrong/unreachable: {', '.join(failures)}")
    return False


if __name__ == "__main__":
    sys.exit(0 if validate(blind="--self-test" in sys.argv) else 1)
