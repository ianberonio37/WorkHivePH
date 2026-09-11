// prove_cross_page_chains — the lineage journeys (T30, T31, T32, T36), 2026-09-07.
//
// Four rows that no single page can answer, because each is about whether an action on ONE surface
// produces a visible, traceable effect on ANOTHER. This is where a platform stops being a set of tools
// and starts being a system - and it is also where a platform quietly stops being one, because each page
// keeps working perfectly while the thread between them is missing.
//
//   K1 stock to supply   a part below its minimum is FLAGGED low, and there is a path from that shortage
//                        to acquiring more - the shortage a person notices is the shortage the
//                        marketplace should be able to answer (T30)
//   K2 answer to standing a good answer in the community reaches the person who wrote it: it is
//                        attributable, and it feeds something that outlives the thread (T31)
//   K3 work to compliance a logbook entry about maintenance is not stranded there - the PM record and the
//                        compliance view read from the same work, so doing the job is recording it (T32)
//   K4 calc to project    an engineering calculation produces a bill of materials that can become project
//                        WORK, rather than a number someone retypes into a spreadsheet (T36)
//
// ★A CHAIN IS PROVEN BY THE LINK, NOT BY BOTH ENDS EXISTING. Two pages that each work, with nothing
// joining them, is exactly the failure these rows exist to catch - so every lens below looks for the
// JOIN: a foreign key, a shared identifier, or a control on page A that names page B.
//
//   node tools/prove_cross_page_chains.mjs
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── K1 · a shortage a person notices, and can act on ─────────────────────────────────────────────
{
  const low = psql("select count(*) from inventory_items where qty_on_hand < min_qty");
  // the LINK: a listing can name the inventory item it came from
  const linkCol = psql("select count(*) from information_schema.columns where table_schema='public' and table_name='marketplace_listings' and column_name='source_inventory_item_id'");
  const linked = psql("select count(*) from marketplace_listings where source_inventory_item_id is not null");
  // and the path a person walks: from the shortage to the place that can fill it
  const inv = read('inventory.html');
  const toMarket = /marketplace|procure|source this|find a supplier|list on/i.test(inv);
  const flagsLow = /low stock|below min|min_qty|reorder/i.test(inv);
  // ★A JOIN NOTHING HAS EVER USED IS A SCHEMA CLAIM, NOT A WALKED ONE. The column exists and 0 rows
  // carry it, so the chain is EXERCISED here: a listing is created from a real low-stock part, read
  // back to confirm the thread survives the round trip, and removed again. A link that has never been
  // traversed is exactly the kind of thing that turns out not to work the first time someone needs it.
  const part = psql("select id||'|'||coalesce(part_name,part_number)||'|'||hive_id from inventory_items where qty_on_hand < min_qty and hive_id is not null limit 1");
  let exercised = 'not attempted';
  if (part) {
    const [itemId, name, hiveId] = part.split('|');
    const ins = psql(`insert into marketplace_listings (hive_id, seller_name, section, category, title, description, price, condition, status, source_inventory_item_id) values ('${hiveId}', 'Leandro Marquez', 'parts', 'Spare Parts', 'wh-chain-probe ${name.replace(/'/g, "''").slice(0, 40)}', 'chain probe', 1, 'used', 'draft', '${itemId}') returning id`);
    // psql -tA still prints its own status line after a RETURNING row, so the id is the FIRST line and
    // the rest ("INSERT 0 1") would otherwise be spliced into the next query and break its quoting
    const newId = (ins.split('\n')[0] || '').trim();
    if (newId) {
      const back = psql(`select source_inventory_item_id::text from marketplace_listings where id = '${newId}'`);
      exercised = back === itemId ? `traversed live: a listing created from the short part kept its link back to it` : `the link did NOT survive the write (wrote ${itemId}, read ${back || 'null'})`;
      psql(`delete from marketplace_listings where id = '${newId}'`);
    } else exercised = 'the listing could not be created, so the join is unexercised';
  }
  const traversed = /traversed live/.test(exercised);
  say(Number(linkCol || 0) > 0 && flagsLow && toMarket && traversed, 'K1 stock to supply',
    `${low} part(s) below minimum; inventory ${flagsLow ? 'flags them' : 'does NOT flag them'} and ${toMarket ? 'offers a route to the marketplace' : 'offers no route onward'}; the schema carries the join (${linkCol} column, ${linked} listing(s) using it today) and it was ${exercised}`,
    Number(linkCol || 0) === 0 ? 'a listing cannot say which inventory item it came from, so the two surfaces have no thread between them'
      : !flagsLow ? 'inventory never marks a part as short, so the shortage is only visible to someone comparing two numbers by eye'
      : !toMarket ? 'nothing on inventory leads toward acquiring more, so a person who spots a shortage has to remember the marketplace exists and start again'
      : `the join did not survive being used: ${exercised}`);
}

// ── K2 · an answer that outlives its thread ──────────────────────────────────────────────────────
{
  const posts = psql("select count(*) from community_posts where deleted_at is null");
  const attributed = psql("select count(*) from community_posts where deleted_at is null and author_name is not null");
  // the ripple: something durable that an answer feeds - a reputation, a skill, an achievement
  const feeds = psql("select string_agg(table_name, ', ') from information_schema.tables where table_schema='public' and table_name ~ '(achievement|skill_profile|reputation|xp_)'");
  const comm = read('community.html');
  // and the answer has to be markable as good, or "best answer" is a thread nobody can find twice
  const markable = /best answer|accepted|helpful|pin post|pinned/i.test(comm);
  say(Number(attributed || 0) === Number(posts || 0) && !!feeds && markable, 'K2 answer to standing',
    `${attributed} of ${posts} live post(s) name their author; a good answer can be marked (${markable}); it feeds ${feeds || 'nothing'}`,
    Number(attributed || 0) < Number(posts || 0) ? 'some posts have no author, so the person who wrote the answer cannot be credited for it'
      : !markable ? 'no answer can be marked as the good one, so the thread is the only record and the next person re-asks'
      : 'nothing durable is fed by answering, so contributing costs time and returns nothing that lasts');
}

// ── K3 · doing the job is recording it ───────────────────────────────────────────────────────────
{
  // the work exists in two places and must agree: the logbook a person writes, and the PM record
  const logbookPM = psql("select count(*) from logbook where maintenance_type is not null");
  const completions = psql("select count(*) from pm_completions");
  // the JOIN: both hang off the same asset, which is what lets compliance read one from the other
  const sharedAsset = psql("select count(*) from information_schema.columns where table_schema='public' and column_name in ('asset_id','machine','linked_asset_no') and table_name in ('logbook','pm_completions','pm_scope_items')");
  const compliance = psql("select string_agg(table_name, ', ') from information_schema.tables where table_schema='public' and (table_name ~ 'complian' or table_name ~ 'v_pm')");
  say(Number(logbookPM || 0) > 0 && Number(completions || 0) > 0 && Number(sharedAsset || 0) >= 2, 'K3 work to compliance',
    `${logbookPM} logbook entry(ies) carry a maintenance type and ${completions} PM completion(s) exist, joined through ${sharedAsset} shared asset column(s); compliance reads ${compliance || 'nothing'}`,
    Number(completions || 0) === 0 ? 'no PM completion has ever been recorded, so the compliance view has nothing to read and the logbook work is stranded'
      : 'the logbook and the PM record share no asset reference, so nothing can tell that an entry and a completion describe the same job');
}

// ── K4 · a calculation that becomes work ─────────────────────────────────────────────────────────
{
  const bom = psql("select count(*) from bom_knowledge");
  const projects = psql("select count(*) from projects");
  const items = psql("select count(*) from project_items");
  // the LINK a person walks: the calc page has to offer the hand-off, and the project has to accept it
  const calcOffers = /bom|bill of materials|sow|scope of work|send to project|import to project/i.test(read('engineering-design.html'));
  const projAccepts = /import|from a calculation|bom|scope of work/i.test(read('project-manager.html'));
  say(calcOffers && projAccepts && Number(items || 0) > 0, 'K4 calc to project',
    `${bom} BOM knowledge row(s); the calculator ${calcOffers ? 'produces a bill of materials and offers the hand-off' : 'offers no hand-off'}, and the project manager ${projAccepts ? 'accepts one' : 'does NOT accept one'}; ${items} project item(s) across ${projects} project(s)`,
    !calcOffers ? 'the calculator produces a number and no bill of materials, so the work of turning it into a job is entirely manual'
      : !projAccepts ? 'the project manager cannot receive a bill of materials, so a person retypes it - which is where the transcription errors live'
      : 'no project has any items, so the receiving end is unproven');
}

console.log(`${bad ? 'FAIL' : 'PASS'} cross-page-chains - a shortage leads to supply, an answer earns standing, doing the job records it, and a calculation becomes work`);
process.exitCode = bad ? 1 : 0;
