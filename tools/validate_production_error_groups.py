#!/usr/bin/env python3
"""validate_production_error_groups.py - production's error trail is READ, not only written (gate `production-errors-read`).

SL sub-layer L1 asks two things of every page: capture what it throws (prove_error_capture_everywhere.mjs) AND "someone
must read it". On 2026-10-14 the answer to Ian's missing logbook assets had been sitting in production's client_errors
for a month - 37 WebKit rows across nine pages - and nobody had read it: three local reproductions were built and
shipped first. This gate makes reading part of the board.

`production_error_groups.json` is a committed, read-only snapshot of production's client_errors grouped by page and
message (no person identifiers), refreshed through the Supabase MCP. Every (page, message) group must be answered by a
`resolutions` entry:

  status fixed   names >=1 registered gate that holds the fix, and either
                   fixed_on (+ optional commit, which must exist in git): the group's last_seen must not be AFTER the
                   fix - a group seen again after its fix is a fix that did not reach the person, and the gate reds;
                   verified_absent_since: the group's last_seen must be that date and at least 30 days before the
                   snapshot was read - silence long enough to mean something;
  status open    names the trajectory row that carries it (it must exist in the registry and not be descoped).

A group with no resolution FAILS: a new error in production is work, not background. A snapshot older than 14 days
WARNS: re-read production (the two GROUP BY queries in the file's _doc) and commit the new snapshot.

  python tools/validate_production_error_groups.py
  python tools/validate_production_error_groups.py --self-test
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "production_error_groups.json"
STALE_DAYS = 14
SILENCE_DAYS = 30
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def registered_gates() -> set:
    src = (ROOT / "run_platform_checks.py").read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'"id"\s*:\s*"([^"]+)"', src))


def registry_rows() -> dict:
    try:
        reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
        return {t["id"]: t.get("status") for t in reg["trajectories"]}
    except Exception:
        return {}


def commit_exists(sha: str) -> bool:
    r = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT, capture_output=True)
    return r.returncode == 0


def check(doc: dict, gates: set, rows: dict, commit_ok=commit_exists) -> tuple[list, list]:
    problems, warnings = [], []
    read_at = _date(doc.get("read_at") or "1970-01-01")
    if (dt.date.today() - read_at).days > STALE_DAYS:
        warnings.append(f"the snapshot was read {read_at} ({(dt.date.today() - read_at).days} days ago) - re-read "
                        f"production's client_errors and commit a fresh one")
    res = doc.get("resolutions") or []
    for g in doc.get("groups") or []:
        page = g.get("page")
        for m in g.get("messages") or []:
            msg = m.get("message")
            match = [r for r in res if r.get("message") == msg and (r.get("pages") == "*" or page in (r.get("pages") or []))]
            if not match:
                problems.append(f"{page}: '{msg[:70]}' ({m.get('n')}x, last {m.get('last_seen')}) has no resolution - a "
                                f"production error nobody has answered")
                continue
            r = match[0]
            last = _date(m.get("last_seen"))
            if r.get("status") == "open":
                if rows.get(r.get("row")) in (None, "descoped"):
                    problems.append(f"{page}: '{msg[:50]}' is open on row {r.get('row')!r}, which is not an in-scope row")
                continue
            if r.get("status") != "fixed":
                problems.append(f"{page}: '{msg[:50]}' has resolution status {r.get('status')!r} (fixed | open)")
                continue
            named = r.get("gates") or []
            missing = [x for x in named if x not in gates]
            if not named or missing:
                problems.append(f"{page}: '{msg[:50]}' is marked fixed with no registered gate holding it "
                                f"({'none named' if not named else 'unregistered: ' + ', '.join(missing)})")
            if r.get("commit") and not commit_ok(r["commit"]):
                problems.append(f"{page}: '{msg[:50]}' names fix commit {r['commit']}, which is not in this repository")
            if r.get("fixed_on"):
                if last > _date(r["fixed_on"]):
                    problems.append(f"{page}: '{msg[:50]}' was seen {last}, AFTER its fix on {r['fixed_on']} - the fix did "
                                    f"not reach the person; reopen it")
            elif r.get("verified_absent_since"):
                if last > _date(r["verified_absent_since"]):
                    problems.append(f"{page}: '{msg[:50]}' was seen {last}, after the silence it is resolved on "
                                    f"({r['verified_absent_since']})")
                elif (read_at - _date(r["verified_absent_since"])).days < SILENCE_DAYS:
                    problems.append(f"{page}: '{msg[:50]}' has been silent only since {r['verified_absent_since']} - "
                                    f"under {SILENCE_DAYS} days is not evidence it is gone")
            else:
                problems.append(f"{page}: '{msg[:50]}' is marked fixed with neither fixed_on nor verified_absent_since")
    return problems, warnings


def self_test() -> int:
    gates = {"g1"}
    rows = {"SL1": "specced", "SL2": "descoped"}
    base = {"read_at": dt.date.today().isoformat(),
            "groups": [{"page": "a.html", "messages": [{"message": "boom", "n": 3, "last_seen": "2026-10-01"}]}]}
    def with_res(r):
        d = json.loads(json.dumps(base)); d["resolutions"] = [r]; return d
    cases = [
        ("an unanswered group FAILs", base, 1),
        ("fixed with a gate, seen before the fix, passes", with_res({"message": "boom", "pages": "*", "status": "fixed", "fixed_on": "2026-10-02", "gates": ["g1"]}), 0),
        ("seen AFTER its fix FAILs", with_res({"message": "boom", "pages": "*", "status": "fixed", "fixed_on": "2026-09-30", "gates": ["g1"]}), 1),
        ("fixed with no registered gate FAILs", with_res({"message": "boom", "pages": "*", "status": "fixed", "fixed_on": "2026-10-02", "gates": ["nope"]}), 1),
        ("a missing fix commit FAILs", with_res({"message": "boom", "pages": "*", "status": "fixed", "fixed_on": "2026-10-02", "gates": ["g1"], "commit": "deadbeef"}), 1),
        ("open on a live row passes", with_res({"message": "boom", "pages": ["a.html"], "status": "open", "row": "SL1"}), 0),
        ("open on a descoped row FAILs", with_res({"message": "boom", "pages": ["a.html"], "status": "open", "row": "SL2"}), 1),
        ("a short silence FAILs", with_res({"message": "boom", "pages": "*", "status": "fixed", "verified_absent_since": "2026-10-01", "gates": ["g1"]}), 1),
    ]
    ok = True
    for label, doc, want in cases:
        probs, _ = check(doc, gates, rows, commit_ok=lambda sha: sha != "deadbeef")
        hit = (len(probs) >= 1) == (want >= 1)
        ok = ok and hit
        print(f"    {'ok ' if hit else 'BAD'}  {label}: {len(probs)} problem(s)")
    print(f"  self-test: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
    if not SNAPSHOT.exists():
        print("FAIL production-errors-read - no production_error_groups.json; read production's client_errors first")
        return 1
    doc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    problems, warnings = check(doc, registered_gates(), registry_rows())
    groups = sum(len(g.get("messages") or []) for g in doc.get("groups") or [])
    print(f"  snapshot read {doc.get('read_at')}: {doc.get('total')} error(s) in {groups} (page, message) group(s) on "
          f"{len(doc.get('groups') or [])} page(s); {len(doc.get('resolutions') or [])} resolution(s)")
    for w in warnings:
        print(f"  WARN {w}")
    if problems:
        print(f"FAIL production-errors-read - {len(problems)} group(s) not answered:")
        for p in problems[:12]:
            print(f"    - {p}")
        return 1
    print("PASS production-errors-read - every error production recorded is answered by a fix a registered gate holds "
          "(none seen after its fix), or by an open row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
