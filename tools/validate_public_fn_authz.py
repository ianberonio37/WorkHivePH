#!/usr/bin/env python3
# DEEPWALK-CELL: * D9
"""
validate_public_fn_authz.py - Arc R (Z-lens, OWASP A01): every verify_jwt=false edge fn that
calls an LLM must enforce its OWN guard (auth OR rate-limit).
====================================================================================================
60 of 61 edge fns run `verify_jwt = false` (platform gateway does NOT enforce a JWT). That is fine
for fns that re-validate the caller themselves — but `voice-model-call` ran verify_jwt=false with
NO auth, NO rate-limit and NO caps: a live, anonymous OPEN LLM PROXY over the platform's provider
keys (quota theft + companion DoS). The existing `validate_ai_rate_limit_coverage` MISSED it because
it only flags fns a frontend `functions.invoke`s — "no frontend caller" was treated as "gateway-
fronted, rate-limited upstream." A deployed verify_jwt=false endpoint is reachable by anyone
regardless of whether the frontend calls it.

This gate closes that blind spot structurally: for every verify_jwt=false fn whose source calls an
LLM (callAI/callGroq/callAIMultimodal or a raw provider chat-completions fetch), require at least one
GUARD marker — an auth check (resolveIdentity/resolveTenancy/requireServiceRole/getUser/
checkSupervisor) OR a rate-limit (checkSoloRateLimit/checkAIRateLimit/_RATE_CAP). Public-by-design
self-authenticating fns (login, the signature-verified webhooks) are exempt by evidence.

Self-test (--self-test): a verify_jwt=false LLM fn with no guard FAILs; one with checkSoloRateLimit
PASSes; a non-LLM fn is ignored.

Exit 0 = every public LLM fn is guarded. Exit 1 = an unguarded open LLM proxy (or self-test fail).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
CONFIG = ROOT / "supabase" / "config.toml"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_public_fn_authz"]

# Self-authenticating / public-by-design (verify their own signature or are the auth entrypoint).
EXEMPT = {"login", "cmms-webhook-receiver"}

LLM_MARKERS = re.compile(
    r"callAIMultimodal|callAI\b|callGroq|chat/completions|api\.groq\.com|api\.openai|"
    r"api\.cerebras|api\.voyage|api\.jina|_callModel|callModel\(",
)
GUARD_MARKERS = re.compile(
    r"resolveIdentity|resolveTenancy|requireServiceRole|checkSupervisor|\.auth\.getUser|"
    r"checkSoloRateLimit|checkAIRateLimit|_RATE_CAP|_WA_RATE_CAP|rateLimit|isServiceRole|verifySignature",
)


def verify_jwt_false_fns() -> list[str]:
    if not CONFIG.exists():
        return []
    out, current = [], None
    for line in CONFIG.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\[functions\.([A-Za-z0-9_-]+)\]", line.strip())
        if m:
            current = m.group(1)
        elif current and re.search(r"verify_jwt\s*=\s*false", line):
            out.append(current)
            current = None
        elif current and re.search(r"verify_jwt\s*=\s*true", line):
            current = None
    return out


def classify(src: str) -> tuple[bool, bool]:
    return (bool(LLM_MARKERS.search(src)), bool(GUARD_MARKERS.search(src)))


def self_test() -> bool:
    ok = True
    unguarded = "const r = await fetch(api_url, { body: JSON.stringify({ messages }) });"  # llm, no guard
    is_llm, has_guard = classify(unguarded + " chat/completions")
    if not (is_llm and not has_guard):
        print(f"{R}self-test FAIL: did not flag unguarded LLM fn.{X}"); ok = False
    guarded = "await checkSoloRateLimit(db, key); callGroq(prompt, sys);"
    is_llm2, has_guard2 = classify(guarded)
    if not (is_llm2 and has_guard2):
        print(f"{R}self-test FAIL: did not see the rate-limit guard.{X}"); ok = False
    nonllm = "const x = await db.from('t').select('*');"
    if classify(nonllm)[0]:
        print(f"{R}self-test FAIL: flagged a non-LLM fn.{X}"); ok = False
    print((G + "self-test PASS - public-fn authZ detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    fns = verify_jwt_false_fns()
    unguarded, guarded, exempt = [], [], []
    for fn in fns:
        p = FUNCS / fn / "index.ts"
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        is_llm, has_guard = classify(src)
        if not is_llm:
            continue
        if fn in EXEMPT:
            exempt.append(fn); continue
        (guarded if has_guard else unguarded).append(fn)

    print(f"{B}Public-fn authZ gate (Arc R / Z-lens, OWASP A01){X}")
    print(f"  verify_jwt=false fns: {len(fns)}  ·  LLM fns guarded: {len(guarded)}  ·  exempt: {len(exempt)}")
    for fn in unguarded:
        print(f"  {R}FAIL{X} {fn}: verify_jwt=false + calls an LLM + NO auth/rate-limit guard (open proxy)")
    if unguarded:
        print(f"{R}FAIL: {len(unguarded)} unguarded public LLM fn(s).{X}")
        return 1
    print(f"{G}PASS - every verify_jwt=false LLM fn enforces an auth or rate-limit guard.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
