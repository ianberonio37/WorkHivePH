#!/usr/bin/env python3
"""seed_layer_fn_wave.py — the LX-FN wave: the surfaces the program had never named at all.

After the layer backfill and the LAYER-UX seeding, one gap was left over from the coverage audit: of
62 edge functions, 18 carried NO trajectory, and one learn article had none either. Every root page,
every calculator and 53 of 54 articles were covered; these 19 were the whole of what "uncharted"
still meant at the surface level.

They are seeded as their own wave rather than folded into LX-CI..LX-S because they are not a lens
applied across surfaces - they ARE the surfaces, one row each, and their question is the contract
question `prove_edge_contract.mjs` already asks of the other 44: what does this function do when it
is asked badly, and does a person on the other side get an answer they can act on.

Layers follow what the function IS, not where it sits: a login is Auth and Security, a webhook
receiver is APIs and Availability, an export is Database, a scorer is Cloud & Compute.

This module is also the DECLARATION the registry gate reads (the ★×16 rule): tools/
validate_trajectory_registry.py imports FUNCTIONS and LEARN from here, so the wave's size is stated
once and the gate and the seeder cannot disagree.

  python tools/seed_layer_fn_wave.py --dry-run
  python tools/seed_layer_fn_wave.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

FUNCTIONS = [
    "batch-risk-scoring", "benchmark-compute", "cmms-push-completion", "cmms-sync",
    "cmms-webhook-receiver", "cold-archive-query", "engineering-bom-sow", "export-hive-data",
    "gcash-receipt-inbound", "login", "notify-push", "pf-calculator", "platform-scraper",
    "project-progress", "resend-webhook-receiver", "send-report-email",
    "supervisor-reset-password", "weibull-fitter",
]
LEARN = "learn/philippine-plants-now-pay-the-highest-power-rates/index.html"
LEARN_TITLE = "Learn arrival: Philippine plants now pay the highest power rates"
WAVE = "LX-FN"


def layers_for(fn: str) -> list:
    """The layers this function's failure is felt through."""
    out = ["A"]
    if "login" in fn or "password" in fn:
        out += ["AU", "S"]
    if "export" in fn or "archive" in fn or "progress" in fn:
        out += ["D"]
    if "webhook" in fn or "inbound" in fn or "notify" in fn or "report-email" in fn:
        out += ["AV"]
    if any(k in fn for k in ("scraper", "compute", "scoring", "fitter", "calculator")):
        out += ["C"]
    if "cmms" in fn or "sync" in fn:
        out += ["D", "AV"]
    return list(dict.fromkeys(out))


def plan() -> list:
    """Every row this wave owns, in the order its ids were assigned."""
    rows = [{
        "wave": WAVE,
        "title": f"Edge function contract & failure modes: {fn}",
        "functions": [fn],
        "layers": layers_for(fn),
    } for fn in FUNCTIONS]
    rows.append({"wave": WAVE, "title": LEARN_TITLE, "pages": [LEARN], "layers": ["F", "H"]})
    return rows


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = doc["trajectories"]
    have = {r["id"] for r in rows}
    seen = {(r.get("title"), tuple(r.get("functions") or []), tuple(r.get("pages") or [])) for r in rows}

    nxt, created = 1, []
    for r in plan():
        key = (r["title"], tuple(r.get("functions") or []), tuple(r.get("pages") or []))
        if key in seen:
            continue
        while f"LX{nxt}" in have:
            nxt += 1
        rid = f"LX{nxt}"
        have.add(rid)
        created.append({"id": rid, "wave": r["wave"], "title": r["title"], "status": "specced",
                        "pct": 5, **({"functions": r["functions"]} if r.get("functions") else {}),
                        **({"pages": r["pages"]} if r.get("pages") else {}), "layers": r["layers"]})

    print(f"  {len(plan())} row(s) in {WAVE}; {len(created)} not yet in the registry")
    if args.dry_run:
        print("  (nothing written)")
        return 0
    if created:
        doc["trajectories"] = rows + created
        doc["count"] = len(doc["trajectories"])
        _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(f"  wrote {len(created)} row(s); registry now {doc['count']}")
    else:
        print("  nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
