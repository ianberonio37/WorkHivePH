#!/usr/bin/env python3
"""validate_realtime_live.py — Arc J: confirm the LIVE realtime proofs passed (Playwright → local stack).

The realtime specs drive REAL Supabase Realtime against the local stack (Flask seeder :5000 → local docker,
real WebSocket + RLS + the supabase_realtime container). This validator reads the Playwright JSON report and
confirms the realtime tests passed — that is the EVIDENCE that the J1/F (live delivery), J5 (presence), and
J6 (payload-safe handling) cells are LIVE, not merely code-proven. If the report is absent or any required
test failed, it returns non-zero so the sweep keeps those cells at `proof` (honest — live requires the live
run to have passed, which requires `docker start supabase_realtime_workhive`).

Maps passing tests → the cells they live-prove:
  feedback-realtime inbox_realtime_pushes_new_row -> J1/F  (real WS+RLS delivery to an AUTHENTICATED admin;
                                                            post-20260621000003 anon is correctly excluded)
  journey-realtime  K1_logbook_insert_subscription -> J2/F (channel wired to postgres_changes INSERT)
  journey-realtime  K2_logbook_delete_subscription -> J6/F (payload.old?.id REPLICA-IDENTITY-safe handling)
  journey-realtime  K3_presence_channel_declared   -> J5/F (presence channel + chip, static)
  realtime-arc-j    J5 presence two same-hive ...   -> J5/F,J5/U,J5/A,J5/I (LIVE WS presence sync +
                                                       self "(you)" + hive-scoped, no cross-hive bleed)

USAGE:      python tools/validate_realtime_live.py
            (run the realtime specs first, writing realtime_live_report.json — see --self-test note)
Self-test:  python tools/validate_realtime_live.py --self-test
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_DEDICATED = ROOT / "realtime_live_report.json"
REPORT = _DEDICATED if _DEDICATED.exists() else (ROOT / "playwright-report.json")
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

SPEC_TAGS = ("feedback-realtime", "journey-realtime", "realtime-arc-j")
# required test-title substrings — the live realtime proofs
REQUIRED = ["inbox_realtime_pushes_new_row", "K1_logbook_insert", "K2_logbook_delete",
            "K3_presence", "J5 presence", "J1/J2 subscription isolation", "J3 listener lifecycle",
            "J4 connection-state guard"]


def _collect_specs(node: dict, out: list, file_hint: str = ""):
    fh = node.get("file", file_hint)
    for spec in node.get("specs", []) or []:
        ok = spec.get("ok")
        if ok is None:
            statuses = [r.get("status") for t in spec.get("tests", []) for r in t.get("results", [])]
            ok = bool(statuses) and all(s in ("passed", "expected") for s in statuses)
        out.append({"title": spec.get("title", ""), "file": spec.get("file", fh), "ok": ok})
    for child in node.get("suites", []) or []:
        _collect_specs(child, out, fh)


def audit(report: dict) -> tuple[list[tuple[str, str, bool]], bool]:
    specs: list = []
    for s in report.get("suites", []) or []:
        _collect_specs(s, specs)
    rt = [s for s in specs if any(tag in (s.get("file") or "") for tag in SPEC_TAGS)]
    rows: list[tuple[str, str, bool]] = []
    all_ok = True
    for req in REQUIRED:
        match = next((s for s in rt if req in (s.get("title") or "")), None)
        ok = bool(match and match["ok"])
        rows.append((req, (match or {}).get("title", "(not found)"), ok))
        if not ok:
            all_ok = False
    return rows, all_ok


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        # synthetic report: all required pass
        fake = {"suites": [{"file": "tests/feedback-realtime.spec.ts", "specs": [
                    {"title": "inbox_realtime_pushes_new_row: ...", "ok": True}]},
                {"file": "tests/journey-realtime.spec.ts", "specs": [
                    {"title": "K1_logbook_insert_subscription_present", "ok": True},
                    {"title": "K2_logbook_delete_subscription_safe", "ok": True},
                    {"title": "K3_presence_channel_declared", "ok": True}]},
                {"file": "tests/realtime-arc-j.spec.ts", "specs": [
                    {"title": "J5 presence: two same-hive workers see each other live", "ok": True},
                    {"title": "J1/J2 subscription isolation: filter=<foreignHive> is blocked", "ok": True},
                    {"title": "J3 listener lifecycle: subscribe adds a channel", "ok": True},
                    {"title": "J4 connection-state guard: rtConn() fires offline", "ok": True}]}]}
        rows, ok = audit(fake)
        assert ok, "self-test should pass"
        bad = dict(fake); bad["suites"][0]["specs"][0]["ok"] = False
        _, ok2 = audit(bad)
        assert not ok2, "self-test should fail when a required test fails"
        print(f"  {GREEN}self-test OK{RST} — audit() passes all-green and fails on a regression")
        return 0

    print("=" * 74)
    print("  Arc J — Realtime LIVE proofs (Playwright → local WS + RLS)")
    print("=" * 74)
    if not REPORT.exists():
        print(f"  {YEL}SKIP{RST}: {REPORT.name} not found — run the realtime specs first")
        print(f"  (PLAYWRIGHT_JSON_OUTPUT_NAME=realtime_live_report.json node node_modules/@playwright/test/cli.js \\")
        print(f"     test tests/feedback-realtime.spec.ts tests/journey-realtime.spec.ts --reporter=json)")
        return 1
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  {RED}ERROR{RST}: could not parse {REPORT.name}: {e}")
        return 1
    rows, ok = audit(report)
    for req, title, passed in rows:
        tag = f"{GREEN}LIVE{RST}" if passed else f"{RED}FAIL{RST}"
        print(f"    {tag}  {req}  ·  {title[:60]}")
    print(f"\n  {(GREEN+'ALL REALTIME LIVE PROOFS PASSED'+RST) if ok else (RED+'realtime live proof missing/failed'+RST)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
