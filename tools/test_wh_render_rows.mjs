// tools/test_wh_render_rows.mjs - SL LB3 (2026-10-21): utils.js whRenderRows against a mock list element (each top-level <li> is one
// child). Run by tools/validate_long_list_render.py (R1); a source file may be passed in place of utils.js (the mutants).
//   node tools/test_wh_render_rows.mjs utils.js
import { readFileSync } from 'fs';
const src = readFileSync(process.argv[2], 'utf8');
const start = src.indexOf('function whRenderRows(');
const end = src.indexOf('if (typeof window !== \'undefined\') window.whRenderRows');
const whRenderRows = new Function(src.slice(start, end) + '; return whRenderRows;')();

// a node: replaceWith swaps it inside its owner's children; focus makes it the active element
function node(html, owner) {
  const n = {
    html, owner, children: [], parentElement: owner,
    contains(x) { return x === n; },
    focus() { globalThis.document.activeElement = n; },
    replaceWith(m) { const i = n.owner.kids.indexOf(n); m.owner = n.owner; m.parentElement = n.owner; n.owner.kids[i] = m; n.owner.patches++; },
  };
  return n;
}
const parse = (h, owner) => (h.match(/<li>[^<]*<\/li>/g) || []).map((s) => node(s, owner));
globalThis.document = {
  activeElement: null,
  createElement() {
    const t = { content: { childElementCount: 0, firstElementChild: null } };
    Object.defineProperty(t, 'innerHTML', { set(h) { const ks = parse(h, null); t.content.childElementCount = ks.length; t.content.firstElementChild = ks[0] || null; } });
    return t;
  },
};
function mockList() {
  const el = {
    kids: [], classes: new Set(), replaces: 0, appends: 0, patches: 0,
    classList: { add: (c) => el.classes.add(c) },
    get children() { return el.kids; },
    get childElementCount() { return el.kids.length; },
    get lastElementChild() { return el.kids[el.kids.length - 1] || null; },
    set innerHTML(h) { el.kids = parse(h, el); el.replaces++; },
    insertAdjacentHTML(pos, h) { if (pos !== 'beforeend') throw new Error(pos); el.kids.push(...parse(h, el)); el.appends++; },
  };
  return el;
}
const row = (x) => `<li>${x.id}:${x.v}</li>`;
const items = (n, v = 'a') => Array.from({ length: n }, (_, i) => ({ id: i, v }));
let fails = 0;
const ok = (cond, what) => { if (!cond) { fails++; console.log('FAIL', what); } else console.log('ok  ', what); };

let L = mockList();
ok(whRenderRows(L, items(20), row, { sig: 'q=' }) === 'replaced' && L.kids.length === 20, 'first render replaces');
ok(whRenderRows(L, items(40), row, { sig: 'q=' }) === 'appended' && L.kids.length === 40 && L.appends === 1 && L.replaces === 1, 'growing the same list appends only the new 20');
ok(L.kids[39].html === '<li>39:a</li>' && L.kids[0].html === '<li>0:a</li>', 'the appended rows are the new ones, in order');
ok(whRenderRows(L, items(40), row, { sig: 'q=' }) === 'appended' && L.replaces === 1 && L.appends === 1, 'an identical re-render touches nothing');
ok(whRenderRows(L, items(60), row, { sig: 'q=x' }) === 'replaced' && L.kids.length === 60, 'a new signature (a search) replaces');
const many = items(60).map((x) => ({ ...x, v: 'm' }));
ok(whRenderRows(L, many, row, { sig: 'q=x' }) === 'replaced' && L.kids[5].html === '<li>5:m</li>', 'many changed rows replace the list');
ok(whRenderRows(L, items(10), row, { sig: 'q=x' }) === 'replaced' && L.kids.length === 10, 'a shorter list replaces');
L.innerHTML = ''; L.replaces = 0;
ok(whRenderRows(L, items(20), row, { sig: 'q=x' }) === 'replaced', 'a list cleared by other code is replaced, not appended to');
L.innerHTML = '<li>s</li>'.repeat(20);   // a skeleton of the same size
ok(whRenderRows(L, items(30), row, { sig: 'q=x' }) === 'replaced' && L.kids[0].html === '<li>0:a</li>', 'a skeleton of the same size is not mistaken for the rows');
const N = mockList();
whRenderRows(N, items(20), row); ok(whRenderRows(N, items(40), row) === 'replaced', 'without a sig the list is always replaced');
const K = mockList();
whRenderRows(K, items(20), row, { sig: 's', key: (x) => x.id });
ok(whRenderRows(K, items(25), row, { sig: 's', key: (x) => x.id }) === 'appended' && K.kids.length === 25, 'a custom key appends');
const C = mockList(); whRenderRows(C, items(3), row, { sig: 's', long: true }); ok(C.classes.has('wh-rows-cv'), 'long:true marks the list for content-visibility');
// a few changed rows are replaced in place, the rest untouched, and a keyboard user's focus moves into the replacement
const P = mockList(); whRenderRows(P, items(40), row, { sig: 's' });
const kept = P.kids[6]; document.activeElement = P.kids[5];
const one = items(40); one[5] = { id: 5, v: 'sel' };
ok(whRenderRows(P, one, row, { sig: 's' }) === 'patched' && P.patches === 1 && P.replaces === 1 && P.kids[5].html === '<li>5:sel</li>', 'one changed row (a selection) is patched in place, not the list');
ok(P.kids[6] === kept, 'the rows around a patched one are the same elements');
ok(document.activeElement === P.kids[5], 'the focus on a patched row moves into its replacement');
const grow = one.concat(items(50).slice(40)); grow[2] = { id: 2, v: 'z' };
ok(whRenderRows(P, grow, row, { sig: 's' }) === 'patched' && P.kids.length === 50 && P.kids[2].html === '<li>2:z</li>', 'a patch and a growth in one render: both land');
const H = mockList();
ok(whRenderRows(H, items(15), row, { key: 'html' }) === 'replaced', "key 'html': first render replaces (no sig needed)");
ok(whRenderRows(H, items(30), row, { key: 'html' }) === 'appended' && H.kids.length === 30 && H.appends === 1, "key 'html': a grown list appends");
const relabel = items(45); relabel[3] = { id: 3, v: 'z' };   // an earlier row would now render differently (a relative time moved)
ok(['patched', 'replaced'].includes(whRenderRows(H, relabel, row, { key: 'html' })) && H.kids[3].html === '<li>3:z</li>' && H.kids.length === 45, "key 'html': a row whose HTML changed is redrawn");
let built = 0; const counted = (x) => { built++; return row(x); };
const H2 = mockList(); whRenderRows(H2, items(10), counted, { key: 'html' }); built = 0;
whRenderRows(H2, items(20), counted, { key: 'html' });
ok(built === 20 && H2.appends === 1, "key 'html': each row's HTML is built once per render (keys and new rows share it)");
console.log(fails ? `FAIL (${fails})` : 'PASS - whRenderRows: appends a grown list, patches a few changed rows, replaces anything else');
process.exit(fails ? 1 : 0);
