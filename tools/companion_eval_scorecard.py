"""
Companion Eval Scorecard — Phase 8 §8.0 (AI_SURFACE_MAP.md "Phase 8").
=====================================================================
The registry reader / validator / coverage-syncer for the companion's SIX evaluation
dimensions (agent · rag · memory · persona · safety · cost). It is the §8.0 deliverable
that makes the dimension taxonomy concrete and self-checking, BEFORE any golden sets (8.1),
graders (8.2), per-dimension gates (8.3) or the optimization loop (8.4) are built.

It does three things, all $0 / offline (no model calls):
  report  — print the 6-dimension scorecard: status (active|pending) · metric · grader ·
            frozen baseline (live from ai_eval_baseline.json) · live corpus coverage per
            split (from gate_eval_splits.json `eval_dimension`, esp. the locked-test split).
  verify  — assert the registry is WELL-FORMED and consistent with the taxonomy:
              * exactly the 6 COMPANION_DIMENSIONS are present, no more/less
              * every dim carries the required fields
              * every `active` dim resolves a real frozen baseline value
              * (warn) any `active` dim with 0 locked-test units — can't honestly gate
            Exit 1 on a malformed/inconsistent registry; DEGRADE-TO-SKIP (exit 0) if the
            registry file is absent (so it never false-FAILs before 8.0 ships on a branch).
  sync    — recompute live coverage per dimension from gate_eval_splits.json and stamp it
            into the registry's `coverage` block (informational; the live numbers always win).

This tool ships STANDALONE first (like P1's ledger and P6's split did) — the per-dimension
REGRESSION gate that exits 1 on a locked-test drop is 8.3 (generalize tools/ai_eval_gate.py),
which is when this gets registered as a G0 validator in run_platform_checks.py.

State: companion_eval_scorecard.json (the registry — the single source of truth).
Exit: 0 normally / SKIP; `verify` returns 1 only on a malformed/inconsistent registry.
"""
from __future__ import annotations
import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT          = Path(__file__).resolve().parent.parent
TOOLS_DIR     = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "companion_eval_scorecard.json"
SPLITS_PATH   = ROOT / "gate_eval_splits.json"
BASELINE_PATH = ROOT / "ai_eval_baseline.json"

# One taxonomy, imported from the ledger (C1 / Phase 8). Fallback keeps the tool runnable.
sys.path.insert(0, str(TOOLS_DIR))
try:
    from gate_efficacy_ledger import COMPANION_DIMENSIONS
except Exception:  # pragma: no cover
    COMPANION_DIMENSIONS = ("agent", "rag", "memory", "persona", "safety", "cost")

SPLITS = ("train", "val", "test")
REQUIRED_FIELDS = ("label", "metric", "metric_desc", "grader", "golden_set",
                   "tolerance", "gate", "status", "blocking")
VALID_STATUS = ("active", "pending")

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _coverage() -> dict:
    """Live per-(companion dimension x split) unit counts from gate_eval_splits.json."""
    data = _load_json(SPLITS_PATH) or {}
    items = data.get("items") or {}
    cov: dict = {d: {s: 0 for s in SPLITS} for d in COMPANION_DIMENSIONS if d != "cost"}
    for v in items.values():
        d = v.get("eval_dimension")
        if d and d in cov and v.get("split") in SPLITS:
            cov[d][v["split"]] += 1
    return cov


def _resolve_ref(ref: str):
    """Resolve a 'file.json::a.b.c' dotted reference to a value (or None). The file part is
    honored (resolved relative to repo root) so a dim can point at ai_eval_baseline.json OR
    companion_dim_baselines.json (the per-dimension baselines)."""
    if not isinstance(ref, str) or "::" not in ref:
        return None
    fname, _, path = ref.partition("::")
    doc = _load_json(ROOT / fname.strip())
    if doc is None:
        return None
    cur = doc
    for key in path.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur


def verify() -> int:
    reg = _load_json(REGISTRY_PATH)
    if not reg:
        print(f"{CYAN}SKIP{RESET} — no companion_eval_scorecard.json yet "
              f"(degrade-to-SKIP: never a false FAIL before 8.0 lands).")
        return 0
    errs: list[str] = []
    warns: list[str] = []
    dims = reg.get("dimensions") or {}

    # 1) exactly the 6 taxonomy dimensions, no drift
    want = set(COMPANION_DIMENSIONS)
    have = set(dims.keys())
    if have != want:
        if want - have:
            errs.append(f"missing dimension(s): {sorted(want - have)}")
        if have - want:
            errs.append(f"unknown dimension(s) not in COMPANION_DIMENSIONS: {sorted(have - want)}")

    # 2) per-dimension shape + active-baseline resolvability
    cov = _coverage()
    for d in sorted(have & want):
        row = dims[d] or {}
        for f in REQUIRED_FIELDS:
            if f not in row:
                errs.append(f"[{d}] missing required field '{f}'")
        status = row.get("status")
        if status not in VALID_STATUS:
            errs.append(f"[{d}] status '{status}' not in {VALID_STATUS}")
        if status == "active":
            # cost has its baseline under scores.<split>.cost (a sub-object); others under a pass_rate
            ref = row.get("baseline_ref")
            val = _resolve_ref(ref) if ref else None
            if val is None:
                errs.append(f"[{d}] status=active but baseline_ref '{ref}' resolves to nothing "
                            f"(freeze a clean baseline or set status=pending)")
            if d != "cost" and cov.get(d, {}).get("test", 0) == 0:
                warns.append(f"[{d}] active but 0 locked-test units — cannot honestly gate")

    bar = "=" * 70
    print(bar)
    if errs:
        print(f"{RED}FAIL{RESET}  companion scorecard registry: {len(errs)} problem(s)")
        for e in errs:
            print(f"  - {e}")
        for w in warns:
            print(f"  {YEL}warn{RESET} {w}")
        print(bar)
        return 1
    n_active = sum(1 for d in want if (dims.get(d) or {}).get("status") == "active")
    print(f"{GREEN}OK{RESET}  companion scorecard registry well-formed — "
          f"{len(want)} dimensions ({n_active} active, {len(want) - n_active} pending).")
    for w in warns:
        print(f"  {YEL}warn{RESET} {w}")
    print(bar)
    return 0


def report() -> int:
    reg = _load_json(REGISTRY_PATH)
    if not reg:
        print(f"{YEL}No companion_eval_scorecard.json — Phase 8 §8.0 not built here.{RESET}")
        return 0
    dims = reg.get("dimensions") or {}
    cov = _coverage()
    base_ok = BASELINE_PATH.exists()

    print(f"\n{BOLD}Companion Eval Scorecard{RESET}  ·  registry v{reg.get('version','?')} "
          f"·  phase {reg.get('phase','?')}  ·  axis {reg.get('axis','?')}")
    print("=" * 74)
    print(f"  {'dim':<9}{'status':<9}{'metric':<16}{'baseline':<12}{'test/val/train':<16}gate-when")
    print("  " + "-" * 70)
    order = sorted(dims, key=lambda d: (dims[d] or {}).get("order", 99))
    for d in order:
        row = dims[d] or {}
        status = row.get("status", "?")
        scol = (GREEN if status == "active" else YEL) + status + RESET
        ref = row.get("baseline_ref")
        bval = _resolve_ref(ref) if ref else None
        if d == "cost":
            bshow = (f"{bval.get('mean_latency_ms')}ms" if isinstance(bval, dict) else "n/a")
        else:
            # baseline_ref points at the split's dimension object {pass_rate, n}; show the rate.
            if isinstance(bval, dict):
                bval = bval.get("pass_rate")
            bshow = (f"{bval}%" if isinstance(bval, (int, float)) else ("proxy" if row.get("baseline_proxy") else "none"))
        c = cov.get(d)
        ccol = (f"{c['test']}/{c['val']}/{c['train']}" if c else "  per-result")
        gate = "enforced" if status == "active" else "SKIP→8.3"
        block = " (blocking)" if row.get("blocking") else ""
        # status col includes ANSI codes -> pad manually
        print(f"  {d:<9}{scol}{' ' * (9 - len(status))}{row.get('metric','?'):<16}{bshow:<12}{ccol:<16}{gate}{block}")

    print()
    n_active = sum(1 for d in dims if (dims[d] or {}).get('status') == 'active')
    print(f"  {n_active} active (frozen baseline → gated), {len(dims) - n_active} pending "
          f"(golden set/baseline pending → degrade-to-SKIP).")
    if not base_ok:
        print(f"  {YEL}note: ai_eval_baseline.json absent — active baselines show n/a until frozen.{RESET}")
    print(f"  next: 8.1 golden sets (agent first) → 8.2 graders → 8.3 per-dim gates. "
          f"See AI_SURFACE_MAP.md Phase 8.")
    print()
    return 0


def sync() -> int:
    reg = _load_json(REGISTRY_PATH)
    if not reg:
        print(f"{YEL}No registry to sync.{RESET}")
        return 0
    cov = _coverage()
    reg.setdefault("coverage", {})
    reg["coverage"]["synced_ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reg["coverage"]["by_dimension"] = {d: {**cov.get(d, {}), "total": sum(cov.get(d, {}).values())}
                                       for d in cov}
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2), encoding="utf-8")
    tot = sum(sum(v.values()) for v in cov.values())
    print(f"{GREEN}Coverage synced{RESET} into {REGISTRY_PATH.name} — "
          f"{tot} companion units across {len(cov)} dimensions.")
    for d, sp in cov.items():
        print(f"    {d:<9} test {sp['test']:>3}  val {sp['val']:>3}  train {sp['train']:>3}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Companion eval scorecard registry (Phase 8 §8.0)")
    ap.add_argument("cmd", nargs="?", default="report", choices=["report", "verify", "sync"])
    args = ap.parse_args()
    if args.cmd == "verify":
        return verify()
    if args.cmd == "sync":
        return sync()
    return report()


if __name__ == "__main__":
    sys.exit(main())
