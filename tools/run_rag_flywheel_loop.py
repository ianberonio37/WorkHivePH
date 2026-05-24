"""
RAG Flywheel Loop Orchestrator
==============================
Runs N consecutive walk → process turns back-to-back with a single command.
Each turn auto-increments. Cycles between local hives to avoid one-hive
rate-limit exhaustion. Writes a consolidated convergence report at the end.

Why: per-turn manual runs work but the user's flywheel cadence wants
"keep it looping" — this is that loop. Run once, get 3 (or N) turns done,
with a single convergence table at the end.

Usage:
  python tools/run_rag_flywheel_loop.py                       # 3 turns, dry preview
  python tools/run_rag_flywheel_loop.py --turns 5 --commit    # 5 real turns, processes each

Env (only when --commit):
  SUPABASE_URL                 = http://127.0.0.1:54321
  SUPABASE_SERVICE_ROLE_KEY    = sb_secret_*
"""

from __future__ import annotations
import os
import sys
import json
import subprocess
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any


TMP_DIR = Path(".tmp")

# Hive rotation pool: distribute walks across local hives so one hive
# doesn't burn through its per-hour limit. All three have seeded 5y data.
HIVE_POOL = [
    ("b0c61993-7e83-4b11-928a-54558d21d8c4", "Bryan Garcia"),       # Baguio Textile Mills
    ("7b785f99-2776-430f-be28-fc21db1d41a6", "Pablo Aguilar"),      # Manila Electronics Assembly
    ("5163ddb9-cfd9-4a0e-b3fe-dc7245c671b7", "Leandro Marquez"),    # Lucena Pharmaceutical Mfg.
]


def find_latest_turn() -> int:
    if not TMP_DIR.exists(): return 0
    nums = []
    for f in TMP_DIR.glob("rag_observations_turn_*.jsonl"):
        try:
            nums.append(int(f.stem.split("_")[-1]))
        except Exception:
            pass
    return max(nums) if nums else 0


def run_walk(turn: int, hive_id: str, worker: str) -> bool:
    """Invoke the Playwright walk for one turn."""
    env = os.environ.copy()
    env["WH_FLYWHEEL_TURN"]      = str(turn)
    env["WH_FLYWHEEL_HIVE_ID"]   = hive_id
    env["WH_FLYWHEEL_WORKER"]    = worker
    # Windows: use node + the playwright CLI script directly to avoid both
    # (a) the &-in-path shim breakage and (b) shell=True quoting hell.
    print(f"\n--- TURN {turn} WALK (hive={hive_id[:8]}... worker={worker}) ---")
    cwd = os.getcwd()
    cli_js = os.path.join(cwd, "node_modules", "@playwright", "test", "cli.js")
    if not os.path.isfile(cli_js):
        # Fallback: try the global shim form
        cli_js = os.path.join(cwd, "node_modules", "playwright", "cli.js")
    args = ["node", cli_js, "test", "tests/journey-rag-flywheel-walk.spec.ts", "--reporter=line"]
    res = subprocess.run(
        args, env=env, capture_output=True, text=True, timeout=4500,
    )
    # Walk passes are best-effort — predictive may fail on retry; the JSONL is still written.
    out = (res.stdout or "") + (res.stderr or "")
    append_count = sum(1 for l in out.splitlines() if "APPEND ok" in l)
    print(f"    turn {turn}: {append_count} APPEND ok events")
    obs_file = TMP_DIR / f"rag_observations_turn_{turn}.jsonl"
    return obs_file.exists() and obs_file.stat().st_size > 0


def run_processor(turn: int) -> Dict[str, Any]:
    """Run processor for one turn, return summary dict."""
    res = subprocess.run(
        [sys.executable, "tools/rag_flywheel_processor.py", "--turn", str(turn), "--commit"],
        capture_output=True, text=True, timeout=120, env=os.environ,
    )
    out = (res.stdout or "") + (res.stderr or "")
    # Parse the processor's final summary line:
    #   "Canonicals seeded: X  L0 locks added: Y"
    #   "Gaps ... missing-anchor: A  checker-fail: B  no-citations: C"
    parsed: Dict[str, Any] = {"raw": out[-1000:]}
    for line in out.splitlines():
        if "Canonicals seeded:" in line:
            import re
            m = re.search(r"Canonicals seeded:\s*(\d+)\s+L0 locks added:\s*(\d+)", line)
            if m:
                parsed["canonicals_seeded"] = int(m.group(1))
                parsed["l0_locks_added"]    = int(m.group(2))
        if "missing-anchor" in line:
            import re
            m = re.search(r"missing-anchor:\s*(\d+)\s+checker-fail:\s*(\d+)\s+no-citations:\s*(\d+)", line)
            if m:
                parsed["missing_anchor"]  = int(m.group(1))
                parsed["checker_failed"]  = int(m.group(2))
                parsed["no_citations"]    = int(m.group(3))
    return parsed


def parse_observations(turn: int) -> Dict[str, Any]:
    """Read the per-turn JSONL and compute convergence metrics."""
    p = TMP_DIR / f"rag_observations_turn_{turn}.jsonl"
    if not p.exists():
        return {"turn": turn, "ok": False, "reason": "no observations file"}
    rows = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return {"turn": turn, "ok": False, "reason": "empty observations file"}
    real = [r for r in rows if r.get("mode") == "real"]
    grader_pass  = sum(1 for r in real if r.get("ai_grader_passed") is True)
    checker_pass = sum(1 for r in real if r.get("ai_checker_passed") is True)
    cited        = sum(1 for r in real if (r.get("ai_citation_count") or 0) > 0)
    rate_limited = sum(1 for r in real if r.get("ai_status") == 429)
    pages = set(r["page"] for r in rows)
    return {
        "turn":          turn,
        "ok":            True,
        "observations":  len(rows),
        "real_calls":    len(real),
        "pages":         len(pages),
        "rate_limited":  rate_limited,
        "grader_pass":   grader_pass,
        "checker_pass":  checker_pass,
        "cited":         cited,
        "grader_rate":   round(100 * grader_pass / max(len(real), 1), 1),
        "checker_rate":  round(100 * checker_pass / max(len(real), 1), 1),
        "citation_rate": round(100 * cited / max(len(real), 1), 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run N consecutive flywheel turns and report the convergence curve")
    ap.add_argument("--turns", type=int, default=3, help="Number of turns to run (default 3)")
    ap.add_argument("--start-from", type=int, help="Override starting turn number (default: latest+1)")
    ap.add_argument("--rest", type=int, default=10, help="Seconds to rest between turns (default 10)")
    ap.add_argument("--commit", action="store_true", help="Actually run (default: dry preview)")
    args = ap.parse_args()

    start = args.start_from or (find_latest_turn() + 1)
    print(f"\n=== RAG Flywheel Loop ===")
    print(f"  Starting turn:  {start}")
    print(f"  Turns to run:   {args.turns}")
    print(f"  Hive rotation:  {[h[0][:8] for h in HIVE_POOL]}")
    print(f"  Commit mode:    {'YES' if args.commit else 'NO (dry preview)'}")
    if not args.commit:
        print(f"\nDry-run: would run turns {start} through {start + args.turns - 1}, rotating hives.")
        print("Pass --commit to actually walk + process.")
        return 0

    if not Path("./node_modules/.bin/playwright").exists():
        print("FAIL: ./node_modules/.bin/playwright not found. cd to project root.")
        return 2

    summaries: List[Dict[str, Any]] = []
    for i in range(args.turns):
        turn = start + i
        hive_id, worker = HIVE_POOL[i % len(HIVE_POOL)]
        ok = run_walk(turn, hive_id, worker)
        if not ok:
            print(f"  TURN {turn}: walk produced no observations — skipping processor")
            summaries.append({"turn": turn, "ok": False, "reason": "walk no obs"})
            continue
        # Light rest between walks to let the edge runtime breathe
        time.sleep(2)
        proc = run_processor(turn)
        obs = parse_observations(turn)
        obs.update({f"proc_{k}": v for k, v in proc.items() if k != "raw"})
        summaries.append(obs)
        print(f"  TURN {turn} done: {obs.get('checker_rate', 0)}% checker pass, {obs.get('cited', 0)} cited tiles, {obs.get('rate_limited', 0)} rate-limited")
        if i < args.turns - 1:
            print(f"    resting {args.rest}s before next turn...")
            time.sleep(args.rest)

    # Convergence table
    print("\n=== Convergence Curve ===\n")
    print(f"{'turn':<5} {'obs':<5} {'pages':<6} {'429':<4} {'grader%':<8} {'checker%':<9} {'cite%':<7} {'cited':<6} {'gaps_anchor':<12} {'gaps_check':<11}")
    print("-" * 90)
    for s in summaries:
        if not s.get("ok"):
            print(f"{s['turn']:<5} (no observations — {s.get('reason','?')})")
            continue
        print(f"{s['turn']:<5} "
              f"{s.get('observations',0):<5} "
              f"{s.get('pages',0):<6} "
              f"{s.get('rate_limited',0):<4} "
              f"{s.get('grader_rate',0):<8} "
              f"{s.get('checker_rate',0):<9} "
              f"{s.get('citation_rate',0):<7} "
              f"{s.get('cited',0):<6} "
              f"{s.get('proc_missing_anchor','?'):<12} "
              f"{s.get('proc_checker_failed','?'):<11}")

    # Consolidated report
    out_path = Path(f"flywheel_loop_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md")
    lines = [
        f"# RAG Flywheel Loop — {len(summaries)} turns",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Range: turns {summaries[0]['turn'] if summaries else '?'} → {summaries[-1]['turn'] if summaries else '?'}",
        "",
        "| Turn | Obs | Pages | 429 | Grader % | Checker % | Cite % | Cited | Missing Anchor | Checker Fail |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        if not s.get("ok"):
            lines.append(f"| {s['turn']} | — | — | — | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {s['turn']} | {s.get('observations',0)} | {s.get('pages',0)} | {s.get('rate_limited',0)} | "
            f"{s.get('grader_rate',0)}% | **{s.get('checker_rate',0)}%** | {s.get('citation_rate',0)}% | "
            f"{s.get('cited',0)} | {s.get('proc_missing_anchor','?')} | {s.get('proc_checker_failed','?')} |"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nConsolidated report -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
