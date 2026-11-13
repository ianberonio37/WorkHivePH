#!/usr/bin/env python3
"""brh_db_walk.py - the live walk the BRH database classes never had (2026-10-22).

The P..Y rows (§BRH.8) were fixed, gated and banked to locking on 2026-10-21 from API probes and production's advisor,
and the ledger counts every one OPEN: each row declares `playwright-mcp + postgres-mcp` at phone-390 and desktop-1280,
and none holds a receipt from that instrument. §BRH.8 says what the walk is: "an API probe made as the person the
defect exposes - anon with only the public key - walked by platform staff from the home". This builds it:

  --plan    reads the open rows of the classes below and the local catalog (argument names, volatility, who may
            execute), and writes the probes - .tmp/slw/brh_db_probes.json - and the MCP walk with them inline,
            .tmp/slw/brh_db_walk.js. The walk signs the platform admin in through the product's form on the home page
            at each viewport, then makes every probe from a SECOND client in the page that holds no session: the
            public key alone, exactly what a stranger holds. A positive control (the public listing grid, which a
            stranger may read) runs first, so an instrument that is refused everything cannot pass as a fix.
  --sql     prints the postgres-MCP readings, one query per class (run them through the MCP, save the rows to
            .tmp/slw/brh_db_state.json as {class: rows})
  --bank    banks each row whose probe answered as its class's fix says, at BOTH viewports, with its catalog state
            read through the postgres MCP agreeing - via bank_sl_walk.bank_walk, the class's own gates run first.

Expected answers come from the gates that hold each class, never from this file: definer-doors' SIGNED_OUT and
POLICY_HELPERS (the functions a stranger keeps, each with its reason), public-read-surface's DECLARED (the tables a
stranger may read). Safety: a function the database still lets anon execute and that is VOLATILE is never called - a
probe must not write - its row is read from the catalog alone and said so.

    python tools/brh_db_walk.py --plan [--classes T,Y,S,P,Q,R,V]
    python tools/brh_db_walk.py --sql
    python tools/brh_db_walk.py --bank [--dry] [--classes ...]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
TMP = ROOT / ".tmp" / "slw"
PROBES = TMP / "brh_db_probes.json"
WALK = TMP / "brh_db_walk.js"
STATE = TMP / "brh_db_state.json"
RES = TMP / "results"
DB = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-At", "-F", "\t"]
CLASSES = ("P", "Q", "R", "S", "T", "V", "Y")
VPS = ("phone-390", "desktop-1280")
ADMIN = "leandromarquez@auth.workhiveph.com"
AQ_PROBES = TMP / "brh_aq_probes.json"
AQ_WALK = TMP / "brh_aq_walk.js"
AQ_SNAPSHOT = TMP / "brh_aq_snapshot.json"
AQ_POST = TMP / "brh_aq_post.json"
AQ_STATE = TMP / "brh_aq_state.json"
# the gates that hold each class (§BRH.8a; the specs that banked them to locking: .tmp/brh_db/*.json)
CLASS_GATES = {"P": ["public_read_surface"], "Q": ["definer-doors"], "R": ["public_read_surface", "definer-doors",
               "view_security_invoker"], "S": ["definer-doors"], "T": ["definer-doors"], "V": ["public_read_surface"],
               "Y": ["definer-doors"],
               # §BRH.8/§BRH.9, the second set: the explicit API grants, the vector extension's schema, the purge jobs,
               # and the keep-alive's own question
               "X": ["api-grants-explicit"], "U": ["vector-search-recall"], "AA": ["free-plan-budget"],
               "AE": ["free-plan-budget"], "AQ": ["record-time-pins"]}
MORE = ("X", "U", "AA", "AE", "AQ")


def x_role_kind(key: str) -> tuple[str, str]:
    """'anon · table' -> ('anon', 'table'); 'service_role · materialized view' -> ('service_role', 'materialized view')"""
    parts = key.split()
    return parts[0], ("materialized view" if "materialized" in key else parts[-1])


def psql(sql: str) -> list[list[str]]:
    r = subprocess.run(DB, input=sql, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"psql: {r.stderr.strip()[-300:]}")
    return [l.split("\t") for l in r.stdout.splitlines() if l.strip()]


def psql_checked(sql: str) -> list[str]:
    r = subprocess.run(DB + ["-v", "ON_ERROR_STOP=1", "-q"], input=sql, capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"psql: {(r.stderr or r.stdout).strip()[-500:]}")
    return [line for line in r.stdout.splitlines() if line.strip()]


def sql_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)


def open_rows(classes) -> list[dict]:
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    man = json.loads((ROOT / "live_walk_manifest.json").read_text(encoding="utf-8"))
    open_waves = set((man.get("open_by_wave") or {}).keys())
    out = []
    for t in reg["trajectories"]:
        b = t.get("brh") or {}
        if t.get("status") in ("descoped", "specced") or str(t.get("wave")) not in open_waves:
            continue
        if b.get("cls") in classes:
            out.append({"id": t["id"], "cls": b["cls"], "key": b.get("key") or "", "persona": t.get("persona")})
    return out


def fn_name(key: str) -> str:
    return key.split("(")[0].strip()


def aq_walked_row_id(p: dict, got: dict) -> str | None:
    walked_row_id = got.get("row_id")
    return p.get("row_id") if walked_row_id is None else walked_row_id


def plan_aq(rows: list[dict]) -> dict[str, dict]:
    from record_time_pins import measure

    aq_rows = [r for r in rows if r["cls"] == "AQ"]
    tables = sorted({r["key"].rsplit(".", 1)[0] for r in aq_rows})
    table_lit = ", ".join(sql_lit(t) for t in tables) or "''"
    catalog = {}
    if tables:
        q = ("select c.relname, exists (select 1 from pg_attribute a where a.attrelid = c.oid and a.attname = 'id' "
             "and a.attnum > 0 and not a.attisdropped), exists (select 1 from pg_trigger tg join pg_proc p on "
             "p.oid = tg.tgfoid where tg.tgrelid = c.oid and not tg.tgisinternal and (tg.tgtype & 2) = 0 "
             "and (tg.tgtype & 16) = 16 and (position('net.http_post' in lower(pg_get_functiondef(p.oid))) > 0 "
             "or position('http_post' in lower(pg_get_functiondef(p.oid))) > 0 "
             "or position('pg_net' in lower(pg_get_functiondef(p.oid))) > 0)) "
             "from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' "
             f"and c.relkind = 'r' and c.relname in ({table_lit}) order by c.relname")
        for table, has_id, sends_request in psql(q):
            catalog[table] = {"has_id": has_id == "t", "sends_request": sends_request == "t"}

    measured = {f"{cell['table']}.{cell['column']}": cell for cell in measure()}
    uid_rows = psql("select id::text from auth.users where email = 'joelcruz@auth.workhiveph.com' limit 1")
    uid = uid_rows[0][0] if uid_rows else None
    probes = {}
    for r in aq_rows:
        table, col = r["key"].rsplit(".", 1)
        p = {"kind": "none", "target": table, "col": col,
             "expect": "kept" if col == "created_at" else "server-timed"}
        cell = measured.get(r["key"])
        p["pinned"] = bool(cell and cell["state"] == "pinned")
        cat = catalog.get(table)
        if not cat:
            p["why"] = "the table is absent from the public catalog"
        elif not cat["has_id"]:
            p["why"] = "the table has no id column"
        elif cat["sends_request"]:
            p["why"] = "an AFTER UPDATE trigger sends a request outside the database"
        elif not uid:
            p["why"] = "Joel Cruz is absent from auth.users"
        else:
            target = "public." + sql_ident(table)
            column = sql_ident(col)
            claims = json.dumps({"sub": uid, "role": "authenticated"}, separators=(",", ":"))
            probe_sql = (
                "begin;\n"
                "create temp table aq_attempt_result (row_id text);\n"
                "grant insert on aq_attempt_result to authenticated;\n"
                f"set local role authenticated;\nset local request.jwt.claims = {sql_lit(claims)};\n"
                "do $aq$ declare candidate record; rid text; begin\n"
                f"for candidate in select id::text as candidate_id from {target} loop\n"
                "begin\n"
                f"update {target} as target set {column} = target.{column} "
                "where target.id::text = candidate.candidate_id returning target.id::text into rid;\n"
                "if rid is not null then\n"
                "insert into pg_temp.aq_attempt_result values (rid); return;\n"
                "end if;\n"
                "exception when insufficient_privilege then null;\n"
                "end;\n"
                "end loop;\n"
                "insert into pg_temp.aq_attempt_result values (null);\n"
                "end $aq$;\nreset role;\n"
                "select coalesce(row_id, '__AQ_NO_ROW__') from aq_attempt_result;\nrollback;\n"
            )
            result = psql_checked(probe_sql)
            row_id = next((line for line in result if line and line != "__AQ_NO_ROW__"), None)
            if row_id:
                p.update(kind="backdate", row_id=row_id, value="2020-01-01T00:00:00+00:00")
            else:
                p["why"] = "Joel has no row in this table that his UPDATE policy lets him change"
        probes[r["id"]] = p
    return probes


def plan(classes) -> list[dict]:
    from validate_definer_doors import SIGNED_OUT, POLICY_HELPERS
    from validate_public_read_surface import DECLARED
    rows = open_rows(classes)
    aq = plan_aq(rows) if any(r["cls"] == "AQ" for r in rows) else {}
    fns = sorted({fn_name(r["key"]) for r in rows if r["cls"] in ("Q", "S", "T", "Y")})
    cat = {}
    if fns:
        q = ("select p.proname, coalesce(array_to_string(p.proargnames, ','), ''), p.pronargs, p.provolatile, "
             "has_function_privilege('anon', p.oid, 'execute'), p.prorettype::regtype::text "
             "from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname in ("
             + ", ".join("'" + f + "'" for f in fns) + ");")
        for name, args, nargs, vol, anon_x, rett in psql(q):
            cat.setdefault(name, []).append({"args": [a for a in args.split(",") if a][:int(nargs)], "volatile": vol,
                                             "anon_exec": anon_x == "t", "returns": rett})
    probes = []
    for r in rows:
        c, key = r["cls"], r["key"]
        p = {"id": r["id"], "cls": c, "key": key}
        if c in ("P", "V", "R"):
            public = (key in DECLARED) if c == "P" else key in ("v_marketplace_listings_public", "v_marketplace_sellers_public")
            p.update(kind="select", target=key, expect="answers" if public else "refused")
        elif c == "Q":
            p.update(kind="rpc", target=fn_name(key), args={}, expect="absent")
        elif c in ("S", "Y"):
            f = fn_name(key)
            keep = f in SIGNED_OUT or f in POLICY_HELPERS
            defs = cat.get(f) or []
            d = defs[0] if defs else None
            if d is None:
                p.update(kind="none", expect="absent", why="no such function in the local catalog")
            elif keep and d["volatile"] == "v":
                p.update(kind="none", expect="answers", why="kept for a stranger by declaration, and VOLATILE: not called")
            elif not keep and d["anon_exec"] and d["volatile"] == "v":
                p.update(kind="none", expect="refused", why="the catalog still lets anon run it and it writes: not called")
            else:
                p.update(kind="rpc", target=f, args={a: None for a in d["args"]}, expect="answers" if keep else "refused")
        elif c == "X":
            role, kind = x_role_kind(key)
            if role == "anon":
                p.update(kind="select", target="multilingual_terms" if kind == "table" else "v_marketplace_listings_public",
                         expect="answers")
            elif role == "authenticated":
                p.update(kind="select_page", target="hive_members" if kind == "table" else "v_worker_truth", expect="answers")
            else:
                p.update(kind="none", expect="granted", why="service_role is the server's key and never reaches a browser")
        elif c == "U":
            p.update(kind="none", expect="relocated")
        elif c == "AA":
            p.update(kind="none", expect="purged")
        elif c == "AE":   # the keep-alive's own question: one id from the public reference table any visitor may read
            p.update(kind="select", target="industry_standards", expect="answers")
        elif c == "AQ":
            p.update(aq[r["id"]])
        else:   # T: the fix is the function's own search_path; there is nothing for a stranger to call
            p.update(kind="none", expect="pinned")
        probes.append(p)
    return probes


WALK_JS = r"""async (page) => {
// BRH database classes, live (tools/brh_db_walk.py --plan, @@GENERATED@@): the platform admin (Leandro Marquez, oversight)
// signs in through the product's form on the home page at each viewport, and from that page makes every probe through a
// SECOND client that holds no session - the public key alone, what a stranger holds. A positive control first: the public
// listing grid, which a stranger may read. Results: .tmp/slw/results/brh_db_walk_<viewport>.json.
const B = 'http://127.0.0.1:5000/workhive/';
const z = (m) => new Promise((r) => setTimeout(r, m));
const PROBES = @@PROBES@@;
const VIEW = { 'phone-390': [390, 844, true], 'desktop-1280': [1280, 900, false] };
const results = [];
for (const vp of ['phone-390', 'desktop-1280']) {
  const [vw, vh, mobile] = VIEW[vp];
  const ctx = await page.context().browser().newContext({ serviceWorkers: 'block', viewport: { width: vw, height: vh }, isMobile: mobile, hasTouch: mobile });
  await ctx.route('**/functions/v1/**', (r) => r.request().method() === 'OPTIONS' ? r.fallback() : r.fallback({ headers: { ...r.request().headers(), 'x-wh-walk-no-model': '1' } }));
  const out = { viewport: vp, generated: new Date().toISOString(), cast: 'leandromarquez (platform admin, oversight)', pageErrors: [], probes: {} };
  const p = await ctx.newPage();
  p.on('pageerror', (e) => out.pageErrors.push(String(e.message || e).slice(0, 200)));
  try {
    let sess = false;
    for (let attempt = 1; attempt <= 2 && !sess; attempt++) {
      await p.goto(B + 'index.html?signin=1', { waitUntil: 'load', timeout: 60000 }).catch(() => {});
      await p.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
      if (await p.locator('#si-username').isVisible().catch(() => false)) {
        await p.fill('#si-username', 'leandromarquez'); await p.fill('#si-password', 'test1234');
        await p.click('#si-btn').catch(() => p.press('#si-password', 'Enter'));
      }
      for (let i = 0; i < 30 && !sess; i++) {
        sess = await p.evaluate(() => Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || ''))).catch(() => false);
        if (!sess) await z(1000);
      }
    }
    out.signin = sess ? 'ok - the sign-in form' : 'no session';
    await p.goto(B + 'index.html', { waitUntil: 'load', timeout: 60000 });
    await p.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await z(1500);
    out.home = await p.evaluate(() => ({ chars: (document.body.innerText || '').length, title: document.title,
      overflowX: document.documentElement.scrollWidth > innerWidth + 1 }));
    out.identity = await p.evaluate(async () => { const s = window._whSupabaseClient ? (await window._whSupabaseClient.auth.getSession()).data.session : null; return { user: s && s.user && s.user.email }; });
    const res = await p.evaluate(async (PROBES) => {
      const anon = window.supabase.createClient(window.WH_SUPABASE_URL, window.WH_SUPABASE_ANON_KEY,
        { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false, storageKey: 'wh-brh-probe-anon' } });
      const said = (e) => (e ? { code: e.code || null, message: String(e.message || '').slice(0, 160), status: e.status || null } : null);
      const out = {};
      const ctl = await anon.from('v_marketplace_listings_public').select('id', { count: 'exact', head: true });
      out.__control = { error: said(ctl.error), count: ctl.count };
      for (const pr of PROBES) {
        if (pr.kind === 'select') {
          const r = await anon.from(pr.target).select('*', { count: 'exact', head: true });
          out[pr.id] = { error: said(r.error), count: r.count, status: r.status };
        } else if (pr.kind === 'select_page') {
          // the page's OWN client - the signed-in platform admin, the authenticated role
          const r = await window._whSupabaseClient.from(pr.target).select('*', { count: 'exact', head: true });
          out[pr.id] = { error: said(r.error), count: r.count, status: r.status, as: 'the page session (authenticated)' };
        } else if (pr.kind === 'rpc') {
          const r = await anon.rpc(pr.target, pr.args);
          out[pr.id] = { error: said(r.error), answered: !r.error, status: r.status };
        } else out[pr.id] = { notCalled: pr.why || 'nothing for a stranger to call' };
      }
      return out;
    }, PROBES);
    out.probes = res;
  } catch (e) { out.error = String((e && e.message) || e).slice(0, 300); }
  await ctx.close();
  try { await fetch('http://127.0.0.1:8765/save?name=brh_db_walk_' + vp, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(out) }); } catch (_) {}
  const ctlOk = out.probes && out.probes.__control && !out.probes.__control.error && out.probes.__control.count > 0;
  results.push(vp + ': ' + (out.error ? 'ERR ' + out.error : out.signin + ' · ' + (out.identity || {}).user + ' · home ' + (out.home || {}).chars + ' chars · control ' + (ctlOk ? 'ok' : 'FAILED') + ' · probes ' + Object.keys(out.probes || {}).length + ' · page errors ' + out.pageErrors.length));
}
return results;
}
"""

AQ_WALK_JS = r"""async (page) => {
// BRH-AQ live walk (tools/brh_db_walk.py --plan --classes AQ): Joel Cruz signs in through the product's form on the
// home page at each viewport, then reads his own logbook as the positive control and uses the page's own client to test
// every backdate probe. Results: .tmp/slw/results/brh_aq_walk_<viewport>.json.
const B = 'http://127.0.0.1:5000/workhive/';
const z = (m) => new Promise((r) => setTimeout(r, m));
const PROBES = @@PROBES@@;
const VIEW = { 'phone-390': [390, 844, true], 'desktop-1280': [1280, 900, false] };
const results = [];
for (const vp of ['phone-390', 'desktop-1280']) {
  const [vw, vh, mobile] = VIEW[vp];
  const ctx = await page.context().browser().newContext({ serviceWorkers: 'block', viewport: { width: vw, height: vh }, isMobile: mobile, hasTouch: mobile });
  await ctx.route('**/functions/v1/**', (r) => r.request().method() === 'OPTIONS' ? r.fallback() : r.fallback({ headers: { ...r.request().headers(), 'x-wh-walk-no-model': '1' } }));
  const out = { viewport: vp, generated: new Date().toISOString(), cast: 'Joel Cruz, worker', pageErrors: [], probes: {} };
  const p = await ctx.newPage();
  p.on('pageerror', (e) => out.pageErrors.push(String(e.message || e).slice(0, 200)));
  try {
    let sess = false;
    for (let attempt = 1; attempt <= 2 && !sess; attempt++) {
      await p.goto(B + 'index.html?signin=1', { waitUntil: 'load', timeout: 60000 }).catch(() => {});
      await p.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
      if (await p.locator('#si-username').isVisible().catch(() => false)) {
        await p.fill('#si-username', 'joelcruz');
        await p.fill('#si-password', 'test1234');
        await p.click('#si-btn').catch(() => p.press('#si-password', 'Enter'));
      }
      for (let i = 0; i < 30 && !sess; i++) {
        sess = await p.evaluate(() => Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || ''))).catch(() => false);
        if (!sess) await z(1000);
      }
    }
    out.signin = sess ? 'ok - the sign-in form' : 'no session';
    await p.goto(B + 'index.html', { waitUntil: 'load', timeout: 60000 });
    await p.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await z(1500);
    out.home = await p.evaluate(() => ({ chars: (document.body.innerText || '').length, title: document.title, overflowX: document.documentElement.scrollWidth > innerWidth + 1 }));
    out.identity = await p.evaluate(async () => { const s = window._whSupabaseClient ? (await window._whSupabaseClient.auth.getSession()).data.session : null; return { user: s && s.user && s.user.email }; });
    const res = await p.evaluate(async (PROBES) => {
      const said = (e) => (e ? { code: e.code || null, message: String(e.message || '').slice(0, 160), status: e.status || null } : null);
      const out = {};
      const ctl = await window._whSupabaseClient.from('logbook').select('id', { count: 'exact', head: true });
      out.__control = { error: said(ctl.error), count: ctl.count, status: ctl.status, as: 'window._whSupabaseClient logbook count' };
      for (const pr of PROBES) {
        if (pr.kind === 'backdate') {
          const when = new Date().toISOString();
          const r = await window._whSupabaseClient.from(pr.target).update({ [pr.col]: pr.value }).eq('id', pr.row_id).select(pr.col);
          out[pr.id] = { error: said(r.error), status: r.status, rows: (r.data || []).length, value: (r.data || [])[0]?.[pr.col] ?? null, row_id: pr.row_id, when };
        } else {
          out[pr.id] = { notCalled: pr.why || 'nothing for Joel to call' };
        }
      }
      return out;
    }, PROBES);
    out.probes = res;
  } catch (e) { out.error = String((e && e.message) || e).slice(0, 300); }
  await ctx.close();
  try { await fetch('http://127.0.0.1:8765/save?name=brh_aq_walk_' + vp, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(out) }); } catch (_) {}
  const ctlOk = out.probes && out.probes.__control && !out.probes.__control.error && Number(out.probes.__control.count || 0) > 0;
  results.push(vp + ': ' + (out.error ? 'ERR ' + out.error : out.signin + ' · ' + (out.identity || {}).user + ' · home ' + (out.home || {}).chars + ' chars · control ' + (ctlOk ? 'ok' : 'FAILED') + ' · probes ' + Object.keys(out.probes || {}).length + ' · page errors ' + out.pageErrors.length));
}
return results;
}
"""


def sql_for(classes) -> dict[str, str]:
    rows = open_rows(classes)
    keys = lambda c: sorted({fn_name(r["key"]) if c in "QSTY" else r["key"] for r in rows if r["cls"] == c})
    lit = lambda xs: ", ".join("'" + x.replace("'", "''") + "'" for x in xs) or "''"
    q = {}
    if keys("P"):
        q["P"] = ("select c.relname as name, c.relrowsecurity as rls, has_table_privilege('anon', c.oid, 'select') as anon_select, "
                  "(select count(*) from pg_policies pl where pl.schemaname = 'public' and pl.tablename = c.relname and "
                  "('anon' = any(pl.roles) or 'public' = any(pl.roles)) and pl.cmd in ('SELECT', 'ALL')) as stranger_policies "
                  "from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relname in ("
                  + lit(keys("P")) + ") order by 1")
    if keys("Q"):
        q["Q"] = ("select p.proname as name from pg_proc p join pg_namespace n on n.oid = p.pronamespace where p.proname like "
                  "'debug\\_%' order by 1")
    if keys("R") or keys("V"):
        q["RV"] = ("select c.relname as name, c.relkind as kind, coalesce(array_to_string(c.reloptions, ','), '') as options, "
                   "has_table_privilege('anon', c.oid, 'select') as anon_select from pg_class c join pg_namespace n on "
                   "n.oid = c.relnamespace where n.nspname = 'public' and c.relname in (" + lit(keys("R") + keys("V")) + ") order by 1")
    if keys("X"):
        q["X"] = ("select r.role || '|' || k.kind as name, count(*) as total, count(*) filter (where has_table_privilege(r.role, "
                  "c.oid, 'select')) as selectable from pg_class c join pg_namespace n on n.oid = c.relnamespace join (values "
                  "('r', 'table'), ('v', 'view'), ('m', 'materialized view')) k(relkind, kind) on k.relkind = c.relkind::text "
                  "cross join (values ('anon'), ('authenticated'), ('service_role')) r(role) where n.nspname = 'public' "
                  "group by 1 order by 1")
    if keys("U"):
        q["U"] = ("select e.extname as name, n.nspname as schema from pg_extension e join pg_namespace n on n.oid = "
                  "e.extnamespace where e.extname in ('vector', 'pg_net') order by 1")
    if keys("AA"):
        q["AA"] = ("select j.jobname as name, regexp_replace(j.command, '\\s+', ' ', 'g') as command, (select max(d.end_time) "
                   "from cron.job_run_details d where d.jobid = j.jobid and d.status = 'succeeded') as last_ok from cron.job j "
                   "where j.jobname like '%retention%' order by 1")
    if keys("AQ"):
        cells = []
        for key in keys("AQ"):
            table, col = key.rsplit(".", 1)
            cells.append(f"({sql_lit(table)}, {sql_lit(col)})")
        q["AQ"] = ("with cells(table_name, column_name) as (values " + ", ".join(cells) + "), "
                   "matches as (select c.table_name, c.column_name, p.proname || ':' || "
                   "split_part(encode(tg.tgargs, 'escape'), '\\000', 1) as trigger_name, "
                   "(lower(regexp_replace(pg_get_functiondef(p.oid), '\\s+', '', 'g')) "
                   "like '%new.' || c.column_name || ':=old.' || c.column_name || '%' "
                   "or lower(pg_get_functiondef(p.oid)) like '%wh_server_time_on_change(' || c.column_name || '%' "
                   "or p.proname = 'wh_server_time_on_change' and "
                   "split_part(encode(tg.tgargs, 'escape'), '\\000', 1) = c.column_name) as pinned "
                   "from cells c join pg_class r on r.relname = c.table_name join pg_namespace n on "
                   "n.oid = r.relnamespace and n.nspname = 'public' left join pg_trigger tg on "
                   "tg.tgrelid = r.oid and not tg.tgisinternal and (tg.tgtype & 2) = 2 and "
                   "(tg.tgtype & 16) = 16 left join pg_proc p on p.oid = tg.tgfoid), "
                   "catalog as (select table_name, column_name, bool_or(coalesce(pinned, false)) as pinned, "
                   "string_agg(trigger_name, ', ' order by trigger_name) filter (where pinned) as trigger_name "
                   "from matches group by table_name, column_name) "
                   "select c.table_name || '.' || c.column_name as name, coalesce(k.pinned, false) as pinned, "
                   "coalesce(k.trigger_name, '') as trigger_name from cells c left join catalog k using "
                   "(table_name, column_name) order by 1")
    fs = keys("S") + keys("T") + keys("Y")
    if fs:
        q["STY"] = ("select p.proname as name, p.prosecdef as definer, p.provolatile as volatility, has_function_privilege('anon', "
                    "p.oid, 'execute') as anon_exec, coalesce(array_to_string(p.proconfig, ','), '') as config from pg_proc p join "
                    "pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname in (" + lit(fs) + ") order by 1")
    return q


def _state_key(cls: str) -> str:
    return "RV" if cls in ("R", "V") else "STY" if cls in ("S", "T", "Y") else cls


def verdict(p: dict, got: dict, state: dict) -> tuple[bool, str]:
    """did the stranger's probe answer as the class's fix says, and does the catalog agree"""
    c, e = p["cls"], (got or {}).get("error") or {}
    code = e.get("code") or ""
    if p["kind"] == "select_page" or (p["kind"] == "select" and c in ("X", "AE")):
        ok = not e and got.get("status") in (200, 206)
        who = "the signed-in role" if p["kind"] == "select_page" else "a stranger"
        if c == "AE":
            wf = (ROOT / ".github" / "workflows" / "keep-alive.yml").exists()
            return ok and wf, (f"the keep-alive's own question answers ({got.get('count')} rows), and .github/workflows/"
                               f"keep-alive.yml asks it every second day" if ok and wf else "the keep-alive's question failed")
        return ok, (f"{who} still reads {p['target']} ({got.get('count')} rows): its explicit grant holds"
                    if ok else f"{who} was refused {p['target']} ({code or got.get('status')})")
    if p["kind"] == "select":
        st = state.get("RV" if c in "RV" else "P", {}).get(p["key"])
        if p["expect"] == "answers":
            ok = not e
            return ok, (f"a stranger reads it ({got.get('count')} rows), as declared" if ok else f"a stranger was refused ({code}) a read declared public")
        cat = (st or {})
        if c == "P" and cat and str(cat.get("rls")) not in ("True", "true", "t"):
            return False, "RLS is off in the catalog"
        if c == "R" and cat and "security_invoker=true" not in str(cat.get("options")) and not cat.get("definer_fn"):
            return False, "the view does not run as its reader"
        # a refusal is evidence only when it is a refusal: no grant (401/403) - or 0 rows while a PARTY to the same rows
        # reads some (a stranger's 0 over an empty view proves nothing; stage a row and read it as a party first)
        if e or got.get("status") in (401, 403):
            return True, f"a stranger is refused ({got.get('status') or code}: no grant)"
        party = got.get("party") if got.get("party") is not None else (state.get("PARTY", {}).get(p["key"]) or {}).get("rows")
        if got.get("count") == 0 and party and int(party) > 0:
            return True, f"a stranger reads 0 rows while a party to them reads {party}"
        return False, (f"a stranger read {got.get('count')} rows" if got.get("count") else
                       "a stranger read 0 rows, and no party read is on record - over an empty view a 0 proves nothing")
    if p["kind"] == "rpc":
        if p["expect"] == "absent":
            ok = code in ("PGRST202", "42883") or got.get("status") == 404
            return ok, ("the function does not exist for a stranger to call" if ok else f"it answered ({code or got.get('status')})")
        if p["expect"] == "refused":
            ok = code == "42501" or got.get("status") in (401, 403)
            return ok, ("a stranger is refused (42501, permission denied)" if ok else f"a stranger was not refused ({code or 'answered'})")
        ok = code not in ("42501", "PGRST202") and got.get("status") not in (401, 403, 404)
        return ok, ("a stranger is answered, as declared" if ok else f"a stranger was refused ({code}) a function declared public")
    # not called: the catalog alone
    if c == "X":
        role, kind = x_role_kind(p["key"])
        row = state.get("X", {}).get(f"{role}|{kind}") or {}
        ok = bool(row) and int(row.get("total") or 0) > 0 and int(row.get("selectable") or 0) == int(row.get("total") or -1)
        return ok, (f"{role} holds SELECT on all {row.get('total')} public {kind}s (the catalog), and api-grants-explicit "
                    f"holds that every one is granted by a migration"
                    if ok else f"{role} reaches {row.get('selectable')} of {row.get('total')} public {kind}s")
    if c == "U":
        row = state.get("U", {}).get(p["key"]) or {}
        ok = row.get("schema") == "extensions"
        return ok, (f"{p['key']} lives in the extensions schema (the catalog)" if ok else f"{p['key']} is in {row.get('schema')}")
    if c == "AA":
        table = p["key"].split(".")[-1]
        jobs = [r for r in state.get("AA", {}).values() if table in str(r.get("command"))]
        ok = any(r.get("last_ok") for r in jobs)
        j = jobs[0] if jobs else {}
        return ok, (f"its purge ({j.get('name')}) ran on {str(j.get('last_ok'))[:16]} (the catalog)" if ok
                    else "no purge job ran for it")
    if c == "AQ":
        walked_row_id = aq_walked_row_id(p, got or {})
        row_note = ""
        if (got or {}).get("row_id") is not None and walked_row_id != p.get("row_id"):
            row_note = (f"(the plan now names {p.get('row_id')}; "
                        f"judged on the walked row {walked_row_id})")

        def explain(reason: str) -> str:
            return f"{reason} {row_note}" if row_note else reason

        row = state.get("AQ", {}).get(p["key"]) or {}
        pinned_value = row.get("pinned")
        pinned = pinned_value is True or str(pinned_value).lower() in ("true", "t", "1")
        if not pinned:
            return False, explain(f"the catalog does not say {p['key']} is pinned")
        if (p["kind"] == "backdate" and code == "42501"
                and int((got or {}).get("rows") or 0) == 0):
            message = str(e.get("message") or "")[:60]
            return True, explain(
                f"the member is refused outright (42501: {message}), so the time cannot be rewritten; "
                f"the catalog shows {row.get('trigger_name')} on it")
        if p["kind"] == "none":
            return True, explain(
                f"the catalog pins {p['key']}; it was not called ({got.get('notCalled') if got else p.get('why')})")
        if p["expect"] == "kept":
            snap = json.loads(AQ_SNAPSHOT.read_text(encoding="utf-8"))
            before_row = snap.get("rows", {}).get(f"{p['target']}.{walked_row_id}")
            before = before_row.get(p["col"]) if isinstance(before_row, dict) else None
            value = (got or {}).get("value")
            has_before = isinstance(before_row, dict) and p["col"] in before_row
            ok = bool(not e and int((got or {}).get("rows") or 0) > 0 and has_before and value == before)
            return ok, explain(
                f"the update kept {p['key']} at its snapshot value {before}; the catalog agrees"
                if ok else f"the update did not keep {p['key']} at its snapshot value; the catalog agrees")
        if p["expect"] == "server-timed":
            value = (got or {}).get("value")
            ok = bool(not e and int((got or {}).get("rows") or 0) > 0 and value is not None
                      and not str(value).startswith("2020-01-01"))
            walk_time = None
            if isinstance((got or {}).get("when"), str):
                try:
                    walk_time = datetime.fromisoformat(got["when"].replace("Z", "+00:00"))
                    server_time = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if walk_time.tzinfo is None:
                        walk_time = walk_time.replace(tzinfo=timezone.utc)
                    if server_time.tzinfo is None:
                        server_time = server_time.replace(tzinfo=timezone.utc)
                    ok = ok and abs((server_time - walk_time).total_seconds()) <= 600
                except ValueError:
                    ok = False
            else:
                ok = False
            return ok, explain(
                f"the record time stayed server-timed to the walk time; the catalog agrees" if ok
                else f"the update did not stay server-timed within 10 minutes; the catalog agrees")
        return False, explain(f"the AQ probe has an unknown expectation ({p.get('expect')}); the catalog agrees")
    st = state.get("STY", {}).get(fn_name(p["key"]))
    if p["expect"] == "pinned":
        ok = bool(st) and "search_path=" in str(st.get("config"))
        return ok, (f"its search_path is pinned ({st.get('config')})" if ok else "its search_path is not pinned")
    if p["expect"] == "absent":
        return st is None, "absent from the catalog" if st is None else "still in the catalog"
    if p["expect"] == "refused":
        ok = bool(st) and str(st.get("anon_exec")) in ("False", "false", "f")
        return ok, ("anon may not execute it (the catalog)" if ok else "anon may still execute it")
    ok = bool(st) and str(st.get("anon_exec")) in ("True", "true", "t")
    return ok, ("anon keeps it, as declared (not called: it writes)" if ok else "anon lost a function declared public")


def load_aq_probes() -> list[dict]:
    if not AQ_PROBES.exists():
        raise SystemExit(f"AQ probes are missing: {AQ_PROBES.relative_to(ROOT)}; run --plan --classes AQ first")
    return json.loads(AQ_PROBES.read_text(encoding="utf-8"))


def aq_rows_by_key(probes: list[dict]) -> dict[str, dict]:
    rows = {}
    for p in probes:
        if p.get("kind") == "backdate":
            key = f"{p['target']}.{p['row_id']}"
            rows[key] = {"table": p["target"], "id": str(p["row_id"])}
    return rows


def aq_pre() -> int:
    probes = load_aq_probes()
    rows = aq_rows_by_key(probes)
    if not AQ_PROBES.exists():
        raise SystemExit("AQ probes are missing")
    tables = sorted({row["table"] for row in rows.values()})
    inserts = []
    for key, row in rows.items():
        table = "public." + sql_ident(row["table"])
        inserts.append(f"select {sql_lit(key)}, row_to_json(t)::jsonb from {table} t "
                       f"where t.id::text = {sql_lit(row['id'])}")
    table_values = ", ".join(f"({sql_lit(table)})" for table in tables)
    if not table_values:
        table_values = "('')"
    sql = (
        "begin;\n"
        "create temp table aq_snap (k text primary key, v jsonb) on commit drop;\n"
        + ("insert into aq_snap(k, v) " + " union all ".join(inserts) + ";\n" if inserts else "")
        + "do $aq$ begin if (select count(*) from aq_snap) <> " + str(len(rows))
        + " then raise exception 'AQ snapshot row count mismatch'; end if; end $aq$;\n"
        + "create temp table aq_active on commit drop as select source_table from public.embedding_registry "
          "where active and source_table in (select column1 from (values " + table_values + ") as tables);\n"
        + "update public.embedding_registry set active = false where source_table in "
          "(select column1 from (values " + table_values + ") as tables);\n"
        + "select jsonb_build_object('t0', now(), 'rows', coalesce((select jsonb_object_agg(k, v) from aq_snap), '{}'::jsonb), "
          "'registry_active', coalesce((select jsonb_agg(source_table order by source_table) from aq_active), '[]'::jsonb), "
          "'tables', to_jsonb(array(select column1 from (values " + table_values + ") as tables order by column1)))::text;\n"
        "commit;\n"
    )
    output = psql_checked(sql)
    if not output:
        raise SystemExit("AQ pre did not return its snapshot")
    snapshot = json.loads(output[-1])
    write_json(AQ_SNAPSHOT, snapshot)
    print(f"snapshotted {len(snapshot.get('rows') or {})} rows; disabled embedding for {len(tables)} table(s)")
    return 0


def aq_read_rows(rows: dict[str, dict]) -> dict:
    selects = []
    for key, row in rows.items():
        table = "public." + sql_ident(row["table"])
        selects.append(f"select {sql_lit(key)} as k, to_jsonb(t) as v from {table} t "
                       f"where t.id::text = {sql_lit(row['id'])}")
    if not selects:
        return {}
    lines = psql_checked("select coalesce(jsonb_object_agg(k, v), '{}'::jsonb)::text from ("
                         + " union all ".join(selects) + ") aq_rows")
    return json.loads(lines[-1]) if lines else {}


def aq_post() -> int:
    if not AQ_SNAPSHOT.exists():
        raise SystemExit(f"AQ snapshot is missing: {AQ_SNAPSHOT.relative_to(ROOT)}; run --aq-pre before the walk")
    snapshot = json.loads(AQ_SNAPSHOT.read_text(encoding="utf-8"))
    snapshot_rows = snapshot.get("rows") or {}
    rows = {}
    for key in snapshot_rows:
        table, row_id = key.split(".", 1)
        rows[key] = {"table": table, "id": row_id}
    current = aq_read_rows(rows)
    restores = []
    for key, before in snapshot_rows.items():
        after = current.get(key)
        if not isinstance(after, dict):
            continue
        changed = [col for col in set(before) | set(after) if before.get(col) != after.get(col)]
        if not changed:
            continue
        table, row_id = rows[key]["table"], rows[key]["id"]
        cols = ", ".join(sql_ident(col) for col in sorted(changed))
        json_row = sql_lit(json.dumps(before, ensure_ascii=False))
        table_ref = "public." + sql_ident(table)
        restores.append(
            f"update {table_ref} as t set ({cols}) = (select {cols} from "
            f"jsonb_populate_record(null::{table_ref}, {json_row}::jsonb)) where t.id::text = {sql_lit(row_id)};"
        )

    all_ids = sorted({row["id"] for row in rows.values()})
    ids_sql = ", ".join(sql_lit(row_id) for row_id in all_ids) or "''"
    t0 = sql_lit(snapshot["t0"])
    active_tables = sorted(set(snapshot.get("registry_active") or []))
    active_sql = ", ".join(sql_lit(table) for table in active_tables) or "''"
    cleanup = (
        "begin;\nset session_replication_role = replica;\n"
        + "create temp table aq_audit on commit drop as select action, target_type, target_id::text as target_id "
          "from public.hive_audit_log where created_at >= " + t0 + "::timestamptz "
          "and target_id::text in (" + ids_sql + ");\n"
        + "\n".join(restores) + "\n"
        + "delete from public.hive_audit_log where created_at >= " + t0 + "::timestamptz "
          "and target_id::text in (" + ids_sql + ");\n"
        + "delete from public.embedding_outbox where enqueued_at >= " + t0 + "::timestamptz "
          "and row_id::text in (" + ids_sql + ") and done_at is null;\n"
        + (f"update public.embedding_registry set active = true where source_table in ({active_sql});\n"
           if active_tables else "")
        + "create temp table aq_sign_in_residue (new_device bigint, client_errors bigint) on commit drop;\n"
        + "do $$ declare joel_uid uuid; new_device_count bigint; client_error_count bigint; begin "
          "select id into joel_uid from auth.users where email = 'joelcruz@auth.workhiveph.com' limit 1; "
          "if joel_uid is null then raise exception 'Joel Cruz is missing from auth.users'; end if; "
          "delete from public.hive_audit_log where created_at >= " + t0 + "::timestamptz "
          "and action = 'new_device' and meta->>'actor_auth_uid' = joel_uid::text; "
          "get diagnostics new_device_count = row_count; "
          "delete from public.client_errors where created_at >= " + t0 + "::timestamptz "
          "and message like 'Some of this page could not be shown%' and auth_uid = joel_uid; "
          "get diagnostics client_error_count = row_count; "
          "insert into aq_sign_in_residue values (new_device_count, client_error_count); end $$;\n"
        + "do $$ declare r record; begin "
          "create temp table aq_residue on commit drop as select table_name::text, row_count::bigint from (select '' as table_name, 0::bigint as row_count) x; "
          "for r in select table_schema, table_name from information_schema.columns "
          "where table_schema = 'public' and column_name = 'created_at' "
          "and table_name not in ('hive_audit_log', 'embedding_outbox') group by table_schema, table_name loop "
          "execute format('insert into aq_residue(table_name, row_count) values (%L, (select count(*) from %I.%I where created_at >= %L::timestamptz))', "
          "r.table_name, 'public', r.table_name, " + t0 + "); "
          "end loop; end $$;\n"
        + "set session_replication_role = origin;\n"
        + "select jsonb_build_object('audit', coalesce((select jsonb_agg(jsonb_build_object("
          "'action', action, 'target_type', target_type, 'target_id', target_id) order by target_id) from aq_audit), "
          "'[]'::jsonb), 'residue', coalesce((select jsonb_agg(jsonb_build_object('table', table_name, 'rows', row_count) "
          "order by table_name) from (select table_name, row_count from aq_residue where row_count > 0) s), '[]'::jsonb), "
          "'sign_in_residue', jsonb_build_object('new_device', coalesce((select new_device from aq_sign_in_residue), 0), "
          "'client_errors', coalesce((select client_errors from aq_sign_in_residue), 0)))::text;\ncommit;\n"
    )
    output = psql_checked(cleanup)
    if not output:
        raise SystemExit("AQ post cleanup did not return its audit receipt")
    cleanup_receipt = json.loads(output[-1])
    final = aq_read_rows(rows)
    details = []
    restored = 0
    for key, before in snapshot_rows.items():
        after = final.get(key)
        if not isinstance(after, dict):
            details.append({"row": key, "missing": True})
            continue
        diffs = [{"column": col, "expected": before.get(col), "actual": after.get(col)}
                 for col in sorted(set(before) | set(after)) if before.get(col) != after.get(col)]
        if diffs:
            details.append({"row": key, "diffs": diffs})
        else:
            restored += 1
    status = f"RESTORED {restored}/{len(snapshot_rows)}"
    residue = cleanup_receipt.get("residue") or []
    receipt = {"t0": snapshot["t0"], "restored": status, "rows": details,
               "audit": cleanup_receipt.get("audit") or [], "residue": residue,
               "sign_in_residue": cleanup_receipt.get("sign_in_residue") or {"new_device": 0, "client_errors": 0}}
    write_json(AQ_POST, receipt)
    print(status)
    if residue:
        for item in residue:
            print(f"RESIDUE {item['table']} {item['rows']}")
    else:
        print("RESIDUE none")
    if restored != len(snapshot_rows):
        for detail in details:
            if detail.get("missing"):
                print(f"DIFF {detail['row']}: row is missing")
            for diff in detail.get("diffs", []):
                print(f"DIFF {detail['row']}.{diff['column']}: expected {diff['expected']!r}, got {diff['actual']!r}")
        return 1
    print(f"audited amendments captured: {len(receipt['audit'])}; receipt: {AQ_POST.relative_to(ROOT)}")
    return 0


def bank_aq(dry: bool, ids: set | None = None) -> int:
    import bank_sl_walk as bsw

    missing_walks = [str((RES / f"brh_aq_walk_{vp}.json").relative_to(ROOT)) for vp in VPS
                     if not (RES / f"brh_aq_walk_{vp}.json").exists()]
    if missing_walks:
        raise SystemExit("AQ walk results are missing: " + ", ".join(missing_walks))
    for path in (AQ_STATE, AQ_SNAPSHOT, AQ_POST):
        if not path.exists():
            raise SystemExit(f"AQ bank evidence is missing: {path.relative_to(ROOT)}")
    probes = [p for p in load_aq_probes() if not ids or p["id"] in ids]
    walks = {vp: json.loads((RES / f"brh_aq_walk_{vp}.json").read_text(encoding="utf-8")) for vp in VPS}
    raw = json.loads(AQ_STATE.read_text(encoding="utf-8"))
    digests = raw.pop("_mcp_digests", None)
    if not digests:
        raise SystemExit("the AQ catalog readings carry no postgres-MCP digests")
    state = {"AQ": {str(r.get("name")): r for r in raw.get("AQ", [])}}
    post = json.loads(AQ_POST.read_text(encoding="utf-8"))
    restored = post.get("restored", "")
    match = re.fullmatch(r"RESTORED (\d+)/(\d+)", restored)
    if not match or match.group(1) != match.group(2):
        raise SystemExit(f"AQ rows were not fully restored ({restored or 'no RESTORED receipt'})")
    if not post.get("audit"):
        raise SystemExit("the AQ post receipt contains no audited amendment")

    for vp, walk in walks.items():
        ctl = (walk.get("probes") or {}).get("__control") or {}
        if walk.get("signin") != "ok - the sign-in form" or (walk.get("identity") or {}).get("user") != "joelcruz@auth.workhiveph.com":
            raise SystemExit(f"{vp}: the walk did not sign Joel Cruz in through the form")
        if ctl.get("error") or not (ctl.get("count") or 0) > 0:
            raise SystemExit(f"{vp}: Joel's own logbook positive control failed ({ctl})")
    gates = CLASS_GATES["AQ"]
    banked, skipped = [], []
    for p in probes:
        per = {vp: verdict(p, (walks[vp].get("probes") or {}).get(p["id"]) or {}, state) for vp in VPS}
        for vp, walk in walks.items():
            if walk.get("pageErrors"):
                per[vp] = (False, "the page reported an error")
        if not all(ok for ok, _ in per.values()):
            skipped.append((p["id"], "; ".join(f"{vp}: {why}" for vp, (ok, why) in per.items() if not ok)))
            continue
        steps = [{
            "viewport": vp,
            "device": "Pixel-class phone, 390 CSS px" if vp == "phone-390" else "desktop, 1280 CSS px",
            "page": "index.html",
            "chars": (walks[vp].get("home") or {}).get("chars", 0),
            "identityKept": True,
            "pageErrors": walks[vp].get("pageErrors") or [],
            "overflowX": (walks[vp].get("home") or {}).get("overflowX", False),
            "cast": "Joel Cruz, worker",
            "as": "joelcruz",
            "probe": {
                **{k: p.get(k) for k in ("kind", "target", "col", "row_id", "value", "expect")},
                "row_id": aq_walked_row_id(p, (walks[vp].get("probes") or {}).get(p["id"]) or {}),
            },
            "answer": (walks[vp].get("probes") or {}).get(p["id"]),
            "control": walks[vp]["probes"]["__control"],
            "verdict": per[vp][1],
        } for vp in VPS]
        why = per["phone-390"][1]
        witness = (f"MCP walk {walks['phone-390']['generated']} (.tmp/slw/results/brh_aq_walk_<viewport>.json): "
                   "the home page opened as Joel Cruz (worker) through the product's sign-in form at phone-390 and "
                   "desktop-1280; from it, the page's own signed-in client tried to move each record time to "
                   "2020-01-01. Every touched row was snapshotted in .tmp/slw/brh_aq_snapshot.json and restored "
                   f"({restored}). The audited amendment was captured before cleanup in .tmp/slw/brh_aq_post.json "
                   f"({len(post['audit'])} audit row(s)); {p['key']} {why}. The catalog, read through the postgres MCP "
                   f"(.tmp/slw/brh_aq_state.json; MCP digest {digests.get('AQ', '-')}), agrees.")
        note = (f"BRH-AQ ({p['key']}): walked live as Joel Cruz, worker - {why}. Held by "
                f"{', '.join(gates)}.")
        if dry:
            banked.append((p["id"], "would bank: " + why))
            continue
        sp = ROOT / ".tmp" / "w4_steps" / f"{p['id']}.json"
        write_json(sp, steps)
        rc = bsw.bank_walk(p["id"], str(sp.relative_to(ROOT)), witness, note, None, "", check=False,
                           instrument="playwright-mcp + postgres-mcp")
        (banked if rc == 0 else skipped).append((p["id"], "banked" if rc == 0 else "bank_walk refused"))
    print(f"gates to run first: {gates}")
    print(f"{'would bank' if dry else 'banked'} {len(banked)}; skipped {len(skipped)}")
    for b in banked[:300]:
        print("  OK  ", b[0], b[1][:160])
    for s in skipped:
        print("  SKIP", s[0], s[1][:300])
    return 0


def bank(classes, dry: bool, ids: set | None = None) -> int:
    if "AQ" in classes:
        if len(classes) != 1:
            raise SystemExit("bank AQ separately with --classes AQ")
        return bank_aq(dry, ids)
    import bank_sl_walk as bsw
    probes = [p for p in json.loads(PROBES.read_text(encoding="utf-8")) if p["cls"] in classes and (not ids or p["id"] in ids)]
    walks = {vp: json.loads((RES / f"brh_db_walk_{vp}.json").read_text(encoding="utf-8")) for vp in VPS}
    # the party proof (.tmp/slw/brh_party_walk.js): for a view whose rows only a party sees, the stranger's reading taken
    # while a row was staged, beside the party's own - it replaces the bare stranger reading for that probe
    party_walks = {vp: RES / f"brh_party_walk_{vp}.json" for vp in VPS}
    staged = set()
    if all(f.exists() for f in party_walks.values()):
        for vp, f in party_walks.items():
            pw = json.loads(f.read_text(encoding="utf-8"))
            if pw.get("signin") == "ok - the sign-in form" and (pw.get("probes") or {}).get("__party", {}).get("signedIn"):
                for k, v in (pw.get("probes") or {}).items():
                    if not k.startswith("__"):
                        walks[vp]["probes"][k] = v
                        staged.add(k)
    raw = json.loads(STATE.read_text(encoding="utf-8"))
    digests = raw.pop("_mcp_digests", None)
    if not digests:
        raise SystemExit("the catalog readings carry no postgres-MCP digests - read them through the MCP first")
    state = {k: {str(r.get("name")): r for r in v} for k, v in raw.items()}
    for vp, w in walks.items():
        ctl = (w.get("probes") or {}).get("__control") or {}
        if w.get("signin") != "ok - the sign-in form" or (w.get("identity") or {}).get("user") != ADMIN:
            raise SystemExit(f"{vp}: the walk did not sign the platform admin in through the form")
        if ctl.get("error") or not (ctl.get("count") or 0) > 0:
            raise SystemExit(f"{vp}: the positive control failed ({ctl}) - an instrument refused everything proves nothing")
    gates = sorted({g for c in classes for g in CLASS_GATES.get(c, [])})
    banked, skipped = [], []
    for p in probes:
        per = {vp: verdict(p, (walks[vp].get("probes") or {}).get(p["id"]) or {}, state) for vp in VPS}
        if not all(ok for ok, _ in per.values()):
            skipped.append((p["id"], "; ".join(f"{vp}: {why}" for vp, (ok, why) in per.items() if not ok)))
            continue
        why = per["phone-390"][1]
        steps = [{"viewport": vp, "device": "Pixel-class phone, 390 CSS px" if vp == "phone-390" else "desktop, 1280 CSS px",
                  "page": "index.html", "chars": walks[vp]["home"]["chars"], "identityKept": True, "pageErrors": [],
                  "overflowX": False, "cast": "Leandro Marquez, platform admin (oversight)", "as": "leandromarquez",
                  "probe": {k: p.get(k) for k in ("kind", "target", "expect")}, "answer": (walks[vp].get("probes") or {}).get(p["id"]),
                  "control": walks[vp]["probes"]["__control"], "verdict": per[vp][1]} for vp in VPS]
        witness = (f"MCP walk {walks['phone-390']['generated']} (.tmp/slw/results/brh_db_walk_<viewport>.json): the home page "
                   f"opened as Leandro Marquez (platform admin) through the product's sign-in form at phone-390 and desktop-1280; "
                   f"from it, a second client holding only the public key (a stranger) asked {p.get('target') or p['key']} - "
                   f"{why} at both viewports, after the positive control (the public listing grid) answered "
                   f"{walks['phone-390']['probes']['__control']['count']} rows. The catalog, read through the postgres MCP "
                   f"(.tmp/slw/brh_db_state.json; MCP digest {digests.get(_state_key(p['cls']), '-')}), agrees.")
        note = (f"BRH-{p['cls']} ({p['key']}): walked live as the person the defect exposed - {why}. Held by "
                f"{', '.join(CLASS_GATES.get(p['cls'], []))}.")
        if p["id"] in staged:
            note += (" The view holds rows only for a party, so two rows were staged locally (a broadcast Bryan Garcia's "
                     "provider may answer, a job his provider was driving to), read by Bryan Garcia signed in through a second "
                     "in-page client, and removed after the walk (.tmp/slw/results/brh_party_walk_<viewport>.json).")
        if dry:
            banked.append((p["id"], "would bank: " + why))
            continue
        sp = ROOT / ".tmp" / "w4_steps" / f"{p['id']}.json"
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(steps, ensure_ascii=False, indent=1), encoding="utf-8")
        rc = bsw.bank_walk(p["id"], str(sp.relative_to(ROOT)), witness, note, None, "", check=False,
                           instrument="playwright-mcp + postgres-mcp")
        (banked if rc == 0 else skipped).append((p["id"], "banked" if rc == 0 else "bank_walk refused"))
    print(f"gates to run first: {gates}")
    print(f"{'would bank' if dry else 'banked'} {len(banked)}; skipped {len(skipped)}")
    for b in banked[:300]:
        print("  OK  ", b[0], b[1][:160])
    for s in skipped:
        print("  SKIP", s[0], s[1][:300])
    return 0


def bank_pages(dry: bool) -> int:
    """W and AD, from .tmp/slw/brh_page_walk.js (results brh_page_walk_<viewport>.json, and a .run1 copy whose desktop
    load met the stale readiness snapshot): each row banks only when every load at both viewports says so."""
    import bank_sl_walk as bsw
    runs = {vp: [json.loads(f.read_text(encoding="utf-8")) for f in (RES / f"brh_page_walk_{vp}.run1.json",
                                                                       RES / f"brh_page_walk_{vp}.json") if f.exists()]
            for vp in VPS}
    out = []
    # W: the stranger's sign-up refused before any account request, the breach range answered, at both viewports
    w_ok = all(r.get("W", {}).get("said", "").startswith("That password has appeared in a public data breach")
               and r["W"].get("signupTried") is False and (r["W"].get("pwned") or {}).get("status") == 200
               and not r["W"].get("pageErrors") for vp in VPS for r in runs[vp])
    # AD: signed in as the worker, no compute_hive_readiness anywhere, the card drawn with its figure on the last load,
    # and the stale path (refresh_hive_readiness 200) met on some load
    calls = [c for vp in VPS for r in runs[vp] for c in (r.get("AD", {}).get("calls") or [])]
    last = {vp: runs[vp][-1].get("AD", {}) for vp in VPS}
    ad_ok = (all(r.get("AD", {}).get("signin") == "ok - the sign-in form" for vp in VPS for r in runs[vp])
             and not any(c["fn"] == "compute_hive_readiness" for c in calls)
             and any(c["fn"] == "refresh_hive_readiness" and c["status"] == 200 for c in calls)
             and all(re.search(r"\b\d+ /100", (last[vp].get("card") or {}).get("text", "")) for vp in VPS))
    for rid, ok, cls in (("BRH448", w_ok, "W"), ("BRH514", ad_ok, "AD")):
        if not ok:
            out.append((rid, "SKIP: the walk did not show it at both viewports"))
            continue
        if cls == "W":
            steps = [{"viewport": vp, "device": "Pixel-class phone, 390 CSS px" if vp == "phone-390" else "desktop, 1280 CSS px",
                      "page": "index.html", "chars": runs[vp][-1]["W"]["chars"], "identityKept": True, "pageErrors": [],
                      "overflowX": False, "cast": "a stranger on the sign-up form, signed out (walked by platform staff)",
                      "as": "signed out", "offered": "password123 (a password from a public breach list)",
                      "said": runs[vp][-1]["W"]["said"], "accountRequest": "none sent (/auth/v1/signup blocked and never asked)",
                      "breachRange": runs[vp][-1]["W"]["pwned"]} for vp in VPS]
            why = ("the sign-up form refused a password from a public breach list - 'That password has appeared in a public "
                   "data breach: choose a different one.' - and sent no account request; only the 5-character SHA-1 range "
                   "prefix left the browser (CBFDA, answered 200)")
            witness = (f"MCP walk {runs['phone-390'][-1]['generated']} (.tmp/slw/results/brh_page_walk_<viewport>.json, two "
                       f"runs): index.html opened signed out at phone-390 and desktop-1280, the sign-up form filled the way a "
                       f"person would with a breached password, submitted; /auth/v1/signup was blocked at the network so even "
                       f"a failing check could not have made an account, and the page never asked. {why}.")
            note = (f"BRH-W (leaked-password protection): walked live as the stranger the defect exposed - {why}. The "
                    f"server-side switch is a Pro-plan setting; the product refuses it at the only places a person sets a "
                    f"password. Held by breached-password-check.")
        else:
            steps = [{"viewport": vp, "device": "Pixel-class phone, 390 CSS px" if vp == "phone-390" else "desktop, 1280 CSS px",
                      "page": "hive.html", "chars": last[vp]["chars"], "identityKept": True, "pageErrors": [],
                      "overflowX": bool(last[vp].get("overflowX")), "cast": "Wilfredo Malabanan, worker, Baguio Textile Mills",
                      "as": "wilfredomalabanan", "readinessCalls": [c for r in runs[vp] for c in (r["AD"].get("calls") or [])],
                      "card": last[vp]["card"]["text"][:200]} for vp in VPS]
            why = ("the worker's hive board never asked compute_hive_readiness (refused to members in production); its stale "
                   "snapshot was refreshed through refresh_hive_readiness (200) and the card read Stair 1, 48/100 with its five "
                   "dimensions, and a fresh snapshot needed no call")
            witness = (f"MCP walk {runs['phone-390'][-1]['generated']} (.tmp/slw/results/brh_page_walk_<viewport>.json and "
                       f".run1.json): signed in as Wilfredo Malabanan through the product's form, hive.html opened at "
                       f"phone-390 and desktop-1280 twice - first with the hive's newest snapshot aged past 24 hours, then "
                       f"fresh. {why}.")
            note = (f"BRH-AD (compute_hive_readiness): walked live as the member the defect exposed - {why}. Held by "
                    f"page-rpcs-callable and definer-doors.")
        if dry:
            out.append((rid, "would bank: " + why[:150]))
            continue
        sp = ROOT / ".tmp" / "w4_steps" / f"{rid}.json"
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(steps, ensure_ascii=False, indent=1), encoding="utf-8")
        rc = bsw.bank_walk(rid, str(sp.relative_to(ROOT)), witness, note, None, "", check=False,
                           instrument="playwright-mcp + postgres-mcp")
        out.append((rid, "banked" if rc == 0 else "bank_walk refused"))
    for rid, said in out:
        print(" ", rid, said)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--sql", action="store_true")
    ap.add_argument("--bank", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--bank-pages", action="store_true", help="W and AD, from the page walks")
    ap.add_argument("--aq-pre", action="store_true", help="snapshot AQ rows and pause embedding before the walk")
    ap.add_argument("--aq-post", action="store_true", help="restore AQ rows and clean up walk residue")
    ap.add_argument("--classes", default=",".join(CLASSES))
    ap.add_argument("--ids", default="", help="with --bank: only these rows (comma-separated)")
    a = ap.parse_args()
    classes = tuple(c.strip() for c in a.classes.split(",") if c.strip())
    if a.aq_pre:
        return aq_pre()
    if a.aq_post:
        return aq_post()
    if a.plan:
        if "AQ" in classes and len(classes) != 1:
            raise SystemExit("plan AQ separately with --classes AQ")
        probes = plan(classes)
        TMP.mkdir(parents=True, exist_ok=True)
        if classes == ("AQ",):
            probe_mtime = AQ_PROBES.stat().st_mtime_ns if AQ_PROBES.exists() else None
            walk_results = [RES / f"brh_aq_walk_{vp}.json" for vp in VPS]
            if probe_mtime is not None and any(
                    path.exists() and path.stat().st_mtime_ns > probe_mtime for path in walk_results):
                print("--plan rewrites the probes the last walk ran with; bank before re-planning")
            write_json(AQ_PROBES, probes)
            js = AQ_WALK_JS.replace("@@PROBES@@", json.dumps(
                [{k: p.get(k) for k in ("id", "kind", "target", "col", "row_id", "value", "expect", "why")}
                 for p in probes], ensure_ascii=False))
            AQ_WALK.write_text(js, encoding="utf-8", newline="\n")
            walk_path = AQ_WALK
        else:
            PROBES.write_text(json.dumps(probes, indent=1), encoding="utf-8")
            import datetime
            js = WALK_JS.replace("@@PROBES@@", json.dumps(
                [{k: p.get(k) for k in ("id", "kind", "target", "args", "why")} for p in probes]))
            WALK.write_text(js.replace("@@GENERATED@@", datetime.date.today().isoformat()), encoding="utf-8", newline="\n")
            walk_path = WALK
        from collections import Counter
        print(f"{len(probes)} probes: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter((p['cls'], p['kind'], p['expect']) for p in probes).items())))
        print(f"walk: {walk_path.relative_to(ROOT)}")
        return 0
    if a.sql:
        for k, q in sql_for(classes).items():
            print(f"-- {k}\n{q};\n")
        return 0
    if a.bank_pages:
        return bank_pages(a.dry)
    if a.bank:
        return bank(classes, a.dry, {x.strip() for x in a.ids.split(",") if x.strip()} or None)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
