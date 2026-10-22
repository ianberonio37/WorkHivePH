#!/usr/bin/env python3
"""build_console_reads.py - the operator console's live numbers, generated from the dashboards themselves (OPC, 2026-10-22).

The operator console (founder-console.html, un-retired as the ONE console - Ian, 2026-10-14) shows each Grafana panel as
a live number in the page, with a link to its dashboard. A number the console computes with its own SQL would drift from
the dashboard it claims to mirror the first time either changed. So the console's reads are GENERATED from the six
provisioned dashboards (infra/mcp/grafana/provisioning/dashboards/*.json): one admin-only read per dashboard that reads
the Supabase database, running each panel's own SQL with Grafana's macros translated:

    $__timeFilter(col)          ->  (col >= p_from and col < p_to)
    $__timeGroup(col, '1d')     ->  date_trunc('day', col)        ('1h' -> 'hour')
    '$hive'                     ->  coalesce(p_hive::text, '%')   (the dashboard's "all hives" default)

Each read is SECURITY DEFINER, asks is_platform_admin() first (42501 for anyone else), and returns one jsonb object keyed
by panel: a stat panel's value, or a table/series panel's rows. Every panel runs in its own exception block, so one
panel that cannot be read (pg_stat_statements not installed) says so in its own key and the rest still arrive. The
dashboard that reads GlitchTip's own database (workhive-errors) gets the same read through a bridge: its panels run
there over dblink as the read-only grafana_reader, with the connection string in Vault ('glitchtip_read_url'), and a
database without that secret answers {"connected": false} with a sentence instead of numbers.

    python tools/build_console_reads.py --out <file.sql>     write the migration
    python tools/build_console_reads.py --check <file.sql>   exit 1 when the file no longer matches the dashboards
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "infra" / "mcp" / "grafana" / "provisioning" / "dashboards"
SUPABASE_DS = "supabase_local"
# GlitchTip keeps its own Postgres. Its dashboard is read through a bridge (OPC, 2026-10-22): the same admin-only read,
# whose panels run in GlitchTip's database over dblink as the read-only grafana_reader. The connection string is a
# Vault secret ('glitchtip_read_url'), never this public repository; a database without one says it has no tracker.
GLITCHTIP_DS = "glitchtip_local"
VAULT_SECRET = "glitchtip_read_url"


def _fn_name(uid: str) -> str:
    return "console_read_" + re.sub(r"[^a-z0-9]+", "_", uid.replace("workhive-", "")).strip("_")


def _bridge(uid: str, d: dict, panels: list) -> str:
    """the read for a GlitchTip dashboard: each panel's SQL runs remotely and comes back as one JSON text column, so
    dblink needs no column list per panel"""
    fn, body, seen = _fn_name(uid), [], set()
    for p in panels:
        key = panel_key(p.get("title"))
        while key in seen:
            key += "_2"
        seen.add(key)
        for i, t in enumerate(p.get("targets") or []):
            sql = translate(t.get("rawSql") or "")
            if not sql:
                continue
            if "$q$" in sql:
                raise ValueError(f"{uid}: a panel's SQL holds the $q$ quote this bridge wraps it in")
            k = key if i == 0 else f"{key}_{i + 1}"
            scalar = p.get("type") == "stat" and re.search(r"\bas value\b", sql, re.I) and not re.search(r"\bgroup by\b", sql, re.I)
            remote = (f"select to_json((select value from ({sql}) q limit 1))::text" if scalar
                      else f"select coalesce(json_agg(q), '[]'::json)::text from ({sql}) q")
            body.append(
                f"  begin\n"
                f"    r := r || jsonb_build_object('{k}', (select t.j::jsonb from extensions.dblink(conn, $q${remote}$q$) as t(j text)));\n"
                f"  exception when others then\n"
                f"    r := r || jsonb_build_object('{k}', jsonb_build_object('error', sqlerrm));\n"
                f"  end;")
    return (
        f"-- {uid}: {len(panels)} panel(s), \"{d.get('title', uid)}\" - GlitchTip's own database, through the bridge\n"
        f"create extension if not exists dblink with schema extensions;\n"
        f"create or replace function public.{fn}(p_from timestamptz default now() - interval '30 days',\n"
        f"  p_to timestamptz default now(), p_hive uuid default null)\n"
        f"returns jsonb language plpgsql stable security definer set search_path = public, extensions, pg_temp as $fn$\n"
        f"declare\n"
        f"  r jsonb := jsonb_build_object('dashboard', '{uid}', 'from', p_from, 'to', p_to, 'read_at', now());\n"
        f"  conn text;\n"
        f"begin\n"
        f"  if not public.is_platform_admin() then\n"
        f"    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';\n"
        f"  end if;\n"
        f"  select decrypted_secret into conn from vault.decrypted_secrets where name = '{VAULT_SECRET}';\n"
        f"  if conn is null then\n"
        f"    return r || jsonb_build_object('connected', false, 'reason',\n"
        f"      'No error tracker is connected to this database, so its numbers cannot be read here.');\n"
        f"  end if;\n"
        f"  begin\n"
        f"    perform 1 from extensions.dblink(conn, 'select 1') as t(x int);\n"
        f"  exception when others then\n"
        f"    return r || jsonb_build_object('connected', false, 'reason', 'The error tracker did not answer: ' || sqlerrm);\n"
        f"  end;\n"
        + "\n".join(body) + "\n"
        f"  return r || jsonb_build_object('connected', true);\n"
        f"end $fn$;\n"
        f"revoke all on function public.{fn}(timestamptz, timestamptz, uuid) from public, anon;\n"
        f"grant execute on function public.{fn}(timestamptz, timestamptz, uuid) to authenticated;\n")


def panel_key(title: str) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", (title or "").lower()).strip("_")
    return k[:60] or "panel"


def opc_marker(surface: str, title: str) -> str:
    """the console's mark for a cell, data-opc="<surface>::<slug>": every word of the title kept (the inventory's
    stop-word key folds "Who's using it?" to nothing), so the console page, this manifest and the gate
    (validate_operator_console_covers_surfaces.py) name a cell the same way"""
    return f"{surface}::" + re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")


def translate(sql: str) -> str:
    s = re.sub(r"\$__timeFilter\(\s*([a-zA-Z_.]+)\s*\)", r"(\1 >= p_from and \1 < p_to)", sql)
    unit = {"1d": "day", "1h": "hour", "1m": "minute", "1w": "week"}
    s = re.sub(r"\$__timeGroup\(\s*([a-zA-Z_.]+)\s*,\s*'([0-9]+[a-z])'\s*\)",
               lambda m: f"date_trunc('{unit.get(m.group(2), 'day')}', {m.group(1)})", s)
    s = s.replace("'$hive'", "coalesce(p_hive::text, '%')")
    if "$" in re.sub(r"\$\$", "", s):
        raise ValueError(f"an untranslated Grafana macro is left in: {s[:160]}")
    return s.strip().rstrip(";")


def build() -> str:
    parts = ["-- GENERATED by tools/build_console_reads.py from infra/mcp/grafana/provisioning/dashboards - do not edit by hand;",
             "-- regenerate when a dashboard changes (the check mode fails while this file and the dashboards disagree).", ""]
    for f in sorted(DASH.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        uid = d.get("uid") or f.stem
        panels = [p for p in d.get("panels", []) if p.get("type") != "row"]
        dss = {(p.get("datasource") or {}).get("uid") if isinstance(p.get("datasource"), dict) else None for p in panels}
        if dss == {GLITCHTIP_DS}:
            parts.append(_bridge(uid, d, panels))
            continue
        if dss != {SUPABASE_DS}:
            parts.append(f"-- {uid}: reads {sorted(x for x in dss if x)} - not this database and no bridge, so no read here")
            parts.append("")
            continue
        fn = _fn_name(uid)
        body, seen = [], set()
        for p in panels:
            key = panel_key(p.get("title"))
            while key in seen:
                key += "_2"
            seen.add(key)
            for i, t in enumerate(p.get("targets") or []):
                sql = translate(t.get("rawSql") or "")
                if not sql:
                    continue
                k = key if i == 0 else f"{key}_{i + 1}"
                scalar = p.get("type") == "stat" and re.search(r"\bas value\b", sql, re.I) and not re.search(r"\bgroup by\b", sql, re.I)
                expr = (f"(select value from ({sql}) q limit 1)" if scalar
                        else f"(select coalesce(jsonb_agg(q), '[]'::jsonb) from ({sql}) q)")
                body.append(
                    f"  begin\n"
                    f"    r := r || jsonb_build_object('{k}', {expr});\n"
                    f"  exception when others then\n"
                    f"    r := r || jsonb_build_object('{k}', jsonb_build_object('error', sqlerrm));\n"
                    f"  end;")
        parts.append(f"-- {uid}: {len(panels)} panel(s), \"{d.get('title', uid)}\"")
        parts.append(
            f"create or replace function public.{fn}(p_from timestamptz default now() - interval '30 days',\n"
            f"  p_to timestamptz default now(), p_hive uuid default null)\n"
            f"returns jsonb language plpgsql stable security definer set search_path = public, extensions, pg_temp as $fn$\n"
            f"declare r jsonb := jsonb_build_object('dashboard', '{uid}', 'from', p_from, 'to', p_to, 'read_at', now());\n"
            f"begin\n"
            f"  if not public.is_platform_admin() then\n"
            f"    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';\n"
            f"  end if;\n"
            + "\n".join(body) + "\n"
            f"  return r;\n"
            f"end $fn$;\n"
            f"revoke all on function public.{fn}(timestamptz, timestamptz, uuid) from public, anon;\n"
            f"grant execute on function public.{fn}(timestamptz, timestamptz, uuid) to authenticated;\n")
    return "\n".join(parts) + "\n"


def manifest() -> list[dict]:
    """The console UI's labels, from the same dashboards: each read's panels in dashboard order, with title, type and
    unit, so the page never retypes a panel's name (a retyped label drifts the way a retyped number does).

    Each panel also names its operator-console cell (`opc`, as tools/operator_console_inventory.py keys it), and `home`
    when the inventory folded it into another cell (the console's own Listings queue already IS the founder-ops count
    of drafts; the growth dashboard's New hives is the founder home's): the console draws a cell once."""
    import operator_console_inventory as inv
    folded = {}
    for c in inv.collect():
        for also in c["also_on"]:
            folded[also] = f"{c['surface']} :: {c['panel']}"
    out = []
    for f in sorted(DASH.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        uid = d.get("uid") or f.stem
        panels = [p for p in d.get("panels", []) if p.get("type") != "row"]
        dss = {(p.get("datasource") or {}).get("uid") if isinstance(p.get("datasource"), dict) else None for p in panels}
        entry = {"uid": uid, "title": d.get("title", uid), "bridge": dss == {GLITCHTIP_DS}, "panels": []}
        if dss in ({SUPABASE_DS}, {GLITCHTIP_DS}):
            entry["fn"] = _fn_name(uid)
        seen = set()
        for p in panels:
            key = panel_key(p.get("title"))
            while key in seen:
                key += "_2"
            seen.add(key)
            unit = (((p.get("fieldConfig") or {}).get("defaults") or {}).get("unit")) or ""
            entry["panels"].append({"key": key, "title": p.get("title"), "type": p.get("type"), "unit": unit,
                                    "opc": opc_marker(f"grafana:{uid}", p.get("title") or ""),
                                    "home": folded.get(f"grafana:{uid} :: {p.get('title')}", "")})
        out.append(entry)
    return out


def main() -> int:
    if "--js" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--js") + 1])
        out.write_text("// GENERATED by tools/build_console_reads.py --js from the provisioned Grafana dashboards - do not edit by hand\n"
                       "window.WH_CONSOLE_PANELS = " + json.dumps(manifest(), ensure_ascii=False, indent=1) + ";\n",
                       encoding="utf-8", newline="\n")
        print(f"wrote {out}")
        return 0
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
        out.write_text(build(), encoding="utf-8", newline="\n")
        print(f"wrote {out}")
        return 0
    if "--check" in sys.argv:
        f = Path(sys.argv[sys.argv.index("--check") + 1])
        ok = f.exists() and f.read_text(encoding="utf-8") == build()
        print("PASS console reads match the dashboards" if ok else f"FAIL {f} no longer matches the dashboards - regenerate it")
        return 0 if ok else 1
    print(build())
    return 0


if __name__ == "__main__":
    sys.exit(main())
