#!/usr/bin/env python3
"""validate_ai_prompt_injection.py — Arc H H8/I: AI fns must keep untrusted input OUT of the system prompt.

OWASP LLM01 Prompt Injection — the primary STRUCTURAL defense is role separation: trusted instructions go in
the `system` message, untrusted user content goes in the `user` message; never concatenate raw user input
INTO the system prompt (privilege confusion → the user can rewrite the instructions). The shared `callAI(prompt,
{systemPrompt})` enforces this by construction: `messages = [{role:system, content:systemPrompt}, {role:user,
content:prompt}]`. This gate locks that posture: no AI edge fn may build a `systemPrompt` (or a `role:"system"`
content) by interpolating a known untrusted request field (message/query/question/transcript/input/body.*).

This is the deterministic LLM01 control. The probabilistic residual (a weak model IGNORING the system
instruction under a jailbreak) is the named ceiling — covered by the live fabrication/adversarial sweep
(Family E), not by this static gate. Baseline 0.

USAGE:      python tools/validate_ai_prompt_injection.py
Self-test:  python tools/validate_ai_prompt_injection.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

LLM_MARKERS = re.compile(r"callAI|callGroq|ai-chain|generateContent|chat/completions|role:\s*['\"]system['\"]", re.I)
# untrusted request fields that must NOT be interpolated into a system prompt
UNTRUSTED = r"(?:message|query|question|transcript|user_input|userInput|prompt_text|body\.\w+|req\.\w+)"
# a system-prompt template literal that interpolates an untrusted field INSIDE its own backticks.
# Bounded to the backtick literal (`[^`]*` can't cross the closing backtick) so a separate user-prompt
# on the same line is NOT falsely flagged — only `${untrusted}` WITHIN the system string matches.
SYS_INTERP = re.compile(
    rf"(?:systemPrompt\s*[:=]\s*`[^`]*|role:\s*['\"]system['\"][^`\n]*content\s*:\s*`[^`]*)\$\{{[^}}]*{UNTRUSTED}",
    re.I,
)


def scan():
    findings, ok = [], []
    for d in sorted(FUNCS.iterdir()):
        if not d.is_dir() or d.name == "_shared":
            continue
        idx = d / "index.ts"
        if not idx.exists():
            continue
        body = idx.read_text(encoding="utf-8", errors="replace")
        nc = re.sub(r"//.*", "", body)
        if not LLM_MARKERS.search(nc):
            continue
        hits = [m.group(0)[:90] for m in SYS_INTERP.finditer(nc)]
        if hits:
            findings.append((d.name, hits))
        else:
            ok.append(d.name)
    return findings, ok


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    findings, ok = scan()

    print("=" * 74)
    print("  Arc H H8/I — AI prompt-injection posture (untrusted input out of the system prompt; LLM01)")
    print("=" * 74)
    print(f"  AI fns with role-separated prompts (no user-input-in-system): {len(ok)} · findings: {len(findings)}")

    if self_test:
        synth = "const systemPrompt = `You are a bot. ${body.message}`;"
        ok_t = bool(SYS_INTERP.search(synth))
        safe = "const systemPrompt = `You are a bot.`; const prompt = `${body.message}`;"
        ok_s = not SYS_INTERP.search(safe)
        passed = ok_t and ok_s
        print(f"  TEETH [{GREEN+'PASS'+RST if passed else RED+'FAIL'+RST}] catches user-input-in-system, ignores user-input-in-user-prompt")
        if not passed:
            return 1

    print()
    if findings:
        for n, hits in findings:
            print(f"  {RED}FAIL{RST}  {n} interpolates untrusted input INTO the system prompt (LLM01): {hits[0]}…")
        print(f"\n  {RED}{len(findings)} AI fn(s) mixing untrusted input into the system prompt{RST} (baseline 0)")
        return 1
    print(f"  {GREEN}PASS{RST} — every AI fn keeps untrusted input in the user message (callAI role separation); system prompt is trusted-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
