#!/usr/bin/env python3
"""
Layer -1: AI Surface Discovery

Proactively scans the codebase for AI surfaces (UI pages, edge functions,
cron jobs, RPCs) and compares against AI_SURFACES_MANIFEST.json to detect
new or changed surfaces that need test coverage.

This is what makes the self-improvement loop truly proactive:
when you add a new AI page, edge function, or cron job, this scanner
flags it before the next loop run.

Output:
  - AI_SURFACES_MANIFEST.json (full registry, updated each run)
  - NEW_SURFACES_REPORT.json (surfaces new since last manifest)
  - SCENARIO_DRIFT.json (existing surfaces whose selectors changed)

Usage:
  python tools/discover_ai_surfaces.py            # full scan
  python tools/discover_ai_surfaces.py --staged   # only staged files (pre-commit)
  python tools/discover_ai_surfaces.py --json     # JSON output only
"""

import json
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "AI_SURFACES_MANIFEST.json"
NEW_REPORT_PATH = ROOT / "NEW_SURFACES_REPORT.json"
DRIFT_PATH = ROOT / "SCENARIO_DRIFT.json"

# Patterns that identify an AI surface
AI_PATTERNS = {
    "verdict_label": re.compile(r'id="([a-z][\w-]*-verdict-label)"'),
    "verdict_box": re.compile(r'id="([a-z][\w-]*-verdict)"'),
    "summary_block": re.compile(r'id="([a-z][\w-]*-summary)"'),
    "source_chip": re.compile(r'id="([a-z][\w-]*-source-chip)"'),
    "edge_function_call": re.compile(r'/functions/v1/([a-z][\w-]+)'),
    "ai_rpc_call": re.compile(r"db\.rpc\(\s*['\"]([\w]+)['\"]"),
    "callAI": re.compile(r"\b(callAI|ai_gateway|platform-gateway)\b"),
    "mic_button": re.compile(r'id="mic-btn"'),
    "chat_input": re.compile(r'id="chat-input"'),
}

# Patterns for AI infrastructure changes
INFRA_PATTERNS = {
    "edge_function_dir": "supabase/functions/*/index.ts",
    "cron_schedule": re.compile(r"cron\.schedule\(\s*['\"]([\w-]+)['\"]"),
    "ai_truth_view": re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w*(?:ai|truth)\w*)", re.IGNORECASE),
    "ai_table": re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(ai_\w+|\w+_ai|agent_\w+)", re.IGNORECASE),
}

# Files to skip
SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", "dist", "build", "test-data-seeder"}
SKIP_PATTERNS = ["*.backup.html", "*-test.html", "*test*.spec.ts"]


def load_manifest() -> dict:
    """Load existing manifest or return empty structure."""
    if not MANIFEST_PATH.exists():
        return {
            "version": 1,
            "last_scan": None,
            "surfaces": {},
            "edge_functions": [],
            "cron_jobs": [],
        }
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "last_scan": None, "surfaces": {}, "edge_functions": [], "cron_jobs": []}


def find_html_pages() -> list:
    """Find all HTML files in the project root (no subdirs)."""
    pages = []
    for path in ROOT.glob("*.html"):
        if any(path.match(p) for p in SKIP_PATTERNS):
            continue
        pages.append(path)
    return pages


def scan_html_for_ai_patterns(html_path: Path) -> dict:
    """Scan a single HTML file for AI surface indicators."""
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    findings = {
        "verdict_labels": [],
        "verdict_boxes": [],
        "summary_blocks": [],
        "source_chips": [],
        "edge_functions": [],
        "ai_rpcs": [],
        "ai_calls": [],
        "interactive": False,
        "ai_score": 0,
    }

    for label_id in AI_PATTERNS["verdict_label"].findall(content):
        findings["verdict_labels"].append(label_id)
        findings["ai_score"] += 3

    for box_id in AI_PATTERNS["verdict_box"].findall(content):
        if not box_id.endswith("-label") and not box_id.endswith("-sub") and not box_id.endswith("-icon"):
            findings["verdict_boxes"].append(box_id)
            findings["ai_score"] += 2

    for sum_id in AI_PATTERNS["summary_block"].findall(content):
        findings["summary_blocks"].append(sum_id)
        findings["ai_score"] += 1

    for chip in AI_PATTERNS["source_chip"].findall(content):
        findings["source_chips"].append(chip)
        findings["ai_score"] += 1

    for fn in set(AI_PATTERNS["edge_function_call"].findall(content)):
        findings["edge_functions"].append(fn)
        findings["ai_score"] += 4

    for rpc in set(AI_PATTERNS["ai_rpc_call"].findall(content)):
        if any(kw in rpc for kw in ["semantic", "ai_", "agent", "callAI", "embed"]):
            findings["ai_rpcs"].append(rpc)
            findings["ai_score"] += 3

    if AI_PATTERNS["callAI"].search(content):
        findings["ai_calls"].append("callAI/gateway")
        findings["ai_score"] += 2

    if AI_PATTERNS["mic_button"].search(content) or AI_PATTERNS["chat_input"].search(content):
        findings["interactive"] = True
        findings["ai_score"] += 3

    return findings


def discover_edge_functions() -> list:
    """List all edge functions (supabase/functions/*/index.ts)."""
    fn_dir = ROOT / "supabase" / "functions"
    if not fn_dir.exists():
        return []
    fns = []
    for index_file in fn_dir.glob("*/index.ts"):
        fns.append(index_file.parent.name)
    return sorted(set(fns))


def discover_cron_jobs() -> list:
    """Find all pg_cron schedules across migrations."""
    cron_jobs = []
    mig_dir = ROOT / "supabase" / "migrations"
    if not mig_dir.exists():
        return cron_jobs
    for mig in mig_dir.glob("*.sql"):
        try:
            content = mig.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for job_name in INFRA_PATTERNS["cron_schedule"].findall(content):
            cron_jobs.append({"job": job_name, "migration": mig.name})
    return cron_jobs


def discover_all() -> dict:
    """Run full discovery and return the surface registry."""
    registry = {
        "version": 1,
        "last_scan": datetime.now().isoformat(),
        "surfaces": {},
        "edge_functions": discover_edge_functions(),
        "cron_jobs": discover_cron_jobs(),
    }

    for html_path in find_html_pages():
        findings = scan_html_for_ai_patterns(html_path)
        if findings.get("ai_score", 0) >= 3:  # threshold for "AI surface"
            registry["surfaces"][html_path.name] = findings

    return registry


def compare_manifests(old: dict, new: dict) -> dict:
    """Return diff between old and new manifests."""
    diff = {
        "new_surfaces": [],
        "removed_surfaces": [],
        "changed_surfaces": [],
        "new_edge_functions": [],
        "removed_edge_functions": [],
        "new_cron_jobs": [],
    }

    old_surfaces = old.get("surfaces", {})
    new_surfaces = new.get("surfaces", {})

    for name, data in new_surfaces.items():
        if name not in old_surfaces:
            diff["new_surfaces"].append({"name": name, "data": data})
        else:
            # Check if key selectors changed
            old_data = old_surfaces[name]
            old_labels = set(old_data.get("verdict_labels", []))
            new_labels = set(data.get("verdict_labels", []))
            if old_labels != new_labels:
                diff["changed_surfaces"].append({
                    "name": name,
                    "added_selectors": list(new_labels - old_labels),
                    "removed_selectors": list(old_labels - new_labels),
                })

    for name in old_surfaces:
        if name not in new_surfaces:
            diff["removed_surfaces"].append(name)

    old_fns = set(old.get("edge_functions", []))
    new_fns = set(new.get("edge_functions", []))
    diff["new_edge_functions"] = sorted(new_fns - old_fns)
    diff["removed_edge_functions"] = sorted(old_fns - new_fns)

    old_crons = {c["job"] for c in old.get("cron_jobs", [])}
    new_crons = {c["job"] for c in new.get("cron_jobs", [])}
    diff["new_cron_jobs"] = sorted(new_crons - old_crons)

    return diff


def main():
    json_only = "--json" in sys.argv

    if not json_only:
        print("=" * 70)
        print("LAYER -1: AI SURFACE DISCOVERY")
        print("=" * 70)

    old_manifest = load_manifest()
    new_manifest = discover_all()
    diff = compare_manifests(old_manifest, new_manifest)

    # Save updated manifest
    MANIFEST_PATH.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")

    # Save new-surfaces report (used by auto-generator)
    NEW_REPORT_PATH.write_text(json.dumps(diff, indent=2), encoding="utf-8")

    # Save drift report (existing surfaces whose selectors changed)
    drift = {
        "scan_time": datetime.now().isoformat(),
        "drifted_surfaces": diff["changed_surfaces"],
    }
    DRIFT_PATH.write_text(json.dumps(drift, indent=2), encoding="utf-8")

    if json_only:
        print(json.dumps({
            "new_surfaces": len(diff["new_surfaces"]),
            "changed_surfaces": len(diff["changed_surfaces"]),
            "removed_surfaces": len(diff["removed_surfaces"]),
            "new_edge_functions": len(diff["new_edge_functions"]),
            "new_cron_jobs": len(diff["new_cron_jobs"]),
            "total_surfaces": len(new_manifest["surfaces"]),
            "total_edge_functions": len(new_manifest["edge_functions"]),
            "total_cron_jobs": len(new_manifest["cron_jobs"]),
        }))
        return

    # Human-readable summary
    print(f"\nTotal AI surfaces discovered: {len(new_manifest['surfaces'])}")
    print(f"Total edge functions: {len(new_manifest['edge_functions'])}")
    print(f"Total cron jobs: {len(new_manifest['cron_jobs'])}")

    if diff["new_surfaces"]:
        print(f"\n[NEW] {len(diff['new_surfaces'])} new AI surface(s):")
        for s in diff["new_surfaces"]:
            score = s["data"].get("ai_score", 0)
            labels = s["data"].get("verdict_labels", [])
            print(f"  - {s['name']} (score: {score}, verdict_labels: {labels})")

    if diff["changed_surfaces"]:
        print(f"\n[CHANGED] {len(diff['changed_surfaces'])} surface(s) drifted:")
        for s in diff["changed_surfaces"]:
            print(f"  - {s['name']}")
            if s["added_selectors"]:
                print(f"      + {s['added_selectors']}")
            if s["removed_selectors"]:
                print(f"      - {s['removed_selectors']}")

    if diff["new_edge_functions"]:
        print(f"\n[NEW] {len(diff['new_edge_functions'])} new edge function(s):")
        for fn in diff["new_edge_functions"]:
            print(f"  - {fn}")

    if diff["new_cron_jobs"]:
        print(f"\n[NEW] {len(diff['new_cron_jobs'])} new cron job(s):")
        for job in diff["new_cron_jobs"]:
            print(f"  - {job}")

    if not any([diff["new_surfaces"], diff["changed_surfaces"], diff["new_edge_functions"], diff["new_cron_jobs"]]):
        print("\nNo new surfaces or changes detected. Manifest is current.")

    print(f"\nManifest saved: {MANIFEST_PATH.name}")
    print(f"Report saved: {NEW_REPORT_PATH.name}")
    print(f"Drift saved: {DRIFT_PATH.name}")

    # Exit code: 0 if no changes, 1 if new/changed surfaces detected
    has_changes = bool(
        diff["new_surfaces"] or diff["changed_surfaces"] or
        diff["new_edge_functions"] or diff["new_cron_jobs"]
    )
    sys.exit(1 if has_changes else 0)


if __name__ == "__main__":
    main()
