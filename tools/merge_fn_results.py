#!/usr/bin/env python3
"""merge_fn_results.py — combine a base contract run with targeted re-asks, later reading wins.

★A RE-ASK IS ONLY WORTH RUNNING IF ITS ANSWER CAN REPLACE THE FIRST ONE. Two things make a contract run
worth repeating for a subset rather than whole: a lens corrected mid-flight (the running process still
carries the old code), and a call that timed out because this 8 GB host was under memory pressure rather
than because the function was slow. Both produce a reading that a second, quieter ask can settle — but only
if the results can be merged, and merged by (function, lens) so a later ok cannot silently overwrite an
earlier BAD belonging to a different question.

A merge is refused if an override names a (function, lens) the base never asked: that means the two runs
disagree about the roster, and a merge across different rosters is a merge of two different questions.

  python tools/merge_fn_results.py .tmp/base.json .tmp/patient.json --out .tmp/fn_merged.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("overrides", nargs="+")
    ap.add_argument("--out", default=".tmp/fn_merged.json")
    a = ap.parse_args()

    base = load(a.base)
    by_key = {(r["fn"], r["lens"]): r for r in base.get("results", [])}
    known = set(by_key)
    replaced, unknown = 0, []

    for path in a.overrides:
        for r in load(path).get("results", []):
            key = (r["fn"], r["lens"])
            if key not in known:
                unknown.append(f"{r['fn']}/{r['lens']}")
                continue
            if by_key[key] != r:
                replaced += 1
            by_key[key] = r

    if unknown:
        print(f"refusing the merge - {len(unknown)} override(s) name a (function, lens) the base never asked: "
              f"{', '.join(unknown[:6])}")
        return 1

    results = list(by_key.values())
    bad = sum(1 for r in results if r["verdict"] == "BAD")
    na = sum(1 for r in results if r["verdict"] == "n/a")
    out = {"asked": len(results), "bad": bad, "na": na, "results": results}
    Path(a.out).parent.mkdir(exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"merged {len(results)} reading(s); {replaced} replaced by a later ask  ·  "
          f"ok {len(results) - bad - na} · BAD {bad} · n/a {na}  ->  {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
