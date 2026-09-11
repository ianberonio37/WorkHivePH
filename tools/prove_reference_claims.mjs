// prove_reference_claims — P-I "a claim a query enforces" on the reference surfaces (2026-09-05).
//
// A number a reference page paints as a claim ("1,094 validators", "1055 pass · 39 fail", "Purity: 92%",
// "37 canonical keys", "12 guides") is honest only if it equals what the SOURCE the page cites says
// right now. This prover opens each page, reads the painted figure from the DOM, computes the same
// figure from the source file, and requires equality. A claim with no computable source is n/a.
//   node tools/prove_reference_claims.mjs            # all; exit 1 on any mismatch
//   node tools/prove_reference_claims.mjs --page design-system.html
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn as harnessSignIn, psql, psqlAs } from './prover_harness.mjs';   // shared preamble + DB truths (2026-09-05)
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
// Truth views that carry an admin/member predicate (v_service_credit_topups_truth, v_gcash_receipts_needing_eyes) return
// NOTHING to a plain postgres session - the count must be taken AS the signed-in person (SET LOCAL ROLE authenticated +
// jwt claims, rolled back), exactly like the psql recipes (2026-09-05: the badge painted 1 while a plain count said 0).
const num = (t) => { const m = String(t || '').replace(/,/g, '').match(/-?\d+(\.\d+)?/); return m ? Number(m[0]) : null; };
const json = (f) => JSON.parse(readFileSync(f, 'utf8'));

const CLAIMS = [
  {
    file: 'validator-catalog.html', wait: 6000,
    read: () => ({
      validators: (document.querySelector('#meta strong') || {}).textContent,
      pass: (document.getElementById('pass-stat') || {}).textContent,
      fail: (document.getElementById('fail-stat') || {}).textContent,
    }),
    truth: () => { const h = json('platform_health.json'); const v = h.validators || []; return { validators: v.length, pass: v.filter((x) => x.status === 'PASS').length, fail: v.filter((x) => x.status === 'FAIL').length }; },
  },
  {
    file: 'founder-console.html', wait: 9000, signin: true,
    read: () => { const t = (document.body.innerText || '').replace(/\s+/g, ' '); const m = t.match(/(\d[\d,]*) pass · (\d[\d,]*) fail/); return { pass: m ? m[1] : null, fail: m ? m[2] : null }; },
    truth: () => { const h = json('platform_health.json'); const v = h.validators || []; return { pass: v.filter((x) => x.status === 'PASS').length, fail: v.filter((x) => x.status === 'FAIL').length }; },
  },
  {
    file: 'design-system.html', wait: 6000,
    read: () => { const t = (document.getElementById('ds-axes') || {}).innerText || ''; const p = t.match(/Purity:\s*(\d+)%/); const k = t.match(/(\d+)\s+canonical keys/); return { purity: p ? p[1] : null, canonical: k ? k[1] : null }; },
    truth: () => { const pu = json('component_purity_baseline.json'); const files = pu.files || {}; const total = Object.keys(files).length; const pure = Object.values(files).filter((v) => v === 0).length; const st = json('storage_key_registry.json'); return { purity: total ? Math.round(100 * pure / total) : 0, canonical: (st.canonical || []).length }; },
  },
  {
    file: 'learn/index.html', wait: 4000,
    read: () => ({ guides: document.querySelectorAll('#lh-grid > *').length }),
    truth: () => { const src = readFileSync('learn/index.html', 'utf8'); const i = src.indexOf('id="lh-grid"'); const seg = src.slice(i, src.indexOf('</section>', i) > 0 ? src.indexOf('</section>', i) : i + 40000); return { guides: (seg.match(/<a [^>]*class="[^"]*\b(card|pillar|tile)\b[^"]*"/g) || []).length || null }; },
    note: 'the grid count is read from the same file; a null truth means the card markup has no stable class and the claim is n/a',
  },
  // P355 platform-actions (2026-09-05): five queue badges vs the database. The top-up/draft/seller reads are capped at
  // 50 and the badges say '50+' when full (num() reads 50, so the truth is least(count, 50)); the GCash badge paints
  // the exact server count; the feedback badge counts what is WAITING (new + triaged + in_progress) among the latest
  // 500 rows, so its truth is n/a when the table holds more than 500. An empty badge (a hidden zero-queue card) reads
  // as 0; an em-dash (a failed read) reads as null and mismatches on purpose.
  {
    file: 'platform-actions.html', wait: 12000, signin: true,
    // '-' is the untouched default of a zero-queue card that stays hidden; an em-dash (a failed read) stays null (2026-09-05)
    read: () => { const g = (id) => { const t = ((document.getElementById(id) || {}).textContent || '').trim(); return (t === '' || t === '-') ? '0' : t; };return { topups: g('svc-topups-count'), drafts: g('mkt-listings-count'), sellers: g('mkt-sellers-count'), gcash: g('gcash-receipts-count'), waiting: g('fb-count-badge') }; },
    truth: () => {
      const n = (q) => { const v = psqlAs('Leandro Marquez', q); return /^\d+$/.test(v) ? Number(v) : null; };   // as the signed-in admin
      const total = n('select count(*) from platform_feedback');
      return {
        topups: (() => { const v = n("select count(*) from v_service_credit_topups_truth where status = 'pending_verification'"); return v == null ? null : Math.min(v, 50); })(),
        drafts: (() => { const v = n("select count(*) from v_marketplace_listings_truth where status = 'draft'"); return v == null ? null : Math.min(v, 50); })(),
        sellers: (() => { const v = n('select count(*) from v_marketplace_sellers_truth where kyb_verified = false or cert_verified = false'); return v == null ? null : Math.min(v, 50); })(),
        gcash: n('select count(*) from v_gcash_receipts_needing_eyes'),
        waiting: (total == null || total > 500) ? null : n("select count(*) from platform_feedback where status in ('new','triaged','in_progress')"),
      };
    },
  },
  // P364 marketplace-seller-profile (2026-09-05): the 'listings' stat is the seller's PUBLISHED listings (read capped at 60).
  {
    file: 'marketplace-seller-profile.html', query: '?worker=Isidro%20Suarez', wait: 9000, signin: true,
    read: () => ({ listings: (document.getElementById('stat-listings') || {}).textContent }),
    truth: () => { const v = psql("select count(*) from v_marketplace_listings_truth where seller_name = 'Isidro Suarez' and status = 'published'"); return { listings: /^\d+$/.test(v) ? Math.min(Number(v), 60) : null }; },
  },
  // P349 agentic-rag-observability (2026-09-05): '#freshness' paints the exact server count of the active hive's traces in
  // the selected window (default 30 days: .eq('hive_id', HIVE_ID).gte('created_at', cutoff)); the DB must agree.
  {
    file: 'agentic-rag-observability.html', wait: 9000, signin: true,
    read: () => { const t = ((document.getElementById('freshness') || {}).textContent || '').replace(/,/g, ''); const m = t.match(/(\d+) traces? in the last (\d+) days?/i); return { traces: m ? m[1] : null, days: m ? m[2] : null }; },
    truth: () => { const v = psql("select count(*) from agentic_rag_traces where hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' and created_at >= now() - interval '30 days'"); return { traces: /^\d+$/.test(v) ? Number(v) : null, days: 30 }; },
  },
];

// P-I "honest interpretability" + P-K "health is a living producer" (2026-09-05): a painted figure must also say
// WHAT it counts (denominator / breakdown), WHEN (window or last-run stamp that matches the source), and the
// source must be alive (a last-run stamp older than STALE_DAYS is a dead producer the page must not call "Live").
const STALE_DAYS = 7;
const EXPLAIN = [
  { file: 'validator-catalog.html', wait: 6000, sel: '#meta',
    checks: (t, j) => { const h = j('platform_health.json'); const ts = String(h.timestamp || '').slice(0, 19).replace('T', ' '); const age = (Date.now() - Date.parse(h.timestamp)) / 864e5;
      return { 'last-run stamp == file': t.includes(ts), 'breakdown PASS/FAIL/WARN/SKIP': /PASS.*FAIL.*WARN.*SKIP/.test(t), 'window named': /refreshed|as of|updated|live/i.test(t), [`producer alive (<${STALE_DAYS}d, ${age.toFixed(1)}d)`]: age < STALE_DAYS }; } },
  { file: 'design-system.html', wait: 6000, sel: '#ds-axes',
    checks: (t, j) => { const pu = j('component_purity_baseline.json'); const files = pu.files || {}; const total = Object.keys(files).length; const pure = Object.values(files).filter((v) => v === 0).length;
      return { 'purity names N/M files': new RegExp(`\\b${pure}/${total}\\b\\s+shared-chrome files pure`).test(t), 'raw literals named': /raw brand literals/.test(t) }; } },
  { file: 'founder-console.html', wait: 9000, sel: '#sec-alive', signin: true,
    checks: (t, j) => { const h = j('platform_health.json'); const age = (Date.now() - Date.parse(h.timestamp)) / 864e5;
      return { 'tech tile names its source': /Platform Health|platform_health/i.test(t), 'tech tile says when the checks ran': /last run|as of|updated|ran /i.test(t), [`producer alive (<${STALE_DAYS}d, ${age.toFixed(1)}d)`]: age < STALE_DAYS }; } },
  { file: 'llm-observability.html', wait: 8000, sel: '#meta',
    checks: () => ({}), text: (t) => ({ 'window named': /last \d+ ?h|in last|as of/i.test(t), 'call count named': /\d+ calls?/.test(t) }) },
  { file: 'agentic-rag-observability.html', wait: 9000, sel: '#freshness', signin: true,
    checks: () => ({}), text: (t) => ({ 'window named': /in the last \d+ days/.test(t), 'count named': /\d+ traces/.test(t) }) },
  // P-I 'honest interpretability' on the DB pages (2026-09-05, P350/P353/P362/P365/P368/P371/P378): a status/source
  // region is present and names a window or freshness beside the figures it explains (signed in).
  { file: 'ai-quality.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  { file: 'marketplace-admin.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  { file: 'marketplace.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  { file: 'status.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  { file: 'ph-intelligence.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  { file: 'community.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  { file: 'platform-actions.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .freshness, .source-chip', signin: true,
    checks: () => ({}), text: (t) => ({ 'source/status region present': t.trim().length > 12, 'window or freshness named': /last \d+|as of|updated|live|refreshed|this shift|today|snapshot|in the last|every \d+/i.test(t) }) },
  // P-K 'health is a living producer' on plant-connections (P429, 2026-09-05): the gateway producer may be idle for
  // months locally - the page must SAY so ('No gateway calls in last 7 days · IDLE') when the table's newest row is
  // older than 7 days, and paint a fresh state otherwise. The check reads the table's age from the database.
  // P145 logbook (2026-09-05): its figures carry their window ('Production this shift' is the entry form's own field, 'today' /
  // 'this week' the summary strips); the prover requires a window phrase to sit in the same status/summary region as a figure.
  { file: 'logbook.html', wait: 9000, sel: '.wh-source-chip, [role="status"], #meta, .summary, .kpi-strip, .stat-strip, main', signin: true,
    checks: () => ({}), text: (t) => ({ 'window named beside figures': /this shift|today|this week|last \d+ days|refreshed on load/i.test(t) && /\d/.test(t) }) },
  { file: 'plant-connections.html', wait: 9000, sel: 'main, body', signin: true,
    checks: () => { const h = Number(psql("select coalesce(round(extract(epoch from now()-max(created_at))/3600), 99999) from gateway_audit_log")); return { ['gateway age read (' + h + 'h)']: Number.isFinite(h) && h > 0 }; },
    text: (t) => { const h = Number(psql("select coalesce(round(extract(epoch from now()-max(created_at))/3600), 99999) from gateway_audit_log")); const idle = h > 168; return { [idle ? 'page says the gateway is IDLE' : 'page shows gateway activity']: idle ? /No gateway calls in last 7 days|IDLE/i.test(t) : /gateway/i.test(t) && !/No gateway calls/i.test(t) }; } },
  { file: 'symbol-gallery.html', wait: 5000, sel: '#sym-count, .wh-source-chip',
    checks: () => ({}), text: (t) => ({ 'count named': /\d+ symbols?/i.test(t), 'source named': /drawing library|drawing-symbols/i.test(t) }) },
];

async function runExplain(ctx) {
  let bad = 0, n = 0, signed = false;
  for (const e of EXPLAIN) {
    if (ONLY && e.file !== ONLY) continue;
    if (e.signin && !signed) { await signIn(ctx); signed = true; }
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/${e.file}`, { waitUntil: 'load' }).catch(() => {});
    await p.waitForTimeout(e.wait);
    const t = await p.evaluate((sel) => [...document.querySelectorAll(sel)].map((x) => (x.innerText || '').replace(/\s+/g, ' ').trim()).join(' | '), e.sel).catch(() => '');
    await p.close();
    let res = {}; try { res = { ...e.checks(t, json), ...(e.text ? e.text(t) : {}) }; } catch (err) { res = { ['check error: ' + err.message]: false }; }
    const misses = Object.entries(res).filter(([, v]) => !v).map(([k]) => k);
    n++; if (misses.length) bad++;
    console.log(`  ${misses.length ? 'BAD' : 'ok '} ${e.file.padEnd(22)} explains: ${Object.keys(res).length - misses.length}/${Object.keys(res).length}${misses.length ? ' · misses: ' + misses.join('; ') : ''}${misses.length ? ' · text="' + t.slice(0, 110) + '"' : ''}`);
  }
  return { bad, n };
}

async function signIn(ctx) { return harnessSignIn(ctx); }

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
let bad = 0, n = 0, signed = false;
for (const c of CLAIMS) {
  if (ONLY && c.file !== ONLY) continue;
  if (c.signin && !signed) { await signIn(ctx); signed = true; }
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${c.file}${c.query || ''}`, { waitUntil: 'load' }).catch(() => {});   // a page that needs a query to render (seller profile)
  await p.waitForTimeout(c.wait);
  const painted = await p.evaluate(c.read).catch(() => ({}));
  await p.close();
  let truth; try { truth = c.truth(); } catch (e) { truth = { _error: e.message }; }
  const keys = Object.keys(truth).filter((k) => k !== '_error');
  const rows = keys.map((k) => { const a = num(painted[k]), t = truth[k]; const ok = t == null ? 'n/a' : (a === t ? 'ok' : 'MISMATCH'); return `${k}: painted=${a} truth=${t} ${ok}`; });
  const mism = rows.filter((r) => /MISMATCH/.test(r)).length;
  const applicable = rows.filter((r) => !/n\/a/.test(r)).length;
  if (applicable) n++;
  if (mism) bad++;
  console.log(`  ${mism ? 'BAD' : (applicable ? 'ok ' : 'n/a')} ${c.file.padEnd(22)} ${rows.join(' · ')}${truth._error ? ' · truth error: ' + truth._error : ''}`);
}
const ex = await runExplain(ctx);
bad += ex.bad; n += ex.n;
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} reference-claims - ${n - bad}/${n} reference pages paint the figure their source computes`);
process.exit(bad ? 1 : 0);
