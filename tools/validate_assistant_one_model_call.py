#!/usr/bin/env python3
"""validate_assistant_one_model_call.py - the Work Assistant answers with ONE model call (UFAI §LM.11, 2026-10-09).

ai-orchestrator used to spend a router call, a call per specialist (2-4 of seven) and a synthesis call - about five
calls and 11.7K tokens a question - and every specialist call only restated data the function had already read.
The specialists now compute their JSON and the router reads the question's words; the synthesis (chat) or the coach
synthesis is the one call left. Measured live after the change: 1 generation call, 1,335 tokens.

This gate keeps it that way, from the source:
  * exactly two model-call sites remain in the file - callGroq(synthPrompt, SYNTH_SYSTEM) and
    callGroq(synthPrompt, COACH_SYNTH_SYSTEM) - and no direct callAI( call besides callGroq's own body;
  * routing goes through routeQuestion(question), never a model;
  * the synthesis input is redacted (redactPIIWithMap + redactKnownNames) and the answer re-filled (_fill).
--selftest plants a specialist model call and a model router and requires both to be caught.
"""
from __future__ import annotations
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'supabase', 'functions', 'ai-orchestrator', 'index.ts')


def _code(src: str) -> str:
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(l.split('//')[0] if not l.lstrip().startswith('`') else l for l in src.splitlines())


def check(src: str) -> list[str]:
    code = _code(src)
    fails = []
    calls = re.findall(r'callGroq\(\s*([A-Za-z_][\w]*)\s*,\s*([A-Z_]+_SYSTEM)\s*\)', code)
    sites = [m for m in re.finditer(r'(?<![\w.])callGroq\(', code)]
    defs = [m for m in re.finditer(r'function\s+callGroq\(', code)]
    n_calls = len(sites) - len(defs)
    allowed = {('synthPrompt', 'SYNTH_SYSTEM'), ('synthPrompt', 'COACH_SYNTH_SYSTEM')}
    if n_calls != 2:
        fails.append(f'{n_calls} callGroq() call sites - the one-call assistant has exactly 2 (chat synthesis, coach synthesis)')
    for prompt, system in calls:
        if (prompt, system) not in allowed:
            fails.append(f'callGroq({prompt}, {system}) - a model call outside the synthesis (a specialist or router asking a model again)')
    direct = [m for m in re.finditer(r'(?<![\w.])callAI\(', code)]
    if len(direct) != 1:
        fails.append(f'{len(direct)} callAI() sites - only callGroq\'s own body may call the chain')
    if not re.search(r'agentsToRun\s*=\s*routeQuestion\(\s*question\s*\)', code):
        fails.append('routing does not go through routeQuestion(question)')
    if not (re.search(r'redactPIIWithMap\(', code) and re.search(r'redactKnownNames\(', code) and re.search(r'answer\s*=\s*_fill\(answer\)', code)):
        fails.append('the synthesis input is not redacted (redactPIIWithMap + redactKnownNames) and re-filled (_fill)')
    return fails


def selftest() -> int:
    src = io.open(SRC, encoding='utf-8').read()
    planted_agent = src.replace('return { agent: "predictive", result: { predictions } };',
                                'const _x = await callGroq(summary, PREDICTIVE_SYSTEM);\n  return { agent: "predictive", result: { predictions } };', 1)
    planted_router = src.replace('agentsToRun = routeQuestion(question);',
                                 'agentsToRun = JSON.parse(await callGroq(`Question: "${question}"`, ROUTE_SYSTEM)).agents;', 1)
    ok = bool(check(planted_agent)) and bool(check(planted_router)) and not check(src)
    print('selftest:', 'PASS (a planted specialist call and a planted model router are both caught; the real source passes)' if ok else 'FAIL')
    return 0 if ok else 1


def main() -> int:
    if '--selftest' in sys.argv:
        return selftest()
    if not os.path.exists(SRC):
        print('SKIP ai-orchestrator source not found'); return 0
    fails = check(io.open(SRC, encoding='utf-8').read())
    if fails:
        print('FAIL assistant-one-model-call')
        for f in fails:
            print('  ' + f)
        return 1
    print('PASS assistant-one-model-call - 2 model-call sites (chat + coach synthesis), routing by routeQuestion, '
          'synthesis input redacted and the answer re-filled')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
