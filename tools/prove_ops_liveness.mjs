// prove_ops_liveness — the OPS & OBSERVABILITY family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "ops & observability" lists ~51 rows whose lens is "health is a living
// producer", "the gate actually runs", cron liveness, log correlation and SLO. A dashboard is a claim that
// somebody is watching; a PANEL whose query returns nothing is that claim with no producer behind it - the
// observability equivalent of a trust chip no query enforces. The only way to know is to run every panel's own
// query against its own datasource and see whether anything comes back.
//
// What it does:
//   1. asks Grafana for every dashboard and every panel's SQL (the same API the grafana MCP speaks)
//   2. expands the Grafana macros a panel relies on ($__timeFilter, $__timeGroup, $__interval, $__unixEpoch)
//   3. runs each query against the local Postgres the datasource points at
//   4. a panel is LIVE when its query returns at least one row carrying a non-null value
//
// A panel that ERRORS is worse than an empty one and is reported separately: an empty panel may be an honest
// "nothing happened yet", but a query that cannot run is a dashboard nobody has opened since the schema moved.
//
//   node tools/prove_ops_liveness.mjs                 # every dashboard
//   node tools/prove_ops_liveness.mjs --dash workhive-slo-arct
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const cfg = JSON.parse(readFileSync('.mcp.json', 'utf8')).mcpServers.grafana.env;
const GRAFANA = (process.env.GRAFANA_URL || cfg.GRAFANA_URL).replace('host.docker.internal', '127.0.0.1');
const KEY = process.env.GRAFANA_API_KEY || cfg.GRAFANA_API_KEY;
const ONLY = (() => { const i = process.argv.indexOf('--dash'); return i >= 0 ? process.argv[i + 1] : null; })();
const WINDOW = "90 days";   // panels default to a short range; the question is whether a producer exists at all

const api = async (path) => {
  const r = await fetch(GRAFANA + path, { headers: { Authorization: 'Bearer ' + KEY, Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
};
// ★A PANEL'S QUERY BELONGS TO ITS OWN DATASOURCE. The first clean run reported six BROKEN panels on the
// GlitchTip dashboard - "relation issue_events_issue does not exist" - because I ran every query against
// Supabase. GlitchTip is a SEPARATE Postgres in its own container; asking one database for another's tables
// is the instrument being wrong, and it looked exactly like a dead dashboard.
const DB = {
  supabase_local: { container: 'supabase_db_workhive', user: 'postgres', db: 'postgres' },
  glitchtip_local: { container: 'workhive_glitchtip_postgres', user: 'glitchtip', db: 'glitchtip' },   // its POSTGRES_USER, not postgres - that role does not exist in this image
};
const psql = (sql, dsUid) => {
  const d = DB[dsUid] || DB.supabase_local;
  return execSync(`docker exec -i ${d.container} psql -U ${d.user} -d ${d.db} -tA -c "${sql.replace(/"/g, '\\"')}"`,
    { encoding: 'utf8', timeout: 40000, stdio: ['pipe', 'pipe', 'pipe'] });
};

// ★A PANEL'S SQL IS NOT VALID SQL - it is SQL plus Grafana's macros, and expanding them is part of the
// instrument. Getting this wrong makes every panel look broken, which is the loudest possible false reading.
const expand = (sql) => sql
  .replace(/\$__timeFilter\(\s*([a-z0-9_."]+)\s*\)/gi, (_, c) => `${c} > now() - interval '${WINDOW}'`)
  .replace(/\$__timeGroup\(\s*([a-z0-9_."]+)\s*,\s*'([^']+)'\s*\)/gi, (_, c, iv) => `date_trunc('${/\d+h/i.test(iv) ? 'hour' : /\d+d/i.test(iv) ? 'day' : 'hour'}', ${c})`)
  .replace(/\$__unixEpochFilter\(\s*([a-z0-9_."]+)\s*\)/gi, (_, c) => `${c} > extract(epoch from now() - interval '${WINDOW}')`)
  .replace(/\$__interval/gi, "'1 hour'")
  .replace(/\$__timeFrom\(\)/gi, `(now() - interval '${WINDOW}')`)
  .replace(/\$__timeTo\(\)/gi, 'now()');

const dashboards = (await api('/api/search?type=dash-db')).filter((d) => !ONLY || d.uid === ONLY);
let dead = 0, broken = 0, live = 0, skipped = 0;
for (const d of dashboards) {
  const full = await api(`/api/dashboards/uid/${d.uid}`);
  const panels = [];
  const walk = (list) => { for (const p of list || []) { if (p.panels) walk(p.panels); if (p.targets) panels.push(p); } };
  walk(full.dashboard.panels);
  const issues = [];
  for (const p of panels) {
    for (const t of p.targets) {
      const sql = t.rawSql || t.expr;
      if (!sql || typeof sql !== 'string') { skipped++; continue; }
      if (/\$\{?\w+(:\w+)?\}?/.test(sql.replace(/\$__\w+/g, ''))) { skipped++; continue; }   // a template variable we cannot bind
      let out;
      const dsUid = (t.datasource && t.datasource.uid) || (p.datasource && p.datasource.uid) || 'supabase_local';
      try { out = psql(expand(sql), dsUid); }
      catch (e) {
        broken++; issues.push(`BROKEN ${p.title} :: ${String(e.stderr || e.message).split('\n').find((l) => /ERROR/.test(l)) || 'query failed'}`);
        continue;
      }
      const rows = out.split('\n').map((l) => l.trim()).filter(Boolean);
      const hasValue = rows.some((r) => r.split('|').some((c) => c !== '' && c !== 'null'));
      if (!rows.length || !hasValue) { dead++; issues.push(`EMPTY  ${p.title} :: the query runs and returns nothing - no producer behind this panel`); }
      else live++;
    }
  }
  console.log(`  ${issues.length ? 'BAD ' : 'ok  '} ${d.uid.padEnd(22)} ${panels.length} panel(s)${issues.length ? ` · ${issues.length} without a producer` : ''}`);
  for (const s of issues.slice(0, 8)) console.log(`        ${s.slice(0, 160)}`);
}
const ok = broken === 0 && dead === 0;
console.log(`${ok ? 'PASS' : 'FAIL'} ops-liveness - ${live}/${live + dead + broken} dashboard panels have a living producer (${broken} query error(s), ${dead} empty, ${skipped} skipped for unbound template variables) @ ${GRAFANA}`);
process.exit(ok ? 0 : 1);
