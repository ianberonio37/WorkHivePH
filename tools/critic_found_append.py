#!/usr/bin/env python3
"""critic_found_append.py - write what a critic batch walk FOUND into critic_found_ledger.json (Wave CF, 2026-11-07).

A walk that grades red and is held (critic_walk_batch.mjs --clean-only) is fixed before it banks, so its defect never
reaches critic_registry; a walk whose page bounced the cast is never banked at all. Both are finds the trajectory roadmap
must carry (tools/critic_findings_census.py reads this ledger beside the bank). The batch calls this for every held walk:

    python tools/critic_found_append.py --walk BRH88 --ids BRH88,CX4044 --persona solo-owner \
        --surveys ".tmp/batchsurvey/BRH88_*.json"
    python tools/critic_found_append.py --walk BRH39 --ids BRH39 --persona solo-owner \
        --screen ai-quality --landed /workhive/hive.html          # the page never showed this person its screen

One entry per (page, persona, dimension, walk); a repeat is skipped. Written atomically.
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "critic_found_ledger.json"
SPEC = ROOT / "ufai-rubric-spec.json"
FAIL_RE = re.compile(r"^(?P<dim>[A-Z]{1,3}\d{1,2})\b\s*(?P<rest>.*)$")


def _severity(dim: str) -> int:
    try:
        v = json.loads(SPEC.read_text(encoding="utf-8")).get(dim) or {}
        return int(v.get("severity") or 2)
    except Exception:
        return 2


def entries_from_surveys(paths: list, persona: str, walk: str, ids: list, at: str) -> list:
    out = []
    for p in paths:
        try:
            s = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        page = s.get("pageId") or Path(p).stem.split("_", 1)[-1]
        for f in s.get("failing") or []:
            m = FAIL_RE.match(str(f))
            if not m:
                continue
            out.append({"page": page, "persona": persona, "dim": m["dim"], "severity": _severity(m["dim"]), "walk": walk,
                        "critic_ids": ids, "at": at, "source": "batch-held", "evidence": f"{page}: {str(f)[:220]}"})
    return out


def append(entries: list) -> int:
    try:
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
    except FileNotFoundError:
        doc = {"_doc": "see tools/critic_found_append.py", "found": []}
    have = {(e.get("page"), e.get("persona"), e.get("dim"), e.get("walk")) for e in doc.get("found") or []}
    added = 0
    for e in entries:
        k = (e["page"], e["persona"], e["dim"], e["walk"])
        if k in have:
            continue
        have.add(k)
        doc.setdefault("found", []).append(e)
        added += 1
    if added:
        tmp = LEDGER.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, LEDGER)
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--walk", required=True)
    ap.add_argument("--ids", default="")
    ap.add_argument("--persona", required=True)
    ap.add_argument("--surveys", default="")
    ap.add_argument("--screen", default="", help="a page that bounced the cast: its pageId")
    ap.add_argument("--landed", default="", help="where the cast was sent instead")
    a = ap.parse_args()
    ids = [i for i in a.ids.split(",") if i] or [a.walk]
    at = datetime.now().isoformat(timespec="minutes")
    if a.screen:
        entries = [{"page": a.screen, "persona": a.persona, "dim": "SCREEN", "severity": 2, "walk": a.walk, "critic_ids": ids,
                    "at": at, "source": "batch-held",
                    "evidence": f"{a.screen}: SCREEN - the page sent {a.persona} to {a.landed or 'another page'} instead of its own screen"}]
    else:
        entries = entries_from_surveys(sorted(glob.glob(a.surveys)), a.persona, a.walk, ids, at)
    n = append(entries)
    print(f"critic-found: {n} new find(s) from {a.walk} ({len(entries)} read)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
