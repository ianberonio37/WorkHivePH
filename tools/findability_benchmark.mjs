/* findability_benchmark.mjs — T173's instrument (first slice, 2026-08-25).
 *
 * Twenty common tasks phrased as USER QUESTIONS, each answered from a cold page via
 * the global hub: open nav-hub -> search or scan -> land on the answering surface,
 * in <= 2 interactions. The QUESTIONS are the spec; a miss is a wayfinding defect,
 * not a search-engine defect.
 *
 * First slice ships 5 questions; grow toward 20 at the wave close.
 * Usage: node tools/findability_benchmark.mjs
 */
import { chromium } from 'playwright';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';

const QUESTIONS = [
  { q: 'Where do I see overdue PMs?',            start: 'logbook',      search: 'PM',           landRe: /pm-scheduler/ },
  { q: 'Where do I check spare part stock?',     start: 'community',    search: 'inventory',    landRe: /inventory/ },
  { q: 'Where do I ask the AI a question?',      start: 'inventory',    search: 'assistant',    landRe: /assistant/ },
  { q: "Where is my team's live board?",         start: 'logbook',      search: 'hive',         landRe: /hive/ },
  { q: 'Where do I build my resume?',            start: 'pm-scheduler', search: 'resume',       landRe: /resume/ },
  { q: 'Where do I log a repair?',               start: 'analytics',    search: 'logbook',      landRe: /logbook/ },
  { q: 'Where do I plan my day?',                start: 'logbook',      search: 'day',          landRe: /dayplanner/ },
  { q: 'Where are the plant KPIs?',              start: 'inventory',    search: 'analytics',    landRe: /analytics/, role: 'supervisor' },
  { q: 'Where do I take a skill quiz?',          start: 'logbook',      search: 'skill',        landRe: /skillmatrix/ },
  { q: 'Where are my badges and XP?',            start: 'logbook',      search: 'growth',       landRe: /achievements|skillmatrix/ },
  { q: 'Where do I buy or sell parts?',          start: 'inventory',    search: 'marketplace',  landRe: /marketplace/ },
  { q: 'Where do I ask my hive-mates?',          start: 'logbook',      search: 'community',    landRe: /community/ },
  { q: 'Where is the shift handover plan?',      start: 'logbook',      search: 'shift',        landRe: /shift-brain/ },
  { q: 'Where do I record a voice note?',        start: 'logbook',      search: 'voice',        landRe: /voice-journal/ },
  { q: 'Where are the plant alerts?',            start: 'logbook',      search: 'alert',        landRe: /alert-hub/ , role: 'supervisor', },
  { q: 'Where do I manage assets?',              start: 'logbook',      search: 'asset',        landRe: /asset-hub/ , role: 'supervisor', },
  { q: 'Where do I run an engineering calc?',    start: 'logbook',      search: 'design',       landRe: /engineering-design/ , role: 'supervisor', },
  { q: 'Where do I manage projects?',            start: 'logbook',      search: 'project',      landRe: /project-manager/ , role: 'supervisor', },
  { q: 'Where do I email a report to my boss?',  start: 'analytics',    search: 'report',       landRe: /report-sender/ , role: 'supervisor', },
  { q: 'Where do I connect SAP or a CMMS?',      start: 'logbook',      search: 'integration',  landRe: /integrations/ , role: 'supervisor', },
];

const browser = await chromium.launch();
// Two persona lanes: questions default to the WORKER; supervisor-lane questions declare
// role:'supervisor' (the hub's role scoping is part of the design, so the benchmark asks
// each question AS the persona who owns it — T173's role-aware form, 2026-08-25).
const wctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(wctx, 'worker'));
const sctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(sctx, 'supervisor'));
const wp = await wctx.newPage();
const sp = await sctx.newPage();
let pass = 0;
for (const t of QUESTIONS) {
  const p = t.role === 'supervisor' ? sp : wp;
  await p.goto(`${ORIGIN}/${t.start}.html`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(6000);
  // interaction 1: open the hub
  await p.evaluate(() => document.getElementById('wh-hub-fab')?.click());
  await p.waitForTimeout(900);
  // interaction 2: tap the tool entry whose label matches
  const landed = await p.evaluate((needle) => {
    const links = [...document.querySelectorAll('#wh-hub-panel a, .wh-hub-item')]
      .filter((a) => a.getClientRects().length);
    const hit = links.find((a) => (a.textContent || '').toLowerCase().includes(needle.toLowerCase()))
      || links.find((a) => (a.getAttribute('href') || '').toLowerCase().includes(needle.toLowerCase()));
    if (!hit) return null;
    const href = hit.getAttribute('href');
    hit.click();
    return href;
  }, t.search);
  await p.waitForTimeout(2500);
  const url = p.url();
  const ok = landed !== null && t.landRe.test(url);
  console.log(`${ok ? 'PASS' : 'FAIL'}  "${t.q}" — from ${t.start} via hub -> ${url.split('/').pop()}`);
  if (ok) pass++;
}
console.log(`findability: ${pass}/${QUESTIONS.length} answered in <=2 interactions`);
process.exit(pass === QUESTIONS.length ? 0 : 1);
