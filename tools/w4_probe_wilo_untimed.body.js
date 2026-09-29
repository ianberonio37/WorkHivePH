// Does the Week view draw an untimed item?
//
// The first run answered "0 chips" and that was NOT the fix failing: this reader's six rows all carry
// a start time (2026-07-19 07:00 ... 2026-07-20 10:30), so the all-day row correctly drew nothing.
// B's 131-of-231 figure is across the whole table, not this worker's slice.
//
// So the item is injected into the page's IN-MEMORY scheduleItems and re-rendered. Nothing is written:
// no RPC, no upsert, no queue - render() reads local state, and a reload discards it. A walk must
// never call a mutating RPC, and this does not.
async (page) => {
  const origin = 'http://localhost:5000/workhive';
  const out = { problems: [] };
  page.on('dialog', (d) => d.accept().catch(() => {}));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/index.html?signin=1&return=dayplanner.html`, { waitUntil: 'load' });
  await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
  if (await page.locator('#si-username').isVisible().catch(() => false)) {
    await page.fill('#si-username', 'hectorsalvador');
    await page.fill('#si-password', 'test1234');
    await page.click('#si-btn').catch(() => {});
    await page.waitForURL(/dayplanner\.html/, { timeout: 25000 }).catch(() => out.problems.push('sign-in did not land'));
  }
  await page.waitForTimeout(4500);

  out.before = await page.evaluate(() => ({
    rows: (typeof scheduleItems !== 'undefined' ? scheduleItems : []).length,
    untimed: (typeof scheduleItems !== 'undefined' ? scheduleItems : []).filter(i => !i.startTime).length,
  }));

  // local-only: two untimed jobs on this week, and one crossing midnight to exercise the night shift
  out.injected = await page.evaluate(() => {
    const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const t = new Date();
    const t2 = new Date(); t2.setDate(t2.getDate() + 1);
    scheduleItems.push(
      { id: 'probe-untimed-1', title: 'Probe: replace sight glass', date: ymd(t),  startTime: '', endTime: '', category: 'CM', notes: '', logbookRef: null, itemStatus: null, sourceKind: null, sourceRef: null },
      { id: 'probe-untimed-2', title: 'Probe: order gasket set',    date: ymd(t2), startTime: '', endTime: '', category: 'PM', notes: '', logbookRef: null, itemStatus: null, sourceKind: null, sourceRef: null },
      { id: 'probe-night-1',   title: 'Probe: night boiler watch',  date: ymd(t),  startTime: '23:00', endTime: '01:00', category: 'PM', notes: '', logbookRef: null, itemStatus: null, sourceKind: null, sourceRef: null },
    );
    switchView('wilo');
    return scheduleItems.length;
  });
  await page.waitForTimeout(1200);

  out.wilo = await page.evaluate(() => ({
    period: (document.getElementById('period-label') || {}).textContent || '',
    allDayRowPresent: !!Array.from(document.querySelectorAll('.wilo-grid')).find(g => /No time|Walang oras/.test(g.textContent || '')),
    untimedChips: document.querySelectorAll('.wilo-grid [role="button"][aria-label*="no time"]').length,
    chipNames: Array.from(document.querySelectorAll('.wilo-grid [role="button"][aria-label*="no time"]')).map(e => e.getAttribute('aria-label')),
    chipBoxes: Array.from(document.querySelectorAll('.wilo-grid [role="button"][aria-label*="no time"]')).map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }),
    timedBlocks: document.querySelectorAll('.wilo-grid [onclick*="openEditModal"]').length,
  }));

  // the day view: the night job's duration, its label, and the capacity figure it now contributes to
  await page.evaluate(() => switchView('dilo'));
  await page.waitForTimeout(1200);
  out.dilo = await page.evaluate(() => {
    const cap = Array.from(document.querySelectorAll('div')).find(d => /Capacity|Kapasidad/.test(d.textContent || '') && d.textContent.length < 260);
    const night = Array.from(document.querySelectorAll('[title*="night boiler watch"]'))[0];
    return {
      capacityRow: cap ? cap.textContent.replace(/\s+/g, ' ').trim().slice(0, 200) : null,
      nightTitle: night ? night.getAttribute('title') : null,
      nightBox: night ? (() => { const r = night.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })() : null,
      nightStatus: (typeof getItemStatus === 'function') ? getItemStatus(scheduleItems.find(i => i.id === 'probe-night-1')) : null,
      gridBottom: (() => { const g = document.querySelector('.calendar-wrap'); return g ? Math.round(g.scrollHeight) : null; })(),
    };
  });

  out.after = await page.evaluate(() => ({
    // nothing left the browser: the probe rows exist only in this tab's memory
    stillLocalOnly: scheduleItems.filter(i => String(i.id).startsWith('probe-')).length,
  }));
  return out;
}
