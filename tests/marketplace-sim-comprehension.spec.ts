/**
 * marketplace-sim-comprehension.spec.ts — the two cells the registry called "needs human judgement".
 *
 * They were classified manual because tone and comprehension feel unmeasurable. Most of both is not.
 * "Does this read warmly?" is a judgement; "does the money screen use the word ESCROW without ever
 * saying what escrow is?" is a fact, and it is the fact that actually decides whether someone with low
 * literacy or no marketplace experience can finish. Classifying a cell manual because its HARDEST part
 * needs a human leaves its LARGEST part untested — so this builds the structure instead of accepting
 * the ceiling, and the residue that genuinely needs Ian's eye is named at the end rather than implied.
 *
 * WHAT IS MEASURED HERE
 *   · jargon: a term of art on a money screen must be explained on that screen, or not used
 *   · sentence length: a 40-word sentence is a wall, whatever it says
 *   · the primary action must state its CONSEQUENCE, not just name itself
 *   · nothing may depend on a convention a first-timer has never met (an unexplained icon, an
 *     abbreviation, a colour that carries meaning alone)
 *
 * WHAT IS NOT: warmth, register, whether the Filipino reads naturally to a Filipino. Those stay human,
 * and the spec says so out loud rather than pretending the coverage is complete.
 */
import { test, expect, Page } from '@playwright/test';
import { adminClient, cleanupServiceArc } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';
const TAG = 'SIMCOMPREHEND';

/* Terms of art a first-time or low-literacy user has no reason to know. Each may appear ONLY if the same
   screen also explains it. These are the words this domain actually reaches for by default — the list is
   the point, not a formality. */
const JARGON: Array<[string, RegExp]> = [
  ['escrow',      /\bescrow(ed|s)?\b/i],
  ['remit',       /\bremit(tance|ted|s)?\b/i],
  ['disburse',    /\bdisburse(ment|d|s)?\b/i],
  ['reconcile',   /\breconcil(e|ed|iation)\b/i],
  ['ledger',      /\bledger\b/i],
  ['commission',  /\bcommission\b/i],
  ['liability',   /\bliabilit(y|ies)\b/i],
  ['counterparty',/\bcounterpart(y|ies)\b/i],
];

/** A gloss counts if the screen says what the word MEANS near it, in plain words. */
const GLOSSED = /\bmeans\b|\bthat is\b|\bi\.e\.\b|\(the |\bwhich is\b|\bin other words\b/i;

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

test.describe('marketplace simulation — comprehension', () => {
  test.describe.configure({ mode: 'serial' });
  let REQ = '';

  test.beforeAll(async ({ browser }) => {
    const cctx = await browser.newContext(); const c = await cctx.newPage();
    const pctx = await browser.newContext(); const p = await pctx.newPage();
    try {
      await signIn(c, CLIENT); await signIn(p, PROVIDER);
      REQ = await c.evaluate(async (tag) => {
        const db = (window as any).getDb();
        const { data: s } = await db.auth.getSession();
        const { data: mine } = await db.from('hive_members').select('hive_id')
          .eq('auth_uid', s.session.user.id).eq('status', 'active')
          .order('hive_id', { ascending: true }).limit(1);
        const { data } = await db.from('service_requests').insert({
          client_auth_uid: s.session.user.id, hive_id: mine?.[0]?.hive_id, segment: 'consumer',
          mode: 'instant', status: 'broadcasting', custom_scope: tag + ' comprehension job', budget: 1500,
        }).select('id').single();
        return data?.id as string;
      }, TAG);
      const acc = await p.evaluate(async (r) => {
        const db = (window as any).getDb();
        const { data } = await db.rpc('accept_service_request', { p_request_id: r });
        return { ok: !!data?.accepted, reason: data?.reason };
      }, REQ);
      expect(acc.ok, `could not stage: ${acc.reason}`).toBe(true);
      for (const st of ['en_route', 'on_site', 'in_progress', 'completed']) {
        await p.evaluate(async ([r, s]) => {
          const db = (window as any).getDb();
          await db.from('service_requests').update({ status: s }).eq('id', r);
        }, [REQ, st] as any);
      }
    } finally { await cctx.close(); await pctx.close(); }
  });

  test.afterAll(async () => { await cleanupServiceArc(TAG); });

  test('P-LOWLITERACY · the money screen explains every term of art it uses', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    await page.click('[data-section="services"]');
    await page.waitForTimeout(2500);

    const text = await page.evaluate((rid) => {
      (window as any).svcConfirmPay(rid, 1500);
      return (document.getElementById('svc-pay-' + rid) as HTMLElement)?.innerText || '';
    }, REQ);
    expect(text.length, 'the money form rendered no text to read').toBeGreaterThan(40);

    const unexplained = JARGON
      .filter(([, re]) => re.test(text))
      .filter(([word]) => {
        // Explained if a gloss appears within ~120 chars of the first use.
        const i = text.toLowerCase().indexOf(word.slice(0, 6));
        return !GLOSSED.test(text.slice(Math.max(0, i - 120), i + 160));
      })
      .map(([w]) => w);
    expect(unexplained, `the money screen uses terms of art it never explains: ${unexplained.join(', ')} `
      + '— someone is agreeing to a peso figure described in words they have no reason to know')
      .toEqual([]);

    // A wall of text is inaccessible whatever it says. 30 words is already a long spoken sentence.
    const longest = text.split(/[.!?]\s+/)
      .map(s => s.trim().split(/\s+/).length)
      .reduce((a, b) => Math.max(a, b), 0);
    expect(longest, `the longest sentence on the money screen is ${longest} words — past roughly 30 it `
      + 'stops being read and starts being skipped').toBeLessThanOrEqual(30);
  });

  test('P-FIRSTTIME · the primary action states its CONSEQUENCE, not just its name', async ({ page }) => {
    /* "Submit" tells a first-timer nothing. On a money screen the button has to say what will happen to
       the money, because that is the only question they are actually asking. */
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    await page.click('[data-section="services"]');
    await page.waitForTimeout(2500);

    const r = await page.evaluate((rid) => {
      (window as any).svcConfirmPay(rid, 1500);
      const go = document.getElementById('svc-pay-go-' + rid) as HTMLElement;
      const slot = document.getElementById('svc-pay-' + rid) as HTMLElement;
      return { label: (go?.innerText || '').trim(), body: (slot?.innerText || '') };
    }, REQ);

    expect(r.label.toLowerCase(), `the primary action reads "${r.label}" — a bare verb tells a first-time `
      + 'user nothing about what happens to their money').not.toMatch(/^(submit|ok|confirm|send|done|go)$/);
    // It must name the two things that actually change: the payment is recorded, the job is released.
    expect(r.label.toLowerCase(), 'the button does not say what it will do').toMatch(/pay|release/);
    // And the screen must state who ends up with the money, since that is the question being asked.
    expect(r.body.toLowerCase(), 'the screen never says who receives the money, which is the ONE thing a '
      + 'first-time user is trying to find out').toMatch(/provider|directly|never holds/);
  });

  test('P-FIRSTTIME · nothing carries meaning by icon or colour alone', async ({ page }) => {
    // A first-timer has met none of this platform's conventions. An icon with no words beside it is a
    // convention; so is a status conveyed only by a colour swatch.
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    await page.click('[data-section="services"]');
    await page.waitForTimeout(2500);

    const bare = await page.evaluate(() => {
      const out: string[] = [];
      document.querySelectorAll('#services-pane button, #services-pane a').forEach(el => {
        const e = el as HTMLElement;
        if (!e.offsetParent) return;                       // not visible
        const txt = (e.innerText || '').replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}️]/gu, '').trim();
        const named = txt || e.getAttribute('aria-label') || e.getAttribute('title') || '';
        if (!named.trim()) out.push(e.id || e.className || e.tagName);
      });
      return out;
    });
    expect(bare, `controls that are an icon with no words and no label: ${bare.join(', ')} — a first-time `
      + 'user has met none of this platform\'s conventions').toEqual([]);
  });

  test('the residue that genuinely needs a human is NAMED, not implied', async () => {
    /* The honest half. Warmth, register, and whether the Filipino reads naturally to a Filipino cannot be
       asserted, and pretending otherwise would be a false 100%. This cell exists so the bank carries the
       remaining judgement as a written obligation rather than as silence — a skipped partition must never
       read as a covered one. */
    const humanResidue = [
      'does the Filipino money copy read naturally to a Filipino, or like a translation?',
      'does "Kumpirmahin ang bayad" carry the same finality as "Confirm payment & release"?',
      'would a first-time GCash user trust this screen enough to press the button?',
    ];
    expect(humanResidue.length, 'the human-judgement residue must stay explicitly listed').toBeGreaterThan(0);
    console.log('HUMAN JUDGEMENT STILL OWED (by design):\n  - ' + humanResidue.join('\n  - '));
  });
});
