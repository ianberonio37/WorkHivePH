"""
Claude Token Analysis CLI
Run this any time to see your token usage patterns and routing recommendations.

    python tools/analyze_tokens.py
    python tools/analyze_tokens.py --recent 20
    python tools/analyze_tokens.py --export tokens_report.json
"""

import sys
import json
import argparse
from pathlib import Path

# Allow running from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.claude_token_tracker import get_all_stats, get_recent_calls, DB_PATH
from tools.claude_model_router import ModelRouter, MIN_SAMPLES

MODEL_DISPLAY = {
    "claude-opus-4-7":   "Opus 4.7  ",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5":  "Haiku 4.5 ",
}

TIER_COLORS = {
    "claude-haiku-4-5":  "\033[92m",   # green
    "claude-sonnet-4-6": "\033[93m",   # yellow
    "claude-opus-4-7":   "\033[94m",   # blue
}
RESET = "\033[0m"


def print_summary(router: ModelRouter) -> None:
    s = router.summary()
    print(f"\n{'='*60}")
    print("  Claude Token Management — Summary")
    print(f"{'='*60}")
    print(f"  Total API calls tracked : {s['total_calls']:,}")
    print(f"  Total cost              : ${s['total_cost_usd']:.4f} USD")
    print(f"  Action types tracked    : {s['action_types_tracked']}")
    print(f"  Ready for auto-routing  : {s['actions_with_data']} action types")
    print(f"  Potential savings (vs Opus always): ${s['potential_savings_usd']:.4f} USD")
    print()


def print_routing_table(router: ModelRouter) -> None:
    table = router.routing_table()
    if not table:
        print("  No data yet. Make some API calls using TrackedClient first.\n")
        return

    print(f"  {'Action Type':<16} {'Recommended':<22} {'Samples':>7} {'Avg Tokens':>10} "
          f"{'Success':>8} {'Savings/100':>11}")
    print(f"  {'-'*16} {'-'*22} {'-'*7} {'-'*10} {'-'*8} {'-'*11}")

    for row in table:
        model   = row["recommended_model"]
        color   = TIER_COLORS.get(model, "")
        display = MODEL_DISPLAY.get(model, model)
        ready   = "" if row["data_ready"] else f"  (need {MIN_SAMPLES - row['total_samples']} more)"
        savings = f"${row['est_savings_per_100_calls_usd']:.4f}" if row["data_ready"] else "—"

        print(
            f"  {row['action_type']:<16} "
            f"{color}{display}{RESET} "
            f"{row['total_samples']:>7,} "
            f"{row['avg_total_tokens']:>10,} "
            f"{row['success_rate_pct']:>7.1f}% "
            f"{savings:>11}"
            f"{ready}"
        )
    print()


def print_recent(limit: int = 20) -> None:
    rows = get_recent_calls(limit)
    if not rows:
        print("  No calls logged yet.\n")
        return

    print(f"\n  Last {limit} API calls:")
    print(f"  {'Timestamp':<26} {'Action':<14} {'Model':<22} "
          f"{'In':>6} {'Out':>6} {'Cost':>10}")
    print(f"  {'-'*26} {'-'*14} {'-'*22} {'-'*6} {'-'*6} {'-'*10}")

    for r in rows:
        ts    = r["timestamp"][:19].replace("T", " ")
        model = MODEL_DISPLAY.get(r["model"], r["model"][:20])
        color = TIER_COLORS.get(r["model"], "")
        print(
            f"  {ts}  {r['action_type']:<14} "
            f"{color}{model}{RESET} "
            f"{r['input_tokens']:>6,} "
            f"{r['output_tokens']:>6,} "
            f"${r['cost_usd']:>9.6f}"
        )
    print()


def print_model_breakdown() -> None:
    stats = get_all_stats()
    if not stats:
        return

    by_model: dict[str, dict] = {}
    for r in stats:
        m = r["model"]
        if m not in by_model:
            by_model[m] = {"calls": 0, "cost": 0.0, "tokens": 0}
        by_model[m]["calls"]  += r["sample_count"]
        by_model[m]["cost"]   += r["total_cost_usd"]
        by_model[m]["tokens"] += r["avg_total_tokens"] * r["sample_count"]

    print("  Spend by model:")
    for model in ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"]:
        if model not in by_model:
            continue
        d     = by_model[model]
        color = TIER_COLORS[model]
        name  = MODEL_DISPLAY[model]
        print(
            f"  {color}{name}{RESET}  "
            f"{d['calls']:>6,} calls  "
            f"${d['cost']:>8.4f}  "
            f"{int(d['tokens']):>9,} tokens"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude token usage report")
    parser.add_argument("--recent", type=int, default=0,
                        help="Show N most recent calls (default: skip)")
    parser.add_argument("--export", type=str, default="",
                        help="Export routing table to a JSON file")
    args = parser.parse_args()

    router = ModelRouter()

    print(f"\n  DB: {DB_PATH}")
    print_summary(router)

    print("=== Routing Recommendations ===")
    print_routing_table(router)

    print("=== Spend by Model ===")
    print_model_breakdown()

    if args.recent:
        print(f"=== Recent Calls ===")
        print_recent(args.recent)

    if args.export:
        data = {
            "summary":       router.summary(),
            "routing_table": router.routing_table(),
            "recent_calls":  get_recent_calls(100),
        }
        Path(args.export).write_text(json.dumps(data, indent=2))
        print(f"  Exported to {args.export}\n")


if __name__ == "__main__":
    main()
