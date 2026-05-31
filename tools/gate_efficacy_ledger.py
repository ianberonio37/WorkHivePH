"""
Gate Efficacy Ledger — P1 of SELF_IMPROVING_GATE_ROADMAP.md.
============================================================
The gate's missing sense: *which of its own validators actually matter.*

PURE OBSERVATION. This tool reads the gate's own output (`platform_health.json`,
already written by run_platform_checks.py) and maintains an append-only ledger
of per-validator efficacy. It NEVER runs the gate, NEVER changes a verdict, and
NEVER affects an exit code. It only watches.

What it tracks per validator, across gate runs:
  - times_run / times_pass / times_fail / times_warn / times_skip
  - true_catches  : PASS-or-WARN -> FAIL transitions (it caught a NEW regression,
                    vs. a chronically-red baseline that fires every run)
  - last_fired_run: the run index of the most recent true catch
  - elapsed_recent: last runtime (feeds the P5 retirement payoff / runtime budget)
  - origin        : bug | miner | manual | wiring | unknown (override file optional)

Why "true catch" = a transition, not just "is FAIL": a validator that is red on
every run is a known-issue baseline, not a catch. A validator that goes green->red
caught something new — that is the load-bearing signal. A validator with 0 true
catches over many runs AND no origin is a P5 retirement candidate (Rule D).

Usage:
  python tools/gate_efficacy_ledger.py            # update from latest platform_health.json
  python tools/gate_efficacy_ledger.py update      # (same)
  python tools/gate_efficacy_ledger.py report      # human-readable efficacy report
  python tools/gate_efficacy_ledger.py update --force   # re-ingest same run (dedup off)

State: `gate_efficacy_ledger.json` (append-only history per validator). Optional
origin overrides: `gate_efficacy_origins.json` ({ "<validator-id>": "bug|miner|manual" }).
Exit code: 0 always (observation tool, never a gate).
"""
from __future__ import annotations
import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT        = Path(__file__).resolve().parent.parent
HEALTH_PATH = ROOT / "platform_health.json"
LEDGER_PATH = ROOT / "gate_efficacy_ledger.json"
ORIGINS_PATH = ROOT / "gate_efficacy_origins.json"
FLYWHEEL_STATE = ROOT / "flywheel_state.json"

MIN_RUNS_FOR_RETIREMENT = 10   # don't call anything a retirement candidate until history is deep enough
FIRED_RUNS_CAP          = 25   # cap the per-validator catch-history list

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _empty_ledger() -> dict:
    return {"version": 1, "runs_observed": 0, "last_ingested_ts": None,
            "last_run": {}, "validators": {}}


def _infer_origin(vid: str, overrides: dict) -> str:
    if vid in overrides:
        return str(overrides[vid])
    # Light auto-inference; everything else is "unknown" until enriched.
    if vid.endswith("-wiring") or "wiring" in vid:
        return "wiring"
    return "unknown"


def update(force: bool = False) -> dict:
    """Ingest the latest platform_health.json into the ledger. Idempotent per
    run (dedup by timestamp) unless --force."""
    health = _load_json(HEALTH_PATH)
    if not health or not isinstance(health.get("validators"), list):
        print(f"{YEL}No usable platform_health.json — run the gate first (run_platform_checks.py).{RESET}")
        return _load_json(LEDGER_PATH) or _empty_ledger()

    ledger   = _load_json(LEDGER_PATH) or _empty_ledger()
    overrides = _load_json(ORIGINS_PATH) or {}
    ts = health.get("timestamp")

    if ts and ledger.get("last_ingested_ts") == ts and not force:
        print(f"{YEL}platform_health.json (ts={ts}) already ingested — nothing new. Use --force to re-ingest.{RESET}")
        return ledger

    run = ledger.get("runs_observed", 0) + 1
    fly = _load_json(FLYWHEEL_STATE) or {}
    vals = ledger.setdefault("validators", {})

    n_catch = 0
    for row in health["validators"]:
        vid = row.get("id")
        if not vid:
            continue
        status = (row.get("status") or "").upper()
        rec = vals.get(vid)
        if rec is None:
            rec = {
                "label": row.get("label", ""), "group": row.get("group", ""),
                "origin": _infer_origin(vid, overrides),
                "first_seen_run": run, "last_run": run,
                "times_run": 0, "times_pass": 0, "times_fail": 0, "times_warn": 0, "times_skip": 0,
                "last_status": None, "true_catches": 0, "last_fired_run": None,
                "fired_runs": [], "elapsed_recent": row.get("elapsed", 0),
            }
            vals[vid] = rec
        # refresh metadata that can change as the gate evolves
        rec["label"] = row.get("label", rec.get("label", ""))
        rec["group"] = row.get("group", rec.get("group", ""))
        if vid in overrides:
            rec["origin"] = str(overrides[vid])
        rec["elapsed_recent"] = row.get("elapsed", rec.get("elapsed_recent", 0))

        prev = rec.get("last_status")
        rec["times_run"] += 1
        rec["last_run"]   = run
        if   status == "PASS": rec["times_pass"] += 1
        elif status == "FAIL": rec["times_fail"] += 1
        elif status == "WARN": rec["times_warn"] += 1
        elif status == "SKIP": rec["times_skip"] += 1

        # True catch: was not-failing (PASS/WARN), now FAIL. A new validator that
        # is born FAIL (prev is None) is NOT a catch — it had nothing to transition from.
        if status == "FAIL" and prev in ("PASS", "WARN"):
            rec["true_catches"] += 1
            rec["last_fired_run"] = run
            rec["fired_runs"] = (rec.get("fired_runs", []) + [run])[-FIRED_RUNS_CAP:]
            n_catch += 1

        rec["last_status"] = status

    ledger["runs_observed"]   = run
    ledger["last_ingested_ts"] = ts
    ledger["last_run"] = {
        "ts": ts, "mode": health.get("mode"),
        "flywheel_turn": fly.get("turn"),
        "ingested_at": datetime.now().isoformat(timespec="seconds"),
        "overall": health.get("overall"),
        "validators_seen": len(health["validators"]),
        "new_catches_this_run": n_catch,
    }
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"{GREEN}Efficacy ledger updated.{RESET} run #{run} · {len(health['validators'])} validators · "
          f"{n_catch} new true-catch(es) this run · history depth {run} run(s).")
    return ledger


def report(ledger: dict | None = None) -> None:
    ledger = ledger or _load_json(LEDGER_PATH)
    if not ledger or not ledger.get("validators"):
        print(f"{YEL}No ledger yet — run `python tools/gate_efficacy_ledger.py update` after a gate run.{RESET}")
        return
    runs = ledger.get("runs_observed", 0)
    vals = ledger["validators"]
    total = len(vals)

    catchers   = sorted([v for v in vals.values() if v["true_catches"] > 0],
                        key=lambda v: -v["true_catches"])
    never      = [k for k, v in vals.items() if v["true_catches"] == 0]
    never_noorigin = [k for k in never if vals[k].get("origin", "unknown") == "unknown"]
    chronic    = [k for k, v in vals.items()
                 if v["times_run"] >= 3 and v["times_fail"] / max(1, v["times_run"]) >= 0.8]
    slowest    = sorted(vals.items(), key=lambda kv: -(kv[1].get("elapsed_recent") or 0))[:8]
    runtime    = sum((v.get("elapsed_recent") or 0) for v in vals.values())

    print(f"\n{BOLD}Gate Efficacy Report{RESET}  ·  history depth: {runs} run(s)  ·  {total} validators tracked")
    print("=" * 68)
    print(f"  total recent gate runtime (sum of last elapsed): {runtime:.0f}s")
    print(f"  load-bearing (>=1 true catch): {len(catchers)}   "
          f"never-fired: {len(never)}   chronically-red: {len(chronic)}")

    if runs < MIN_RUNS_FOR_RETIREMENT:
        print(f"\n  {YEL}History is shallow (need >= {MIN_RUNS_FOR_RETIREMENT} runs for retirement signal). "
              f"Counts below are seeded but not yet actionable.{RESET}")

    print(f"\n{CYAN}{BOLD}  Top catchers (load-bearing validators){RESET}")
    if catchers:
        for v in catchers[:12]:
            print(f"    {GREEN}{v['true_catches']:>3}x{RESET}  {_short(v['label']) or '?'}  "
                  f"[{v.get('origin','unknown')}]  last fired run #{v.get('last_fired_run')}")
    else:
        print(f"    (none yet — true catches accrue as validators go green->red across runs)")

    print(f"\n{CYAN}{BOLD}  Chronically-red ({len(chronic)}){RESET} — known-issue baselines or miscalibrated (not catches):")
    for k in chronic[:10]:
        v = vals[k]; print(f"    {RED}{v['times_fail']}/{v['times_run']} fail{RESET}  {k}")
    if not chronic: print("    (none)")

    print(f"\n{CYAN}{BOLD}  Retirement candidates (Rule D){RESET} — never fired AND no origin: {len(never_noorigin)}")
    if runs >= MIN_RUNS_FOR_RETIREMENT:
        for k in never_noorigin[:15]:
            print(f"    {YEL}-{RESET} {k}  (runs={vals[k]['times_run']}, never a true catch, origin=unknown)")
        if len(never_noorigin) > 15:
            print(f"    ... +{len(never_noorigin) - 15} more")
    else:
        print(f"    {YEL}deferred until history depth >= {MIN_RUNS_FOR_RETIREMENT} ({len(never_noorigin)} would qualify today){RESET}")

    print(f"\n{CYAN}{BOLD}  Slowest validators (runtime budget){RESET}")
    for k, v in slowest:
        print(f"    {(v.get('elapsed_recent') or 0):>6.1f}s  {k}")
    print()


def _short(s: str, n: int = 52) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate efficacy ledger (pure observation)")
    ap.add_argument("cmd", nargs="?", default="update", choices=["update", "report"])
    ap.add_argument("--force", action="store_true", help="re-ingest the current platform_health.json")
    args = ap.parse_args()
    if args.cmd == "report":
        report()
    else:
        led = update(force=args.force)
        report(led)
    return 0


if __name__ == "__main__":
    sys.exit(main())
