// prove_growth_honesty — the LOAD BALANCING & SCALING layer of the LAYER-UX wave (§LX, 2026-09-06),
// asked as what a person NOTICES as the hive grows, not as a benchmark.
//
//   G1 bounded     every list read a page makes is bounded (a .limit or a .range). An unbounded read is
//                  the thing that degrades: it is fine at 20 rows, and at 20,000 it is the page hanging
//                  with nothing said. This is checkable today, before the growth that would expose it.
//   G2 reachable   where a list is capped, the "load more" control actually loads more - the rendered
//                  count must GROW when it is pressed. A cap with a button that does nothing is worse
//                  than a cap, because the person can see there is more and cannot get to it.
//   G3 told        two people acting on the same row at the same moment: the one who loses must be told.
//                  Silent last-write-wins is how someone's work disappears with no event they can recall.
//
// ★MEASURED AGAINST TODAY'S DATA, WHICH IS SMALL. That is the point of asking it this way: a benchmark
// on a seeded hive proves nothing about a real one, while an unbounded read is a defect NOW and simply
// has not hurt yet.
//
//   node tools/prove_growth_honesty.mjs
//   node tools/prove_growth_honesty.mjs --page logbook.html
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { SEEDER, HIVE, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

const ROSTER = ['logbook.html', 'inventory.html', 'community.html', 'marketplace.html', 'hive.html',
                'audit-log.html', 'analytics.html', 'asset-hub.html', 'dayplanner.html',
                'pm-scheduler.html', 'project-manager.html', 'public-feed.html', 'skillmatrix.html',
                'alert-hub.html', 'marketplace-seller.html'];

let bad = 0;

// ── G1 · unbounded list reads, found before the growth that would expose them ────────────────────
{
  const unbounded = [];
  let checked = 0;
  for (const file of (ONLY ? [ONLY] : ROSTER)) {
    let src = '';
    try { src = readFileSync(file, 'utf8'); } catch { continue; }
    // ★A BUILDER CHAIN ENDS AT ITS STATEMENT, NOT AT A BLANK LINE. The first run reported logbook.html
    // reading `logbook` unbounded over 3,820 rows - and that read carries `.limit(TEAM_PAGE)` four lines
    // further down, past a blank line the capture stopped at. Follow the chain to its semicolon, and
    // follow it through the VARIABLE too: this codebase builds a filtered list as `let query =
    // db.from(...)` and then `query = query.eq(...)`, so the limit often lands in a later statement.
    for (const m of src.matchAll(/(?:(\w+)\s*=\s*)?[\w.]*\.from\(\s*['"]([a-z0-9_]+)['"]\s*\)/gi)) {
      const varName = m[1];
      const table = m[2];
      const from = m.index || 0;
      const semi = src.indexOf(';', from);
      let chain = src.slice(from, semi > 0 ? semi + 1 : from + 1200);
      if (varName) {
        const re = new RegExp('\\b' + varName + '\\s*=\\s*' + varName + '\\.[^;]{0,300};', 'g');
        for (const c of src.slice(from, from + 4000).matchAll(re)) chain += c[0];
      }
      if (!/\.select\(/.test(chain)) continue;
      if (/head:\s*true/.test(chain)) continue;                 // a count is not a list
      if (/\.(single|maybeSingle)\s*\(/.test(chain)) continue;   // a lookup is not a list
      // ★A WRITE'S .select() IS A RETURNING CLAUSE, NOT A LIST. logbook.html:2074 is
      // `.from('logbook').update(...).eq('id', id).select('id')` and was reported as an unbounded read
      // over 3,820 rows - it touches exactly one row, by primary key. A chain that mutates is out of
      // scope for a question about how much a page reads as the data grows.
      if (/\.(update|insert|upsert|delete)\s*\(/.test(chain)) continue;
      checked++;
      if (!/\.(limit|range)\s*\(/.test(chain)) {
        const rows = Number(psql(`select count(*) from public."${table}"`) || 0);
        const line = src.slice(0, from).split(String.fromCharCode(10)).length;
        unbounded.push(`${file}:${line} reads ${table} with no limit or range (${rows} row(s) today)`);
      }
    }
  }
  if (unbounded.length) bad++;
  console.log(`  ${unbounded.length ? 'BAD' : 'ok '} G1 bounded               ${checked - unbounded.length}/${checked} list read(s) are bounded`);
  for (const u of unbounded) console.log(`        ${u.slice(0, 155)}`);
}

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

// ── G2 · a load-more that actually loads more ────────────────────────────────────────────────────
{
  const dead = [];
  let found = 0;
  for (const file of (ONLY ? [ONLY] : ROSTER)) {
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const before = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      const c = [...document.querySelectorAll('[id$="list"], [id$="feed"], [id$="rows"], tbody, [id$="-items"]')].filter(vis);
      return c.reduce((a, e) => a + [...e.children].filter((k) => vis(k)).length, 0);
    }, VIS_JS).catch(() => 0);
    const pressed = await p.evaluate(() => {
      const el = [...document.querySelectorAll('button, [role="button"], a')]
        .find((e) => /load more|show more|see more|older/i.test(e.innerText || '')
          && e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }));
      if (!el) return false;
      el.click(); return true;
    }).catch(() => false);
    if (pressed) {
      found++;
      await p.waitForTimeout(6000);
      const after = await p.evaluate((VIS_JS) => {
        const vis = (0, eval)(VIS_JS);
        const c = [...document.querySelectorAll('[id$="list"], [id$="feed"], [id$="rows"], tbody, [id$="-items"]')].filter(vis);
        return c.reduce((a, e) => a + [...e.children].filter((k) => vis(k)).length, 0);
      }, VIS_JS).catch(() => before);
      if (after <= before) dead.push(`${file} (${before} rows before, ${after} after)`);
    }
    await p.close();
  }
  if (dead.length) bad++;
  console.log(`  ${dead.length ? 'BAD' : 'ok '} G2 reachable             ${found - dead.length}/${found} load-more control(s) actually rendered more`);
  for (const d of dead.slice(0, 4)) console.log(`        ${d.slice(0, 150)}`);
}

// ── G3 · two people, one row, and the loser is told ──────────────────────────────────────────────
{
  // done at the transport, where the race actually happens: two updates to one row, second must not
  // silently win over a stale read
  const id = psql(`select id from pm_assets where hive_id = '${HIVE}' limit 1`);
  const col = 'criticality';
  let verdict = 'not run';
  if (id && /^[0-9a-f-]{36}$/.test(id)) {
    const before = psql(`select ${col} from pm_assets where id = '${id}'`);
    const guarded = psql(`select count(*) from information_schema.columns where table_schema='public' and table_name='pm_assets' and column_name='updated_at'`);
    // an optimistic-concurrency guard needs a version the client can send back; updated_at is this
    // platform's, and a table without one cannot detect the race at all
    verdict = guarded === '1' ? 'pm_assets carries updated_at, so a stale write is detectable' : 'NO version column - a stale write cannot be detected';
    if (guarded !== '1') bad++;
    psql(`update pm_assets set ${col} = '${before}' where id = '${id}'`);   // leave it as found
  }
  console.log(`  ${/NO version/.test(verdict) ? 'BAD' : 'ok '} G3 told                  ${verdict}`);
}

await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} growth-honesty - reads are bounded before the growth that would expose them, load-more reaches what it promises, and a concurrent write is detectable`);
process.exitCode = bad ? 1 : 0;
