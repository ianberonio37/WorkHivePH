"""census_selection_ceiling.py - a duty above the catalog must not be handed the catalog's largest size as if it were enough.

Found 2026-11-02 (Wave ED, B1 walk): the cooling-tower engine computed a condenser pump in watts and printed it as kW
(6,695.8 "kW" for a 6.7 kW duty), and the motor pick `next((s for s in PUMP_MOTOR_SIZES_KW if s >= p), SIZES[-1])` ran
off the end of its list and answered 90 kW - silently, as a recommendation. 45 selections in 28 engines are written that
way: a shaft, a breaker, a vessel wall, a battery, a pump, a rope. When the duty exceeds the largest entry, each returns
the largest entry, undersized, and says nothing.

The instrument: every `next(<generator>, <list>[-1])` in python-api/calcs is rewritten IN MEMORY (the files are not
touched) so that the fallback records its site when it fires. Each served case in .tmp/ed_report_cases.json (the form's
own payload) is then run with each numeric input scaled x10 and x1000, one at a time. A site that fired is a fault unless
the result says so - the engine either raises a ValueError naming the limit, or lists the site in `exceeds_catalog`.

    python tools/census_selection_ceiling.py [--gate] [--json]
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "python-api"
CASES = ROOT / ".tmp" / "ed_report_cases.json"
BASELINE = ROOT / "selection_ceiling_baseline.json"
sys.path.insert(0, str(API))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_SENT = object()


class _Fallback(ast.NodeTransformer):
    """next(gen, L[-1]) -> __wh_next(gen, L[-1], "<module>:<line>")"""

    def __init__(self, mod):
        self.mod, self.sites = mod, []

    def visit_Call(self, node):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Name) and node.func.id == "next" and len(node.args) == 2
                and isinstance(node.args[0], ast.GeneratorExp)
                and isinstance(node.args[1], ast.Subscript)
                and isinstance(getattr(node.args[1], "slice", None), ast.UnaryOp)
                and isinstance(node.args[1].slice.op, ast.USub)
                and getattr(node.args[1].slice.operand, "value", None) == 1):
            site = f"{self.mod}:{node.lineno}"
            self.sites.append(site)
            return ast.copy_location(ast.Call(func=ast.Name(id="__wh_next", ctx=ast.Load()),
                                              args=[node.args[0], node.args[1], ast.Constant(site)], keywords=[]), node)
        return node


def instrumented(mod_name: str, strip_disclosure: bool = False):
    """import calcs.<mod> with every list-end pick recording when it runs past its list - a raw `next(.., L[-1])` and
    calcs._catalog.pick_at_least alike (the helper's sites are named by the `what` it was given)"""
    path = API / "calcs" / f"{mod_name}.py"
    text = path.read_text(encoding="utf-8")
    if strip_disclosure:                       # teeth: an engine that picks through the helper but never returns the record
        text = text.replace("@discloses\n", "")
    tree = ast.parse(text)
    tr = _Fallback(mod_name)
    tree = ast.fix_missing_locations(tr.visit(tree))
    helper_sites = [f"{mod_name}:{n.lineno}" for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "pick_at_least"]
    fired: list[str] = []

    def __wh_next(gen, dflt, site):
        v = next(gen, _SENT)
        if v is _SENT:
            fired.append(site)
            return dflt
        return v

    m = types.ModuleType(f"calcs.{mod_name}")
    m.__file__, m.__package__ = str(path), "calcs"
    m.__dict__["__wh_next"] = __wh_next
    exec(compile(tree, str(path), "exec"), m.__dict__)
    real = m.__dict__.get("pick_at_least")
    if real is not None:
        def pick(sizes, need, what, *a, **k):
            out = real(sizes, need, what, *a, **k)
            val = k.get("value") or ((lambda s: s[k["key"]]) if k.get("key") else (lambda s: s))
            if not any(val(s) >= need for s in sizes):
                fired.append(f"{mod_name}: {what}")
            return out
        m.__dict__["pick_at_least"] = pick
    return m, tr.sites + helper_sites, fired


def says_so(res: dict, site: str) -> bool:
    # the engine names WHAT ran past its list (it cannot know a line number); any entry is the engine saying so
    ex = res.get("exceeds_catalog") if isinstance(res, dict) else None
    return bool(ex)


def census(strip_disclosure: bool = False) -> dict:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    rows, all_sites, covered = [], {}, set()
    for calc, c in cases.items():
        mod = str(c.get("module") or "").replace("calcs.", "")
        if not mod or not (API / "calcs" / f"{mod}.py").exists():
            continue
        try:
            m, sites, fired = instrumented(mod, strip_disclosure)
        except Exception as e:  # noqa: BLE001
            rows.append({"calc": calc, "module": mod, "error": f"import: {e}"})
            continue
        all_sites.setdefault(mod, sites)
        if not sites:
            continue
        inputs = c.get("inputs") or {}
        for k, v in inputs.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
                continue
            for mult in (10, 1000):
                fired.clear()
                trial = dict(inputs, **{k: v * mult})
                try:
                    res = m.calculate(trial)
                except ValueError:
                    continue                  # refused in words: the engine said so
                except Exception:             # noqa: BLE001 - another failure is another lens's
                    continue
                for site in sorted(set(fired)):
                    covered.add(site)
                    if not says_so(res, site):
                        rows.append({"calc": calc, "module": mod, "site": site, "input": k, "x": mult})
    # one row per site: the first input that drove it off its list
    seen, faults = set(), []
    for r in rows:
        key = r.get("site") or r.get("error")
        if key in seen:
            continue
        seen.add(key)
        faults.append(r)
    total = sum(len(v) for v in all_sites.values())
    return {"sites": total, "driven": len(covered), "faults": faults,
            "raw": sorted(s for v in all_sites.values() for s in v if ":" in s and "pick" not in s and s.split(":")[1].isdigit())}


def main() -> int:
    gate, as_json, teeth = "--gate" in sys.argv, "--json" in sys.argv, "--teeth" in sys.argv
    if not CASES.exists():
        print(f"SKIP selection-ceiling: {CASES.name} is missing - run python tools/ed_report_cases.py")
        return 0
    if teeth:
        bad = census(strip_disclosure=True)
        ok = len(bad["faults"]) >= 10
        print(f"{'TEETH ok' if ok else 'BLUNT'} selection-ceiling: with @discloses stripped, {len(bad['faults'])} picks run past "
              f"their list and say nothing")
        return 0 if ok else 1
    out = census()
    if as_json:
        print(json.dumps(out, indent=1))
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"open": None}
    for f in out["faults"][:80]:
        print(f"  silent  {f.get('site') or f.get('module')}  ({f['calc']}: {f.get('input')} x{f.get('x')})  {f.get('error', '')}")
    n = len(out["faults"])
    worse = base["open"] is not None and n > base["open"]
    print(f"{'FAIL' if gate and worse else 'PASS'} selection-ceiling: {out['sites']} list-end selections in python-api/calcs; "
          f"{out['driven']} driven past their list by a served case scaled x10/x1000; {n} hand out the largest size "
          f"without saying so" + (f" (baseline {base['open']})" if base["open"] is not None else ""))
    return 1 if gate and worse else 0


if __name__ == "__main__":
    sys.exit(main())
