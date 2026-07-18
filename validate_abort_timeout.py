"""
AbortSignal Timeout Coverage -- WorkHive Platform
==================================================
Catches outbound `fetch()` calls in edge functions that lack a timeout
signal. Without `signal: AbortSignal.timeout(N)`, a slow / hung third
party (OpenAI, Anthropic, Resend) holds the edge function open
indefinitely. The function then times out at the platform level (60s for
Supabase Edge), but during those 60 seconds it consumes a slot, blocks
queue progress, and a frontend `await db.functions.invoke(...)` keeps
the browser tab spinning.

Layer 1 -- fetch() to external host without signal                       [WARN]
  Any `fetch(URL, ...)` call where URL is a literal string containing
  a known third-party hostname AND the options object does not carry
  `signal: AbortSignal.timeout(...)`. Domain-internal fetches (Supabase
  RPC, internal helpers) are exempt by host pattern.

Layer 2 -- Long-running fetch loop without per-iteration timeout         [WARN]
  fetch() calls inside a `for` / `while` loop body that lack a timeout
  signal -- a single hung iteration will starve all the rest.

Layer 3 -- Timeout duration distribution (informational)                 [INFO]
  Per-fn breakdown of timeout values used. Helps spot inconsistency
  (one fn uses 5s, another 60s for the same upstream).

Layer 4 -- Edge fn without ANY fetch (informational)                     [INFO]
  Edge functions that do not call fetch() at all -- pure DB / response
  shapers; no upstream-timeout concern by definition.

Skills consulted: devops (deploy timeouts, request slot pressure),
performance (cold-start + upstream-stall amplification), AI engineer
(provider routing patterns; multi-provider chain in _shared expects
the caller to scope timeouts).
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

# Known external hostnames that warrant timeouts. Internal Supabase URLs
# (anything matching app.supabase_functions_url helpers) are exempt.
EXTERNAL_HOSTS = [
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"api\.groq\.com",
    r"api\.cerebras\.ai",
    r"api\.deepseek\.com",
    r"api\.resend\.com",
    r"openrouter\.ai",
    r"generativelanguage\.googleapis\.com",
    r"github\.com",
    r"hooks\.slack\.com",
]
EXTERNAL_RE = re.compile("|".join(EXTERNAL_HOSTS))

# fetch( ... )  -- captures the FULL parenthesised call (depth-aware walk).
FETCH_RE = re.compile(r"\bfetch\s*\(")
TIMEOUT_RE = re.compile(r"AbortSignal\.timeout\s*\(\s*(\d+)\s*\)")
SIGNAL_KEY_RE = re.compile(r"\bsignal\s*:\s*AbortSignal\.timeout")
LOOP_KEYWORDS = re.compile(r"\b(for|while)\s*\(")

# Per-fn exemptions. Each entry needs a one-line justification.
TIMEOUT_OK = {
    "_shared":  "shared lib; per-call site applies its own timeout",
}


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _find_fetch_calls(src: str) -> list[dict]:
    """Brace-depth walk for each fetch( ... ) call; returns list of
    {start, end, body, url_literal_or_none}."""
    out: list[dict] = []
    for m in FETCH_RE.finditer(src):
        i = m.end()       # position after the opening `(`
        depth = 1
        in_str = None
        body_start = i
        while i < len(src) and depth > 0:
            ch = src[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == in_str:
                    in_str = None
            elif ch in "\"'`":
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth != 0:
            continue   # malformed
        body = src[body_start:i-1]
        # Try to extract the literal URL (first string literal in body).
        url_m = re.search(r"['\"`]([^'\"`]+)['\"`]", body)
        url = url_m.group(1) if url_m else None
        out.append({
            "start": m.start(),
            "end":   i,
            "body":  body,
            "url":   url,
        })
    return out


def _line_no(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def _is_inside_loop(src: str, pos: int) -> bool:
    """Heuristic: walk backward from `pos` looking for a `for(` / `while(`
    that has a matching `}` AFTER pos. Cheap approximation."""
    # Look at the 800 chars before pos for a for/while keyword.
    window = src[max(0, pos - 800):pos]
    return bool(LOOP_KEYWORDS.search(window))


# -- Layer 1: fetch() to external host without signal -----------------------

def check_external_without_signal(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in TIMEOUT_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        for call in _find_fetch_calls(src):
            url = call["url"] or ""
            if not EXTERNAL_RE.search(url):
                # Try peeking at variables that might hold the URL.
                # If body contains an external host string anywhere, count it.
                if not EXTERNAL_RE.search(call["body"]):
                    continue
            if SIGNAL_KEY_RE.search(call["body"]):
                continue
            line = _line_no(src, call["start"])
            report.append({
                "fn":   name,
                "path": path,
                "line": line,
                "url":  url[:60] if url else "<dynamic>",
            })
            issues.append({
                "check": "external_without_signal", "skip": True,
                "reason": (
                    f"{name}/index.ts:{line}: fetch() to external host "
                    f"({url[:60] if url else 'dynamic URL'}) lacks "
                    f"`signal: AbortSignal.timeout(N)`. A hung upstream "
                    f"holds the edge fn open until the platform-level 60s "
                    f"timeout, blocking the queue and the frontend invoke. "
                    f"Add `signal: AbortSignal.timeout(10000)` (or appropriate)."
                ),
            })
    return issues, report


# -- Layer 2: fetch in loop without timeout --------------------------------

def check_loop_without_timeout(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in TIMEOUT_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        for call in _find_fetch_calls(src):
            if not _is_inside_loop(src, call["start"]):
                continue
            if SIGNAL_KEY_RE.search(call["body"]):
                continue
            line = _line_no(src, call["start"])
            report.append({
                "fn":   name,
                "line": line,
                "url":  (call["url"] or "<dynamic>")[:60],
            })
            issues.append({
                "check": "loop_without_timeout", "skip": True,
                "reason": (
                    f"{name}/index.ts:{line}: fetch() inside a for/while "
                    f"loop body lacks `signal: AbortSignal.timeout(N)`. One "
                    f"hung iteration starves the rest of the loop and "
                    f"compounds the latency budget. Add a per-iteration "
                    f"timeout signal."
                ),
            })
    return issues, report


# -- Layer 3: Timeout duration distribution (informational) ---------------

def check_timeout_distribution(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    counter: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        for m in TIMEOUT_RE.finditer(src):
            try:
                ms = int(m.group(1))
            except ValueError:
                continue
            counter[name][ms] += 1
    rows: list[dict] = []
    for name, by_ms in counter.items():
        rows.append({
            "fn":      name,
            "total":   sum(by_ms.values()),
            "by_ms":   dict(by_ms),
            "min_ms":  min(by_ms.keys()),
            "max_ms":  max(by_ms.keys()),
        })
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Layer 4: Edge fn without any fetch (informational) -------------------

def check_no_fetch_fns(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        if not _find_fetch_calls(src):
            rows.append({"fn": name})
    return [], rows


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = [
    "external_without_signal",
    "loop_without_timeout",
    "timeout_distribution",
    "no_fetch_fns",
]
CHECK_LABELS = {
    "external_without_signal": "L1  External fetch carries AbortSignal.timeout(N)               [WARN]",
    "loop_without_timeout":    "L2  fetch in for/while loop carries AbortSignal.timeout(N)      [WARN]",
    "timeout_distribution":    "L3  Timeout duration consistency per fn (informational)         [INFO]",
    "no_fetch_fns":            "L4  Edge fns with no fetch() at all (informational)             [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAbortSignal Timeout Coverage (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned (TIMEOUT_OK={len(TIMEOUT_OK)}).\n")

    l1_issues, l1_report = check_external_without_signal(fns)
    l2_issues, l2_report = check_loop_without_timeout(fns)
    l3_issues, l3_report = check_timeout_distribution(fns)
    l4_issues, l4_report = check_no_fetch_fns(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('TIMEOUT DURATION PER FN (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            timings = ", ".join(f"{ms}ms x{n}" for ms, n in sorted(r["by_ms"].items()))
            print(f"  {r['fn']:<30}  {r['total']:>2} timeouts  ({timings})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":               "abort_timeout",
        "total_checks":            total,
        "passed":                  n_pass,
        "warned":                  n_warn,
        "failed":                  n_fail,
        "n_fns":                   len(fns),
        "external_without_signal": l1_report,
        "loop_without_timeout":    l2_report,
        "timeout_distribution":    l3_report,
        "no_fetch_fns":            l4_report,
        "issues":                  [i for i in all_issues if not i.get("skip")],
        "warnings":                [i for i in all_issues if i.get("skip")],
    }
    with open("abort_timeout_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
