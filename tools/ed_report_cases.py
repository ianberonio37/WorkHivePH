#!/usr/bin/env python3
"""ed_report_cases.py - one served calculation per built calculator, for the report walk (Wave ED R1, 2026-11-02).

For every calculator in tools/fixtures/ed_default_payloads.json (collectInputs() at the form's defaults, with the values
a person must type set by census_calc_served_engine.FILL) this runs the handler python-api serves for that calc_type
(main.HANDLERS, then main._to_jsonable - exactly what POST /calculate returns, without needing its API key) and writes
.tmp/ed_report_cases.json:

    {calc_type: {"inputs": {...}, "results": {...}, "module": "ups_sizing",
                 "headline": [[label, result_key, unit], ...]}}

The headline keys are the door page's (tools/build_calc_pages.py CALC_DATA, by module): the figures a person is told
first. tools/prove_engineering_reports.mjs renders each report from these results and checks the report states them.

    python tools/ed_report_cases.py
"""
from __future__ import annotations

import io
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python-api"))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

OUT = ROOT / ".tmp" / "ed_report_cases.json"


def main() -> int:
    warnings.filterwarnings("ignore")
    import logging
    logging.disable(logging.WARNING)
    import census_calc_served_engine as cse
    import build_calc_pages as bcp
    import main as api  # python-api/main.py - the served handlers

    payloads = json.loads(cse.FIXTURE.read_text(encoding="utf-8"))["payloads"]
    headline_by_module = {d["module"]: [list(h) for h in d.get("headline", [])] for d in bcp.CALC_DATA.values()}
    cases, failed = {}, []
    for calc, p in payloads.items():
        inputs = dict(p)
        for k, v in cse.FILL.items():
            if k in inputs and inputs[k] in (0, "", None):
                inputs[k] = v
        handler = api.HANDLERS.get(calc)
        if handler is None:
            failed.append((calc, "no python handler"))
            continue
        try:
            results = api._to_jsonable(handler(inputs))
        except Exception as e:  # noqa: BLE001 - the served endpoint would answer 422/500 here
            failed.append((calc, f"{type(e).__name__}: {str(e)[:120]}"))
            continue
        module = getattr(handler, "__module__", "").replace("calcs.", "")
        cases[calc] = {"inputs": inputs, "results": results, "module": module,
                       "headline": headline_by_module.get(module, [])}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    print(f"ed-report-cases: {len(cases)} served calculations written to {OUT.relative_to(ROOT)}"
          + (f"; {len(failed)} did not run: " + "; ".join(f"{c} ({w})" for c, w in failed) if failed else ""))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
