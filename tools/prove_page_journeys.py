#!/usr/bin/env python3
"""prove_page_journeys.py - SL sub-layer CI2 (2026-10-15): "The platform must keep a live journey on this page that
passes in Chromium and in WebKit."

KEPT means registered and walked: each reading is the record of the instrument that walks it, never re-derived.
  public pages   .tmp/public_journeys_results.json - tools/prove_public_journeys.mjs: signed out, the reader's job
                 (arrive and read, a calculator's worked example, a FAQ answer, the onward link clicked to a live
                 surface), per engine
  app pages      live_page_journeys_results.json (Chromium) and live_page_journeys_results.webkit.json (WebKit) -
                 tools/live_page_journeys.mjs's registered jobs-to-be-done, the same registry in both engines (`--engine
                 webkit`); a page needs at least one LIVE journey (every applicable lens passed, not an external
                 ceiling) in each engine
A page with no registered journey is open: the next unit is to author one, not to call it covered.
TEETH (in memory): a page whose WebKit walk is taken away, and a page whose only journey turns gap, must each read open.

  python tools/prove_page_journeys.py [--page a.html,...] [--json .tmp/page_journeys_results.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ("chromium", "webkit")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load() -> dict:
    pub = _load(ROOT / ".tmp" / "public_journeys_results.json")
    boards = {"chromium": _load(ROOT / "live_page_journeys_results.json"),
              "webkit": _load(ROOT / "live_page_journeys_results.webkit.json")}
    public = {}
    for r in pub.get("results") or []:
        public.setdefault(r["page"], {})[r["engine"]] = r
    app = {}
    for eng, b in boards.items():
        for j in b.get("journeys") or []:
            app.setdefault(j["page"], {}).setdefault(eng, []).append(j)
    return {"public": public, "app": app, "runs": {"public": pub.get("generated"),
            **{f"journeys-{e}": (boards[e] or {}).get("ran") for e in ENGINES}}}


def check(page: str, page_class: str, R: dict) -> dict:
    per = {}
    for eng in ENGINES:
        problems, how = [], ""
        if page_class == "public":
            r = (R["public"].get(page) or {}).get(eng)
            if not r:
                problems.append(f"{eng}: not walked by prove_public_journeys")
            elif not r.get("ok"):
                problems.extend(f"{eng}: {p}" for p in r.get("problems") or [])
            else:
                g = (r.get("steps") or {}).get("go_on") or {}
                how = f"arrived, read{', worked example' if 'example' in r['steps'] else ''}{', FAQ answered' if 'answer' in r['steps'] else ''}, went on to {g.get('to')}"
        else:
            js = (R["app"].get(page) or {}).get(eng) or []
            live = [j for j in js if j.get("live") and not j.get("external")]
            if not js:
                problems.append(f"{eng}: no registered journey walked on this page")
            elif not live:
                problems.append(f"{eng}: {len(js)} journey(s) walked, none live ({', '.join(j['id'] for j in js[:4])})")
            else:
                how = f"{len(live)}/{len(js)} journey(s) live ({', '.join(j['id'] for j in live[:4])})"
        per[eng] = {"problems": problems, "how": how}
    problems = [p for e in ENGINES for p in per[e]["problems"]]
    return {"page": page, "per": per, "problems": problems, "ok": not problems}


def teeth(R: dict, pub_sample: str | None, app_sample: str | None) -> dict:
    out = {}
    if pub_sample:
        R1 = dict(R, public={**R["public"], pub_sample: {k: v for k, v in R["public"][pub_sample].items() if k != "webkit"}})
        out["webkit_removed_caught"] = not check(pub_sample, "public", R1)["ok"]
    if app_sample:
        gone = {e: [dict(j, live=False) for j in js] for e, js in R["app"][app_sample].items()}
        R2 = dict(R, app={**R["app"], app_sample: gone})
        out["gap_caught"] = not check(app_sample, "production", R2)["ok"]
    out["bit"] = bool(out) and all(out.values())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "page_journeys_results.json"))
    a = ap.parse_args()
    R = load()
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    rows = {t["sl"]["page"]: t for t in reg["trajectories"]
            if (t.get("sl") or {}).get("sublayer") == "CI2" and t.get("status") != "descoped"}
    pages = a.page.split(",") if a.page else sorted(rows)
    results, open_ = [], 0
    for page in pages:
        pc = rows[page]["sl"].get("page_class") if page in rows else "production"
        r = check(page, pc, R)
        for eng in ENGINES:   # one reading per engine, as the banker reads them
            results.append({"page": page, "engine": eng, "condition": "journey", "page_class": pc, "cast": (rows.get(page) or {}).get("persona"),
                            "how": r["per"][eng]["how"], "problems": r["per"][eng]["problems"], "ok": not r["per"][eng]["problems"]})
        open_ += 0 if r["ok"] else 1
        print(f"  {'ok  ' if r['ok'] else 'open'} {page:<60} " + ("; ".join(r["problems"])[:170] if r["problems"] else r["per"]["webkit"]["how"][:120]))
    pub_s = next((p for p in pages if p in R["public"] and len(R["public"][p]) == 2), None)
    app_s = next((p for p in pages if p in R["app"]), None)
    t = teeth(R, pub_s, app_s)
    print(f"\n  teeth - {pub_s}'s WebKit walk taken away, and {app_s}'s journeys turned gap: {'both CAUGHT' if t['bit'] else 'NOT CAUGHT'} ({t})")
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayer": "CI2", "pages": len(pages),
                               "open": open_, "runs": R["runs"], "teeth": t, "results": results}, indent=1), encoding="utf-8")
    failed = 0 if t["bit"] else 1
    print(f"\n{'FAIL' if failed else 'PASS'} page-journeys - {len(pages) - open_}/{len(pages)} page(s) keep a live journey in Chromium and "
          f"WebKit ({open_} open) -> {out}")
    return failed


if __name__ == "__main__":
    sys.exit(main())
