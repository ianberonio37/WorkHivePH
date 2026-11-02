#!/usr/bin/env python3
"""door-examples-are-keys - every worked example on a calculator door page computes what it names (2026-11-02).

Each door page (tools/<slug>/index.html, specced in tools/build_calc_pages.py CALC_DATA) runs its module on an example and
prints the result as "an X in Y". Three pages were found claiming a choice their engine never made, because the value was
not a key of the engine's table and the lookup fell back silently:
  - vibration-isolation-calculator: "on spring isolators" sent "Spring" - computed as a rubber mount;
  - noise-acoustics-calculator: "in a 400 m2 factory" sent "Factory / Workshop" - judged at an open office's NC 40;
  - v-belt-drive-calculator: "SPB section" - B's geometry with a flat estimate, 4 belts where B's rating needs 6.
A sweep of every string in every example then found 17 more (Manila for "Metro Manila / NCR", "Ellipsoidal" for
"Ellipsoidal (2:1)", "SA-516-70", "R410A", a stairwell "Office" computed as unsprinklered, ...).

THE TEST, per string input of each example: run the module on the example, and again with that value replaced by a
garbage string. If the two results are identical (once the echoed value itself is masked) and the value is not a literal
in the module's code, the engine never recognised it. RECOGNISED_BY_RULE names the few values an engine accepts by a
rule rather than a table key, each with its reason.

    python tools/validate_door_examples_are_keys.py
    python tools/validate_door_examples_are_keys.py --self-test
"""
from __future__ import annotations

import importlib
import io
import json
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python-api"))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

GARBAGE = "zz-not-a-key-zz"
RECOGNISED_BY_RULE = {
    ("drainage-pipe-sizing-calculator", "system_type"):
        "drainage_pipe_sizing treats everything but 'Drain Stack' as horizontal piping - a building drain is horizontal",
    ("chiller-sizing-calculator", "chiller_type"):
        "chiller reads 'Water' in the type (with is_water_cooled) and positive-displacement keywords; centrifugal otherwise",
    ("voltage-drop-calculator", "circuit_type"):
        "voltage_drop only echoes the circuit type; the limit is the example's own vd_limit",
}


def _code_only(src: str) -> str:
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    return re.sub(r"#[^\n]*", "", src)


def _strip(r):
    if isinstance(r, dict):
        return {k: _strip(v) for k, v in r.items() if k not in ("inputs_used", "code_notes", "calculation_source")}
    if isinstance(r, list):
        return [_strip(x) for x in r]
    return r


def unrecognised(calc_data: dict) -> list[tuple[str, str, str]]:
    out = []
    for slug, d in calc_data.items():
        if not d.get("module"):
            continue
        mod = importlib.import_module(f"calcs.{d['module']}")
        src = _code_only(Path(mod.__file__).read_text(encoding="utf-8"))
        ex = d.get("example_inputs", {})
        for k, v in ex.items():
            if not isinstance(v, str) or (slug, k) in RECOGNISED_BY_RULE:
                continue
            try:
                a = json.dumps(_strip(mod.calculate(dict(ex))), sort_keys=True, default=str)
                g = json.dumps(_strip(mod.calculate({**ex, k: GARBAGE})), sort_keys=True, default=str)
            except Exception:  # noqa: BLE001 - an example that raises is the page gate's finding, not this one's
                continue
            same = a.replace(json.dumps(v)[1:-1], "@") == g.replace(GARBAGE, "@")
            literal = f'"{v}"' in src or f"'{v}'" in src
            if same and not literal:
                out.append((slug, k, v))
    return out


def main() -> int:
    warnings.filterwarnings("ignore")
    import logging
    logging.disable(logging.WARNING)
    import build_calc_pages as bcp
    if "--self-test" in sys.argv:
        planted = {"vibration-isolation-calculator": dict(bcp.CALC_DATA["vibration-isolation-calculator"])}
        planted["vibration-isolation-calculator"]["example_inputs"] = {
            **planted["vibration-isolation-calculator"]["example_inputs"], "isolator_type": "Spring"}
        caught = any(k == "isolator_type" for _, k, _ in unrecognised(planted))
        print(("PASS" if caught else "FAIL") + " door-examples-are-keys --self-test: the original 'Spring' isolator "
              + ("is caught" if caught else "was NOT caught"))
        return 0 if caught else 1
    bad = unrecognised(bcp.CALC_DATA)
    if bad:
        print(f"FAIL door-examples-are-keys - {len(bad)} worked-example value(s) the engine never recognises:")
        for slug, k, v in bad:
            print(f"    - {slug}: {k} = {v!r} computes exactly as an unknown value would")
        print("    The page prints the example as if the engine used it. Use the engine's own key (the form's value), or")
        print("    record a rule-based acceptance in RECOGNISED_BY_RULE with its reason.")
        return 1
    n = sum(1 for d in bcp.CALC_DATA.values() for v in d.get("example_inputs", {}).values() if isinstance(v, str))
    print(f"PASS door-examples-are-keys - all {n} string values in the door pages' worked examples are recognised by "
          f"their engines ({len(RECOGNISED_BY_RULE)} by a recorded rule).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
