// prove_read_only_lane — a person who only READS is never forced to write.
//
// ★THE PERSONA (T53). Not every account operates the plant. A manager, an owner, a client on a
// site visit signs in to LOOK: what is overdue, what broke, is the fleet healthy. They open a
// surface, read it, and leave. That lane has no gate of its own, because every existing journey
// asserts that an ACTION succeeds — and an action-shaped oracle cannot see the defect this
// persona meets, which is being stopped before reading anything at all.
//
// THE ORACLE, and why it is checkable without deciding anything: whether the exec should get a
// different LANDING is a design call and stays Ian's. Whether a reader is FORCED INTO A WRITE is
// not a matter of taste — it is observable on arrival, before any interaction. So this walks each
// exec-shaped surface signed in, waits for it to settle, and requires that a reader meets:
//
//   - no blocking modal over the content        (a dialog that must be answered to read)
//   - no body-scroll lock                        (a page that will not let them scroll)
//   - no auth / pick-a-hive wall                 (a signed-in reader re-asked to sign in)
//   - no stolen focus into a text input          (a keyboard opening on a phone at a reader)
//   - no uncaught page error
//   - and something actually READ: real words on the glass, not a shell
//
// ★THE LAST CLAUSE EXISTS BECAUSE THE FIRST FIVE ARE ALL ABSENCES. A blank page that failed to
// load passes every one of them: no modal, no lock, no wall, no focus theft. An all-absence
// oracle grades a dead page as a perfect reading experience, so the walk must also prove the
// reader got something. It counts VISIBLE TEXT rather than a figure count — T53's own walk twice
// misread a healthy surface as thin, once by counting characters mid-render and once by counting
// figures on a page whose correct state is an instruction with no figures.
//
// Read-only by construction: the walk never clicks, types or submits.
//
// USAGE:  node tools/prove_read_only_lane.mjs [--page <file>] [--width N] [--gate]
// OUTPUT: read_only_lane_report.json  (narrowed runs write their own)
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const WIDTH = (() => { const i = args.indexOf('--width'); return i >= 0 ? parseInt(args[i + 1], 10) : 1280; })();
const NARROW = [PAGE_ONLY ? `page-${PAGE_ONLY}` : '', args.indexOf('--width') >= 0 ? `w-${WIDTH}` : '']
  .filter(Boolean).join('.').replace(/[^\w.-]+/g, '_');
const REPORT = NARROW ? `read_only_lane_report.${NARROW}.json` : 'read_only_lane_report.json';

// The surfaces a read-mostly person actually opens. Deliberately NOT the whole roster: a reader
// does not open the logbook compose form, and demanding this property there would be enforcing an
// opinion about who may write.
const SURFACES = [
  { page: 'index.html',            why: 'the ops home - the first thing anyone sees' },
  { page: 'analytics.html',        why: 'the KPI surface an exec is most likely to be shown' },
  { page: 'alert-hub.html',        why: 'what needs attention, the read a manager asks for' },
  { page: 'analytics-report.html', why: 'the print-ready pack; its correct empty state is an INSTRUCTION' },
  { page: 'asset-hub.html',        why: 'fleet health at a glance' },
  { page: 'pm-scheduler.html',     why: 'compliance, read rather than operated' },
];

// A reader has read something when the page carries real prose. 220 chars is deliberately low:
// analytics-report's correct state is a single instruction sentence, and a threshold tuned to a
// dense dashboard would call that page broken.
const MIN_VISIBLE_CHARS = 220;

// The measurement, named so --teeth can re-run it against a deliberately broken page. Keeping ONE
// copy matters: a teeth mode that re-implements the oracle proves the copy works, not the gate.
const MEASURE = (minChars) => {
      const out = {};
      const vis = el => {
        if (!el) return false;
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') < 0.05) return false;
        const rc = el.getBoundingClientRect();
        return rc.width > 1 && rc.height > 1;
      };
      const modalish = Array.from(document.querySelectorAll(
        '[role="dialog"],[role="alertdialog"],dialog[open],.modal,.wh-modal,.sheet'))
        .filter(vis)
        .filter(el => {
          const rc = el.getBoundingClientRect();
          return (rc.width * rc.height) > (window.innerWidth * window.innerHeight * 0.25);
        });
      out.blockingModals = modalish.map(el => el.id || el.className || el.tagName).slice(0, 4);
      const bs = getComputedStyle(document.body);
      out.scrollLocked = (bs.overflow === 'hidden' || bs.position === 'fixed')
                      && document.body.scrollHeight > window.innerHeight + 40;
      out.url = location.pathname + location.search;
      const t = (document.body.innerText || '');
      out.wall = /sign in to continue|please sign in|choose a hive|pick a hive|select a hive/i.test(t);
      const ae = document.activeElement;
      out.focusStolen = !!(ae && /^(INPUT|TEXTAREA)$/.test(ae.tagName)
                        && !/^(checkbox|radio|button|submit)$/i.test(ae.type || ''));
      out.focusEl = out.focusStolen ? (ae.id || ae.name || ae.tagName) : null;
      out.visibleChars = t.replace(/\s+/g, ' ').trim().length;
      out.enoughToRead = out.visibleChars >= minChars;
      return out;
};

function findingsFor(obs, errors) {
  const f = [];
  if (obs.blockingModals.length) f.push(`a blocking dialog covers the page on arrival (${obs.blockingModals[0]}) - a reader must answer something before reading`);
  if (obs.scrollLocked)          f.push('the body is scroll-locked while the page is taller than the viewport - a reader cannot reach the rest');
  if (obs.wall)                  f.push('a signed-in reader meets a sign-in / pick-a-hive wall');
  if (obs.focusStolen)           f.push(`focus was taken into a text input (${obs.focusEl}) - on a phone that opens a keyboard at someone who came to read`);
  if (!obs.enoughToRead)         f.push(`only ${obs.visibleChars} visible chars - the reader got a shell, not a page (all the other clauses are ABSENCES and a blank page passes them)`);
  if (errors && errors.length)   f.push(`page error: ${errors[0]}`);
  return f;
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 900 } });
await signIn(ctx, 'supervisor');

// ── --teeth: each clause must actually FIRE ──────────────────────────────────────────────────
// A gate that locks behaviour which is ALREADY correct has never once been seen to go red, so
// without this it is a green light of unknown wiring. Each injection breaks exactly one clause on
// a real signed-in page, and the run asserts that clause - and only that clause - reports.
if (args.includes('--teeth')) {
  const INJECTIONS = [
    { id: 'blocking-modal', expect: /blocking dialog/, apply: () => {
        const d = document.createElement('div');
        d.setAttribute('role', 'dialog'); d.id = 'teeth-modal';
        d.style.cssText = 'position:fixed;inset:0;background:#000;z-index:99999;';
        document.body.appendChild(d);
      } },
    { id: 'scroll-lock', expect: /scroll-locked/, apply: () => {
        const s = document.createElement('div'); s.style.height = '4000px'; document.body.appendChild(s);
        document.body.style.overflow = 'hidden';
      } },
    { id: 'auth-wall', expect: /sign-in \/ pick-a-hive wall/, apply: () => {
        const w = document.createElement('p'); w.textContent = 'Please sign in to continue';
        document.body.appendChild(w);
      } },
    { id: 'focus-theft', expect: /focus was taken/, apply: () => {
        const i = document.createElement('input'); i.type = 'text'; i.id = 'teeth-input';
        document.body.appendChild(i); i.focus();
      } },
    { id: 'blank-shell', expect: /got a shell/, apply: () => { document.body.innerHTML = '<span>x</span>'; } },
  ];
  let bad = 0;
  console.log('read-only-lane --teeth: each clause must fire on a deliberately broken page\n');
  for (const inj of INJECTIONS) {
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(8000);
    const clean = findingsFor(await p.evaluate(MEASURE, MIN_VISIBLE_CHARS), []);
    await p.evaluate(inj.apply);
    const broken = findingsFor(await p.evaluate(MEASURE, MIN_VISIBLE_CHARS), []);
    const fired = broken.some(f => inj.expect.test(f));
    // non-vacuity: the clean page must NOT already report it, or "it fired" proves nothing
    const wasCleanBefore = !clean.some(f => inj.expect.test(f));
    const ok = fired && wasCleanBefore;
    if (!ok) bad++;
    console.log(`  ${ok ? 'ok  ' : 'MISS'} ${inj.id.padEnd(16)} clean=${clean.length} broken=${broken.length}${wasCleanBefore ? '' : '  (clean page ALREADY reported it - vacuous)'}`);
    await p.close();
  }
  await browser.close();
  console.log(`\nTEETH ${bad ? 'FAILED' : 'ok'} - ${INJECTIONS.length - bad}/${INJECTIONS.length} clauses fire`);
  process.exit(bad ? 1 : 0);
}

const results = [];
for (const s of SURFACES) {
  if (PAGE_ONLY && s.page !== PAGE_ONLY) continue;
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  let r = { page: s.page, why: s.why, findings: [] };
  try {
    await p.goto(`${SEEDER}/workhive/${s.page}`, { waitUntil: 'domcontentloaded' });
    // Settle. T53's walk misread two healthy pages by measuring mid-render; a reader waits.
    await p.waitForTimeout(9000);
    const obs = await p.evaluate(MEASURE, MIN_VISIBLE_CHARS);
    Object.assign(r, obs);
    r.findings.push(...findingsFor(obs, errors));
  } catch (e) {
    r.findings.push(`walk failed: ${String(e).slice(0, 120)}`);
  }
  results.push(r);
  await p.close();
}
await browser.close();

const failing = results.filter(r => r.findings.length);
const report = {
  generated_by: 'tools/prove_read_only_lane.mjs',
  width: WIDTH,
  surfaces: results.length,
  failing: failing.length,
  min_visible_chars: MIN_VISIBLE_CHARS,
  results,
};
writeFileSync(REPORT, JSON.stringify(report, null, 2));

console.log(`read-only-lane - a person who only READS is never forced to write  (${WIDTH}px)`);
for (const r of results) {
  const mark = r.findings.length ? 'FAIL' : 'ok  ';
  console.log(`  ${mark} ${r.page.padEnd(22)} ${r.visibleChars ?? '?'} chars read`);
  for (const f of r.findings) console.log(`         ${f}`);
}
console.log(`\n  ${results.length - failing.length}/${results.length} surfaces let a reader read.`);
if (failing.length) {
  console.log('\nFAIL - a read-mostly person is blocked or handed a shell.');
  process.exit(GATE ? 1 : 0);
}
console.log('\nPASS - every exec-shaped surface opens, settles and reads without demanding a write.');
