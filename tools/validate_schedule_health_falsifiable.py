#!/usr/bin/env python3
"""
validate_schedule_health_falsifiable.py — PJK2: a number that decides what slips must be falsifiable.

THE CLASS. project-manager renders two computed verdicts that drive real decisions: the CRITICAL
PATH (which work is allowed to slip) and EARNED VALUE (the cost/schedule health a client is shown).
Each needs a stated method, a refusal path when the inputs cannot support it, and exactly one
implementation.

WHAT THE WALK FOUND, and half of it was that the engine is GOOD — worth asserting so nobody
"simplifies" it away:

  * python-api/projects/prescriptive.py cites PMBOK 7 §6.5.2.2 and AACE 24R-03, uses
    networkx.dag_longest_path() rather than hand-rolled graph code, and refuses cleanly when
    networkx is absent. Its docstring records that the PREVIOUS hand-rolled version silently
    miscomputed cycles — the exact regression this gate exists to prevent a return to.
  * python-api/projects/diagnostic.py cites PMBOK 7 and AACE RP 80R-13, states every EVM formula,
    attributes the green/amber/red bands, and returns {available: False, reason: ...} rather than
    guessing when budget or dates are missing.

THE DEFECTS:
  1. TWO IMPLEMENTATIONS OF EVM. clientRollup() re-computed it in the browser, uncited, and had
     already diverged — it rounded pct_complete to an integer where the engine keeps the float,
     moving EV by up to 0.5% of BAC (about PHP 9,250 on a PHP 1,850,000 project) — and it was the
     number a supervisor saw whenever the edge fn had not answered. DELETED, not patched.
  2. AN ABSENCE RENDERED AS A VERDICT. renderCpm defaulted to an empty critical path when the rollup
     was unavailable, so every task drew as NON-critical with ZERO slack: a positive, and
     self-contradictory, answer (zero slack is normally what MAKES a task critical). renderBudget
     likewise told a supervisor to "add a budget, start date and end date" when all three existed.

Static + offline. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "project-manager.html"
CPM  = ROOT / "python-api" / "projects" / "prescriptive.py"
EVM  = ROOT / "python-api" / "projects" / "diagnostic.py"
FORMULAS = ROOT / "canonical" / "formula_contracts.json"


def main():
    if "--selftest" in sys.argv:
        probs = []
        for f in (PAGE, CPM, EVM, FORMULAS):
            if not f.exists():
                probs.append(f"missing input: {f.name}")
        if probs:
            print("SELFTEST FAIL:")
            for x in probs:
                print("  " + x)
        else:
            print("SELFTEST PASS")
        return 1 if probs else 0

    print(f"\n{BOLD}SCHEDULE / HEALTH FALSIFIABLE (method cited, refusal real, ONE implementation){RESET}")
    print("-" * 78)

    page_raw = PAGE.read_text(encoding="utf-8", errors="replace") if PAGE.exists() else ""
    # COMMENTS STRIPPED before looking for the deleted implementation. The comment that RECORDS a
    # removal necessarily quotes the thing removed — this gate's own first run failed on
    # `hoursActual * 200` surviving in the note explaining why it is gone. Third time in one session
    # that a line-based scanner matched a comment instead of code (validate_xss's function-scope
    # walk and validate_seeder_insert_columns' variable match were the others), so it is stripped
    # here by construction rather than after the fact.
    page = re.sub(r"/\*[\s\S]*?\*/", " ", page_raw)
    page = re.sub(r"^\s*//.*$", " ", page, flags=re.M)
    cpm  = CPM.read_text(encoding="utf-8", errors="replace") if CPM.exists() else ""
    evm  = EVM.read_text(encoding="utf-8", errors="replace") if EVM.exists() else ""
    try:
        formulas = json.loads(FORMULAS.read_text(encoding="utf-8"))["formulas"]
    except Exception:
        formulas = []

    evm_contract = next((f for f in formulas if f.get("formula_id") == "evm_cpi_spi_pmbok"), None)

    checks = [
        # The engine keeps its citations. A "simplification" that drops them is the regression.
        ("CPM cites PMBOK + AACE", "PMBOK" in cpm and "AACE" in cpm),
        ("CPM uses networkx, not hand-rolled", "dag_longest_path" in cpm),
        ("CPM refuses without networkx", "networkx not installed" in cpm),
        ("EVM cites PMBOK + AACE", "PMBOK" in evm and "AACE" in evm),
        ("EVM refuses on missing inputs",
         '"available": False' in evm or "'available': False" in evm),

        # ONE implementation. The magic rate reappearing in the page means the duplicate is back.
        ("client does NOT recompute EVM", "hoursActual * 200" not in page),
        ("client does NOT recompute the critical path",
         "dag_longest_path" not in page and "topological" not in page.lower()),

        # An absence must not render as a verdict.
        ("CPM pane says when it could not compute",
         "critical path could not be computed" in page_raw),
        ("budget pane distinguishes 'not computed' from 'no inputs'",
         "Earned Value could not be computed" in page_raw),

        # The contract exists and is honest about WHICH part is partial.
        ("EVM registered as a formula contract", evm_contract is not None),
        ("EVM contract admits AC is a proxy",
         bool(evm_contract) and evm_contract.get("partial_variant") is True
         and "proxy" in (evm_contract.get("partial_reason") or "").lower()),
    ]

    fails = 0
    for label, ok in checks:
        if ok:
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {label}")

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail")
    (ROOT / "schedule_health_falsifiable_report.json").write_text(
        json.dumps({"validator": "schedule_health_falsifiable", "fail": fails}, indent=2),
        encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
