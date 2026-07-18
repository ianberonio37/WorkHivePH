// frontend_i1_authgate.mjs — Arc D / D2 Internal-Control, the RIGOROUS I1 test.
//
// WHY: e2e_roles_runner's "solo" simulates no-hive by clearing localStorage on a
// REAL member — pages legitimately re-derive that member's hive, so content shows
// (correct authz, not a leak). That is a WEAK I1 proxy. The real I1 threat model is
// LOGGED OUT (no Supabase session at all): an authed-only page MUST bounce to the
// entry/login OR show a gate, and MUST NOT render authenticated primary content.
//
// This probe loads each I1-applicable page in a FRESH, never-signed-in context and
// DUMPS the logged-out state (final URL, bounced?, gate visible?, has session?, body
// length, h1). Verdict is assigned by reading the evidence (classify-by-evidence),
// not a brittle auto-rule. Writes frontend_i1_authgate.json.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const PAGES = [
  'engineering-design','logbook','inventory','pm-scheduler','voice-journal','dayplanner',
  'asset-hub','alert-hub','analytics','analytics-report','shift-brain','ai-quality',
  'ph-intelligence','project-manager','project-report','skillmatrix','achievements','audit-log',
  'assistant','hive','community','marketplace','marketplace-seller','marketplace-seller-profile',
  'marketplace-admin','integrations','plant-connections','report-sender','status',
  'founder-console','llm-observability','agentic-rag-observability',
];

const browser = await chromium.launch();
// FRESH context, NEVER signed in. No storage state.
const ctx = await browser.newContext();
const out = [];
for (const name of PAGES) {
  const page = await ctx.newPage();
  let rec = { page: name + '.html' };
  try {
    await page.goto(`${SEEDER}/workhive/${name}.html`, { waitUntil: 'networkidle', timeout: 20000 });
    await page.waitForTimeout(2500); // let any auth-check redirect / gate render settle
    const info = await page.evaluate(() => {
      const vis = el => { if (!el) return false; const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      // gate signals: a #hive-gate / [class*=gate] overlay, or sign-in prompt text
      const gateEl = document.querySelector('#hive-gate,[id*="gate"],[class*="gate"],[class*="signin"],[class*="sign-in"]');
      const bodyTxt = (document.body.innerText || '').trim();
      const signinText = /sign\s*in|log\s*in|sign\s*in\s*required|please\s+(sign|log)|you (must|need) (to )?(sign|log)/i.test(bodyTxt.slice(0, 600));
      const h1 = document.querySelector('h1');
      // is there a live Supabase session token in storage?
      let hasSession = false;
      try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (/sb-.*-auth-token|supabase\.auth/.test(k) && localStorage.getItem(k) && localStorage.getItem(k) !== 'null') hasSession = true; } } catch (e) {}
      return {
        gateVisible: vis(gateEl), gateExists: !!gateEl,
        signinText, bodyLen: bodyTxt.length,
        h1: h1 ? (h1.textContent || '').trim().slice(0, 50) : null,
        hasSession,
      };
    });
    rec.finalUrl = page.url();
    rec.bounced = !page.url().includes(`${name}.html`);
    Object.assign(rec, info);
  } catch (e) {
    rec.error = String(e).slice(0, 120);
  }
  await page.close();
  out.push(rec);
  const tag = rec.bounced ? 'BOUNCED' : (rec.gateVisible ? 'GATE' : (rec.signinText ? 'SIGNIN-TXT' : 'OPEN?'));
  console.log(`${tag.padEnd(11)} ${name.padEnd(34)} url=${(rec.finalUrl||'').split('/').pop()} bodyLen=${rec.bodyLen} h1=${JSON.stringify(rec.h1)} session=${rec.hasSession}`);
}
writeFileSync('frontend_i1_authgate.json', JSON.stringify({ generated: new Date().toISOString(), base: SEEDER, results: out }, null, 2));
console.log('\n-> wrote frontend_i1_authgate.json (' + out.length + ' pages)');
await browser.close();
