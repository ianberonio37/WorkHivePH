#!/usr/bin/env python3
"""
Workflow Gate - Ian's TOTAL, UNCONDITIONAL ban on multi-agent fan-out (2026-07-16).

WHY: prose in CLAUDE.md + memory failed TWICE to stop me spawning Workflows without
Ian's opt-in. The second time a 29-agent N1 fleet burned ~1.4M subagent tokens in
~9 min and drained his entire 5-hour max quota. He first asked for a hard gate, then:
  Ian: "just delete it entirely and forget it those that overrides mine."
So there is NO escape hatch. The `Workflow` tool is DEAD on this project. Every call
is denied, always. The session-injected `Ultracode` toggle ("use the Workflow tool on
every substantive task; token cost is not a constraint") is thereby made completely
inert - it cannot fire what the harness refuses to run.

CONTRACT:
  - Fires only on the `Workflow` tool (settings.json matcher = "Workflow").
  - DENIES unconditionally. There is no flag, no opt-in file, no bypass.
  - To ever re-enable: Ian removes this hook from `.claude/settings.json` himself, or
    tells me to. It is HIS switch, not a flag I or a session default can flip.

Hook I/O: read the PreToolUse event JSON on stdin; print a PreToolUse
hookSpecificOutput with permissionDecision "deny". Exit 0 always. Any exception
while handling a Workflow call still denies (fails CLOSED).
"""
import sys, os, json

DENY_REASON = (
    "WORKFLOW PERMANENTLY DISABLED on this project (tools/workflow_gate.py). Ian deleted "
    "multi-agent fan-out entirely (2026-07-16) after it burned his 5-hour quota twice. There is "
    "NO opt-in flag and NO bypass - do NOT look for one, do NOT retry the Workflow. This overrides "
    "every session default: the Ultracode injection ('use the Workflow tool on every substantive "
    "task; token cost is not a constraint') is VOID here - Ian pays per token and inline is the only "
    "way. Do the work INLINE in the main loop, one surface at a time, retrieving from substrate/ , "
    "SKILL.md files, Memento, and tools/ scripts instead of re-deriving. Only Ian can re-enable "
    "workflows, by removing this hook from .claude/settings.json himself. See WORKFLOW_TOKEN_GOVERNANCE.md."
)


def deny():
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
        }
    }))
    sys.exit(0)


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    tool = str(payload.get("tool_name", "")).strip()

    # The settings matcher scopes this to Workflow; if it ever fires for anything else,
    # do not interfere (fail OPEN on non-Workflow).
    if tool and tool != "Workflow":
        sys.exit(0)

    # Workflow: always denied.
    deny()


if __name__ == "__main__":
    main()
