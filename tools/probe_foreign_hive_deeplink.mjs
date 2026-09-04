/**
 * probe_foreign_hive_deeplink.mjs - T43: a link to ANOTHER hive's object (2026-08-28)
 *
 * READ-ONLY. Signs in, deep-links asset-hub at an asset that belongs to a DIFFERENT hive, and
 * reads what a person would actually see. RLS will (correctly) return no row - the question this
 * trajectory asks is what the GLASS then says about it.
 *
 * The bar is boundary_not_emptiness: a refusal must name the boundary. "This asset is not in your
 * hive" is a fact someone can act on - they followed a link meant for another plant. A blank
 * panel, a spinner that never resolves, or "no data yet" are all the same failure wearing
 * different clothes: they describe the DATA when the truth is about ACCESS, and they leave the
 * reader to conclude their own plant's records are missing.
 *
 * Uses walk_page.mjs's visibleText so the reading is occlusion-aware - innerText alone returns
 * text from display:none nodes, which is exactly how an earlier probe "found" an empty state that
 * was never on screen.
 *
 * Usage: node tools/probe_foreign_hive_deeplink.mjs <foreign-node-uuid>
 */
import { chromium } from 'playwright';
import { visibleText } from './walk_page.mjs';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };
const FOREIGN = process.argv[2];
if (!FOREIGN) { console.log('usage: node tools/probe_foreign_hive_deeplink.mjs <uuid>'); process.exit(2); }

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });

const auth = await ctx.newPage();
await auth.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
                           { timeout: 20000 }).catch(() => {});
const signedIn = await auth.evaluate(async ({ acct, url }) => {
  try {
    const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
    const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
    const uid = data?.session?.user?.id;
    const { data: m } = uid ? await db.from('hive_members').select('hive_id')
      .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
    if (m?.hive_id) { localStorage.setItem('wh_active_hive_id', m.hive_id); localStorage.setItem('wh_hive_id', m.hive_id); }
    localStorage.setItem('wh_last_worker', acct.worker);
    return !error && !!data?.session;
  } catch (e) { return false; }
}, { acct: ACCT, url: SB_URL });
await auth.close();
if (!signedIn) { console.log('  sign-in FAILED'); await browser.close(); process.exit(1); }

const page = await ctx.newPage();
const consoleErrs = [];
page.on('console', m => { if (m.type() === 'error') consoleErrs.push(m.text().slice(0, 110)); });

console.log(`asset-hub deep-linked to a FOREIGN hive's asset\n  ?node_id=${FOREIGN}\n`);
await page.goto(`${BASE}/workhive/asset-hub.html?node_id=${FOREIGN}`, { waitUntil: 'domcontentloaded' });

/* ★SAMPLE REPEATEDLY, BECAUSE A REFUSAL MAY BE A TOAST. The first version of this probe took ONE
   reading at 6 seconds and reported that the page "says nothing" - and banked that as a finding.
   It was wrong: asset-hub toasts "That asset link could not be resolved in this hive.", and the
   toast had already faded by the time the single sample ran. A late reading cannot tell "never
   said" from "said and gone", and the stronger claim is the one that gets written down. This is
   the platform's own recorded trap - the toast fades, the empty state is what stays - so the probe
   now watches the whole window and reports WHEN as well as WHETHER. */
const ephemeral = [];
for (let i = 0; i < 24; i++) {
  const hit = await page.evaluate(() => {
    const re = /could not be resolved|not in the fleet|awaiting approval|was rejected|no access|not found/i;
    // SKIP is deliberate: a <style> block's CSS text matched the pattern on the first run and was
    // reported as a refusal at +0ms. Stylesheet text is not something a person reads.
    // ★AND THE MATCH MUST LIVE INSIDE <body>. Skipping STYLE/SCRIPT by tag was not enough: the
    // first hit was an ANCESTOR of both <title> and a <style> block, whose concatenated textContent
    // matched - <html> itself, which passes a child-count filter with room to spare. Tag-blocking
    // the leaf does nothing when the match is made by something that contains it.
    const SKIP = new Set(['STYLE', 'SCRIPT', 'TITLE', 'HEAD', 'META', 'LINK', 'NOSCRIPT']);
    const els = [...document.querySelectorAll('body *')].filter((e) => {
      if (SKIP.has(e.tagName)) return false;
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'
             && s.opacity !== '0' && e.children.length <= 3 && re.test(e.textContent || '');
    });
    return els.length ? (els[els.length - 1].textContent || '').replace(/\s+/g, ' ').trim().slice(0, 130) : null;
  });
  if (hit && !ephemeral.some(e => e.text === hit)) ephemeral.push({ at: i * 500, text: hit });
  await page.waitForTimeout(500);
}
if (ephemeral.length) {
  console.log('  TRANSIENT REFUSAL(S) caught while watching (would be missed by one late sample):');
  for (const e of ephemeral) console.log(`    +${e.at}ms  "${e.text}"`);
  console.log('');
}

const { lines, dropped } = await visibleText(page, { max: 45, maxLen: 130 });
console.log(`  VISIBLE TEXT (${lines.length} lines${dropped ? `, ${dropped} dropped` : ''}):`);
for (const l of lines) console.log('    ' + l);

const blob = lines.join(' | ').toLowerCase();
const namesBoundary = /(not in your hive|another hive|different hive|do not have access|don't have access|no access|not found|belongs to)/.test(blob);
const looksEmpty = /(no assets|nothing here|no data|get started|register your first|add your first)/.test(blob);

console.log('');
console.log(`  names the ACCESS boundary : ${namesBoundary}`);
console.log(`  reads as an EMPTY plant   : ${looksEmpty}`);
if (consoleErrs.length) console.log(`  console errors            : ${consoleErrs.length} (first: ${consoleErrs[0]})`);
await browser.close();
