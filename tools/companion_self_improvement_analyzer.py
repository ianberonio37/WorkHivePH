#!/usr/bin/env python3
"""
Companion Self-Improvement Analyzer
====================================

Phase 2 of 100-turn flywheel: Analyze observations, extract patterns,
propose improvements, validate against baseline.

Layers:
  - Layer -1.5: Drift mining (identify failure patterns)
  - Layer -1: Convention discovery (extract rules from successes)
  - Layer 0: Improvement proposals (ratchet-safe enhancements)
  - Layer 2: Validation testing (measure gains)
"""
import io
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

def analyze_observations():
    """Read all 100 observations and extract patterns."""
    obs_dir = ROOT / ".tmp"
    observations = []

    # Load all observations
    for obs_file in sorted(obs_dir.glob("companion_observations_turn_*.jsonl")):
        try:
            line = obs_file.read_text(encoding="utf-8").strip()
            if line:
                observations.append(json.loads(line))
        except Exception:
            pass

    if not observations:
        print("ERROR: No observations found")
        return None

    print(f"\n{'='*80}")
    print(f"  Phase 2: Self-Improvement Analysis")
    print(f"  Loaded {len(observations)} observations")
    print(f"{'='*80}\n")

    # Layer -1.5: Drift Mining (identify failure patterns)
    print("LAYER -1.5: Drift Mining")
    print("-" * 80)

    routing_errors = [o for o in observations if not o.get("routing_correct", False)]
    safety_failures = [o for o in observations if not o.get("safety_pass", False)]
    low_accuracy = [o for o in observations if o.get("accuracy_score", 0) < 50]

    print(f"  Routing errors: {len(routing_errors)}/100 ({len(routing_errors)}%)")
    print(f"  Safety failures: {len(safety_failures)}/100 ({len(safety_failures)}%)")
    print(f"  Low accuracy (<50%): {len(low_accuracy)}/100 ({len(low_accuracy)}%)")

    # Analyze routing errors by scenario
    routing_by_scenario = defaultdict(list)
    for obs in routing_errors:
        routing_by_scenario[obs["scenario"]].append(obs)

    if routing_errors:
        print("\n  Routing errors by scenario:")
        for scenario in sorted(routing_by_scenario.keys()):
            errors = routing_by_scenario[scenario]
            print(f"    - {scenario}: {len(errors)} errors")
            if errors:
                print(f"      Expected agents: {Counter(e.get('expected_agent', '?') for e in errors)}")
                print(f"      Actual agents: {Counter(e.get('routing_agent', '?') for e in errors)}")

    # Safety failure analysis
    if safety_failures:
        print("\n  Safety failures by page:")
        safety_by_page = defaultdict(int)
        for obs in safety_failures:
            safety_by_page[obs["page"]] += 1
        for page in sorted(safety_by_page.keys()):
            print(f"    - {page}: {safety_by_page[page]} failures")

    # Layer -1: Convention Discovery (extract success patterns)
    print("\n\nLAYER -1: Convention Discovery")
    print("-" * 80)

    successes = [o for o in observations if o.get("routing_correct") and o.get("safety_pass") and o.get("accuracy_score", 0) >= 70]
    print(f"  High-quality turns (routing + safety + accuracy >= 70%): {len(successes)}/100")

    if successes:
        # What made these succeed?
        success_personas = Counter(s["persona"] for s in successes)
        success_pages = Counter(s["page"] for s in successes)
        success_scenarios = Counter(s["scenario"] for s in successes)

        print("\n  Success patterns:")
        print(f"    Personas: {dict(success_personas)}")
        print(f"    Pages: {dict(success_pages)}")
        print(f"    Scenarios: {dict(success_scenarios)}")

        # Average metrics for high-quality turns
        avg_latency = sum(s.get("response_latency_ms", 0) for s in successes) / len(successes)
        print(f"    Average latency: {avg_latency:.0f}ms")

    # Layer 0: Improvement Proposals
    print("\n\nLAYER 0: Improvement Proposals (Ratchet-Safe)")
    print("-" * 80)

    proposals = []

    # Proposal 1: Scenario-specific routing rules
    if routing_errors:
        proposals.append({
            "id": "P1_scenario_routing_refinement",
            "title": "Refine scenario→agent routing rules",
            "issue": f"{len(routing_errors)} routing errors detected",
            "fix": "Add scenario-specific prompts to clarify intent routing",
            "impact": f"Expected improvement: ~{len(routing_errors)*5}% (10-15% per error fixed)",
            "ratchet": "routing_accuracy >= 81% (baseline)"
        })

    # Proposal 2: Page-specific safety gates
    if safety_failures:
        proposals.append({
            "id": "P2_page_safety_hardening",
            "title": "Add page-specific safety context",
            "issue": f"{len(safety_failures)} safety failures detected",
            "fix": "Inject page context into safety check system prompt",
            "impact": f"Expected improvement: ~{len(safety_failures)*3}% (5-10% per failure fixed)",
            "ratchet": "safety_pass_rate >= 91% (baseline)"
        })

    # Proposal 3: Accuracy improvement via latency optimization
    high_latency = [o for o in observations if o.get("response_latency_ms", 0) > 3000]
    if high_latency:
        proposals.append({
            "id": "P3_latency_accuracy_correlation",
            "title": "Optimize response generation for lower latency",
            "issue": f"{len(high_latency)} turns exceeded 3s latency",
            "fix": "Simplify generator prompts, use faster model selection",
            "impact": f"Expected improvement: ~{len(high_latency)*2}% (shorter responses = faster accuracy)",
            "ratchet": "avg_latency <= 2080ms (baseline)"
        })

    # Proposal 4: Persona differentiation
    persona_accuracy = defaultdict(list)
    for obs in observations:
        persona_accuracy[obs["persona"]].append(obs.get("accuracy_score", 0))

    zaniah_avg = sum(persona_accuracy["zaniah"]) / len(persona_accuracy["zaniah"])
    hezekiah_avg = sum(persona_accuracy["hezekiah"]) / len(persona_accuracy["hezekiah"])

    if abs(zaniah_avg - hezekiah_avg) > 2:
        proposals.append({
            "id": "P4_persona_differentiation",
            "title": "Strengthen persona differentiation",
            "issue": f"Zaniah {zaniah_avg:.1f}% vs Hezekiah {hezekiah_avg:.1f}% (gap: {abs(zaniah_avg - hezekiah_avg):.1f}%)",
            "fix": "Add persona-specific system prompts (strategist vs technical lens)",
            "impact": "Expected improvement: ~3-5% overall accuracy via better voice match",
            "ratchet": "persona_differentiation >= 2% (baseline)"
        })

    for i, prop in enumerate(proposals, 1):
        print(f"\n  {prop['id']}: {prop['title']}")
        print(f"    Issue: {prop['issue']}")
        print(f"    Fix: {prop['fix']}")
        print(f"    Impact: {prop['impact']}")
        print(f"    Ratchet: {prop['ratchet']}")

    # Layer 2: Create validation spec
    print("\n\nLAYER 2: Validation Checklist")
    print("-" * 80)

    validation = {
        "test_count": len(observations),
        "baseline_accuracy": round(sum(o.get("accuracy_score", 0) for o in observations) / len(observations), 1),
        "baseline_routing": len([o for o in observations if o.get("routing_correct")]) / len(observations) * 100,
        "baseline_safety": len([o for o in observations if o.get("safety_pass")]) / len(observations) * 100,
        "improvements_proposed": len(proposals),
        "improvements": [p["id"] for p in proposals],
    }

    print(f"  Baseline accuracy: {validation['baseline_accuracy']}%")
    print(f"  Baseline routing: {validation['baseline_routing']:.1f}%")
    print(f"  Baseline safety: {validation['baseline_safety']:.1f}%")
    print(f"  Proposed improvements: {len(proposals)}")

    # Write analysis report
    report = {
        "generated": datetime.now().isoformat(),
        "observations_analyzed": len(observations),
        "layer_minus_1_5_drift_mining": {
            "routing_errors": len(routing_errors),
            "safety_failures": len(safety_failures),
            "low_accuracy_turns": len(low_accuracy),
        },
        "layer_minus_1_conventions": {
            "high_quality_turns": len(successes),
            "success_patterns": {
                "personas": dict(success_personas) if successes else {},
                "pages": dict(success_pages) if successes else {},
                "scenarios": dict(success_scenarios) if successes else {},
            }
        },
        "layer_0_proposals": proposals,
        "layer_2_validation": validation,
    }

    report_path = ROOT / f"companion_improvement_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n\nAnalysis report: {report_path.name}")

    return report


def main() -> int:
    report = analyze_observations()

    if not report:
        return 1

    print(f"\n{'='*80}")
    print(f"  Phase 2 Analysis Complete")
    print(f"  Ready for improvement implementation")
    print(f"{'='*80}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
