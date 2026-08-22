/**
 * UX JOURNEYS — the multi-step claims a single-page probe cannot settle
 * ═══════════════════════════════════════════════════════════════════════════════════════════════
 *
 * 32 rows in the live-MCP bank assert something about a JOURNEY: a first-timer reaching value, a
 * returning person not redoing setup, context surviving a handoff between surfaces, an abandoned
 * flow leaving nothing half-applied, two identities seeing one object truthfully. Every one of them
 * had been walked by hand and expired the moment its page was edited.
 *
 * A journey has a property no single-page probe has: it must ADVANCE. So the discipline here is the
 * one earned by "a click that changes NOTHING logs as ok" — every step asserts the transition, never
 * merely that the control was clickable. A control that is present, enabled, hit-testable and inert
 * fails these tests.
 *
 * NON-VACUITY. A journey that cannot be CONSTRUCTED fails; it never skips. If a surface has no
 * composer to abandon or no link to hand off through, that is a finding about the surface (or about
 * this file's knowledge of it), and it must be looked at — not quietly counted as a pass.
 */
import { expect } from '@playwright/test';
import { test } from './_fixtures';
import type { Page } from '@playwright/test';

type Surface = {
  name: string;
  url: string;
  /** Something that only appears once real content has loaded. */
  content: string;
  /** A control that changes the page when used, and the proof that it did. */
  advance?: { control: string; changes: string };
  /** A multi-step form whose abandonment must leave nothing behind. */
  composer?: { open?: string; field: string; submit: string };
};

const SURFACES: Surface[] = [
  {
    name: 'market',
    url: '/workhive/marketplace.html',
    content: '[class*="listing-card"], [class*="card"]',
    advance: { control: '#filter-chips button, #filter-chips [role="button"]', changes: 'rows' },
  },
  {
    name: 'market_svc',
    url: '/workhive/marketplace.html?section=services',
    content: '[class*="card"]',
    advance: { control: '#filter-chips button, #filter-chips [role="button"]', changes: 'rows' },
  },
  {
    name: 'seller',
    url: '/workhive/marketplace-seller.html',
    content: '#ps-listings, [class*="card"]',
    composer: { field: '#messenger-input', submit: '#btn-save-messenger' },
  },
  {
    name: 'admin',
    url: '/workhive/platform-actions.html',
    content: '#mkt-listings-count, [class*="card"]',
    composer: { open: 'button[data-fb-id]', field: '#fb-d-note', submit: '#fb-d-save' },
  },
];

/** Wait for the surface to stop moving, without letting a hung read read as a settled page. */
async function settle(page: Page) {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1200);
}

/** A dead end: the person is looking at a surface that offers them nothing to do next. */
async function deadEndReport(page: Page) {
  return page.evaluate(() => {
    const vis = (el: Element) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const actionable = [...document.querySelectorAll(
      'button:not([disabled]), a[href]:not([href^="#"]), [role="button"]:not([aria-disabled="true"]), input, select, textarea')]
      .filter(vis);
    const body = (document.body.innerText || '').replace(/\s+/g, ' ');
    return { actionable: actionable.length, chars: body.length, text: body.slice(0, 400) };
  });
}

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// J1 · first_run_to_value — a first-time person reaches the first useful outcome without a dead end
// ═══════════════════════════════════════════════════════════════════════════════════════════════
for (const s of SURFACES) {
  test(`journey_first_run_to_value · ${s.name}: a first-timer reaches value without a dead end`,
    async ({ whPage }) => {
      // Everything a returning visitor would carry, removed — EXCEPT the session, because a
      // first-time SIGNED-IN person is the journey under test. Wiping auth would test the sign-in
      // wall instead, and would sign the walker out for every later step.
      await whPage.goto(s.url);
      const cleared = await whPage.evaluate(() => {
        const keep = /auth|token|session|supabase|sb-/i;
        const dropped: string[] = [];
        for (const k of Object.keys(localStorage)) if (!keep.test(k)) { dropped.push(k); localStorage.removeItem(k); }
        sessionStorage.clear();
        return dropped;
      });
      await whPage.reload();
      await settle(whPage);

      const rows = await whPage.locator(s.content).count();
      const report = await deadEndReport(whPage);

      expect(rows,
        `${s.name}: with ${cleared.length} returning-visitor key(s) cleared, a first-timer sees 0 rows ` +
        `of content. First run reaches nothing. Page said: "${report.text.slice(0, 200)}"`)
        .toBeGreaterThan(0);
      expect(report.actionable,
        `${s.name}: a first-timer sees ${rows} row(s) but nothing they can act on — that is a dead ` +
        `end, which is what this journey exists to rule out`).toBeGreaterThan(0);
    });
}

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// J2 · repeat_visit — a returning person is not made to redo setup
// ═══════════════════════════════════════════════════════════════════════════════════════════════
for (const s of SURFACES) {
  test(`journey_repeat_visit · ${s.name}: a returning person is not made to redo setup`,
    async ({ whPage }) => {
      await whPage.goto(s.url);
      await settle(whPage);
      const firstRows = await whPage.locator(s.content).count();
      expect(firstRows,
        `${s.name}: the first visit rendered 0 rows, so a second visit has nothing to compare ` +
        `against`).toBeGreaterThan(0);

      // The second visit. Same session, same everything — the only thing that changed is that the
      // person has been here before.
      await whPage.goto(s.url);
      await settle(whPage);
      const secondRows = await whPage.locator(s.content).count();

      // A blocking setup gate on a REPEAT visit is the defect: an onboarding sheet, a "choose your
      // hive" prompt, a tour — anything that stands between a returning person and the content they
      // already reached once.
      const gate = await whPage.evaluate(() => {
        const modals = [...document.querySelectorAll(
          '[role="dialog"], [aria-modal="true"], .modal, [class*="onboard"], [class*="tour"], [class*="welcome"]')]
          .filter(el => {
            const r = el.getBoundingClientRect();
            if (r.width <= 120 || r.height <= 80) return false;
            // "Blocking" is a PAINTED-IN-FRONT-OF-THE-PERSON fact, and it took three terms to ask it
            // honestly (measured 2026-08-21, six closed sheets reported as gates on a page the
            // screenshot shows fully usable):
            //  1. the element's own display/visibility/opacity — not enough, marketplace's dialog
            //     sheets read opacity:1;
            //  2. ancestor opacity via checkVisibility — not enough either, the opacity:0 overlay is
            //     the sheet's SIBLING, not its parent (openSheet() flips .open on both);
            //  3. viewport intersection — the sheets actually hide by TRANSLATING BELOW the viewport,
            //     which no opacity or visibility check sees, while their boxes stay full-size.
            const inViewport = r.bottom > 0 && r.right > 0
              && r.top < window.innerHeight && r.left < window.innerWidth;
            if (!inViewport) return false;
            if (typeof (el as any).checkVisibility === 'function'
                && !(el as any).checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) {
              return false;
            }
            const st = getComputedStyle(el);
            return st.display !== 'none' && st.visibility !== 'hidden' && +st.opacity > 0.01
                   && st.pointerEvents !== 'none';
          });
        return modals.map(m => (m.textContent || '').replace(/\s+/g, ' ').slice(0, 90));
      });

      expect(gate,
        `${s.name}: a returning visit is blocked by ${gate.length} setup/onboarding panel(s): ` +
        `${JSON.stringify(gate)}`).toEqual([]);
      expect(secondRows,
        `${s.name}: the first visit rendered ${firstRows} rows and the second rendered ${secondRows} ` +
        `— coming back cost the person content they had already reached`).toBeGreaterThanOrEqual(firstRows);
    });
}

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// J3 · cross_surface_handoff — context survives the move between surfaces
// ═══════════════════════════════════════════════════════════════════════════════════════════════
// The handoff this product actually makes: a listing card names its seller, and following that name
// must land on THAT seller — not on a generic profile, and not on whoever the page defaults to. The
// clicked name is captured from the DOM and compared to what the destination renders, so the test
// cannot be satisfied by any profile page loading.
// market only: ?section=services is the service-HAILING pane (SERVICE_HAILING_ROADMAP D14) — the
// listings grid is hidden there and no seller card renders BY DESIGN, so a seller-handoff journey
// does not exist on that surface (its own handoff, hail → offers → provider, is a different journey
// that needs its own test). The two market_svc bank rows are declared-na with this reasoning; forcing
// the listings-shaped oracle onto the hail pane produced only false "no seller link" findings
// (measured 2026-08-21).
for (const s of SURFACES.filter(x => x.name === 'market')) {
  test(`journey_cross_surface_handoff · ${s.name}: the seller you clicked is the seller you land on`,
    async ({ whPage }) => {
      await whPage.goto(s.url);
      await settle(whPage);

      // :visible, because .first() alone picks DOCUMENT order: on the services section the first
      // a.seller-link in the DOM belongs to the HIDDEN parts list, and the click waited 8s on an
      // element that was never going to be visible (measured 2026-08-21 — the same document-order
      // trap assistant's #chat-input selector recorded: the page renders every section's list and
      // shows one).
      const link = whPage.locator('a.seller-link[data-seller]:visible').first();
      const found = await link.count();
      expect(found,
        `${s.name}: no VISIBLE seller link is on this surface, so the handoff cannot be walked. ` +
        `Either the card stopped naming its seller or this test is looking for the wrong control — ` +
        `both are findings, neither is a pass`).toBeGreaterThan(0);

      const clickedSeller = (await link.getAttribute('data-seller'))?.trim() || '';
      expect(clickedSeller,
        `${s.name}: the seller link carries an empty data-seller, so the handoff has no context to ` +
        `carry`).not.toBe('');

      await link.click();
      await settle(whPage);

      const landedUrl = whPage.url();
      expect(landedUrl,
        `${s.name}: following the seller link did not reach a seller profile (went to ${landedUrl})`)
        .toContain('marketplace-seller-profile.html');

      const shown = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
      expect(shown.includes(clickedSeller),
        `${s.name}: clicked "${clickedSeller}" and the profile that loaded never names them. The ` +
        `handoff carried the navigation but not the context. URL: ${landedUrl}`).toBe(true);
    });
}

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// J4 · abandon_resume — leaving midway leaves nothing half-applied
// ═══════════════════════════════════════════════════════════════════════════════════════════════
for (const s of SURFACES.filter(x => x.composer)) {
  test(`journey_abandon_resume · ${s.name}: abandoning midway leaves nothing half-applied`,
    async ({ whPage }) => {
      const cc = s.composer!;
      await whPage.goto(s.url);
      await settle(whPage);

      if (cc.open) {
        const opener = whPage.locator(cc.open).first();
        expect(await opener.count(),
          `${s.name}: the composer's opener ${cc.open} is not on this surface, so there is no ` +
          `half-finished flow to abandon`).toBeGreaterThan(0);
        await opener.click();
        await whPage.locator(cc.field).first().waitFor({ state: 'visible', timeout: 8000 });
      }

      const field = whPage.locator(cc.field).first();
      expect(await field.count(),
        `${s.name}: the composer field ${cc.field} is not on this surface`).toBeGreaterThan(0);

      const original = await field.inputValue();
      const abandoned = `WH abandoned draft ${Date.now().toString().slice(-6)}`;

      // Every write this surface makes, watched. Abandoning must send NOTHING — that is the whole
      // claim, and counting requests is the only way to see a write that left without a visible sign.
      // ★ATTRIBUTION ENDS WHEN THE NEXT DOCUMENT COMMITS. The first version kept counting through
      // the destination page's load, and failed seller/admin on SEVEN requests that were all the
      // DESTINATION's own: its analytics_events insert and its read-only RPCs — which PostgREST
      // transports as POST regardless of semantics (measured 2026-08-21: service_knob/_pct,
      // get_marketplace_trust_badges). A beforeunload-fired write still lands inside the window,
      // because it goes out BEFORE the new document commits — so a genuine leak cannot hide behind
      // this cut; only the new page's own traffic falls outside it.
      const writes: string[] = [];
      let departed = false;
      whPage.on('framenavigated', f => {
        if (f === whPage.mainFrame() && !f.url().includes(s.url)) departed = true;
      });
      whPage.on('request', r => {
        if (departed) return;
        if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(r.method())) writes.push(`${r.method()} ${r.url().slice(0, 90)}`);
      });

      await field.fill(abandoned);
      // Leave. Not a reload — a genuine departure to another surface, which is how people abandon.
      await whPage.goto('/workhive/marketplace.html');
      await settle(whPage);

      expect(writes,
        `${s.name}: typing and then LEAVING sent ${writes.length} write(s) — the draft was applied ` +
        `although it was never submitted: ${JSON.stringify(writes.slice(0, 3))}`).toEqual([]);

      // Come back. The field must be in a state the person can trust: either their draft restored,
      // or the original value — never a half-applied mixture, and never the abandoned text presented
      // as if it had been saved.
      await whPage.goto(s.url);
      await settle(whPage);
      if (cc.open) {
        await whPage.locator(cc.open).first().click();
        await whPage.locator(cc.field).first().waitFor({ state: 'visible', timeout: 8000 });
      }
      const onReturn = await whPage.locator(cc.field).first().inputValue();

      expect([original, abandoned, ''].includes(onReturn),
        `${s.name}: after abandoning, the field came back holding "${onReturn}" — neither the saved ` +
        `value ("${original}"), nor the restored draft, nor empty. That is a half-applied state`)
        .toBe(true);

      // The decisive half: whatever the FIELD shows, the SERVER must not have taken the draft. Read
      // it back from a fresh load with no draft restoration in play.
      if (onReturn === abandoned) {
        const persisted = await whPage.evaluate(() => {
          const keys = Object.keys(localStorage).concat(Object.keys(sessionStorage));
          return keys.filter(k => /draft|compose|unsent/i.test(k));
        });
        expect(persisted.length,
          `${s.name}: the abandoned text came back, which is only trustworthy if it was kept as a ` +
          `local DRAFT. No draft key exists, so it came from the server — the abandoned write landed`)
          .toBeGreaterThan(0);
      }
    });
}
