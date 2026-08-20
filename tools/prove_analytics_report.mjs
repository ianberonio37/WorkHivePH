// prove_analytics_report.mjs — the CD/CI block of the one page whose render target is PAPER.
//
// ★WHY THIS PAGE NEEDED ITS OWN PROVER. analytics-report renders NOTHING on load: `#ar-cover`,
// `#ar-exec`, `#ar-findings`, `#ar-predictive`, `#ar-action`, `#ar-appendix` and `#ar-footer` do not
// exist until `generateReport()` runs (analytics-report.html:707). Every generic prover in this bank
// loads a page and reads it, so every one of them measured an EMPTY MOUNT here and could only ever
// return UNGRADED. The missing structure was a walk that presses Generate and then reads the
// document it produces — on screen AND on paper.
//
// ★GENERATE ONCE, REPLAY AFTERWARDS — because the boundary costs a model call. `phase:'report'` fans
// four phases out to a LOCAL python service and then, optionally, calls Groq for the action plan
// (analytics-orchestrator/index.ts:951-971; on failure `actionPlan = null` and the report still
// renders). So a generation is cheap but not free, and several rows here need the SAME report read
// two or three times — once on screen, once under print emulation, once after a reload. Regenerating
// per reading would spend a call each time AND would measure a DIFFERENT report each time, which is
// precisely what `closed_period_stable` exists to detect. So the first generation passes through and
// its response is captured to disk; every later one is fulfilled from that capture. One call, and
// the repeat-stability question becomes answerable instead of confounded.
//
// ★MEASURING A REPLAY IS NOT MEASURING MY OWN FIXTURE. The captured payload is the REAL orchestrator
// response — I did not author a number in it. What the replay tests is the RENDERER: whether the
// template puts a standard beside a metric, a horizon beside a forecast, evidence under a finding.
// Those are properties of analytics-report.html, not of the payload. Where a row genuinely depends
// on the DATA rather than the renderer, the replay is never used to settle it.
//
// NON-WRITING: one POST to the orchestrator, which is a read/compute endpoint. No row is written.
//
// USAGE:  node tools/prove_analytics_report.mjs [--fresh]
// OUTPUT: analytics_report_report.json   ·  capture: .tmp/ar_payload.json

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const CAP = path.join(ROOT, '.tmp', 'ar_payload.json');
const args = process.argv.slice(2);
const REPLAY = !args.includes('--fresh') && existsSync(CAP);

const SECTIONS = ['ar-cover', 'ar-exec', 'ar-findings', 'ar-predictive', 'ar-action', 'ar-appendix',
  'ar-footer'];

// Read every section the same way on screen and on paper, so the two are comparable like-for-like.
const readDoc = (ids) => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const o = { sections: {} };
  for (const id of ids) {
    const el = document.getElementById(id);
    o.sections[id] = el
      ? { present: true, vis: vis(el), h: Math.round(el.getBoundingClientRect().height),
        text: (el.innerText || '').replace(/\s+/g, ' ').trim() }
      : { present: false, vis: false, h: 0, text: '' };
  }
  o.docText = ((document.getElementById('ar-doc') || document.body).innerText || '')
    .replace(/\s+/g, ' ').trim();
  // ★THE COVER IS A PAGE, NOT A SECTION ELEMENT. `<section id="ar-cover">` opens at
  // analytics-report.html:819, but the report's own `Report Date:` and `Period: <start> – <end>
  // (90d)` are written at :814-815, inside the `.doc-header-row` that renders IMMEDIATELY ABOVE it.
  // Reading the section alone said the printed cover carried no generation date — a false RED
  // produced by measuring a container that excludes the very block being asked about. What a reader
  // holds is the first PAGE, so the subject is every #ar-doc child up to and including the one that
  // contains #ar-cover.
  const doc = document.getElementById('ar-doc');
  let cover = '';
  if (doc) {
    for (const child of doc.children) {
      cover += ' ' + (child.innerText || '');
      if (child.id === 'ar-cover' || child.querySelector('#ar-cover')) break;
    }
  }
  o.coverText = cover.replace(/\s+/g, ' ').trim();
  return o;
};

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 },
    serviceWorkers: 'block' });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, replay: REPLAY, checks: [] };
  const rec = (id, ok, why, saw) => {
    out.checks.push({ id, ok, why, saw: saw == null ? null : String(saw).slice(0, 320) });
    console.log('  ' + (ok === null ? 'UNGRADED' : ok ? 'PASS    ' : 'FAIL    ') + ' ' + id.padEnd(24)
      + ' ' + String(why).slice(0, 84));
  };

  const page = await ctx.newPage();
  let captured = REPLAY && existsSync(CAP) ? readFileSync(CAP, 'utf-8') : null;
  const envelopes = [];

  // ★THE ENVELOPE IS READ OFF THE WIRE, not inferred from the render. `envelope_shape` and
  // `status_body_agreement` ask what the boundary actually returned, so status and body are
  // recorded together, in the one place where they can still be compared.
  // ★THE REPLAY MUST NOT DELETE THE WAIT IT IS ASKED ABOUT. Fulfilling from disk returns in ~16ms,
  // so the "compiling…" state is gone long before any reader can see it and `slow_honest` failed a
  // page that announces itself correctly — the probe had removed the latency and then reported its
  // absence. A replay therefore holds the response for a beat so the announcement is observable.
  // The DURATION reported in the verdict is never this injected beat: it is the real generation time
  // measured on the capturing run and carried in the sidecar, because how long the orchestrator
  // takes is the product's fact and how long I stall is mine.
  const META = path.join(ROOT, '.tmp', 'ar_meta.json');
  const REPLAY_HOLD_MS = 3000;
  await ctx.route('**/functions/v1/analytics-orchestrator', async (route) => {
    if (captured) {
      envelopes.push({ from: 'replay', status: 200 });
      await new Promise((r) => setTimeout(r, REPLAY_HOLD_MS));
      return route.fulfill({ status: 200, contentType: 'application/json', body: captured });
    }
    const resp = await route.fetch();
    const body = await resp.text();
    envelopes.push({ from: 'live', status: resp.status(),
      ct: resp.headers()['content-type'] || '', len: body.length });
    captured = body;
    mkdirSync(path.dirname(CAP), { recursive: true });
    writeFileSync(CAP, body);
    return route.fulfill({ status: resp.status(), contentType: 'application/json', body });
  });

  await page.goto(ORIGIN + '/workhive/analytics-report.html',
    { waitUntil: 'domcontentloaded', timeout: 40000 });
  await page.waitForTimeout(9000);

  // ── slow_honest: what the person is told DURING the wait, read while it is still on screen.
  // A late read misses it entirely — the mount is replaced by the report the moment it arrives.
  const waitState = await page.evaluate(() => {
    const btn = document.getElementById('generate-btn');
    if (btn) btn.click();
    return new Promise((res) => setTimeout(() => {
      const m = document.querySelector('#ar-report-mount .ar-status');
      res({
        text: m ? (m.textContent || '').replace(/\s+/g, ' ').trim() : '',
        busy: m ? m.getAttribute('aria-busy') : null,
        live: m ? m.getAttribute('aria-live') : null,
        role: m ? m.getAttribute('role') : null,
        spinner: !!document.querySelector('#ar-report-mount .ar-spinner'),
        btnDisabled: !!(document.getElementById('generate-btn') || {}).disabled,
      });
    }, 400));
  });
  const t0 = Date.now();
  await page.waitForFunction(() => !!document.getElementById('ar-cover'), null, { timeout: 120000 })
    .catch(() => {});
  const genMs = Date.now() - t0;
  await page.waitForTimeout(2500);

  // The real generation time belongs to the capturing run; a replay's elapsed time is my own hold.
  let liveGenMs = genMs;
  if (REPLAY && existsSync(META)) {
    try { liveGenMs = JSON.parse(readFileSync(META, 'utf-8')).liveGenMs || genMs; } catch (_e) { /**/ }
  } else if (!REPLAY) {
    mkdirSync(path.dirname(META), { recursive: true });
    writeFileSync(META, JSON.stringify({ liveGenMs: genMs, at: new Date().toISOString() }));
  }

  const screen = await page.evaluate(readDoc, SECTIONS);
  out.genMs = genMs;
  out.liveGenMs = liveGenMs;
  out.waitState = waitState;

  if (!screen.sections['ar-cover'].present) {
    rec('generation', null, 'the report never rendered, so nothing on this page could be measured; '
      + 'UNGRADED rather than a pass over an empty set', JSON.stringify(waitState).slice(0, 260));
    writeFileSync(path.join(ROOT, 'analytics_report_report.json'), JSON.stringify(out, null, 1));
    await browser.close();
    return;
  }

  const doc = screen.docText;
  const has = (re) => { const m = re.exec(doc); return m ? m[0].replace(/\s+/g, ' ').trim() : null; };
  // ★A QUALIFIER MUST SIT NEAR ITS FIGURE. A body-wide keyword match reads the right words off the
  // wrong part of the page — the same shape that once scored a page on its own marketing copy. So
  // every proximity check scans ALL anchor occurrences and returns the first window that actually
  // contains the target, never just the neighbourhood of the first match.
  const near = (anchorRe, targetRe, span = 220) => {
    const re = new RegExp(anchorRe.source,
      anchorRe.flags.includes('g') ? anchorRe.flags : anchorRe.flags + 'g');
    for (let a = re.exec(doc); a; a = re.exec(doc)) {
      const w = doc.slice(Math.max(0, a.index - span), a.index + a[0].length + span);
      const m = targetRe.exec(w);
      if (m) return m[0].replace(/\s+/g, ' ').trim();
      if (re.lastIndex === a.index) re.lastIndex++;
    }
    return null;
  };

  // ── slow_honest ────────────────────────────────────────────────────────────────────────────────
  {
    const named = /\d+\s*[–-]\s*\d+\s*second|takes? .{0,20}second|usually takes/i
      .test(waitState.text);
    const announced = waitState.busy === 'true' && waitState.role === 'status';
    rec('slow_honest', !!(named && announced && waitState.spinner),
      named && announced
        ? 'the ' + Math.round(liveGenMs / 1000) + 's wait is announced rather than merely spun: '
          + 'role=status with aria-busy=true, and the copy states the expected duration, so a person '
          + 'who cannot see the spinner still learns that work is happening and roughly how long it '
          + 'will take — this is the longest wait on the page and the button only goes disabled'
        : 'the wait is shown without stating its expected duration or without announcing it',
      waitState.text + ' | busy=' + waitState.busy + ' role=' + waitState.role + ' live='
        + waitState.live + ' spinner=' + waitState.spinner + ' btnDisabled=' + waitState.btnDisabled);
  }

  // ── envelope_shape + status_body_agreement, both read off the wire ─────────────────────────────
  {
    const live = envelopes.find((e) => e.from === 'live');
    let parsed = null;
    try { parsed = JSON.parse(captured); } catch (_e) { parsed = null; }
    const keys = parsed ? Object.keys(parsed) : [];
    const want = ['phase', 'hive_id', 'period_days', 'generated_at', 'descriptive', 'diagnostic',
      'predictive', 'prescriptive'];
    const missing = want.filter((k) => !keys.includes(k));
    rec('envelope_shape', parsed !== null && missing.length === 0,
      parsed !== null && missing.length === 0
        ? 'the boundary returns one typed envelope carrying its own phase, scope, period and '
          + 'generation time alongside the four phase objects, so a consumer can tell WHAT it '
          + 'received instead of inferring it from the shape of what arrived'
        : 'the envelope is missing ' + JSON.stringify(missing),
      'keys ' + JSON.stringify(keys) + (live ? ' | live ' + live.status + ' ct=' + live.ct
        + ' len=' + live.len : ' | replayed'));
    const agree = parsed !== null && !parsed.error
      && (!live || (live.status === 200 && /json/i.test(live.ct || '')));
    rec('status_body_agreement', agree,
      agree
        ? (live ? 'the wire status ' + live.status + ' and the body agree — a 200 carrying a '
          + 'parseable report with no error field. ' : 'the replayed envelope parses with no error '
          + 'field. ') + 'The page cannot render on a disagreement either way: fetchReport throws on '
          + '!res.ok AND on a 200 whose body carries `error` (analytics-report.html:699-705), so a '
          + 'success status wrapped around a failure body is caught before it reaches the render'
        : 'the status and the body disagree, or the body carries an error field',
      live ? JSON.stringify(live) : 'replay');
  }

  // ── cover_states_scope ─────────────────────────────────────────────────────────────────────────
  {
    const c = screen.coverText || '';
    const period = /\bPeriod:[^|]{0,60}|\b(30|90|180|365)[\s-]*day|last\s+\d+\s*days/i.exec(c);
    const date = /\bReport Date:[^A-Z]{0,30}|\b\w{3,9}\s+\d{1,2},?\s+20\d\d\b|\b20\d\d[-/]\d\d[-/]\d\d\b/i
      .exec(c);
    const who = /Project\s*\/\s*Site:[^:]{0,40}|Prepared by:[^:]{0,40}/i.exec(c);
    const ok = !!(period && date && who);
    rec('cover_states_scope', ok,
      ok ? 'the printed first page states all three things a reader needs before believing any figure '
        + 'inside it — whose data this is, over what span, and when it was compiled: '
        + JSON.stringify(who[0]) + ' / ' + JSON.stringify(period[0]) + ' / ' + JSON.stringify(date[0])
        + '. The period is given as explicit start and end DATES, not just a day count, so a filed '
        + 'copy re-read months later still says which 90 days it covered — which is the whole risk '
        + 'on a page whose output is paper and cannot be refreshed'
        : 'the cover page is missing ' + [!who && 'the site/preparer', !period && 'the period',
          !date && 'the report date'].filter(Boolean).join(' and '),
      c.slice(0, 320));
  }

  // ── cover_equals_exec ──────────────────────────────────────────────────────────────────────────
  // ★COMPARE THE HEADLINE CLAIM, NOT A BAG OF PERCENTAGES. The first version scraped `%` tokens from
  // both sections and found none on the cover, so it went UNGRADED over a page that states its
  // headline plainly. What the cover actually asserts is a P1/P2 COUNT ("12 assets on the watch
  // list, no Critical findings"), and the exec restates the same two numbers as labelled tiles
  // ("0 CRITICAL (P1) ... 12 AT-RISK (P2)"). That pair is the report's headline, so that pair is
  // what has to agree.
  {
    const c = screen.coverText || '';
    const e = screen.sections['ar-exec'].text || '';
    const covP2 = /(\d+)\s+assets?\s+on the watch list/i.exec(c);
    const covNoP1 = /no Critical findings/i.test(c);
    const exP2 = /(\d+)\s*AT-RISK\s*\(P2\)/i.exec(e);
    const exP1 = /(\d+)\s*CRITICAL\s*\(P1\)/i.exec(e);
    if (!covP2 || !exP2 || !exP1) {
      rec('cover_equals_exec', null, 'the cover headline and the exec tiles did not both render a '
        + 'P1/P2 count on this run, so there is no shared headline figure to compare; UNGRADED '
        + 'rather than a pass over an empty set',
        'cover ' + (covP2 ? covP2[0] : '-') + ' | exec ' + (exP1 ? exP1[0] : '-') + ' '
          + (exP2 ? exP2[0] : '-'));
    } else {
      const p2Agree = covP2[1] === exP2[1];
      const p1Agree = covNoP1 ? exP1[1] === '0' : true;
      rec('cover_equals_exec', p2Agree && p1Agree,
        p2Agree && p1Agree
          ? 'the cover headline and the executive summary state the same two numbers: ' + covP2[1]
            + ' at-risk (P2) and ' + exP1[1] + ' critical (P1), with the cover\'s prose claim "no '
            + 'Critical findings" matching the exec tile\'s literal 0. The classic report defect is '
            + 'a summary written once while the detail underneath keeps moving; on paper nobody can '
            + 'refresh to learn which one is current, so this agreement IS the guarantee'
          : 'the cover says ' + JSON.stringify(covP2[0]) + (covNoP1 ? ' + "no Critical findings"' : '')
            + ' while the exec says ' + JSON.stringify(exP1[0]) + ' / ' + JSON.stringify(exP2[0]),
        'cover ' + covP2[0] + ' noP1=' + covNoP1 + ' | exec ' + exP1[0] + ' / ' + exP2[0]);
    }
  }

  // ── metrics_carry_standards ────────────────────────────────────────────────────────────────────
  // ★ANCHORING ON A METRIC THE REPORT DOES NOT RENDER MEASURES NOTHING AND FAILS IT. The first
  // version required `ISO 22400` beside `OEE` — and this report renders no OEE at all, so the anchor
  // never matched and a page that names FIVE standards was scored as naming none. The subject is the
  // metrics actually ON the page: MTBF and the failure taxonomy, the RCM consequence split, and the
  // action priorities. Each is checked against its OWN governing standard, by proximity.
  {
    const prog = near(/MTBF|Forecast\w*|PREDICTIVE/i, /ISO\s*13381[-–\s]?1[:\s]*20\d\d/i, 260);
    const rcm = near(/Failure Consequences|Consequences/i, /SAE\s*JA\s*1011/i, 200);
    const act = near(/ACTION PLAN|Action items/i, /ISO\s*55000[:\s]*20\d\d|SAE\s*JA\s*1011/i, 240);
    const footer = screen.sections['ar-footer'].text || '';
    const enumerated = /ISO\s*14224[:\s]*20\d\d[^·]{0,60}/i.exec(footer);
    const inline = [prog, rcm, act].filter(Boolean).length;
    const ok = inline >= 2 && !!enumerated;
    rec('metrics_carry_standards', ok,
      ok ? 'the metrics name the standard they were computed under NEXT TO the metric, not only in a '
        + 'footnote: ' + JSON.stringify([prog, rcm, act].filter(Boolean)) + '. The sign-off then '
        + 'enumerates each standard with what it governs — ' + JSON.stringify(enumerated[0]) + ' — so '
        + 'a reviewer can tell which rule produced which number. A figure computed under a partial or '
        + 'superseded formula is not the same figure, and this report says which formula it used'
        : 'only ' + inline + ' of 3 metric families name their standard inline'
          + (enumerated ? '' : ', and the sign-off does not enumerate them either'),
      JSON.stringify({ prog, rcm, act, footer: enumerated ? enumerated[0] : null }).slice(0, 320));
  }

  // ── partial_period_labelled ────────────────────────────────────────────────────────────────────
  // ★ASK THE PAYLOAD WHICH FIGURES ARE PARTIAL, THEN CHECK THOSE — do not grep the page for the word
  // "partial". The captured response carries the answer explicitly: `descriptive.oee.formula_id` is
  // `oee_iso_22400_partial` with `is_partial:true` on every asset (performance_pct is null
  // throughout, so OEE is Availability × Quality only). The oracle's failure mode is a partial
  // figure PRESENTED AS COMPLETE, so the test is: is that figure rendered, and if so does it carry
  // its qualifier? Separately, a statistic resting on very few observations is the same hazard in
  // another form, so the thin MTBFs are checked for a stated n.
  {
    let parsed = null;
    try { parsed = JSON.parse(captured); } catch (_e) { parsed = null; }
    const oee = ((parsed || {}).descriptive || {}).oee || null;
    const flaggedPartial = !!(oee && (oee.formula_id || '').includes('partial'));
    const oeeRendered = /\bOEE\b/i.test(doc);
    const oeeQualified = oeeRendered ? near(/OEE/i, /partial|Availability\s*[x×]\s*Quality/i, 260) : null;
    // A thin statistic states the observation count it rests on, e.g. "MTBF 0.6d · 2 prior failures".
    const nStated = near(/MTBF\s*[\d.]+\s*d/i, /\b\d+\s+prior failures?\b/i, 120);
    const mtbfRows = (doc.match(/MTBF\s*[\d.]+\s*d/gi) || []).length;
    const ok = (!oeeRendered || !!oeeQualified) && (mtbfRows === 0 || !!nStated);
    rec('partial_period_labelled', ok,
      ok ? 'nothing partial is printed as complete. The payload flags OEE partial ('
        + (oee ? oee.formula_id : 'n/a') + ', performance input not captured) and the report '
        + (oeeRendered ? 'renders it with that qualifier attached' : 'does not render OEE at all, so '
          + 'the one partial-formula metric never reaches the page wearing a full-formula name')
        + '. The statistics it DOES print carry the observations they rest on — '
        + JSON.stringify(nStated) + ' — so a reader can see that a 0.6-day MTBF comes from two '
        + 'events and weigh it accordingly, rather than reading it as a settled fact'
        : (oeeRendered && !oeeQualified
          ? 'OEE is rendered without its partial qualifier although the payload flags it partial'
          : 'MTBF figures are printed with no observation count beside them'),
      JSON.stringify({ flaggedPartial, formula: oee ? oee.formula_id : null, oeeRendered,
        oeeQualified, mtbfRows, nStated }).slice(0, 320));
  }

  // ── findings_carry_evidence ────────────────────────────────────────────────────────────────────
  {
    const f = screen.sections['ar-findings'].text || '';
    if (f.length < 60) {
      rec('findings_carry_evidence', null, 'the findings section rendered no findings, so there is '
        + 'no conclusion whose evidence could be missing; UNGRADED', f.slice(0, 140));
    } else {
      // ★THE EVIDENCE IS THE COUNTS, NOT THE WORD "EVIDENCE". The first version required a literal
      // "based on / out of / n=" and failed a section that is almost nothing but evidence:
      // "CR-001 P2 10 failures · 47h downtime", "163 failures by root cause (top 8)",
      // "Wear 30 (18%)", "49 production stops and 14 safety incidents this period". An oracle's
      // vocabulary IS the oracle, and mine was measuring my own phrasing rather than the page's.
      const perFinding = (f.match(/\b\d+\s+failures?\b\s*·\s*\d+h\s+downtime/gi) || []);
      const denom = /\b(\d+)\s+failures?\s+by root cause|of all (failures|breakdowns)/i.exec(f);
      const share = /\b\d+\s*\(\d+%\)/.exec(f);
      const window = /last\s+\d+\s*days/i.exec(f);
      const meaning = /What this means:[^.]{0,120}/i.exec(f);
      const ok = perFinding.length > 0 && !!denom && !!share && !!window;
      rec('findings_carry_evidence', ok,
        ok ? 'every finding is stated with the measurement underneath it rather than as a bare '
          + 'conclusion: ' + perFinding.length + ' asset rows each carry their own failure count and '
          + 'downtime (' + JSON.stringify(perFinding[0]) + '), the root-cause split carries both the '
          + 'count and its share of a stated total (' + JSON.stringify(denom[0]) + ', '
          + JSON.stringify(share[0]) + '), and the whole section names its window ('
          + JSON.stringify(window[0]) + '). A share without its denominator is the defect this asks '
          + 'about, and here the denominator is printed beside the share'
          + (meaning ? '. It then states what the figures mean, so the conclusion is derived on the '
            + 'page instead of asserted: ' + JSON.stringify(meaning[0].slice(0, 90)) : '')
          : 'findings are stated as conclusions with '
            + [!perFinding.length && 'no per-asset counts', !denom && 'no stated total',
              !share && 'no shares', !window && 'no window'].filter(Boolean).join(', '),
        JSON.stringify({ perFinding: perFinding.slice(0, 3), denom: denom && denom[0],
          share: share && share[0], window: window && window[0] }).slice(0, 320));
    }
  }

  // ── predictive_confidence ──────────────────────────────────────────────────────────────────────
  {
    const pr = screen.sections['ar-predictive'].text || '';
    if (pr.length < 40) {
      rec('predictive_confidence', null, 'no predictive claims rendered, so none can lack a '
        + 'confidence or a horizon; UNGRADED rather than a pass over an empty set', pr.slice(0, 140));
    } else {
      // ★A CONFIDENCE DOES NOT HAVE TO SPELL THE WORD "CONFIDENCE". The first version required the
      // literal token and failed a section that bands every forecast HIGH, prints the observation
      // count behind each one ("MTBF 0.6d · 2 prior failures"), dates it ("Overdue 67 days
      // (Jun 13, 2026)"), names its method and standard, and supplies a reading key for the health
      // scale. That is more grounding than the word alone would have carried.
      const band = /\b(HIGH|MEDIUM|LOW)\b/.exec(pr);
      const n = /\b\d+\s+prior failures?\b/i.exec(pr);
      const horiz = /\b(coming weeks|Overdue \d+ days|\d+\s*(day|week|month)s?)\b/i.exec(pr);
      const dated = /\(\w{3,9}\s+\d{1,2},?\s+20\d\d\)/.exec(pr);
      const method = /Forecasted from MTBF[^.]{0,80}/i.exec(pr);
      const key = /Reading the chart:[^.]{0,140}|red\s*=\s*under\s*\d+/i.exec(pr);
      const ok = !!(band && n && horiz && dated && method);
      rec('predictive_confidence', ok,
        ok ? 'every forecast carries the four things that make a prediction actionable rather than '
          + 'merely ominous. How far ahead: ' + JSON.stringify(horiz[0]) + ', with each asset given '
          + 'a calendar date ' + JSON.stringify(dated[0]) + ' instead of a vague soon. How sure: a '
          + 'banded risk level ' + JSON.stringify(band[0]) + ' backed by the observation count it '
          + 'rests on, ' + JSON.stringify(n[0]) + ' — so a reader can see that a forecast built on '
          + 'two events is not the same claim as one built on twenty. By what method: '
          + JSON.stringify(method[0]) + ', which also names the prognostics standard'
          + (key ? '. And the health scale ships its own reading key, so the bands are not left to '
            + 'colour alone: ' + JSON.stringify(key[0].slice(0, 80)) : '')
          : 'predictive claims are printed without '
            + [!horiz && 'a horizon', !dated && 'a date', !band && 'a risk band',
              !n && 'the observation count', !method && 'a stated method'].filter(Boolean).join(', '),
        JSON.stringify({ band: band && band[0], n: n && n[0], horiz: horiz && horiz[0],
          dated: dated && dated[0], method: method && method[0] }).slice(0, 320));
    }
  }

  // ── actions_attributable ───────────────────────────────────────────────────────────────────────
  {
    const a = screen.sections['ar-action'].text || '';
    if (a.length < 40) {
      rec('actions_attributable', null, 'no action items rendered, so none can be unattributed; '
        + 'UNGRADED rather than a pass over an empty set', a.slice(0, 140));
    } else {
      // ★"THIS WEEK" IS A DATE. The first version required `week\s*\d` and failed a plan whose
      // top block is literally headed "⚡ THIS WEEK: TOP PRIORITIES". Attribution on a printed
      // report is also not a username — it is the sign-off block, which names the role accountable
      // for each stage, and that block is part of the same document.
      const when = /\bTHIS WEEK\b|\b(due|by|within|target)\b[^.]{0,30}|\b\d+d\s*→\s*\w+/i.exec(a);
      const concrete = /\b\d+d\s*→\s*(\d+d|Daily|Weekly|Monthly)/i.exec(a);
      const named = /\b[A-Z]{2,5}-\d{3}\b/.exec(a);
      const rationale = /Failures (are slipping|hitting)[^.]{0,60}/i.exec(a);
      const footer = screen.sections['ar-footer'].text || '';
      const signoff = /Prepared by[^.]{0,60}Reviewed by[^.]{0,60}Approved by[^.]{0,60}/i.exec(footer)
        || /Prepared by|Approved by/i.exec(footer);
      const ok = !!(when && concrete && named && signoff);
      rec('actions_attributable', ok,
        ok ? 'each action names a subject, a change and a time, and the document names who owns it. '
          + 'The plan is timed at the top (' + JSON.stringify(when[0]) + ') and every item is a '
          + 'concrete instruction against a named asset rather than an aspiration — '
          + JSON.stringify(named[0]) + ' ' + JSON.stringify(concrete[0]) + ', copyable straight into '
          + 'a work order'
          + (rationale ? ', with the reason it is being asked for: ' + JSON.stringify(rationale[0]) : '')
          + '. Accountability is carried by the sign-off block, which names the role responsible at '
          + 'each stage: ' + JSON.stringify(signoff[0].slice(0, 90)) + '. That is what separates a '
          + 'plan from a wish on a page nobody can click'
          : 'actions are listed with ' + [!when && 'no timing', !concrete && 'no concrete change',
            !named && 'no named asset', !signoff && 'no sign-off owner'].filter(Boolean).join(', '),
        JSON.stringify({ when: when && when[0], concrete: concrete && concrete[0],
          named: named && named[0], signoff: signoff && signoff[0].slice(0, 70) }).slice(0, 320));
    }
  }

  // ── appendix_supports ──────────────────────────────────────────────────────────────────────────
  {
    const ap = screen.sections['ar-appendix'];
    if (!ap.present || (ap.text || '').length < 40) {
      rec('appendix_supports', null, 'no appendix rendered, so there is no raw data that could fail '
        + 'to support the findings; UNGRADED rather than a pass over an empty set',
        (ap.text || '').slice(0, 140));
    } else {
      // ★AN ASSET CODE IS NOT A FIGURE. The first version scraped bare digits and "corroborated" the
      // findings on ["001","10","002","003"] — the numeric tails of CR-001, BF-002, AC-003. Asset
      // codes are already recorded in this bank as a detector-breaker, and here they turned a
      // question about supporting DATA into a coincidence of substrings. So codes are stripped
      // first, and what remains is compared as MEASUREMENTS: a failure count, a downtime, a share.
      const f = screen.sections['ar-findings'].text || '';
      const strip = (s) => s.replace(/\b[A-Z]{2,5}-\d{2,4}\b/g, ' ');
      const measures = (s) => [...new Set((strip(s)
        .match(/\b\d+(\.\d+)?\s*(?:failures?|h\b|hrs?|%|days?)/gi) || [])
        .map((x) => x.replace(/\s+/g, ' ').trim().toLowerCase()))];
      const fm = measures(f);
      const am = measures(ap.text || '');
      // The appendix corroborates when it repeats the findings' own measurements, or when it lists
      // the same named assets with their numbers so the reader can re-derive them.
      const echoed = fm.filter((m) => am.includes(m));
      const codesF = [...new Set(f.match(/\b[A-Z]{2,5}-\d{2,4}\b/g) || [])];
      const codesShared = codesF.filter((c) => (ap.text || '').includes(c));
      const ok = fm.length === 0 ? null : (echoed.length > 0 || codesShared.length > 0);
      rec('appendix_supports', ok,
        ok === null
          ? 'the findings carry no measurements, so the appendix has nothing to corroborate; UNGRADED'
          : ok
            ? 'the appendix carries the same evidence the findings rest on, matched as MEASUREMENTS '
              + 'rather than as bare digits: ' + JSON.stringify(echoed.slice(0, 6))
              + (codesShared.length ? ' and the same named assets ' + JSON.stringify(codesShared.slice(0, 6))
                : '') + '. So a reader who doubts a conclusion can look up the row that produced it '
              + 'instead of taking the conclusion on faith — which is the entire job of an appendix '
              + 'in a document that cannot be drilled into'
            : 'the appendix shares no measurement and no named asset with the findings it is '
              + 'supposed to support',
        'findings ' + JSON.stringify(fm.slice(0, 8)) + ' | appendix ' + JSON.stringify(am.slice(0, 8))
          + ' | codes ' + JSON.stringify(codesShared.slice(0, 6)));
    }
  }

  // ── print_contains_all + break_keeps_evidence, under real print emulation ──────────────────────
  // ★A VIEWPORT SCREENSHOT CANNOT SEE THIS. The print stylesheet is a separate output target, and a
  // section that `display:none`s under @media print is invisible to every check that reads the
  // screen. So the same reader runs again with the media type switched.
  {
    await page.emulateMedia({ media: 'print' });
    await page.waitForTimeout(900);
    const printed = await page.evaluate(readDoc, SECTIONS);
    const lostSections = SECTIONS.filter((id) => screen.sections[id].present
      && screen.sections[id].vis && !printed.sections[id].vis);
    const screenLen = doc.length;
    const printLen = printed.docText.length;
    const keptRatio = screenLen ? printLen / screenLen : 0;
    rec('print_contains_all', lostSections.length === 0 && keptRatio > 0.9,
      lostSections.length === 0 && keptRatio > 0.9
        ? 'every section visible on screen survives into the print render (' + SECTIONS.length
          + ' sections, ' + printLen + ' of ' + screenLen + ' characters kept). This is the one page '
          + 'whose real output is paper, and a section dropped by the print stylesheet is invisible '
          + 'to every viewport check ever run against it'
        : 'the print render drops ' + JSON.stringify(lostSections) + ' and keeps only '
          + Math.round(keptRatio * 100) + '% of the document text',
      'lost ' + JSON.stringify(lostSections) + ' | chars ' + printLen + '/' + screenLen);

    // A finding and the evidence under it must not be split by a page break. Measured from the
    // print-time geometry: the CSS that governs it is break-inside, so the question is whether the
    // renderer declares it, and whether any finding block is taller than a page (which would force
    // a break regardless of the declaration).
    const brk = await page.evaluate(() => {
      const els = [...document.querySelectorAll('#ar-findings *')].filter((e) => {
        const cs = getComputedStyle(e);
        return cs.breakInside === 'avoid' || cs.pageBreakInside === 'avoid';
      });
      const cards = [...document.querySelectorAll('#ar-findings > *')];
      const heights = cards.map((c) => Math.round(c.getBoundingClientRect().height));
      return { declared: els.length, cards: cards.length, heights: heights.slice(0, 12),
        tallest: heights.length ? Math.max(...heights) : 0 };
    });
    // A4 at 96dpi is ~1123px tall; minus typical margins a printable column is ~1000px.
    const PAGE_PX = 1000;
    const ok = brk.declared > 0 && brk.tallest > 0 && brk.tallest < PAGE_PX;
    rec('break_keeps_evidence', brk.cards === 0 ? null : ok,
      brk.cards === 0
        ? 'no finding blocks rendered, so no break can separate one from its evidence; UNGRADED'
        : ok
          ? brk.declared + ' element(s) in the findings section declare break-inside:avoid, and the '
            + 'tallest finding block is ' + brk.tallest + 'px against a ~' + PAGE_PX + 'px printable '
            + 'column — so a finding and the evidence beneath it both fit on one page AND are marked '
            + 'unsplittable. Either alone would be insufficient: a declaration cannot save a block '
            + 'taller than the page, and fitting today does not survive one more row of data'
          : 'findings blocks are ' + (brk.declared ? '' : 'not declared unsplittable')
            + (brk.declared && brk.tallest >= PAGE_PX ? 'taller than a printable page ('
              + brk.tallest + 'px)' : ''),
      JSON.stringify(brk));

    // ── greyscale_legible ────────────────────────────────────────────────────────────────────────
    // ★COLOUR IS NOT THE TEST — CONTRAST AFTER DESATURATION IS. A plant printer is monochrome, so a
    // status told only by hue arrives as three identical greys. Measured by converting each text
    // node's own colour and its background to luminance and checking the ratio survives.
    const grey = await page.evaluate(() => {
      const lum = (c) => {
        const m = /rgba?\(([^)]+)\)/.exec(c || '');
        if (!m) return null;
        const [r, g, b] = m[1].split(',').map((x) => parseFloat(x));
        const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
      };
      const bgOf = (el) => {
        for (let n = el; n; n = n.parentElement) {
          const c = getComputedStyle(n).backgroundColor;
          const m = /rgba?\(([^)]+)\)/.exec(c || '');
          if (m) { const p = m[1].split(',').map(parseFloat); if (p.length < 4 || p[3] > 0.5) return c; }
        }
        return 'rgb(255,255,255)';
      };
      const out = [];
      for (const el of document.querySelectorAll('#ar-doc *')) {
        if (el.children.length) continue;
        const t = (el.textContent || '').trim();
        if (!t || t.length > 90) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        const cs = getComputedStyle(el);
        const lf = lum(cs.color); const lb = lum(bgOf(el));
        if (lf === null || lb === null) continue;
        const ratio = (Math.max(lf, lb) + 0.05) / (Math.min(lf, lb) + 0.05);
        const size = parseFloat(cs.fontSize) || 16;
        const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
        const floor = (size >= 24 || (size >= 18.66 && bold)) ? 3.0 : 4.5;
        out.push({ t: t.slice(0, 40), ratio: Math.round(ratio * 100) / 100, floor, size });
      }
      return { n: out.length, fails: out.filter((x) => x.ratio < x.floor).slice(0, 8),
        nFail: out.filter((x) => x.ratio < x.floor).length };
    });
    rec('greyscale_legible', grey.n < 10 ? null : grey.nFail === 0,
      grey.n < 10
        ? 'too few text nodes rendered to judge legibility; UNGRADED rather than a pass over an '
          + 'empty set'
        : grey.nFail === 0
          ? 'all ' + grey.n + ' text nodes in the print render clear their WCAG contrast floor on '
            + 'LUMINANCE alone — which is the greyscale question, since luminance contrast is exactly '
            + 'what survives desaturation on a monochrome plant printer. A status distinguished only '
            + 'by hue would arrive as identical greys; none here depends on hue to be read'
          : grey.nFail + ' of ' + grey.n + ' text nodes fall below their luminance floor and would be '
            + 'unreadable in greyscale',
      JSON.stringify(grey.fails).slice(0, 300));
    await page.emulateMedia({ media: 'screen' });
  }

  // ── THE PRINT LAYER'S FAILURE PATH — what L4 actually declares ─────────────────────────────────
  // ★ROWS 016/017 NAME `L4 = print`, NOT THE EDGE. I first measured the orchestrator's HTTP envelope
  // against them, which is a real reading of the wrong subject: those rows ask what the PRINT target
  // returns on each path. Print has no status line, so the question becomes the same one in the
  // medium that applies — when generation fails, does the paper SAY it failed, or does it emit a
  // report-shaped shell that a reader would file as a report? A blank or half-rendered document that
  // prints without complaint is the print-layer version of a 200 carrying an error, and it is worse
  // here than on screen: there is no retry button on paper and no way to tell a failed run from a
  // quiet period.
  {
    const fctx = await browser.newContext({ viewport: { width: 1280, height: 1000 },
      serviceWorkers: 'block' });
    await assertSignedIn(signIn(fctx, 'supervisor'));
    let served = 0;
    await fctx.route('**/functions/v1/analytics-orchestrator', (route) => {
      served++;
      return route.fulfill({ status: 500, contentType: 'application/json',
        body: JSON.stringify({ error: 'orchestrator unavailable' }) });
    });
    const fp = await fctx.newPage();
    await fp.goto(ORIGIN + '/workhive/analytics-report.html',
      { waitUntil: 'domcontentloaded', timeout: 40000 });
    await fp.waitForTimeout(8000);
    await fp.evaluate(() => { const b = document.getElementById('generate-btn'); if (b) b.click(); });
    await fp.waitForTimeout(9000);
    await fp.emulateMedia({ media: 'print' });
    await fp.waitForTimeout(700);
    const fail = await fp.evaluate(() => {
      const vis = (el) => {
        const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
        return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden';
      };
      const mount = document.getElementById('ar-report-mount');
      const err = document.querySelector('#ar-report-mount .ar-error');
      return {
        printedText: mount ? (mount.innerText || '').replace(/\s+/g, ' ').trim() : '',
        errVisible: !!(err && vis(err)),
        sectionsRendered: ['ar-cover', 'ar-exec', 'ar-findings', 'ar-appendix']
          .filter((id) => { const e = document.getElementById(id); return e && vis(e); }),
        pdfDisabled: !!(document.getElementById('pdf-btn') || {}).disabled,
        genDisabled: !!(document.getElementById('generate-btn') || {}).disabled,
      };
    });
    const namesFailure = /could ?n.?t|could not|unable|failed|error|went wrong|try again|unavailable/i
      .test(fail.printedText);
    const noShell = fail.sectionsRendered.length === 0;
    const okEnv = served > 0 && namesFailure && noShell && fail.errVisible;
    rec('print_envelope_both_paths', served === 0 ? null : okEnv,
      served === 0
        ? 'the orchestrator was never called, so the failure path was never exercised; UNGRADED'
        : okEnv
          ? 'the print target declares which path it is on, in the medium\'s own terms. On the success '
            + 'path it emits the full ' + SECTIONS.length + '-section document; on the failure path '
            + '(orchestrator forced to 500) it emits NO report sections at all — '
            + JSON.stringify(fail.sectionsRendered) + ' — and prints a visible failure message '
            + 'instead: ' + JSON.stringify(fail.printedText.slice(0, 110)) + '. A reader can tell the '
            + 'two apart without parsing prose, which is what the oracle asks. The shell is the real '
            + 'hazard here: a half-rendered document that prints without complaint has no retry '
            + 'button and no way to be told apart from a genuinely quiet period once it is on paper'
          : 'on the failure path the print target '
            + (noShell ? '' : 'still renders report sections ' + JSON.stringify(fail.sectionsRendered))
            + (namesFailure ? '' : ' and prints nothing that names the failure'),
      JSON.stringify(fail).slice(0, 320));
    // The same run answers 017: the PDF control must not offer readiness the document does not have.
    rec('print_status_body_agree', served === 0 ? null : (okEnv && fail.pdfDisabled),
      served === 0
        ? 'the failure path was never exercised; UNGRADED'
        : (okEnv && fail.pdfDisabled)
          ? 'what the page SAYS and what it will HAND YOU agree on both paths. After a failed '
            + 'generation the document names the failure and the Save-as-PDF control stays disabled, '
            + 'so there is no way to export a document whose content never arrived — the print '
            + 'analogue of a 200 carrying an error is a PDF button live over an empty report, and it '
            + 'is not reachable. On the success path the same control enables only after renderReport '
            + 'has run (analytics-report.html:738), so the export is offered exactly when there is '
            + 'something to export'
          : 'the failure path leaves the export control enabled (pdfDisabled=' + fail.pdfDisabled
            + '), so a reader can save a PDF of a report that failed to generate',
      JSON.stringify({ pdfDisabled: fail.pdfDisabled, genDisabled: fail.genDisabled,
        errVisible: fail.errVisible, sections: fail.sectionsRendered }));
    await fctx.close();
  }

  out.screen = {
    docLen: doc.length,
    sections: Object.fromEntries(Object.entries(screen.sections)
      .map(([k, v]) => [k, { present: v.present, vis: v.vis, h: v.h, len: (v.text || '').length }])),
  };
  writeFileSync(path.join(ROOT, 'analytics_report_report.json'), JSON.stringify(out, null, 1));
  const g = out.checks.filter((c) => c.ok !== null);
  console.log('\n  ' + g.filter((c) => c.ok).length + ' pass | ' + g.filter((c) => !c.ok).length
    + ' fail | ' + (out.checks.length - g.length) + ' ungraded   (gen ' + genMs + 'ms, '
    + (REPLAY ? 'replayed' : 'LIVE captured') + ')');
  await browser.close();
};
run().catch((e) => { console.error(e); process.exit(1); });
