"""
Build Substrate Manifest (Layer -1.5, P1 roadmap 2026-05-27).
==============================================================
Aggregates every pattern-miner output + drift-detector report into a single
JSON file. This is the substrate layer's source of truth — answers "what
patterns are emerging and what proposals are pending?" without making
the user read 8 separate report files.

Inputs (all optional; included if present):
  edge_pattern_mining_report.json
  html_pattern_mining_report.json
  migration_pattern_mining_report.json
  seeder_pattern_mining_report.json
  validator_pattern_mining_report.json
  js_module_pattern_mining_report.json
  python_tool_pattern_mining_report.json
  skill_rules_mining_report.json
  test_page_drift_report.json
  validator_self_coverage_report.json
  canonical_drift_platform_report.json
  auto_discovery_report.json
  NEW_SURFACES_REPORT.json

Output:
  substrate_manifest.json — single aggregator
  substrate_manifest.md   — human-readable summary

Exit codes:
  0  manifest generated (always; this is informational, not gating)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "substrate_manifest.json"
OUT_MD = ROOT / "substrate_manifest.md"

SOURCES = [
    ("Edge fn patterns",          "edge_pattern_mining_report.json"),
    ("HTML patterns",             "html_pattern_mining_report.json"),
    ("Migration patterns",        "migration_pattern_mining_report.json"),
    ("Seeder patterns",           "seeder_pattern_mining_report.json"),
    ("Validator patterns",        "validator_pattern_mining_report.json"),
    ("JS module patterns",        "js_module_pattern_mining_report.json"),
    ("Python tool patterns",      "python_tool_pattern_mining_report.json"),
    ("Skill rules",               "skill_rules_mining_report.json"),
    ("Test page drift",           "test_page_drift_report.json"),
    ("Validator self coverage",   "validator_self_coverage_report.json"),
    ("Canonical drift",           "canonical_drift_platform_report.json"),
    ("Auto-discovery",            "auto_discovery_report.json"),
    ("New surfaces",              "NEW_SURFACES_REPORT.json"),
]


def summarize(label: str, path: Path) -> dict:
    if not path.exists():
        return {"label": label, "file": path.name, "present": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return {"label": label, "file": path.name, "present": True, "error": str(e)[:120]}
    out: dict = {"label": label, "file": path.name, "present": True}
    # Surface key counts without dragging the full report in.
    if isinstance(data, dict):
        for key in ("total", "count", "warnings", "issues", "proposals", "drift", "summary"):
            if key in data:
                out[key] = data[key]
        if "proposals" in data and isinstance(data["proposals"], list):
            out["proposal_count"] = len(data["proposals"])
        if "items" in data and isinstance(data["items"], list):
            out["item_count"] = len(data["items"])
    elif isinstance(data, list):
        out["item_count"] = len(data)
    return out


def main() -> int:
    rows = [summarize(label, ROOT / f) for label, f in SOURCES]
    present = sum(1 for r in rows if r.get("present"))

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources":      len(SOURCES),
        "present":      present,
        "absent":       len(SOURCES) - present,
        "summaries":    rows,
    }
    OUT_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Human-readable summary
    lines = [
        f"# Substrate Manifest — {manifest['generated_at']}",
        "",
        f"**Aggregates {len(SOURCES)} pattern-miner + drift-detector outputs into one view.**",
        "",
        f"- Present: {present} / {len(SOURCES)}",
        f"- Absent:  {len(SOURCES) - present}",
        "",
        "## Per-source summary",
        "",
        "| Source | Present | Notes |",
        "|---|---|---|",
    ]
    for r in rows:
        if not r.get("present"):
            lines.append(f"| {r['label']} | no | (file missing — miner not run) |")
            continue
        notes = []
        for k in ("total", "count", "warnings", "drift", "proposal_count", "item_count"):
            if k in r:
                notes.append(f"`{k}`: {r[k]}")
        if r.get("error"):
            notes.append(f"error: {r['error']}")
        lines.append(f"| {r['label']} | yes | {' · '.join(notes) or '—'} |")

    lines += [
        "",
        "## How to use",
        "",
        "Run this tool once per session to see if any miner surfaced new",
        "proposals worth promoting via `/harden`. The substrate layer is the",
        "earliest warning system — patterns that fire 3+ times across files",
        "should auto-promote to validators.",
        "",
        f"Generated by `tools/build_substrate_manifest.py`.",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Substrate manifest: {present}/{len(SOURCES)} miner outputs present.")
    print(f"  See: {OUT_JSON.relative_to(ROOT)} + {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
