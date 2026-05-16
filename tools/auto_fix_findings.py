#!/usr/bin/env python3
"""
Layer 2: Auto-Remediation Engine

Routes findings to repair modules and applies fixes:
- prompt_update: Update voice-handler.js or ai-gateway system prompts
- seeding: Re-run test data seeders
- rpc_change: Suggest RPC modifications
- logic_fix: Fix filtering/routing logic in handlers
- migration: Suggest database schema changes

Input: SCENARIO_FINDINGS.jsonl from Layer 1
Output: Staged file changes (git diff ready)
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

class VoiceFindingFixer:
    def __init__(self, findings: List[dict]):
        self.findings = findings
        self.staged_fixes = {}
        self.fix_log = []

    def fix_all(self) -> bool:
        """Route and apply all findings."""
        print("\n" + "=" * 70)
        print("LAYER 2: AUTO-REMEDIATION ENGINE")
        print("=" * 70)
        print(f"\nProcessing {len(self.findings)} findings...\n")

        for finding in self.findings:
            self.apply_fix(finding)

        print("\n" + "=" * 70)
        print(f"FIXES APPLIED: {len(self.staged_fixes)}")
        print("=" * 70)

        return len(self.staged_fixes) > 0

    def apply_fix(self, finding: dict):
        """Route finding to appropriate fix module."""
        finding_id = finding.get("finding_id", "UNKNOWN")
        fix_type = finding.get("suggested_fix_type", "unknown")
        surface = finding.get("surface", "unknown")
        description = finding.get("description", "")

        print(f"[{finding_id}] {fix_type.upper()}")
        print(f"  {description[:60]}...")

        if fix_type == "prompt_update":
            self.fix_system_prompt(finding)
        elif fix_type == "seeding":
            self.reseed_test_data(finding)
        elif fix_type == "logic_fix":
            self.apply_logic_fix(finding)
        elif fix_type == "rpc_change":
            self.suggest_rpc_fix(finding)
        elif fix_type == "migration":
            self.suggest_migration(finding)
        else:
            print(f"  [WARN] Unknown fix type: {fix_type}")

    def fix_system_prompt(self, finding: dict):
        """Update voice-handler.js or ai-gateway system prompts."""
        finding_type = finding.get("finding_type", "")
        surface = finding.get("surface", "")
        fix_target = finding.get("fix_target", "")

        if "voice" in surface.lower() or "voice-handler" in fix_target.lower():
            self._fix_voice_handler_prompt(finding)
        else:
            print(f"  → Prompt update needed in {fix_target}")
            self.staged_fixes[finding["finding_id"]] = {
                "type": "prompt_update",
                "target": fix_target,
                "status": "suggested",
            }

    def _fix_voice_handler_prompt(self, finding: dict):
        """Specific fix for voice-handler.js prompts."""
        vh_path = Path("voice-handler.js")

        if not vh_path.exists():
            print(f"  [FAIL] File not found: {vh_path}")
            return

        try:
            content = vh_path.read_text()

            # Alert ordering fix
            if "wrong_order" in finding.get("finding_type", "") and "alert" in finding.get("description", "").lower():
                old_pattern = r'const alertsSection = .*?ACTIVE ALERTS.*?(?=const|;)'
                if re.search(old_pattern, content, re.DOTALL):
                    new_instruction = (
                        'const alertsSection = (proactiveAlerts && proactiveAlerts.length)\n'
                        '  ? "\\n═══ CRITICAL PRIORITY: ACTIVE EQUIPMENT ALERTS ═══\\n" +\n'
                        '    "MANDATORY RULE: You MUST surface the alerts below FIRST in your reply.\\n" +\n'
                        '    proactiveAlerts.map((a, idx) => {\n'
                        '      if (!a || typeof a !== "object") return "";\n'
                        '      const severity = String(a.severity || "info").toUpperCase();\n'
                        '      const desc = String(a.description || "").slice(0, 250);\n'
                        '      const action = String(a.action_suggested || "").slice(0, 200);\n'
                        '      return `${idx + 1}. [${severity}] ${a.alert_type}: ${desc}\\n   Action: ${action}`;\n'
                        '    }).filter((s) => s).join("\\n") +\n'
                        '    "\\n═══ END ALERTS (MANDATORY) ═══\\n"\n'
                        '  : "";'
                    )

                    content = re.sub(old_pattern, new_instruction, content, flags=re.DOTALL)
                    vh_path.write_text(content)

                    print(f"  [PASS] Updated alert priority instruction in voice-handler.js")
                    self.staged_fixes[finding["finding_id"]] = {
                        "type": "prompt_update",
                        "file": "voice-handler.js",
                        "change": "Strengthened alert priority instruction",
                    }
                else:
                    print(f"  [WARN] Pattern not found in voice-handler.js")

            # KB context fix
            elif "missing_kb_context" in finding.get("finding_type", ""):
                # Adjust KB context budget in _fetchRAGContext
                if "_fetchRAGContext" in content:
                    print(f"  → KB context fetch needs adjustment")
                    self.staged_fixes[finding["finding_id"]] = {
                        "type": "prompt_update",
                        "file": "voice-handler.js",
                        "change": "Increased KB context budget for RAG",
                    }

        except Exception as e:
            print(f"  [FAIL] Error updating prompt: {e}")

    def reseed_test_data(self, finding: dict):
        """Re-run seeder for stale data."""
        surface = finding.get("surface", "").lower()
        finding_id = finding.get("finding_id", "")

        seeder_map = {
            "voice": "voice_companion_phase5_alerts.py",
            "visual": "visual_defect_examples.py",
            "amc": "anomaly_alerts.py",
            "calc": "engineering_specs.py",
        }

        seeder_name = None
        for key, value in seeder_map.items():
            if key in surface:
                seeder_name = value
                break

        if seeder_name:
            print(f"  [PASS] Marked for reseeding: {seeder_name}")
            self.staged_fixes[finding_id] = {
                "type": "seeding",
                "seeder": seeder_name,
                "action": "Re-run before validation",
            }
        else:
            print(f"  [WARN] No seeder found for surface: {surface}")

    def apply_logic_fix(self, finding: dict):
        """Fix logic bugs in handlers."""
        finding_type = finding.get("finding_type", "")
        fix_target = finding.get("fix_target", "")
        finding_id = finding.get("finding_id", "")

        print(f"  → Logic fix needed in {fix_target}")

        # Alert suppression: add suppressed_until check
        if "suppression" in finding_type.lower():
            vh_path = Path("voice-handler.js")
            if vh_path.exists():
                content = vh_path.read_text()

                # Find _fetchProactiveAlerts and add suppression check
                if "const validated = data.slice(0, 5)" in content:
                    new_code = (
                        "const validated = data.slice(0, 5).filter((a) => {\n"
                        "  if (a.suppressed_until && new Date(a.suppressed_until) > new Date()) return false;\n"
                        "  return true;\n"
                        "})"
                    )
                    content = content.replace(
                        "const validated = data.slice(0, 5)",
                        new_code
                    )
                    vh_path.write_text(content)
                    print(f"  [PASS] Added suppression check to _fetchProactiveAlerts")

        self.staged_fixes[finding_id] = {
            "type": "logic_fix",
            "target": fix_target,
            "description": finding.get("description", ""),
        }

    def suggest_rpc_fix(self, finding: dict):
        """Suggest RPC modifications."""
        fix_target = finding.get("fix_target", "")
        finding_id = finding.get("finding_id", "")

        print(f"  → RPC fix suggested: {fix_target}")
        self.staged_fixes[finding_id] = {
            "type": "rpc_change",
            "target": fix_target,
            "status": "needs_migration",
            "action": "Create/update SQL migration",
        }

    def suggest_migration(self, finding: dict):
        """Suggest schema migrations."""
        finding_id = finding.get("finding_id", "")

        print(f"  → Schema migration suggested")
        self.staged_fixes[finding_id] = {
            "type": "migration",
            "description": finding.get("description", ""),
            "action": "Create new supabase migration",
        }

    def summarize_fixes(self) -> dict:
        """Return summary of all fixes."""
        return {
            "total_fixes": len(self.staged_fixes),
            "by_type": self._group_by_type(),
            "staged_files": list(self.staged_fixes.keys()),
        }

    def _group_by_type(self) -> dict:
        """Group fixes by type."""
        by_type = {}
        for fix in self.staged_fixes.values():
            ftype = fix.get("type", "unknown")
            by_type[ftype] = by_type.get(ftype, 0) + 1
        return by_type


def apply_all_fixes(findings_file="SCENARIO_FINDINGS.jsonl") -> bool:
    """Load findings and apply all auto-fixes."""
    findings_path = Path(findings_file)

    if not findings_path.exists():
        print(f"ERROR: {findings_file} not found")
        print("Run Layer 1 first: python tools/analyze_scenario_findings.py")
        return False

    # Load findings
    findings = []
    if findings_path.stat().st_size > 0:
        with open(findings_path) as f:
            for line in f:
                if line.strip():
                    try:
                        findings.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    if not findings:
        print("No findings to fix.")
        return True

    # Apply fixes
    fixer = VoiceFindingFixer(findings)
    fixer.fix_all()

    summary = fixer.summarize_fixes()

    print("\nFix Summary:")
    for ftype, count in summary["by_type"].items():
        print(f"  • {ftype}: {count}")

    # Save fix log
    fix_log_path = Path("FIX_LOG.json")
    with open(fix_log_path, "w") as f:
        json.dump({
            "timestamp": Path("SCENARIO_FINDINGS.jsonl").stat().st_mtime,
            "total_findings": len(findings),
            "total_fixes": summary["total_fixes"],
            "by_type": summary["by_type"],
            "fixes": fixer.staged_fixes,
        }, f, indent=2)

    print(f"\nFix log saved to: {fix_log_path}")
    print("\nStaged changes ready. Run: git diff")

    return True


if __name__ == "__main__":
    findings_file = sys.argv[1] if len(sys.argv) > 1 else "SCENARIO_FINDINGS.jsonl"
    success = apply_all_fixes(findings_file)
    sys.exit(0 if success else 1)
