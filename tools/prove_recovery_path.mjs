// prove_recovery_path — the EX-RV wave: "I deleted the wrong thing" (2026-09-07).
//
// One row per rostered destructive control (substrate/reference/destructive_control_registry.json),
// each a contract: after pressing it by mistake, the platform must offer the way back AND the way back
// must WORK. That is two halves, and prove_destructive_sweep (T50) already proves the first - a confirm
// or an undo intervenes. This wave proves the second on the roster's own list: the undo, once pressed,
// puts the row back where a person would see it.
//
//   R1 offered      the control is guarded: a confirm to cancel, or an undo to press (T50's D2, per row)
//   R2 reachable    the way back can actually be pressed by this sweep - an undo nobody can reach is decoration
//   R3 restores     pressing it brings the LIVE row count back to what it was - counted as a person sees
//                   it, because count(*) is blind to a soft delete (this file's own lesson from T50)
//
// ★THE ROSTER IS THE SOURCE OF TRUTH, AND IT IS READ, NOT REMEMBERED. Each registry entry is a file and
// the first words of its confirm message; the sweep finds the control by pressing every distinct
// destructive label on the page and matching what the confirm SAID against the roster's message_head.
// A rostered control the sweep cannot bring on screen is reported NOT REACHED, never clean.
//
//   node tools/prove_recovery_path.mjs
//   node tools/prove_recovery_path.mjs --page community.html
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS, HIVE } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

// the roster, grouped by page: [{page, heads: [message_head...]}]
const ROSTER = (() => {
  const d = JSON.parse(readFileSync('substrate/reference/destructive_control_registry.json', 'utf8'));
  const out = {};
  for (const [path, items] of Object.entries(d.controls || {})) {
    const page = path.split('/').pop();
    if (!page.endsWith('.html') || path.includes('/')) continue;      // root pages only, as the wave seeded
    out[page] = (items || []).map((c) => String(c.message_head || '').replace(/\\$/, '').trim()).filter(Boolean);
  }
  return out;
})();

// live rows as a PERSON sees them: soft-deleted rows are gone to them and present to count(*)
const SOFT = new Set(psql("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname='deleted_at' and not a.attisdropped where n.nspname='public' and c.relkind='r'").split('\n').map((s) => s.trim()).filter(Boolean));
const WATCH = ['logbook', 'community_posts', 'inventory_items', 'pm_assets', 'marketplace_listings', 'pm_scope_items', 'project_items', 'report_contacts', 'asset_nodes'];
const census = () => Object.fromEntries(WATCH.map((t) => [t, psql(`select count(*) from public."${t}" where hive_id = '${HIVE}'${SOFT.has(t) ? ' and deleted_at is null' : ''}`) || '?']));

// ★A ROSTERED CONTROL IS REACHED THE WAY ITS PERSON REACHES IT (2026-09-07). The first sweep pressed every
// visible delete-ish label and reported 53/53 "not brought on screen": the controls live behind a menu
// (hive's danger items), inside a modal (dayplanner's item), in an open thread (community's copy-link),
// in a 360 view (Asset Brain's FMEA / RCM), on a tab (integrations' API keys). Each entry below is the
// path, authored from the page's source: `steps` are clicked in order, then `trigger` is pressed and the
// confirm / undo that appears is judged exactly as before. `heads` names the roster entries the path
// answers - a post-action message ("Your account has been deactivated…") rides the confirm before it.
const REACH = {
  'hive.html': [
    { steps: ['#btn-hive-menu'], trigger: '#btn-deactivate-account', heads: ['Deactivate your account?', 'Your account has been deactivated'] },
    { steps: ['#btn-hive-menu'], trigger: '#btn-leave-hive', heads: ["Leave this hive? You'll lose access", '${_coSups[0]}'] },
    { steps: [], trigger: 'button[onclick^="resetMemberPassword"]', heads: ["Reset ${workerName}'s password?", 'Temporary password for'] },
    { steps: [], trigger: 'button[data-i="reject"][onclick^="rejectItem"]', heads: ['Reject "${label}" submitted by'] },
  ],
  'community.html': [
    { steps: ['button[onclick^="openThread"]'], trigger: 'button[onclick="copyThreadLink()"]', heads: ['Copy this link:'] },
  ],
  'dayplanner.html': [
    // the harness worker has nothing scheduled, so the item is seeded for the walk and removed after it - a
    // probe's setup write, confirmed by the RETURNING id and reversed by the cleanup whatever the walk did
    // the page's own vocabulary: date is TEXT in the Manila day, status is the canonical 'pending', times HH:MM
    { prep: "insert into schedule_items (id, worker_name, auth_uid, title, date, start_time, end_time, item_status, category) values (gen_random_uuid(), 'Leandro Marquez', (select id from auth.users where email='leandromarquez@auth.workhiveph.com'), 'RV probe item (delete me)', to_char(now() at time zone 'Asia/Manila', 'YYYY-MM-DD'), '09:00', '10:00', 'pending', 'Other') returning id",
      cleanup: "delete from schedule_items where id = '{id}'",
      steps: ['[onclick*="openEditModal"]'], trigger: '#m-delete-btn', heads: ['Remove this scheduled item?'] },
  ],
  'asset-hub.html': [
    { steps: [], trigger: 'button[data-action="asset-reject"]', heads: ['Reject this asset? It stays in the queue'] },
    // BLR-001 carries 4 FMEA modes and 2 RCM strategies in the seeded hive - its card, not the first card
    // …and the workbench that lists them is collapsed behind "Show Reliability Workbench (engineer view)"
    { steps: ['text=^BLR-001', 'js:(function(){const t=document.querySelector("[aria-controls=\\"reliability-card\\"]");if(t&&t.getAttribute("aria-expanded")!=="true")t.click();})()'], trigger: '#rel-panel-fmea [data-action="delete"]', heads: ['Delete this FMEA failure mode?'] },
    // the strategy strips arrive after the modes (a second fetch): two idle steps give them the seconds they need
    { steps: ['text=^BLR-001', 'js:(function(){const t=document.querySelector("[aria-controls=\\"reliability-card\\"]");if(t&&t.getAttribute("aria-expanded")!=="true")t.click();})()', 'js:void 0', 'js:void 0'], trigger: '#rel-panel-fmea [data-action="strat-delete"]', heads: ['Delete this RCM strategy?'] },
  ],
  'alert-hub.html': [
    { steps: [], trigger: '#amc-reject-btn', heads: ['Reject today'] },
  ],
  'founder-console.html': [
    { steps: [], trigger: 'button[onclick*="svcTopupDecide"][onclick*="false"]', heads: ['Reject this top-up?'] },
    // the mint confirm comes after the form validates: a code, a kind and a value are filled the way a person would
    { steps: ["js:(function(){const g=(i)=>document.getElementById(i);g('vm-code').value='RVPROBE1';const k=g('vm-kind');if(k&&k.options.length>1&&!k.value)k.selectedIndex=1;g('vm-value').value='10';})()"], trigger: 'button[onclick="svcMintVoucher()"]', heads: ['Mint voucher'] },
    // the listing-moderation reject is its own control (wireMktModeration, delegated data-mkt-act), not the top-up reject
    { steps: [], trigger: '#sec-mkt-mod button[data-mkt-act="reject-listing"]', heads: ['Reject this listing. Tell the seller'] },
  ],
  'index.html': [
    // the signed-in person's menu (avatar -> user-menu) carries "Deactivate account"; the confirm is Cancelled here -
    // the RPC anonymizes the harness worker for good, so the way back is proven by declining, not by undoing.
    { steps: ['js:(()=>{let n=document.getElementById("user-menu");while(n&&n!==document.body){n.classList.remove("hidden");if(getComputedStyle(n).display==="none")n.style.display="block";n=n.parentElement;}})()'], trigger: '#user-menu button[onclick="deactivateAccount()"]', heads: ['Deactivate your account?', 'Your account has been deactivated'] },
    { steps: [], trigger: 'button[onclick="forgotPassword(event)"]', heads: ['Enter the email on your account', 'Could not send the reset link', 'Set a new password (at least 8', 'Password must be at least 8'] },
    // the sign-in form: a signed-out person's control - the consent banner is answered first, then "Sign In" by its words
    { anon: true, steps: ['#wh-consent button', 'js:openSignIn(new Event("click"))'], trigger: '#si-sso-btn', heads: ['Enter your company email domain'] },
  ],
  'integrations.html': [
    // the wizard creates a vehicle (asset + PM schedule + starter parts), then offers "Undo - remove everything just
    // created". The confirm is ACCEPTED here: the undo is the way back, and the census proves it put everything back.
    { accept: true,
      steps: ['#veh-open', '#veh-preset-ranger', 'text=^Next: service schedule', 'text=^Next: starter parts', '#veh-create', 'js:void 0', 'js:void 0', 'js:void 0'],
      trigger: 'text=^Undo - remove everything', heads: ['Remove everything this wizard just created'] },
    { prep: "insert into api_keys (hive_id, key_prefix, key_hash, label, enabled) values ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 'rvprobe', 'rvprobe-hash-not-a-key', 'RV probe key (delete me)', true) returning id", cleanup: "delete from api_keys where id = '{id}'", steps: ['#tab-api'], trigger: 'button[onclick^="revokeKey"]', heads: ['Revoke this API key?'] },
    // the import history lists batches from cmms_audit_log within 24 h - one is seeded for the walk and removed after
    { prep: "insert into cmms_audit_log (hive_id, batch_id, operation, entity_type, system_type, rows_attempted, rows_written, triggered_by) values ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 'rvprobe-batch-delete-me', 'file_import', 'work_orders', 'generic', 1, 1, 'Leandro Marquez') returning id",
      cleanup: "delete from cmms_audit_log where id = '{id}'",
      steps: ['#tab-import'], trigger: 'button[onclick^="rollbackBatch"]', heads: ['Undo this import?'] },
  ],
  'inventory.html': [
    { steps: ['button[onclick^="openDetailModal"]'], trigger: 'button[onclick^="confirmDeleteItem"]', heads: ['Remove "${item.part_name}"'] },
    // the "staged for an asset" guard on Use stock: a reservation is seeded on a known approved part and removed after
    { prep: "insert into parts_staged_reservations (hive_id, asset_name, item_id, qty_reserved, reserved_by, notes) values ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 'RV probe asset', 'inv-65e6c3991b3e', 1, 'Leandro Marquez', 'RV probe (delete me)') returning id",
      cleanup: "delete from parts_staged_reservations where id = '{id}'",
      steps: ["button[onclick=\"openUseModal('inv-65e6c3991b3e')\"]"], trigger: '#use-submit-btn', heads: ['${_uResv} ${_uUnit} of this part is stag'] },
  ],
  'logbook.html': [
    // the registry list lives in the asset modal's "manage" view (openAssetModal(tab)); the button opens "register"
    { steps: ['#open-asset-modal-btn', 'js:openAssetModal("manage")'], trigger: 'button[onclick^="deleteAsset"]', heads: ['Remove this asset from the registry?'] },
    // an entry's Delete lives in its modal (openModal on the row); the button shows only on the person's own entry
    { steps: ['text=^My Entries', '[onclick^="openModal"]'], trigger: 'button[onclick^="confirmDelete"]', heads: ['Delete this entry? This cannot be undone'] },
  ],
  'marketplace-admin.html': [
    // each queue is a tab (#tab-published / #tab-sellers / #tab-disputes); the buttons are delegated data-action
    { steps: ['#tab-published'], trigger: 'button[data-action="unpublish"]', heads: ['${_verb} "${(listing'] },
    { steps: ['#tab-sellers'], trigger: 'button[data-action="unverify"], button[data-action="cert-unverify"]', heads: ["Remove ${workerName}'s ${noun}?"] },
    // an open dispute is seeded so the queue has one to resolve, and removed after
    { prep: "insert into marketplace_disputes (opened_by, seller_name, reason, description, status) values ('Wilfredo Malabanan', 'Leandro Marquez', 'RV probe dispute (delete me)', 'probe', 'open') returning id",
      cleanup: "delete from marketplace_disputes where id = '{id}'",
      steps: ['#tab-disputes'], trigger: 'button[data-action="refund"], button[data-action="release"], button[data-action="escalate"]', heads: ['${verb} for this dispute?'] },
  ],
  'marketplace-seller.html': [
    // Delete shows only on a DRAFT listing; one is seeded for the harness worker and removed after
    { prep: "insert into marketplace_listings (hive_id, seller_name, section, category, title, description, price, status) values ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 'Leandro Marquez', 'parts', 'Other', 'RV probe draft listing (delete me)', 'probe', 1, 'draft') returning id",
      cleanup: "delete from marketplace_listings where id = '{id}'",
      steps: [], trigger: 'button[data-action="delete"]', heads: ['Delete "${item.title}"?'] },
    // the harness worker is not a provider: a freelancer profile and an accepted job are seeded together and removed together
    { prep: "with p as (insert into service_providers (provider_type, auth_uid, worker_name, hive_id, display_name, contact, categories, availability) values ('freelancer', (select id from auth.users where email='leandromarquez@auth.workhiveph.com'), 'Leandro Marquez', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'RV probe provider (delete me)', 'probe', array['electrical'], 'on_job') returning id), r as (insert into service_requests (client_auth_uid, client_worker_name, hive_id, mode, custom_scope, address, status, matched_provider_id) select (select id from auth.users where email='wilfredomalabanan@auth.workhiveph.com'), 'Wilfredo Malabanan', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'instant', 'RV probe job (delete me)', 'RV probe site', 'accepted', p.id from p returning id) select id from r",
      cleanup: "with r as (delete from service_requests where id = '{id}' returning matched_provider_id) delete from service_providers where id in (select matched_provider_id from r)",
      steps: ['text=^Services'], trigger: 'button[onclick*="svcCancelJob"]', heads: ['Cancel this job?'] },
  ],
  'marketplace.html': [
    { prep: "insert into service_requests (client_auth_uid, client_worker_name, hive_id, mode, custom_scope, status) values ((select id from auth.users where email='leandromarquez@auth.workhiveph.com'), 'Leandro Marquez', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'instant', 'RV probe request (delete me)', 'completed') returning id", cleanup: "delete from service_requests where id = '{id}'", steps: ['text=^Services'], trigger: 'button[onclick^="svcRaiseObjection"]', heads: ['What went wrong with this job?', 'Cancel this request?'] },
    // "already hailed at the same address": an open request at that address is seeded, then the person hails again there
    // the duplicate check is catalog item + address + status broadcasting within ten minutes - the seed matches all three
    { prep: "insert into service_requests (client_auth_uid, client_worker_name, hive_id, mode, catalog_item_id, address, status) values ((select id from auth.users where email='leandromarquez@auth.workhiveph.com'), 'Leandro Marquez', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'instant', '54aa11ba-ecf8-4ff8-9df8-cd403cae28b6', 'RV probe site, Baguio', 'broadcasting') returning id",
      cleanup: "delete from service_requests where id = '{id}'",
      steps: ['js:(function(){const s=document.getElementById("svc-hail-item");if(s){s.value="54aa11ba-ecf8-4ff8-9df8-cd403cae28b6";s.dispatchEvent(new Event("change",{bubbles:true}));}const a=document.getElementById("svc-hail-address");if(a){a.value="RV probe site, Baguio";a.dispatchEvent(new Event("input",{bubbles:true}));}})()'],
      trigger: '#svc-hail-go', heads: ['You already hailed this'] },
    { prep: "insert into marketplace_saved_searches (worker_name, search_name, section, query_text, active) values ('Leandro Marquez', 'RV probe search', 'parts', 'probe', true) returning id", cleanup: "delete from marketplace_saved_searches where id = '{id}'", steps: ['#btn-saved-searches'], trigger: '.btn-delete-search', heads: ['Delete this saved search?'] },
  ],
  'pm-scheduler.html': [
    { steps: ['.asset-card'], trigger: '#det-autohail-btn', heads: ['Auto-hail this asset'] },
    { steps: ['.asset-card'], trigger: '#btn-delete-asset', heads: ['Delete "${currentAsset.asset_name}"?'] },
    // the duplicate-name guard: open Add Asset, type a name the hive already has, press Next - the person's own path
    { steps: ['text=^Add Asset', 'js:(function(){const e=document.getElementById("w-name");e.value="Siemens Simotics SD 200L";e.dispatchEvent(new Event("input",{bubbles:true}));})()'],
      trigger: 'button[onclick="goStep(2)"]', heads: ['"${name}" is already registered as'] },
  ],
  'project-manager.html': [
    { steps: ['.pcard'], trigger: 'button[onclick="deleteProject()"]', heads: ['Hide project'] },
    // the wizard's empty-scope guard: New project -> a type -> a template -> every scope item unticked -> Create
    // (a tile or a card selects; "Next →" advances - the wizard's own rhythm, probed on 2026-09-07)
    { steps: ['button[onclick="openNewProject()"]', '.type-tile[data-type="shutdown"]', 'text=^Next', '.template-card', 'text=^Next', 'js:_wizardState.items.forEach(function(i){i._checked=false})'],
      trigger: '#wiz-create', heads: ['No scope items checked. Create an empty'] },
    // each control lives on its own detail pane (#detail-tabs button[data-pane=…]); the panes render from data
    { steps: ['.pcard', '#detail-tabs button[data-pane="linked"]'], trigger: 'button[onclick^="removeLink"]', heads: ['Remove this link?'] },
    { steps: ['.pcard', '#detail-tabs button[data-pane="roles"]'], trigger: 'button[onclick^="removeRole"]', heads: ['Remove this role?'] },
    // a pending change order is seeded on the active Baguio project and that project is opened by its name
    { prep: "insert into project_change_orders (project_id, hive_id, co_number, title, scope_change, reason, requested_by, status) values ('539e0d9a-9ff7-474b-ab03-9254406ca7dc', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'RV-PROBE', 'RV probe change order', 'probe scope', 'probe', 'Leandro Marquez', 'pending') returning id", cleanup: "delete from project_change_orders where id = '{id}'", steps: ['text=Centrifugal Pump Annual Overhaul', '#detail-tabs button[data-pane="changes"]'], trigger: 'button[onclick^="approveCO"]', heads: ['Approve this change order?'] },
    { prep: "insert into project_change_orders (project_id, hive_id, co_number, title, scope_change, reason, requested_by, status) values ('539e0d9a-9ff7-474b-ab03-9254406ca7dc', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'RV-PROBE', 'RV probe change order', 'probe scope', 'probe', 'Leandro Marquez', 'pending') returning id", cleanup: "delete from project_change_orders where id = '{id}'", steps: ['text=Centrifugal Pump Annual Overhaul', '#detail-tabs button[data-pane="changes"]'], trigger: 'button[onclick^="rejectCO"]', heads: ['Reason for rejection'] },
    { prep: "insert into project_change_orders (project_id, hive_id, co_number, title, scope_change, reason, requested_by, status) values ('539e0d9a-9ff7-474b-ab03-9254406ca7dc', '084c113b-99c0-45c6-a8e8-b4b8349da46d', 'RV-PROBE', 'RV probe change order', 'probe scope', 'probe', 'Leandro Marquez', 'pending') returning id", cleanup: "delete from project_change_orders where id = '{id}'", steps: ['text=Centrifugal Pump Annual Overhaul', '#detail-tabs button[data-pane="changes"]'], trigger: 'button[onclick^="cancelCO"]', heads: ['Cancel this change order?'] },
    { steps: ['.pcard', '#detail-tabs button[data-pane="signoff"]'], trigger: 'button[onclick="markComplete()"]', heads: ['Mark project as complete?'] },
  ],
  'report-sender.html': [
    { steps: [], trigger: 'button[data-del]', heads: ['Remove ${_c && _c.name'] },
    // the outsider confirm: pick a report chip, type an address outside the hive, press Send - the person's sequence
    { steps: ['#chips-grid .chip', 'js:(function(){const e=document.getElementById("email-input");e.value="outsider.rvprobe@example.com";e.dispatchEvent(new Event("input",{bubbles:true}));e.dispatchEvent(new Event("change",{bubbles:true}));})()'],
      trigger: '#send-btn', heads: ['Send this report to ${_who}?'] },
  ],
  'shift-brain.html': [
    { steps: [], trigger: 'text=^Archive', heads: ['Archive this shift plan?'] },
  ],
  'platform-actions.html': [
    // the publish confirm only fires when the "public" box is ticked before Save - the person's own sequence
    { steps: ['.fb-card', '#fb-d-public'], trigger: '#fb-d-save', heads: ['Publish this feedback to the PUBLIC'] },
    // moderation buttons are delegated on #sec-mkt-mod by data-mkt-act; a pending listing must exist to show one
    { steps: [], trigger: '#sec-mkt-mod button[data-mkt-act="reject-listing"]', heads: ['Reject this listing. Tell the seller'] },
  ],
};
// a template head ("Reset ${workerName}'s password?") matches on its static words
// an UNCLOSED template (the roster truncates heads mid-expression: "Remove ${_c && _c.name ? _c.name : 'this") is
// stripped to its end, so a path's shorter head and the roster's longer one reduce to the same static words
const headKey = (h) => String(h || '').replace(/\$\{[^}]*(\}|$)/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
const headMatches = (head, said) => {
  const k = headKey(head); const t = String(said || '').toLowerCase().replace(/\s+/g, ' ');
  if (!k) return false;
  const words = k.split(' ').filter((w) => w.length > 2).slice(0, 4).join(' ');
  return words.length >= 6 ? t.includes(words) : t.startsWith(k.slice(0, Math.min(18, k.length)));
};

const b = await chromium.launch();
let bad = 0, rowsChecked = 0;
const notReached = [];
for (const [file, heads] of Object.entries(ROSTER)) {
  if (ONLY && file !== ONLY) continue;
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  let dialogs = 0, lastDialog = '';
  p.on('dialog', async (d) => { dialogs++; lastDialog = d.message(); await d.dismiss().catch(() => {}); });   // always cancel a native dialog
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  // open the menus destructive controls hide behind
  // buttons only: an <a aria-label="menu"> navigates, and every read after that failed silently (modals 0->0)
  for (const trig of (process.env.RV_NO_PRECLICK ? [] : await p.$$('button[aria-haspopup], button[aria-label*="more" i], button[aria-label*="menu" i], button[aria-label*="options" i]'))) {
    await trig.click({ timeout: 800 }).catch(() => {});
  }
  await p.waitForTimeout(600);
  if (!p.url().includes(file)) {   // a pre-click navigated away - come back, or every verdict below is about the wrong page
    await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
  }

  // one press per DISTINCT destructive label (a feed repeats the same button per card)
  const labels = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const seen = new Set(); const out = [];
    for (const e of document.querySelectorAll('button, [role="button"], [role="menuitem"], a')) {
      const t = (e.innerText || e.getAttribute('aria-label') || '').trim();
      if (!t || !vis(e) || e.disabled) continue;
      if (!/^(delete|remove|reject|clear|discard|revoke|unpublish|kick|deactivate|archive|reset|withdraw|cancel (order|listing|request)|leave hive|end |wipe)/i.test(t)) continue;
      if (seen.has(t)) continue;
      seen.add(t); out.push(t);
    }
    return out;
  }, VIS_JS).catch(() => []);

  const matched = new Map();   // roster head -> verdict
  // ★A PROVEN HEAD IS NEVER PRESSED AGAIN (2026-09-07). The generic sweep pressed "Reject" on alert-hub, saw the
  // confirm, matched the head - then the authored path pressed the same button into a page still holding that
  // confirm, got nothing, and its BAD verdict overwrote the good one. Authored paths go first, and any target
  // whose heads are already proven is skipped.
  const targets = [...(REACH[file] || []), ...labels];
  for (const label of targets) {
    if (typeof label === 'object' && label.heads.every((lh) => [...matched.entries()].some(([h, v]) => v.offered && (headKey(h) === headKey(lh) || headKey(h).startsWith(headKey(lh).slice(0, 16)))))) continue;
    const before = census();
    const dlgBefore = dialogs;
    // ★COUNT BEFORE AND AFTER WITH THE SAME EYES (2026-09-07). This counted EVERY dialog before the press (six
    // transform-closed sheets on marketplace, hidden sheets everywhere) and only VISIBLE ones after, so a real
    // confirm overlay never out-counted the baseline and 53 controls read "fired with no confirm" while the
    // probe showed the confirm on screen. Same visibility filter on both sides.
    const modalsBefore = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      return [...document.querySelectorAll('[id^="wh-modal-ov-"], [role="dialog"]')].filter(vis).length;
    }, VIS_JS).catch(() => 0);
    if (typeof label === 'object') {
      if (process.env.RV_DEBUG) console.log(`        (path -> ${label.trigger} via ${label.steps.length} step(s))`);
      if (label.prep) {
        label._id = psql(label.prep).split('\n')[0].trim();
        if (!label._id) { console.log(`        (prep write did not land for "${label.heads[0]}" - control left NOT REACHED)`); continue; }
        await p.reload({ waitUntil: 'load' }).catch(() => {}); await p.waitForTimeout(SETTLE_MS);
      }
      // ★EVERY AUTHORED PATH STARTS FROM A FRESH PAGE (2026-09-07). pm-scheduler's delete read "no confirm"
      // only when it ran AFTER the auto-hail entry on the same page: the detail dialog and the cancelled confirm
      // left state behind, and the second path pressed into it. The person's path begins at page load.
      // (every entry, not only the second onwards: the pre-click sweep of menu buttons had folded report-sender's
      // contacts list before the first entry's trigger was looked for)
      if (!label.prep && !label.anon) { await p.reload({ waitUntil: 'load' }).catch(() => {}); await p.waitForTimeout(SETTLE_MS); }
      // an anonymous entry (the sign-in form) walks its steps on a fresh, signed-out page
      let pAnon = null;
      if (label.anon) {
        const c2 = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
        pAnon = await c2.newPage();
        pAnon.on('dialog', async (d) => { dialogs++; lastDialog = d.message(); await d.dismiss().catch(() => {}); });
        await pAnon.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
        await pAnon.waitForTimeout(SETTLE_MS);
        label._pAnon = pAnon;
      }
      for (const st of label.steps) {
        await (pAnon || p).evaluate((sel) => {
          const vis = (e) => e.checkVisibility && e.checkVisibility();
          // a `js:` step calls the page's own opener (index's openSignIn) when the landing's overlays hide the button
          // that calls it - the OPENER is called by hand, never the control under test
          if (sel.startsWith('js:')) { try { (0, eval)(sel.slice(3)); } catch (e) { /* empty-catch-allow: a missing opener leaves the control NOT REACHED */ } return; }
          const pool = sel.startsWith('text=')
            ? [...document.querySelectorAll('button, [role="button"], a, .asset-card, .pcard, [onclick]')].filter((e) => new RegExp(sel.slice(5), 'i').test((e.innerText || e.getAttribute('aria-label') || '').trim()))
            : [...document.querySelectorAll(sel)];
          // a step is an OPENER (a tab, a card, a menu): press the visible one, else the first - a hidden tab
          // button still switches its panel, and the control under test is judged for visibility on its own
          const el = pool.find(vis) || pool[0]; if (el) el.click();
        }, st).catch(() => {});
        await p.waitForTimeout(2500);   // a tab's list is fetched after the click (the disputes queue took >1.5 s)
      }
      const pressed = await (pAnon || p).evaluate((sel) => {
        const vis = (e) => e.checkVisibility && e.checkVisibility() && !e.disabled;
        const pool = sel.startsWith('text=')
          ? [...document.querySelectorAll('button, [role="button"], [role="menuitem"], a')].filter((e) => new RegExp(sel.slice(5), 'i').test((e.innerText || e.getAttribute('aria-label') || '').trim()))
          : [...document.querySelectorAll(sel)];
        const el = pool.find(vis); if (el) { el.click(); return true; }
        const scene = ((document.querySelector('#content-area, [role="dialog"]:not([hidden]), main') || document.body).innerText || '').replace(/\s+/g, ' ').slice(0, 140);
        return `no visible match for ${sel} (${pool.length} in DOM, url ${location.pathname.split('/').pop()}) · scene: ${scene}`;   // the instrument explains its number
      }, label.trigger).catch((e) => `read failed: ${String(e && e.message).slice(0, 80)}`);
      if (pressed !== true) { console.log(`        (${pressed})`); if (label.cleanup && label._id) psql(label.cleanup.replace('{id}', label._id)); continue; }   // NOT REACHED, never clean - and the seed is reversed
    } else await p.evaluate((label) => {
      const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
      const e = [...document.querySelectorAll('button, [role="button"], [role="menuitem"], a')].find((x) => vis(x) && (x.innerText || x.getAttribute('aria-label') || '').trim() === label);
      if (e) e.click();
    }, label).catch(() => {});
    await p.waitForTimeout(2600);   // an undo toast needs time to render (T50's lesson)
    const after = await ((typeof label === 'object' && label.anon && label._pAnon) ? label._pAnon : p).evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      const modals = [...document.querySelectorAll('[id^="wh-modal-ov-"], [role="dialog"]')].filter(vis);
      const confirmText = modals.map((m) => (m.innerText || '').replace(/\s+/g, ' ').trim()).join(' | ');
      const undo = [...document.querySelectorAll('button, [role="button"], a')].find((e) => /^\s*(undo|restore)\b/i.test(e.innerText || '') && vis(e));
      return { modals: modals.length, confirmText, undo: !!undo, raw: document.querySelectorAll('[id^="wh-modal-ov-"], [role="dialog"]').length, url: location.pathname.split('/').pop() };
    }, VIS_JS).catch((e) => { console.log(`        (read failed on ${file}: ${String(e && e.message).slice(0, 90)})`); return { modals: modalsBefore, confirmText: '', undo: false }; });
    const said = (after.confirmText || lastDialog || '').slice(0, 200);
    // which rostered control did this press reach? match the confirm's first words against the roster
    const head = (typeof label === 'object')
      ? heads.find((h) => label.heads.some((lh) => headKey(h) === headKey(lh) || headKey(h).startsWith(headKey(lh).slice(0, 16))))
      : heads.find((h) => h && headMatches(h, said));
    const offered = dialogs > dlgBefore || after.modals > modalsBefore || after.undo;
    let restored = null, reachable = null;
    if (after.modals > modalsBefore) {
      // a confirm: cancel it - no damage, and the way back was the Cancel. An entry marked accept:true presses
      // the confirm's OK instead (the vehicle wizard's Undo IS the way back) and is judged by the rows after it.
      const accept = typeof label === 'object' && label.accept === true;
      await p.evaluate((accept) => {
        const vis = (e) => e.checkVisibility && e.checkVisibility();
        for (const o of [...document.querySelectorAll('[id^="wh-modal-ov-"], [role="dialog"]')].filter(vis)) {
          const btns = [...o.querySelectorAll('button, [role="button"]')].filter(vis);
          const word = (b) => (b.innerText || b.getAttribute('aria-label') || '').trim();
          const cancel = btns.find((b) => /^(cancel|keep|no\b|close|back|never mind)/i.test(word(b)));
          const ok = btns.find((b) => /^(remove|undo|ok|yes|confirm|delete)/i.test(word(b)));
          const press = accept ? (ok || cancel) : cancel;
          if (press) press.click(); else o.remove();
        }
      }, accept).catch(() => {});
      await p.waitForTimeout(accept ? 6000 : 600);
      reachable = true;
      restored = accept ? WATCH.every((t) => census()[t] === before[t]) : true;   // an accepted undo must put every row back
    } else if (after.undo) {
      reachable = await p.evaluate(() => {
        const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
        const u = [...document.querySelectorAll('button, [role="button"], a')].find((e) => /^\s*(undo|restore)\b/i.test(e.innerText || '') && vis(e));
        if (u) { u.click(); return true; } return false;
      }).catch(() => false);
      await p.waitForTimeout(3500);
      const back = census();
      restored = WATCH.every((t) => back[t] === before[t]);
    } else if (dialogs > dlgBefore) {
      reachable = true; restored = true;   // native dialog, cancelled
    }
    const verdict = { label: typeof label === 'object' ? label.trigger : label, offered, reachable, restored, said: said.slice(0, 60),
      why: `dialogs ${dlgBefore}->${dialogs} · modals ${modalsBefore}->${after.modals} (raw ${after.raw}) · undo ${after.undo} · at ${after.url}` };   // the instrument explains its number
    if (process.env.RV_DEBUG && typeof label === 'object') console.log(`        (verdict ${JSON.stringify(verdict).slice(0, 170)} · heads ${heads.map((h) => headKey(h).slice(0, 20)).join(' | ')})`);
    if (typeof label === 'object' && label.cleanup && label._id) { psql(label.cleanup.replace('{id}', label._id)); }
    if (typeof label === 'object') {
      for (const h of heads) if (label.heads.some((lh) => headKey(h) === headKey(lh) || headKey(h).startsWith(headKey(lh).slice(0, 16)))) matched.set(h, verdict);
    }
    else if (head && !(matched.get(head) && matched.get(head).offered)) matched.set(head, verdict);
    else if (offered) matched.set(`(unrostered) ${label}`, verdict);
  }
  await ctx.close();

  // report per rostered control, and name the ones the sweep never reached
  for (const head of heads) {
    rowsChecked++;
    const v = matched.get(head);
    if (!v) { notReached.push(`${file}: "${head.slice(0, 32)}"`); console.log(`  n/a ${file.padEnd(26)} "${head.slice(0, 40)}" - not brought on screen by this sweep`); continue; }
    const ok = v.offered && v.reachable !== false && v.restored !== false;
    if (!ok) bad++;
    console.log(`  ${ok ? 'ok ' : 'BAD'} ${file.padEnd(26)} "${head.slice(0, 40)}" via "${v.label.slice(0, 22)}" · offered ${v.offered} · way back ${v.reachable === null ? 'n/a' : v.reachable} · restored ${v.restored === null ? 'n/a' : v.restored}`);
    if (!ok) console.log(`        ${!v.offered ? 'the control fired with no confirm and no undo - the wrong thing is simply gone (' + v.why + ')' : !v.reachable ? 'an undo was shown that could not be pressed' : 'the undo was pressed and the live rows did not come back'}`);
  }
}
await b.close();
if (notReached.length) console.log(`  note ${notReached.length} rostered control(s) NOT REACHED, not clean: ${notReached.slice(0, 6).join('; ')}`);
console.log(`${(bad || notReached.length) ? 'FAIL' : 'PASS'} recovery-path -${rowsChecked - bad - notReached.length}/${rowsChecked - notReached.length} reached destructive control(s) offer a way back that works`);
// ★A GATE THAT REACHED NOTHING MUST NOT PASS (2026-09-07). The first run reported "PASS recovery-path - 0/0
// reached" with 53 controls NOT REACHED - a vacuous green, the exact shape the teeth-metric family warns
// about. A rostered control the sweep could not bring on screen is owed, so it fails the gate too.
process.exitCode = (bad || notReached.length) ? 1 : 0;
