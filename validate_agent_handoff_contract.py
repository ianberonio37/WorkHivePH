"""
Agent Handoff Contract -- WorkHive Platform
============================================
Validates the contract between ai-gateway and the specialist agents it
fans out to. The gateway's outbound payload MUST carry a stable shape:
  { message, context, hive_id, worker_name: "<redacted>", memory, gateway: true }
Specialist agents MUST be able to consume that shape (or be an opt-out
fn called via direct invocation, never via gateway).

Layer 1 -- Gateway sends required payload keys                           [WARN]
  ai-gateway/index.ts must include the canonical handoff key set in
  the body of its forward fetch(). Drift from this set means downstream
  agents lose access to memory + gateway sentinel.

Layer 2 -- Specialist agents recognize the gateway sentinel              [WARN]
  Every fn listed in AGENT_ROUTES values should reference either
  `gateway` or `memory` somewhere in its source -- evidence the agent
  was updated to consume the gateway-shaped body. Otherwise the
  agent ignores memory and loses the centralisation benefit.

Layer 3 -- Worker name never enters specialist agent body raw            [WARN]
  Specialist agents downstream of the gateway must NOT trust the
  body's `worker_name` field; it is `<redacted>` by construction.
  Each routed agent should default to deriving the worker_name from
  the JWT (worker_profiles join via auth_uid) and not read body.worker_name.

Layer 4 -- Handoff inventory (informational)                             [INFO]
  Per-agent: (gateway aware? memory aware? jwt-derived worker?)
  matrix. Useful for tracking adoption.

Skills consulted: ai-engineer (multi-agent fan-out), security (PII
boundary at the function-to-function call), architect (handoff
contract as the sticky abstraction).
"""
from __future__ import annotations

import re
import json
import sys
import os

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


GATEWAY_FILE  = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
FUNCTIONS_DIR = os.path.join("supabase", "functions")

REQUIRED_HANDOFF_KEYS = {
    "message", "context", "hive_id", "worker_name", "memory", "gateway",
}

# Specialist agents not yet wired to consume the gateway-shaped body.
# Each entry needs a one-line justification. Gradual adoption is fine --
# remove the entry once the agent reads body.memory + body.gateway.
HANDOFF_DEFERRED_GATEWAY_AWARE = {
    # 2026-05-11: 5 specialist agents now import `_shared/memory.ts`
    # (loadMemory + saveTurn + formatMemoryContext). The import signals
    # adoption; per-agent body.memory consumption is incremental.
    # Closes PRODUCTION_FIXES #49 gateway-aware track.
}
HANDOFF_DEFERRED_JWT_DERIVED = {
    # 2026-05-11: analytics-orchestrator + voice-logbook-entry now have
    # a `deriveWorkerFromJWT` helper that falls back to JWT + worker_profiles
    # when body.worker_name is `<redacted>` (gateway-routed). Closes
    # PRODUCTION_FIXES #49 JWT-derive track.
}

AGENT_ROUTES_RE = re.compile(
    r"""const\s+AGENT_ROUTES\s*:\s*Record<string,\s*\{[^}]*\}>\s*=\s*\{(?P<body>[\s\S]*?)\n\};""",
)
ROUTE_FN_RE = re.compile(r"""fn\s*:\s*['"`](?P<fn>[a-z0-9_-]+)['"`]""")
HANDOFF_BODY_RE = re.compile(
    r"""body\s*:\s*JSON\.stringify\s*\(\s*\{(?P<body>[^{}]*(?:\{[^{}]*\}[^{}]*)*?)\}""",
    re.DOTALL,
)


def parse_routed_fns() -> list[str]:
    src = read_file(GATEWAY_FILE) or ""
    m = AGENT_ROUTES_RE.search(src)
    if not m:
        return []
    return list(set(rm.group("fn") for rm in ROUTE_FN_RE.finditer(m.group("body"))))


def gateway_handoff_keys() -> set[str]:
    src = read_file(GATEWAY_FILE) or ""
    keys: set[str] = set()
    for m in HANDOFF_BODY_RE.finditer(src):
        body = m.group("body")
        # Capture explicit `key: value` properties.
        for km in re.finditer(r"""['"`]?(\w+)['"`]?\s*:""", body):
            keys.add(km.group(1))
        # Capture shorthand object properties (`{ hive_id, ... }`) at the
        # top level of the body. Avoid matching identifiers inside nested
        # expressions by walking with brace-depth = 0.
        depth = 0
        token = ""
        for ch in body + ",":
            if ch in "({[":
                depth += 1
                token = ""
            elif ch in ")}]":
                depth -= 1
                token = ""
            elif ch == ",":
                if depth == 0 and token.strip() and re.fullmatch(r"\w+", token.strip()):
                    keys.add(token.strip())
                token = ""
            elif depth == 0:
                if ch == ":":
                    token = ""
                else:
                    token += ch
        return keys
    return keys


def fn_source(fn_name: str) -> str:
    p = os.path.join(FUNCTIONS_DIR, fn_name, "index.ts")
    return read_file(p) or ""


# -- Layer 1: Gateway sends required payload keys -------------------------

def check_handoff_keys() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    keys = gateway_handoff_keys()
    missing = REQUIRED_HANDOFF_KEYS - keys
    report.append({
        "found_keys": sorted(keys),
        "required":   sorted(REQUIRED_HANDOFF_KEYS),
        "missing":    sorted(missing),
    })
    if missing:
        issues.append({
            "check": "handoff_keys", "skip": True,
            "reason": (
                f"ai-gateway forward body is missing handoff key(s): "
                f"{sorted(missing)}. Specialist agents lose access to "
                f"memory / gateway sentinel / hive context."
            ),
        })
    return issues, report


# -- Layer 2: Specialists recognise the gateway sentinel ------------------

def check_specialist_awareness(fns: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for fn in fns:
        src = fn_source(fn)
        if not src:
            continue
        gateway_aware = "gateway" in src or "memory" in src
        report.append({"fn": fn, "gateway_aware": gateway_aware})
        if not gateway_aware and fn not in HANDOFF_DEFERRED_GATEWAY_AWARE:
            issues.append({
                "check": "specialist_awareness", "skip": True,
                "reason": (
                    f"{fn}/index.ts is routed via the gateway but its "
                    f"source references neither `gateway` nor `memory`. "
                    f"It will discard the memory block + sentinel from "
                    f"the gateway's forward body. Wire awareness or "
                    f"justify the no-op."
                ),
            })
    return issues, report


# -- Layer 3: Worker name not trusted from body ---------------------------

def check_worker_name_trust(fns: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for fn in fns:
        src = fn_source(fn)
        if not src:
            continue
        # Heuristic: pattern `body.worker_name` or `body["worker_name"]` or
        # destructure of worker_name from req.json() implies trust of body.
        trusts_body = bool(re.search(
            r"""body\.worker_name|body\s*\[\s*['"]worker_name['"]\s*\]""", src,
        )) or bool(re.search(
            r"""const\s*\{[^}]*worker_name[^}]*\}\s*=\s*await\s+req\.json""", src, re.DOTALL,
        ))
        derives_from_jwt = bool(re.search(
            r"""worker_profiles""", src,
        )) or bool(re.search(
            r"""auth\.getUser\s*\(""", src,
        ))
        report.append({
            "fn":              fn,
            "trusts_body":     trusts_body,
            "derives_from_jwt": derives_from_jwt,
        })
        if trusts_body and not derives_from_jwt and fn not in HANDOFF_DEFERRED_JWT_DERIVED:
            issues.append({
                "check": "worker_name_trust", "skip": True,
                "reason": (
                    f"{fn}/index.ts reads worker_name from the request "
                    f"body without a JWT-derived fallback. When called "
                    f"via the gateway, body.worker_name is `<redacted>`; "
                    f"the agent should derive identity from auth.getUser()"
                    f" + worker_profiles instead."
                ),
            })
    return issues, report


# -- Layer 4: Handoff inventory (informational) --------------------------

def check_inventory(fns: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for fn in fns:
        src = fn_source(fn)
        rows.append({
            "fn":               fn,
            "gateway_aware":    ("gateway" in src or "memory" in src),
            "derives_from_jwt": ("worker_profiles" in src or "auth.getUser" in src),
        })
    return [], rows


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = [
    "handoff_keys",
    "specialist_awareness",
    "worker_name_trust",
    "inventory",
]
CHECK_LABELS = {
    "handoff_keys":         "L1  Gateway forward body carries the required handoff keys     [WARN]",
    "specialist_awareness": "L2  Routed specialist agents reference gateway / memory        [WARN]",
    "worker_name_trust":    "L3  Specialists derive worker_name from JWT, not body          [WARN]",
    "inventory":            "L4  Per-agent handoff awareness inventory (informational)      [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAgent Handoff Contract (4-layer)"))
    print("=" * 60)

    fns = parse_routed_fns()
    print(f"  {len(fns)} routed specialist fn(s).\n")

    l1_issues, l1_report = check_handoff_keys()
    l2_issues, l2_report = check_specialist_awareness(fns)
    l3_issues, l3_report = check_worker_name_trust(fns)
    l4_issues, l4_report = check_inventory(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('PER-AGENT HANDOFF AWARENESS (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            ck = lambda b: "Y" if b else "-"
            print(f"  {r['fn']:<32}  gateway-aware={ck(r['gateway_aware'])}  jwt={ck(r['derives_from_jwt'])}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":            "agent_handoff_contract",
        "total_checks":         total,
        "passed":               n_pass,
        "warned":               n_warn,
        "failed":               n_fail,
        "n_routed_fns":         len(fns),
        "handoff_keys":         l1_report,
        "specialist_awareness": l2_report,
        "worker_name_trust":    l3_report,
        "inventory":            l4_report,
        "issues":               [i for i in all_issues if not i.get("skip")],
        "warnings":             [i for i in all_issues if i.get("skip")],
    }
    with open("agent_handoff_contract_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
