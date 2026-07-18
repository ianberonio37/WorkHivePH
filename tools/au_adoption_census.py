"""
au_adoption_census.py — Layer AU (Auth) adoption census, AU-P0.
================================================================================
The Layer-AU instantiation of the P0 template (FULLSTACK_COMPONENT_LIBRARY §1).
Measures the client-side SESSION/IDENTITY floor over the family pages (write-side
attribution is Layer D's D3/D5; entry-point fns are delegated rows).

Rows (au_component_registry.json):
  AU1 restoreIdentityFromSession   need = signed-in pages     adopt = js-call present
  AU2 session-settled reads        need = pages with RLS-gated reads at init
                                   adopt = auth.getUser(/getSession( present
  AU3 login lockout / AU4 reset    delegated (owned by the fns, gated by api-adoption + runbook)
  AU5 role floor                   census-only v1 (server re-check idiom varies; a per-gate
                                   heuristic needs the role-gate map — queued)

need heuristics (∪ adopters, comment-stripped, script/style-scoped — Layer F laws):
  signed-in:  page reads WORKER_NAME/wh_last_worker or calls restoreIdentityFromSession
  gated-read: page issues .from( reads at init AND is signed-in

OUTPUT: au_adoption_baseline.json (floors forward-only) + au_adoption_report.md
USAGE:  python tools/au_adoption_census.py
"""

from __future__ import annotations

import datetime
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from component_adoption_census import strip_comments  # scoped stripper (Layer F law)

REGISTRY = ROOT / "au_component_registry.json"
FAMILY = ROOT / "family_rubric_baseline.json"
OUT_JSON = ROOT / "au_adoption_baseline.json"
OUT_MD = ROOT / "au_adoption_report.md"


def run_census():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fam = json.loads(FAMILY.read_text(encoding="utf-8"))
    pages = sorted(fam["pages"].keys() if isinstance(fam["pages"], dict) else fam["pages"])
    src = {p: strip_comments((ROOT / p).read_text(encoding="utf-8", errors="ignore"))
           for p in pages if (ROOT / p).exists()}

    signed_in = {p for p, s in src.items()
                 if re.search(r"wh_last_worker|WORKER_NAME|restoreIdentityFromSession", s)}
    gated_read = {p for p in signed_in if re.search(r"\.from\(\s*['\"]", src[p])}

    def comp(cid):
        return next(c for c in reg["components"] if c["id"] == cid)

    def row(cid, adopters, need):
        exempt = set(comp(cid).get("exempt", []))
        adopters = sorted((set(adopters) | set()) - exempt)
        need = sorted((set(need) | set(adopters)) - exempt)
        gap = sorted(set(need) - set(adopters))
        pct = round(100 * len(adopters) / len(need)) if need else None
        c = comp(cid)
        return {"id": cid, "class": c["class"], "name": c["name"], "satisfies": c["satisfies"],
                "mode": "measured", "adopters_n": len(adopters), "need_n": len(need), "pct": pct,
                "adopters": adopters, "gap": gap}

    au1 = {p for p, s in src.items() if re.search(r"(?<!function )\brestoreIdentityFromSession\s*\(", s)}
    au2 = {p for p in gated_read if re.search(r"auth\.getUser\(|auth\.getSession\(", src[p])}

    rows = [
        row("AU1", au1, signed_in),
        row("AU2", au2, gated_read),
        {"id": "AU3", "class": comp("AU3")["class"], "name": comp("AU3")["name"],
         "satisfies": comp("AU3")["satisfies"], "mode": "delegated", "gate": "login fn (api-adoption) + mig 20260621000002"},
        {"id": "AU4", "class": comp("AU4")["class"], "name": comp("AU4")["name"],
         "satisfies": comp("AU4")["satisfies"], "mode": "delegated", "gate": "supervisor-reset-password fn (api-adoption + deploy runbook)"},
        {"id": "AU5", "class": comp("AU5")["class"], "name": comp("AU5")["name"],
         "satisfies": comp("AU5")["satisfies"], "mode": "census-only",
         "adopters_n": sum(1 for s in src.values() if "wh_hive_role" in s),
         "note": "per-gate server-recheck heuristic queued (needs the role-gate map)"},
    ]
    return rows, len(src)


def main() -> int:
    rows, n_pages = run_census()
    measured = [r for r in rows if r["mode"] == "measured"]
    prior = {}
    if OUT_JSON.exists():
        try:
            prior = json.loads(OUT_JSON.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            prior = {}
    floors = {r["id"]: max(r["adopters_n"], prior.get(r["id"], 0)) for r in measured}
    OUT_JSON.write_text(json.dumps({
        "_doc": "Layer AU adoption baseline. Floors forward-only from any writer (Layer F law).",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pages": n_pages, "rows": rows, "floors": floors,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    L = ["# AU Adoption Report — Layer AU (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §1)\n",
         f"> MEASURED {datetime.date.today().isoformat()} over **{n_pages}** family pages.\n",
         "| ID | Canonical primitive | Adoption | % | Gap (first 8) |", "|---|---|---|---|---|"]
    for r in rows:
        if r["mode"] == "measured":
            gap_s = ", ".join(g.replace(".html", "") for g in r["gap"][:8]) + (" …" if len(r["gap"]) > 8 else "")
            L.append(f"| {r['id']} | {r['name']} | **{r['adopters_n']}/{r['need_n']}** | **{r['pct']}%** | {gap_s or '—'} |")
        elif r["mode"] == "delegated":
            L.append(f"| {r['id']} | {r['name']} | → `{r['gate']}` | — | — |")
        else:
            L.append(f"| {r['id']} | {r['name']} | {r['adopters_n']} page(s) | n/a | {r.get('note','')} |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"AU adoption census -- {n_pages} family pages")
    for r in measured:
        print(f"  {r['id']:4s} {r['name'][:46]:46s} {r['adopters_n']:3d}/{r['need_n']:<3d} {str(r['pct'])+'%':>5s}")
    print("  -> au_adoption_baseline.json + au_adoption_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
