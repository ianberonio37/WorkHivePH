#!/usr/bin/env python3
"""
Companion Flywheel Launcher — 100-Turn Self-Improvement Loop
=============================================================

Direct launcher for 100 turns of companion validation across all scenarios,
pages, hives, and personas. Uses Playwright to test actual UI behavior.

Runs turns sequentially, collecting observations into JSONL files.
"""
from __future__ import annotations
import subprocess
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
TURNS = 100
PAGES = ["alert-hub.html", "analytics.html", "logbook.html", "skillmatrix.html"]
SCENARIOS = ["logbook_entry", "asset_query", "report_intent", "safety_check", "energy_anomaly"]
HIVES = ["manila", "baguio", "cebu"]
REST_BETWEEN_TURNS = 5  # seconds


def run_single_turn(turn: int, page: str, scenario: str, hive: str) -> dict:
    """
    Run a single turn via Playwright.
    Returns observation dict or error status.
    """
    persona = "hezekiah" if turn % 2 == 0 else "zaniah"

    cmd = [
        "npx",
        "playwright",
        "test",
        "tests/journey-companion-flywheel-walk.spec.ts",
        "--grep", f"turn {turn}",
    ]

    env = {
        "COMPANION_TURN": str(turn),
        "COMPANION_PAGE": page,
        "COMPANION_SCENARIO": scenario,
        "COMPANION_HIVE": hive,
        "COMPANION_PERSONA": persona,
    }

    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            env={**dict(os.environ), **env},
        )

        # Parse JSONL from stdout
        observations = []
        for line in result.stdout.split("\n"):
            if line.strip() and line.startswith("{"):
                try:
                    observations.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return {
            "turn": turn,
            "page": page,
            "scenario": scenario,
            "hive": hive,
            "persona": persona,
            "ok": result.returncode == 0,
            "observations": observations,
        }

    except subprocess.TimeoutExpired:
        return {
            "turn": turn,
            "page": page,
            "scenario": scenario,
            "hive": hive,
            "persona": persona,
            "ok": False,
            "error": "TIMEOUT",
            "observations": [],
        }
    except Exception as e:
        return {
            "turn": turn,
            "page": page,
            "scenario": scenario,
            "hive": hive,
            "persona": persona,
            "ok": False,
            "error": str(e)[:100],
            "observations": [],
        }


def main() -> int:
    import os

    print(f"\n{'='*80}")
    print(f"  AI Companion Zaniah & Hezekiah — 100-Turn Flywheel")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    # Create .tmp directory
    tmp_dir = ROOT / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    all_metrics = []
    report_lines = [
        "# AI Companion Flywheel — 100-Turn Report",
        f"**Generated**: {datetime.now().isoformat()}",
        "",
        "## Convergence Curve",
        "| Turn | Page | Scenario | Hive | Persona | Status | Accuracy | Latency | Safety |",
        "|------|------|----------|------|---------|--------|----------|---------|--------|",
    ]

    for turn in range(1, TURNS + 1):
        page = PAGES[(turn - 1) % len(PAGES)]
        scenario = SCENARIOS[(turn - 1) % len(SCENARIOS)]
        hive = HIVES[(turn - 1) % len(HIVES)]
        persona = "hezekiah" if turn % 2 == 0 else "zaniah"

        print(
            f"TURN {turn:3d}  {page:25s}  {scenario:20s}  {hive:10s}  {persona:10s}",
            end="  ",
            flush=True,
        )

        result = run_single_turn(turn, page, scenario, hive)

        if result["ok"] and result["observations"]:
            obs = result["observations"][0]
            accuracy = obs.get("accuracy_score", 0)
            latency = obs.get("response_latency_ms", 0)
            safety = "✓" if obs.get("safety_pass", False) else "✗"

            print(f"✓ acc={accuracy:.0f}% lat={latency:.0f}ms {safety}")

            report_lines.append(
                f"| {turn} | {page} | {scenario} | {hive} | {persona} | OK | {accuracy:.0f}% | {latency:.0f}ms | {safety} |"
            )

            # Write observation
            obs_file = tmp_dir / f"companion_observations_turn_{turn:03d}.jsonl"
            obs_file.write_text(json.dumps(obs) + "\n", encoding="utf-8")

            all_metrics.append({
                "turn": turn,
                "accuracy": accuracy,
                "latency": latency,
                "safety": obs.get("safety_pass", False),
                "cited_tiles": obs.get("cited_tiles", 0),
            })

        else:
            error = result.get("error", "UNKNOWN")
            print(f"✗ {error}")
            report_lines.append(
                f"| {turn} | {page} | {scenario} | {hive} | {persona} | ERROR | — | — | ✗ |"
            )

        # Rest between turns
        if turn < TURNS:
            time.sleep(REST_BETWEEN_TURNS)

    # Summary stats
    if all_metrics:
        avg_accuracy = sum(m["accuracy"] for m in all_metrics) / len(all_metrics)
        avg_latency = sum(m["latency"] for m in all_metrics) / len(all_metrics)
        safety_rate = sum(1 for m in all_metrics if m["safety"]) / len(all_metrics) * 100

        report_lines.extend([
            "",
            "## Summary Statistics",
            f"- **Turns Completed**: {len(all_metrics)}/100",
            f"- **Average Accuracy**: {avg_accuracy:.1f}%",
            f"- **Average Latency**: {avg_latency:.0f}ms",
            f"- **Safety Pass Rate**: {safety_rate:.0f}%",
            f"- **Total Cited Tiles**: {sum(m['cited_tiles'] for m in all_metrics)}",
        ])

    # Write report
    report_path = ROOT / f"companion_flywheel_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\n{'='*80}")
    print(f"  Report: {report_path}")
    print(f"  Observations: {tmp_dir}/*.jsonl")
    print(f"{'='*80}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
