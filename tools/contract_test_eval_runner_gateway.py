#!/usr/bin/env python3
"""contract_test_eval_runner_gateway.py — C4 contract test for the ai→ai / ai-eval-runner→ai-gateway seam.

WHY THIS SEAM (2026-10-27): the nightly AI eval stopped grading a stub and asks the REAL gateway as an eval account, so
the seam miner grew the ai→ai count by one. Rather than accept a higher uncovered floor, this pins the wire.

THE CONTRACT (both directions):
  caller SENDS   POST {SUPABASE_URL}/functions/v1/ai-gateway
                 headers: Authorization: Bearer <the eval ACCOUNT's own session token> (never the service key - the
                 gateway must verify it like any person's), apikey, Content-Type: application/json
                 body: { agent, message, context, hive_id } - the four fields the gateway destructures
                 bounded: an AbortSignal timeout, so a hung specialist cannot take the heartbeat down
  caller READS   the shared envelope { ok, data: { answer } } (top-level `answer` only as the pre-envelope fallback),
                 and a non-2xx or an empty answer as an INFRA reason - recorded, never graded
  callee ACCEPTS a JSON body and destructures exactly { agent, message, context, hive_id }

USAGE:      python tools/contract_test_eval_runner_gateway.py
Self-test:  python tools/contract_test_eval_runner_gateway.py --selftest
Exit 0 = contract holds; 1 = the seam drifted.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
G = "\033[92m"; R = "\033[91m"; X = "\033[0m"

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "supabase" / "functions" / "ai-eval-runner" / "index.ts"
GATEWAY = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"


def check(runner: str, gateway: str) -> list[str]:
    problems: list[str] = []
    i = runner.find("/functions/v1/ai-gateway")
    if i < 0:
        return ["ai-eval-runner no longer calls /functions/v1/ai-gateway - the seam this pins is gone (update "
                "ai_seam_contracts.json if that is deliberate)"]
    call = runner[i:i + 1600]
    if not re.search(r"Authorization[\"']?\s*:\s*`Bearer \$\{evalSession\.token\}`", call):
        problems.append("the runner no longer sends the eval ACCOUNT's session as the Bearer - with the service key the "
                        "gateway would skip the membership proof it applies to every person")
    if "apikey" not in call:
        problems.append("the runner dropped the apikey header")
    if "AbortSignal.timeout(" not in call:
        problems.append("the runner's gateway call has no timeout - a hung specialist would hold the heartbeat")
    for field in ("agent:", "message:", "context:", "hive_id:"):
        if field not in call:
            problems.append(f"the runner's body no longer sends {field.rstrip(':')}")
    rr = re.search(r"async function readGatewayReply\b(.{0,1400})", runner, re.S)
    if not rr:
        problems.append("readGatewayReply is gone - the runner would read the reply ad hoc")
    else:
        body = rr.group(1)
        if "j?.data?.answer" not in body:
            problems.append("readGatewayReply no longer reads the shared envelope's data.answer - an authorised call "
                            "would record an empty answer (the 2026-10-07 defect)")
        if "!res.ok" not in body or "infraReason" not in body:
            problems.append("a non-2xx gateway reply is no longer recorded as an infra reason")
    # one line, defaults allowed (`context = {}` holds a brace of its own)
    if not re.search(r"const\s*\{\s*agent\s*,\s*message\s*,\s*context\b[^\n]*?\bhive_id\b[^\n]*\}\s*=\s*body\s*;", gateway):
        problems.append("ai-gateway no longer destructures { agent, message, context, hive_id } from its body - the "
                        "runner's request shape is no longer the one the gateway reads")
    return problems


def main() -> int:
    runner = RUNNER.read_text(encoding="utf-8", errors="replace")
    gateway = GATEWAY.read_text(encoding="utf-8", errors="replace")
    problems = check(runner, gateway)
    if problems:
        print(f"{R}FAIL{X} ai-eval-runner -> ai-gateway seam drifted:")
        for p in problems:
            print("    " + p)
        return 1
    print(f"{G}PASS{X} ai-eval-runner -> ai-gateway seam - the eval account's own Bearer + apikey, a bounded call, "
          "{ agent, message, context, hive_id } as the gateway reads it, and the envelope's data.answer read back.")
    return 0


def selftest() -> int:
    runner = RUNNER.read_text(encoding="utf-8", errors="replace")
    gateway = GATEWAY.read_text(encoding="utf-8", errors="replace")
    fails = []
    if check(runner, gateway):
        fails.append("healthy tree should PASS")
    if not check(runner.replace("${evalSession.token}", "${SERVICE_KEY}"), gateway):
        fails.append("a service-key Bearer must FAIL")
    if not check(runner.replace("j?.data?.answer", "j?.answer"), gateway):
        fails.append("reading only the pre-envelope answer must FAIL")
    if not check(runner, gateway.replace("const { agent, message, context = {}, hive_id = null } = body;",
                                         "const { agent, prompt } = body;")):
        fails.append("a gateway that stops reading the runner's fields must FAIL")
    if fails:
        print(f"{R}SELF-TEST FAIL{X}: " + "; ".join(fails)); return 1
    print(f"{G}PASS{X} contract_test_eval_runner_gateway self-test (service-key Bearer / pre-envelope read / "
          "a re-shaped gateway body all redden)")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
