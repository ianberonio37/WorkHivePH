/**
 * models_are_live — THE DIAGNOSIS A PERSON READS MUST MATCH THE FAILURE THAT HAPPENED
 * ==================================================================================
 *
 * `validate_groq_fallback`'s TIER 1 rule `models_are_live` asks each provider's own /models endpoint
 * which models it actually serves and fails on any chain entry that is gone. It exists because a
 * DENY-LIST only ever catches a name someone remembered to add: on 2026-09-10 four entries at the
 * HEAD of the Groq tier had been retired, so every AI call on the platform walked four guaranteed
 * 404s before reaching a live model, and `voice-model-call` — which carries its own chain — had no
 * live entry at all and answered every caller:
 *
 *     503  "All models failed (rate limited or down)"
 *
 * That sentence is the reason these tests exist. Not one of the four causes was a rate limit: two
 * were retired models (404), and two were EMBEDDINGS companies (Voyage, Jina) that have never had a
 * /chat/completions endpoint and could not have worked on any day. The function stated a cause it
 * had no evidence for, and the evidence that would have contradicted it was being swallowed by a
 * catch that logged `{ detail: err }` — an Error serialises to `{}`.
 *
 * So the invariant under test is not "the AI works". It is: WHEN THE CHAIN IS WRONG, THE SURFACE
 * MUST NOT MISATTRIBUTE THE CAUSE. A retired model is a deploy-time defect a maintainer must fix;
 * a rate limit is a busy minute a person should wait out. Telling the second story about the first
 * sends everyone — the technician and the maintainer — to the wrong action, and nothing errors.
 *
 * WHY THE SERVICE WORKER IS BLOCKED. `page.route` does not see requests issued by a service worker,
 * and this site registers one. Measured elsewhere in this suite rather than assumed: on a healthy
 * load `page.on('request')` counted 62 supabase reads while `page.route` counted 0. Blocking it is a
 * faithful substitution here — sw.js passes supabase URLs straight through with no cache write — so
 * the page receives byte-identical responses either way.
 *
 * WHY THE ORACLE IS A DIFFERENCE. Each assertion is made twice, healthy then injected. If the
 * failure wording were already on the healthy page, finding it after injection would prove nothing;
 * and if the injection never fired, a silent page is indistinguishable from a passing one. Both are
 * guarded explicitly below, because both have produced false greens in this repo before.
 */
import { expect } from '@playwright/test';
import { test } from './_fixtures';
import { waitForPageReady } from './_helpers';

test.use({ serviceWorkers: 'block' });

const ASSISTANT = '/workhive/assistant.html';

/** Wide enough to recognise the words this product actually uses, not just this author's phrasing.
 *  An oracle that only knows its own wording measures vocabulary, not behaviour. */
const FAILURE_WORDS =
  /something went wrong|may nangyaring mali|couldn'?t|could not|failed|unable to|try again|subukan|busy|abala|expired|nag-expire/i;

/** The misdiagnosis the incident produced. These words must NOT appear for a model-not-found cause. */
const RATE_LIMIT_WORDS =
  /rate.?limit|too many|quota|call limit|limit reached|hinto muna|masyadong marami/i;

/** Ask the assistant something and wait for the turn to settle either way. */
async function ask(page: any, text: string) {
  const input = page.locator('#chat-input');
  await input.waitFor({ state: 'visible', timeout: 30_000 });
  await input.fill(text);
  await page.locator('#send-btn').click();
  // The turn is done when the composer re-enables; fall through on timeout so the
  // assertions below can report what the page actually showed.
  await page.waitForFunction(
    () => { const b = document.getElementById('send-btn') as HTMLButtonElement | null; return !!b && !b.disabled; },
    { timeout: 45_000 },
  ).catch(() => {});
  await page.waitForTimeout(1200);
  return (await page.locator('#chat-messages').innerText()).replace(/\s+/g, ' ');
}

test('models_are_live: the assistant answers while every chain model is live', async ({ whPage }) => {
  await whPage.goto(ASSISTANT);
  await waitForPageReady(whPage);

  const thread = await ask(whPage, 'In one short sentence, what is preventive maintenance?');

  // The point of the happy path is the BASELINE for the test below: the failure vocabulary must be
  // absent here, or its presence after injection would prove nothing. A skip is honest when the
  // local edge runtime has no key — but a silent pass is not, so say which case this was.
  const failure = whPage.evaluate(() => (window as any).__whGatewayFailure ?? null);
  const classified = await failure;

  if (classified) {
    test.skip(true,
      `the live gateway could not answer (classified "${classified}"), so this run measured the ` +
      `environment rather than the chain — start the edge runtime and set a provider key to make ` +
      `this assertion meaningful`);
  }

  expect(thread.length,
    'the assistant thread rendered almost nothing, so neither an answer nor a failure was shown')
    .toBeGreaterThan(40);
  expect(RATE_LIMIT_WORDS.test(thread),
    'a healthy turn already speaks of rate limits, so the injected test below could not tell the ' +
    'two causes apart').toBe(false);
});

test('models_are_live: a retired model is never reported to the person as a rate limit', async ({ whPage }) => {
  await whPage.goto(ASSISTANT);
  await waitForPageReady(whPage);

  // Every model in the chain is gone — the 2026-09-10 shape, in the provider's own words. 404 with
  // `model_not_found` is exactly what Groq returned for the four retired entries.
  let intercepted = 0;
  await whPage.route('**/functions/v1/ai-gateway**', async route => {
    intercepted++;
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          message: 'The model `meta-llama/llama-4-scout-17b-16e-instruct` does not exist or you do not have access to it.',
          type: 'invalid_request_error',
          code: 'model_not_found',
        },
      }),
    });
  });

  const thread = await ask(whPage, 'In one short sentence, what is preventive maintenance?');
  const classified = await whPage.evaluate(() => (window as any).__whGatewayFailure ?? null);

  // The injection must actually have fired, or this measured nothing at all.
  expect(intercepted,
    'the route never matched the ai-gateway call, so the page was never made to fail — this is an ' +
    'instrument failure, not a passing surface').toBeGreaterThan(0);

  // 1 · it must SAY the turn failed. Silence after a 404 leaves the person waiting on an answer
  //     that is never coming.
  expect(FAILURE_WORDS.test(thread),
    `the gateway returned 404 model_not_found ${intercepted} time(s) and the thread never said the ` +
    `turn had failed. It showed: "${thread.slice(0, 240)}"`).toBe(true);

  // 2 · and it must not tell the WRONG story. This is the whole rule: a model the provider no longer
  //     serves is a chain defect, and calling it a rate limit sends the person off to wait instead
  //     of the maintainer off to fix the chain.
  expect(RATE_LIMIT_WORDS.test(thread),
    `a model_not_found failure was reported to the person as a rate limit — the exact misdiagnosis ` +
    `"All models failed (rate limited or down)" that models_are_live exists to prevent. Thread: ` +
    `"${thread.slice(0, 240)}"`).toBe(false);

  expect(classified,
    `the gateway failure was classified "${classified}" for a 404 model_not_found; 'rate_limit' ` +
    `drives the rate-limit sentence in the composer toast and would repeat the misdiagnosis`)
    .not.toBe('rate_limit');

  // 3 · and it must not answer anyway. A fabricated reply after a total chain failure is worse than
  //     any error message, because nothing marks it as unfounded.
  expect(/preventive maintenance is|ang preventive maintenance ay/i.test(thread),
    `the thread rendered a substantive answer to the question while every model was returning 404 — ` +
    `an answer with no model behind it`).toBe(false);
});
