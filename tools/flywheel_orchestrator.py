"""
Flywheel Improvement Loop — one turn of the Unified Mega Gate.
================================================================
The existing flywheels in this codebase ("Cross-Surface KPI Parity",
"Canonical Drift") were manual N-turn sweeps. This script makes the
loop explicit + runnable.

Each turn walks every Mega Gate layer in order, snapshots its state,
diffs against the previous turn, and surfaces three things:

  1. RATCHETS — baselines that tightened since last turn (forward-only
     wins; the platform got measurably better)
  2. REGRESSIONS — baselines that loosened (caught here before they
     ship; should never happen if Mega Gate is green, but defensive)
  3. PROMOTIONS — L-1 patterns ready to promote into L-1.5 / L0 / L2
     (the queue for the next manual turn)

Layers walked:

  L-1   cluster pattern miners (mine_*.py)             → emergent rules
  L-1.5 skill rules manifest scan                       → documented rules
  L0    static validators with forward-only ratchets   → baseline counts
  L2    Playwright sentinel spec count                  → runtime coverage
  L13   walkthrough staleness                          → coverage freshness

State persists in `flywheel_state.json` (turn number + last-snapshot
counts per layer). Output: `flywheel_turn_report.md` (latest turn only;
not appended — each run replaces).

Usage:
  python tools/flywheel_orchestrator.py            # run one turn
  python tools/flywheel_orchestrator.py --json     # machine output
  python tools/flywheel_orchestrator.py --reset    # zero the state

Exit code: 0 always (this is a reporting tool, not a gate).
"""
from __future__ import annotations
import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
STATE_PATH  = ROOT / "flywheel_state.json"
REPORT_PATH = ROOT / "flywheel_turn_report.md"


# ── ANSI for terminal output ───────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── State helpers ───────────────────────────────────────────────────────────

def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {"turn": 0, "history": [], "snapshots": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"turn": 0, "history": [], "snapshots": {}}


def _write_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _read_json(rel: str) -> dict | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Layer snapshotters ──────────────────────────────────────────────────────
# Each returns a dict of measurable scalars for the layer. The flywheel
# diffs successive snapshots — improvements (lower drift, higher coverage)
# are RATCHETS, the opposite are REGRESSIONS.

def _snapshot_L_minus_1() -> dict:
    """L-1 cluster miners. Read the *_pattern_mining_report.md files for
    proposal counts. Each new proposal is a candidate for L-1.5 rule
    promotion."""
    snap = {"proposals_by_cluster": {}}
    for md in ROOT.glob("*_pattern_mining_report.md"):
        cluster = md.name.replace("_pattern_mining_report.md", "")
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Count rule proposals — heuristic: lines starting with "- **" or
        # `## Proposal` sections.
        n_props = len(re.findall(r"^##\s+Proposal", text, re.MULTILINE))
        if n_props == 0:
            n_props = len(re.findall(r"^- \*\*", text, re.MULTILINE))
        snap["proposals_by_cluster"][cluster] = n_props
    snap["total_proposals"] = sum(snap["proposals_by_cluster"].values())
    return snap


def _snapshot_L_minus_1_5() -> dict:
    """L-1.5 skill rules. Counts rules in the manifest + conformance from
    the mining report."""
    snap = {"rules_in_manifest": 0, "conformant_rules": 0, "drift_rules": 0}
    manifest = _read_json("skill_rules_manifest.json")
    if manifest:
        rules = manifest.get("rules", [])
        snap["rules_in_manifest"] = len(rules)
    mining = ROOT / "skill_rules_mining_report.md"
    if mining.exists():
        text = mining.read_text(encoding="utf-8", errors="replace")
        # Look for the "✅ FULL" vs "⚠️" / "❌" counts
        m_full = re.search(r"FULL conformance.*?:\s*\*\*(\d+)\*\*", text)
        m_drift = re.search(r"(?:drift|partial).*?:\s*\*\*(\d+)\*\*", text, re.IGNORECASE)
        if m_full:  snap["conformant_rules"] = int(m_full.group(1))
        if m_drift: snap["drift_rules"]      = int(m_drift.group(1))
    return snap


def _snapshot_L0() -> dict:
    """L0 static validators with forward-only ratchet baselines. Reads
    each *_baseline.json + corresponding *_report.json to surface
    'current' and 'baseline' counts. Tightening = ratchet event."""
    snap: dict[str, Any] = {"baselines": {}, "total_baseline_count": 0,
                            "validators_with_baseline": 0}
    for bf in sorted(ROOT.glob("*_baseline.json")):
        name = bf.name.replace("_baseline.json", "")
        try:
            baseline_doc = json.loads(bf.read_text(encoding="utf-8"))
        except Exception:
            continue
        # The baseline file stores the locked count under various keys
        # depending on the validator. Pull the first numeric value.
        baseline_count = 0
        for v in baseline_doc.values():
            if isinstance(v, (int, float)):
                baseline_count = int(v); break
        snap["baselines"][name] = baseline_count
        snap["total_baseline_count"] += baseline_count
        snap["validators_with_baseline"] += 1
    return snap


def _snapshot_L2() -> dict:
    """L2 Playwright sentinel coverage. Counts test('check_...') and
    `name: 'check_...'` declarations across the canonical-signal-parity
    + cross-surface-kpi-parity specs."""
    snap = {"sentinel_specs": 0, "sentinel_fixme": 0, "voice_sentinels": 0}
    for sf in (ROOT / "tests" / "journey-canonical-signal-parity.spec.ts",
               ROOT / "tests" / "journey-cross-surface-kpi-parity.spec.ts"):
        if sf.exists():
            body = sf.read_text(encoding="utf-8", errors="replace")
            snap["sentinel_specs"] += len(re.findall(r"\btest\s*\(\s*['\"]check_", body))
            snap["sentinel_specs"] += len(re.findall(r"\bname\s*:\s*['\"]check_", body))
            snap["sentinel_fixme"] += len(re.findall(r"\btest\.fixme\s*\(\s*['\"]check_", body))
    vsf = ROOT / "tests" / "journey-voice-phases.spec.ts"
    if vsf.exists():
        body = vsf.read_text(encoding="utf-8", errors="replace")
        snap["voice_sentinels"] = len(re.findall(r"\btest\s*\(\s*['\"]phase_", body))
    return snap


def _snapshot_L13() -> dict:
    """L13 staleness — read the staleness gate report if present."""
    snap = {"walkthroughs_total": 0, "walkthroughs_stale": 0}
    sg = _read_json("staleness_gate_report.json") or _read_json("sentinel_baseline.json")
    if sg:
        s = sg.get("summary", {})
        snap["walkthroughs_total"] = s.get("walkthroughs_total", 0)
        snap["walkthroughs_stale"] = s.get("walkthroughs_stale", 0)
    return snap


# ── Diff + report ──────────────────────────────────────────────────────────

def _diff_L0(prev: dict, curr: dict) -> tuple[list, list]:
    """Compare baselines across turns. Return (ratchets, regressions)."""
    p_base = prev.get("baselines", {})
    c_base = curr.get("baselines", {})
    ratchets, regressions = [], []
    for name, c_val in c_base.items():
        p_val = p_base.get(name, c_val)  # unknown = no change
        if c_val < p_val:
            ratchets.append({"validator": name, "from": p_val, "to": c_val})
        elif c_val > p_val:
            regressions.append({"validator": name, "from": p_val, "to": c_val})
    # New baselines (validator added this turn)
    for name in c_base:
        if name not in p_base:
            pass  # not a ratchet or regression — just a new layer
    return sorted(ratchets, key=lambda x: x["to"] - x["from"]), regressions


def _scalar_diff(prev: dict, curr: dict, key: str) -> dict:
    p = prev.get(key, 0)
    c = curr.get(key, 0)
    return {"from": p, "to": c, "delta": c - p}


# ── Turn runner ────────────────────────────────────────────────────────────

def _run_turn(reset: bool = False) -> dict:
    state = {"turn": 0, "history": [], "snapshots": {}} if reset else _read_state()

    turn = state.get("turn", 0) + 1
    prev_snaps = state.get("snapshots", {})

    curr = {
        "L-1":   _snapshot_L_minus_1(),
        "L-1.5": _snapshot_L_minus_1_5(),
        "L0":    _snapshot_L0(),
        "L2":    _snapshot_L2(),
        "L13":   _snapshot_L13(),
    }

    diff = {
        "L-1_total_proposals":      _scalar_diff(prev_snaps.get("L-1", {}),   curr["L-1"],   "total_proposals"),
        "L-1.5_rules_in_manifest":  _scalar_diff(prev_snaps.get("L-1.5", {}), curr["L-1.5"], "rules_in_manifest"),
        "L0_total_baseline_count":  _scalar_diff(prev_snaps.get("L0", {}),    curr["L0"],    "total_baseline_count"),
        "L0_validators_with_baseline": _scalar_diff(prev_snaps.get("L0", {}), curr["L0"],    "validators_with_baseline"),
        "L2_sentinel_specs":        _scalar_diff(prev_snaps.get("L2", {}),    curr["L2"],    "sentinel_specs"),
        "L13_walkthroughs_stale":   _scalar_diff(prev_snaps.get("L13", {}),   curr["L13"],   "walkthroughs_stale"),
    }
    ratchets, regressions = _diff_L0(prev_snaps.get("L0", {}), curr["L0"])

    turn_record = {
        "turn":        turn,
        "ts":          datetime.now().isoformat(timespec="seconds"),
        "diff":        diff,
        "L0_ratchets": ratchets,
        "L0_regressions": regressions,
    }

    state["turn"]     = turn
    state["snapshots"] = curr
    state["history"]  = (state.get("history") or [])[-9:] + [turn_record]
    _write_state(state)
    return turn_record


# ── Reporting ──────────────────────────────────────────────────────────────

def _print_terminal(turn_record: dict) -> None:
    d = turn_record["diff"]
    print()
    print(f"{BOLD}Flywheel Turn #{turn_record['turn']}{RESET}    {turn_record['ts']}")
    print("=" * 64)
    print(f"  {CYAN}L-1{RESET}    cluster proposals:        "
          f"{d['L-1_total_proposals']['from']} → {d['L-1_total_proposals']['to']}  "
          f"({_signed(d['L-1_total_proposals']['delta'])})")
    print(f"  {CYAN}L-1.5{RESET}  skill rules in manifest:  "
          f"{d['L-1.5_rules_in_manifest']['from']} → {d['L-1.5_rules_in_manifest']['to']}  "
          f"({_signed(d['L-1.5_rules_in_manifest']['delta'])})")
    print(f"  {CYAN}L0{RESET}     baselines tracked:         "
          f"{d['L0_validators_with_baseline']['from']} → {d['L0_validators_with_baseline']['to']}  "
          f"({_signed(d['L0_validators_with_baseline']['delta'])})")
    print(f"  {CYAN}L0{RESET}     total locked count:        "
          f"{d['L0_total_baseline_count']['from']} → {d['L0_total_baseline_count']['to']}  "
          f"({_signed(d['L0_total_baseline_count']['delta'], invert=True)})")
    print(f"  {CYAN}L2{RESET}     sentinel parity cases:     "
          f"{d['L2_sentinel_specs']['from']} → {d['L2_sentinel_specs']['to']}  "
          f"({_signed(d['L2_sentinel_specs']['delta'])})")
    print(f"  {CYAN}L13{RESET}    stale walkthroughs:        "
          f"{d['L13_walkthroughs_stale']['from']} → {d['L13_walkthroughs_stale']['to']}  "
          f"({_signed(d['L13_walkthroughs_stale']['delta'], invert=True)})")

    if turn_record["L0_ratchets"]:
        print()
        print(f"{GREEN}{BOLD}  RATCHETS ({len(turn_record['L0_ratchets'])}){RESET} — baselines that tightened this turn:")
        for r in turn_record["L0_ratchets"][:10]:
            print(f"    {GREEN}↓{RESET} {r['validator']:<40s}  {r['from']} → {r['to']}")

    if turn_record["L0_regressions"]:
        print()
        print(f"{RED}{BOLD}  REGRESSIONS ({len(turn_record['L0_regressions'])}){RESET} — baselines that loosened (FIX):")
        for r in turn_record["L0_regressions"][:10]:
            print(f"    {RED}↑{RESET} {r['validator']:<40s}  {r['from']} → {r['to']}")

    if not turn_record["L0_ratchets"] and not turn_record["L0_regressions"]:
        print()
        print(f"  {YELLOW}No ratchets or regressions this turn — platform is stable.{RESET}")


def _signed(n: int, invert: bool = False) -> str:
    """Format a delta. invert=True flips arrow direction (for "lower is
    better" stats like baseline_count / stale_walkthroughs)."""
    if n == 0: return "·"
    if invert:
        return f"{GREEN}↓{abs(n)}{RESET}" if n < 0 else f"{RED}↑{n}{RESET}"
    return f"{GREEN}+{n}{RESET}" if n > 0 else f"{RED}{n}{RESET}"


def _write_report_md(turn_record: dict) -> None:
    d = turn_record["diff"]
    lines = []
    lines.append(f"# Flywheel Turn #{turn_record['turn']}\n")
    lines.append(f"_{turn_record['ts']}_\n")
    lines.append("## Layer deltas\n")
    lines.append("| Layer | Metric | Before | After | Delta |")
    lines.append("|---|---|---:|---:|---:|")
    lines.append(f"| L-1   | cluster proposals       | {d['L-1_total_proposals']['from']} | {d['L-1_total_proposals']['to']} | {_md_delta(d['L-1_total_proposals']['delta'])} |")
    lines.append(f"| L-1.5 | rules in manifest       | {d['L-1.5_rules_in_manifest']['from']} | {d['L-1.5_rules_in_manifest']['to']} | {_md_delta(d['L-1.5_rules_in_manifest']['delta'])} |")
    lines.append(f"| L0    | baselines tracked       | {d['L0_validators_with_baseline']['from']} | {d['L0_validators_with_baseline']['to']} | {_md_delta(d['L0_validators_with_baseline']['delta'])} |")
    lines.append(f"| L0    | total locked count      | {d['L0_total_baseline_count']['from']} | {d['L0_total_baseline_count']['to']} | {_md_delta(d['L0_total_baseline_count']['delta'], invert=True)} |")
    lines.append(f"| L2    | sentinel parity cases   | {d['L2_sentinel_specs']['from']} | {d['L2_sentinel_specs']['to']} | {_md_delta(d['L2_sentinel_specs']['delta'])} |")
    lines.append(f"| L13   | stale walkthroughs      | {d['L13_walkthroughs_stale']['from']} | {d['L13_walkthroughs_stale']['to']} | {_md_delta(d['L13_walkthroughs_stale']['delta'], invert=True)} |")
    lines.append("")

    if turn_record["L0_ratchets"]:
        lines.append(f"## ✅ Ratchets ({len(turn_record['L0_ratchets'])}) — baselines tightened\n")
        lines.append("| Validator | Was | Now |")
        lines.append("|---|---:|---:|")
        for r in turn_record["L0_ratchets"]:
            lines.append(f"| `{r['validator']}` | {r['from']} | **{r['to']}** |")
        lines.append("")
    if turn_record["L0_regressions"]:
        lines.append(f"## ❌ Regressions ({len(turn_record['L0_regressions'])}) — baselines loosened (FIX)\n")
        lines.append("| Validator | Was | Now |")
        lines.append("|---|---:|---:|")
        for r in turn_record["L0_regressions"]:
            lines.append(f"| `{r['validator']}` | {r['from']} | **{r['to']}** |")
        lines.append("")
    if not turn_record["L0_ratchets"] and not turn_record["L0_regressions"]:
        lines.append("## No ratchets or regressions this turn — platform stable.\n")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _md_delta(n: int, invert: bool = False) -> str:
    if n == 0: return "·"
    if invert:
        return f"↓{abs(n)} ✅" if n < 0 else f"↑{n} ❌"
    return f"+{n} ✅" if n > 0 else f"{n} ❌"


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="One turn of the Mega Gate flywheel")
    ap.add_argument("--json",  action="store_true", help="emit JSON instead of pretty")
    ap.add_argument("--reset", action="store_true", help="zero state and start over")
    args = ap.parse_args()

    turn_record = _run_turn(reset=args.reset)
    _write_report_md(turn_record)

    # Retrospection stage (SELF_IMPROVING_GATE_ROADMAP.md P1): fold the latest
    # gate output into the efficacy ledger. Best-effort + fully isolated — this
    # reporting tool stays exit-0, and the gate's verdicts are never touched.
    try:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "tools" / "gate_efficacy_ledger.py"), "update"],
                       timeout=30, capture_output=True)
    except Exception:
        pass

    if args.json:
        print(json.dumps(turn_record, indent=2))
    else:
        _print_terminal(turn_record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
