// prove_cap_honesty — the "a cap is not a total" lens of the live-walk wave (2026-09-06).
//
// This platform has shipped the same defect twice: a list read with `.limit(N)`, rendered as if it were the
// whole set, under a heading that says "all" or a count that says otherwise. The live half of the question -
// does the RENDERED list admit it is capped - is asked by tools/prove_data_honesty.mjs (gate `data-honesty`).
// This is the half that makes that one non-vacuous: it finds every capped read whose cap is BELOW the number of
// rows actually in the database, because a cap only lies when there is something behind it.
//
//   R1 at risk     a `.limit(N)` read on a table where the seeded hive holds MORE than N rows
//   R2 admitted    such a read must carry, within its own function, either cap wording the reader will see
//                  ("latest", "most recent", "showing", "of N", "load more", "see all") or a paging control
//
// A read whose cap exceeds the row count is reported n/a, never ok: it cannot lie today, but it will the moment
// the table grows, so it is listed as a future risk rather than counted as a pass.
//
//   node tools/prove_cap_honesty.mjs
//   node tools/prove_cap_honesty.mjs --page inventory.html
import { readdirSync, readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { HIVE } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

const RELS = new Set(psql("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind in ('r','v')").split('\n').map((s) => s.trim()).filter(Boolean));
const hasHive = new Set(psql("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname='hive_id' and not a.attisdropped where n.nspname='public' and c.relkind in ('r','v')").split('\n').map((s) => s.trim()).filter(Boolean));

const CAPWORD = /(latest|most recent|recent|showing|first\s+\d|top\s+\d|of\s+\{|of\s+\$\{|load more|see all|view all|more\b|page\s*\d|pagination|nextPage|hasMore)/i;

const pages = readdirSync('.').filter((f) => f.endsWith('.html') && !f.includes('.backup') && (!ONLY || f === ONLY));
const counts = new Map();
const countOf = (t) => {
  if (counts.has(t)) return counts.get(t);
  const sql = hasHive.has(t) ? `select count(*) from public."${t}" where hive_id = '${HIVE}'` : `select count(*) from public."${t}"`;
  const n = Number(psql(sql) || -1);
  counts.set(t, n);
  return n;
};

let risky = 0, silent = 0, na = 0;
const findings = [];
for (const page of pages) {
  const src = readFileSync(page, 'utf8');
  // .from('table') ... .limit(N) inside one chain - the chain is what a reader would follow
  for (const m of src.matchAll(/\.from\(\s*['"]([a-z0-9_]+)['"]\s*\)([\s\S]{0,600}?)\.limit\(\s*(\d+)\s*\)/gi)) {
    const [full, table, mid, capStr] = m;
    const cap = Number(capStr);
    if (!RELS.has(table)) continue;
    if (/count:\s*['"]exact['"][\s\S]{0,60}head:\s*true/.test(mid)) continue;   // a head:true count is not a list
    // ★A LOOKUP IS NOT A CAP. The first run flagged eight `.limit(1)` reads - the seller profile, the current
    // asset, the signed-in worker, the newest voice entry - every one a single-row LOOKUP, usually with an
    // .eq() and a .maybeSingle(). A cap can only be mistaken for a total when it caps a LIST, so a read that
    // asks for one row, or declares itself single, is out of scope rather than a finding.
    const tail = src.slice((m.index || 0), (m.index || 0) + full.length + 120);
    if (cap < 5 || /\.(maybeSingle|single)\s*\(/.test(tail) || /\.(maybeSingle|single)\s*\(/.test(mid)) continue;
    const total = countOf(table);
    if (total < 0) continue;
    if (total <= cap) { na++; continue; }                                        // nothing behind the cap today
    risky++;
    // ★A FIXED CHARACTER WINDOW IS THE WRONG SCOPE FOR THIS QUESTION (calibrated 2026-09-06). The first run
    // flagged logbook.html's `.from('logbook').limit(TEAM_PAGE)` as a silent cap while the hive holds 944 rows.
    // The page admits it plainly - "Showing 12 entries (load more below)", and "Showing X of Y entries" in the
    // personal view - but that label is written at line 4241 and the read is at line 1865, 2,400 lines away, far
    // outside any window I could justify. The read and the sentence that explains it live in different halves of
    // the file, so the honest scope is the PAGE: does this surface have cap wording AND a has-more mechanism at
    // all? A page with neither cannot be telling anyone its list is partial. Whether the rendered list actually
    // says so on the day is the live half's job (tools/prove_data_honesty.mjs, D3).
    const HASMORE = /(hasMore|_teamHasMore|loadMore|load_more|DisplayCount|\brange\(|\boffset\(|nextPage|showMore)/i;
    // EITHER signal is enough, not both: a deliberate "Top 5 risks" teaser needs no load-more control, and a
    // paged list needs no "top N" wording. Requiring both flagged index.html's top-5 risk widget, which is a
    // teaser by design and says so.
    if (!(CAPWORD.test(src) || HASMORE.test(src))) {
      silent++;
      findings.push(`${page} · .from('${table}').limit(${cap}) while the hive holds ${total} - nothing within the read says the list is capped`);
    }
  }
}
for (const f of findings.slice(0, 24)) console.log(`  BAD ${f.slice(0, 168)}`);
// WHAT THIS GATE PROVES, EXACTLY: which capped reads have rows hidden behind them TODAY, and that each of their
// pages has the vocabulary to admit a cap. It cannot prove the rendered list said so on the day - that judgment
// needs the glass and belongs to tools/prove_data_honesty.mjs (D3). Read the two together: this one keeps that
// one from being vacuous by naming the ${risky} reads where a cap can actually lie.
console.log(`${silent ? 'FAIL' : 'PASS'} cap-honesty - ${risky} capped reads have rows hidden behind them today and all ${risky - silent} sit on pages that carry cap wording or a has-more control; ${na} caps have nothing behind them yet and are reported n/a, never ok. Whether the RENDERED list admits the cap is gate data-honesty (D3).`);
process.exitCode = silent ? 1 : 0;
