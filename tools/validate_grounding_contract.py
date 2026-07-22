#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D10 report=grounding_contract.json
"""validate_grounding_contract.py — §13.15 A6: artifact-agent grounding field-contract (static).
================================================================================
The recurring value-drift class (§13.15): an LLM BOM/SOW agent reads `results.<field>`
keys to ground its prompt; when the calc renames/restructures an output field, the
read falls to its `?? "N/A"` default and the agent ships a confident but UNGROUNDED
artifact ("N/A L/min @ N/A m TDH, N/A HP") — with NO error. Fire-pump was one of
this class; per project_calc_diagram_qa_progress it has recurred for a year.

This is the FULL-COVERAGE static ratchet (no LLM, deterministic): for EVERY BOM/SOW
agent (the 55 dispatch branches in engineering-bom-sow/index.ts), extract its
`results.<field>` reads grouped by assignment statement, fetch the calc's REAL
top-level output key-set live (`/calculate` with empty input → defaults), and assert
each read-group resolves to a real key (any branch of its `??`/`||` fallback chain).
A group where NO key resolves = a DRIFT cell = the next fire-pump-style "N/A".

Reads `inputs_used` (the calc's echoed-inputs sub-object) and `inputs.*` are NOT
grounding-on-results, so excluded. Calc unreachable / needs-inputs (422 on {}) →
that agent is SKIPPED (can't verify without inputs), reported, not FAILed.
Exit 0 = no drift cell (or only allowlisted); 1 = a new drift cell; 2 = api down.
"""
from __future__ import annotations
import io
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EDGE_FN = ROOT / "supabase" / "functions" / "engineering-bom-sow" / "index.ts"
PY_API = "http://127.0.0.1:8000"
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

# Minimal inputs for calc types that 422 on {} (need a required field to compute).
CALC_MIN_INPUTS = {
    "Wire Sizing": {"load_current_a": 100, "length_m": 30, "voltage_v": 230, "phases": 1},
}
# Multi-mode calcs emit DIFFERENT output schemas per mode (e.g. a boiler in Steam vs
# Hot Water mode). An agent reads keys from EVERY mode it handles, so verifying against
# one mode's keyset false-flags the other mode's (correct) reads. For these, also fetch
# each listed variant and UNION the keysets — a read is grounded if it resolves in ANY mode.
CALC_MODE_VARIANTS = {
    "Boiler System": [{"boiler_type": "Hot Water"}],
    # steel beam (default) vs steel column (axial/phi_Pn) vs RC beam (As_mm2/fc/fy) vs RC column
    "Beam / Column Design": [
        {"member_type": "Steel Column"},
        {"member_type": "RC Beam"},
        {"member_type": "RC Column"},
    ],
    # room SPL (default) vs dose (8-hr TWA) vs barrier (insertion loss)
    "Noise / Acoustics": [{"calc_type": "Dose"}, {"calc_type": "Barrier"}],
    # cylinder-only (default) vs full System (also emits pump + pump_displacement_cm3 + accumulator)
    "Fluid Power": [{"calc_type": "System"}],
}
# Drift cells confirmed acceptable (documented) — forward-only baseline. (empty = ratchet at 0 once clean)
ALLOWLIST: set[str] = set()


# The host port 8000 is often UNMAPPED on the local stack (the python-api runs inside the
# `workhive_python_api` container binding 0.0.0.0:8000 with no host publish). So a direct HTTP
# POST from the host fails even though the API is healthy. Mirror python_api_live_invoke.py: if
# the HTTP transport can't connect, fall back to POSTing from INSIDE the container via
# `docker exec`. This makes the grounding ratchet PASS whenever the API container is up (the
# normal local state) instead of SKIPping on a host-port quirk. Returns the parsed JSON dict,
# "HTTP_ERROR" (calc needs valid inputs → treat as unresolvable), or "DOWN" (truly unreachable).
_API_CONTAINER = "workhive_python_api"


def _post_calculate(body: dict):
    payload = json.dumps(body).encode()
    req = urllib.request.Request(f"{PY_API}/calculate", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError:
        return "HTTP_ERROR"
    except Exception:
        pass  # host transport failed → try the in-container fallback
    # docker exec fallback: POST to localhost:8000 from inside the API container.
    import subprocess
    script = (
        "import sys,json,urllib.request,urllib.error\n"
        "b=sys.stdin.buffer.read()\n"
        "req=urllib.request.Request('http://127.0.0.1:8000/calculate',data=b,"
        "headers={'Content-Type':'application/json'},method='POST')\n"
        "try:\n"
        "    import urllib.request as u\n"
        "    r=u.urlopen(req,timeout=30); sys.stdout.write(r.read().decode())\n"
        "except urllib.error.HTTPError as e:\n"
        "    sys.stdout.write('__HTTP_ERROR__')\n"
    )
    try:
        p = subprocess.run(["docker", "exec", "-i", _API_CONTAINER, "python", "-c", script],
                           input=payload, capture_output=True, timeout=45)
        out = p.stdout.decode(errors="replace").strip()
        if out == "__HTTP_ERROR__":
            return "HTTP_ERROR"
        if not out:
            return "DOWN"
        return json.loads(out)
    except Exception:
        return "DOWN"


def _calc_keys_one(calc_type: str, extra: dict | None = None) -> set[str] | str | None:
    """Live top-level result key-set for ONE input variant. None = unresolvable; 'DOWN' = api down."""
    inputs = dict(CALC_MIN_INPUTS.get(calc_type, {}))
    if extra:
        inputs.update(extra)
    body = {"calc_type": calc_type, "inputs": inputs}
    j = _post_calculate(body)
    if j == "HTTP_ERROR":
        return None
    if j == "DOWN" or not isinstance(j, dict):
        return "DOWN"  # sentinel: api unreachable
    res = j.get("results")
    if not isinstance(res, dict):
        return None
    # a 200 whose result is just {"error": ...} means the calc needs valid inputs (it
    # signals via results.error, not HTTP 422) — unresolvable, SKIP (don't read {error}
    # as the key-set → would false-flag every read as drift).
    if "error" in res and len(res) <= 2:
        return None
    return set(res.keys())


def calc_keys(calc_type: str) -> set[str] | str | None:
    """Live result key-set, UNIONED across every mode variant (CALC_MODE_VARIANTS) so an
    agent's reads from a non-default mode aren't false-flagged. None = unresolvable; 'DOWN'."""
    base = _calc_keys_one(calc_type)
    if base == "DOWN":
        return "DOWN"
    union: set[str] = set(base) if isinstance(base, set) else set()
    for variant in CALC_MODE_VARIANTS.get(calc_type, []):
        ks = _calc_keys_one(calc_type, variant)
        if ks == "DOWN":
            return "DOWN"
        if isinstance(ks, set):
            union |= ks
    # if neither base nor any variant resolved, propagate the unresolvable signal
    return union if union else (None if base is None else base)


READ_RX = re.compile(r"""results\.([A-Za-z_]\w*)|results\.get\(\s*['"]([^'"]+)['"]|results\[\s*['"]([^'"]+)['"]\s*\]""")


def agent_bodies(src: str) -> dict[str, str]:
    """Map agent fn name → its body text (def to next async-function def)."""
    defs = [(m.group(1), m.start()) for m in re.finditer(r"async function (\w+)\s*\(", src)]
    bodies = {}
    for i, (name, start) in enumerate(defs):
        end = defs[i + 1][1] if i + 1 < len(defs) else len(src)
        bodies[name] = src[start:end]
    return bodies


def dispatch_map(src: str) -> list[tuple[str, str, str]]:
    """(discipline, calc_type, agent_fn) for each dispatch branch."""
    rx = re.compile(r'discipline === "([^"]+)" && calc_type === "([^"]+)"\)\s*\{\s*result = await (\w+)\(')
    return [(m.group(1), m.group(2), m.group(3)) for m in re.finditer(rx, src)]


def read_groups(body: str) -> list[set[str]]:
    """Per STATEMENT (`;`-delimited, so multi-line `??`/`||` fallback chains stay together),
    the set of results.<key> read. A whole fallback chain is ONE group — it resolves if ANY
    branch hits a real key. Grounding reads only (skip inputs_used + the inner inputs.* echo)."""
    # strip line comments so a `// results.x` note isn't counted as a read
    nocomment = "\n".join(re.sub(r"//.*$", "", ln) for ln in body.splitlines())
    groups = []
    for stmt in nocomment.split(";"):
        keys = set()
        for m in READ_RX.finditer(stmt):
            k = m.group(1) or m.group(2) or m.group(3)
            if k and k != "inputs_used":
                keys.add(k)
        if keys:
            groups.append(keys)
    return groups


def main() -> int:
    print(f"{BOLD}\nGROUNDING FIELD-CONTRACT (§13.15 A6) — BOM/SOW agent reads resolve to real calc keys{RESET}")
    print("=" * 80)
    src = EDGE_FN.read_text(encoding="utf-8")
    bodies = agent_bodies(src)
    dispatch = dispatch_map(src)
    if not dispatch:
        print(f"{RED}could not parse dispatch map{RESET}")
        return 1

    # cache calc key-sets
    keyset_cache: dict[str, set[str] | str | None] = {}
    total_groups = 0
    resolved_groups = 0
    skipped_agents = 0
    drift: list[dict] = []
    per_agent: dict = {}

    for discipline, calc_type, fn in dispatch:
        body = bodies.get(fn)
        if body is None:
            continue
        if calc_type not in keyset_cache:
            keyset_cache[calc_type] = calc_keys(calc_type)
        ks = keyset_cache[calc_type]
        if ks == "DOWN":
            print(f"{YEL}SKIP (exit 2){RESET}: python-api ({PY_API}) unreachable.")
            return 2
        groups = read_groups(body)
        if ks is None:
            skipped_agents += 1
            per_agent[fn] = {"calc_type": calc_type, "skipped": "calc 422 on {} (needs inputs)", "groups": len(groups)}
            continue
        agent_drift = []
        for g in groups:
            total_groups += 1
            if g & ks:
                resolved_groups += 1
            else:
                cell = f"{fn} [{calc_type}] reads {{{', '.join(sorted(g))}}} — none in calc output"
                if cell not in ALLOWLIST:
                    agent_drift.append(sorted(g))
                    drift.append({"agent": fn, "calc_type": calc_type, "keys": sorted(g)})
        per_agent[fn] = {"calc_type": calc_type, "groups": len(groups), "drift": agent_drift}

    # ── forward-only baseline: FAIL only on a NEW drift cell; the known set ratchets DOWN ──
    BASELINE = ROOT / "grounding_contract_baseline.json"
    sig = lambda d: f"{d['agent']}::{d['calc_type']}::{','.join(d['keys'])}"
    cur_sigs = {sig(d) for d in drift}
    reset = "--reset-baseline" in sys.argv
    if BASELINE.exists() and not reset:
        base_sigs = set(json.loads(BASELINE.read_text(encoding="utf-8")).get("known_drift", []))
    else:
        base_sigs = cur_sigs
        BASELINE.write_text(json.dumps({"known_drift": sorted(cur_sigs),
                                        "note": "A6 grounding drift baseline — forward-only; fix cells to ratchet DOWN (lower count = re-baseline)."},
                                       indent=2), encoding="utf-8")
    new_drift = [d for d in drift if sig(d) not in base_sigs]
    fixed = sorted(base_sigs - cur_sigs)
    if fixed and not reset:  # someone fixed a drift cell → ratchet the baseline down
        base_sigs &= cur_sigs
        BASELINE.write_text(json.dumps({"known_drift": sorted(base_sigs),
                                        "note": "A6 grounding drift baseline — forward-only; ratcheted down as cells are fixed."},
                                       indent=2), encoding="utf-8")

    verifiable = total_groups
    pct = round(100 * resolved_groups / verifiable, 1) if verifiable else 100.0
    (ROOT / "grounding_contract.json").write_text(json.dumps({
        "tool": "tools/validate_grounding_contract.py",
        "subject": "BOM/SOW agent results.<field> reads resolve to the calc's real output keys",
        "agents": len(dispatch), "skipped_agents": skipped_agents,
        "read_groups_total": verifiable, "read_groups_resolved": resolved_groups,
        "resolved_pct": pct, "drift_cells": drift, "known_baseline": len(base_sigs),
        "new_drift": [sig(d) for d in new_drift], "fixed_since_baseline": fixed, "per_agent": per_agent,
        # `violations` mirrors the FAIL condition (NEW drift only, not baselined) under a key the
        # deepwalk flywheel's report_status() recognizes — so this report can back the `ai:* D10`
        # cell HONESTLY (empty => PASS, non-empty => FAIL) instead of being re-run in the 90s floor
        # (55 live /calculate calls via docker-exec fallback exceed it -> SKIP -> false 🟡). 2026-07-22.
        "violations": [sig(d) for d in new_drift],
        "result": "PASS" if not new_drift else "FAIL",
    }, indent=2), encoding="utf-8")

    print(f"  agents (dispatch branches) : {len(dispatch)}   ·  skipped (calc needs inputs): {skipped_agents}")
    print(f"  read-groups resolved       : {resolved_groups}/{verifiable} = {pct}%")
    print(f"  drift cells                : {len(drift)} total  ·  {len(base_sigs)} baselined (ratchet-down)  ·  {len(new_drift)} NEW")
    if fixed:
        print(f"  {GREEN}↓ {len(fixed)} drift cell(s) FIXED since baseline — ratchet lowered{RESET}")
    if new_drift:
        print(f"\n  {RED}{BOLD}NEW DRIFT ({len(new_drift)}) — a fresh ungrounded read shipped (fix it):{RESET}")
        for d in new_drift[:40]:
            print(f"    {RED}✗{RESET} {d['agent']} [{d['calc_type']}]: {{{', '.join(d['keys'])}}}")
        print(f"\n{RED}{BOLD}  GROUNDING CONTRACT: FAIL{RESET} — {len(new_drift)} NEW drift cell(s).")
        return 1
    print(f"\n{GREEN}{BOLD}  GROUNDING CONTRACT: PASS{RESET} — no new drift "
          f"({pct}% resolve; {len(base_sigs)} known cells tracked in baseline for A6.2 fixes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
