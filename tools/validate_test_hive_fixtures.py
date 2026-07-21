#!/usr/bin/env python3
"""validate_test_hive_fixtures.py — the stale-hive-fixture DETECTOR (gate `test-hive-fixtures`).

WHY (2026-07-21): a reseed is an identity-ROTATION event — it re-mints hive UUIDs. Any harness/
gate that PINS a hive UUID literal silently rots: the signed-in user isn't a member of the
pinned hive → RLS returns 0 rows / the edge fn 403s "not_a_member" → the surface is SKIPPED or
scanned EMPTY → the gate VACUOUSLY PASSES (it silently disables itself). This class has now
rotted through THREE generations of ids (9b4eaeac → 636cf7e8 → deleted; Lucena c9def338 →
4eec150e) across ~37+ files, and was "fixed" twice by pinning the NEXT id — which rotted too.

THE RULE: pinning a NEWER UUID is not a fix. Resolve at runtime from the live `hive_members`
row — Python: tools/lib/test_identity.py; JS: live_page_journeys.mjs signIn() (h.hive).

WHAT THIS GATE DOES (Detect + Govern):
  1. Scans tools/**.py|.mjs|.js + root *.mjs|.js for UUID literals on CODE lines (comment-only
     lines are skipped — a UUID in prose is history, not behavior) whose line/context mentions
     'hive'.
  2. Live-checks each pinned UUID against the CURRENT `hives` table (docker psql; skips cleanly
     if the DB is unreachable — never a false fail on a down stack).
  3. A pin that exists in `hives` = WARN (working today, will rot at the next reseed — convert
     to runtime-resolve). A pin that does NOT exist = STALE (the vacuous-pass hazard) → counted.
  4. Forward-only ratchet vs test_hive_fixture_baseline.json: the STALE count may only FALL.
     (Files converted to runtime-resolve keep their literal only as a documented FALLBACK —
     those lines are exempt via the marker 'fallback' on the line or the preceding line.)

  python tools/validate_test_hive_fixtures.py            # check
  python tools/validate_test_hive_fixtures.py --update-baseline
  python tools/validate_test_hive_fixtures.py --self-test

CONVERSION POLICY (2026-07-21, the wave that took STALE 54 → 39):
  - REGISTERED gates + shared harness libs (the vacuous-pass hazard class) = converted NOW:
    live_page_journeys signIn/h.hive · backend_live_invoke · page_battery/page_crud ·
    ai_live_invoke · crud_rollback · marketplace_trust · voice_family_probe · fb1 ·
    backend_edge_probe · companion batteries · axe_scan_live · arc_x/intuition/a1 (.mjs).
  - validate_narrative_grounding = DOCUMENTED-DEFERRED (snapshot-coupled; prior session's
    explicit disposition — see its own comment).
  - debug_*/scratch one-offs (not CI-run, cannot vacuous-pass a gate) = FIX-ON-TOUCH; the
    ratchet stops NEW pins and holds the count monotonic.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASELINE = REPO / "test_hive_fixture_baseline.json"
UUID_RE = re.compile(r"['\"]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})['\"]", re.I)
COMMENT_LEAD = re.compile(r"^\s*(#|//|\*|<!--|--)")

SCAN_GLOBS = ["tools/*.py", "tools/*.mjs", "tools/*.js", "tools/lib/*.py", "*.mjs"]
# The resolver itself + this gate mention historical ids in docstrings/comments by design.
EXEMPT_FILES = {"validate_test_hive_fixtures.py"}


def live_hive_ids() -> set[str] | None:
    """Current hives from the live DB, or None if unreachable (skip cleanly)."""
    try:
        r = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", "SELECT id FROM public.hives;"],
            capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return None
        return {ln.strip().lower() for ln in r.stdout.splitlines() if ln.strip()}
    except Exception:
        return None


def scan(repo: Path) -> list[dict]:
    """All hive-context UUID pins on code lines: [{file, line, uuid, fallback}]."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for g in SCAN_GLOBS:
        for f in sorted(repo.glob(g)):
            if f.name in EXEMPT_FILES or not f.is_file():
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines):
                if COMMENT_LEAD.match(ln):
                    continue                       # prose/history, not behavior
                m = UUID_RE.search(ln)
                if not m:
                    continue
                # hive-context = the line ITSELF mentions hive, or the directly-above line is a
                # COMMENT naming it ("# the test hive" ↵ pin). A neighbouring CODE line grants no
                # context — that bleed false-positived the self-test's USER fixture twice.
                above = lines[i - 1] if i else ""
                ctx = ln.lower()
                if COMMENT_LEAD.match(above):
                    ctx += " " + above.lower()
                if "hive" not in ctx:
                    continue                       # only hive pins; user ids etc. out of scope
                fallback = "fallback" in " ".join(lines[max(0, i - 3):i + 1]).lower()
                key = (str(f.relative_to(repo)), m.group(1).lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append({"file": key[0], "line": i + 1, "uuid": key[1], "fallback": fallback})
    return out


_SYNTHETIC_RUN = re.compile(r"([0-9a-f])\1{5}")   # >=6 identical hex chars in a row


def is_synthetic(uuid: str) -> bool:
    """Deliberately-fabricated probe ids (44444444-…, 77777777-…, a0000000-…) — used by
    adversarial gates (e.g. validate_hive_isolation spoof-INSERT row PKs) where nonexistence
    is the POINT. No real minted v4 UUID carries a >=6-char identical run."""
    return bool(_SYNTHETIC_RUN.search(uuid.replace("-", "")))


def classify(pins: list[dict], live: set[str]) -> tuple[list[dict], list[dict]]:
    """(stale, working). Exempt from STALE: documented fallbacks + synthetic probe ids."""
    stale = [p for p in pins
             if p["uuid"] not in live and not p["fallback"] and not is_synthetic(p["uuid"])]
    working = [p for p in pins if p["uuid"] in live]
    return stale, working


def self_test() -> int:
    fails = []
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "tools").mkdir()
        (repo / "tools" / "a.py").write_text(
            "# history: '1a2b3c4d-1111-4abc-8def-0123456789ab' hive\n"          # comment → skip
            "HIVE = '2b3c4d5e-2222-4bcd-8ef0-123456789abc'  # the test hive\n"  # code pin
            "# the fallback below is the documented last resort\n"
            "F = '3c4d5e6f-3333-4cde-8f01-23456789abcd'  # hive fallback only\n"  # fallback-marked
            "USER = '4d5e6f70-4444-4def-8012-3456789abcde'\n"                   # no hive context
            "SPOOF = '77777777-7777-4777-8777-777777777777'  # spoof hive row probe\n",  # synthetic
            encoding="utf-8")
        pins = scan(repo)
        uu = {p["uuid"][:1] for p in pins}
        if "1" in uu:
            fails.append("comment-line UUID should be skipped")
        if "2" not in uu:
            fails.append("code-line hive pin should be found")
        if "4" in uu:
            fails.append("non-hive-context UUID should be out of scope")
        stale, working = classify(pins, live={"5e6f7081-5555-4ef0-8123-456789abcdef"})
        if not any(p["uuid"].startswith("2") for p in stale):
            fails.append("nonexistent pinned hive should be STALE")
        if any(p["uuid"].startswith("3") for p in stale):
            fails.append("fallback-marked pin should be exempt from STALE")
        if any(p["uuid"].startswith("7") for p in stale):
            fails.append("synthetic probe id (repeated-run) should be exempt from STALE")
        stale2, working2 = classify(pins, live={"2b3c4d5e-2222-4bcd-8ef0-123456789abc"})
        if any(p["uuid"].startswith("2") for p in stale2) or not working2:
            fails.append("live pinned hive should classify as WORKING (warn)")
    if fails:
        print("FAIL validate_test_hive_fixtures self-test:")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS validate_test_hive_fixtures self-test (comment-skip / context / stale / fallback / working)")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    live = live_hive_ids()
    if live is None:
        print("SKIP test-hive-fixtures: local DB unreachable (docker psql) — cannot classify pins.")
        return 0
    pins = scan(REPO)
    stale, working = classify(pins, live)
    print(f"test-hive-fixtures: {len(pins)} hive-UUID pin(s) on code lines · "
          f"{len(stale)} STALE (vacuous-pass hazard) · {len(working)} working-but-pinned (warn) · "
          f"{sum(1 for p in pins if p['fallback'])} documented fallback(s) · live hives {len(live)}")
    for p in stale[:20]:
        print(f"  STALE  {p['file']}:{p['line']}  {p['uuid'][:8]}…  → convert to runtime-resolve "
              f"(test_identity.py / signIn h.hive)")
    for p in working[:10]:
        print(f"  warn   {p['file']}:{p['line']}  {p['uuid'][:8]}… exists today — will rot at the next reseed")
    if "--update-baseline" in argv:
        BASELINE.write_text(json.dumps({"stale": len(stale),
                                        "files": sorted({p['file'] for p in stale})}, indent=2),
                            encoding="utf-8")
        print(f"baseline banked: stale={len(stale)} → {BASELINE.name}")
        return 0
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text(encoding="utf-8")).get("stale", 0)
        if len(stale) > base:
            print(f"FAIL test-hive-fixtures: stale pins {len(stale)} > baseline {base} (forward-only ratchet)")
            return 1
        print(f"PASS test-hive-fixtures: stale {len(stale)} <= baseline {base} (ratchet held)")
        return 0
    print("PASS test-hive-fixtures (no baseline yet — run --update-baseline to lock the ratchet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
