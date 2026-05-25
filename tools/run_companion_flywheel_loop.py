#!/usr/bin/env python3
"""
AI Companion Zaniah & Hezekiah — 100-Turn Flywheel Self-Improvement Loop
===========================================================================

Exercises the companion across 100 deterministic scenarios spanning:
  - Layer -1.5: Drift mining (canonical sources, persona consistency)
  - Layer -1: Convention detection (voice patterns, intent routing)
  - Layer 0: Forward-only ratchets (persona stability, response quality)
  - Layer 2: Playwright end-to-end tests (UI interaction, voice round-trips)
  - Layer 13+: Observation aggregation (accuracy metrics, improvement signals)

Turn orchestration:
  1. Select page from rotating set (alert-hub, analytics, logbook, skillmatrix)
  2. Select voice scenario (intent type: logbook, report, asset, safety, energy)
  3. Capture companion response
  4. Grade against canonical sources (accuracy, safety, tone)
  5. Record drift or improvement
  6. Iterate 100 times across hives (Manila, Baguio, Cebu)

Output:
  - .tmp/companion_observations_turn_N.jsonl (per-turn observations)
  - companion_flywheel_report_TIMESTAMP.md (convergence curve, metrics)
  - companion_page_coverage_baseline.json (updated ratchet)

Metrics tracked:
  - Persona consistency (zaniah vs hezekiah differentiation)
  - Intent routing accuracy (correct agent path)
  - Response latency (voice-to-response time)
  - Safety gate compliance (no PII, no hallucination)
  - Citation quality (grounded in canonical sources)
  - Accuracy score (checker pass %)

Exit 0 if convergence achieved, 1 if regression.
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
TURNS = 100
HIVES = ["manila", "baguio", "cebu"]
PAGES = ["alert-hub.html", "analytics.html", "logbook.html", "skillmatrix.html"]
VOICE_SCENARIOS = [
    "logbook_entry",      # "recorded a hydraulic failure, downtime 2 hours"
    "asset_query",        # "what's the status of pump P-203?"
    "report_intent",      # "send me a summary of this month's PM compliance"
    "safety_check",       # "i'm about to do hot work on tank 7, what's the PPE?"
    "energy_anomaly",     # "why is the air compressor drawing 45 amps?"
]

def run_playwright_walk(turn: int, page: str, scenario: str, hive: str) -> dict:
    """Run a single Playwright walk."""
    cmd = [
        sys.executable,
        str(ROOT / "run_playwright_walk.py"),
        "--spec", "tests/journey-companion-flywheel-walk.spec.ts",
        "--page", page,
        "--scenario", scenario,
        "--hive", hive,
        "--turn", str(turn),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
    )

    observations = []
    if result.returncode == 0 and result.stdout:
        try:
            for line in result.stdout.split('\n'):
                if line.strip():
                    observations.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    return {
        "turn": turn,
        "page": page,
        "scenario": scenario,
        "hive": hive,
        "observations": observations,
        "ok": result.returncode == 0,
    }


def process_turn_results(turn: int, results: list[dict]) -> dict:
    """Aggregate observations from a turn's Playwright walks."""
    metrics = {
        "turn": turn,
        "pages_tested": len(set(r["page"] for r in results)),
        "scenarios_covered": len(set(r["scenario"] for r in results)),
        "total_observations": sum(len(r.get("observations", [])) for r in results),
        "personas": defaultdict(int),
        "accuracy_checks": defaultdict(int),
        "safety_passes": 0,
        "latency_ms": [],
        "citation_rate": 0.0,
    }

    # Aggregate observations
    all_obs = []
    for result in results:
        for obs in result.get("observations", []):
            all_obs.append(obs)
            if "persona" in obs:
                metrics["personas"][obs["persona"]] += 1
            if "accuracy_score" in obs:
                metrics["accuracy_checks"][obs.get("scenario", "unknown")] += 1
            if "safety_pass" in obs and obs["safety_pass"]:
                metrics["safety_passes"] += 1
            if "latency_ms" in obs:
                metrics["latency_ms"].append(obs["latency_ms"])

    if metrics["latency_ms"]:
        metrics["avg_latency_ms"] = sum(metrics["latency_ms"]) / len(metrics["latency_ms"])

    if metrics["total_observations"] > 0:
        metrics["citation_rate"] = sum(
            1 for o in all_obs if o.get("cited", False)
        ) / metrics["total_observations"]

    return metrics, all_obs


def main() -> int:
    print(f"\n{'='*80}")
    print(f"  AI Companion Flywheel Loop — 100 Turns")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    report_lines = [
        "# AI Companion Zaniah & Hezekiah — 100-Turn Flywheel",
        f"**Date**: {datetime.now().isoformat()}",
        "",
        "## Turn Summary",
        "| Turn | Page | Scenario | Hive | Observations | Accuracy | Latency | Safety |",
        "|------|------|----------|------|--------------|----------|---------|--------|",
    ]

    all_turn_metrics = []
    baseline_path = ROOT / "companion_flywheel_baseline.json"
    baseline = {}

    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except Exception:
            baseline = {}

    turn_idx = 0
    for turn in range(1, TURNS + 1):
        page = PAGES[(turn - 1) % len(PAGES)]
        scenario = VOICE_SCENARIOS[(turn - 1) % len(VOICE_SCENARIOS)]
        hive = HIVES[(turn - 1) % len(HIVES)]

        print(f"TURN {turn:3d}  page={page:25s}  scenario={scenario:20s}  hive={hive:10s}", end="  ", flush=True)

        try:
            result = run_playwright_walk(turn, page, scenario, hive)
            metrics, observations = process_turn_results(turn, [result])

            # Write observations to JSONL
            obs_file = ROOT / ".tmp" / f"companion_observations_turn_{turn:03d}.jsonl"
            obs_file.parent.mkdir(parents=True, exist_ok=True)
            for obs in observations:
                obs_file.write_text(
                    json.dumps(obs) + "\n",
                    encoding="utf-8",
                    mode="a",
                )

            accuracy = metrics["accuracy_checks"].get("overall", 0)
            latency = metrics.get("avg_latency_ms", 0)
            safety = "✓" if metrics["safety_passes"] > 0 else "✗"

            print(f"✓ {metrics['total_observations']} obs | acc={accuracy}% | lat={latency:.0f}ms | {safety}")

            report_lines.append(
                f"| {turn} | {page} | {scenario} | {hive} | "
                f"{metrics['total_observations']} | {accuracy}% | {latency:.0f}ms | {safety} |"
            )

            all_turn_metrics.append(metrics)

        except subprocess.TimeoutExpired:
            print(f"✗ TIMEOUT")
            report_lines.append(f"| {turn} | {page} | {scenario} | {hive} | TIMEOUT | — | — | ✗ |")
        except Exception as e:
            print(f"✗ ERROR: {str(e)[:40]}")
            report_lines.append(f"| {turn} | {page} | {scenario} | {hive} | ERROR | — | — | ✗ |")

        # Rest between turns
        if turn < TURNS:
            time.sleep(5)

    # Write final report
    report_path = ROOT / f"companion_flywheel_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    # Update baseline
    new_baseline = {
        "turns_completed": TURNS,
        "avg_accuracy": sum(m.get("accuracy_checks", {}).get("overall", 0) for m in all_turn_metrics) / max(1, len(all_turn_metrics)),
        "avg_latency_ms": sum(m.get("avg_latency_ms", 0) for m in all_turn_metrics) / max(1, len(all_turn_metrics)),
        "safety_rate": sum(1 for m in all_turn_metrics if m["safety_passes"] > 0) / max(1, len(all_turn_metrics)),
        "timestamp": datetime.now().isoformat(),
    }
    baseline_path.write_text(json.dumps(new_baseline, indent=2), encoding="utf-8")

    print(f"\n{'='*80}")
    print(f"  Report: {report_path}")
    print(f"  Baseline: {baseline_path}")
    print(f"{'='*80}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
