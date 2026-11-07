#!/usr/bin/env python3
"""critic_findings_census.py - what the critic program has FOUND, as trajectory cells (Wave CF, 2026-11-07).

Ian, 2026-11-07: "what we find in critic program should be added appropriate numbers of trajectories in trajectories
roadmap so that we have a common framework working on this."

The critic deepwalk grades screens and banks what fails into critic_registry (main + CX/GJ shards). Those findings lived in
a second ledger with its own percentage, outside the trajectory roadmap's CLOSED/OPEN line, its milestones and their pushes.
This census turns them into the roadmap's unit: ONE CELL PER DISTINCT DEFECT a person meets -

    (page, persona, dimension)   e.g. (inventory.html, solo-owner, G3) "three primary buttons at once"

never one per finding (43,136 findings on 1,929 open rows collapse to a few hundred defects: the same screen graded on
many walks), and never one per page (a page with three defects has three things to fix and three things to prove).

Two sources, both measured, never typed:
  1. THE BANK - every critic row still open (status critiqued, findings, no improvement_refs). Its finding evidence reads
     "<page>: <DIM> <n>% - <detail>"; the persona is the row's cell. Dimensions Ian descoped (N1, Filipino and dictionary
     work: tools/close_critic_findings.DESCOPED_DIMS) are not cells.
  2. THE BATCH LEDGER - critic_found_ledger.json. A batch walk that graded red and was fixed BEFORE it banked
     (critic_walk_batch.mjs --clean-only holds it) leaves no finding in the bank, so its defect would vanish from the
     roadmap. The batch appends each held defect here; a screen a page never showed the cast (it bounced them) is the
     pseudo-dimension SCREEN.

A cell's milestone (its block, each closed by a production push - Ian, 2026-11-04) is declared once, here:
CF_MILESTONES. Signed-in screens are M12; the signed-out face is M13.

    python tools/critic_findings_census.py           # the tables: per block, per persona, per dimension, per page
    python tools/critic_findings_census.py --json    # the machine population (what the seeder reads)
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import registry_io as _rio  # noqa: E402

LEDGER = ROOT / "critic_found_ledger.json"
SPEC = ROOT / "ufai-rubric-spec.json"
DIM_RE = re.compile(r"^\s*(?P<page>[^:]+?):\s*(?P<dim>[A-Z]{1,3}\d{1,2}|SCREEN)\b\s*(?P<detail>.*)$")

CF_MILESTONES = OrderedDict([
    ("M12", {"name": "the critic's finds on signed-in screens", "screen": "signed-in"}),
    ("M13", {"name": "the critic's finds on the signed-out face", "screen": "signed-out"}),
])
PSEUDO_DIMS = {"SCREEN": "the page's own screen - a page that bounces this person elsewhere has shown them nothing"}


def _descoped() -> dict:
    try:
        from close_critic_findings import DESCOPED_DIMS
        return dict(DESCOPED_DIMS)
    except Exception:
        return {"N1": "Filipino and dictionary work are out of the roadmap"}


def dim_names() -> dict:
    try:
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
    except Exception:
        return dict(PSEUDO_DIMS)
    out = {k: (v.get("title") or v.get("name") or k) for k, v in spec.items() if isinstance(v, dict) and k != "_meta"}
    out.update(PSEUDO_DIMS)
    return out


def page_file(pid: str) -> str:
    """A finding names its page by survey pageId ('hive', a learn slug, 'feedback', or a path). Resolve it to the served
    file, the way close_critic_findings resolves sweep keys: exact, '<pg>.html', '<pg>/index.html', then a family dir."""
    pid = (pid or "").strip().replace("\\", "/")
    for cand in (pid, f"{pid}.html", f"{pid}/index.html", f"learn/{pid}/index.html", f"tools/{pid}/index.html"):
        if cand and (ROOT / cand).is_file():
            return cand
    return pid if pid.endswith(".html") else f"{pid}.html"


def _persona(row: dict) -> str:
    parts = (row.get("cell") or "").split("|")
    return parts[1] if len(parts) > 1 and parts[1] else "any"


def screen_of(persona: str) -> str:
    return "signed-out" if persona == "anon" else "signed-in"


def milestone_of_screen(screen: str) -> str:
    for m, v in CF_MILESTONES.items():
        if v["screen"] == screen:
            return m
    return next(iter(CF_MILESTONES))


def read_ledger() -> list:
    try:
        return list(json.loads(LEDGER.read_text(encoding="utf-8")).get("found") or [])
    except FileNotFoundError:
        return []


def census(critic: dict | None = None) -> dict:
    critic = critic or _rio.load_critic()
    descoped = _descoped()
    names = dim_names()
    cells: "OrderedDict[tuple, dict]" = OrderedDict()

    def add(page, persona, dim, evidence, row_id, at, sev, source):
        key = (page, persona, dim)
        c = cells.get(key)
        if c is None:
            c = cells[key] = {"page": page, "persona": persona, "dim": dim, "dim_name": names.get(dim, dim),
                              "screen": screen_of(persona), "evidence": evidence, "found_at": at or "",
                              "severity": sev, "critic_ids": [], "findings": 0, "sources": []}
        c["findings"] += 1
        if row_id and row_id not in c["critic_ids"]:
            c["critic_ids"].append(row_id)
        if source not in c["sources"]:
            c["sources"].append(source)
        if sev is not None and (c["severity"] is None or sev < c["severity"]):
            c["severity"] = sev
        if at and (not c["found_at"] or at < c["found_at"]):
            c["found_at"], c["evidence"] = at, evidence

    skipped = Counter()
    for r in critic.get("rows") or []:
        if r.get("status") != "critiqued" or not r.get("findings") or r.get("improvement_refs"):
            continue
        at = r.get("banked_at") or r.get("walked_at") or ""
        for f in r["findings"]:
            m = DIM_RE.match(str(f.get("evidence") or ""))
            if not m:
                skipped["unparsed"] += 1
                continue
            if m["dim"] in descoped:
                skipped[f"descoped {m['dim']}"] += 1
                continue
            try:
                sev = int(f.get("severity"))
            except (TypeError, ValueError):
                sev = None
            add(page_file(m["page"]), _persona(r), m["dim"], str(f["evidence"])[:240], r["id"], at, sev, "critic-bank")
    for e in read_ledger():
        if e.get("dim") in descoped:
            skipped[f"descoped {e.get('dim')}"] += 1
            continue
        for rid in (e.get("critic_ids") or [e.get("walk")]) or [None]:
            add(page_file(e["page"]), e.get("persona") or "any", e["dim"], str(e.get("evidence") or "")[:240], rid,
                e.get("at") or "", e.get("severity"), "batch-held")
    for c in cells.values():
        c["milestone"] = milestone_of_screen(c["screen"])
    order = {m: i for i, m in enumerate(CF_MILESTONES)}
    ranked = sorted(cells.values(), key=lambda c: (order[c["milestone"]], c["severity"] if c["severity"] is not None else 9,
                                                  c["page"], c["persona"], c["dim"]))
    return {"cells": ranked, "skipped": dict(skipped),
            "by_block": Counter(c["milestone"] for c in ranked),
            "by_persona": Counter(c["persona"] for c in ranked),
            "by_dim": Counter(c["dim"] for c in ranked),
            "by_source": Counter(s for c in ranked for s in c["sources"]),
            "pages": len({c["page"] for c in ranked})}


def main() -> int:
    c = census()
    if "--json" in sys.argv:
        print(json.dumps({k: (v if k == "cells" else dict(v) if isinstance(v, Counter) else v) for k, v in c.items()},
                         ensure_ascii=False, indent=1))
        return 0
    n = len(c["cells"])
    print(f"CRITIC FINDINGS CENSUS - {n} distinct defects (page x persona x dimension) on {c['pages']} page(s)")
    print("  per block:   " + " · ".join(f"{m} {c['by_block'].get(m, 0)} ({v['name']})" for m, v in CF_MILESTONES.items()))
    print("  per source:  " + " · ".join(f"{k} {v}" for k, v in c["by_source"].most_common()))
    print("  per persona: " + " · ".join(f"{k} {v}" for k, v in c["by_persona"].most_common()))
    print("  per dim:     " + " · ".join(f"{k} {v}" for k, v in c["by_dim"].most_common()))
    if c["skipped"]:
        print("  not cells:   " + " · ".join(f"{k} {v}" for k, v in sorted(c["skipped"].items())))
    pages = Counter(x["page"] for x in c["cells"])
    print("  top pages:   " + " · ".join(f"{k} {v}" for k, v in pages.most_common(10)))
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
