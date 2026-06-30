#!/usr/bin/env python3
"""perf_l3_calc_latency.py — Arc L · L3: measure each python calc's compute p95 vs
the 1 s budget (S lens) + response weight (E lens), and merge the result into the
calc:: cells of perf_scale_results.json (which the L0 miner emits as S/E `pending`).

WHY in-process (not HTTP): the calc p95 budget is about COMPUTE time. We import the
real handler (the SAME `HANDLERS` dict FastAPI dispatches `/calculate` to) and time it
with the oracle input vectors from `validate_calc_formula_accuracy.py` (no new inputs
invented — same reuse as validate_calc_api_serializable.py). This is hermetic (no
network/DB/edge jitter) and measures the calc itself; the HTTP/pydantic/edge overhead
is the L3-EDGE phase's job (a separate probe). Response weight (E) uses the real
`_to_jsonable` boundary coercion the API applies before returning.

After writing the cells, re-run `perf_scale_sweep.mjs --accept --update-baseline`
(it recomputes lens_pass across ALL cells, incl. these, and ratchets).

USAGE: python tools/perf_l3_calc_latency.py            # measure + merge into results.json
       python tools/perf_l3_calc_latency.py --dry      # measure + report only, no write
"""
from __future__ import annotations
import json, os, sys, time, statistics

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYAPI = os.path.join(ROOT, "python-api")
TOOLS = os.path.dirname(os.path.abspath(__file__))
for p in (PYAPI, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

RESULTS = os.path.join(ROOT, "perf_scale_results.json")
N = 7                         # timed runs per calc (after 1 warm-up)
CALC_P95_BUDGET_MS = 1000     # roadmap §1: calc p95 ≤ 1 s
CALC_WEIGHT_BUDGET = 100 * 1024  # E: a calc JSON result is small; 100 KB is generous headroom
DRY = "--dry" in sys.argv

from validate_calc_formula_accuracy import VECTORS          # noqa: E402
from main import _to_jsonable                               # noqa: E402


def cell_key_for(module: str) -> str:
    # "calcs.solar_pv" -> "calc::calcs/solar_pv.py" ; "reliability.weibull" -> "calc::reliability/weibull.py"
    return "calc::" + module.replace(".", "/") + ".py"


def measure(calculate, inputs):
    # invoke the module's calculate() with a fresh inputs dict — the SAME path
    # validate_calc_api_serializable.py uses (the proven handler entry point).
    # A few calcs' calculate() expect the wrapped {inputs:{...}} request form → fall back.
    def call():
        try:
            return calculate(dict(inputs))
        except KeyError as e:
            if str(e).strip("'\"") == "inputs":
                return calculate({"inputs": dict(inputs)})
            raise
    call()  # warm (import/JIT/first-call caches)
    times = []
    last = None
    for _ in range(N):
        t0 = time.perf_counter()
        last = call()
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    p95 = times[min(len(times) - 1, int(round(0.95 * (len(times) - 1))))]
    med = statistics.median(times)
    weight = len(json.dumps(_to_jsonable(last)).encode("utf-8"))
    return p95, med, weight


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    # one representative case per module (a module = one calc:: cell)
    by_module = {}
    for case in VECTORS:
        by_module.setdefault(case["module"], case)

    updated, missing_cell, no_handler, errored, slow, heavy = [], [], [], [], [], []
    for mod, case in sorted(by_module.items()):
        ct = case["calc_type"]
        key = cell_key_for(mod)
        cell = surf.get(key)
        if cell is None:
            missing_cell.append((ct, key)); continue
        try:
            module = __import__(mod, fromlist=["calculate"])
            calculate = getattr(module, "calculate", None)
            if calculate is None:
                no_handler.append(ct); continue
            p95, med, weight = measure(calculate, case["inputs"])
        except Exception as e:
            errored.append((ct, str(e)[:80])); continue
        s_ok = p95 <= CALC_P95_BUDGET_MS
        e_ok = weight <= CALC_WEIGHT_BUDGET
        L = cell["lenses"]
        if L.get("S", {}).get("applicable"):
            L["S"]["status"] = "pass" if s_ok else "fix"
            L["S"]["measured"] = f"p95={p95:.1f}ms med={med:.1f}ms (in-process compute, n={N})"
            L["S"]["why"] = "calc compute p95 <=1s, measured in-process via the oracle input vector (local; pydantic+HTTP+edge overhead is the L3-edge phase)"
            L["S"]["env"] = "local"
        if L.get("E", {}).get("applicable"):
            L["E"]["status"] = "pass" if e_ok else "fix"
            L["E"]["measured"] = f"response {weight} bytes (<= {CALC_WEIGHT_BUDGET} budget)" if e_ok else f"response {weight} bytes EXCEEDS {CALC_WEIGHT_BUDGET}"
        updated.append((ct, key, p95, weight, s_ok, e_ok))
        if not s_ok:
            slow.append((ct, p95))
        if not e_ok:
            heavy.append((ct, weight))

    # recompute lens aggregates (mirror the sweep/miner math) so a dry-read is consistent
    for lens in ("S", "E", "R", "B"):
        p = d = pend = 0
        for s in surf.values():
            c = s.get("lenses", {}).get(lens)
            if not c or not c.get("applicable"):
                continue
            d += 1
            if c["status"] == "pass":
                p += 1
            elif c["status"] == "pending":
                pend += 1
        results["lens_pass"][lens] = p
        results["lens_pending"][lens] = pend
        results["lens_pct"][lens] = round(1000 * p / d) / 10 if d else 0

    if not DRY:
        json.dump(results, open(RESULTS, "w", encoding="utf-8"), indent=2)

    print("=" * 64)
    print("ARC L — L3 CALC latency (in-process compute p95 vs 1s budget)")
    print("=" * 64)
    print(f"  modules measured : {len(updated)}  (of {len(by_module)} VECTOR modules)")
    print(f"  S pass (<=1s)    : {sum(1 for u in updated if u[4])}")
    print(f"  S fix (slow)     : {len(slow)}")
    print(f"  E pass (weight)  : {sum(1 for u in updated if u[5])}")
    if slow:
        print("  SLOW calcs (p95 > 1s):")
        for ct, p95 in sorted(slow, key=lambda x: -x[1]):
            print(f"    {ct:34} p95={p95:.0f}ms")
    if heavy:
        print("  HEAVY responses (> budget):")
        for ct, w in heavy:
            print(f"    {ct:34} {w} bytes")
    if no_handler:
        print(f"  (no handler for {len(no_handler)} vector calc_types: {no_handler[:5]}{'...' if len(no_handler) > 5 else ''})")
    if missing_cell:
        print(f"  (no calc:: cell for {len(missing_cell)} modules: {[m[1] for m in missing_cell[:5]]})")
    if errored:
        print(f"  (handler errored for {len(errored)}: {errored[:3]})")
    # slowest few for visibility
    top = sorted(updated, key=lambda u: -u[2])[:5]
    print("  slowest measured:")
    for ct, key, p95, w, sok, eok in top:
        print(f"    {ct:34} p95={p95:.1f}ms  {w}B")
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> {'(dry, not written)' if DRY else 'merged calc:: S+E cells into perf_scale_results.json'}")
    print("  NEXT: node tools/perf_scale_sweep.mjs --median 3 --accept --update-baseline  (recount + ratchet)")


if __name__ == "__main__":
    main()
