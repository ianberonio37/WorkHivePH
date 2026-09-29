// Live verification of the W45908 critique fixes on dayplanner.html (2026-09-15).
//
// The node prover (.tmp/prove_dayplanner_critique_fixes.mjs) executes the shipped FUNCTIONS; it cannot
// see a computed height, an accessible name, or whether the calendar has room to exist. Both
// assessments were explicit that they never opened a browser, so every geometric claim they made -
// the ~4px calendar at 1280, the 5.36px year cells at 390 - is arithmetic awaiting a measurement.
// This is that measurement, taken at the two viewports the design lens walks.
async (page) => {
  const out = { viewports: {}, problems: [] };
  const origin = 'http://localhost:5000/workhive';

  page.on('dialog', (d) => d.accept().catch(() => {}));   // never leave a confirm() hanging the run

  const signIn = async () => {
    await page.goto(`${origin}/index.html?signin=1&return=dayplanner.html`, { waitUntil: 'load' });
    await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
    if (await page.locator('#si-username').isVisible().catch(() => false)) {
      await page.fill('#si-username', 'hectorsalvador', { timeout: 8000 });
      await page.fill('#si-password', 'test1234', { timeout: 8000 });
      await page.click('#si-btn', { timeout: 10000 }).catch(() => {});
      await page.waitForURL(/dayplanner\.html/, { timeout: 25000 }).catch(() => {
        out.problems.push('sign-in did not reach dayplanner in 25s');
      });
    }
  };

  const measure = (label) => page.evaluate((lbl) => {
    const px = (el, p) => el ? Math.round(parseFloat(getComputedStyle(el)[p]) || 0) : null;
    const txt = (sel) => { const e = document.querySelector(sel); return e ? e.textContent.replace(/\s+/g, ' ').trim() : null; };
    const wrap = document.querySelector('.calendar-wrap');
    const main = document.querySelector('.main-area');
    const tog  = document.getElementById('sidebar-toggle');
    const badge = document.getElementById('sidebar-rail-count');
    const hourLabels = document.querySelectorAll('.calendar-wrap [style*="position:absolute"]');
    return {
      label: lbl,
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      // P2/§5.11 - the calendar must have room to exist
      calendarHeight: wrap ? Math.round(wrap.getBoundingClientRect().height) : null,
      calendarScrollHeight: wrap ? wrap.scrollHeight : null,
      calendarMinHeight: px(wrap, 'minHeight'),
      mainOverflowY: main ? getComputedStyle(main).overflowY : null,
      hourRowCount: document.querySelectorAll('.time-slot').length,
      anyHourLabelPainted: !!Array.from(hourLabels).find((e) => /\b(6 AM|12 AM|11 PM)\b/.test(e.textContent || '')),
      // §5.2 - the phone sidebar toggle
      toggleName: tog ? (tog.getAttribute('aria-label') || '') : null,
      toggleExpanded: tog ? tog.getAttribute('aria-expanded') : null,
      toggleControls: tog ? tog.getAttribute('aria-controls') : null,
      toggleBox: tog ? (() => { const r = tog.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })() : null,
      badgeText: badge ? badge.textContent.trim() : null,
      badgeShown: badge ? getComputedStyle(badge).display !== 'none' : null,
      // the copy the reader acts on
      verdict: txt('#dp-verdict-label'),
      verdictSub: txt('#dp-verdict-sub'),
      action: txt('#dp-action-text'),
      // §5.3 - the capacity figure
      capacityRow: (() => {
        const el = Array.from(document.querySelectorAll('div')).find((d) => /Capacity|Kapasidad/.test(d.textContent || '') && d.textContent.length < 200);
        return el ? el.textContent.replace(/\s+/g, ' ').trim().slice(0, 160) : null;
      })(),
      // the strip caption that was 10.88px on every page
      stripLabelPx: (() => {
        const e = document.querySelector('.wh-progress-strip span');
        return e ? +parseFloat(getComputedStyle(e).fontSize).toFixed(2) : null;
      })(),
      stripLabelText: txt('.wh-progress-strip span'),
      // any text still under the 12px floor
      underFloor: (() => {
        const bad = [];
        document.querySelectorAll('body *').forEach((e) => {
          if (!e.childNodes.length) return;
          const hasText = Array.from(e.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
          if (!hasText) return;
          const s = getComputedStyle(e);
          if (s.visibility === 'hidden' || s.display === 'none') return;
          const fs = parseFloat(s.fontSize);
          if (fs && fs < 11.5) bad.push(fs.toFixed(2) + 'px "' + e.textContent.replace(/\s+/g, ' ').trim().slice(0, 40) + '"');
        });
        return bad.slice(0, 8);
      })(),
    };
  }, label);

  // year-view geometry, measured rather than computed from the stylesheet
  const yiloCells = () => page.evaluate(() => {
    const cells = document.querySelectorAll('.yilo-mini-cell');
    const months = document.querySelectorAll('.yilo-month');
    const g = document.querySelector('.yilo-grid');
    const first = cells[0] ? cells[0].getBoundingClientRect() : null;
    const m0 = months[0] || null;
    return {
      gridColumns: g ? getComputedStyle(g).gridTemplateColumns : null,
      cellCount: cells.length,
      cellSize: first ? [+first.width.toFixed(2), +first.height.toFixed(2)] : null,
      cellPointerEvents: cells[0] ? getComputedStyle(cells[0]).pointerEvents : null,
      cellAriaHidden: cells[0] ? cells[0].getAttribute('aria-hidden') : null,
      monthRole: m0 ? m0.getAttribute('role') : null,
      monthTabIndex: m0 ? m0.getAttribute('tabindex') : null,
      monthName: m0 ? (m0.getAttribute('aria-label') || '').slice(0, 90) : null,
      monthBox: m0 ? (() => { const r = m0.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })() : null,
    };
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await signIn();
  await page.waitForTimeout(4500);
  out.viewports['phone-390'] = await measure('phone-390');

  // the Week view's all-day row, and the Year view's geometry
  await page.click('#tab-wilo', { timeout: 8000 }).catch(() => out.problems.push('could not reach the Week tab at 390'));
  await page.waitForTimeout(1200);
  const countChips = () => page.evaluate(() =>
    document.querySelectorAll('.wilo-grid [role="button"][aria-label*="no time"], .wilo-grid [role="button"][aria-label*="walang nakatakdang"]').length);
  // This reader's rows are all dated July, and WILO opens on the CURRENT week - so counting chips on
  // the week the page happens to open is a test of the seed data, not of the fix. Walk back until the
  // untimed row has something to draw, exactly as a supervisor would to reach his own overdue work.
  let chips = await countChips(), backs = 0;
  while (!chips && backs < 10) {
    await page.click('#btn-prev, [onclick*="navigate(-1)"]', { timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(700);
    chips = await countChips(); backs++;
  }
  out.viewports['phone-390'].wiloUntimedChips = chips;
  out.viewports['phone-390'].wiloWeeksBack = backs;
  out.viewports['phone-390'].wiloTimedBlocks = await page.evaluate(() =>
    document.querySelectorAll('.wilo-grid [onclick*="openEditModal"]').length);

  await page.click('#tab-yilo', { timeout: 8000 }).catch(() => out.problems.push('could not reach the Year tab at 390'));
  await page.waitForTimeout(1200);
  out.viewports['phone-390'].yilo = await yiloCells();

  await page.click('#tab-dilo', { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(800);

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.reload({ waitUntil: 'load' });
  await page.waitForTimeout(4500);
  out.viewports['desktop-1280'] = await measure('desktop-1280');
  await page.click('#tab-yilo', { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(1200);
  out.viewports['desktop-1280'].yilo = await yiloCells();
  await page.click('#tab-dilo', { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(600);

  const dir = 'C:/Users/ILBeronio/Desktop/Industry 4.0/AI Maintenance Engineer/Self-learning Road-Map/Build & Sell with Claude Code/Website simple 1st/.tmp/w4_design';
  await page.screenshot({ path: `${dir}/W45908_after_desktop-1280.png`, fullPage: true }).catch(() => {});
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${dir}/W45908_after_phone-390.png`, fullPage: true }).catch(() => {});

  return out;
}
