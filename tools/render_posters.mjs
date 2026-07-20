/* Render WorkHive promo posters to PNG via puppeteer.
   Self-serving static server (repo root) so relative asset paths resolve.

   Usage:
     node tools/render_posters.mjs                 # render all -> promo_posters/_out
     node tools/render_posters.mjs v1 v3           # render a subset
     node tools/render_posters.mjs --desktop       # render all -> Desktop\WorkHive Promo Posters
     node tools/render_posters.mjs beetest         # render the mascot test card
*/
import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import puppeteer from 'puppeteer';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const PORT = 3111;

const MIME = { '.html':'text/html','.css':'text/css','.js':'application/javascript',
  '.mjs':'application/javascript','.json':'application/json','.png':'image/png',
  '.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml','.ico':'image/x-icon',
  '.woff':'font/woff','.woff2':'font/woff2' };

// name -> {file (relative to root), w, h, out}
const POSTERS = {
  beetest: { file: 'promo_posters/_beetest.html', w: 900, h: 900, out: 'workhive-beetest.png' },
  contact: { file: 'promo_posters/_contact.html', w: 1600, h: 1700, out: 'workhive-promo-0-ALL-overview.png' },
  v1: { file: 'promo_posters/poster-v1.html', w: 1600, h: 900, out: 'workhive-promo-1-companion-hero.png' },
  v2: { file: 'promo_posters/poster-v2.html', w: 1600, h: 900, out: 'workhive-promo-2-hive-connects.png' },
  v3: { file: 'promo_posters/poster-v3.html', w: 1600, h: 900, out: 'workhive-promo-3-mascot-spotlight.png' },
  v4: { file: 'promo_posters/poster-v4.html', w: 1600, h: 900, out: 'workhive-promo-4-command-center.png' },
  v5: { file: 'promo_posters/poster-v5.html', w: 1600, h: 900, out: 'workhive-promo-5-swarm-momentum.png' },
};

const args = process.argv.slice(2);
const toDesktop = args.includes('--desktop');
const picks = args.filter(a => !a.startsWith('--'));
const targets = picks.length ? picks.filter(p => POSTERS[p]) : Object.keys(POSTERS).filter(k => k !== 'beetest');

const OUT_DIR = toDesktop
  ? path.join(os.homedir(), 'Desktop', 'WorkHive Promo Posters')
  : path.join(ROOT, 'promo_posters', '_out');
fs.mkdirSync(OUT_DIR, { recursive: true });

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  const fp = path.join(ROOT, p);
  fs.readFile(fp, (err, data) => {
    if (err) { res.writeHead(404); res.end('404 ' + p); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(fp).toLowerCase()] || 'application/octet-stream' });
    res.end(data);
  });
});

await new Promise(r => server.listen(PORT, r));
const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--force-color-profile=srgb'] });

for (const name of targets) {
  const spec = POSTERS[name];
  const page = await browser.newPage();
  await page.setViewport({ width: spec.w, height: spec.h, deviceScaleFactor: 2 });
  await page.goto(`http://127.0.0.1:${PORT}/${spec.file}`, { waitUntil: 'networkidle2', timeout: 45000 });
  try { await page.evaluate(() => document.fonts.ready); } catch {}
  await new Promise(r => setTimeout(r, 700));
  const el = await page.$('#poster');
  const outPath = path.join(OUT_DIR, spec.out);
  if (el) await el.screenshot({ path: outPath });
  else await page.screenshot({ path: outPath });
  console.log(`  ✓ ${name.padEnd(8)} -> ${outPath}`);
  await page.close();
}

await browser.close();
server.close();
console.log(`Done. Output: ${OUT_DIR}`);
