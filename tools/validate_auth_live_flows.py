#!/usr/bin/env python3
"""validate_auth_live_flows.py — Arc I: confirm the LIVE auth-flow proofs passed (Playwright → local stack).

The `tests/auth-identity-arc-i.spec.ts` suite drives the REAL index.html auth flows against the local
stack (Flask seeder :5000 → local docker Supabase, real edge fns + RLS). This validator reads the
Playwright JSON report and confirms every Arc I auth test passed — that is the EVIDENCE that the I1/I2/I3/I4
flow cells are live (not merely code-proven). If the report is absent or any auth test failed, it returns
non-zero so the sweep keeps those cells at `proof` (honest — live requires the live run to have passed).

Maps passing tests → the cells they live-prove:
  I1/I login uniform-response            -> I1/I  (+ I1/U: signup/login forms render)
  I1/F + I3/F credential rules           -> I1/F, I3/F (+ I1/U, I3/U: fields render)
  I2/F login + session establishes       -> I2/F, I2/U
  I2/I signOut clears identity+hive       -> I2/I
  I4/F session carries DB-resolved role  -> I4/F

USAGE:      python tools/validate_auth_live_flows.py
            (run `node node_modules/@playwright/test/cli.js test tests/auth-identity-arc-i.spec.ts` first)
Self-test:  python tools/validate_auth_live_flows.py --self-test
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
# Prefer the dedicated Arc I report (not clobbered by other suites); fall back to the shared report.
_DEDICATED = ROOT / "auth_live_report.json"
REPORT = _DEDICATED if _DEDICATED.exists() else (ROOT / "playwright-report.json")
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

SPEC_TAG = "auth-identity-arc-i"
# required test-title substrings (one per Arc I live flow test)
REQUIRED = ["I1/I", "I1/F", "I2/F", "I2/I", "I4/F", "I7/I"]


def _collect_specs(node: dict, out: list, file_hint: str = ""):
    """Recursively gather {title, file, ok} for every spec in the Playwright JSON tree."""
    fh = node.get("file", file_hint)
    for spec in node.get("specs", []) or []:
        title = spec.get("title", "")
        ok = spec.get("ok")
        if ok is None:  # derive from results
            statuses = [r.get("status") for t in spec.get("tests", []) for r in t.get("results", [])]
            ok = bool(statuses) and all(s in ("passed", "expected") for s in statuses)
        out.append({"title": title, "file": spec.get("file", fh), "ok": ok})
    for child in node.get("suites", []) or []:
        _collect_specs(child, out, fh)


def audit(report: dict) -> tuple[list[tuple[str, str]], bool]:
    specs: list = []
    for s in report.get("suites", []) or []:
        _collect_specs(s, specs)
    auth = [s for s in specs if SPEC_TAG in (s.get("file") or "")]
    out: list[tuple[str, str]] = []
    if not auth:
        out.append(("FAIL", f"no {SPEC_TAG} specs in playwright-report.json (run the spec first)"))
        return out, False
    all_ok = True
    for needle in REQUIRED:
        match = [s for s in auth if needle in s["title"]]
        if not match:
            out.append(("FAIL", f"required live test '{needle}' not found in report")); all_ok = False
        elif not all(s["ok"] for s in match):
            out.append(("FAIL", f"live test '{needle}' did NOT pass")); all_ok = False
        else:
            out.append(("OK", f"live test '{needle}' passed"))
    return out, all_ok


def _self_test() -> int:
    good = {"suites": [{"file": "tests/auth-identity-arc-i.spec.ts", "specs": [
        {"title": f"{n} x", "ok": True} for n in REQUIRED]}]}
    bad = {"suites": [{"file": "tests/auth-identity-arc-i.spec.ts", "specs": [
        {"title": "I1/I x", "ok": True}, {"title": "I2/F x", "ok": False}]}]}
    good_ok = audit(good)[1] is True
    bad_ok = audit(bad)[1] is False
    ok = good_ok and bad_ok
    print(f"  self-test: all-pass→ok={good_ok}  one-fail→blocked={bad_ok}  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    if not REPORT.exists():
        print(f"{YEL}SKIP/FAIL{RST} — {REPORT.name} absent; run "
              f"`node node_modules/@playwright/test/cli.js test tests/{SPEC_TAG}.spec.ts` first")
        return 1
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print(f"{RED}FAIL{RST} — cannot parse {REPORT.name}: {e}")
        return 1
    findings, ok = audit(report)
    print("=" * 74)
    print("  validate_auth_live_flows — Arc I (live auth flows via Playwright → local stack)")
    print("=" * 74)
    for sev, msg in findings:
        c = GREEN if sev == "OK" else RED
        print(f"  {c}{sev:<4}{RST} {msg}")
    print("-" * 74)
    if not ok:
        print(f"  {RED}FAIL{RST} — not all Arc I live auth flows passed")
        return 1
    print(f"  {GREEN}PASS{RST} — all {len(REQUIRED)} Arc I auth flows live-proven against the local stack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
