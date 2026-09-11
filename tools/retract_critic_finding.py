#!/usr/bin/env python3
"""retract_critic_finding.py - withdraw a banked critic finding the instrument got WRONG, with its reason.

★A RULER FIX DOES NOT REACH BACKWARDS (2026-09-10). Five instrument errors were found in one day - C2 not
knowing WCAG's disabled-control exemption, N1 counting `data-i` as if it were the whole i18n mechanism, X1's
guidance vocabulary speaking only English on a bilingual product, the offline-3g loss being random, and
release-mid-way firing on every document. Each was fixed in the ruler. But the ruler only grades the NEXT
walk: every claim the old ruler already banked stays in the registry, worded exactly as confidently as a true
one, and nothing in the bank knows it is stale. Fixing the instrument and leaving the findings is how a
retracted claim outlives its retraction - so the fix is only half done until the bank is corrected too.

THERE ARE TWO DIFFERENT CORRECTIONS AND THEY ARE NOT INTERCHANGEABLE:

  * the MEASUREMENT was right, the INTERPRETATION was wrong -> the finding STAYS and the row's prose carries
    the retraction. analytics N1 75% genuinely counts 1 of 6 `data-i` labels; what was false was the sentence
    'a Filipino technician meets a page that is largely still English', because the rest is rendered through
    `_t()`. Use --keep-finding: the number is evidence, the story about it was not.

  * the MEASUREMENT itself is now FALSE -> the finding is REMOVED. hive X1 80% claimed a dead-end at
    "Nothing to approve on this board."; that sentence renders only when work waits ELSEWHERE, and the very
    same branch paints the pointer to it in the adjacent element. Re-surveyed with the fixed ruler the page
    reads X1 100%, so the finding is not a softer claim - there is nothing left of it. Leaving it as prose
    would be worse than deleting it: a reader would meet a failing dim that the instrument no longer reports.

Either way the row keeps the RECORD in `clean_note` - what was claimed, why it was wrong, and what re-proved
it - because a bank that silently drops a claim teaches nobody. --replace-json adds the finding the corrected
walk DID justify, so a retraction can carry a real defect out with it rather than only subtracting.

  python tools/retract_critic_finding.py --dim X1 --evidence-contains "Nothing to approve" --why "..."
  python tools/retract_critic_finding.py ... --replace-json f.json --apply
  python tools/retract_critic_finding.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
TRAJ = ROOT / "trajectory_registry.json"   # carries journey.language, which the critic row does not


def apply_retraction(rows: list, dim: str, needle: str, why: str, keep_finding: bool,
                     replacement: dict | None, today: str, lang_ok=None) -> list:
    """Mutate `rows` in place; return the ids touched.

    A retraction that matches NOTHING is refused by the caller - silently touching zero rows reads like a
    success and is how a correction gets believed without ever landing.

    ★SOME RULERS ARE WRONG IN ONE LANGUAGE ONLY (2026-09-10). B3's readability grade is Flesch-Kincaid,
    whose coefficients are fitted to ENGLISH; on the platform's own EN/FIL parallel corpus the identical
    sentence grades +4.5 harder in Filipino (180 of 193 pairs), so the Filipino findings are artifacts
    while the English ones remain valid evidence. A retraction keyed only on dim+evidence cannot say that:
    the evidence string carries no language. `lang_ok` is a predicate over the ROW, so a caller can retract
    exactly the cells the ruler was wrong for and leave the rest standing. Retracting the English ones too
    would be the mirror error - over-correcting is still corrupting the bank.
    """
    touched = []
    for r in rows:
        if lang_ok is not None and not lang_ok(r):
            continue
        fs = r.get("findings") or []
        hit = [f for f in fs if f.get("dim") == dim and needle in str(f.get("evidence", ""))]
        if not hit:
            continue
        if not keep_finding:
            r["findings"] = [f for f in fs if not (f.get("dim") == dim and needle in str(f.get("evidence", "")))]
        if replacement:
            r.setdefault("findings", []).append(dict(replacement))
        verb = ("RETRACTED (interpretation only - the measurement stands)" if keep_finding
                else "RETRACTED and REMOVED (the measurement itself is false)")
        note = (f" [{today}] {verb}: {dim} - \"{str(hit[0].get('evidence', ''))[:150]}\". {why}")
        r["clean_note"] = (str(r.get("clean_note") or "").rstrip() + note).strip()
        touched.append(r.get("id"))
    return touched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", required=True)
    ap.add_argument("--evidence-contains", required=True)
    ap.add_argument("--why", required=True, help="why the claim was wrong and what re-proved it")
    ap.add_argument("--keep-finding", action="store_true",
                    help="the number is right, only the story about it was wrong")
    ap.add_argument("--replace-json", default="", help="path to a JSON finding the corrected walk DID justify")
    ap.add_argument("--ids", default="",
                    help="comma-separated critic row ids - narrow the retraction to exactly these rows, "
                         "for a ruler that was wrong on SOME pages of a row and right on the rest")
    ap.add_argument("--lang", default="",
                    help="retract only rows whose journey language is this (e.g. fil) - for a ruler that is "
                         "wrong in ONE language only, such as B3's English-calibrated readability grade")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    doc = json.loads(io.open(CRITIC, encoding="utf-8").read())
    rows = doc["rows"] if isinstance(doc, dict) and "rows" in doc else doc
    replacement = None
    if args.replace_json:
        replacement = json.loads(io.open(args.replace_json, encoding="utf-8").read())
        for k in ("dim", "evidence"):
            if k not in replacement:
                print(f"refused: the replacement finding needs a {k!r}")
                return 1

    id_ok = None
    if args.ids:
        # ★A RULER CAN BE WRONG FOR SOME PAGES IN A ROW, NOT THE WHOLE ROW (2026-09-11). B3's grade was
        # keyed on the READER'S preference rather than the text's language, so it was withheld on
        # ENGLISH-ONLY content (the learn articles and calculators) whenever the walk was cast in
        # Filipino. `--dim B3 --lang fil` matched 69 rows — but on 63 of them the page's text really IS
        # Filipino and `grade=n/a` is the CORRECT reading, so retracting them would have annotated 63
        # sound findings with a correction that does not apply to them. The precise set was six rows on
        # one article. A retraction that cannot be narrowed to the rows it is true of is not a
        # correction, it is a second error, so the tool has to be able to name them.
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
        id_ok = lambda r: str(r.get("id")) in wanted                  # noqa: E731

    lang_ok = None
    if args.lang:
        # The language lives on the TRAJECTORY (journey.language), not on the critic row, so it is read
        # from there; a row whose trajectory is missing is never retracted on a guess.
        tdoc = json.loads(io.open(TRAJ, encoding="utf-8").read())
        tlist = tdoc["trajectories"] if isinstance(tdoc, dict) and "trajectories" in tdoc else tdoc
        langs = {x.get("id"): ((x.get("journey") or {}).get("language")) for x in tlist}
        lang_ok = lambda r: langs.get(r.get("id")) == args.lang       # noqa: E731

    # both filters may be given; a row must satisfy every one that is present
    preds = [p for p in (id_ok, lang_ok) if p]
    row_ok = (lambda r: all(p(r) for p in preds)) if preds else None
    touched = apply_retraction(rows, args.dim, args.evidence_contains, args.why,
                               args.keep_finding, replacement, date.today().isoformat(), row_ok)
    if not touched:
        print(f"refused: no banked finding matches dim {args.dim} containing {args.evidence_contains!r}"
              + (f" on a {args.lang!r} walk" if args.lang else "")
              + " - nothing was changed (a retraction that lands on zero rows is not a retraction)")
        return 1

    print(f"{'APPLY' if args.apply else 'DRY RUN'}: {args.dim} retracted on {len(touched)} row(s): "
          + ", ".join(str(t) for t in touched[:12]) + (" ..." if len(touched) > 12 else ""))
    print(f"  finding {'kept (interpretation retracted)' if args.keep_finding else 'REMOVED'}"
          + (f"; replacement {replacement['dim']} added" if replacement else ""))
    if not args.apply:
        print("  re-run with --apply to write critic_registry.json")
        return 0

    tmp = CRITIC.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CRITIC)
    print(f"  wrote {CRITIC.name}")
    return 0


def _self_test() -> int:
    fails = []
    mk = lambda: [{"id": "R1", "clean_note": "walked.",
                   "findings": [{"dim": "X1", "evidence": "hive: X1 80% - dead-end \"Nothing to approve\""},
                                {"dim": "C2", "evidence": "logbook: C2 92%"}]},
                  {"id": "R2", "clean_note": "walked.",
                   "findings": [{"dim": "X1", "evidence": "other: X1 50% - something else"}]}]

    rows = mk()
    t = apply_retraction(rows, "X1", "Nothing to approve", "the sibling carried the link.", False, None, "D")
    if t != ["R1"]:
        fails.append(f"only the matching row may be touched, got {t}")
    if [f["dim"] for f in rows[0]["findings"]] != ["C2"]:
        fails.append("a false measurement must be REMOVED, leaving the row's other findings intact")
    if "RETRACTED and REMOVED" not in rows[0]["clean_note"] or "sibling carried" not in rows[0]["clean_note"]:
        fails.append("the row must record WHAT was retracted and WHY")
    if len(rows[1]["findings"]) != 1:
        fails.append("a non-matching X1 finding on another row must survive")

    rows = mk()
    apply_retraction(rows, "X1", "Nothing to approve", "the count is real.", True, None, "D")
    if [f["dim"] for f in rows[0]["findings"]] != ["X1", "C2"]:
        fails.append("--keep-finding must leave the measurement banked")
    if "interpretation only" not in rows[0]["clean_note"]:
        fails.append("--keep-finding must say the measurement stands")

    rows = mk()
    apply_retraction(rows, "X1", "Nothing to approve", "w", False,
                     {"dim": "U3", "evidence": "hive: the pointer named a page that owed nothing"}, "D")
    if [f["dim"] for f in rows[0]["findings"]] != ["C2", "U3"]:
        fails.append("a replacement finding must be appended when the corrected walk justifies one")

    rows = mk()
    if apply_retraction(rows, "Z9", "nope", "w", False, None, "D"):
        fails.append("a retraction matching nothing must touch no rows (main() then refuses)")

    # A ruler wrong in ONE language must retract only that language's rows (B3/Flesch-Kincaid, 2026-09-10).
    rows = mk()
    only_first = apply_retraction(rows, "X1", "Nothing to approve", "FK is English-calibrated.", False,
                                  None, "D", lang_ok=lambda r: r.get("id") == rows[0]["id"])
    if only_first != [rows[0]["id"]]:
        fails.append("--lang must retract ONLY rows the predicate admits")
    if not (rows[1].get("findings") or []):
        fails.append("--lang must leave an excluded row's findings entirely untouched")
    if rows[1].get("clean_note") != "walked.":
        fails.append("--lang must leave an excluded row's clean_note byte-identical (no retraction note)")

    print("FAIL retract_critic_finding self-test - " + "; ".join(fails) if fails
          else "self-test OK: a false measurement is removed, a true one is kept with its interpretation "
               "retracted, other rows and other dims are untouched, a replacement finding lands, and a "
               "retraction that matches nothing changes nothing")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
