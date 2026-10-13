// prove_offline_queue_forced_close.js - run through the Playwright MCP:
//   browser_run_code_unsafe filename=tools/prove_offline_queue_forced_close.js
//
// 2026-10-13, critique W45908 (dayplanner): the walk's console carried an unhandled rejection every 60 s -
// "InvalidStateError: Failed to execute 'transaction' on 'IDBDatabase': The database connection is closing" from
// offline-queue.js getPending <- drain. The walker had cleared the origin's IndexedDB at the end of its walk while the
// page was still open, and the browser force-closed the queue's connection. whCreateQueue cached that connection
// forever (_dbRef), so every later transaction threw - not only the periodic drain but ENQUEUE, i.e. the next offline
// save on that page could not be queued until a reload. The same forced close happens to a person: site data
// cleared while the app is open, storage evicted on a full phone, a database deleted from another tab.
//
// What this proves, against the file ON DISK (fetched past the service worker and evaluated fresh):
//   1. enqueue works, then the origin's IndexedDB is cleared under the open connection (CDP, as the walker does);
//   2. the NEXT enqueue must land (the queue re-opens its database) and getPending must read it back;
//   3. drain() with a stub client must resolve, not reject;
//   4. deleting the queue's database from the page must not be BLOCKED by the queue's own open connection.
// It touches only its own database name (wh_probe_forced_close) and an in-page stub client: no network write.
async (page) => {
  const base = 'http://localhost:5000/workhive';
  const origin = 'http://localhost:5000';
  const out = { file: 'offline-queue.js', steps: [] };
  const src = await (await page.request.get(`${base}/offline-queue.js`, { timeout: 8000 })).text();
  out.hasCloseHandler = /onclose|addEventListener\(\s*['"]close['"]/.test(src);
  await page.goto(`${base}/index.html`, { waitUntil: 'domcontentloaded' });
  await page.evaluate((s) => {
    delete window.whCreateQueue;
    (0, eval)(s);
    window.__pq = window.whCreateQueue({ db: 'wh_probe_forced_close', table: 'probe_forced_close' });
  }, src);
  const step = async (name, fn) => {
    try { const v = await page.evaluate(fn); out.steps.push({ name, ok: true, v }); return v; }
    catch (e) { out.steps.push({ name, ok: false, err: String(e.message || e).split('\n')[0].slice(0, 160) }); return null; }
  };
  await step('enqueue before the forced close', async () => { await window.__pq.enqueue({ id: 'a', op: 'insert', payload: { n: 1 } }); return (await window.__pq.getPending()).length; });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Storage.clearDataForOrigin', { origin, storageTypes: 'indexeddb' });
  await page.waitForTimeout(500);
  await step('enqueue AFTER the forced close', async () => { await window.__pq.enqueue({ id: 'b', op: 'insert', payload: { n: 2 } }); return (await window.__pq.getPending()).map((r) => r.id); });
  await step('drain AFTER the forced close (stub client)', async () => {
    const stub = { from: () => ({ insert: async () => ({ error: null }) }) };
    return await window.__pq.drain(stub);
  });
  await step('pending after the drain', async () => (await window.__pq.getPending()).length);
  await step('delete the probe database (must not be blocked)', () => new Promise((resolve) => {
    const r = indexedDB.deleteDatabase('wh_probe_forced_close');
    let blocked = false;
    r.onblocked = () => { blocked = true; };
    r.onsuccess = () => resolve({ deleted: true, blockedFirst: blocked });
    r.onerror = () => resolve({ deleted: false, blockedFirst: blocked });
    setTimeout(() => resolve({ deleted: false, blockedFirst: blocked, timedOut: true }), 3000);
  }));
  try { await cdp.detach(); } catch (e) { void e; }
  const s = out.steps;
  out.verdict = (s[1] && s[1].ok && s[2] && s[2].ok && s[4] && s[4].v && s[4].v.deleted && !s[4].v.blockedFirst)
    ? 'PASS: the queue survives a forced close' : 'FAIL: the queue is dead after a forced close';
  return out;
}
