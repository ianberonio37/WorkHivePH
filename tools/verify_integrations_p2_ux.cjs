// verify_integrations_p2_ux.cjs — CMMS Integrations PDDA P2 (Adaptability + Usability) live gate.
//
// Locks the P2 client fixes with a headless Playwright walk (identity injected via localStorage,
// so it needs no seeded hive data; the outage is a real fetch-rejection, not a route abort which
// supabase-js swallows differently):
//   I2  role gate — a WORKER sees "Supervisor access only" (no token field); a SUPERVISOR sees the
//       full wizard; the worker-denied path throws NO console error (the drop-zone null-guard).
//   U5  keyboard a11y — source/entity cards are role=button + tabindex=0 + aria-pressed; drop zone
//       is keyboard-activatable.
//   A5  outage honesty — with integration_configs failing, the verdict reads "Couldn't load your
//       integrations" (never the fake "No integrations configured" empty state).
//
// RUN: NODE_PATH="$(pwd)/node_modules" node tools/verify_integrations_p2_ux.cjs
// Exit 0 = all checks pass; non-zero = a P2 UX regression. Needs the Flask server at :5000.
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5000/workhive/integrations.html';
const HIVE = 'b86f9ef6-b0a6-477d-b9c6-ca865c3b9dba';

function initScript(role, blockConfigs) {
  let s = `
    localStorage.setItem('wh_last_worker','Pablo Aguilar');
    localStorage.setItem('wh_active_hive_id','${HIVE}');
    localStorage.setItem('wh_hive_id','${HIVE}');
    localStorage.setItem('wh_hive_role','${role}');
    localStorage.setItem('wh_cmms_guide_dismissed','1');
  `;
  if (blockConfigs) {
    s += `
      const _f = window.fetch;
      window.fetch = (...a) => {
        const u = typeof a[0]==='string' ? a[0] : (a[0] && a[0].url) || '';
        if (/integration_configs/.test(u)) return Promise.reject(new TypeError('simulated outage'));
        return _f.apply(window, a);
      };
    `;
  }
  return s;
}

async function load(browser, role, opts = {}) {
  const ctx = await browser.newContext();
  const errors = [];
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await ctx.addInitScript(initScript(role, opts.blockConfigs));
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(opts.blockConfigs ? 9000 : 3000); // supabase-js retries a rejected fetch ~several s
  const probe = await page.evaluate(() => ({
    denied: /Supervisor access only/i.test(document.body.innerText),
    srcCards: document.querySelectorAll('.source-card[role="button"][tabindex="0"]').length,
    entCards: document.querySelectorAll('[data-entity][role="button"]').length,
    dropZone: document.querySelectorAll('.drop-zone[role="button"][tabindex="0"]').length,
    ariaPressed: document.querySelectorAll('.source-card[aria-pressed]').length,
    verdictLabel: document.getElementById('it-verdict-label') ? document.getElementById('it-verdict-label').textContent : '',
    fakeEmpty: /No integrations configured/i.test(document.body.innerText),
    hasWizard: !!document.querySelector('#wizard'),
    hasTokenField: !!document.querySelector('#sc-token, input[placeholder*="token"]'),
  }));
  await ctx.close();
  const realErrors = errors.filter(e => !/simulated outage|Failed to load resource|ERR_FAILED|net::/i.test(e));
  return { realErrors, probe };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  let S, W, O;
  try {
    S = await load(browser, 'supervisor');
    W = await load(browser, 'worker');
    O = await load(browser, 'supervisor', { blockConfigs: true });
  } finally { await browser.close(); }

  const checks = [
    ['I2 supervisor: full UI (not denied, wizard present)', S.probe.denied === false && S.probe.hasWizard === true],
    ['I2 supervisor: 0 real console errors',                S.realErrors.length === 0],
    ['I2 WORKER denied (Supervisor access only)',           W.probe.denied === true],
    ['I2 worker: no token field exposed',                   W.probe.hasTokenField === false],
    ['I2 worker-denied path: 0 console errors',             W.realErrors.length === 0],
    ['U5 source cards keyboard-accessible',                 S.probe.srcCards >= 1],
    ['U5 source cards have aria-pressed',                   S.probe.ariaPressed >= 1],
    ['U5 drop zone keyboard-accessible',                    S.probe.dropZone >= 1],
    ['A5 outage: honest "Couldn\'t load" verdict',          /couldn.t load/i.test(O.probe.verdictLabel)],
    ['A5 outage: NOT fake-empty',                           O.probe.fakeEmpty === false],
    ['A5 outage: no unexpected console errors',             O.realErrors.length === 0],
  ];
  console.log('='.repeat(68));
  let pass = 0;
  for (const [n, ok] of checks) { console.log(`  ${ok ? '[PASS]' : '[FAIL]'} ${n}`); if (ok) pass++; }
  console.log('-'.repeat(68));
  console.log(`  ${pass}/${checks.length} CMMS integrations P2 UX checks passed`);
  if (W.realErrors.length) console.log('  worker errors:', JSON.stringify(W.realErrors.slice(0, 3)));
  process.exit(pass === checks.length ? 0 : 1);
})();
