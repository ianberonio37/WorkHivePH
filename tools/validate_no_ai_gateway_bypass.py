#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D26
# DEEPWALK-CELL: * CP
r"""
validate_no_ai_gateway_bypass.py — regression guard: NO browser page may POST a
chat/completions payload to an EXTERNAL model endpoint, bypassing the canonical
ai-gateway (tenancy + PII redaction + rate-limit + memory). Ext-1 "gateway-route
EVERY AI call".

WHY (K1, live-caught 2026-07-12): assistant.html's Step-2 fallback POSTed the full
system prompt + entire chat history + semantic KB context to a PUBLIC Cloudflare
Worker (workhive-assistant.ian-beronio37.workers.dev) with NO auth, NO PII
redaction, NO rate-limit, NO memory — a raw bypass of the one front door, triggered
whenever the slow Step-1 orchestrator path timed out. Fixed by routing the fallback
through ai-gateway's 'voice-journal' agent. This gate stops the whole class from
recurring: a page must reach models ONLY through ai-gateway (or an internal
/functions/v1/<specialist> that itself sits behind the gateway/service auth) —
never a direct fetch to a public model host.

WHAT THIS CHECKS (static, deterministic, $0, no deno/DB/model):
  For every root *.html, flag a NON-COMMENT line that fetches/XHRs a BANNED
  external model endpoint:
    - *.workers.dev                (a personal Cloudflare Worker model proxy)
    - api.groq.com / api.openai.com / api.anthropic.com / openrouter.ai
    - generativelanguage.googleapis.com / api.mistral.ai / api.cerebras.ai
    - any URL path containing "/chat/completions" or "/v1/messages"
  A hit = FAIL (the page is calling a model provider from the browser, leaking the
  key and every guardrail). The legitimate path is db.functions.invoke('ai-gateway')
  or a fetch to the LOCAL 127.0.0.1:54321 / <project>.supabase.co /functions/v1/*.

Exit 0 = PASS, 1 = FAIL. No file is ever edited.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GRN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

# Banned external model endpoints (host or path fragments). A browser page reaching
# any of these is calling a model provider directly = a gateway bypass.
BANNED = [
    r"[a-z0-9-]+\.workers\.dev",
    r"api\.groq\.com",
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"openrouter\.ai",
    r"generativelanguage\.googleapis\.com",
    r"api\.mistral\.ai",
    r"api\.cerebras\.ai",
    r"/chat/completions",
    r"/v1/messages",
]
BANNED_RE = re.compile("|".join(BANNED), re.IGNORECASE)

# A line is code (not a comment) if it isn't a JS // line-comment, a /* */ block, or
# an HTML comment. We only flag lines that also look like a network call.
NETCALL_RE = re.compile(r"\bfetch\s*\(|fetchWithTimeout\s*\(|XMLHttpRequest|\.open\s*\(\s*['\"]POST", re.IGNORECASE)


def _is_comment(line: str) -> bool:
    s = line.strip()
    return s.startswith("//") or s.startswith("*") or s.startswith("/*") or s.startswith("<!--")


def main() -> int:
    fails: list[str] = []
    scanned = 0
    for html in sorted(ROOT.glob("*.html")):
        scanned += 1
        for i, line in enumerate(html.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if _is_comment(line):
                continue
            if not BANNED_RE.search(line):
                continue
            # Only a FAIL if the banned endpoint appears on a line that is a network call
            # OR is a bare URL literal assigned to a const used as a fetch target. To keep
            # it precise + teeth-proven, require the network-call shape on the same line.
            if NETCALL_RE.search(line):
                hit = BANNED_RE.search(line).group(0)
                fails.append(f"{html.name}:{i} browser network call to BANNED model endpoint "
                             f"`{hit}` — route AI through ai-gateway instead: {line.strip()[:110]}")

    if fails:
        for f in fails:
            print(f"{RED}FAIL{RST} {f}")
        print(f"\n{RED}validate_no_ai_gateway_bypass: {len(fails)} bypass(es) across {scanned} pages{RST}")
        return 1
    print(f"{GRN}PASS{RST} no browser page bypasses ai-gateway with a direct external-model call "
          f"({scanned} pages scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
