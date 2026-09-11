#!/usr/bin/env python3
"""advance_trajectory.py — move a trajectory along the flywheel, honestly. The ONLY writer of a
row's status/pct/basis.

Phase 5 of the P-program advances 500 rows through specced -> walked -> fixed -> locking -> locked.
Doing that by hand-editing trajectory_registry.json is how a percentage drifts: the pct field and
the status stop agreeing, or an in-flight row ends up carrying a number with no written reason.
Every rule the registry gate enforces is enforced HERE, at the moment of writing, so a dishonest
row cannot be created in the first place rather than being caught later by a board:

  · pct is DERIVED from status, never passed in (specced 5 / walked 25 / fixed 60 / locked 100);
    an in-flight status (walking/fixing/locking) takes an explicit --pct plus a basis.
  · a basis is REQUIRED for every in-flight and descoped row — "a percentage without a basis is
    a vibe" — and is APPENDED with a date stamp, never overwritten, so the row keeps its history.
  · 'locking' and 'locked' must NAME a gate (--gate), because those statuses MEAN a lock exists;
    the registry gate additionally holds the name to being registered in run_platform_checks.
  · forward-only by default: a row cannot silently regress to an earlier status (--allow-regress
    if a walk genuinely invalidates a claim, which should be rare and deliberate).

After writing it regenerates the header scoreboard and runs the registry gate, so the doc and the
SSOT can never be left disagreeing by a half-finished command.

  advance_trajectory.py --id P1 --status walked --basis "walked 3 viewports; 2 findings"
  advance_trajectory.py --id P1 --status fixed  --basis "central fix in utils.js:214"
  advance_trajectory.py --id P1 --status locking --pct 90 --gate render-integrity --basis "gate built"
  advance_trajectory.py --ids P1,P2,P3 --status walked --basis "wave P-A batch 1 walked"
  advance_trajectory.py --show P1
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
TODAY = "2026-09-05"

STATUS_PCT = {"specced": 5, "walked": 25, "fixed": 60, "locked": 100}
IN_FLIGHT = {"walking", "fixing", "locking"}
# In-flight states precede the state they finish into: walking -> walked, fixing -> fixed, locking -> locked.
# (2026-09-05: the old order put "fixed" before "fixing", so fixing -> fixed was refused as a regress.)
ORDER = ["specced", "walking", "walked", "fixing", "fixed", "locking", "locked"]


def _rank(s: str) -> int:
    return ORDER.index(s) if s in ORDER else -1


def _check(st, pct, basis, gate, ids, rows, allow_regress):
    """Every honesty rule, applied to one entry BEFORE anything is written. Returns an error string or None."""
    if not ids or not st:
        return "need an id and a status"
    if st not in STATUS_PCT and st not in IN_FLIGHT and st != "descoped":
        return f"unknown status {st!r}"
    if st in IN_FLIGHT:
        if pct is None or not (0 <= pct <= 100):
            return f"in-flight status {st!r} needs an explicit pct 0-100"
        if not (basis or "").strip():
            return f"in-flight status {st!r} needs a basis (a percentage without a basis is a vibe)"
    if st == "descoped" and not (basis or "").strip():
        return "descoped needs a basis saying why it is out of scope"
    if st in ("locking", "locked") and not gate:
        return f"status {st!r} MEANS a lock exists - name it with a gate registered in run_platform_checks"
    missing = [i for i in ids if i not in rows]
    if missing:
        return f"no such trajectories: {missing[:5]}"
    if not allow_regress:
        back = [i for i in ids if _rank(st) < _rank(rows[i]["status"])]
        if back:
            return (f"refusing to regress {back[:5]} (currently {rows[back[0]]['status']} -> {st}); "
                    "pass allow_regress if deliberate")
    return None


def _apply(st, pct, basis, gate, ids, rows):
    """Write one entry into the in-memory rows. The basis APPENDS, never overwrites."""
    for i in ids:
        t = rows[i]
        t["status"], t["pct"] = st, pct
        if (basis or "").strip():
            prev = (t.get("basis") or "").strip()
            t["basis"] = (prev + " \u00b7 " if prev else "") + f"[{TODAY}] {basis.strip()}"
        if gate:
            arts = t.setdefault("artifacts", {})
            gates = arts.setdefault("gates", [])
            for g in gate:
                if g not in gates:
                    gates.append(g)


def _self_test() -> int:
    """★A BATCH THAT HALF-APPLIES IS WORSE THAN ONE THAT REFUSES, so prove it refuses whole.

    If some rows advanced and others did not, the registry would carry both with no record of which - and
    every rule this file exists to enforce would be enforceable only on the entries that happened to be
    checked first. Each case below must be REFUSED and must leave the registry byte-identical.

    One case here was learned the hard way: the first version of this test aimed "specced -> specced" at a
    specced row and called it a regression. It is not one, the writer correctly accepted it, the test read
    that as a missing guard, and the write it caused had to be undone by hand. **A test that does not know
    what it is asserting will accuse the code and damage the data in the same step** - so the regression case
    now aims at a row that has actually advanced.
    """
    import hashlib
    import tempfile

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = {t["id"]: t for t in reg["trajectories"]}
    a_row = next(iter(rows))
    advanced = next((t["id"] for t in reg["trajectories"] if t.get("status") in ("locking", "locked")), None)
    if not advanced:
        print("FAIL advance-batch self-test - no advanced row to aim the regression case at")
        return 1

    def digest():
        return hashlib.sha256(REGISTRY.read_bytes()).hexdigest()

    cases = [
        ([{"id": "W_NO_SUCH_ROW", "status": "locking", "gate": ["x"], "basis": "b"}], "a nonexistent id"),
        ([{"id": a_row, "status": "locking", "basis": "b"}], "locking with no gate"),
        ([{"id": a_row, "status": "locking", "pct": 60, "gate": ["x"], "basis": ""}], "in-flight with no basis"),
        ([{"id": a_row, "status": "locking", "pct": 60, "gate": ["x"], "basis": "ok"},
          {"id": "W_NO_SUCH_ROW", "status": "locking", "pct": 60, "gate": ["x"], "basis": "bad"}],
         "one good entry beside one bad one"),
        ([{"id": advanced, "status": "specced", "gate": ["x"], "basis": "b"}], "a real regression"),
    ]
    fails = []
    for entries, label in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(entries, fh)
            path = fh.name
        before = digest()
        p = subprocess.run([sys.executable, str(Path(__file__)), "--batch", path],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        os.unlink(path)
        if p.returncode == 0:
            fails.append(f"{label} was ACCEPTED")
        elif digest() != before:
            fails.append(f"{label} was refused but the registry CHANGED")
    print("FAIL advance-batch self-test - " + "; ".join(fails) if fails
          else f"self-test OK: {len(cases)} bad batches, each refused whole, registry byte-identical after every one")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--ids", help="comma-separated ids to advance together")
    ap.add_argument("--status")
    ap.add_argument("--pct", type=int, help="only for an in-flight status")
    ap.add_argument("--basis", default="")
    ap.add_argument("--gate", action="append", default=[], help="gate id (repeatable)")
    ap.add_argument("--allow-regress", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--batch", help="a JSON file: [{id|ids, status, pct, basis, gate:[...]}, ...] applied "
                                    "in ONE pass - same rules, one scoreboard regeneration, one validation")
    a = ap.parse_args()

    # ★A BASIS THAT WENT THROUGH A SHELL CAN ARRIVE WITH ITS EVIDENCE EATEN (2026-09-09). W31103 was
    # banked with "occurred_at fell back to `new Date()`" and "the `deduped` counter" - both backticked,
    # both run as command substitution by bash, and both DELETED. What landed read as a finished sentence
    # while the two technical facts the basis existed to carry were simply gone; only reading the record
    # back caught it. A basis is evidence, so a gap where a word should be is worth refusing to accept
    # silently. Warn loudly and carry on - the writer decides, but never unknowingly.
    if a.basis:
        import re as _re
        _gaps = _re.findall(r"\b\w+  +(?:whenever|was|the|a|an|and|is|to|from|of|in)\b", a.basis)
        if _gaps:
            print("  ! WARNING: this basis has a word-gap where text may have been eaten by a shell "
                  f"({_gaps[:3]}). Backticks and $(...) run as commands in bash. Pass a basis through "
                  "subprocess with an ARGUMENT LIST, never a shell string. Recording it as given.")

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = {t["id"]: t for t in reg["trajectories"]}

    if a.show:
        t = rows.get(a.show)
        if not t:
            print(f"no such trajectory {a.show}")
            return 1
        print(json.dumps(t, ensure_ascii=False, indent=1))
        return 0

    if a.batch:
        entries = json.loads(Path(a.batch).read_text(encoding="utf-8"))
        errs, applied = [], 0
        # ★CHECK EVERY ENTRY BEFORE WRITING ANY OF THEM. A batch that half-applies is worse than one that
        # refuses: the registry would carry some rows advanced and some not, with no record of which.
        prepared = []
        for n, e in enumerate(entries):
            ids = [i.strip() for i in (e.get("ids") or e.get("id") or "").split(",") if i.strip()]
            st = e.get("status")
            pct = e.get("pct")
            if isinstance(pct, str) and pct.strip():
                pct = int(pct)
            pct = pct if st in IN_FLIGHT else (0 if st == "descoped" else STATUS_PCT.get(st))
            gate = e.get("gate") or []
            if isinstance(gate, str):
                gate = [gate]
            err = _check(st, pct, e.get("basis", ""), gate, ids, rows, e.get("allow_regress", False))
            if err:
                errs.append(f"  entry {n} ({ids[:1]}): {err}")
            else:
                prepared.append((st, pct, e.get("basis", ""), gate, ids))
        if errs:
            print(f"refusing the whole batch - {len(errs)} of {len(entries)} entries break a rule:")
            for e in errs[:12]:
                print(e)
            return 1
        for st, pct, basis, gate, ids in prepared:
            _apply(st, pct, basis, gate, ids, rows)
            applied += len(ids)
        reg["updated"] = TODAY
        tmp = REGISTRY.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, REGISTRY)
        print(f"advanced {applied} row(s) in one pass from {a.batch}")
        subprocess.run([sys.executable, str(ROOT / "tools" / "update_trajectory_scoreboard.py")],
                       capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_trajectory_registry.py")],
                           capture_output=True, text=True)
        print((r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "")
        return r.returncode

    ids = [i.strip() for i in (a.ids or a.id or "").split(",") if i.strip()]
    if not ids or not a.status:
        print("need --id/--ids and --status (or --show ID)")
        return 1
    st = a.status
    if st not in STATUS_PCT and st not in IN_FLIGHT and st != "descoped":
        print(f"unknown status {st!r} — one of {sorted(set(STATUS_PCT) | IN_FLIGHT)} or descoped")
        return 1

    # ── the honesty rules, enforced BEFORE anything is written ────────────────────────────────
    if st in IN_FLIGHT:
        if a.pct is None or not (0 <= a.pct <= 100):
            print(f"in-flight status {st!r} needs an explicit --pct 0-100")
            return 1
        if not a.basis.strip():
            print(f"in-flight status {st!r} needs a --basis (a percentage without a basis is a vibe)")
            return 1
    if st == "descoped" and not a.basis.strip():
        print("descoped needs a --basis saying why it is out of scope")
        return 1
    if st in ("locking", "locked") and not a.gate:
        print(f"status {st!r} MEANS a lock exists — name it with --gate <id> "
              "(and it must be registered in run_platform_checks)")
        return 1

    pct = a.pct if st in IN_FLIGHT else (0 if st == "descoped" else STATUS_PCT[st])
    missing = [i for i in ids if i not in rows]
    if missing:
        print(f"no such trajectories: {missing[:5]}")
        return 1
    if not a.allow_regress:
        back = [i for i in ids if _rank(st) < _rank(rows[i]["status"])]
        if back:
            print(f"refusing to regress {back[:5]} (currently "
                  f"{rows[back[0]]['status']} -> {st}); pass --allow-regress if deliberate")
            return 1

    for i in ids:
        t = rows[i]
        t["status"], t["pct"] = st, pct
        if a.basis.strip():
            # APPEND, never overwrite: the basis is the row's account of itself, and a walk that
            # replaces the previous reason destroys the evidence trail the gate reads back.
            prev = (t.get("basis") or "").strip()
            t["basis"] = (prev + " · " if prev else "") + f"[{TODAY}] {a.basis.strip()}"
        if a.gate:
            arts = t.setdefault("artifacts", {})
            gates = arts.setdefault("gates", [])
            for g in a.gate:
                if g not in gates:
                    gates.append(g)

    reg["updated"] = TODAY
    tmp = REGISTRY.with_suffix(".json.tmp")     # atomic: open(w) truncates before the write
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, REGISTRY)
    print(f"advanced {len(ids)} row(s) -> {st} (pct {pct})"
          + (f" · gates {a.gate}" if a.gate else ""))

    subprocess.run([sys.executable, str(ROOT / "tools" / "update_trajectory_scoreboard.py")],
                   capture_output=True, text=True)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_trajectory_registry.py")],
                       capture_output=True, text=True)
    print((r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "")
    return r.returncode


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
