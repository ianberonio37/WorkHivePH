// prove_count_matches_source.mjs — does a number on a product page equal its source of truth?
//
// THE ORACLE: "every visible number matches its source of truth." tests/surface-numbers.spec.ts already
// does this for the 4 MARKETPLACE surfaces; this is the same discipline over the 22 product pages.
//
// ★WHY THIS CANNOT BE A GENERIC HARNESS, stated up front because the roadmap says so explicitly: a
// generic checker cannot know a surface's truth query, so it ends up checking the STRUCTURAL half
// ("a number rendered, it isn't NaN") and calling that agreement. That is the shape of a bank that
// becomes decoration. Every check here is therefore HAND-AUTHORED from the page's own source: the
// selector and the SQL are written to match the query the page actually issues, and the comment on
// each records where that query lives, so a reader can check my reading rather than trust it.
//
// ★AND THE SCOPE IS READ FROM THE PAGE, NOT HARDCODED. logbook counts `worker_name = WORKER_NAME` and
// `hive_id = HIVE_ID or hive_id is null`. Hardcoding an identity into the SQL would compare the page's
// number against a DIFFERENT question and call a mismatch a defect. So the page is asked for its own
// scope variables at runtime and the truth query is parameterised with them: the comparison is between
// what THIS page displays and what is true FOR THE IDENTITY IT IS ACTUALLY USING.
//
// A CHECK THAT CANNOT RUN FAILS; it never skips. A number still rendering its placeholder em-dash is
// NOT agreement — the page is saying "I do not know", and a comparison that never happened must never
// read as one. Same rail as the marketplace spec it extends.
//
// WHY `#machine-count` IS DELIBERATELY ABSENT from logbook's checks: it is `allMachines.size`, computed
// from the LOADED WINDOW rather than from a count query (logbook.html:3650), so it is a true statement
// about what is on screen and NOT a claim about the database. Asserting it against a DB distinct-count
// would manufacture a failure out of a capped window. Recorded here rather than silently omitted.
//
// USAGE:  node tools/prove_count_matches_source.mjs [--page <name>]
// OUTPUT: count_matches_source_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { execFileSync } from 'node:child_process';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

/** One number as psql sees it — runs as postgres, so it reads the truth, not a role's view of it. */
const truth = (sql) => {
  const out = execFileSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql',
    '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8', timeout: 60000 }).trim();
  const n = Number(out.split('\n')[0]);
  if (!Number.isFinite(n)) throw new Error(`truth query did not return a number: ${out.slice(0, 120)}`);
  return n;
};

// ★THE SCOPE IS TAKEN FROM THE PAGE'S OWN REQUEST, NOT FROM `window`. The first version read
// window.WORKER_NAME / window.HIVE_ID and got null for both: they are module-scoped consts inside the
// page's IIFE and were never globals, so the probe could not see them (the page-scoped-symbols trap).
// Reconstructing the identity from a fixture would have been worse than useless — it would compare the
// page's number against a DIFFERENT question and report the difference as a defect.
// So the scope is parsed out of the PostgREST URL the page actually issued. That is strictly better
// than either alternative: the truth query is then built from the very filters the page sent, so a
// mismatch can only mean the DB and the display disagree — never that I asked a different question.
const scopeFromRequests = (urls, relation) => {
  // NOT `count=exact` — that travels in the Prefer HEADER, never the query string, and looking for it
  // in the URL silently picked the page's FIRST logbook request (a hive-scoped id list) instead of the
  // count query. The count requests are the ones carrying the identity filter, so select on that.
  // The identity filter is not always called `worker_name` — community scopes its own-posts read by
  // `author_name`, and selecting only on worker_name picked the page's FEED read instead, which
  // carries no identity at all. Both names are accepted, and the request carrying one is preferred.
  const hit = urls.find((u) => u.includes(`/rest/v1/${relation}?`) && /(worker_name|author_name)=eq\./.test(u))
           || urls.find((u) => u.includes(`/rest/v1/${relation}?`));
  if (!hit) return null;
  const qs = new URLSearchParams(hit.split('?')[1] || '');
  const eqv = (k) => { const v = qs.get(k); return v && v.startsWith('eq.') ? decodeURIComponent(v.slice(3)) : null; };
  const or = qs.get('or') || '';
  const hiveM = /hive_id\.eq\.([0-9a-f-]{36})/i.exec(or);
  return { worker: eqv('worker_name') || eqv('author_name'), hive: hiveM ? hiveM[1] : qs.get('hive_id') && qs.get('hive_id').startsWith('eq.') ? qs.get('hive_id').slice(3) : null, from: hit };
};

const q = (s) => `'${String(s).replace(/'/g, "''")}'`;

const CHECKS = {
  // public-feed states its count STRUCTURALLY - one card per public post, no total rendered anywhere.
  // The discriminator is the whole post set (112): a read that lost its `public` predicate would show
  // that instead, so a pass here cannot be a coincidence of a small dataset.
  'public-feed': [
    { label: 'rendered public post cards', countSelector: '.post-card',
      // ★THE PREDICATE IS TAKEN FROM THE WIRE, NOT FROM THE PAGE'S NAME. The observed request is
      // `public=eq.true&flagged=eq.false` - so the oracle is BOTH clauses. Filtering on `public`
      // alone happens to give the same 15 today only because zero public posts are currently
      // flagged; the moment one were, the page would correctly render 15 and this check would
      // claim 16 and report a FALSE RED against a page doing exactly the right thing. An oracle
      // that is not the page's own predicate is the wrong oracle even while it agrees.
      sql: () => 'select count(*) from v_community_posts_truth where public and not flagged',
      discriminator: { label: 'ALL posts (what a lost public predicate would render)',
                       sql: () => 'select count(*) from v_community_posts_truth' } },
    { label: 'flagged public posts are withheld', countSelector: '.post-card',
      sql: () => 'select count(*) from v_community_posts_truth where public and not flagged',
      discriminator: { label: 'public INCLUDING flagged (what a lost moderation filter would render)',
                       sql: () => 'select count(*) from v_community_posts_truth where public' } },
  ],
  logbook: [
    {
      label: 'total entries pill',
      selector: '#total-count',
      // logbook.html:3665 — db.from('logbook').select('*',{count:'exact',head:true})
      //   .eq('worker_name', WORKER_NAME) [.or(`hive_id.eq.${HIVE_ID},hive_id.is.null`)]
      sql: ({ worker, hive }) => `select count(*) from logbook where worker_name = ${q(worker)}`
        + (hive ? ` and (hive_id = ${q(hive)} or hive_id is null)` : ''),
    },
    {
      label: 'open entries pill',
      selector: '#open-count',
      // logbook.html:3666 — the same query plus .eq('status','Open')
      sql: ({ worker, hive }) => `select count(*) from logbook where worker_name = ${q(worker)}`
        + ` and status = 'Open'` + (hive ? ` and (hive_id = ${q(hive)} or hive_id is null)` : ''),
    },
  ],
  // ── inventory ────────────────────────────────────────────────────────────────────────────────────
  // SCOPE DETERMINED BY MEASUREMENT, NOT BY READING. The page issues TWO v_inventory_items_truth
  // reads - one hive+status, one hive+worker - and only one feeds the pills. hive+worker returns 7;
  // the page shows 27, which is the hive+status set. Guessing would have produced a 27-vs-7 "defect"
  // that was really me asking the wrong question.
  inventory: [
    { label: 'total parts pill', selector: '#stat-total',
      // inventory.html:1020 — items.length over the loaded set (limit 2000; 27 rows, so complete)
      sql: ({ hive }) => `select count(*) from v_inventory_items_truth where hive_id = ${q(hive)}`
        + ` and status in ('approved','pending','rejected')` },
    { label: 'low-stock pill', selector: '#stat-low',
      // inventory.html:748-756 — the view's OWN derived flag, is_low_stock = min_qty > 0 AND
      // qty_on_hand <= min_qty. The page prefers this flag over local math precisely so the home
      // tile and this pill stay in lockstep. Checking against the flag is therefore checking the
      // page's real contract, and it DISCRIMINATES the domain rule: a hardcoded `qty <= 1`
      // threshold would show 0 here, not 3.
      sql: ({ hive }) => `select count(*) from v_inventory_items_truth where hive_id = ${q(hive)}`
        + ` and status in ('approved','pending','rejected') and is_low_stock` },
    { label: 'out-of-stock pill', selector: '#stat-out',
      // same source, is_out_of_stock = qty_on_hand <= 0
      sql: ({ hive }) => `select count(*) from v_inventory_items_truth where hive_id = ${q(hive)}`
        + ` and status in ('approved','pending','rejected') and is_out_of_stock` },
  ],
  // ── community ────────────────────────────────────────────────────────────────────────────────────
  // #profile-xp READS ZERO AND THAT IS CORRECT - checked rather than assumed, because a 0 next to a
  // live community_xp read is exactly the shape of a silent fallback. community_xp holds no row for
  // this worker in this hive (max = 0) and none in ANY hive, so the surface is reporting a true zero
  // rather than swallowing a failed read. Verifying which of those two a 0 is, is the whole job.
  community: [
    { label: 'my posts', selector: '#profile-posts',
      // v_community_posts_truth?select=id&hive_id=eq.X&author_name=eq.<me>&deleted_at=is.null
      sql: ({ hive, worker }) => `select count(*) from v_community_posts_truth where hive_id = ${q(hive)}`
        + ` and author_name = ${q(worker)} and deleted_at is null` },
    { label: 'my community XP', selector: '#profile-xp',
      sql: ({ hive, worker }) => `select coalesce(max(xp_total), 0) from community_xp`
        + ` where worker_name = ${q(worker)} and hive_id = ${q(hive)}` },
  ],
  // ── achievements ─────────────────────────────────────────────────────────────────────────────────
  // The composite is the SUM of current_level across the worker's achievements. Worth checking rather
  // than trusting a stored total: the CD invariant for this page requires level be RECOMPUTED rather
  // than read from a column that can drift from the log it summarises.
  achievements: [
    { label: 'composite level', selector: '#stat-composite',
      sql: ({ worker }) => `select coalesce(sum(current_level), 0) from v_worker_achievements_truth`
        + ` where worker_name = ${q(worker)}` },
  ],
  // ── pm-scheduler ─────────────────────────────────────────────────────────────────────────────────
  // THE PILLS ARE A CLIENT-SIDE ROLLUP, NOT A QUERY, so there is no single truth query to compare each
  // one against: getAssetOverallStatus() folds each asset's scope items into one status
  // (pm-scheduler.html:1012). Replicating that fold in SQL would risk manufacturing a defect out of my
  // own re-implementation - the exact failure this bank exists to avoid.
  // WHAT IS HONESTLY CHECKABLE IS THE PARTITION: every asset must land in exactly one displayed
  // bucket, so the three pills must SUM to the hive's asset count. That is a real DB fact, and it
  // catches an asset silently falling out of the summary.
  // ★AND IT HAS A KNOWN LATENT HOLE, named rather than left implied: getAssetOverallStatus returns a
  // FOURTH value, 'nodata', for an asset with no scope items - and there is no pill for it. Today that
  // bucket is empty (0 of 30 assets lack scope items) so the sum is exact; the first asset that lands
  // there will disappear from the summary with nothing on screen saying so.
  'pm-scheduler': [
    { label: 'the three status pills partition the asset set',
      sum: ['#stat-overdue', '#stat-duesoon', '#stat-ontrack'],
      sql: ({ hive }) => `select count(*) from pm_assets where hive_id = ${q(hive)}` },
  ],
};

const run = async () => {
  const pages = (ONE ? [ONE] : Object.keys(CHECKS)).filter((p) => CHECKS[p]);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, results: [] };

  for (const name of pages) {
    const page = await ctx.newPage();
    const rec = { page: name, checks: [] };
    const seen = [];
    page.on('request', (req) => { const u = req.url(); if (u.includes('/rest/v1/')) seen.push(u); });
    try {
      await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(4500);
      const REL = { inventory: 'v_inventory_items_truth', community: 'v_community_posts_truth',
                    'pm-scheduler': 'pm_assets',
                    achievements: 'v_worker_achievements_truth', logbook: 'logbook' };
      rec.scope = scopeFromRequests(seen, REL[name] || name);
      // inventory is hive-scoped, not worker-scoped, so a missing worker filter is expected there.
      if (['inventory', 'community', 'pm-scheduler'].includes(name) && rec.scope && rec.scope.hive == null) {
        const u = seen.find((x) => x.includes(REL[name]) && /hive_id=eq\./.test(x));
        const m = u && /hive_id=eq\.([0-9a-f-]{36})/i.exec(u);
        if (m) rec.scope = { worker: rec.scope.worker, hive: m[1], from: u };
      }
      // ★public-feed IS NOT UNSCOPED - ITS SCOPE IS THE `public` PREDICATE, and that is the thing worth
      // proving. It is the one anon surface: no worker, no hive, just "posts marked public". Exempting
      // it from the scope check would skip the single most important fact about the read; instead the
      // scope is READ OFF THE WIRE the same way every other page's is, by requiring the page's own
      // request to carry public=eq.true. If that predicate is ever lost, this throws rather than
      // quietly comparing 112 rendered cards against 15 and calling it a mismatch of counts, when the
      // real event would be a privacy regression.
      if (name === 'public-feed') {
        const u = seen.find((x) => /v_community_posts_truth/.test(x));
        if (!u || !/public=eq\.true/.test(u)) {
          throw new Error('public-feed did not issue a request filtered on public=eq.true '
                        + `(observed: ${u || 'no v_community_posts_truth request at all'}) — the page is `
                        + 'not asking the question this check is about');
        }
        rec.scope = { publicOnly: true, from: u };
      } else if (!rec.scope || (['inventory', 'pm-scheduler'].includes(name) ? rec.scope.hive == null : rec.scope.worker == null)) {
        throw new Error(`page scope unreadable (worker=${JSON.stringify(rec.scope)}) — the comparison `
                      + 'would be against a different question, so it is a failure, not a skip');
      }
      for (const c of CHECKS[name]) {
        // A SUM check reads several pills and compares their total; a missing one fails the whole
        // check rather than quietly summing the rest.
        if (c.sum) {
          const parts = [];
          for (const sel of c.sum) {
            const t = (await page.textContent(sel).catch(() => null) || '').trim();
            parts.push({ sel, t, n: /^-?\d[\d,]*$/.test(t) ? Number(t.replace(/,/g, '')) : null });
          }
          const chk = { label: c.label, selectors: c.sum, parts };
          if (parts.some((p) => p.n === null)) {
            chk.ok = false;
            chk.why = 'at least one pill is not rendering a number, so the partition cannot be checked';
          } else {
            chk.displayed = parts.reduce((a2, p) => a2 + p.n, 0);
            chk.sql = c.sql(rec.scope); chk.truth = truth(chk.sql);
            chk.ok = chk.displayed === chk.truth;
            chk.shown = String(chk.displayed);
            chk.why = chk.ok ? 'the pills partition the set exactly'
                             : `pills sum to ${chk.displayed}, the set holds ${chk.truth}`;
          }
          rec.checks.push(chk);
          continue;
        }
        // ★A COUNT IS NOT ALWAYS A NUMBER ON SCREEN. Some surfaces state their count only by RENDERING
        // that many things - public-feed shows fifteen post cards and no total anywhere. Reading
        // textContent there returns nothing and the check would report "the page makes no claim",
        // which is false: the page IS claiming "these are the public posts", just structurally rather
        // than numerically. countSelector asks the page the same question in the form it answers in.
        if (c.countSelector) {
          const n = await page.evaluate((sel) => document.querySelectorAll(sel).length, c.countSelector);
          const sql = c.sql(rec.scope);
          const chk = { label: c.label, countSelector: c.countSelector, displayed: n, sql, truth: truth(sql) };
          chk.ok = n === chk.truth && n > 0;
          // A count check that can only ever pass is not evidence. The discriminator is the number a
          // WRONGLY-scoped read would show, and it must differ from the right one.
          if (c.discriminator) {
            chk.discriminator = { label: c.discriminator.label, value: truth(c.discriminator.sql(rec.scope)) };
            chk.discriminates = chk.discriminator.value !== chk.displayed;
          }
          chk.why = n === 0 ? 'nothing rendered, so there is no claim to compare - a failure to compare, '
                            + 'never a pass'
                  : chk.ok ? 'the number of rendered items equals the source set exactly'
                           : `rendered ${n}, the source set holds ${chk.truth}`;
          rec.checks.push(chk);
          continue;
        }
        const shown = (await page.textContent(c.selector).catch(() => null) || '').trim();
        const chk = { label: c.label, selector: c.selector, shown };
        if (!shown || !/^-?\d[\d,]*$/.test(shown)) {
          // An em-dash is the page saying "I do not know". That is not agreement.
          chk.ok = false;
          chk.why = `the number is not rendered (shown: ${JSON.stringify(shown)}); the page is not `
                  + 'making a claim, so there is nothing to agree with — recorded as a failure to '
                  + 'compare rather than a pass';
        } else {
          const sql = c.sql(rec.scope);
          chk.sql = sql;
          chk.truth = truth(sql);
          chk.displayed = Number(shown.replace(/,/g, ''));
          chk.ok = chk.displayed === chk.truth;
          chk.why = chk.ok ? 'the displayed number equals its source of truth'
                           : `displayed ${chk.displayed}, truth ${chk.truth}`;
        }
        rec.checks.push(chk);
      }
    } catch (e) { rec.error = String(e.message || e).slice(0, 220); }
    await page.close();
    out.results.push(rec);
    for (const c of rec.checks) {
      console.log(`  ${c.ok ? 'PASS' : 'FAIL'}  ${name.padEnd(16)} ${String(c.selector || (c.selectors || []).join('+')).padEnd(16)} ` +
        `shown=${String(c.shown).padEnd(7)} truth=${c.truth ?? '-'}  ${c.label}`);
    }
    if (rec.error) console.log(`  ERROR ${name}: ${rec.error}`);
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'count_matches_source_report.json'), JSON.stringify(out, null, 1));
  const all = out.results.flatMap((r) => r.checks);
  console.log(`\n  ${all.length} check(s) over ${out.results.length} page(s) · ${all.filter((c) => !c.ok).length} failing`);
  console.log('  -> count_matches_source_report.json');
};

run().catch((e) => { console.error(e); process.exit(1); });
