// capture_clean_screen.mjs — topic-aligned "clean" phone screens for the video pipeline.
//
// The marketing videos embed a real app screenshot inside a phone frame
// (remotion_scenes/public/wh_<feature>_clean.png). A video about feature X MUST
// show feature X's page — not a borrowed screen. This captures the actual feature
// page at the SAME 430x932 phone viewport as the existing clean screens, resolving
// the route from page_evidence.json so the picture always follows the topic.
//
// Auth-gated pages (resume, etc.) redirect to the landing page without a session.
// For those we inject a LOCAL session into localStorage (supabase-js getSession()
// reads storage with no network call) + seed a demo draft into IndexedDB, and we
// ABORT every request to *.supabase.co so nothing ever touches prod. The page then
// renders its real, populated UI fully offline.
//
// Usage:
//   node tools/capture_clean_screen.mjs <feature-id> [--out wh_<name>_clean] [--route path] [--scroll N] [--auth]
//   node tools/capture_clean_screen.mjs resume            # auto --auth + demo draft
//   node tools/capture_clean_screen.mjs engineering-design --out wh_engdesign_clean
//
// Requires the static server running:  node serve.mjs   (http://localhost:3000)

import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'remotion_scenes', 'public');
const EVIDENCE = path.join(ROOT, 'page_evidence.json');
const BASE = process.env.CAPTURE_BASE || 'http://localhost:3000';
const SUPABASE_REF = 'hzyvnjtisfgbksicrouu'; // matches SUPABASE_URL in the pages

// Phone viewport that yields the canonical 430x932 clean screen (215x466 @ 2x DPR).
const VW = 215, VH = 466, DPR = 2;

function arg(flag, def = null) {
  const i = process.argv.indexOf(flag);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}
const hasFlag = (f) => process.argv.includes(f);

const featureId = process.argv[2];
if (!featureId || featureId.startsWith('--')) {
  console.error('usage: node tools/capture_clean_screen.mjs <feature-id> [--out name] [--route path] [--scroll N] [--auth]');
  process.exit(2);
}

// Pages that redirect to the landing page unless a session + identity are present.
const AUTH_PAGES = new Set(['resume', 'skillmatrix', 'logbook', 'inventory', 'pm-scheduler', 'analytics',
  'analytics-report', 'report-sender', 'alert-hub', 'asset-hub', 'shift-brain', 'dayplanner',
  'assistant', 'achievements', 'community', 'audit-log', 'project-manager', 'project-report']);
const needAuth = hasFlag('--auth') || AUTH_PAGES.has(featureId);

let route = arg('--route');
if (!route) {
  try { route = (JSON.parse(fs.readFileSync(EVIDENCE, 'utf8')).evidence || {})[featureId]?.route; } catch { /* */ }
}
if (!route) route = `${featureId}.html`;
route = route.replace(/^\//, '');

const outName = (arg('--out') || `wh_${featureId.replace(/-/g, '')}_clean`).replace(/\.png$/, '');
const scrollY = parseInt(arg('--scroll', '0'), 10) || 0;
const outPath = path.join(OUT_DIR, `${outName}.png`);

const WORKER = 'Mateo Reyes';
const HIVE_ID = '00000000-0000-0000-0000-000000000abc';
const AUTH_UID = '11111111-1111-1111-1111-111111111111';

// A well-formed, far-future supabase-js v2 session so getSession() returns it
// without a refresh (no network). Value is stored under sb-<ref>-auth-token.
function fakeSession() {
  const far = 4102444800; // 2100-01-01
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const jwt = `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ sub: AUTH_UID, role: 'authenticated', exp: far })}.sig`;
  return { access_token: jwt, token_type: 'bearer', expires_in: 3600, expires_at: far,
           refresh_token: 'local-capture', user: { id: AUTH_UID, aud: 'authenticated', role: 'authenticated',
           email: 'demo@workhiveph.com', user_metadata: { full_name: WORKER }, app_metadata: {} } };
}

// JSON-Resume demo draft so resume.html renders POPULATED, not the empty state.
const RESUME_DRAFT = {
  resume: {
    basics: { name: WORKER, label: 'Maintenance Engineer', email: '', phone: '', url: '',
      summary: '8 years keeping packaging and utility lines running across two Laguna plants. NC II Mechatronics, PSME-aligned.',
      location: { city: 'Cabuyao', region: 'Laguna', countryCode: 'PH' }, profiles: [], _src: {} },
    work: [
      { name: 'San Miguel Yamamura', position: 'Maintenance Engineer', location: 'Canlubang, Laguna',
        startDate: '2021-03', endDate: '', highlights: ['Cut line P-204B downtime 34% with a PM-first schedule', 'Led a 6-person shift crew across 3 lines'] },
      { name: 'Nestle Cabuyao', position: 'Mechanical Technician', location: 'Cabuyao, Laguna',
        startDate: '2018-01', endDate: '2021-02', highlights: ['Rebuilt 12 gearboxes; raised MTBF from 90 to 210 days'] },
    ],
    education: [{ institution: 'Technological University of the Philippines', area: 'Mechanical Engineering Technology', studyType: 'BS', startDate: '2013', endDate: '2017' }],
    skills: [{ name: 'Preventive Maintenance' }, { name: 'Vibration Analysis' }, { name: 'PLC / SCADA' }, { name: 'Welding (SMAW)' }],
    certificates: [{ name: 'TESDA NC II — Mechatronics Servicing' }, { name: 'PSME Affiliate Member' }],
    projects: [], awards: [], references: [],
    meta: { template: 'ats-plain', title: 'Maintenance Engineer Resume', generatedBy: 'WorkHive Resume Builder' },
  },
  _resumeId: null, worker: WORKER, ts: 1,
};

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: VW, height: VH, deviceScaleFactor: DPR });

  if (needAuth) {
    // Never touch prod: abort every supabase.co request; the page falls back to the seeded draft.
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      if (/supabase\.co/i.test(req.url())) {
        // Fulfill instantly with an empty result rather than abort: aborting makes
        // supabase-js retry/hang, which stalls async inits (assistant.html startChat
        // awaits Promise.all of DB queries before painting its greeting + chips).
        // An empty 200 resolves every query fast without touching prod.
        req.respond({ status: 200, contentType: 'application/json',
          headers: { 'content-range': '*/0', 'access-control-allow-origin': '*' }, body: '[]' }).catch(() => {});
      } else req.continue().catch(() => {});
    });
    // Set the session in localStorage BEFORE any page script runs (sync, on every
    // document) so the auth guard never fires the redirect that destroys the context.
    await page.evaluateOnNewDocument(({ ref, sess, worker, hive }) => {
      try {
        localStorage.setItem(`sb-${ref}-auth-token`, JSON.stringify(sess));
        localStorage.setItem('wh_last_worker', worker);
        localStorage.setItem('wh_active_hive_id', hive);
      } catch (e) { /* */ }
    }, { ref: SUPABASE_REF, sess: fakeSession(), worker: WORKER, hive: HIVE_ID });

    // First load (renders, no redirect) → seed the IndexedDB draft → reload populated.
    await page.goto(`${BASE}/${route}`, { waitUntil: 'networkidle2', timeout: 30000 }).catch(() => {});
    await page.evaluate(async (draft) => {
      await new Promise((res) => {
        const open = indexedDB.open('wh_resume', 1);
        open.onupgradeneeded = () => { if (!open.result.objectStoreNames.contains('draft')) open.result.createObjectStore('draft'); };
        open.onsuccess = () => { const d = open.result; const tx = d.transaction('draft', 'readwrite'); tx.objectStore('draft').put(draft, 'current'); tx.oncomplete = () => res(); tx.onerror = () => res(); };
        open.onerror = () => res();
      });
    }, RESUME_DRAFT).catch(() => {});
  }

  await page.goto(`${BASE}/${route}`, { waitUntil: 'networkidle2', timeout: 30000 }).catch(() => {});

  await page.evaluate(() => {
    document.querySelectorAll('.reveal').forEach((el) => el.classList.add('visible'));
    ['#wh-feedback-fab', '.wh-feedback-fab', '#cookie-banner', '.cookie-banner',
     '#companion-launcher', '.companion-launcher', '.toast', '#toast-root', '.wh-fab',
     '#wh-hub-fab', '.wh-hub-fab', '#wh-hub-panel', '#wh-guide-link',
     // connectivity "Backend down" pill (offline capture) — data-driven dashboards
     '#wh-conn-chip', '#wh-conn-popover', '.wh-conn-chip', '.live-chip.offline']
      .forEach((sel) => document.querySelectorAll(sel).forEach((el) => (el.style.display = 'none')));
  });
  if (scrollY) await page.evaluate((y) => window.scrollTo(0, y), scrollY);
  // Auth pages with an async chat init (assistant.html startChat) paint their
  // capability-showcase starter chips after the aborted DB queries settle — wait
  // for them (best-effort) so the shot isn't the empty pre-chip state.
  const gotChips = await page.waitForSelector('.starter-chip', { timeout: 9000 }).then(() => true).catch(() => false);
  await new Promise((r) => setTimeout(r, gotChips ? 600 : (needAuth ? 2000 : 1200)));

  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: outPath, clip: { x: 0, y: 0, width: VW, height: VH } });
  const url = await page.url();
  console.log(`captured ${featureId}  (${route})  ->  ${path.relative(ROOT, outPath)}   [landed: ${url.replace(BASE, '')}]`);
  await browser.close();
})();
