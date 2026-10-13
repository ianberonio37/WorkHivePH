#!/usr/bin/env python3
"""fold_journey_rerun.py: fold an ISOLATED journey re-run into the full live_page_journeys sweep, with provenance.

WHY (2026-10-13, release night). The full sweep (110 journeys, ~25 minutes on this host) reported LA7 as a gap.
The product was right and the journey was stale: the page now reveals its sticky mobile CTA only once the hero's
own button has left through the top of the screen, and LA7 still scrolled a fixed 800px, where the bar is correctly
hidden. After the journey was corrected, `--journey LA7` passed alone. But validate_conversion_bank.py reads the
FULL results file, and the runner, by design, writes a narrowed run to its own suffixed file so that a narrowed run
can never be read as a complete sweep (live_page_journeys.mjs, the NARROW comment). The only ways back were to
re-run all 110 journeys for one changed journey, or to fold the one re-run in, which is this tool.

WHAT IT KEEPS HONEST, on purpose:
  * The base stays the full sweep: every journey not named here keeps the record and the timestamp it was walked with.
  * A journey is folded only from its own isolated file (live_page_journeys_results.journey-<ID>.json), only if that
    run is NEWER than the sweep and walked exactly that journey, and only when the registry title it ran under is the
    title the registry carries now (a re-run of an older definition is refused).
  * Every fold is written into the file as `reruns`: id, source file, when it ran, the verdict before and after, and
    the reason given on the command line. A fold cannot be silent.
  * The rollups (summary live/applicable/live_pct, per_page, per_lens) are recomputed with the runner's own formulas.
    Findings are left as the sweep found them: an isolated run re-audits the same page, and the sweep already holds
    that page's findings.

USAGE
  python tools/fold_journey_rerun.py LA7 --reason "journey scrolled a fixed 800px; corrected to the page's reveal rule"
  python tools/fold_journey_rerun.py LA7 --dry-run
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "live_page_journeys_results.json"
REGISTRY = ROOT / "tools" / "live_page_journeys.registry.mjs"
LENSES = ["R", "J", "T", "C", "X"]


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _registry_title(jid: str) -> str | None:
    src = REGISTRY.read_text(encoding="utf-8")
    m = re.search(r"id:\s*'" + re.escape(jid) + r"'[^\n]*\n\s*title:\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')", src)
    return json.loads(m.group(1)) if m and m.group(1).startswith('"') else (m.group(1)[1:-1] if m else None)


def _pct(n: int, d: int) -> float:
    return round(1000 * n / d) / 10 if d else 0


def _rollups(out: dict) -> None:
    per_page, n_app, n_live, n_ext = {}, 0, 0, 0
    for j in out["journeys"]:
        p = per_page.setdefault(j["page"], {"page": j["page"], "live": 0, "applicable": 0, "external": 0})
        if j.get("external"):
            n_ext += 1
            p["external"] += 1
        else:
            n_app += 1
            p["applicable"] += 1
            if j.get("live"):
                n_live += 1
                p["live"] += 1
    out["summary"].update({"journeys_total": len(out["journeys"]), "applicable": n_app, "live": n_live,
                           "external": n_ext, "live_pct": _pct(n_live, n_app)})
    out["per_page"] = [{**p, "live_pct": _pct(p["live"], p["applicable"])} for p in per_page.values()]
    out["per_lens"] = {}
    for lens in LENSES:
        appl = [j for j in out["journeys"] if not j.get("external") and j["verdict"].get(lens) is not None]
        passed = [j for j in appl if j["verdict"].get(lens) is True]
        out["per_lens"][lens] = {"applicable": len(appl), "pass": len(passed), "pct": _pct(len(passed), len(appl))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--reason", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not a.reason.strip():
        print("REFUSED: a fold needs --reason (it is written into the results file).")
        return 2
    full = json.loads(FULL.read_text(encoding="utf-8"))
    swept = _ts(full["ran"])
    folds = []
    for jid in a.ids:
        src = ROOT / f"live_page_journeys_results.journey-{jid}.json"
        if not src.exists():
            print(f"REFUSED {jid}: no isolated run at {src.name} (run: node tools/live_page_journeys.mjs --journey {jid})")
            return 2
        iso = json.loads(src.read_text(encoding="utf-8"))
        recs = [j for j in iso.get("journeys", []) if j["id"] == jid]
        if len(iso.get("journeys", [])) != 1 or len(recs) != 1:
            print(f"REFUSED {jid}: {src.name} did not walk exactly that one journey")
            return 2
        if _ts(iso["ran"]) <= swept:
            print(f"REFUSED {jid}: the isolated run ({iso['ran']}) is not newer than the sweep ({full['ran']})")
            return 2
        if iso.get("degraded"):
            print(f"REFUSED {jid}: the isolated run was degraded {iso['degraded']}")
            return 2
        new = recs[0]
        title = _registry_title(jid)
        if title is None or new["title"] != title:
            print(f"REFUSED {jid}: it ran under a title that is not the registry's current one")
            return 2
        idx = [i for i, j in enumerate(full["journeys"]) if j["id"] == jid]
        if len(idx) != 1:
            print(f"REFUSED {jid}: the sweep holds {len(idx)} records for it")
            return 2
        old = full["journeys"][idx[0]]
        folds.append({"id": jid, "from": src.name, "ran": iso["ran"], "was_live": bool(old.get("live")),
                      "now_live": bool(new.get("live")), "reason": a.reason.strip()})
        full["journeys"][idx[0]] = new
        print(f"{jid}: {'LIVE' if old.get('live') else 'gap'} -> {'LIVE' if new.get('live') else 'gap'}  (isolated run {iso['ran']})")
    before = dict(full["summary"])
    _rollups(full)
    full["reruns"] = [r for r in full.get("reruns", []) if r["id"] not in {f["id"] for f in folds}] + folds
    print(f"sweep {full['ran']}: live {before['live']}/{before['applicable']} = {before['live_pct']}%  ->  "
          f"{full['summary']['live']}/{full['summary']['applicable']} = {full['summary']['live_pct']}%")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    FULL.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {FULL.name} (reruns recorded: {', '.join(f['id'] for f in full['reruns'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
