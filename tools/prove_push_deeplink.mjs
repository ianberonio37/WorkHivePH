/* prove_push_deeplink.mjs — T105: a push keeps its DESTINATION, not just its page (2026-08-26).
 *
 * THE DEFECT THIS WAS BUILT AGAINST. sw.js's notificationclick matched an already-open tab with
 * `c.url.includes(target.split('?')[0])` — the PATH, with the query thrown away — and returned
 * `c.focus()`. Every url notify-push sends carries its destination in the QUERY (?tab=services,
 * ?asset=, ?post=). So a provider with marketplace-seller open on ?tab=listings who tapped a
 * job-offer push got their existing tab focused and nothing else: the push's promise evaporated
 * silently, which is the same class as a wall that drops the return-to (T4/T8/T43).
 *
 * THE ORACLE — three cases against the REAL worker, not a re-implementation of it:
 *   1. NO TAB OPEN        → a window is opened at the full target, query intact.
 *   2. TAB ON WRONG QUERY → the tab is NAVIGATED to the target (the case that was broken).
 *   3. TAB ALREADY THERE  → focus only, no redundant navigation (a navigate here would reload
 *                           the page under someone mid-task).
 *
 * ★WHY IT DRIVES THE WORKER'S OWN SOURCE. A test that copies the handler's logic proves only that
 * I can copy logic. This loads sw.js from disk, installs the listener it registers, dispatches a
 * synthetic notificationclick, and watches what the handler does to a fake clients registry — so
 * the assertion is about the file that ships. Node has no service-worker globals, so the harness
 * supplies the minimum the handler touches (self.addEventListener, clients, WindowClient) and
 * nothing more; anything the handler reaches for beyond that surfaces as an error, not a pass.
 *
 * Usage: node tools/prove_push_deeplink.mjs
 */
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const TARGET = '/workhive/marketplace-seller.html?tab=services';
const ORIGIN = 'https://workhiveph.com';

function makeClient(url) {
  return {
    url: ORIGIN + url,
    focused: false,
    navigatedTo: null,
    focus() { this.focused = true; return Promise.resolve(this); },
    navigate(u) { this.navigatedTo = u; this.url = new URL(u, this.url).href; return Promise.resolve(this); },
  };
}

/* Load the SHIPPING worker and capture the notificationclick listener it registers. */
function loadHandler() {
  const src = readFileSync('sw.js', 'utf8');
  const listeners = {};
  const opened = [];
  const clientsRegistry = { list: [] };
  const sandbox = {
    self: {
      addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
      registration: { showNotification: () => Promise.resolve(), scope: ORIGIN + '/workhive/' },
      location: { href: ORIGIN + '/workhive/sw.js', origin: ORIGIN },
      skipWaiting: () => Promise.resolve(),
      clients: { claim: () => Promise.resolve() },
    },
    clients: {
      matchAll: () => Promise.resolve(clientsRegistry.list),
      openWindow: (u) => { opened.push(u); return Promise.resolve(makeClient(u)); },
      claim: () => Promise.resolve(),
    },
    caches: { open: () => Promise.resolve({ addAll: () => Promise.resolve(), match: () => Promise.resolve(null), put: () => Promise.resolve() }),
              keys: () => Promise.resolve([]), delete: () => Promise.resolve(true), match: () => Promise.resolve(null) },
    fetch: () => Promise.resolve({ ok: true }),
    URL, console, Promise, Object, JSON,
  };
  sandbox.self.addEventListener = sandbox.self.addEventListener.bind(sandbox.self);
  sandbox.addEventListener = sandbox.self.addEventListener;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: 'sw.js' });
  const fns = listeners.notificationclick || [];
  if (!fns.length) throw new Error('sw.js registered NO notificationclick listener');
  return { fn: fns[0], clientsRegistry, opened };
}

async function runCase(openUrls) {
  const { fn, clientsRegistry, opened } = loadHandler();
  clientsRegistry.list = openUrls.map(makeClient);
  let waited = null;
  const evt = {
    notification: { close() {}, data: { url: TARGET } },
    waitUntil(p) { waited = p; },
  };
  fn(evt);
  if (waited) await waited;
  return { clients: clientsRegistry.list, opened };
}

const results = {};

// 1 — nothing open: a window opens at the FULL target
{
  const r = await runCase([]);
  results.noTab = r.opened.length === 1 && r.opened[0] === TARGET;
  console.log(`  no tab open        -> openWindow(${r.opened[0] || 'none'})  ${results.noTab ? 'OK' : 'WRONG'}`);
}

// 2 — a tab on the SAME PAGE, DIFFERENT query: it must be navigated (the broken case)
{
  const r = await runCase(['/workhive/marketplace-seller.html?tab=listings']);
  const c = r.clients[0];
  results.wrongQuery = c.navigatedTo === TARGET && c.focused === true && r.opened.length === 0;
  console.log(`  tab on ?tab=listings -> navigated=${JSON.stringify(c.navigatedTo)} focused=${c.focused}  ${results.wrongQuery ? 'OK' : 'WRONG'}`);
}

// 3 — a tab ALREADY at the target: focus, and do NOT reload it under the user
{
  const r = await runCase([TARGET]);
  const c = r.clients[0];
  results.alreadyThere = c.navigatedTo === null && c.focused === true && r.opened.length === 0;
  console.log(`  tab already there    -> navigated=${JSON.stringify(c.navigatedTo)} focused=${c.focused}  ${results.alreadyThere ? 'OK' : 'WRONG'}`);
}

const pass = results.noTab && results.wrongQuery && results.alreadyThere;
console.log((pass ? 'PASS' : 'FAIL') + ` — push deep-link fidelity: ${JSON.stringify(results)}`);
process.exit(pass ? 0 : 1);
