// walk_conditions.mjs - Wave VX-J's field conditions, emulated in a Playwright context (2026-11-15).
//
// The critic batch walked only normal, offline-3g, dependency-down and release-mid-way. Wave VX-J asks each journey
// under six conditions a field person meets. Each is emulated here in the BROWSER CONTEXT only - no database mutation,
// no server change - so a walk grades what the person sees under the condition, and refuses rather than grade "normal"
// when a condition has no emulation (the batch's KNOWN_COND guard).
//
//   offline-mid-task         the first page loads online, then the network is cut before the rest of the journey
//   slow-3g                  every request is delayed ~600 ms and bodies trickle (CDP Network.emulateNetworkConditions)
//   rate-limited-429         every edge-function and REST write answers 429 with Retry-After (reads still pass)
//   session-expired          the stored session's access token is replaced with an expired one before the journey
//   second-device            a second context signs in as the same person and makes the first context's data stale
//                            (handled by the caller: it needs the sign-in helper) - here only the marker
//   returning-after-30-days  the page clock is moved 30 days ahead (Date only; the server's clock is untouched)

// conditions whose walk needs the service worker ALLOWED (the batch blocks it otherwise)
export const WANTS_SW = new Set(['offline-mid-task']);

export const VX_CONDITIONS = ['offline-mid-task', 'slow-3g', 'rate-limited-429', 'session-expired', 'second-device',
  'returning-after-30-days'];

const THIRTY_DAYS = 30 * 24 * 3600 * 1000;

/** Set up the context BEFORE the first page of the walk opens. */
export async function prepareCondition(ctx, cond) {
  if (cond === 'rate-limited-429') {
    const limited = (route) => route.fulfill({ status: 429, headers: { 'Retry-After': '30', 'Content-Type': 'application/json' },
      body: '{"error":"rate limited (critic-walk probe)"}' });
    await ctx.route('**/functions/v1/**', limited);
    await ctx.route('**/rest/v1/**', (route) => (route.request().method() === 'GET' ? route.continue() : limited(route)));
  }
  if (cond === 'returning-after-30-days') {
    await ctx.addInitScript((ms) => {
      const RealDate = Date;
      const shift = ms;
      // eslint-disable-next-line no-global-assign
      Date = class extends RealDate {
        constructor(...a) { super(...(a.length ? a : [RealDate.now() + shift])); }
        static now() { return RealDate.now() + shift; }
      };
    }, THIRTY_DAYS);
  }
  if (cond === 'session-expired') {
    await ctx.addInitScript(() => {
      try {
        for (const k of Object.keys(localStorage)) {
          if (!/auth-token/.test(k)) continue;
          const v = JSON.parse(localStorage.getItem(k) || 'null');
          if (v && v.expires_at) { v.expires_at = Math.floor(Date.now() / 1000) - 3600; v.access_token = 'expired.' + (v.access_token || ''); localStorage.setItem(k, JSON.stringify(v)); }
        }
      } catch (_) { /* storage blocked: the walk reads the page as it is */ }
    });
  }
}

/** Called on each new page of the walk; `index` is its position in the journey. */
export async function onPage(page, ctx, cond, index) {
  if (cond === 'slow-3g') {
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 600,
      downloadThroughput: (400 * 1024) / 8, uploadThroughput: (400 * 1024) / 8 });
  }
  // ★A PHONE THAT LOSES SIGNAL STILL HAS ITS SERVICE WORKER (2026-11-15): the first run blocked the worker, so 47 of 58
  // walks failed on ERR_INTERNET_DISCONNECTED - a reading of no app a person could have. The worker installs on the first
  // page (it precaches the shell); the network goes only after it is running.
  if (cond === 'offline-mid-task' && index === 1) {
    if (!ctx.serviceWorkers().length) await ctx.waitForEvent('serviceworker', { timeout: 15000 }).catch(() => {});
    await new Promise((r) => setTimeout(r, 3000));   // let the install precache the shell
    await ctx.setOffline(true);
  }
}

export function conditionNote(cond) {
  return {
    'offline-mid-task': 'graded with the network cut after the first page of the journey',
    'slow-3g': 'graded under CDP slow-3g (600 ms latency, 400 kbps)',
    'rate-limited-429': 'graded with every edge call and REST write answering 429 + Retry-After',
    'session-expired': 'graded with the stored session expired before the journey began',
    'second-device': 'graded on the first device while the same person stays signed in on a second device',
    'returning-after-30-days': 'graded with the page clock 30 days ahead',
  }[cond] || '';
}
