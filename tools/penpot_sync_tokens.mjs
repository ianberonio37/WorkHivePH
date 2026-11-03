// penpot_sync_tokens.mjs - mirror tokens.css into the WorkHive Penpot file, idempotently (2026-11-03).
//
// The design source stays in code (Ian, 2026-10-13); Penpot is the canvas a comp is drawn on, so its palette must be
// tokens.css's palette and nothing else (OD-P: "every fill is a library colour"). This writes the :root colours twice -
// as library colours (the swatches a designer picks) and as a design-token set (what a shape binds to, read back by
// shape.tokens) - and removes any token the CSS no longer has.
//
// ★Penpot token names are paths: a leaf "wh.orange" refuses "wh.orange.dark" beneath it ("a token already exists at the
// path ... or at a prefix thereof"). The names stay flat, as the CSS writes them: wh-orange, wh-orange-dark.
//
//   node tools/penpot_sync_tokens.mjs          # sync (the Penpot tab must be open with MCP -> Connect)
//   node tools/penpot_sync_tokens.mjs --check  # report drift only; exit 1 when Penpot and tokens.css disagree
import fs from 'node:fs';
import { penpot } from './lib/penpot_mcp.mjs';

const SET = 'WorkHive tokens.css';
const check = process.argv.includes('--check');

const css = fs.readFileSync('tokens.css', 'utf8');
const root = css.slice(css.indexOf(':root'), css.indexOf('}', css.indexOf(':root')));
const want = [...root.matchAll(/--(wh-[\w-]+)\s*:\s*(#[0-9a-fA-F]{6}|rgba?\([^)]*\))\s*;/g)]
  .map((m) => ({ name: m[1], value: m[2].replace(/\s+/g, ' ').toUpperCase().replace('RGBA', 'rgba').replace('RGB(', 'rgb(') }));

const p = await penpot();
const res = await p.run(`
const want = ${JSON.stringify(want)}, check = ${check};
const lib = penpot.library.local, cat = lib.tokens;
let set = cat.sets.find((s) => s.name === ${JSON.stringify(SET)});
if (!set && !check) set = cat.addSet({ name: ${JSON.stringify(SET)} });
if (set && !set.active && !check) set.toggleActive();
const wanted = new Map(want.map((w) => [w.name, w.value]));
const out = { tokensWanted: want.length, tokenStale: [], tokenMissing: [], colourMissing: [], made: 0, removed: 0 };
for (const t of (set ? set.tokens : [])) {
  if (wanted.get(t.name) !== t.value) { out.tokenStale.push(t.name); if (!check) { t.remove(); out.removed++; } }
}
const have = new Set((set ? set.tokens : []).map((t) => t.name));
for (const w of want) {
  if (have.has(w.name)) continue;
  out.tokenMissing.push(w.name);
  if (!check) { set.addToken({ type: 'color', name: w.name, value: w.value }); out.made++; }
}
const colours = new Map(lib.colors.map((c) => [c.name, c]));
for (const w of want.filter((x) => x.value.startsWith('#'))) {
  const c = colours.get(w.name);
  if (c && c.color.toUpperCase() === w.value) continue;
  out.colourMissing.push(w.name);
  if (!check) { const n = c || lib.createColor(); n.name = w.name; n.path = 'WorkHive tokens'; n.color = w.value; n.opacity = 1; }
}
return out;`);
const drift = res.tokenStale.length + res.tokenMissing.length + res.colourMissing.length;
if (check) {
  console.log(drift ? `FAIL penpot-tokens: Penpot disagrees with tokens.css - stale ${res.tokenStale.length}, missing tokens `
    + `${res.tokenMissing.length}, missing/changed colours ${res.colourMissing.length}` : `PASS penpot-tokens: ${res.tokensWanted} tokens agree`);
  process.exit(drift ? 1 : 0);
}
console.log(`synced: ${res.made} token(s) added, ${res.removed} stale removed, ${res.colourMissing.length} library colour(s) written`);
