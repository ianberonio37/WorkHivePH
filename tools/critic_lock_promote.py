#!/usr/bin/env python3
"""critic_lock_promote.py - the step that turns a critic row's "lock = <gate>" into LOCKED, or refuses to (2026-10-13).

Every receipt the critic closer writes ends "lock = family-rubric-ratchet on the full board", and the improvement plan
said the post-board step "flips critiqued/improving -> locked on gate-PASS". No tool did: post_board_promote.py only
reads trajectory_registry.json, so the critic program could never pass 85% however many rows improved, and a CLEAN
critiqued row (nothing found) could never pass 70%. A receipt that names a lock nothing ever checks is a claim, not a
lock. This is the place it is cashed.

A row is promoted to `locked` only when ALL of these hold:
  * platform_health.json is a FULL board (mode == "full") - never a --fast or --only run;
  * the board ran AFTER the row's newest evidence (the leading date of its newest improvement ref, or its walk date
    for a clean critique);
  * every gate its refs name after "lock = " is PASS on that board (a clean row names none, so it takes the default,
    family-rubric-ratchet - the gate that holds every page's rubric floor);
  * the row is `improving`, or `critiqued` with no findings (clean). A critiqued row WITH findings is never touched:
    nothing on it was fixed, so there is nothing to lock.
Anything else keeps the row where it is and says why. This tool never demotes a row.

  python tools/critic_lock_promote.py            # dry run: what would lock, what is kept and why
  python tools/critic_lock_promote.py --apply    # write `locked` + a lock ref, then validate and regenerate the scoreboard
  python tools/critic_lock_promote.py --self-test
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
HEALTH = ROOT / "platform_health.json"
DEFAULT_LOCK = "family-rubric-ratchet"
LOCK_RE = re.compile(r"lock = ([a-z0-9_\-]+(?:\s*\+\s*[a-z0-9_\-]+)*)")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
BASELINE = ROOT / "family_rubric_baseline.json"
# ★A LOCK IS ONLY AS WIDE AS WHAT ITS GATE MEASURES (2026-10-13). family-rubric-ratchet holds the floors of the pages the
# supervisor board sweeps. It backs a row whose evidence IS that board, or a supervisor / persona-agnostic row on those
# pages - and nothing else: a worker's in-motion walk, a signed-out screen or a page off the board is a different screen,
# and "locked by the ratchet" would be a sentence about something the ratchet never looked at. Measured on the first dry
# run: 1,808 of 3,566 candidates are covered; the rest need a screen-class ratchet of their own.
SWEEP_PERSONAS = {"supervisor", "any", ""}


def _board_pages() -> set:
    try:
        return set((json.loads(BASELINE.read_text(encoding="utf-8")).get("pages") or {}).keys())
    except (OSError, ValueError):
        return set()


def _ratchet_covers(r: dict, board_pages: set) -> bool:
    pg = set(r.get("pages") or [])
    if not pg or not pg <= board_pages:
        return False
    persona = r.get("persona") or ((r.get("cell") or "").split("|")[1:2] or [""])[0]
    return r.get("target_source") == "family-rubric-board" or persona in SWEEP_PERSONAS


def _board(health: dict):
    status = {v.get("id"): (v.get("status") or "").upper() for v in (health.get("validators") or []) if isinstance(v, dict)}
    ts = health.get("timestamp") or ""
    try:
        when = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        when = None
    return health.get("mode"), when, status


def _evidence_date(r: dict):
    dates = [m.group(1) for ref in (r.get("improvement_refs") or []) for m in [DATE_RE.match(str(ref))] if m]
    d = max(dates) if dates else (r.get("walked_at") or "")
    try:
        # the END of that day, conservatively: a board on the same day may have run before the evidence
        return _dt.datetime.fromisoformat(str(d)[:10] + "T23:59:59+00:00")
    except ValueError:
        return None


def _named_gates(r: dict) -> list[str]:
    gates = []
    for ref in r.get("improvement_refs") or []:
        for m in LOCK_RE.finditer(str(ref)):
            gates += [g.strip() for g in m.group(1).split("+") if g.strip()]
    return sorted(set(gates)) or [DEFAULT_LOCK]


def plan(critic: dict, health: dict, board_pages: set | None = None):
    mode, when, status = _board(health)
    board_pages = _board_pages() if board_pages is None else board_pages
    lock, keep = [], []
    for r in critic.get("rows") or []:
        st = r.get("status")
        clean = st == "critiqued" and not (r.get("findings") or [])
        if not (st == "improving" or clean):
            continue
        rid = r.get("id")
        if mode != "full":
            keep.append((rid, f"board mode is {mode!r}, not full"))
            continue
        ev = _evidence_date(r)
        if when is None or ev is None or when <= ev:
            keep.append((rid, "the board did not run after this row's evidence"))
            continue
        gates = _named_gates(r)
        if DEFAULT_LOCK in gates and not _ratchet_covers(r, board_pages):
            keep.append((rid, f"{DEFAULT_LOCK} does not measure this screen (a persona, signed-out or off-board walk)"))
            continue
        bad = [f"{g}={status.get(g) or 'not-on-board'}" for g in gates if status.get(g) != "PASS"]
        if bad:
            keep.append((rid, "; ".join(bad)))
            continue
        lock.append((r, gates))
    return mode, when, lock, keep


def main(apply: bool) -> int:
    if not HEALTH.exists():
        print("critic-lock-promote: platform_health.json absent - run a full board first.")
        return 1
    critic = json.loads(CRITIC.read_text(encoding="utf-8"))
    health = json.loads(HEALTH.read_text(encoding="utf-8"))
    mode, when, lock, keep = plan(critic, health)
    reasons: dict[str, int] = {}
    for _, why in keep:
        reasons[why.split(";")[0]] = reasons.get(why.split(";")[0], 0) + 1
    print(f"board mode={mode} ts={when.isoformat() if when else '?'}  |  lockable: {len(lock)}  kept: {len(keep)}")
    for why, n in sorted(reasons.items(), key=lambda x: -x[1])[:6]:
        print(f"  kept {n:5}  {why}")
    for r, gates in lock[:12]:
        print(f"  LOCK  {r['id']}  ({r['status']})  by {' + '.join(gates)}")
    if not apply:
        print("  (dry run - pass --apply to write)")
        return 0
    if not lock:
        return 0
    lockfile = str(CRITIC) + ".lock"
    import time as _time
    deadline = _time.time() + 60
    while True:
        try:
            os.close(os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)); break
        except FileExistsError:
            if _time.time() > deadline:
                print("refused: critic_registry.json is locked by another writer (60 s) - nothing written"); return 1
            _time.sleep(0.25)
    try:
        fresh = json.loads(CRITIC.read_text(encoding="utf-8"))
        by = {x["id"]: x for x in fresh["rows"]}
        today = _dt.date.today().isoformat()
        n = 0
        for r, gates in lock:
            cur = by.get(r["id"])
            if not cur or cur.get("status") != r.get("status") or cur.get("findings") != r.get("findings"):
                continue   # changed under us: leave it for the next run
            cur["status"] = "locked"
            cur.setdefault("improvement_refs", []).append(
                f"{today}: locked - {' + '.join(gates)} PASS on the full board of {when.isoformat(timespec='minutes')}, "
                f"after this row's evidence")
            n += 1
        fresh["updated"] = today
        tmp = str(CRITIC) + ".tmp"
        Path(tmp).write_text(json.dumps(fresh, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, CRITIC)
    finally:
        try:
            os.remove(lockfile)
        except OSError:
            pass
    print(f"applied: {n} row(s) -> locked")
    for cmd in (["tools/validate_critic_registry.py"], ["tools/update_critic_scoreboard.py"]):
        r = subprocess.run([sys.executable] + cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (r.stdout or r.stderr).strip().splitlines()
        print(f"  {'OK ' if r.returncode == 0 else 'ERR'} {cmd[0]}: {tail[-1][:100] if tail else ''}")
    return 0


def self_test() -> int:
    board_ts = "2026-10-20T09:00:00+00:00"
    def health(mode="full", ratchet="PASS", ts=board_ts):
        return {"mode": mode, "timestamp": ts, "validators": [{"id": DEFAULT_LOCK, "status": ratchet},
                                                               {"id": "critic-registry", "status": "PASS"}]}
    BP = {"hive.html"}
    imp = {"id": "A", "status": "improving", "findings": [{"dim": "B3"}], "walked_at": "2026-10-13",
           "pages": ["hive.html"], "cell": "phone-390|supervisor|x|y",
           "improvement_refs": ["2026-10-14: hive.html re-swept at 100% (...) with B3 clean; lock = family-rubric-ratchet on the full board"]}
    clean = {"id": "B", "status": "critiqued", "findings": [], "walked_at": "2026-10-13", "clean_note": "nothing found",
             "pages": ["hive.html"], "cell": "phone-390|worker|x|y", "target_source": "family-rubric-board"}
    worker = dict(imp, id="E", cell="phone-390|worker|x|y")
    offboard = dict(imp, id="F", pages=["learn/x/index.html"])
    open_row = {"id": "C", "status": "critiqued", "findings": [{"dim": "B3"}], "walked_at": "2026-10-13"}
    named = dict(imp, id="D", improvement_refs=["2026-10-14: ...; lock = calc-method-defaults-split + family-rubric-ratchet"])
    cases = [
        ("full board after the evidence, ratchet PASS: a supervisor row and a board-graded clean row lock; an open row,"
         " a worker's in-motion walk and an off-board page never do", health(), {"A", "B"}),
        ("a --fast board locks nothing", health(mode="fast"), set()),
        ("a board BEFORE the evidence locks nothing", health(ts="2026-10-13T08:00:00+00:00"), set()),
        ("the named gate FAILED: nothing locks", health(ratchet="FAIL"), set()),
    ]
    ok = True
    for name, h, want in cases:
        _, _, lock, _ = plan({"rows": [imp, clean, open_row, worker, offboard]}, h, BP)
        got = {r["id"] for r, _ in lock}
        ok &= got == want
        print(("ok " if got == want else "XX ") + f"{name}: {sorted(got)} (want {sorted(want)})")
    _, _, lock, keep = plan({"rows": [named]}, health(), BP)
    two = not lock and any("calc-method-defaults-split=not-on-board" in why for _, why in keep)
    ok &= two
    print(("ok " if two else "XX ") + "a row naming two gates locks only when BOTH passed (one is not on the board here)")
    print("PASS critic-lock-promote self-test" if ok else "FAIL critic-lock-promote self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main("--apply" in sys.argv))
