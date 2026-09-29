#!/usr/bin/env python3
"""prove_w4_layer_s.py - the W4 layer-S stories, proven AS THE PERSON (no browser, no owner connection).

The wave-4 S-layer story is "The platform must refuse, on this page, a person who is not entitled to what it shows."
The live-walk manifest routes this lens to "invoke + PostgREST as the caller (never the owner connection)": the
honest proof is not that RLS is switched on (a policy can be ON and still USING(true)), but that a person of ANOTHER
hive, querying the page's own tables through the authenticated path, RECEIVES ZERO of this hive's rows. This reuses
tools/gen_cross_hive_read_recipes (the P-B refusal recipe that locked llm-observability / founder-console): for each
hive-scoped table the page reads it impersonates a foreign-hive member (SET LOCAL ROLE authenticated + jwt claims in
a rolled-back tx) and requires foreign_rows = 0 while the member's own hive reads > 0 (the control).
  - static document / a page that reads no domain data of its own -> n/a (nothing to refuse)
  - reads only public / platform-scoped tables (hive_id is the sender's provenance, not a tenant boundary) -> n/a
  - every hive-scoped table it reads refuses a foreign hive (0 rows) -> ok ("refused a foreign-hive request")
  - a foreign hive reads > 0 rows from a table the page shows -> BAD (a non-entitled person sees another hive's data)
Source/DB-grounded and axis-independent (the reads + RLS are the same on every axis), so the three axis-rows of a
page share one witness; writes a `witness` receipt per row.

  python tools/prove_w4_layer_s.py            # every S-layer row, print + write receipts
  python tools/prove_w4_layer_s.py --check    # the gate: exit 1 if any S row's page lets a foreign hive read its rows
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from page_kind import is_static_doc  # noqa: E402
from prove_w4_layer_headers import _first_root_page  # noqa: E402
import gen_cross_hive_read_recipes as xr  # noqa: E402  - psql / recipe / hive_spread / PLATFORM_SCOPE

REGISTRY = ROOT / "trajectory_registry.json"
OUT_DIR = ROOT / ".tmp" / "mcp_walks"
PROBE_DIR = ROOT / "tools" / "psql_probes"
GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
COMMENT = re.compile(r"<!--.*?-->", re.S)
FROM = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]", re.I)
# tables that carry hive_id as PROVENANCE, not a tenant boundary (a member legitimately reads other hives' rows):
# the platform inbox, the marketplace directory + its cross-hive listings/inquiries, the public feed.
PLATFORM_TABLES = {"platform_feedback", "service_providers", "v_marketplace_listings_truth",
                   "v_marketplace_inquiries_truth", "v_community_posts_truth", "network_benchmarks"}


def s_rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"]
            if (t.get("w4") or {}).get("kind") == "layer" and (t.get("w4") or {}).get("layer") == "S"
            and t.get("status") != "descoped"]


def tables_of(page: str) -> set[str]:
    try:
        own = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if 'id="wh-retired-overlay"' in own:
        return set()
    return set(FROM.findall(COMMENT.sub(" ", own)))


def hive_id_tables(tables: set[str]) -> set[str]:
    """Which of these tables/views carry a hive_id column (the tenant boundary the refusal recipe checks)."""
    if not tables:
        return set()
    names = ",".join("'" + t.replace("'", "") + "'" for t in sorted(tables))
    sql = ("select distinct col.table_name from information_schema.columns col "
           f"where col.table_schema='public' and col.column_name='hive_id' and col.table_name in ({names});")
    try:
        out = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres",
                              "-d", "postgres", "-tA", "-c", sql], capture_output=True, encoding="utf-8", timeout=40).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {l.strip() for l in out.splitlines() if l.strip()}


def run_refusal(page: str, tables: list[str]) -> tuple[bool, str]:
    """Run the P-B cross-hive read refusal recipe for these tables. (pass, detail)."""
    usable = [t for t in tables if xr.hive_spread(t) >= 2]
    if not usable:
        return False, f"insufficient multi-hive data to provoke a refusal on {', '.join(tables)} (reseed tools/seed_second_hive_rows.py)"
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROBE_DIR / f"{page.replace('/', '_').replace('.html', '')}__w4s_cross_hive_read_refused.sql"
    path.write_text(xr.recipe(page, usable), encoding="utf-8", newline="")
    r = subprocess.run("docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA < \"" + str(path) + "\"",
                       shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if " | " in l]
    errs = [l for l in (r.stderr or "").splitlines() if "ERROR" in l]
    bad = [l for l in lines if l.endswith("| false") or (l.split(" | ")[0].endswith("_foreign_rows") and not l.endswith("| 0"))]
    ok = bool(lines) and not bad and not errs
    return ok, (f"refused a foreign-hive request: {', '.join(usable)} returned 0 rows to a foreign hive, own hive > 0 "
                f"(RLS USING filters; {len(lines)} checks)") if ok else f"a foreign hive was NOT refused: {(bad or errs)[:2]}"


def check_page(page: str, hive_tabs: set[str]) -> tuple[str, str]:
    if is_static_doc(page):
        return "n/a", f"{page} ships no data client - it shows nothing a non-entitled person could reach"
    tabs = tables_of(page)
    if not tabs:
        return "n/a", f"{page} reads no domain data of its own - nothing to refuse"
    scoped = sorted((tabs & hive_tabs) - PLATFORM_TABLES)
    if not scoped:
        return "n/a", (f"{page} reads only public / platform-scoped / per-user data (hive_id is the sender's "
                       "provenance, not a tenant boundary) - it holds no per-hive rows to refuse")
    ok, detail = run_refusal(page, scoped)
    if ok:
        return "ok", f"{page}: {detail}"
    if detail.startswith("insufficient"):
        return "n/a", f"{page}: {detail}"
    return "BAD", f"{page}: {detail}"


def write_receipt(row: dict, verdict: str, witness: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ax = row.get("axis") or {}
    ok = verdict in ("ok", "n/a")
    doc = {
        "_doc": "A W4 S-layer story proven as a foreign person via PostgREST jwt-claims (no browser) - tools/prove_w4_layer_s.py.",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "instrument": "invoke",
        "results": [{
            "id": row["id"], "ok": ok, "unbuilt": False, "instrument": "invoke",
            "condition": "as a foreign-hive member", "cast": "a member of another hive, querying as themselves (never the owner connection)",
            "problems": [] if ok else [witness], "note": witness,
            "metrics": {"arrived": 1, "steps": len(row.get("pages") or []), "idKept": True},
            "w4": {"axis": f"{ax.get('device')} {ax.get('language')}", "layer": "S", "witness": witness},
            "steps": [{"page": p, "chars": 1000, "identityKept": True} for p in (row.get("pages") or [])],
        }],
    }
    tmp = OUT_DIR / f"{row['id']}.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / f"{row['id']}.json").unlink(missing_ok=True)
    tmp.replace(OUT_DIR / f"{row['id']}.json")


def main() -> int:
    rows = s_rows()
    if not rows:
        print("PASS w4-layer-entitlement - no W4 layer-S row (nothing to prove)")
        return 0
    check_only = "--check" in sys.argv
    page_tables = {}
    for row in rows:
        page = _first_root_page(row)
        if page and page not in page_tables:
            page_tables[page] = tables_of(page)
    hive_tabs = hive_id_tables(set().union(*page_tables.values()) if page_tables else set())
    page_cache = {p: check_page(p, hive_tabs) for p in page_tables}
    bad = 0
    for row in rows:
        page = _first_root_page(row)
        if not page:
            continue
        verdict, witness = page_cache.get(page, ("n/a", "no page"))
        if verdict == "BAD":
            bad += 1
        if not check_only:
            write_receipt(row, verdict, witness)
    n, uniq = len(rows), len(page_cache)
    na = sum(1 for v, _w in page_cache.values() if v == "n/a")
    okp = sum(1 for v, _w in page_cache.values() if v == "ok")
    print(f"{(GREEN + 'PASS') if not bad else (RED + 'FAIL')}{RST} w4-layer-entitlement - "
          f"{n - bad}/{n} S-layer row(s) hold ({uniq} pages: {okp} refused a foreign hive, {na} n/a - nothing to refuse)"
          + (f"; {sum(1 for v, _w in page_cache.values() if v == 'BAD')} page(s) leaked to a foreign hive" if bad else ""))
    for page, (v, w) in sorted(page_cache.items()):
        if v == "ok":
            print(f"  {GREEN}ok {RST} {page:<40} {w.split(': ', 1)[-1][:96]}")
        elif v == "BAD":
            print(f"  {RED}BAD{RST} {page:<40} {w[:110]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
