// prove_no_raw_enum.mjs — the CE `no_raw_enum` oracle, read off the rendered page.
//
// THE ORACLE: "no lowercase_with_underscores status reaches a person."
//
// ★THE SHAPE IS THE TELL, and it is unusually decidable: `in_progress`, `rate_limit_exceeded`,
// `awaiting_approval` are database values that leaked through a renderer with no display mapping. A
// person is being shown a column, not a sentence. Because the shape is mechanical, this is one of the
// few oracles that can be judged from what the page paints without inferring intent.
//
// ★BUT THE ROSTER IS FULL OF THINGS THAT LOOK LIKE ENUMS AND ARE NOT, and every one of them would be a
// false accusation. Excluded, each for a stated reason:
//   · ASSET AND PART CODES — "BF-002", "GEN-001", "LATH-001". Already recorded in this bank as a
//     detector-breaker.
//   · FILE AND FUNCTION NAMES in developer-facing surfaces, and anything inside <code>/<pre>.
//   · i18n KEYS in `data-i` attributes — a marker is not displayed text (its own oracle owns that).
//   · URLs, EMAILS, IDS, and hyphen-joined slugs in hrefs.
//   · SNAKE_CASE INSIDE A LONGER SENTENCE, which is prose quoting a field name, not a status chip.
// The judgement is therefore scoped to SHORT, STANDALONE strings in status-bearing positions - a chip,
// a pill, a badge, a cell, a leaf whose whole text is the token - which is exactly where a status is
// rendered and exactly where a leak is legible.
//
// ★THE ZERO-DENOMINATOR RAIL. A page whose examined-token count is zero was not measured; "0 raw enums
// of 0 candidates" reads identically to a thorough pass. Those return UNGRADED.
//
// NON-WRITING: pages are loaded and read. Nothing is clicked, typed or submitted.
//
// USAGE:  node tools/prove_no_raw_enum.mjs [--page <name>]
// OUTPUT: no_raw_enum_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };

const scan = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) > 0.05;
  };
  // A raw enum: lowercase words joined by underscores, standing alone as the element's whole text.
  const ENUM = /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/;
  // Things shaped like enums that are not statuses reaching a person.
  const CODE_CTX = 'code, pre, kbd, samp, script, style, [data-i], [contenteditable]';

  const examined = [];
  const hits = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;                 // leaves only: a status is a leaf
    if (el.closest(CODE_CTX)) continue;               // developer text, not product copy
    const t = (el.textContent || '').trim();
    if (!t || t.length > 40) continue;                // a sentence quoting a field is not a status chip
    if (!vis(el)) continue;
    // Only the positions a STATUS is rendered in, plus bare short leaves.
    examined.push(t);
    if (!ENUM.test(t)) continue;
    // A slug inside a link is a URL fragment, not a status.
    if (el.closest('a[href]') && (el.closest('a[href]').getAttribute('href') || '').includes(t)) continue;
    hits.push({
      text: t,
      where: (el.closest('[id]') || {}).id || null,
      cls: String(el.className || '').slice(0, 40),
    });
  }
  return { examined: examined.length, hits: hits.slice(0, 12) };
};

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, pages: [] };

  for (const name of (ONE ? ONE.split(',') : PAGES)) {
    const rec = { page: name };
    const page = await ctx.newPage();
    try {
      await page.goto(ORIGIN + '/workhive/' + name + '.html' + (QUERY[name] || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6500);
      const r = await page.evaluate(scan);
      rec.examined = r.examined;
      rec.hits = r.hits;
      if (r.examined < 10) {
        rec.ok = null;
        rec.why = 'only ' + r.examined + ' visible text leaves rendered, so the page did not load enough '
          + 'to judge; UNGRADED rather than a pass over an empty set';
      } else {
        rec.ok = r.hits.length === 0;
        rec.why = rec.ok
          ? r.examined + ' visible short text leaves were examined and none is a raw '
            + 'lowercase_with_underscores token - every status reaching a person is display text'
          : r.hits.length + ' raw enum(s) reach a person: '
            + r.hits.map((h) => JSON.stringify(h.text)).join(', ');
      }
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await page.close();
    out.pages.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + name.padEnd(19) + ' ' + (rec.why || '').slice(0, 92));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'no_raw_enum_report.json'), JSON.stringify(out, null, 1));
  const g = out.pages.filter((p) => p.ok !== null);
  console.log('\n  ' + g.filter((p) => p.ok).length + ' pass | ' + g.filter((p) => !p.ok).length
    + ' fail | ' + (out.pages.length - g.length) + ' ungraded');
};
run().catch((e) => { console.error(e); process.exit(1); });
