#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D25
r"""
validate_setcontext_pii_safe.py — regression guard: a floating-companion context
marked `piiSafe: true` (which IS transmitted to the LLM as page_context) must NOT
interpolate a person-NAME field into its summary.

WHY (K4, 2026-07-12): companion-launcher only forwards `context.page_context` to the
ai-gateway when the page called `WHAssistant.setContext({... piiSafe: true ...})`.
The gateway's context redaction (redactPIIWithMap) scrubs email/phone but does NOT
catch a NAME sitting in free prose — so `owner: ${_detail.owner_name}` in a piiSafe
summary would ship a person's name to the model provider. project-manager /
project-report shipped exactly that shape (the flag was omitted, so the whole summary
was dropped — grounding dead); fixing K4 set piiSafe:true AND stripped owner_name. This
gate locks the invariant forward-only: a piiSafe summary interpolating a *_name person
field FAILs, so a later edit can't silently re-introduce the leak.

WHAT THIS CHECKS (static, deterministic, $0):
  For every root *.html, find each `piiSafe: true` occurrence, take the ~30-line
  lookback window (where the summary that setContext transmits is built), and FAIL on
  a NON-COMMENT line that interpolates a banned person-name field inside a template
  literal: `${ ... owner_name|display_name|worker_name|author_name|full_name|
  first_name|last_name ... }`. Equipment names / codes / counts are fine (that's the
  whole point — ground on the SHAPE, not the person).

Exit 0 = PASS, 1 = FAIL. No file is ever edited.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRN, RED, RST = "\033[92m", "\033[91m", "\033[0m"

LOOKBACK = 30
# A person-name field interpolated into a transmitted string = a leak. `name` alone is
# NOT banned (asset/project NAMES are legitimate business data, like the piiSafe pages
# already ship); only person-scoped *_name fields.
BANNED_FIELDS = r"(?:owner_name|display_name|worker_name|author_name|full_name|first_name|last_name|assignee_name|contact_name)"
INTERP_RE = re.compile(r"\$\{[^}]*" + BANNED_FIELDS + r"[^}]*\}")
PIISAFE_RE = re.compile(r"piiSafe\s*:\s*true")


def _is_comment(line: str) -> bool:
    s = line.strip()
    return s.startswith("//") or s.startswith("*") or s.startswith("/*") or s.startswith("<!--")


def main() -> int:
    fails: list[str] = []
    scanned = piisafe_sites = 0
    for html in sorted(ROOT.glob("*.html")):
        scanned += 1
        lines = html.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines):
            if not PIISAFE_RE.search(line):
                continue
            piisafe_sites += 1
            lo = max(0, i - LOOKBACK)
            for j in range(lo, i + 1):
                if _is_comment(lines[j]):
                    continue
                m = INTERP_RE.search(lines[j])
                if m:
                    fails.append(f"{html.name}:{j+1} a piiSafe:true setContext summary interpolates a "
                                 f"person-name field → leaks a name to the LLM: {m.group(0)[:80]}")

    if fails:
        for f in fails:
            print(f"{RED}FAIL{RST} {f}")
        print(f"\n{RED}validate_setcontext_pii_safe: {len(fails)} name-in-piiSafe-summary leak(s){RST}")
        return 1
    print(f"{GRN}PASS{RST} no piiSafe:true companion context interpolates a person-name field "
          f"({piisafe_sites} piiSafe site(s) across {scanned} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
