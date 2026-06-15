#!/usr/bin/env python3
"""
Companion Held-Out Diverse Gate — the standing CI gate for the §0.7 grounding arc.

WHY (Ian's invariant): "millions of questions can be right yet a real user still fails."
The TEMPLATED fabrication families overfit — the companion passes the phrasings it was tuned
against and breaks on novel ones. The HELD-OUT `--diverse` bank (novel/adversarial phrasings,
run ONCE, mechanical DB-truth grader in companion_fabrication_sweep.py) is the instrument that
keeps the fabrication FLOOR honest. This gate institutionalizes it so the floor can't silently
regress: every full platform-check run validates the latest diverse board.

HONEST DESIGN (the rate is non-deterministic): the diverse fab rate OSCILLATES ~0-7% run-to-run
(rotating free-tier model + false-memory loop = the documented ceiling). So this is NOT a strict
"== 0" gate — it FAILS only when fab exceeds a threshold (oscillation-ceiling + margin in
companion_diverse_baseline.json), i.e. a genuine REGRESSION, and DEGRADES-TO-SKIP (exit 0) when
there is no fresh/valid board — so it never blocks a commit on missing live infra (mirrors
validate_ai_eval_regression.py / validate_companion_dim_gate.py).

MODES:
  (default)         Read the latest .tmp/fab_sweep_<user>_diverse_*.json and gate on threshold +
                    freshness + validity. SKIP if none/stale/too-few-valid-probes.
  --run             If the local stack (edge :54321) is reachable, RUN the diverse sweep first
                    (fresh adversarial probes), then gate. Use this in a scheduled job for a true
                    standing loop; needs the local stack + free-tier API keys.
  --update-baseline Lower max_fab_pct to the latest observed rate (forward-only; refuses to raise).

EXIT: 0 = PASS or SKIP (degrade) · 1 = FAIL (diverse fabrication regressed beyond threshold).
"""
import sys, os, io, json, glob, time, socket, subprocess, argparse
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(ROOT, ".tmp")
BASELINE = os.path.join(ROOT, "companion_diverse_baseline.json")
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"


def load_baseline() -> dict:
    try:
        return json.load(io.open(BASELINE, encoding="utf-8"))
    except Exception:
        return {"max_fab_pct": 12.0, "max_deflect_pct": 12.0, "max_age_days": 7,
                "min_valid_probes": 30, "user": "leandro"}


def latest_board(user: str):
    files = sorted(glob.glob(os.path.join(TMP, f"fab_sweep_{user}_diverse_*.json")),
                   key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def edge_up(host="127.0.0.1", port=54321, timeout=2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_diverse(user: str) -> bool:
    """Produce a fresh diverse board. Returns True on success."""
    cmd = [sys.executable, os.path.join("tools", "companion_fabrication_sweep.py"),
           "--user", user, "--diverse", "--workers", "2", "--fresh-memory", "--label", "cigate"]
    print(f"{Y}--run: producing a fresh held-out diverse board (~10-15 min)...{X}", flush=True)
    try:
        r = subprocess.run(cmd, cwd=ROOT, timeout=1800)
        return r.returncode == 0
    except Exception as e:
        print(f"{R}--run failed: {e}{X}")
        return False


def skip(msg: str) -> int:
    print(f"{Y}SKIP{X} — {msg}")
    print(f"{Y}(degrade-to-SKIP: exit 0; this gate only FAILS on a real diverse-fabrication regression){X}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="run a fresh diverse sweep first (needs local stack)")
    ap.add_argument("--update-baseline", action="store_true", help="lower max_fab_pct to latest observed (forward-only)")
    args = ap.parse_args()

    bl = load_baseline()
    user = bl.get("user", "leandro")
    max_fab = float(bl.get("max_fab_pct", 12.0))
    max_defl = float(bl.get("max_deflect_pct", 12.0))
    max_age_days = float(bl.get("max_age_days", 7))
    min_valid = int(bl.get("min_valid_probes", 30))

    print(f"{B}Companion Held-Out Diverse Gate{X} (user={user}, thresholds: fab≤{max_fab}% deflect≤{max_defl}%)")

    if args.run:
        if not edge_up():
            return skip("--run requested but the local stack (edge :54321) is not reachable")
        if not run_diverse(user):
            return skip("--run sweep did not complete cleanly")

    board = latest_board(user)
    if not board:
        return skip(f"no diverse board found (.tmp/fab_sweep_{user}_diverse_*.json) — run with --run to produce one")

    age_days = (time.time() - os.path.getmtime(board)) / 86400.0
    if not args.run and age_days > max_age_days:
        return skip(f"latest diverse board is {age_days:.1f}d old (> {max_age_days}d) — stale; run with --run for a fresh one")

    try:
        d = json.load(io.open(board, encoding="utf-8"))
        fam = next(f for f in d["families"] if f["family"] == "DIVERSE")
    except Exception as e:
        return skip(f"could not read DIVERSE family from {os.path.basename(board)}: {e}")

    rows = fam.get("rows", [])
    n = fam.get("n", len(rows))
    # validity guard: a free-tier-exhausted board is mostly empty answers and would read as a
    # spurious pass (empties aren't graded fab). Require enough SUBSTANTIVE replies.
    valid = sum(1 for r in rows if len((r.get("answer") or "").strip()) > 10)
    if valid < min_valid:
        return skip(f"only {valid}/{n} substantive replies (< {min_valid}) — likely free-tier exhaustion; not a trustworthy measurement")

    fab = float(fam.get("fab_rate", 0.0))
    defl = float(fam.get("deflect_rate", 0.0))
    flagged = [r for r in rows if r.get("verdict") in ("fabricate", "deflect")]

    print(f"  board: {os.path.basename(board)} ({age_days:.1f}d old, {valid}/{n} valid)")
    print(f"  FAB={fab:.1f}%  DEFLECT={defl:.1f}%  (flagged {len(flagged)}/{n})")
    # read-the-replies discipline: always surface flagged replies, pass or fail.
    for r in flagged:
        print(f"    {R}{r.get('verdict')}{X} [{r.get('kind')}] {','.join(r.get('labels', []))}")
        print(f"       Q: {r.get('q','')[:90]}")
        print(f"       A: {(r.get('answer') or '')[:160]}")

    if args.update_baseline:
        if fab <= max_fab:
            bl["max_fab_pct"] = round(max(fab + 5.0, 8.0), 1)   # observed + a 5pt oscillation margin, floor 8
            bl["last_observed_fab_pct"] = fab
            bl["last_observed_deflect_pct"] = defl
            bl["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            io.open(BASELINE, "w", encoding="utf-8", newline="\n").write(json.dumps(bl, indent=2, ensure_ascii=False) + "\n")
            print(f"{G}baseline updated: max_fab_pct={bl['max_fab_pct']}% (observed {fab}% + 5pt margin){X}")
        else:
            print(f"{R}refusing to update baseline: observed {fab}% already exceeds max_fab_pct {max_fab}%{X}")
        return 0

    regressed = fab > max_fab or defl > max_defl
    if regressed:
        print(f"{R}{B}FAIL{X} — held-out diverse fabrication REGRESSED beyond the oscillation ceiling "
              f"(fab {fab:.1f}% vs ≤{max_fab}%, deflect {defl:.1f}% vs ≤{max_defl}%). Read the flagged replies above.")
        return 1
    print(f"{G}{B}PASS{X} — held-out diverse fabrication within the oscillation band "
          f"(fab {fab:.1f}% ≤ {max_fab}%, deflect {defl:.1f}% ≤ {max_defl}%).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
