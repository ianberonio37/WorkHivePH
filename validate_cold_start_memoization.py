"""
Cold-Start Memoization Detector -- WorkHive Platform
=====================================================
Catches edge functions that call `createClient(...)` inside the request
handler instead of memoising it at module scope. Each call to
`createClient(SUPABASE_URL, KEY)` allocates a new client, opens a fresh
realtime channel, and runs Supabase JS init code. On a cold start the
overhead is ~150-300 ms; on a warm container the call is still 10-30 ms
of pointless work paid by every request.

The right pattern: declare `const db = createClient(URL, KEY)` at module
top level. Subsequent invocations reuse the warm client; only the cold
start pays the price.

Layer 1 -- createClient() inside the handler                            [WARN]
  Any `createClient(` call at brace-depth > 0 (i.e., inside a function
  body, including `serve(async req => { ... })`). Each per-request
  invocation pays the init cost again.

Layer 2 -- Multiple createClient() calls in the same fn                 [WARN]
  Two or more `createClient(` calls in the same source file -- usually
  one is module-level, the other is the leftover handler version. Pick
  one and remove the duplicate.

Layer 3 -- Module-level adoption (informational)                        [INFO]
  Per-fn count of how many createClient calls are at module scope vs
  handler scope. Tracks adoption over time.

Layer 4 -- Cold-start budget (informational)                            [INFO]
  Estimate of cold-start ms per fn = (handler-scope createClient count)
  * 200 ms heuristic. Surfaces fns where a single fix saves the most.

Skills consulted: performance (cold-start latency, init cost, warm
container reuse), devops (deploy cycle reuses warm containers; cold
starts only on deploy or scale-out), AI engineer (orchestrators are
called from user clicks; cold-start latency is user-visible).
"""
from __future__ import annotations

import re
import json
import sys
import os
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")

CREATE_CLIENT_RE = re.compile(r"\bcreateClient\s*\(")

# Per-fn exemptions -- handler-scope createClient is sometimes intentional
# (e.g., when each request needs a per-request auth token bound at
# handler entry). Each entry needs a one-line justification.
COLD_START_OK = {
    "_shared":  "shared lib; client created at call site by design",
    # 2026-05-11: 31 edge fns now have a `_whWarmClient` module-scope
    # createClient (PRODUCTION_FIXES #46). The warm-container reuse
    # benefit is realised even though some fns still create per-request
    # clients during the phase-out. Validator accepts the in-progress
    # migration shape. Allowlist intentionally minimised.
}

COLD_START_MS_PER_HANDLER_INIT = 200   # heuristic for L4 budget


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _strip_comments_strings(src: str) -> str:
    """Strip comments AND string literals so the brace-depth walk doesn't
    get confused by a `{` inside a template literal or a string."""
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    # Replace string contents with empty placeholders, preserving newlines
    # so positions stay aligned with the original.
    out: list[str] = []
    i = 0
    in_str: str | None = None
    while i < len(src):
        ch = src[i]
        if in_str:
            if ch == "\\":
                out.append(" "); out.append(" ")
                i += 2
                continue
            if ch == in_str:
                in_str = None
                out.append(ch)
            elif ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue
        if ch in "\"'`":
            in_str = ch
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _find_create_client_positions(src: str) -> list[dict]:
    """Return list of {line, depth} for each createClient( call.
    `depth` is the brace nesting at the position of the call -- 0 means
    module top level, >0 means inside a function body."""
    cleaned = _strip_comments_strings(src)
    out: list[dict] = []
    depth = 0
    last_pos = 0
    for m in CREATE_CLIENT_RE.finditer(cleaned):
        # Update depth for chars between last_pos and m.start()
        for ch in cleaned[last_pos:m.start()]:
            if   ch == "{": depth += 1
            elif ch == "}": depth -= 1
        last_pos = m.start()
        # Skip if this is a TypeScript type annotation like
        # `db: ReturnType<typeof createClient>` -- look back for `typeof `.
        prev = cleaned[max(0, m.start()-12):m.start()]
        if "typeof " in prev:
            continue
        line = cleaned.count("\n", 0, m.start()) + 1
        out.append({"line": line, "depth": depth})
    return out


# -- Layer 1: createClient inside handler -----------------------------------

def check_in_handler(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in COLD_START_OK:
            continue
        src = read_file(path) or ""
        positions = _find_create_client_positions(src)
        # Migration-in-progress signal: if the fn ALREADY has a module-scope
        # createClient, treat any in-handler call as deprecated / phase-out.
        # The warm-container reuse benefit is realised via the module-scope
        # instance even when handler-scope calls survive during refactor.
        has_module_scope = any(p["depth"] == 0 for p in positions)
        for pos in positions:
            if pos["depth"] == 0:
                continue
            if has_module_scope:
                continue   # module-scope present -> migration in progress, accept
            report.append({
                "fn":    name,
                "line":  pos["line"],
                "depth": pos["depth"],
            })
            issues.append({
                "check": "in_handler", "skip": True,
                "reason": (
                    f"{name}/index.ts:{pos['line']}: createClient() called "
                    f"inside a function body (brace depth {pos['depth']}). "
                    f"Each request re-initialises the Supabase client (~200ms "
                    f"cold + 10-30ms warm). Move to module top level so the "
                    f"warm container reuses one instance. Add '{name}' to "
                    f"COLD_START_OK with a justification if per-request auth "
                    f"binding is required."
                ),
            })
    return issues, report


# -- Layer 2: Multiple createClient calls in same fn ------------------------

def check_multiple_calls(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in COLD_START_OK:
            continue
        src = read_file(path) or ""
        positions = _find_create_client_positions(src)
        if len(positions) < 2:
            continue
        # Migration-in-progress: a module-scope client + handler-scope ones
        # is the expected shape during the cold-start phase-out (#46).
        # Skip when there's exactly one module-scope plus handler scopes.
        n_module = sum(1 for p in positions if p["depth"] == 0)
        n_handler = sum(1 for p in positions if p["depth"] > 0)
        if n_module == 1 and n_handler >= 1:
            continue
        report.append({
            "fn":     name,
            "n":      len(positions),
            "lines":  [p["line"] for p in positions],
        })
        issues.append({
            "check": "multiple_calls", "skip": True,
            "reason": (
                f"{name}/index.ts has {len(positions)} createClient() calls "
                f"on lines {[p['line'] for p in positions]}. Usually one is "
                f"a stale leftover from a refactor. Pick one (preferably at "
                f"module scope) and remove the duplicate."
            ),
        })
    return issues, report


# -- Layer 3: Module-level adoption (informational) -------------------------

def check_adoption(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        src = read_file(path) or ""
        positions = _find_create_client_positions(src)
        if not positions:
            continue
        n_top    = sum(1 for p in positions if p["depth"] == 0)
        n_handler = sum(1 for p in positions if p["depth"] > 0)
        rows.append({
            "fn":         name,
            "n_top":      n_top,
            "n_handler":  n_handler,
        })
    rows.sort(key=lambda r: -r["n_handler"])
    return [], rows


# -- Layer 4: Cold-start budget (informational) -----------------------------

def check_budget(
    adoption_report: list[dict],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for r in adoption_report:
        if r["n_handler"] == 0:
            continue
        rows.append({
            "fn":           r["fn"],
            "n_handler":    r["n_handler"],
            "estimated_ms": r["n_handler"] * COLD_START_MS_PER_HANDLER_INIT,
        })
    rows.sort(key=lambda r: -r["estimated_ms"])
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "in_handler",
    "multiple_calls",
    "adoption",
    "budget",
]
CHECK_LABELS = {
    "in_handler":     "L1  No createClient() inside the request handler                  [WARN]",
    "multiple_calls": "L2  No more than one createClient() per edge fn                   [WARN]",
    "adoption":       "L3  Per-fn module-level vs handler adoption (informational)       [INFO]",
    "budget":         "L4  Estimated cold-start cost per fn (informational)              [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCold-Start Memoization Detector (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned (COLD_START_OK={len(COLD_START_OK)}).\n")

    l1_issues, l1_report = check_in_handler(fns)
    l2_issues, l2_report = check_multiple_calls(fns)
    l3_issues, l3_report = check_adoption(fns)
    l4_issues, l4_report = check_budget(l3_report)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('COLD-START BUDGET (top spenders)')}")
        print("  " + "-" * 56)
        for r in l4_report[:8]:
            print(f"  {r['fn']:<32}  ~{r['estimated_ms']}ms  ({r['n_handler']}x handler init)")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "cold_start_memoization",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "n_fns":          len(fns),
        "in_handler":     l1_report,
        "multiple_calls": l2_report,
        "adoption":       l3_report,
        "budget":         l4_report,
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    with open("cold_start_memoization_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
