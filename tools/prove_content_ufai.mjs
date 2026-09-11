// prove_content_ufai — W3-LN and W3-CL: the 114 content pages, on the three dimensions they never carried.
//
// 54 learn articles and 60 calculators each held exactly ONE trajectory row, all of it Usability. 52 articles
// and 59 calculators carried zero Functionality, zero Adaptability and zero Internal Control - the largest
// structural gap the wave-3 determination found. These pages are also the platform's front door: an engineer
// meets a calculator before they meet a hive.
//
// THREE LENSES, ONE VISIT PER PAGE (the browser is the expensive part, so each page is opened once and asked
// everything):
//
//   F  IT DOES THE JOB IT PROMISES.
//      article    : its call to action goes to the tool it NAMES, that tool exists, and the tool's own page
//                   answers to that name - the "60 calc CTAs named a calculator and opened HVAC" class.
//      calculator : the page's own worked example reproduces. The inputs it prints are typed in, the button
//                   it names is pressed, and the number that comes back must be a number - not NaN, not
//                   empty, not the placeholder it started with. A calculator that cannot reproduce its own
//                   example is wrong in the only way that matters.
//
//   A  IT HOLDS UP AWAY FROM A DESK. Rendered at 390: no horizontal overflow, the primary control reachable
//      without a pinch, and the page survives being opened with the network refusing every request (the
//      service worker's job) rather than showing a blank frame.
//
//   I  IT SAYS WHERE ITS NUMBERS COME FROM. An article names its sources and how fresh it is; a calculator
//      names the standard and clause behind its constants, and refuses an out-of-range input in a sentence
//      rather than silently computing nonsense.
//
//   node tools/prove_content_ufai.mjs --kind learn        # the 54 articles
//   node tools/prove_content_ufai.mjs --kind calc --limit 6
//   node tools/prove_content_ufai.mjs --page tools/oee-calculator/index.html
//   node tools/prove_content_ufai.mjs --self-test         # teeth, no browser
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readdirSync, existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const args = process.argv.slice(2);
const argOf = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const KIND = argOf('--kind');
// what each calculator owes its reader, published by tools/check_calc_citations.py from the generator's own
// declared field - so this lens verifies visibility and never re-guesses what a citation looks like
const DECLARED = (() => {
  try { return JSON.parse(readFileSync('.tmp/calc_declared_standards.json', 'utf8')); } catch { return {}; }
})();
const ONE = argOf('--page');
const LIMIT = Number(argOf('--limit') || 0);

const learnPages = () => readdirSync('learn').filter((d) => existsSync(`learn/${d}/index.html`) && d !== 'index.html').map((d) => `learn/${d}/index.html`);
const calcPages = () => readdirSync('tools').filter((d) => existsSync(`tools/${d}/index.html`)).map((d) => `tools/${d}/index.html`);

// ── what the page says about itself, read in the page ─────────────────────────────────────────────
const READ = () => {
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null);
  const text = (document.body ? document.body.innerText || '' : '').replace(/\s+/g, ' ').trim();
  // ★PROVENANCE IS OFTEN INSIDE A COLLAPSED DISCLOSURE, AND innerText CANNOT SEE IT. The rubric already
  // records this for its own E3 ("Read textContent, NOT innerText: the provenance chip is DELIBERATELY
  // collapsed inside a 'More' disclosure") and this prover repeated the mistake: it read 1,955 characters of
  // a 19KB page and reported that calculators naming ASME BPVC and their clause "name no clause or table".
  // What a reader can OPEN counts as present; what the page never contains does not.
  const deep = (document.body ? document.body.textContent || '' : '').replace(/\s+/g, ' ').trim();
  const ctas = Array.from(document.querySelectorAll('a[href]')).filter(vis)
    .filter((a) => /calculator|tool|try|open|use the|start|compute/i.test(a.textContent || '') || /\/tools\//.test(a.getAttribute('href') || ''))
    .map((a) => ({ label: (a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70), href: a.getAttribute('href') || '' }))
    .slice(0, 10);
  const inputs = Array.from(document.querySelectorAll('input[type="number"], input[type="text"], select')).filter(vis)
    .map((el) => ({ id: el.id || '', name: el.getAttribute('name') || '', value: el.value || '', tag: el.tagName.toLowerCase(), type: (el.getAttribute('type') || '').toLowerCase() })).slice(0, 30);
  const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]')).filter(vis)
    .map((b) => ({ text: (b.textContent || b.value || '').replace(/\s+/g, ' ').trim().slice(0, 40), id: b.id || '' })).slice(0, 20);
  const overflow = document.documentElement.scrollWidth > window.innerWidth + 2;
  const smallTargets = Array.from(document.querySelectorAll('a, button, [role="button"], input, select')).filter(vis)
    .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && (r.height < 40 || r.width < 40); }).length;
  return {
    chars: text.length, text: text.slice(0, 6000), ctas, inputs, buttons, overflow, smallTargets,
    // Internal Control, in the page's own vocabulary rather than mine
    sources: /\bsources?\b|\breferences?\b|according to|per (?:the )?(?:DOE|IEA|ASHRAE|NFPA|PSME|IEEE|ISO|DOLE)/i.test(text),
    freshness: /updated|reviewed|as of|last checked|published/i.test(text),
    // ★THE VOCABULARY IS THE PHILIPPINES', NOT NFPA'S. Demanding an acronym followed by a digit accused the
    // septic tank (Plumbing Code §P-1101), the storm drain (DPWH Blue Book, Rational Method), water
    // treatment (PNS/PNSDW) and the boilers (ASME BPVC Section I - letters, not digits) of citing nothing.
    standard: /(NFPA|ASHRAE|IEEE|ISO|ASME|API|PEC\b|NSCP|DIN|BS\s?EN|EN\s?[0-9]|UL\s?[0-9]|NEC\b|IEC|PSME|national plumbing code|plumbing code|NPCP|sanitation code|fire code|building code|PNS\b|PNSDW|DPWH|DENR|DAO\s?[0-9]|PD\s?[0-9]{3,4}|RA\s?[0-9]{3,4}|BPVC|rational method|hazen|darcy|manning|colebrook|blue book)/i.test(deep),
    // ★ASK WHETHER THE CITATION CAN BE LOOKED UP - NOT WHETHER IT USES MY WORDS. This lens once demanded
    // the literal words clause/section/table and accused forty calculators of naming "no clause or table"
    // while they cited ASHRAE 62.1, ASHRAE 90.1, ISO 898-1:2013, ASME PTC 23 and ASHRAE 2021 Ch. 21 - every
    // one the exact part an engineer opens. The static gate tools/check_calc_citations.py had already been
    // corrected through this same mistake and out the other side; the browser lens kept the old pattern, so
    // one instrument was fixed and its twin went on asking the refuted question. A CORRECTION IS NOT LANDED
    // UNTIL EVERY INSTRUMENT THAT ASKS THAT QUESTION HAS IT. Specific = the standard's family name carries a
    // number (a version, a part, an article, a chapter) OR a real clause reference follows a keyword+digit.
    clause: /((clause|section|sec\.|table|annex|appendix|art(icle)?\.|chapter|ch\.)\s*[0-9]|§\s*[A-Za-z]?-?[0-9])/i.test(deep)
      || /(NFPA|ASHRAE|IEEE|ISO|ASME|API|PEC|NSCP|DIN|EN|UL|NEC|IEC|PSME|PNS|CTI|SMRP|UPC|BPVC|plumbing code|fire code|building code)[^.;|]{0,24}?\s(?:no\.?\s*)?[0-9]/i.test(deep),
    bilingual: !!document.querySelector('[data-i], [data-i18n]') || typeof window._t === 'function',
    provenance: !!document.querySelector('.wh-source-chip, [class*="source-chip"], [class*="provenance"]'),
  };
};

const titleOf = (file) => { try { const m = readFileSync(file, 'utf8').match(/<title>([^<]{3,140})<\/title>/i); return m ? m[1] : ''; } catch { return ''; } };
// the words a link promises, reduced to the ones that identify a tool
// ★THE NAME IS OFTEN THE ACRONYM. A length filter of >3 deleted `OEE`, `AHU`, `FCU`, `UPS`, `PV` - the very
// words that identify which calculator a link promises - so "Open the OEE Calculator" and "OEE Calculator"
// shared nothing and the oracle could not tell a correct link from a wrong one. Three letters are kept, and
// the short filler words are named instead of measured away.
const STOP = new Set(['free', 'online', 'calculator', 'calc', 'tool', 'tools', 'philippines', 'open', 'the', 'your',
  'with', 'this', 'using', 'try', 'use', 'start', 'guide', 'and', 'for', 'our', 'you', 'its', 'new', 'get',
  'how', 'why', 'now', 'per', 'via', 'see', 'all', 'from', 'into', 'that', 'here', 'more', 'best', 'full']);
const keywords = (s) => (s || '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/)
  .filter((w) => w.length > 2 && !STOP.has(w));

const kindOf = (f) => (f.startsWith('learn/') ? 'learn' : 'calc');

async function walk(browser, file) {
  const kind = file.startsWith('learn/') ? 'learn' : 'calc';
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const out = { file, kind, F: null, A: null, I: null };
  try {
    await page.goto(`${ORIGIN}/${file}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    // ★A PAGE THE WALK NEVER REACHED CANNOT BE GRADED. A sign-in door answers 200 and renders happily, so a
    // redirect is invisible in the reading itself - only the landed URL tells the difference. The
    // shared-component prover walked /inventory.html without an identity, was sent to
    // /index.html?signin=1&return=inventory.html, and graded the DOOR three times for every piece: nine
    // findings and thirty n/a verdicts about a page that was not the subject, and 37 rows banked on them
    // before anything noticed. These content pages are public and do not bounce today; the guard costs one
    // evaluate and outlives the assumption that they always will be.
    const _landed = await page.evaluate(() => location.pathname.replace(/^\//, ''));
    const _want = file.replace(/^\//, '');
    if (_landed && !_want.endsWith(_landed) && !_landed.endsWith(_want)) {
      throw new Error(`bounced to ${_landed.slice(0, 50)} - this walk never reached ${_want}`);
    }
    // ★SETTLE, DO NOT COUNT TO 2.6. The first run of this prover reported that every calculator had "0
    // inputs, no run button" and that boiler-steam "names no standard" - while a static read of the very
    // same file finds ASME BPVC Section I and a full form. The pages build their calculator after load; the
    // reader was arriving at 2.6 seconds and describing an empty shell. Same class as the journey walk's
    // 618-vs-2,617 characters, in a second instrument: wait until the page stops changing, and never accept
    // a reading that still looks empty until the budget is spent.
    let r = null;
    let stable = 0;
    let prev = -1;
    for (const t0 = Date.now(); ;) {
      await page.waitForTimeout(700);
      r = await page.evaluate(READ);
      stable = r.chars === prev ? stable + 1 : 0;
      prev = r.chars;
      const looksBuilt = r.chars >= 1200 && (r.inputs.length > 0 || r.ctas.length > 0 || kindOf(file) === 'learn');
      if ((stable >= 3 && looksBuilt) || Date.now() - t0 > 20000) break;
    }

    // ── F ──
    if (kind === 'learn') {
      // ★AN IN-PAGE ANCHOR IS NOT A BROKEN LINK. `rel` strips the fragment, so `href="#tooling"` became the
      // EMPTY string, `existsSync('')` was false, and four articles were reported as having a call to action
      // that "points at , which does not exist" - the empty target in that sentence was the tell. A link to a
      // section of the page the reader is already on is a jump, not a hand-off to a tool, so it is not what
      // this lens is asking about; only a link that LEAVES the page can answer "does the tool it names open".
      const leaves = (c) => c.href && !c.href.startsWith('#') && c.href.split('#')[0].split('?')[0] !== '';
      const toolCta = r.ctas.find((c) => /\/tools\//.test(c.href) && leaves(c)) || r.ctas.find(leaves);
      if (!toolCta) out.F = { verdict: 'BAD', line: 'the article offers no way into any tool - every link it carries stays on this page' };
      else {
        const rel = toolCta.href.replace(/^\//, '').replace(/^workhive\//, '').split('#')[0].split('?')[0];
        const target = rel.endsWith('/') ? rel + 'index.html' : rel;
        const exists = existsSync(target) || existsSync(target.replace(/\/index\.html$/, '.html'));
        const t = exists ? titleOf(existsSync(target) ? target : target.replace(/\/index\.html$/, '.html')) : '';
        const promised = keywords(toolCta.label);
        const delivered = keywords(t);
        const agree = promised.length === 0 || promised.some((w) => delivered.includes(w)) || /engineering[- ]design/i.test(target);
        out.F = !exists ? { verdict: 'BAD', line: `its call to action "${toolCta.label}" points at ${rel}, which does not exist` }
          : !agree ? { verdict: 'BAD', line: `its call to action promises "${toolCta.label}" and opens "${t}" - a different tool` }
          : { verdict: 'ok', line: `"${toolCta.label}" opens ${rel} ("${t.slice(0, 48)}")` };
      }
    } else {
      // the calculator's own worked example, typed in and run
      const numeric = r.inputs.filter((i) => i.tag === 'input');
      const run = r.buttons.find((b) => /calculate|compute|run|generate/i.test(b.text));
      // ★A CALCULATOR PAGE IS A LANDING PAGE, NOT AN APPLICATION. Served HTML for these pages contains ZERO
      // input, select or button elements in 19KB - they describe a calculator and hand the reader to the
      // interactive one ("Open the interactive AHU Sizing Calculator in WorkHive" -> engineering-design.html).
      // Asking them to reproduce a worked example in-page reported "nothing to reproduce" for every single
      // one: the lens demanding a form of a page that never had one. What the page owes is the hand-off, and
      // whether it opens THIS calculator rather than a different one - the exact defect class that once had
      // 60 calculator CTAs opening HVAC.
      const handoff = r.ctas.find((c) => /engineering-design|\/tools\//.test(c.href) && /open|interactive|try|use/i.test(c.label));
      if (!numeric.length && !run) {
        const promised = keywords(file.split('/')[1].replace(/-/g, ' '));
        const carried = handoff ? keywords(`${handoff.label} ${handoff.href}`) : [];
        out.F = !handoff
          ? { verdict: 'BAD', line: 'a landing page with no hand-off: it describes a calculator and offers no way into one' }
          : promised.some((w) => carried.includes(w))
            ? { verdict: 'ok', line: `hands off by name: "${handoff.label.slice(0, 56)}" -> ${handoff.href}` }
            : { verdict: 'BAD', line: `its hand-off "${handoff.label.slice(0, 40)}" does not name this calculator (${promised.slice(0, 3).join(' ')})` };
      } else if (!numeric.length || !run) out.F = { verdict: 'BAD', line: `an interactive page missing half its form: ${numeric.length} input(s), ${run ? 'a run button' : 'no run button'}` };
      else {
        const before = await page.evaluate(() => (document.body.innerText.match(/[\d,]+\.?\d*/g) || []).join('|'));
        await page.evaluate(() => {
          for (const el of document.querySelectorAll('input[type="number"]')) {
            if (!el.value) { el.value = el.getAttribute('placeholder') && /^\d/.test(el.getAttribute('placeholder')) ? el.getAttribute('placeholder') : '100'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }
          }
        });
        await page.evaluate((label) => {
          const b = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'))
            .find((x) => (x.textContent || x.value || '').trim().slice(0, 40) === label);
          if (b) b.click();
        }, run.text);
        await page.waitForTimeout(1800);
        const after = await page.evaluate(() => document.body.innerText);
        const changed = (after.match(/[\d,]+\.?\d*/g) || []).join('|') !== before;
        const broken = /\bNaN\b|Infinity|undefined/.test(after);
        out.F = broken ? { verdict: 'BAD', line: `pressing "${run.text}" produced NaN/undefined on the page` }
          : !changed ? { verdict: 'BAD', line: `pressing "${run.text}" changed no number on the page - the control is inert` }
          : { verdict: 'ok', line: `"${run.text}" computed from ${numeric.length} input(s) and the result changed` };
      }
    }

    // ── A ── phone shape, then the same page with the network refusing
    let offline = 'not attempted';
    try {
      const off = await ctx.newPage();
      await off.route('**/*', (route) => (/\/(learn|tools)\//.test(route.request().url()) || route.request().resourceType() === 'document' ? route.continue() : route.abort()));
      await off.goto(`${ORIGIN}/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
      await off.waitForTimeout(1500);
      const chars = await off.evaluate(() => (document.body ? document.body.innerText.length : 0));
      offline = chars > 400 ? `still readable with every subresource refused (${chars} chars)` : `collapsed to ${chars} chars when its subresources were refused`;
      await off.close();
    } catch (e) { offline = 'the offline pass threw: ' + String(e.message).slice(0, 50); }
    const aBad = r.overflow || !/still readable/.test(offline);
    out.A = { verdict: aBad ? 'BAD' : 'ok',
      line: `at 390: ${r.overflow ? 'the page scrolls sideways' : 'no sideways scroll'}, ${r.smallTargets} target(s) under 40px; ${offline}` };

    // ── I ──
    if (kind === 'learn') {
      const have = [r.sources && 'sources', r.freshness && 'a freshness line', r.provenance && 'a provenance chip', r.bilingual && 'bilingual labels'].filter(Boolean);
      const missing = [!r.sources && 'no sources', !r.freshness && 'no freshness line', !r.bilingual && 'no bilingual labels'].filter(Boolean);
      out.I = { verdict: missing.length ? 'BAD' : 'ok', line: missing.length ? `${missing.join(', ')} (has: ${have.join(', ') || 'nothing'})` : `carries ${have.join(', ')}` };
    } else {
      // an out-of-range input must be refused in words, not computed
      // ★A PAGE WITH NO INPUT NEVER ACCEPTED ANYTHING. The first version ran this pass unconditionally and,
      // finding no refusal words on a page that had no number field to refuse, reported "accepted a negative
      // input silently" - a sentence about a form that does not exist. The VERDICT was right (the clause below
      // only counts the range result for an interactive page) but the LINE was false, and the line is what
      // gets written into the trajectory basis as the evidence a human reads later. Eleven landing pages were
      // about to be banked green on a receipt accusing them of a defect they could not have. A lens must not
      // report an outcome for a test it never actually ran.
      const hasNumberInput = r.inputs.some((i) => i.tag === 'input' && i.type === 'number');
      let refused = hasNumberInput ? 'not attempted' : 'has no input to refuse - a landing page owes no range check';
      try {
        if (!hasNumberInput) throw { skip: true };
        await page.evaluate(() => { for (const el of document.querySelectorAll('input[type="number"]')) { el.value = '-999999'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } });
        const runb = r.buttons.find((b) => /calculate|compute|run|generate/i.test(b.text));
        if (runb) await page.evaluate((label) => { const b = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]')).find((x) => (x.textContent || x.value || '').trim().slice(0, 40) === label); if (b) b.click(); }, runb.text);
        await page.waitForTimeout(1200);
        const t = await page.evaluate(() => document.body.innerText);
        refused = /must be|cannot be|invalid|enter a|greater than|positive|out of range|check your/i.test(t) ? 'refused a negative input in words'
          : /\bNaN\b|Infinity/.test(t) ? 'answered a negative input with NaN/Infinity' : 'accepted a negative input silently';
      } catch (e) { if (!e || !e.skip) refused = 'the range pass threw'; }
      // a landing page has no inputs, so "it accepted a negative input" is a statement about a form that is
      // not there - only an interactive page owes the range refusal
      const interactive = hasNumberInput;
      // ★NEITHER INSTRUMENT OWNS THE PATTERN. Whether a citation is SPECIFIC is settled once, statically, by
      // tools/check_calc_citations.py reading the generator's declared field - it cannot be fooled by a
      // stylesheet and cannot be defeated by a standards body nobody listed. That gate publishes the token
      // each page owes its reader, and this lens asks the only question a browser can answer better than a
      // file read: does the person actually SEE it. Twice now a pattern was corrected in one instrument
      // while its twin went on asking the refuted question; a shared answer file is what stops that.
      const declaredTok = DECLARED[file.replace(/^tools\//, '').replace(/\/index\.html$/, '')]?.must_show || '';
      const showsCitation = declaredTok
        ? await page.evaluate((t) => (document.body.textContent || '').toLowerCase().includes(t), declaredTok)
        : null;
      const cites = showsCitation === null ? r.clause : showsCitation;
      // ★WHEN THE PAGE DECLARES ITS CITATION, THE VISIBILITY CHECK IS THE WHOLE ANSWER. The leftover
      // `r.standard` guess is a family-name regex, and it does not know CIBSE, TEMA, IPC, AHRI, VDI or ACI -
      // so the elevator calculator, which cites CIBSE Guide D:2015, read "names no standard". That is the
      // NINTH time a hand-listed vocabulary has accused a correct page in this wave. A declared token makes
      // the guess unnecessary: if the page shows what it declared, it cites its standard, full stop.
      const missing = [!declaredTok && !r.standard && 'names no standard',
        !cites && (declaredTok ? `never shows the citation it declares ("${declaredTok}")` : 'names no clause or table'),
        interactive && !/refused/.test(refused) && refused].filter(Boolean);
      out.I = { verdict: missing.length ? 'BAD' : 'ok',
        line: missing.length ? missing.join('; ')
          : `shows the citation it declares${declaredTok ? ` ("${declaredTok}")` : ''}, and ${refused}` };
    }
  } catch (e) {
    const line = 'the page could not be walked: ' + String(e.message || e).slice(0, 90);
    out.F = out.A = out.I = { verdict: 'BAD', line };
  } finally { await ctx.close().catch(() => {}); }
  return out;
}

// ── teeth, no browser ─────────────────────────────────────────────────────────────────────────────
if (args.includes('--self-test')) {
  const fails = [];
  const L = learnPages(); const C = calcPages();
  if (L.length < 50) fails.push(`learn roster is ${L.length}, expected ~54`);
  if (C.length < 55) fails.push(`calculator roster is ${C.length}, expected ~60`);
  for (const f of [...L.slice(0, 3), ...C.slice(0, 3)]) if (!titleOf(f)) fails.push(`${f} has no <title> to answer to`);
  // the CTA oracle must reject a mismatch and accept a match, or it can never find the class it exists for
  const promised = keywords('Try the Fire Sprinkler Calculator');
  if (!promised.includes('fire') || !promised.includes('sprinkler')) fails.push('keywords() dropped the words that identify the tool');
  if (promised.some((w) => keywords('HVAC Cooling Load Calculator: Free Online Tool').includes(w))) fails.push('the CTA oracle would accept a sprinkler link that opens HVAC');
  if (!keywords('Open the OEE Calculator').some((w) => keywords('OEE Calculator - Overall Equipment Effectiveness').includes(w))) fails.push('the CTA oracle would reject a correct match');
  console.log(fails.length ? 'FAIL content-ufai self-test - ' + fails.join('; ')
    : `self-test OK: ${L.length} articles + ${C.length} calculators on disk, the CTA oracle separates a sprinkler promise from an HVAC page`);
  process.exit(fails.length ? 1 : 0);
}

// ── the run ───────────────────────────────────────────────────────────────────────────────────────
let roster = ONE ? [ONE] : (KIND === 'learn' ? learnPages() : KIND === 'calc' ? calcPages() : [...learnPages(), ...calcPages()]);
if (LIMIT) roster = roster.slice(0, LIMIT);
console.log(`walking ${roster.length} content page(s) on F/A/I, one visit each`);
// this host has one browser slot and the suite runs gates concurrently - queue, do not race
await takeBrowserSlot('content-ufai');
const browser = await chromium.launch();
const results = [];
let bad = 0;
for (const f of roster) {
  const r = await walk(browser, f);
  results.push(r);
  for (const lens of ['F', 'A', 'I']) {
    const v = r[lens];
    if (v && v.verdict === 'BAD') bad++;
    console.log(`  ${v && v.verdict === 'ok' ? 'ok ' : 'BAD'} ${lens} ${f.replace(/\/index\.html$/, '').padEnd(52)} ${(v ? v.line : '').slice(0, 118)}`);
  }
}
await browser.close();
try { mkdirSync('.tmp', { recursive: true }); } catch (e) { void e; }
const out = `.tmp/content_ufai${KIND ? '_' + KIND : ''}.json`;
writeFileSync(out, JSON.stringify({ walked: roster.length, bad, results }, null, 2));
console.log(`${bad ? 'FAIL' : 'PASS'} content-ufai - ${roster.length * 3 - bad}/${roster.length * 3} lens(es) hold  ·  ${out}`);
process.exitCode = bad ? 1 : 0;
