#!/usr/bin/env python3
"""bank_fn_contracts.py - turn a function-contract walk into per-row bank entries (W3-FN).

`tools/prove_fn_contracts.mjs` asks each edge function three questions it never carried a row for, in the
words of the person the answer reaches: does it REFUSE a caller who is not entitled to it and say so (I),
does it DEGRADE legibly when its dependency is down (A), and does it answer its documented job in its own
declared shape with a real caller naming it (F). Each answer belongs to one seeded row - the wave was seeded
as three rows per function - so this matches verdicts back by (function, lens) and writes each through
`advance_trajectory.py`, the only writer of status/pct/basis.

Three verdicts, three different fates, and the third is the one worth being careful about:

  ok   -> banked. The contract held under a real call.
  BAD  -> HELD. The row keeps its finding and stays open; its two siblings may still bank, because a
          function that refuses correctly but degrades badly has one true claim and one false one.
  n/a  -> NEITHER. ★AN UNANSWERED CALL IS NOT A PASSED CONTRACT. When the platform bounds its own provider
          call at 60s and the prober waits 35, a timeout says nothing about the function - it says the
          instrument was less patient than its subject. Banking that as evidence would be inventing a
          reading; failing it would be blaming the product for the probe. It stays open and is reported.

  python tools/bank_fn_contracts.py .tmp/fn_contracts.json --dry-run
  python tools/bank_fn_contracts.py .tmp/fn_contracts.json --status locking --pct 60
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

# the seeded lens text per dimension - how a row is recognised without re-typing its title
LENS_KEY = {
    "I": "refuse this function to a caller who is not entitled",
    "A": "degrade legibly when this function's dependency is down",
    "F": "complete this function's documented job",
}


def rows_by_fn_lens() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = {}
    for t in reg["trajectories"]:
        if t.get("wave") != "W3-FN":
            continue
        fn = (t.get("functions") or [None])[0]
        dim = (t.get("ufai") or [None])[0]
        if not fn or dim not in LENS_KEY:
            continue
        if LENS_KEY[dim] in (t.get("title") or "").lower():
            out[(fn, dim)] = t
    return out


# ★WHAT EACH LENS USED TO ACCEPT, AND WHY IT PROVED NOTHING. All three graded the FIRST reply, so a request
# that died on its own shape - "Missing required field: question" - was read as the answer to a question it
# never reached. 128 of 186 rows were banked that way. A row cannot simply be re-banked over that: the old
# reading has to be withdrawn in words, so the ledger shows what was believed and why it was wrong.
WITHDRAWAL = {
    "I": "the old reading counted a 4xx complaining about MY REQUEST as a refusal of the CALLER - the "
         "request died on its shape, before anything looked at whose hive it named",
    "A": "the old reading counted a 4xx complaining about MY REQUEST as legible degradation of a DEPENDENCY "
         "the call never reached",
    "F": "the old reading counted a 4xx carried in the house envelope as the function COMPLETING its "
         "documented job - the envelope carried the complaint, not the work",
}
BANKED = ("locking", "locked", "fixed")

# ★A WITHDRAWAL MUST REST ON A READING, NOT ON THE ABSENCE OF ONE. Some `n/a` verdicts say the CLAIM was not
# reached ("the request never got past its own shape check") — those refute the old green. Others say the
# PROBE failed: it ran out of patience, the function is not deployed here, the host rate-limited it. Under
# memory pressure this machine produces the second kind in bulk, and withdrawing on them would delete good
# evidence because Docker was busy — the same error as reading a busy database as an empty one.
PROBE_FAILED = ("budget", "gave up first", "not deployed locally", "rate-limited", "wrong method",
                "429", "limit reached", "rate limit")

# ★A RETRACTION IS ABOUT THE OLD EVIDENCE, NOT THE NEW VERDICT. Deciding from the fresh reading got this
# backwards twice over: a row whose green was ALWAYS false stayed banked because today's re-ask happened to
# time out, and a row whose green was honestly earned would be withdrawn the day the host was busy. So the
# test is the basis itself. These are the exact shapes the corrected lenses proved cannot support the claim:
# a refusal read off a status that complains about the REQUEST, degradation read off a call that never
# reached the dependency, and a documented job "completed" by a non-2xx carried in the house envelope.
FALSE_GREEN = (
    re.compile(r"refused a foreign-hive request with (?:400|405|422|429)"),
    re.compile(r"degraded legibly: (?:400|422)"),
    re.compile(r"answered (?:400|401|403|405|422|429|5\d\d) in its own declared shape"),
    re.compile(r"name resolution failed"),          # the edge runtime was down; nothing was measured at all
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--status", default="locking")
    ap.add_argument("--pct", default="60")
    ap.add_argument("--gate", default="fn-contracts")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--withdraw-false-green", action="store_true",
                    help="a row already banked whose new reading does NOT support its claim is regressed to "
                         "specced, with the withdrawal written into its basis. Deliberate, never automatic.")
    a = ap.parse_args()

    doc = json.loads(Path(a.results).read_text(encoding="utf-8"))
    index = rows_by_fn_lens()
    banked = held = unanswered = unmatched = withdrawn = 0
    batch = []
    for r in doc.get("results", []):
        fn, lens = r.get("fn"), r.get("lens")
        row = index.get((fn, lens))
        if not row:
            unmatched += 1
            print(f"    no row  {str(fn)[:30]:32} {lens}")
            continue
        rid, was = row["id"], row.get("status")
        verdict = r.get("verdict")
        line = (r.get("line") or "").strip()
        probe_failed = any(p in line for p in PROBE_FAILED)
        # the LAST reading in the basis is the one the row currently stands on
        basis = (row.get("basis") or "").split("·")[-1]
        stands_on_false = any(p.search(basis) for p in FALSE_GREEN)
        # a fresh honest OK supersedes a false green - it is corrected, not retracted
        if verdict != "ok" and was in BANKED and stands_on_false:
            # this row is standing on evidence the corrected lens has just refuted
            withdrawn += 1
            # ★A WITHDRAWAL MUST STATE ITS OWN NUMBER. The registry gate holds every row's pct field to the
            # last `pct -> N` written in its basis, and a retraction that only narrates leaves the basis
            # still saying 60 while the field reads 5 - so the whole batch is refused for dishonesty by a
            # rule that exists to catch exactly that. A percentage without a basis is a vibe; a basis whose
            # number contradicts the field is worse.
            wb = (f"pct -> 5. WITHDRAWN: this row was banked green on a reading that does not support its claim - "
                  f"{WITHDRAWAL.get(lens, 'the lens could not answer it')}. Asked again with the request "
                  f"repaired at the function's own asking, {fn} now reads: {line}. Back to specced; the "
                  f"claim is unproven, not disproven.")
            act = "WITHDRAW" if (a.withdraw_false_green and not a.dry_run) else "would-wd"
            print(f"    {act} {rid:<8} {lens} {str(fn)[:28]:30} {line[:62]}")
            if a.withdraw_false_green and not a.dry_run:
                batch.append({"id": rid, "status": "specced", "basis": wb, "allow_regress": True})
            continue
        if verdict == "n/a":
            unanswered += 1
            why = "the probe failed, not the claim" if probe_failed else "unanswerable by this instrument"
            print(f"    open    {rid:<8} {lens} {str(fn)[:28]:30} {why}: {line[:56]}")
            continue
        if verdict != "ok":
            held += 1
            print(f"    hold    {rid:<8} {lens} {str(fn)[:28]:30} {line[:70]}")
            continue
        basis = (f"pct -> {a.pct}. WALKED LIVE {date.today().isoformat()} via tools/prove_fn_contracts.mjs - "
                 f"{lens} on {fn}: {line}"
                 + (" (this SUPERSEDES an earlier reading on this row that did not support the claim: the "
                    "lens graded whatever came back first, and what came back was a complaint about the "
                    "request. Asked properly, the claim holds.)" if stands_on_false else ""))
        if a.dry_run:
            print(f"    bank    {rid:<8} {lens} {str(fn)[:28]:30} {line[:70]}")
            banked += 1
            continue
        batch.append({"id": rid, "status": a.status, "pct": a.pct, "gate": [a.gate], "basis": basis})

    # ★ONE PASS, NOT ONE PER ROW. advance_trajectory.py re-runs the scoreboard generator AND the whole
    # registry validator on every call - measured at 30 SECONDS per banked row against a 7.7 MB registry, so
    # a 176-row wave regenerated the roadmap 176 times to answer one question each. --batch applies them
    # together under the same rules, with one regeneration and one validation at the end.
    if batch:
        Path(".tmp").mkdir(exist_ok=True)
        bf = Path(".tmp/bank_fn_batch.json")
        bf.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "advance_trajectory.py"), "--batch", str(bf)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print((p.stdout or p.stderr).strip()[-400:])
        banked = len(batch) if p.returncode == 0 else 0
        if p.returncode:
            print("    the batch was REFUSED, so nothing was written - fix the entries and re-run")
    print(f"\n  {banked} bankable · {held} held (each keeps its finding) · {unanswered} unanswered "
          f"(open - a timeout is not a pass) · {withdrawn} standing on a reading the corrected lens refutes"
          f"{' (WITHDRAWN)' if a.withdraw_false_green and not a.dry_run else ' (pass --withdraw-false-green to retract)'}"
          f" · {unmatched} verdict(s) matched no seeded row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
