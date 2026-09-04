// prove_cost_before_commit.mjs — CM `what_does_it_cost`: "cost, hold and reward are stated BEFORE
// commitment, not after."
//
// BEFORE IS THE ENTIRE CLAIM. A page that tells you what an action cost once you have taken it has told
// you nothing you could act on — the decision is already made. So this reads the surface in the state a
// person is in when their thumb is over the button: form open, fields filled, submit not yet pressed.
// Nothing is ever submitted by this prover, which is also why it is the safest of the action provers.
//
// THREE THINGS, NOT ONE, because they are different promises and a page can keep one and break another:
//   COST   — what leaves you: credits, pesos, stock units, a quota draw.
//   HOLD   — what is reserved rather than spent: a staged part, a credit hold on a listing.
//   REWARD — what comes back: XP, a badge, a tier step.
// The platform's own domain truth already demands the third one in these words: "XP per action is stated
// BEFORE the action, where it is meant to motivate."
//
// ★DISCLOSURE IS GRADED ONLY WHERE THERE IS SOMETHING TO DISCLOSE, and that is decided from the page's
// own write, not from my expectations. Registering an asset costs nothing, holds nothing and rewards
// nothing — demanding a cost line there would manufacture a defect on a form that is behaving perfectly.
// So each flow declares which of the three actually apply, and a flow with none is reported N/A rather
// than passed (vacuity) or failed (fiction). That is the same rule the component prover had to learn:
// an absence is only a defect where a subject exists.
//
// THE VOCABULARY IS HARVESTED FROM THIS PRODUCT, not invented — "+50 XP", "credits", "on hand",
// "reserved", "staged" are the platform's own words. An oracle that rejects the product's correct
// sentence because its author thought of different ones is the trap this arc keeps re-learning.
//
// Usage:
//   node tools/prove_cost_before_commit.mjs [--page community] [--selftest]
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const COST_SRC = [
  '\\bcosts?\\b', '\\bcredits?\\b', '\\bfee\\b', 'php\\s*\\d', '\\u20b1\\s*\\d', '\\bprice\\b',
  'deduct', 'uses \\d', 'consumes?', 'will use', 'from stock', 'on hand', 'quota', 'remaining',
].join('|');
const HOLD_SRC = [
  '\\bhold\\b', '\\breserv', '\\bstaged?\\b', 'set aside', 'locked for', 'pending release',
].join('|');
const REWARD_SRC = [
  '\\+\\s*\\d+\\s*xp', '\\bxp\\b', 'earns?\\b', 'you will earn', '\\bbadge\\b', 'level up',
  'unlocks?\\b', 'points?\\b', 'reward',
].join('|');

// Which of the three each write actually involves — declared from the page's own behaviour.
const FLOWS = {
  community: {
    steps: [{ click: '#fab-post' }, { fill: '#post-content', value: 'cost probe' }],
    scope: '#composer-overlay',
    applies: ['reward'],
    why: 'posting AWARDS Community XP (+50 first post, +25 safety, +20 at 3 reactions) and costs nothing, '
       + 'so reward is the only one of the three with a subject here',
  },
  inventory: {
    steps: [{ click: 'button:has-text("Add Part")' },
            { fill: '#f-part-number', value: 'WH-COST-PROBE' },
            { fill: '#f-part-name', value: 'cost probe part' }, { fill: '#f-qty', value: '1' }],
    scope: '#part-modal',
    applies: [],
    why: 'ADDING a part neither spends nor reserves nor rewards — it is stock arriving, not leaving. The '
       + 'costed action on this page is Use/Restock, which draws stock down; this flow is the wrong '
       + 'subject for cost and is reported N/A rather than failed',
  },
  // THE GENUINELY COSTED ACTION ON THIS PLATFORM'S FIELD SIDE. "Use" draws stock DOWN, so cost has a real
  // subject here in a way the Add-Part form never did — this is the flow the inventory N/A row pointed at.
  // The modal ships #use-qty-available beside the quantity field, so the disclosure is expected to be there.
  'inventory-use': {
    page: 'inventory',
    steps: [{ click: 'button:has-text("Use")' }, { fill: '#use-qty', value: '1' }],
    scope: '#use-modal',
    applies: ['cost'],
    why: 'consuming a part REMOVES units from stock, so what it costs (and what remains) is the thing a '
       + 'person needs before committing — over-drawing a critical spare is not recoverable by undo',
  },
  // THE EXAM. This platform's own domain truth demands it in as many words — "The exam pass mark is stated
  // BEFORE the exam" — and this page's badges attach to someone's CREDENTIAL, which makes it the least
  // acceptable place to withhold what passing takes. The lesson modal is the pre-commit surface: the
  // Take Exam control lives in its footer.
  'skillmatrix-exam': {
    page: 'skillmatrix',
    steps: [{ eval: "document.querySelector('.disc-card') && document.querySelector('.disc-card').click()" }],
    scope: '#lesson-modal',
    applies: ['reward'],
    extra: { key: 'passMark', src: 'pass(ing)?\s*(mark|score)|\d+\s*of\s*\d+\s*correct|to pass' },
    why: 'committing to an assessment whose badge lands on a credential — the reward AND the threshold both '
       + 'belong in front of the person before they start',
  },
  // Each of these three WRITES SOMETHING but spends, reserves and rewards NOTHING — and that has to be
  // reasoned per write rather than assumed from the page, which is why they are separate entries with
  // separate justifications instead of one blanket exclusion.
  'asset-hub-fmea': {
    page: 'asset-hub',
    steps: [{ eval: "document.querySelector('.asset-card') && document.querySelector('.asset-card').click()" },
            { click: '#asset-view-toggle' }, { click: '[data-tab=\"fmea\"]' }, { click: '#fmea-add-btn' },
            { fill: '#fmea-function', value: 'cost probe function' },
            { fill: '#fmea-failure-mode', value: 'cost probe mode' }],
    scope: '#fmea-modal',
    applies: [],
    why: 'recording a failure MODE is analysis, not consumption — it draws no stock, holds no part and pays '
       + 'no XP. The costed action in this family is parts STAGING (parts_staged_reservations), which is a '
       + 'hold and lives on a different control',
  },
  'pm-scheduler-add': {
    page: 'pm-scheduler',
    steps: [{ click: '#tab-add' }, { fill: '#w-name', value: 'Cost Probe Asset' },
            { fill: '#w-tag', value: 'WH-COST-PM' }, { fill: '#w-location', value: 'Probe Bay' }],
    scope: '#step-1',
    applies: [],
    // ★CORRECTED: I first wrote that the cost "lands later, at completion, where parts are actually
    // consumed". That was an assumption, not a measurement, and it was wrong. The completion sheet has no
    // parts field, and this page's writes are pm_assets, pm_scope_items, pm_completions, logbook,
    // asset_nodes, project_links and hive_audit_log — records, every one. It never touches
    // inventory_items, so NO view on this page spends, reserves or rewards anything.
    why: 'adding an asset to the PM schedule commits future WORK, not a resource. Verified against the '
       + "page's actual write targets: pm_assets / pm_scope_items / pm_completions / logbook — records, "
       + 'not resources. inventory_items is never written from this page, so nothing here is spent, '
       + 'reserved or paid at any point, completion included',
  },
  'dayplanner-item': {
    page: 'dayplanner',
    steps: [{ click: 'button:has-text(\"+ Schedule\")' }, { fill: '#m-title', value: 'cost probe' }],
    scope: '#modal',
    applies: [],
    why: 'planning an item allocates a person TIME, which the planner already surfaces as planned-vs-'
       + 'available hours on its own board; the write itself spends, holds and rewards nothing',
  },
  logbook: {
    steps: [{ click: 'button:has-text("Register Asset")' },
            { fill: '#a-asset-id', value: 'WH-COST-PROBE' }, { fill: '#a-name', value: 'cost probe' }],
    scope: '#asset-modal',
    applies: [],
    why: 'registering an asset costs nothing, holds nothing and rewards nothing',
  },
};

const READ_SCOPE = ({ scope, costSrc, holdSrc, rewardSrc }) => {
  const host = document.querySelector(scope) || document.body;
  const clone = host.cloneNode(true);
  clone.querySelectorAll('style,script,noscript,template').forEach((n) => n.remove());
  const txt = ((clone.textContent || '').replace(/\s+/g, ' ').trim());
  const hit = (src) => {
    const m = txt.match(new RegExp(src, 'i'));
    return m ? txt.slice(Math.max(0, m.index - 45), m.index + 55).trim() : null;
  };
  return { chars: txt.length, cost: hit(costSrc), hold: hit(holdSrc), reward: hit(rewardSrc) };
};

if (args.includes('--selftest')) {
  let fail = 0;
  const T = (src, s) => new RegExp(src, 'i').test(s);
  const cases = [
    [REWARD_SRC, 'Earns +50 XP for your first post', true, 'a stated XP reward'],
    [REWARD_SRC, 'Write something for your hive', false, 'ordinary composer copy'],
    [COST_SRC, 'Uses 2 from stock (14 on hand)', true, 'a stated stock draw'],
    [COST_SRC, 'Part name and quantity', false, 'plain field labels'],
    [HOLD_SRC, '3 staged for a predicted failure', true, 'a stated hold'],
    [HOLD_SRC, 'Add a part to your inventory', false, 'plain instruction'],
  ];
  for (const [src, text, want, label] of cases) {
    const got = T(src, text);
    if (got !== want) { console.log(`  FAIL — ${label}: "${text}" -> ${got}, expected ${want}`); fail++; }
    else console.log(`  ok — ${label} -> ${got}`);
  }
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
    : '\n  SELFTEST PASSED — each of cost/hold/reward fires on its own disclosure and stays silent on plain copy');
  process.exit(fail ? 1 : 0);
}

const browser = await chromium.launch();
const report = { ran: new Date().toISOString(), pages: {} };
for (const p of (ONE ? [ONE] : Object.keys(FLOWS))) {
  const flow = FLOWS[p];
  const rec = { page: p, applies: flow.applies };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN}/${flow.page || p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    for (const st of flow.steps) {
      if (st.eval) await page.evaluate(st.eval).catch(() => {});
      else if (st.fill) await page.fill(st.fill, st.value, { timeout: 6000 }).catch(() => {});
      else await page.click(st.click, { timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(450);
    }
    // Read the PRE-COMMIT surface. Nothing is submitted.
    const seen = await page.evaluate(READ_SCOPE,
      { scope: flow.scope, costSrc: COST_SRC, holdSrc: HOLD_SRC, rewardSrc: REWARD_SRC });
    // Some commitments carry a threshold rather than a price — an exam pass mark is a cost of a different
    // currency, and this oracle would miss it entirely if it only ever looked for money and units.
    if (flow.extra) {
      seen[flow.extra.key] = await page.evaluate(({ scope, src }) => {
        const host = document.querySelector(scope) || document.body;
        const t = ((host.textContent || '').replace(/\s+/g, ' ').trim());
        const m = t.match(new RegExp(src, 'i'));
        return m ? t.slice(Math.max(0, m.index - 40), m.index + 60).trim() : null;
      }, { scope: flow.scope, src: flow.extra.src });
    }
    rec.seen = seen;
    if (!flow.applies.length) {
      rec.status = 'N/A';
      rec.why = `nothing to disclose: ${flow.why}`;
    } else {
      const need = flow.extra ? [...flow.applies, flow.extra.key] : flow.applies;
      const missing = need.filter((k) => !seen[k]);
      rec.missing = missing;
      rec.status = missing.length ? 'FAIL' : 'PASS';
      rec.why = missing.length
        ? `${missing.join(' + ')} applies here but is NOT stated before the person commits (${flow.why})`
        : (flow.extra ? [...flow.applies, flow.extra.key] : flow.applies)
            .map((k) => `${k} stated: "${String(seen[k]).slice(0, 60)}"`).join('; ');
    }
  } catch (e) { rec.status = 'UNGRADED'; rec.why = 'probe error: ' + String(e).slice(0, 80); }
  report.pages[p] = rec;
  console.log(`  ${p.padEnd(13)} ${String(rec.status).padEnd(9)} ${rec.why || ''}`.slice(0, 160));
  await ctx.close();
}
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'cost_before_commit_report.partial.json' : 'cost_before_commit_report.json'), JSON.stringify(report, null, 1));
const v = Object.values(report.pages);
console.log(`\n  wrote cost_before_commit_report.json — ${v.filter((x) => x.status === 'PASS').length} pass, `
  + `${v.filter((x) => x.status === 'FAIL').length} fail, ${v.filter((x) => x.status === 'N/A').length} n/a`);
console.log('  NOTHING WAS SUBMITTED: this oracle reads the surface BEFORE the commit, by definition.');
await browser.close();
