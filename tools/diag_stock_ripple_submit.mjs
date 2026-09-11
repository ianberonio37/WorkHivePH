// diag_stock_ripple_submit.mjs — WHY does prove_stock_ripple's UI submit sometimes write nothing?
// Same identity, hive, staging and modal drive as the prover, but the submit is INSTRUMENTED:
// what covers the button at click time, what the page logs, which responses fail, and what the
// inventory_deduct RPC actually returned. Cleans up its own probe row and restores qty + min_qty
// EXPLICITLY (the ledger trigger is INSERT-only, so deleting the row never re-syncs qty).
import { chromium } from 'playwright'; import { execFileSync } from 'child_process';
const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };
const JOB_REF = 'WH-T11-DIAG submit';
const psql = (sql) => execFileSync('docker', ['exec','supabase_db_workhive','psql','-U','postgres','-d','postgres','-t','-A','-c', sql], { encoding:'utf8' }).trim();
const row = psql(`SELECT id||'|'||qty_on_hand||'|'||min_qty FROM inventory_items WHERE hive_id='${HIVE.id}' AND qty_on_hand > 1 AND qty_on_hand > min_qty ORDER BY qty_on_hand DESC LIMIT 1`);
const [PART_ID, ORIG_QTY, ORIG_MIN] = row.split('|'); const STAGE_MIN = Number(ORIG_QTY) - 1;
console.log('part', PART_ID, 'qty', ORIG_QTY, 'min', ORIG_MIN, '-> stage min', STAGE_MIN);
psql(`UPDATE inventory_items SET min_qty=${STAGE_MIN} WHERE id='${PART_ID}'`);
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } }); const page = await ctx.newPage();
  const log = []; page.on('console', m => { if (['error','warning'].includes(m.type())) log.push(m.type()+': '+m.text().slice(0,160)); });
  page.on('pageerror', e => log.push('pageerror: '+String(e).slice(0,160)));
  const rpc = []; page.on('response', async r => { const u=r.url(); if (u.includes('inventory_deduct') || (u.includes('/rest/v1/') && r.status()>=400) || (u.includes('/functions/v1/') && r.status()>=400)) { let body=''; try { body=(await r.text()).slice(0,200); } catch(_){} rpc.push(`${r.status()} ${u.replace(/^https?:\/\/[^/]+/,'').slice(0,80)} :: ${body}`); } });
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil:'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout:25000 });
  const s = await page.evaluate(async ({email,password,worker,hive}) => { const db=(typeof getDb==='function')?getDb():window.db; const { error } = await db.auth.signInWithPassword({ email, password }); if (error) return { ok:false, err:error.message };
    localStorage.setItem('wh_worker_name',worker); localStorage.setItem('wh_last_worker',worker); localStorage.setItem('wh_active_hive_id',hive.id); localStorage.setItem('wh_hive_id',hive.id); localStorage.setItem('wh_hive_name',hive.name); localStorage.setItem('wh_hive_role','worker'); return { ok:true }; }, { email:ACCT.email, password:ACCT.pw, worker:ACCT.worker, hive:HIVE });
  console.log('sign-in', JSON.stringify(s));
  await page.goto(`${SEEDER}/inventory.html`, { waitUntil:'domcontentloaded' });
  await page.waitForFunction(() => typeof window.openUseModal === 'function', { timeout:25000 });
  const t0=Date.now(); let known=false;
  while (Date.now()-t0 < 20000) { known = await page.evaluate((id) => { try { return !!(typeof loadInventory==='function' && loadInventory().find(i=>i.id===id)); } catch(_) { return false; } }, PART_ID); if (known) break; await page.waitForTimeout(700); }
  console.log('part known to loadInventory():', known, 'after', Date.now()-t0, 'ms');
  await page.evaluate((id) => openUseModal(id), PART_ID);
  const modalVisible = await page.waitForSelector('#use-modal', { state:'visible', timeout:10000 }).then(()=>true).catch(()=>false);
  await page.fill('#use-qty', '1'); await page.fill('#use-job-ref', JOB_REF);
  const pre = await page.evaluate(() => { const b=document.getElementById('use-submit-btn'); if(!b) return {btn:false}; const r=b.getBoundingClientRect(); const cx=r.x+r.width/2, cy=r.y+r.height/2; const top=document.elementFromPoint(cx,cy); const cs=getComputedStyle(b);
    return { btn:true, disabled:b.disabled, rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)], inViewport: cy>=0 && cy<=innerHeight, display:cs.display, visibility:cs.visibility, pointerEvents:cs.pointerEvents, topAtCenter: top ? (top.tagName+(top.id?'#'+top.id:'')+(typeof top.className==='string'&&top.className?'.'+top.className.split(' ').slice(0,2).join('.'):'')) : null, coveredByOther: !!(top && top!==b && !b.contains(top)), qty: document.getElementById('use-qty')?.value, job: document.getElementById('use-job-ref')?.value, requiredEmpty: [...document.querySelectorAll('#use-modal [required]')].filter(e=>!e.value).map(e=>e.id||e.name) }; });
  console.log('modal visible', modalVisible, '| submit btn', JSON.stringify(pre));
  await page.click('#use-submit-btn', { timeout: 5000 }).then(()=>console.log('click: dispatched')).catch(e=>console.log('click FAILED:', String(e).slice(0,160)));
  const tD=Date.now(); let n='0';
  while (Date.now()-tD < 20000) { n = psql(`SELECT count(*) FROM inventory_transactions WHERE item_id='${PART_ID}' AND job_ref LIKE '%WH-T11-DIAG%'`); if (n==='1') break; await page.waitForTimeout(700); }
  console.log('tx rows after submit:', n, 'in', Date.now()-tD, 'ms | modal still visible:', await page.isVisible('#use-modal').catch(()=>null));
  console.log('rpc/failed responses:', JSON.stringify(rpc.slice(0,6)));
  console.log('console/page errors:', JSON.stringify(log.slice(0,6)));
  await ctx.close();
} finally {
  psql(`DELETE FROM inventory_transactions WHERE item_id='${PART_ID}' AND job_ref LIKE '%WH-T11-DIAG%'`);
  psql(`UPDATE inventory_items SET min_qty=${ORIG_MIN}, qty_on_hand=${ORIG_QTY} WHERE id='${PART_ID}'`);
  console.log('cleanup ->', psql(`SELECT qty_on_hand||'/'||min_qty FROM inventory_items WHERE id='${PART_ID}'`), '| probe rows', psql(`SELECT count(*) FROM inventory_transactions WHERE item_id='${PART_ID}' AND job_ref LIKE '%WH-T11-DIAG%'`));
  await browser.close();
}
