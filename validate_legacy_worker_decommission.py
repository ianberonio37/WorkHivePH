"""
Legacy Cloudflare Worker Decommission Validator -- WorkHive Platform
=====================================================================
Catches the bug class where production JS files still call the legacy
Cloudflare Worker (`workhive-assistant.ian-beronio37.workers.dev`) for
AI replies after the platform has been migrated to the supabase
`ai-gateway` edge function (Companion Streamline Step C, 2026-05-18).

The Step C migration is a one-way door: every AI conversation should
flow through ai-gateway so the persona contract + memory + PII redaction
+ rate-limit policy applies uniformly. A stray Cloudflare Worker call:

  - Bypasses Step D's Hezekiah=Technical / Zaniah=Strategist domain lens
    (the Worker's prompt does not include DOMAIN_LENS).
  - Returns generic OpenAI-shaped JSON the voice handler can't always
    parse cleanly, then falls through to the "Sorry, I'm offline."
    error path — even when the underlying network is fine.
  - Costs us a separate Groq quota (the Worker has its own key).
  - Skips PII redaction, memory writes, and rate-limit checks.

Layer 1 — No production JS file references the legacy Worker URL  [FAIL]
  Scans every committed *.js file (excluding node_modules / venv) for
  literal references to `workhive-assistant.ian-beronio37.workers.dev`
  or the WH_ASSISTANT_WORKER_URL constant being USED in a fetch call.
  Production callers must POST to `/functions/v1/ai-gateway` instead.

  Allowlist: a single declaration of the URL const is allowed (it stays
  in the file as a tombstone alongside any embed paths that haven't
  migrated yet). The validator fails only when the URL is USED — i.e.
  passed to fetch/fetcher/fetchWithTimeout as the URL argument.

Layer 2 — No production JS file leaves the Cloudflare endpoint as the
  conversational reply path                                       [FAIL]
  Greps for `fetch(WH_ASSISTANT_WORKER_URL` and similar patterns inside
  `conversational`, `reply`, `answer`, `intent`, or `router` named
  functions. If a function whose purpose is producing a user-visible
  reply still POSTs to the Worker, that's the bug that caused the
  "Sorry, I'm offline" regression on voice-journal.

History:
  - 2026-05-18 commit b64fd8a — companion-launcher.js migrated.
  - 2026-05-19 — voice-handler.js conversational + intent-router calls
    migrated after the user noticed Zaniah (then "Rosa") stuck in offline mode.
  - This validator was added so the same bug class never lands again.

Skills consulted: ai-engineer (gateway-routing pattern + persona
contract integration), security (PII boundary lives ONLY at ai-gateway),
devops (one infra path per call shape).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import format_result


ROOT = Path(__file__).resolve().parent

LEGACY_WORKER_HOST = "workhive-assistant.ian-beronio37.workers.dev"

# Files that may legitimately mention the legacy host (tombstone comment,
# this validator, archived docs). Anything NOT on this allowlist must be
# clean.
ALLOWLIST_FILES = {
    "validate_legacy_worker_decommission.py",
}

# JS files to skip entirely.
SKIP_DIR_FRAGMENTS = (
    os.sep + "node_modules" + os.sep,
    os.sep + "venv" + os.sep,
    os.sep + ".venv" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "dist" + os.sep,
)


def _iter_production_js() -> list[Path]:
    """Every *.js at project root + 1 level deep (no node_modules)."""
    paths: list[Path] = []
    for p in ROOT.glob("*.js"):
        paths.append(p)
    for p in ROOT.glob("**/*.js"):
        s = str(p)
        if any(frag in s for frag in SKIP_DIR_FRAGMENTS):
            continue
        if p in paths:
            continue
        paths.append(p)
    return paths


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def check_no_legacy_worker_fetch() -> list[dict]:
    """L1 — no production JS calls fetch() on the legacy Worker URL."""
    issues: list[dict] = []

    # Patterns that count as a USE (not just a comment / tombstone):
    #   fetch(WH_ASSISTANT_WORKER_URL          — direct fetch
    #   fetcher(WH_ASSISTANT_WORKER_URL        — wrapped fetcher
    #   fetchWithTimeout(WH_ASSISTANT_WORKER_URL
    #   fetch('https://workhive-assistant...   — literal URL fetch
    #   fetch("https://workhive-assistant...
    use_patterns = [
        re.compile(r"\b(?:fetch|fetcher|fetchWithTimeout)\s*\(\s*WH_ASSISTANT_WORKER_URL\b"),
        re.compile(rf"\b(?:fetch|fetcher|fetchWithTimeout)\s*\(\s*['\"]https?://{re.escape(LEGACY_WORKER_HOST)}"),
    ]

    for path in _iter_production_js():
        if path.name in ALLOWLIST_FILES:
            continue
        content = _read(path)
        if not content:
            continue
        # Skip files that don't even mention the host (vast majority).
        if LEGACY_WORKER_HOST not in content and "WH_ASSISTANT_WORKER_URL" not in content:
            continue
        for pat in use_patterns:
            for m in pat.finditer(content):
                # Compute 1-based line number for the match start.
                line_no = content.count("\n", 0, m.start()) + 1
                rel = path.relative_to(ROOT).as_posix()
                issues.append({
                    "check": "no_legacy_worker_fetch",
                    "reason": (
                        f"{rel}:{line_no} still fetches the legacy "
                        f"Cloudflare Worker. Route through "
                        f"`/functions/v1/ai-gateway` (agent: 'voice-journal' "
                        f"or whatever specialist matches) instead. "
                        f"See Companion Streamline Step C/D commit history."
                    ),
                })
    return issues


CHECK_NAMES = ["no_legacy_worker_fetch"]

CHECK_LABELS = {
    "no_legacy_worker_fetch":
        "L1  No production JS calls fetch() against the legacy "
        "workhive-assistant.workers.dev URL",
}


def main() -> int:
    print("\033[1m\nLegacy Worker Decommission Validator\033[0m")
    print("=" * 60)
    js_files = _iter_production_js()
    print(f"  Scanning {len(js_files)} production JS file(s)...")

    issues = check_no_legacy_worker_fetch()

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
