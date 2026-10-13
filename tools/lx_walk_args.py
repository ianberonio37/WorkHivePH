"""lx_walk_args.py - write .tmp/lx_args.json for ONE BATCH of LAYER-UX browser rows (LXP / LXC), the cells
tools/lx_walk.js walks through the Playwright MCP.

An LX row is (persona, layer, page): "the <layer> ask, answered from <page> itself at phone-390 AND desktop-1280, as
<persona>". Several layers of one (persona, page) CELL are answered by ONE walk of that page as that person - the
same arrival, the same settled page - each read through its own lens. So a batch is a list of cells, never of rows.

This file decides, deterministically, what the walk must not improvise:

  1. WHO signs in (the cast), read from the database, never typed:
       supervisor / fleet-supervisor / oversight -> a non-admin active SUPERVISOR of the row's hive (journey.vertical)
       solo-owner                                -> Jun Salvador (tools/seed_solo_personas.py: no hive at all)
       adversary                                 -> a non-admin WORKER of ANOTHER hive (he reads the page as himself)
       every other persona                       -> a non-admin WORKER of the row's hive (a hive with no worker
                                                    account - Ramos Jeepney Line - is walked by its supervisor, the
                                                    rule the CA and nav-hub walks already follow)
     A platform admin is never cast: an admin sees surfaces nobody else does, so his page is not the persona's page.
  2. WHICH rows each cell answers (its open layers) and the ROUTE it arrives by (the row's own `pages`).
  3. The model functions the walk must STUB (no live or paid model call, ever) and the functions that SEND (email,
     push, notify) which are answered by the stub too - a walk never sends anything to anyone.

  python tools/lx_walk_args.py --list                     -> the open cells, grouped, nothing written
  python tools/lx_walk_args.py --cells 6 [--persona p] [--page x.html] [--layers CA,C]  -> writes the next batch
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB = "supabase_db_workhive"
PASSWORD = "test1234"
SOLO = {"user": "junvanowner", "name": "Jun Salvador"}
# RL joined 2026-10-12: tools/prove_consumption_bound.py reads a page's SOURCE, and on four pages it could not resolve
# the cap's table (a shared script, an aliased read) - so the walk reads each request's limit and returned rows live
BROWSER_LAYERS = ("CA", "C", "LB", "AV", "CI", "L", "A", "D", "RL")
SUP_PERSONAS = ("supervisor", "fleet-supervisor", "oversight")
OUT = ROOT / ".tmp" / "lx_args.json"


def psql(sql: str) -> list[str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return [ln for ln in (r.stdout or "").strip().splitlines() if ln.strip()]


def roster() -> dict:
    """{hive name: {"worker": [...], "supervisor": [...]}} of NON-ADMIN active members with an account, each as
    (worker_name, login local part, hive id, how many active hives the person holds)."""
    admins = set(psql("select worker_name from marketplace_platform_admins"))
    out: dict = defaultdict(lambda: {"worker": [], "supervisor": []})
    rows = psql("select h.name||'|'||m.worker_name||'|'||m.role||'|'||split_part(u.email,'@',1)||'|'||h.id||'|'||"
                "(select count(*) from hive_members x where x.auth_uid = m.auth_uid and x.status = 'active') "
                "from hive_members m join hives h on h.id = m.hive_id join auth.users u on u.id = m.auth_uid "
                "where m.status = 'active' order by h.name, m.worker_name")
    for line in rows:
        hive, name, role, user, hid, nh = line.split("|")
        if name in admins:
            continue
        out[hive]["supervisor" if role == "supervisor" else "worker"].append((name, user, hid, int(nh)))
    for h in out.values():                     # single-hive people first: the page shows ONE hive's data
        h["worker"].sort(key=lambda x: (x[3], x[0]))
        h["supervisor"].sort(key=lambda x: (x[3], x[0]))
    return out


def cast_for(persona: str, vertical: str, ros: dict) -> dict | None:
    if persona == "solo-owner":
        return {"castName": SOLO["name"], "user": SOLO["user"], "hiveId": None, "castRole": "solo (no hive)"}
    if persona == "adversary":
        others = sorted(h for h in ros if h != vertical and ros[h]["worker"])
        if not others:
            return None
        n, u, hid, _ = ros[others[0]]["worker"][0]
        return {"castName": n, "user": u, "hiveId": hid, "castRole": f"worker of {others[0]} (another hive)"}
    want = "supervisor" if persona in SUP_PERSONAS else "worker"
    pool = ros.get(vertical, {}).get(want) or ros.get(vertical, {}).get("supervisor" if want == "worker" else "worker")
    if not pool:
        return None
    n, u, hid, _ = pool[0]
    role = want if ros.get(vertical, {}).get(want) else ("supervisor (the hive has no worker account)" if want == "worker" else "worker")
    return {"castName": n, "user": u, "hiveId": hid, "castRole": f"{role} of {vertical}"}


def _lit(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def arrival(page: str, vertical: str, cast: dict) -> str:
    """The query string the page's OWN inbound link composes, on a value read from the database - or "".

    ★A PAGE ABOUT ONE THING IS OPENED ON ONE THING (2026-10-09, UFAI LXP378/415/451). marketplace-seller-profile.html
    reads ?worker= and project-report.html reads ?project_id=; opened bare, each shows its "No ... specified" screen,
    and every layer of every row was judged on that screen - 309 characters - instead of a profile or a report. Nobody
    arrives bare: the marketplace composes ?worker= on every seller link, and Project Manager composes ?project_id=
    on "Print report". So the walk arrives the same way.
      seller profile -> the seller with the most live listings who is not the cast (a visitor reads someone else's)
      project report -> the most recently updated project of the ROW's hive (journey.vertical): the cast's own hive
                        for every persona except the adversary, for whom it is a foreign link - the boundary he tests
    """
    if page == "marketplace-seller-profile.html":
        rows = psql("select worker_name from v_marketplace_sellers_public where active_listings_count > 0 "
                    f"and worker_name <> {_lit(cast.get('castName') or '')} order by active_listings_count desc, worker_name limit 1")
        return ("?worker=" + quote(rows[0])) if rows else ""
    if page == "project-report.html" and vertical:
        rows = psql("select p.project_id from v_project_truth p join hives h on h.id = p.hive_id "
                    f"where h.name = {_lit(vertical)} order by p.updated_at desc, p.project_id limit 1")
        return ("?project_id=" + rows[0]) if rows else ""
    return ""


def open_rows() -> list[dict]:
    import live_walk_manifest as lm
    reg = {t["id"]: t for t in json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))["trajectories"]}
    out = []
    for r in lm.build()["rows"]:
        if not str(r["wave"]).startswith(("LXP-", "LXC-")) or lm.row_closed(r):
            continue
        t = reg[r["id"]]
        lx = t.get("lx") or {}
        if lx.get("layer") not in BROWSER_LAYERS:
            continue
        out.append(t)
    return out


def model_fns() -> list[str]:
    from seed_expansion_wave4 import LM_MODEL_FNS
    return sorted(LM_MODEL_FNS | {"ai-gateway", "analytics-orchestrator", "equipment-label-ocr"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--cells", type=int, default=6)
    ap.add_argument("--persona", default="")
    ap.add_argument("--page", default="")
    ap.add_argument("--layers", default="")
    ap.add_argument("--skip", default="", help="comma list of persona:page cells to leave out (walked already)")
    ap.add_argument("--rewalk", action="store_true", help="also re-walk rows walked red since their page last changed")
    a = ap.parse_args()

    rows = open_rows()
    # ★A ROW ALREADY WALKED RED SINCE ITS PAGE LAST CHANGED IS NOT RE-WALKED (it would read the same): its receipt
    # names the finding, and the page has to change before another walk can say anything new. --rewalk overrides.
    if not a.rewalk:
        def _red_since_page(t):
            rp = ROOT / ".tmp" / "mcp_walks" / f"{t['id']}.json"
            pg = ROOT / t["lx"]["page"]
            if not rp.exists() or not pg.exists() or rp.stat().st_mtime < pg.stat().st_mtime:
                return False
            try:
                res = json.loads(rp.read_text(encoding="utf-8"))["results"][0]
            except Exception:
                return False
            return not res.get("ok") and "lx_walk" in (res.get("note") or "") + json.dumps(res.get("w4") or {})
        held = [t["id"] for t in rows if _red_since_page(t)]
        rows = [t for t in rows if t["id"] not in set(held)]
        if held and not a.list:
            print(f"  ({len(held)} row(s) already walked red since their page last changed - not re-walked)")
    if a.layers:
        keep = set(a.layers.split(","))
        rows = [t for t in rows if t["lx"]["layer"] in keep]
    cells: dict = defaultdict(list)
    for t in rows:
        cells[(t["lx"]["persona"], t["lx"]["page"], (t.get("journey") or {}).get("vertical"))].append(t)
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    # never-walked rows first: a cell whose rows all carry a receipt already (walked red, page since edited by someone
    # else) is a RE-walk, and re-walks wait until every row has had its first reading
    def _walked(t):
        return (ROOT / ".tmp" / "mcp_walks" / f"{t['id']}.json").exists()
    keys = sorted(cells, key=lambda k: (all(_walked(t) for t in cells[k]), k[1], k[0], k[2] or ""))
    keys = [k for k in keys if (not a.persona or k[0] == a.persona) and (not a.page or k[1] == a.page)
            and f"{k[0]}:{k[1]}" not in skip]
    if a.list:
        print(f"{len(rows)} open LX browser row(s) in {len(keys)} cell(s)")
        for k in keys[:400]:
            print(f"  {k[1]:32} {k[0]:16} {k[2] or '-':28} {','.join(sorted(t['lx']['layer'] for t in cells[k]))}")
        return 0

    ros = roster()
    batch, unc = [], []
    for k in keys:
        if len(batch) >= a.cells:
            break
        persona, page, vertical = k
        c = cast_for(persona, vertical or "", ros)
        if not c:
            unc.append(k)
            continue
        ts = cells[k]
        # the route the row names, ending on its subject (every row of a cell shares the page; take the longest route)
        path = max((t.get("pages") or [page] for t in ts), key=len)
        if path[-1] != page:
            path = list(path) + [page]
        q = arrival(page, vertical or "", c)
        batch.append({"persona": persona, "page": page, "vertical": vertical, "path": path,
                      **({"arrive": {page: q}} if q else {}),
                      "rows": [{"id": t["id"], "layer": t["lx"]["layer"]} for t in sorted(ts, key=lambda x: x["id"])],
                      **c, "pass": PASSWORD})
    args = {"batch": batch, "origin": "http://localhost:5000/workhive", "api": "http://127.0.0.1:54321",
            "modelFns": model_fns(),
            "viewports": [{"name": "phone-390", "width": 390, "height": 844, "mobile": True},
                          {"name": "desktop-1280", "width": 1280, "height": 800, "mobile": False}]}
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(json.dumps(args, ensure_ascii=False, indent=1))
    os.replace(tmp, OUT)
    print(f"wrote {OUT.relative_to(ROOT)} - {len(batch)} cell(s), {sum(len(c['rows']) for c in batch)} row(s)")
    for c in batch:
        print(f"  {c['page']:30} {c['persona']:15} as {c['castName']} ({c['castRole']}) - "
              f"{','.join(r['layer'] for r in c['rows'])}" + (f"  opened as {c['page']}{c['arrive'][c['page']]}" if c.get("arrive") else ""))
    for k in unc:
        print(f"  NO CAST for {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
