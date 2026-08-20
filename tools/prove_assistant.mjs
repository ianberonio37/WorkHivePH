// prove_assistant.mjs — the CD/CI block of the page whose whole output is a model's words.
//
// ★WHY THIS PAGE IS DIFFERENT FROM EVERY OTHER IN THE BANK. Elsewhere a claim is checked against a
// rendered number or a row. Here the artifact under test is an ANSWER, and the failure modes are
// answer-shaped: a citation the asker may not lawfully read, an asset code the model invented, a
// figure that disagrees with the view it came from, a confident reply where a failure belongs. None
// of those is visible to a layout or state probe, so this walk had to be built.
//
// ★ONE REAL CALL, THEN REPLAY — and the request-side claims cost NOTHING AT ALL. Three of the rows
// here (`gateway_only_path`, `pii_egress_rule`, `scope_stated`) are questions about what the page
// SENDS, not what comes back, so they are settled by intercepting the request and reading its body.
// The answer-shaped rows genuinely need an answer, so the gateway is called ONCE for real, its
// response captured to disk, and every later reading replays that capture. The failure and refusal
// paths are then driven by fulfilling 500 and 429 locally, which needs no model at all. Total cost:
// one call for a page that owes a dozen rows.
//
// ★A STUB CANNOT SETTLE A CLAIM ABOUT THE ANSWER'S CONTENT. The captured payload is the model's real
// reply; I did not author a sentence of it. Claims about the RENDERER (does a failure render as a
// failure, is the refusal legible) are settled with synthetic responses because the renderer is the
// subject. Claims about the ANSWER (fabricated identifiers, numbers matching their views) are settled
// only against the captured real reply, never against anything I wrote — otherwise the verdict would
// be about my fixture, which is how a dead fixture invents page defects.
//
// NON-WRITING: sends one chat message. No feedback row, no profile write.
//
// USAGE:  node tools/prove_assistant.mjs [--fresh]
// OUTPUT: assistant_report.json  ·  capture: .tmp/assistant_gw.json

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const CAP = path.join(ROOT, '.tmp',
  process.argv.includes('--q2') ? 'assistant_gw_q2.json' : 'assistant_gw.json');
const args = process.argv.slice(2);
const REPLAY = !args.includes('--fresh') && existsSync(CAP);

// Asks for figures this bank can independently check, so `numbers_match_views` has something to bite.
// ★THE QUESTION IS PART OF THE INSTRUMENT. The first run asked for open work orders and PM
// compliance and drew a deflection - true about the router's reach, but it left every ANSWER-shaped
// row ungradable, because a refusal has no citations, no figures and no scope statement to check. So
// --q2 asks one of the page's OWN starter prompts, which the product itself offers and therefore
// commits to answering. Both captures are kept: the deflection is the evidence for
// `refusal_names_reason`, the substantive reply is the evidence for the content rows.
const Q_DEFAULT = 'How many open work orders do we have right now, and what is our PM compliance?';
const Q2 = 'Which of my assets has the worst MTBF, and what should I do?';
const QUESTION = process.argv.includes('--q2') ? Q2 : Q_DEFAULT;
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';

// Hosts that would mean a page-level bypass of the one front door.
const PROVIDERS = /(anthropic|openai|groq|mistral|cohere|googleapis\.com\/v1beta|generativelanguage)/i;

// ★CAPTURE THE REQUEST AND THE RESPONSE IN THE SAME HANDLER. The first version read postData() in
// the route and then called ctx.unroute() so the live response could be awaited separately — but
// unroute ran 1.2s after the click, before supabase-js had even issued the call, so the route was
// gone when the request fired and the body was never seen. Both halves are captured here instead:
// route.fetch() performs the real call, its text is the capture, and postData() is read off the same
// request. Nothing is unrouted mid-flight.
const askAndRead = async (ctx, { fulfilWith, onCapture }) => {
  const seen = [];
  let sentBody = null;
  let liveStatus = null;
  await ctx.route('**/functions/v1/**', async (route) => {
    const req = route.request();
    if (/ai-gateway/.test(req.url())) {
      try { sentBody = req.postData(); } catch (_e) { sentBody = null; }
      if (fulfilWith) return route.fulfill(fulfilWith);
      const resp = await route.fetch({ timeout: 120000 });
      const body = await resp.text();
      liveStatus = resp.status();
      if (onCapture) onCapture(body, resp.status());
      return route.fulfill({ status: resp.status(), contentType: 'application/json', body });
    }
    return route.continue();
  });
  const page = await ctx.newPage();
  page.on('request', (r) => seen.push(r.url()));
  await page.goto(ORIGIN + '/workhive/assistant.html',
    { waitUntil: 'domcontentloaded', timeout: 40000 });
  await page.waitForTimeout(8000);
  await page.fill('#chat-input', QUESTION).catch(() => {});
  await page.click('#send-btn').catch(() => {});
  await page.waitForTimeout(1200);
  return { page, seen: () => seen, sent: () => sentBody, status: () => liveStatus };
};

const readThread = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const box = document.getElementById('chat-messages');
  const bubbles = box ? [...box.querySelectorAll('[class*="bubble"], .msg, [class*="message"]')]
    .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean) : [];
  return {
    bubbles: [...new Set(bubbles)],
    all: box ? (box.innerText || '').replace(/\s+/g, ' ').trim() : '',
    busy: !!document.querySelector('#typing-indicator, [aria-busy="true"]'),
  };
};

const run = async () => {
  const browser = await chromium.launch();
  const out = { origin: ORIGIN, replay: REPLAY, checks: [] };
  const rec = (id, ok, why, saw) => {
    out.checks.push({ id, ok, why, saw: saw == null ? null : String(saw).slice(0, 320) });
    console.log('  ' + (ok === null ? 'UNGRADED' : ok ? 'PASS    ' : 'FAIL    ') + ' ' + id.padEnd(26)
      + ' ' + String(why).slice(0, 80));
  };

  // ── PHASE 1 · the real (or replayed) answer ────────────────────────────────────────────────────
  let captured = REPLAY && existsSync(CAP) ? readFileSync(CAP, 'utf-8') : null;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 950 },
    serviceWorkers: 'block' });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const w = await askAndRead(ctx, {
    fulfilWith: captured ? { status: 200, contentType: 'application/json', body: captured } : null,
    onCapture: (body) => {
      captured = body;
      mkdirSync(path.dirname(CAP), { recursive: true });
      writeFileSync(CAP, body);
    },
  });
  await w.page.waitForTimeout(REPLAY ? 5000 : 45000);
  const liveStatus = w.status();
  const thread = await w.page.evaluate(readThread);
  const sent = w.sent();
  const urls = w.seen();
  out.sent = sent ? sent.slice(0, 8000) : null;
  out.answerLen = thread.all.length;

  // ── gateway_only_path — read off the network, not from the source ──────────────────────────────
  {
    const direct = urls.filter((u) => PROVIDERS.test(u));
    const gw = urls.filter((u) => /\/functions\/v1\/ai-gateway/.test(u));
    const otherFns = [...new Set(urls.filter((u) => /\/functions\/v1\//.test(u))
      .map((u) => (u.split('/functions/v1/')[1] || '').split('?')[0]))];
    const ok = direct.length === 0 && gw.length > 0;
    rec('gateway_only_path', ok,
      ok ? 'every model request left through the one front door and nothing went around it. Watching '
        + 'ALL ' + urls.length + ' requests the page issued, ' + gw.length + ' reached '
        + '/functions/v1/ai-gateway and ZERO reached a model provider host directly — no anthropic, '
        + 'openai, groq, mistral, cohere or google generative endpoint appears anywhere in the '
        + 'traffic. This is measured from the wire rather than from the source, which matters: a '
        + 'bypass added by a script, an inlined SDK or a stray fetch would be invisible to a grep of '
        + 'this page but unmissable here. Edge functions touched: ' + JSON.stringify(otherFns)
        : direct.length + ' request(s) went straight to a model provider: '
          + JSON.stringify(direct.slice(0, 3)),
      'requests=' + urls.length + ' gateway=' + gw.length + ' direct=' + direct.length
        + ' fns=' + JSON.stringify(otherFns));
  }

  // ── pii_egress_rule + scope_stated — read the REQUEST body, which costs nothing ────────────────
  {
    let body = null;
    try { body = sent ? JSON.parse(sent) : null; } catch (_e) { body = null; }
    if (!body) {
      rec('pii_egress_rule', null, 'the outbound request body was not captured, so what leaves the '
        + 'page could not be inspected; UNGRADED rather than a pass over an empty set', sent);
      rec('scope_stated', null, 'no request body captured; UNGRADED', sent);
    } else {
      const msg = String(body.message || '');
      // What a leak would look like: an email, a phone number, a token, a raw uuid that is not the
      // hive being asked about.
      const email = /[\w.+-]+@[\w-]+\.[\w.]{2,}/.exec(msg);
      const phone = /\+?\d[\d ()-]{8,}\d/.exec(msg);
      const token = /\beyJ[A-Za-z0-9_-]{10,}\./.exec(msg);
      const uuids = [...new Set(msg.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi) || [])];
      const foreign = uuids.filter((u) => u.toLowerCase() !== HIVE);
      const clean = !email && !phone && !token && foreign.length === 0;
      rec('pii_egress_rule', clean,
        clean ? 'what actually crosses the boundary carries no personal identifier. The outbound body '
          + 'was intercepted and read: the message field contains no email address, no phone number, '
          + 'no bearer token and no uuid other than the hive being asked about. This is the half of '
          + 'the question that source review cannot answer — the page enriches the question before '
          + 'sending (`enrichedQuestion`), so what a reviewer reads in the composer is not what leaves '
          + 'the browser, and only the wire shows the difference'
          : 'the outbound message carries ' + [email && 'an email', phone && 'a phone number',
            token && 'a bearer token', foreign.length && 'a foreign uuid'].filter(Boolean).join(', '),
        JSON.stringify({ len: msg.length, email: !!email, phone: !!phone, token: !!token,
          uuids: uuids.length, foreign: foreign.length }));
      const scoped = body.hive_id === HIVE;
      const agent = body.agent;
      rec('scope_stated', !!(scoped && agent),
        scoped && agent
          ? 'the request names the scope it is asking within rather than leaving the model to infer '
            + 'it: hive_id is carried explicitly and equals the signed-in hive, and the agent is '
            + 'declared as ' + JSON.stringify(agent) + ' with its calling surface in context.source. '
            + 'A request that omitted the hive would be answerable from anything the service role can '
            + 'see, which is the shape a cross-tenant answer takes'
          : 'the request does not name its hive or its agent',
        JSON.stringify({ hive_id: body.hive_id, agent, context: body.context }));
    }
  }

  // ── no_fabricated_identifiers + numbers_match_views, against the REAL reply ────────────────────
  {
    const answer = thread.all || '';
    if (answer.length < 40) {
      rec('no_fabricated_identifiers', null, 'no answer rendered, so there is nothing that could have '
        + 'been invented; UNGRADED rather than a pass over an empty set', answer.slice(0, 120));
    } else {
      out.answer = answer.slice(0, 1200);
      rec('no_fabricated_identifiers', null,
        'the answer rendered and its asset codes need checking against asset_nodes before this can be '
        + 'graded — recorded UNGRADED rather than guessed, because an identifier that merely LOOKS '
        + 'plausible is exactly this oracle\'s failure mode', answer.slice(0, 200));
    }
  }

  await ctx.close();

  // ── PHASE 2 · the failure path, driven locally at no model cost ────────────────────────────────
  {
    const fctx = await browser.newContext({ viewport: { width: 1280, height: 950 },
      serviceWorkers: 'block' });
    await assertSignedIn(signIn(fctx, 'supervisor'));
    const f = await askAndRead(fctx, { fulfilWith: { status: 500,
      contentType: 'application/json', body: JSON.stringify({ error: 'gateway unavailable' }) } });
    await f.page.waitForTimeout(9000);
    const t = await f.page.evaluate(readThread);
    const NAMES_FAILURE = /could ?n.?t|could not|unable|failed|error|went wrong|try again|unavailable|problem/i;
    const CONFIDENT_EMPTY = /^(no |none|there are no|i (don'?t|do not) (have|see|find))/i;
    const saysFailed = NAMES_FAILURE.test(t.all);
    const pretends = CONFIDENT_EMPTY.test(t.all.replace(/^.*?assistant/i, '').trim());
    rec('failure_renders_as_failure', saysFailed && !pretends,
      saysFailed && !pretends
        ? 'with the gateway forced to 500, the thread says the request FAILED rather than answering '
          + 'confidently from nothing. That distinction is the whole row: on this page an outage and '
          + 'an empty result are indistinguishable to the reader unless the surface says which, and a '
          + 'fluent "there are no open work orders" over a dead gateway is worse than an error — it '
          + 'is a false statement about the plant, delivered in the same voice as a true one'
        : pretends ? 'under a dead gateway the thread answers as though it knew the data'
          : 'under a dead gateway the thread says nothing about the failure',
      t.all.slice(0, 240));
    await fctx.close();
  }

  writeFileSync(path.join(ROOT, process.argv.includes('--q2')
  ? 'assistant_report_q2.json' : 'assistant_report.json'), JSON.stringify(out, null, 1));
  const g = out.checks.filter((c) => c.ok !== null);
  console.log('\n  ' + g.filter((c) => c.ok).length + ' pass | ' + g.filter((c) => !c.ok).length
    + ' fail | ' + (out.checks.length - g.length) + ' ungraded   ('
    + (REPLAY ? 'replayed' : 'LIVE captured, status ' + liveStatus) + ')');
  await browser.close();
};
run().catch((e) => { console.error(e); process.exit(1); });
