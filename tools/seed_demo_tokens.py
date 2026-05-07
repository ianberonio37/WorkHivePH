"""
Seeds realistic demo token data so the dashboard is useful right away.
Run once: python tools/seed_demo_tokens.py

Safe to re-run — adds more samples on top of existing data.
"""
import sys
import random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.claude_token_tracker import TrackedClient

# Realistic token profiles per action type
# (input_range, output_range, avg_duration_ms, mostly_uses_model)
PROFILES = {
    "validation": {
        "input":  (150, 400),
        "output": (80,  200),
        "ms":     (300, 800),
        "model":  "claude-haiku-4-5",
        "count":  25,
    },
    "search": {
        "input":  (100, 350),
        "output": (50,  180),
        "ms":     (250, 600),
        "model":  "claude-haiku-4-5",
        "count":  20,
    },
    "explanation": {
        "input":  (400, 900),
        "output": (300, 700),
        "ms":     (800, 2000),
        "model":  "claude-sonnet-4-6",
        "count":  18,
    },
    "code_edit": {
        "input":  (600, 1500),
        "output": (400, 1000),
        "ms":     (1200, 3000),
        "model":  "claude-sonnet-4-6",
        "count":  22,
    },
    "debugging": {
        "input":  (800, 2500),
        "output": (600, 1800),
        "ms":     (2000, 6000),
        "model":  "claude-opus-4-7",
        "count":  16,
    },
    "build": {
        "input":  (1200, 4000),
        "output": (1500, 5000),
        "ms":     (4000, 12000),
        "model":  "claude-opus-4-7",
        "count":  14,
    },
    "review": {
        "input":  (1000, 3000),
        "output": (500, 1500),
        "ms":     (2000, 5000),
        "model":  "claude-opus-4-7",
        "count":  12,
    },
    "planning": {
        "input":  (500, 1200),
        "output": (800, 2000),
        "ms":     (1500, 4000),
        "model":  "claude-sonnet-4-6",
        "count":  10,
    },
}

SAMPLE_PROMPTS = {
    "validation":  "validate the schema coverage for inventory_transactions",
    "search":      "find all files that reference hive_id",
    "explanation": "explain how RLS works in Supabase",
    "code_edit":   "update the logbook entry to include the parts cost field",
    "debugging":   "fix the null-pointer error in inventory when parts have no unit_cost",
    "build":       "build the marketplace listing feature with image upload",
    "review":      "review the community post XSS hardening for safety",
    "planning":    "plan the Phase 6 predictive analytics roadmap",
}


def main():
    tracker = TrackedClient()
    total = 0

    for action_type, cfg in PROFILES.items():
        prompt = SAMPLE_PROMPTS.get(action_type, f"perform {action_type} task")
        for _ in range(cfg["count"]):
            inp  = random.randint(*cfg["input"])
            out  = random.randint(*cfg["output"])
            ms   = random.randint(*cfg["ms"])
            # Occasionally use a slightly different model to show mixed history
            model = cfg["model"]
            if random.random() < 0.15:
                model = "claude-opus-4-7"

            tracker.log_raw(
                action_type    = action_type,
                model          = model,
                input_tokens   = inp,
                output_tokens  = out,
                cache_read     = int(inp * random.uniform(0, 0.3)),
                cache_write    = int(inp * random.uniform(0, 0.1)),
                duration_ms    = ms,
                prompt_preview = prompt,
                success        = 1 if random.random() > 0.03 else 0,
                notes          = "demo data",
            )
            total += 1

    print(f"\nSeeded {total} demo calls across {len(PROFILES)} action types.")
    print("Open http://localhost:5000/token-stats to see the dashboard.")
    print("Or run: python tools/analyze_tokens.py\n")


if __name__ == "__main__":
    main()
