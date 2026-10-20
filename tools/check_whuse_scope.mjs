// check_whuse_scope.mjs <page.html ...> - SL L3 (2026-10-21), run by tools/validate_usage_events.py (U5).
// For every whUse / whUseThen(<Identifier>, ...) call in a page's inline scripts: is the identifier declared in an
// enclosing scope, or at the top level of one of the page's classic scripts? A call whose client name is out of scope
// throws a ReferenceError BEFORE whUse runs - the use is lost and the handler it sits in dies with it.
// One pass with a scope STACK (each scope's names computed once on entry), linear in the size of the page.
// Two instrument lessons from building it: the repo's acorn is 7.4.1, which LOOPS FOREVER on ecmaVersion 'latest'
// (a number is required); and an HTML comment that MENTIONS "<script>" opened a false match that swallowed the real
// script after it, so comments are blanked first. A script that does not parse is reported and fails the run -
// an unchecked script is not a clean one.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(process.cwd() + '/');
const acorn = require('acorn');

const SCRIPT = /<script(\s[^>]*)?>([\s\S]*?)<\/script>/gi;
const FN = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']);
const declNames = (node, out) => {
  if (!node) return;
  if (node.type === 'Identifier') out.add(node.name);
  else if (node.type === 'ObjectPattern') node.properties.forEach((p) => declNames(p.value || p.argument, out));
  else if (node.type === 'ArrayPattern') node.elements.forEach((e) => declNames(e, out));
  else if (node.type === 'AssignmentPattern') declNames(node.left, out);
  else if (node.type === 'RestElement') declNames(node.argument, out);
};
const directDecls = (stmts, out) => {
  for (const s of stmts || []) {
    if (s.type === 'VariableDeclaration') s.declarations.forEach((d) => declNames(d.id, out));
    else if ((s.type === 'FunctionDeclaration' || s.type === 'ClassDeclaration') && s.id) out.add(s.id.name);
  }
};
const hoistedVars = (root, out) => {           // var anywhere in this function, not crossing nested functions
  const stack = [root];
  while (stack.length) {
    const n = stack.pop();
    if (!n || typeof n.type !== 'string') continue;
    if (n !== root && FN.has(n.type)) continue;
    if (n.type === 'VariableDeclaration' && n.kind === 'var') n.declarations.forEach((d) => declNames(d.id, out));
    for (const k in n) {
      if (k === 'loc' || k === 'start' || k === 'end') continue;
      const v = n[k];
      if (Array.isArray(v)) { for (const c of v) if (c && typeof c.type === 'string') stack.push(c); }
      else if (v && typeof v.type === 'string') stack.push(v);
    }
  }
};
const scopeOf = (n) => {
  const here = new Set();
  if (FN.has(n.type)) {
    n.params.forEach((q) => declNames(q, here));
    if (n.type === 'FunctionExpression' && n.id) here.add(n.id.name);
    hoistedVars(n.body, here);
    if (n.body && n.body.type === 'BlockStatement') directDecls(n.body.body, here);
    return here;
  }
  if (n.type === 'BlockStatement') { directDecls(n.body, here); return here; }
  if (n.type === 'SwitchStatement') { n.cases.forEach((c) => directDecls(c.consequent, here)); return here; }
  if (n.type === 'CatchClause') { if (n.param) declNames(n.param, here); return here; }
  if ((n.type === 'ForStatement' && n.init && n.init.type === 'VariableDeclaration')
      || ((n.type === 'ForOfStatement' || n.type === 'ForInStatement') && n.left.type === 'VariableDeclaration')) {
    (n.init || n.left).declarations.forEach((d) => declNames(d.id, here));
    return here;
  }
  return null;
};

let bad = 0, calls = 0;
for (const file of process.argv.slice(2)) {
  // an HTML comment that MENTIONS "<script>" would open a false match and swallow the real script after it; blank
  // the comments first (newlines kept, so line numbers still point at the file)
  const html = readFileSync(file, 'utf8').replace(/<!--[\s\S]*?-->/g, (c) => c.replace(/[^\n]/g, ' '));
  const programs = [];
  for (const m of html.matchAll(SCRIPT)) {
    const attrs = m[1] || '';
    if (/\bsrc=/.test(attrs) || /type=["'](application\/(ld\+)?json|module|text\/template)/i.test(attrs)) continue;
    const startLine = html.slice(0, m.index).split('\n').length;
    try { programs.push({ ast: acorn.parse(m[2], { ecmaVersion: 2021, sourceType: 'script', allowReturnOutsideFunction: true, locations: true }), startLine }); }
    catch (e) { bad++; console.log(`  UNCHECKED ${file}: the script at line ${startLine} did not parse (${e.message})`); }
  }
  const globals = new Set();
  for (const p of programs) { directDecls(p.ast.body, globals); hoistedVars(p.ast, globals); }
  for (const p of programs) {
    const scopes = [];
    const walk = (n) => {
      if (!n || typeof n.type !== 'string') return;
      const sc = scopeOf(n);
      if (sc) scopes.push(sc);
      if (n.type === 'CallExpression' && n.callee.type === 'Identifier' && (n.callee.name === 'whUse' || n.callee.name === 'whUseThen')) {
        calls++;
        const a0 = n.arguments[0];
        if (a0 && a0.type === 'Identifier' && !globals.has(a0.name) && !scopes.some((s) => s.has(a0.name))) {
          bad++;
          console.log(`  NOT IN SCOPE ${file}:${p.startLine + n.loc.start.line - 1}  ${n.callee.name}(${a0.name}, ...)`);
        }
      }
      for (const k in n) {
        if (k === 'loc' || k === 'start' || k === 'end') continue;
        const v = n[k];
        if (Array.isArray(v)) { for (const c of v) walk(c); } else if (v && typeof v.type === 'string') walk(v);
      }
      if (sc) scopes.pop();
    };
    walk(p.ast);
  }
}
console.log(`${bad ? 'FAIL' : 'ok'} - ${calls} whUse call(s), ${bad} with a client name out of scope`);
process.exitCode = bad ? 1 : 0;
