#!/usr/bin/env python3
"""validate_debug_echo_prod_safe.py — static guard for the W3 debug-echo wire.

The ai-gateway has a LOCAL-ONLY `debug_echo_memory_block` short-circuit (W3 of the
companion wiring roadmap): when enabled it returns the assembled memory_block +
which layer sections fired, WITHOUT an LLM call, so the wiring battery can assert
J1/K3/K5/K8 deterministically. That echo must be IMPOSSIBLE to trigger in prod.

This validator reads supabase/functions/ai-gateway/index.ts and asserts, statically:
  1. The enable flag (DEBUG_ECHO_ENABLED) is NOT unconditionally true — it depends on
     a local-URL check and/or an explicit env var (fail-closed).
  2. The local-URL regex does NOT match a real prod URL (https://<proj>.supabase.co)
     but DOES match the local docker host (http://kong:8000) — replicated in Python.
  3. The echo's return branch is triple-gated: DEBUG_ECHO_ENABLED && authUid &&
     context.debug_echo_memory_block === true.
  4. There is exactly ONE `debug_echo:` emission and it lives inside that guard.

Exit 0 = prod-safe; exit 1 = a leak path exists. Forward-only teeth; run standalone
or fold into the companion gate. (companion wiring W3, 2026-06-12)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"
AI_CHAIN = ROOT / "supabase" / "functions" / "_shared" / "ai-chain.ts"

# The local-detection regex the gateway uses (keep in sync with index.ts).
LOCAL_URL_RE = re.compile(r"//(kong|localhost|127\.0\.0\.1)(:|/|$)")


def fail(msg: str) -> None:
    print(f"  \033[91mx\033[0m {msg}")


def ok(msg: str) -> None:
    print(f"  \033[92mok\033[0m {msg}")


def main() -> int:
    if not GATEWAY.exists():
        print(f"FAIL: {GATEWAY} not found")
        return 1
    src = GATEWAY.read_text(encoding="utf-8", errors="ignore")
    fails: list[str] = []

    # 1. DEBUG_ECHO_ENABLED defined and NOT unconditionally true.
    m = re.search(r"const\s+DEBUG_ECHO_ENABLED\s*=\s*([^;]+);", src)
    if not m:
        fails.append("DEBUG_ECHO_ENABLED is not defined — the echo gate is missing")
    else:
        expr = m.group(1).strip()
        if re.fullmatch(r"true|1|['\"]1['\"]", expr):
            fails.append(f"DEBUG_ECHO_ENABLED is unconditionally on: `{expr}`")
        elif "Deno.env.get" not in expr and "_IS_LOCAL_SUPABASE" not in expr and "SUPABASE_URL" not in expr:
            fails.append(f"DEBUG_ECHO_ENABLED does not gate on env/local URL: `{expr}`")
        else:
            ok(f"DEBUG_ECHO_ENABLED is conditionally gated: `{expr[:80]}`")

    # 2. The local regex must reject a prod URL and accept the local one.
    prod = "https://abcdefgh.supabase.co"
    local = "http://kong:8000"
    if LOCAL_URL_RE.search(prod):
        fails.append(f"local-detection regex MATCHES a prod URL ({prod}) — would enable echo in prod")
    else:
        ok("local-detection regex rejects a prod *.supabase.co URL")
    if not LOCAL_URL_RE.search(local):
        fails.append(f"local-detection regex does NOT match the local docker host ({local})")
    else:
        ok("local-detection regex accepts the local docker host")
    # Confirm the same regex literal is present in source (kept in sync).
    if "kong|localhost|127" not in src.replace("\\", ""):
        fails.append("the kong|localhost|127.0.0.1 local-detection literal is missing from the gateway")

    # 3 + 4. Exactly one `debug_echo:` emission, inside the triple gate.
    emissions = [mm.start() for mm in re.finditer(r"\bdebug_echo:\s*\{", src)]
    if len(emissions) != 1:
        fails.append(f"expected exactly 1 `debug_echo:` emission, found {len(emissions)}")
    else:
        # The guard must appear within ~600 chars before the emission.
        window = src[max(0, emissions[0] - 600):emissions[0]]
        needs = [
            ("DEBUG_ECHO_ENABLED", "the enable flag"),
            ("authUid", "auth gate"),
            ("debug_echo_memory_block", "the explicit opt-in flag"),
        ]
        missing = [label for tok, label in needs if tok not in window]
        if missing:
            fails.append(f"debug_echo emission is not triple-gated — missing: {', '.join(missing)}")
        else:
            ok("debug_echo emission is triple-gated (DEBUG_ECHO_ENABLED + authUid + debug_echo_memory_block)")

    # 5. W4 fault-injection (ai-chain.ts) must be local-gated too.
    if not AI_CHAIN.exists():
        fails.append(f"{AI_CHAIN} not found (W4 fault hook expected)")
    else:
        chain = AI_CHAIN.read_text(encoding="utf-8", errors="ignore")
        if "faultInject" in chain:
            # the simulated-skip branch must require _AI_CHAIN_LOCAL
            mfi = re.search(r"if\s*\(\s*faultInject\s*&&\s*_AI_CHAIN_LOCAL", chain)
            if not mfi:
                fails.append("ai-chain faultInject branch is not gated on _AI_CHAIN_LOCAL (could fire in prod)")
            elif "kong|localhost|127" not in chain.replace("\\", ""):
                fails.append("_AI_CHAIN_LOCAL local-detection literal missing from ai-chain.ts")
            else:
                ok("ai-chain faultInject is local-gated (_AI_CHAIN_LOCAL)")
        else:
            ok("ai-chain has no faultInject hook (nothing to guard)")
    # The gateway debug_fault_inject path must be DEBUG_ECHO_ENABLED-gated.
    if "debug_fault_inject" in src:
        mff = re.search(r"DEBUG_ECHO_ENABLED\s*&&\s*authUid[^\n]*\n[^\n]*debug_fault_inject", src)
        if not mff and "debug_fault_inject" in src:
            # looser: ensure DEBUG_ECHO_ENABLED appears within 400 chars before the read
            idx = src.index("debug_fault_inject")
            if "DEBUG_ECHO_ENABLED" not in src[max(0, idx - 400):idx]:
                fails.append("gateway debug_fault_inject is not DEBUG_ECHO_ENABLED-gated")
            else:
                ok("gateway debug_fault_inject is DEBUG_ECHO_ENABLED-gated")
        else:
            ok("gateway debug_fault_inject is DEBUG_ECHO_ENABLED-gated")

    print()
    if fails:
        print("\033[91m\033[1mDEBUG-ECHO PROD-SAFETY: FAIL\033[0m")
        for f in fails:
            fail(f)
        return 1
    print("\033[92m\033[1mDEBUG-ECHO PROD-SAFETY: PASS\033[0m — echo is local-only, triple-gated, prod-dead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
