"""
db_adoption_census.py — Layer D (Database) adoption census, D-P0.
================================================================================
The Layer-D instantiation of the P0 template (FULLSTACK_COMPONENT_LIBRARY §1).
A Database 'component' is a canonical PATTERN; adoption is measured over the
substrate's live-DB-derived chunks (built by tools/build_substrate.py from
pg_policies/pg_trigger/pg_get_viewdef introspection, freshness-gated), so this
census measures the REAL database one derivation step removed — rerun
build_substrate.py first if the DB changed.

Rows (db_component_registry.json):
  D1 RLS enabled on tenant tables      need = has hive_id        adopt = RLS enabled True
  D2 hive-membership scoping policy    need = D1 adopters        adopt = policies reference hive_members
  D3 auth_uid ownership policy         need = has auth_uid col   adopt = policies reference auth_uid = auth.uid()
  D4 security_invoker views            need = every view         adopt = security_invoker: on
  D5 bind_* attribution triggers       census-only               count = chunks mentioning bind_

OUTPUT: db_adoption_baseline.json (floors forward-only) + db_adoption_report.md
USAGE:  python tools/db_adoption_census.py
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
OUT_JSON = ROOT / "db_adoption_baseline.json"
OUT_MD = ROOT / "db_adoption_report.md"


def parse_tables() -> dict:
    tables = {}
    for p in sorted((ROOT / "substrate" / "table-rls").glob("*.md")):
        s = p.read_text(encoding="utf-8", errors="ignore")
        name_m = re.search(r"## table-rls · `(\w+)`", s)
        if not name_m:
            continue
        pol_i = s.find("Policies:")
        tables[name_m.group(1)] = {
            "rls": bool(re.search(r"RLS enabled: \*\*True\*\*", s)),
            "hive_id": "has hive_id: True" in s,
            "auth_uid_col": "has auth_uid: True" in s,
            "policies": s[pol_i:] if pol_i >= 0 else "",
            "bind": "bind_" in s,
            # The substrate's own rules-engine verdict — the canonical scoping analyzer
            # (knows the user_hive_ids()/auth_worker_names() helper-fn idiom). REUSED for
            # D2 instead of re-deriving policy shapes here (a literal 'hive_members' grep
            # false-gapped 30 correctly-scoped tables on first run).
            "verdict_scoped": bool(re.search(r"\*\*Verdict:\*\* SCOPED", s)),
        }
    return tables


def parse_views() -> dict:
    views = {}
    for p in sorted((ROOT / "substrate" / "view").glob("*.md")):
        s = p.read_text(encoding="utf-8", errors="ignore")
        name_m = re.search(r"## view · `(\w+)`", s)
        if not name_m:
            continue
        views[name_m.group(1)] = {"invoker_on": bool(re.search(r"security_invoker:\*{0,2}\s*\*{0,2}on", s))}
    return views


def run_census():
    reg = json.loads((ROOT / "db_component_registry.json").read_text(encoding="utf-8"))
    T, V = parse_tables(), parse_views()

    def row(cid, name, satisfies, adopters, need, mode="measured"):
        # registry exempt-with-reason (same mechanism as the F/A censuses): exempt
        # surfaces leave the denominator entirely.
        exempt = set(next((c.get("exempt", []) for c in reg["components"] if c["id"] == cid), []))
        adopters, need = sorted(set(adopters) - exempt), sorted(set(need) - exempt)
        gap = sorted(set(need) - set(adopters))
        pct = round(100 * len(adopters) / len(need)) if need else None
        return {"id": cid, "class": next(c["class"] for c in reg["components"] if c["id"] == cid),
                "name": name, "satisfies": satisfies, "mode": mode,
                "adopters_n": len(adopters), "need_n": len(need), "pct": pct,
                "adopters": adopters, "gap": gap}

    tenant = {t for t, v in T.items() if v["hive_id"]}
    d1_adopt = {t for t in tenant if T[t]["rls"]}
    d2_adopt = {t for t in d1_adopt if T[t]["verdict_scoped"]}
    authuid_tables = {t for t, v in T.items() if v["auth_uid_col"]}
    # a bind_* trigger is the STRONGER pin (server-side, immune to policy drift) — counts as adoption
    d3_adopt = {t for t in authuid_tables
                if re.search(r"auth_uid\s*=\s*auth\.uid\(\)|auth\.uid\(\)\s*=\s*auth_uid", T[t]["policies"]) or T[t]["bind"]}
    d4_adopt = {v for v, x in V.items() if x["invoker_on"]}

    rows = [
        row("D1", "RLS enabled on tenant tables", "tenant isolation floor", d1_adopt, tenant),
        row("D2", "hive-membership scoping policy", "multitenant isolation", d2_adopt, d1_adopt),
        row("D3", "auth_uid ownership policy", "write attribution", d3_adopt, authuid_tables),
        row("D4", "security_invoker on views", "no owner-rights RLS bypass", d4_adopt, set(V)),
    ]
    bind_tables = sorted(t for t, v in T.items() if v["bind"])
    rows.append({"id": "D5", "class": "DT Triggers", "name": "bind_* attribution triggers",
                 "satisfies": "attribution pin", "mode": "census-only",
                 "adopters_n": len(bind_tables), "adopters": bind_tables})
    return rows, len(T), len(V)


def main() -> int:
    rows, n_t, n_v = run_census()
    measured = [r for r in rows if r["mode"] == "measured"]
    prior = {}
    if OUT_JSON.exists():
        try:
            prior = json.loads(OUT_JSON.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            prior = {}
    floors = {r["id"]: max(r["adopters_n"], prior.get(r["id"], 0)) for r in measured}
    OUT_JSON.write_text(json.dumps({
        "_doc": "Layer D adoption baseline. Floors forward-only from any writer (Layer F law). "
                "Source = substrate table-rls/view chunks (rebuild via tools/build_substrate.py).",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tables": n_t, "views": n_v, "rows": rows, "floors": floors,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    L = ["# DB Adoption Report — Layer D (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §1)\n",
         f"> MEASURED {datetime.date.today().isoformat()} over **{n_t}** tables + **{n_v}** views "
         "(substrate live-DB derivation).\n",
         "| ID | Canonical pattern | Adoption | % | Gap (first 8) |", "|---|---|---|---|---|"]
    for r in rows:
        if r["mode"] == "census-only":
            L.append(f"| {r['id']} | {r['name']} | {r['adopters_n']} table(s): {', '.join(r['adopters'][:8])} | n/a | — |")
        else:
            gap_s = ", ".join(r["gap"][:8]) + (" …" if len(r["gap"]) > 8 else "")
            L.append(f"| {r['id']} | {r['name']} | **{r['adopters_n']}/{r['need_n']}** | **{r['pct']}%** | {gap_s or '—'} |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"DB adoption census -- {n_t} tables, {n_v} views")
    for r in rows:
        if r["mode"] == "measured":
            print(f"  {r['id']:4s} {r['name'][:44]:44s} {r['adopters_n']:3d}/{r['need_n']:<3d} {str(r['pct'])+'%':>5s}")
        else:
            print(f"  {r['id']:4s} {r['name'][:44]:44s} {r['adopters_n']:3d} (census)")
    print("  -> db_adoption_baseline.json + db_adoption_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
