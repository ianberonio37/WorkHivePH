// tdz_reads.cjs - a let/const/class name READ before the statement that declares it (the temporal dead zone).
//
// ★A SCRIPT THAT PARSES CAN STILL DIE ON ITS FIRST LINE (2026-11-06, GJ M10 G-ESC). An edit put
// `const isPublic = row?.ref_post_id ? ...` ABOVE `const row = ...` in the founder console's save handler. The script
// parsed (a let/const read before its declaration is legal syntax), and every click of "Save changes" threw a
// ReferenceError before writing anything: WorkHive's answer to an escalation was never saved, and only the group walk saw
// it. So: inside one statement list, a statement that reads a let/const/class name BEFORE the statement that declares
// it - outside any nested function, which may legitimately run later - is reported. A nested block that declares the
// same name shadows it and is not searched. One copy, used by tools/check_inline_scripts.js (per page) and
// tools/validate_scripts_parse.mjs (gate scripts-parse, every served page and shared script).
let acorn = null;
try { acorn = require('acorn'); } catch (_) { acorn = null; }   // no parser installed: callers still run their syntax check

const FN = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression', 'ClassBody']);

function lexNames(stmt) {
  if (stmt.type === 'VariableDeclaration' && stmt.kind !== 'var') {
    const out = [];
    const pat = (p) => {
      if (!p) return;
      if (p.type === 'Identifier') out.push(p.name);
      else if (p.type === 'ObjectPattern') p.properties.forEach((q) => pat(q.type === 'RestElement' ? q.argument : q.value));
      else if (p.type === 'ArrayPattern') p.elements.forEach(pat);
      else if (p.type === 'AssignmentPattern') pat(p.left);
      else if (p.type === 'RestElement') pat(p.argument);
    };
    stmt.declarations.forEach((d) => pat(d.id));
    return out;
  }
  if (stmt.type === 'ClassDeclaration' && stmt.id) return [stmt.id.name];
  return [];
}

// every Identifier READ under node that names `name`, not inside a nested function or a block that redeclares it
function reads(node, name, out) {
  if (!node || typeof node.type !== 'string' || FN.has(node.type)) return;
  if ((node.type === 'BlockStatement' || node.type === 'Program') && node.body.some((s) => lexNames(s).includes(name))) return;
  // a loop's own head (`for (const [k, v] of ...)`) and a catch parameter are scopes of their own: the name there is a
  // different binding (offline-queue.js's confirm loop declared `v` in a for-of head and a `const v` two lines below)
  const head = node.type === 'ForStatement' ? node.init : (node.type === 'ForOfStatement' || node.type === 'ForInStatement') ? node.left : null;
  if (head && head.type === 'VariableDeclaration' && lexNames(head).includes(name)) return;
  if (node.type === 'CatchClause' && node.param && lexNames({ type: 'VariableDeclaration', kind: 'let',
      declarations: [{ id: node.param }] }).includes(name)) return;
  if (node.type === 'Identifier' && node.name === name) { out.push(node); return; }
  for (const k of Object.keys(node)) {
    if (k === 'loc' || k === 'start' || k === 'end') continue;
    if (node.type === 'MemberExpression' && k === 'property' && !node.computed) continue;   // a.row is not row
    if (node.type === 'Property' && k === 'key' && !node.computed) continue;                // { row: 1 } is not row
    const v = node[k];
    if (Array.isArray(v)) v.forEach((c) => c && typeof c.type === 'string' && reads(c, name, out));
    else if (v && typeof v.type === 'string') reads(v, name, out);
  }
}

function tdzReads(src) {
  if (!acorn) return [];
  let ast;
  try {
    ast = acorn.parse(src, { ecmaVersion: 'latest', sourceType: 'script', allowReturnOutsideFunction: true,
                             allowAwaitOutsideFunction: true, locations: true });
  } catch (_) { return []; }   // the caller's own parse decides syntax; a grammar acorn reads differently is not this question
  const found = [];
  const visitList = (list) => {
    list.forEach((stmt, idx) => {
      for (const name of lexNames(stmt)) {
        for (let e = 0; e < idx; e++) {
          const hits = [];
          reads(list[e], name, hits);
          for (const h of hits) found.push(`"${name}" is read on line ${h.loc.start.line} before its declaration on line ${stmt.loc.start.line}`);
        }
      }
    });
  };
  const walk = (node) => {
    if (!node || typeof node.type !== 'string') return;
    if (node.type === 'Program' || node.type === 'BlockStatement' || node.type === 'StaticBlock') visitList(node.body);
    if (node.type === 'SwitchCase') visitList(node.consequent);
    for (const k of Object.keys(node)) {
      if (k === 'loc') continue;
      const v = node[k];
      if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v.type === 'string') walk(v);
    }
  };
  walk(ast);
  return found;
}

// the cases every caller's self-test runs: the real shape caught; a closure, a shadow and a property are not
function tdzSelfTest() {
  const fails = [];
  if (!acorn) fails.push('acorn is not installed - the TDZ lens cannot run');
  const bad1 = tdzReads('function save(id){ const a = row ? 1 : 2; const row = find(id); }');
  if (bad1.length !== 1) fails.push('the console save-handler shape was not caught: ' + JSON.stringify(bad1));
  [
    'function save(id){ const row = find(id); const a = row ? 1 : 2; }',
    'function f(){ const g = () => row; const row = 1; return g(); }',
    'function f(){ if (x) { const row = 2; use(row); } const row = 1; }',
    'function f(o){ const a = o.row; const b = { row: 1 }; const row = 3; }',
    'function f(m){ for (const [k, v] of Object.entries(m)) use(k, v); const v = 1; }',   // offline-queue.js's loop head
    'function f(){ try { g(); } catch (v) { use(v); } const v = 1; }',
  ].forEach((src, n) => { const r = tdzReads(src); if (r.length) fails.push('false positive #' + (n + 1) + ': ' + JSON.stringify(r)); });
  return fails;
}

module.exports = { tdzReads, tdzSelfTest, hasParser: () => !!acorn };
