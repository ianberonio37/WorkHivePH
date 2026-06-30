"""
Voice Router Determinism Oracle — guardian wrapper (Arc H H2)
============================================================
The Voice Action Router's intent classification is LLM-based (probabilistic,
needs a live model). Its routing/tool-selection CORRECTNESS lives in two PURE
deterministic functions in supabase/functions/_shared/voice-router-core.ts:

    sanitiseIntents()      — kind allowlist, confidence clamp [0,1], slot-fill
                             guard (asset-required intent w/ no asset demoted
                             below the 0.5 confirmation floor — the A3 junk-write
                             fix, WAT: the gate is code not the model).
    pickPrimaryCandidate() — asset disambiguation: context → exact → single → ambiguous.

This wrapper runs the VALUE oracle (tests/voice-router-determinism.spec.ts) that
exercises the REAL exported functions — the same module the edge function imports,
so there is one source and zero drift. It is HERMETIC: no Flask seeder, no Docker,
no model, no DB. That is why it lives as its own gate instead of riding the full
validate_playwright_smoke.py suite (which skips when the seeder is down).

Exit 0 = all oracle cases pass. Exit 1 = a routing-correctness invariant broke.

Usage:  python validate_voice_router_oracle.py
Output: voice_router_oracle_report.json

Skills consulted: ai-engineer (router contract = the deterministic half is
oracle-able even when the LLM half is not), qa (oracle asserts the VALUE not the
shape), security (slot-fill guard is code-enforced, never model-trusted),
platform-guardian (parseable output, graceful skip when node/playwright absent).
"""
import json
import os
import subprocess
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPEC = "voice-router-determinism"
CORE_MODULE = os.path.join("supabase", "functions", "_shared", "voice-router-core.ts")
SPEC_FILE = os.path.join("tests", "voice-router-determinism.spec.ts")
PW_CLI = os.path.join("node_modules", "@playwright", "test", "cli.js")
REPORT = "voice_router_oracle_report.json"
RUN_TIMEOUT = 180  # pure logic — finishes in ~1s, generous ceiling for cold start


def _bold(s):
    return f"\033[1m{s}\033[0m"


def _skip(reason: str) -> int:
    """Graceful skip (exit 0) — the gate cannot run in this env but nothing is broken.
    Mirrors validate_playwright_smoke.py's seeder-down skip pattern."""
    print(f"\033[93m  SKIP  {reason}\033[0m")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "voice_router_oracle", "skipped": True,
                   "reason": reason, "passed": 0, "failed": 0}, f, indent=2)
    return 0


def main() -> int:
    print(_bold("\nVoice Router Determinism Oracle (Arc H H2)"))
    print("=" * 55)

    # Structural preconditions — these MUST exist (the build is local, no excuse).
    if not os.path.exists(CORE_MODULE):
        print(f"\033[91m  FAIL  {CORE_MODULE} missing — routing core not extracted\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "voice_router_oracle", "passed": 0, "failed": 1,
                       "reason": f"{CORE_MODULE} missing"}, f, indent=2)
        return 1
    if not os.path.exists(SPEC_FILE):
        print(f"\033[91m  FAIL  {SPEC_FILE} missing — oracle spec not present\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "voice_router_oracle", "passed": 0, "failed": 1,
                       "reason": f"{SPEC_FILE} missing"}, f, indent=2)
        return 1

    # Runtime preconditions — skip gracefully if the JS toolchain is unavailable.
    if not os.path.exists(PW_CLI):
        return _skip(f"{PW_CLI} not found — run `npm install` to enable the oracle gate")

    # Invoke via `node <relative cli>` (NOT npx): the repo path contains '&' which
    # mangles npx's spawned path; a relative node invocation from cwd sidesteps it.
    cmd = ["node", PW_CLI, "test", SPEC, "--reporter=json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("\033[91m  FAIL  oracle run timed out\033[0m")
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"validator": "voice_router_oracle", "passed": 0, "failed": 1,
                       "reason": "timeout"}, f, indent=2)
        return 1
    except FileNotFoundError:
        return _skip("node not on PATH — install Node.js to enable the oracle gate")

    # Playwright's json reporter prints the report to stdout when --reporter=json
    # is given on the CLI. Parse stats.{expected,unexpected,flaky,skipped}.
    passed = failed = 0
    parsed_ok = False
    try:
        # The JSON object starts at the first '{' — node may prepend a banner line.
        out = proc.stdout
        brace = out.find("{")
        if brace >= 0:
            data = json.loads(out[brace:])
            stats = data.get("stats", {})
            passed = stats.get("expected", 0)
            failed = stats.get("unexpected", 0) + stats.get("flaky", 0)
            parsed_ok = True
    except (json.JSONDecodeError, ValueError):
        parsed_ok = False

    if not parsed_ok:
        # Fall back to the process exit code if JSON parse failed.
        failed = 0 if proc.returncode == 0 else 1
        passed = 0

    total = passed + failed
    if failed == 0 and passed > 0:
        print(f"\033[92m  PASS  {passed}/{total} routing-correctness oracle cases\033[0m")
    elif failed == 0 and passed == 0 and proc.returncode == 0:
        print("\033[92m  PASS  oracle ran clean (exit 0)\033[0m")
    else:
        print(f"\033[91m  FAIL  {passed} pass / {failed} fail — a routing invariant broke\033[0m")
        # Surface the first failing test names from stdout/stderr for the operator.
        tail = (proc.stdout or "")[-600:]
        if tail.strip():
            print(tail)

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"validator": "voice_router_oracle", "passed": passed,
                   "failed": failed, "total": total,
                   "returncode": proc.returncode}, f, indent=2)

    return 1 if (failed > 0 or proc.returncode != 0) else 0


if __name__ == "__main__":
    sys.exit(main())
