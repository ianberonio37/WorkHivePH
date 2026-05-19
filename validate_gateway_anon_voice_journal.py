"""
ai-gateway anon-friendly voice-journal contract validator
==========================================================
Locks in the 2026-05-19 fix that made voice-journal the platform's
anon-friendly onboarding companion. The bug it prevents: every other
agent in ai-gateway requires Supabase Auth, but voice-journal MUST
let anonymous callers through because Step D made Rosa the default
persona for first-time visitors — workers talk to her BEFORE they
sign up.

When ai-gateway hard-required auth on voice-journal, the platform
silently degraded to "Sorry, I'm offline" on every first-touch
conversation because:
  1. voice-handler.js POSTs to ai-gateway with the worker's anon JWT
  2. ai-gateway returned 401 "Sign-in required"
  3. voice-handler's try/catch fired _generateFallbackReply
  4. User saw canned offline copy instead of Rosa's strategist voice

Layer 1 — ANON_OK_AGENTS set declared in ai-gateway/index.ts       [FAIL]
  The gateway must declare an `ANON_OK_AGENTS` Set (or equivalent
  literal containing the string "voice-journal") near the top of the
  auth check so reviewers see the policy at a glance. Without this
  set, the auth gate falls back to the default "all agents require
  auth" behavior and the bug returns.

Layer 2 — Auth gate references ANON_OK_AGENTS                      [FAIL]
  The `if (!user)` block must skip the 401 when the requested agent
  is in ANON_OK_AGENTS. We grep for the pattern
  `if (!user && !ANON_OK_AGENTS.has(agent))` or any equivalent guard
  that excludes voice-journal from the auth requirement.

Layer 3 — Anon-safe persistence — saveTurn / persistJournalEntry
  guarded on authUid (or equivalent non-null check)                [FAIL]
  agent_memory and voice_journal_entries are RLS-keyed on auth_uid.
  If the gateway writes a turn under a null auth_uid the insert
  returns 401 and the gateway's own success path 502s — silently
  re-triggering the offline fallback for the user. The persistence
  block must therefore be guarded so anon callers skip the writes.

Layer 4 — voice-journal listed in AGENT_ROUTES                     [FAIL]
  The set is meaningless if voice-journal isn't actually a registered
  agent. Final structural check.

History:
  2026-05-19 — User saw Rosa stuck at "Sorry, I'm offline" even
  after Step C + Step D shipped. Root cause was the auth wall here.
  Fix in commit f5a8d99. This validator captures the fix as policy.

Skills consulted: ai-engineer (gateway-routing pattern + per-agent
auth posture), security (PII boundary preserved — only voice-journal
opens, every other route stays auth-walled), multitenant-engineer
(RLS-keyed persistence guarded on authUid for anon paths).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import format_result


ROOT = Path(__file__).resolve().parent
GATEWAY_PATH = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def check_anon_ok_set_declared(content: str) -> list[dict]:
    """L1 — ANON_OK_AGENTS set exists and contains voice-journal."""
    if not content:
        return [{"check": "anon_ok_set_declared",
                 "reason": f"{GATEWAY_PATH.relative_to(ROOT).as_posix()} not found"}]
    # Accept any TS pattern that declares the set with voice-journal in it:
    #   const ANON_OK_AGENTS = new Set([... "voice-journal" ...])
    #   const ANON_OK_AGENTS: Set<string> = new Set([... 'voice-journal' ...])
    pattern = re.compile(
        r"\bANON_OK_AGENTS\b[^=]{0,80}=\s*new\s+Set\s*\(\s*\[[^\]]*['\"]voice-journal['\"]",
        re.DOTALL,
    )
    if not pattern.search(content):
        return [{
            "check": "anon_ok_set_declared",
            "reason": (
                "ai-gateway/index.ts is missing the `ANON_OK_AGENTS` Set "
                "containing 'voice-journal'. Without this, the gateway "
                "falls back to auth-walling every agent — which silently "
                "degrades the worker's first-touch conversation with Rosa "
                "to the 'Sorry, I'm offline' canned reply. See commit f5a8d99."
            ),
        }]
    return []


def check_auth_gate_references_set(content: str) -> list[dict]:
    """L2 — the auth check excludes ANON_OK_AGENTS members from the 401."""
    if not content:
        return []
    # Grep for the conditional that skips Sign-in required when the
    # agent is anon-friendly. Accept either order:
    #   !user && !ANON_OK_AGENTS.has(agent)
    #   !ANON_OK_AGENTS.has(agent) && !user
    patterns = [
        re.compile(r"!user\s*&&\s*!ANON_OK_AGENTS\.has\("),
        re.compile(r"!ANON_OK_AGENTS\.has\([^)]*\)\s*&&\s*!user"),
    ]
    if not any(p.search(content) for p in patterns):
        return [{
            "check": "auth_gate_references_set",
            "reason": (
                "The 401 'Sign-in required' guard does not skip "
                "ANON_OK_AGENTS members. Required pattern: "
                "`if (!user && !ANON_OK_AGENTS.has(agent)) { return 401 }`. "
                "Without it the anon-allow set has no effect and the "
                "offline bug returns."
            ),
        }]
    return []


def check_persistence_guarded_on_authuid(content: str) -> list[dict]:
    """L3 — saveTurn and persistJournalEntry must NOT run for anon callers."""
    if not content:
        return []
    issues: list[dict] = []
    # saveTurn must be inside an `if (authUid)` block. We allow either
    # an explicit if-guard wrapping the call, or the use of `authUid`
    # in the MemoryHandle (which itself must be constructed inside an
    # if guard — checked separately).
    if "saveTurn(" in content:
        # Find the saveTurn call site and look upward for an if (authUid).
        # Heuristic: between the previous `if (authUid)` and the saveTurn
        # call there must be no closing brace at depth 0.
        m = re.search(r"saveTurn\s*\(", content)
        if m:
            before = content[: m.start()]
            # Look for the last occurrence of `if (authUid)` before the call.
            guard = re.search(r"if\s*\(\s*authUid\s*\)\s*\{", before)
            if not guard:
                issues.append({
                    "check": "persistence_guarded_on_authuid",
                    "reason": (
                        "saveTurn() is called without an `if (authUid)` "
                        "guard. Anon voice-journal callers will hit a 401 "
                        "RLS error on agent_memory insert and the gateway "
                        "will 502 — re-triggering the offline fallback."
                    ),
                })
    if "persistJournalEntry(" in content:
        m = re.search(r"persistJournalEntry\s*\(", content)
        if m:
            before = content[: m.start()]
            guard = re.search(r"if\s*\(\s*authUid\s*\)\s*\{", before)
            if not guard:
                issues.append({
                    "check": "persistence_guarded_on_authuid",
                    "reason": (
                        "persistJournalEntry() is called without an "
                        "`if (authUid)` guard. voice_journal_entries is "
                        "RLS-keyed on auth_uid; anon inserts will 401 and "
                        "the gateway will 502."
                    ),
                })
    return issues


def check_voice_journal_in_routes(content: str) -> list[dict]:
    """L4 — voice-journal must actually be a registered agent.

    AGENT_ROUTES is a large object with multi-line entries; the simple
    `[^}]*` shortcut bails out on the first inner `}`. Walk the brace
    structure properly: find AGENT_ROUTES, find the matching close, then
    look for the 'voice-journal' key inside that body.
    """
    if not content:
        return []
    m = re.search(r"\bAGENT_ROUTES\b[^=]{0,200}=\s*\{", content)
    if not m:
        return [{
            "check": "voice_journal_in_routes",
            "reason": "AGENT_ROUTES declaration not found in ai-gateway/index.ts",
        }]
    start = m.end()
    depth = 1
    i = start
    while i < len(content) and depth > 0:
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    body = content[start:i - 1]
    if not re.search(r"['\"]voice-journal['\"]\s*:", body):
        return [{
            "check": "voice_journal_in_routes",
            "reason": (
                "voice-journal is missing from AGENT_ROUTES. The anon "
                "allowlist is meaningless if the agent isn't routable. "
                "Add { 'voice-journal': { fn: 'voice-journal-agent', ... } }."
            ),
        }]
    return []


CHECK_NAMES = [
    "anon_ok_set_declared",
    "auth_gate_references_set",
    "persistence_guarded_on_authuid",
    "voice_journal_in_routes",
]

CHECK_LABELS = {
    "anon_ok_set_declared":
        "L1  ai-gateway declares ANON_OK_AGENTS containing 'voice-journal'",
    "auth_gate_references_set":
        "L2  Auth-required guard excludes ANON_OK_AGENTS members from 401",
    "persistence_guarded_on_authuid":
        "L3  saveTurn / persistJournalEntry guarded on authUid (anon-safe)",
    "voice_journal_in_routes":
        "L4  voice-journal registered in AGENT_ROUTES",
}


def main() -> int:
    print("\033[1m\nai-gateway Anon Voice-Journal Contract Validator (4-layer)\033[0m")
    print("=" * 60)
    content = _read(GATEWAY_PATH)
    print(f"  Scanning {GATEWAY_PATH.relative_to(ROOT).as_posix()}")

    issues: list[dict] = []
    issues += check_anon_ok_set_declared(content)
    issues += check_auth_gate_references_set(content)
    issues += check_persistence_guarded_on_authuid(content)
    issues += check_voice_journal_in_routes(content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
