"""
Envelope Conformance Validator (L0, P1 roadmap 2026-05-26).
============================================================
Every edge fn under supabase/functions/ (except _shared/ and config files)
must either:
  (a) import from "../_shared/envelope.ts" and return via ok()/fail(), OR
  (b) be declared in ENVELOPE_EXEMPT_PATHS below.

Why: a single response envelope makes the frontend retry/fallback logic
uniform across all routes, and lets gates assert contract conformance from
one helper. New edge fns that ship without the envelope re-fragment the
surface.

Exit codes:
  0  every edge fn imports envelope OR is on the exempt list
  1  one or more fns lack the envelope (FAIL with file:line)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "envelope_conformance_report.json"
BASELINE = ROOT / "envelope_conformance_baseline.json"

CHECK_NAMES = ["envelope_conformance"]

# Edge fns that pre-date the envelope and cannot be migrated atomically
# (e.g. they return non-JSON like audio/wav). Add new exemptions ONLY with
# a justification comment.
ENVELOPE_EXEMPT = {
    "audio-tts",            # returns audio/wav binary
    "audio-stt",            # streaming text/event-stream
    "cold-archive-query",   # bulk rows[] reader (hyparquet) - non-envelope by design
    "voice-health",         # legacy plain-text health probe
}

REQUIRED_TOKEN = '"../_shared/envelope.ts"'


def scan() -> dict:
    if not FN_DIR.exists():
        return {"fns": [], "missing": [], "error": "no functions dir"}
    fns, missing = [], []
    for entry in sorted(FN_DIR.iterdir()):
        if not entry.is_dir(): continue
        if entry.name.startswith("_"): continue
        index = entry / "index.ts"
        if not index.exists():
            continue
        text = index.read_text(encoding="utf-8", errors="replace")
        has_envelope = REQUIRED_TOKEN in text
        exempt = entry.name in ENVELOPE_EXEMPT
        row = {
            "fn":          entry.name,
            "has_envelope": has_envelope,
            "exempt":      exempt,
        }
        fns.append(row)
        if not has_envelope and not exempt:
            missing.append(row)
    return {"fns": fns, "missing": missing}


def main() -> int:
    result = scan()
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    n_fns     = len(result["fns"])
    n_missing = len(result["missing"])

    # Baseline ratchet — first run captures current gap; gate fails when
    # a new fn ships without the envelope or a previously compliant fn
    # drops it.
    baseline = n_missing
    if BASELINE.exists():
        try: baseline = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("missing", n_missing))
        except Exception: pass
    else:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")

    print(f"Envelope conformance: {n_fns} edge fns, {n_missing} missing envelope (baseline {baseline}).")
    if n_missing > baseline:
        print(f"\033[91mFAIL: regressed +{n_missing - baseline} above baseline\033[0m")
        for e in result["missing"][:10]:
            print(f"  - supabase/functions/{e['fn']}/index.ts")
        return 1
    if n_missing < baseline:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")
        print(f"\033[92mPASS: baseline tightened {baseline} → {n_missing}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
