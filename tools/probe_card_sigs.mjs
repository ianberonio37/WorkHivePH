import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY } from './prover_harness.mjs';
const pages = process.argv.slice(2);
const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' }); await signIn(ctx);
for (const f of pages) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${f}${PAGE_QUERY[f] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(6000);
  const r = await p.evaluate(() => {
    const vis = (e) => e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const g = {};
    for (const c of [...document.querySelectorAll('.simple-card')].filter(vis)) { const s = getComputedStyle(c); const k = `${s.borderRadius}|${s.padding}`; (g[k] ||= []).push((c.id ? '#' + c.id : '') + '.' + [...c.classList].join('.') + ' <' + (c.parentElement.id ? '#' + c.parentElement.id : c.parentElement.className.toString().slice(0, 30)) + '>'); }
    return Object.entries(g).map(([k, v]) => `${k}: n=${v.length} e.g. ${v.slice(0, 3).join(' ; ')}`);
  });
  console.log(f); r.forEach((l) => console.log('   ' + l.slice(0, 220)));
  await p.close();
}
await b.close();
