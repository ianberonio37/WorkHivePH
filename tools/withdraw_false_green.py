# -*- coding: utf-8 -*-
"""Withdraw a row banked green on evidence that turned out not to support its claim.

WHY THIS IS A TOOL AND NOT A HAND EDIT. The ratchet in validate_live_mcp_bank.py allows the baseline
to fall ONLY for rows that are `owed` AND carry a `false-green-withdrawn` finding, and it records the
ids that bought the decrease so one withdrawal cannot pay for a second drop. Hand-editing a bank to
retract a green gets that shape wrong in ways that either fail the gate or, worse, pass it while
absorbing real drift. The retraction has to be as mechanical as the banking.

WHAT IT PRESERVES. The withdrawn evidence is not deleted -- it moves into the finding's
`withdrawn_evidence`. A retraction that threw the old reading away would cost the next session the
whole probe again, and would hide WHY the claim looked true. The point is the opposite: the finding
must make the false green legible, so the re-walk tests the thing the first walk missed.

    python tools/withdraw_false_green.py <page> <row-id> --title "..." --reason "..." [--apply]
"""
import argparse
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import validate_live_mcp_bank as V  # noqa: E402

GREEN, YEL, RED, DIM, RST = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("row_id")
    ap.add_argument("--title", required=True, help="one line: what the green claimed vs what is true")
    ap.add_argument("--reason", required=True, help="the full audit: which lens was blind, and to what")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    path = os.path.join(ROOT, "banks", "%s_live_mcp_bank.json" % a.page)
    bank = json.load(open(path, encoding="utf-8"))
    rows = bank.get("scenarios") or bank.get("rows") or []
    row = next((r for r in rows if str(r.get("id")) == a.row_id), None)
    if row is None:
        raise SystemExit("%sno such row%s: %s" % (RED, RST, a.row_id))

    gates, urls = V.gate_ids(), V.surface_urls(bank)
    state, why = V.classify(row, gates, urls)
    # A WITHDRAWAL IS ONLY MEANINGFUL AGAINST A GREEN. Withdrawing an owed row would mint a finding
    # that buys a future drop it never paid for -- the same both-ways-ratchet bug, from the other end.
    if state != "green":
        raise SystemExit("%sREFUSED%s %s is %s, not green%s — nothing to withdraw"
                         % (RED, RST, a.row_id, state, (" (%s)" % why) if why else ""))

    finding = {"date": date.today().isoformat(),
               "severity": "false-green-withdrawn",
               "title": a.title[:300],
               "detail": a.reason}
    old = row.get("evidence")
    if isinstance(old, dict):
        finding["withdrawn_evidence"] = {k: old.get(k) for k in
                                         ("kind", "ref", "asserts", "checked", "value_checked")
                                         if old.get(k)}
    row.setdefault("findings", []).append(finding)
    row["status"] = "owed"
    row.pop("evidence", None)

    after, _ = V.classify(row, gates, urls)
    print("  %s%s%s\n    green -> %s" % (YEL, a.row_id, RST, after))
    print("    %s%s%s" % (DIM, a.title, RST))
    if a.apply:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(bank, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
        print("  wrote %s" % os.path.relpath(path, ROOT))
        print("  %snow run validate_live_mcp_bank.py so the ratchet records the audited drop%s"
              % (DIM, RST))
    else:
        print("  (dry run — pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
