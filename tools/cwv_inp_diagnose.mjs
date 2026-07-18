// tools/cwv_inp_diagnose.mjs — close the loop on the INP question: measure the MEANINGFUL
// interactions the page-responsiveness H1 click never exercised — the landing catalog popup
// (openAllToolsPopup innerHTML render, the richest interaction) and a FAQ <summary> toggle —
// on a SETTLED page (networkidle + 2.5s). If these are <200ms the INP cell is genuinely green;
// if slow, it's a real finding (NOT a measurement artifact).
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5000';
const VIEWPORT = { width: 390, height: 780 };

function INIT() {
  window.__inp = { max: 0, target: null, phases: null };
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.interactionId > 0 && e.duration > window.__inp.max) {
          const t = e.target;
          window.__inp.max = e.duration;
          window.__inp.target = t && t.tagName ? `${t.tagName}${t.id ? '#' + t.id : ''}` : 'doc-level';
          window.__inp.phases = {
            inputDelay: Math.round(e.processingStart - e.startTime),
            processing: Math.round(e.processingEnd - e.processingStart),
            presentation: Math.round(e.startTime + e.duration - e.processingEnd),
          };
        }
      }
    }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
  } catch (e) { /* unsupported */ }
}

async function settle(page) {
  try { await page.waitForLoadState('networkidle', { timeout: 3000 }); } catch (e) { /* ok */ }
  await page.waitForTimeout(2500);
}
function report(label, inp) {
  const ph = inp.phases ? `input ${inp.phases.inputDelay} + proc ${inp.phases.processing} + present ${inp.phases.presentation}` : '-';
  const flag = !inp.max ? 'unmeasured' : (inp.max > 200 ? `\x1b[91m${Math.round(inp.max)}ms OVER\x1b[0m` : `\x1b[92m${Math.round(inp.max)}ms\x1b[0m`);
  console.log(`  ${label}: INP=${flag} (${ph}) target=${inp.target || '-'}`);
}

const browser = await chromium.launch({ headless: true });

// 1) index.html — the catalog popup (richest interaction) + a FAQ summary
{
  const ctx = await browser.newContext({ viewport: VIEWPORT, isMobile: true, hasTouch: true });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  await page.goto(BASE + '/workhive/', { waitUntil: 'load', timeout: 30000 });
  await settle(page);
  console.log('=== index.html — catalog popup (openAllToolsPopup) ===');
  const popup = await page.evaluate(() => {
    const el = Array.from(document.querySelectorAll('[onclick]')).find((e) => /openAllToolsPopup|openStagePopup/.test(e.getAttribute('onclick') || ''));
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, desc: (el.getAttribute('onclick') || '').slice(0, 40), text: (el.textContent || '').trim().slice(0, 30) };
  });
  if (popup) {
    console.log(`  trigger: "${popup.text}" onclick=${popup.desc}`);
    await page.mouse.click(popup.x, popup.y);
    await page.waitForTimeout(1000);
    report('popup render', await page.evaluate(() => window.__inp));
  } else { console.log('  (no popup trigger found in DOM)'); }
  await page.close(); await ctx.close();
}

// 2) a content article — FAQ <summary> toggle (the real article interaction)
{
  const ctx = await browser.newContext({ viewport: VIEWPORT, isMobile: true, hasTouch: true });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  await page.goto(BASE + '/workhive/learn/power-plant-reliability-metrics-philippines/', { waitUntil: 'load', timeout: 30000 });
  await settle(page);
  console.log('\n=== power-plant-reliability — FAQ <summary> toggle ===');
  const sum = await page.evaluate(() => {
    const el = document.querySelector('summary, button');
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, tag: el.tagName, text: (el.textContent || '').trim().slice(0, 30) };
  });
  if (sum) {
    console.log(`  trigger: <${sum.tag}> "${sum.text}"`);
    await page.mouse.click(sum.x, sum.y);
    await page.waitForTimeout(1000);
    report('summary toggle', await page.evaluate(() => window.__inp));
  } else { console.log('  (no summary/button found)'); }
  await page.close(); await ctx.close();
}

await browser.close();
