/**
 * Tier 8 — Security & multi-tenancy (6 scenarios, P0)
 *
 * RLS isolation, console-call escalation prevention, onclick role guards,
 * XSS, service_role exposure, Stripe webhook signature.
 *
 * I4, I5 are static (real assertions). Others are fixme until live test
 * environment is reachable.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync, readdirSync, statSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

function listProductionHtmlAndJs(): string[] {
  return readdirSync(ROOT)
    .filter((f) => (f.endsWith('.html') || f.endsWith('.js'))
      && !/-test\.html$/.test(f)
      && !/\.backup\d*\.html$/.test(f)
      && statSync(resolve(ROOT, f)).isFile());
}

test.describe('Tier 8 — Security & multi-tenancy', () => {

  test('I1_rls_policies_use_auth_uid_or_user_in_hive: tenant boundary uses canonical predicate', async () => {
    // WHY: RLS predicate `auth.uid()` (or hive-membership helper `user_in_hive(...)`) is the canonical tenant boundary
    // STATIC: at least one migration file must define a policy using one of these predicates
    const migDir = resolve(ROOT, 'supabase', 'migrations');
    const files = readdirSync(migDir).filter((f) => f.endsWith('.sql'));
    let found = 0;
    for (const f of files) {
      const sql = readFileSync(resolve(migDir, f), 'utf-8');
      if (/CREATE\s+POLICY[\s\S]{0,800}(auth\.uid\s*\(\s*\)|user_in_hive\s*\()/i.test(sql)) {
        found++;
        if (found >= 3) break;
      }
    }
    expect(found, `at least 3 migrations should declare RLS via auth.uid() or user_in_hive; found ${found}`).toBeGreaterThanOrEqual(3);
  });

  test('I2_deletecalc_scopes_to_worker_name: engineering-design.deleteCalc filters by WORKER_NAME', async () => {
    // WHY: defense-in-depth — JS-level worker_name scope guards even if RLS would also stop it
    const html = readFileSync(resolve(ROOT, 'engineering-design.html'), 'utf-8');
    // Find deleteCalc function start, then walk forward to a generous window to capture full body.
    const fnIdx = html.search(/function\s+deleteCalc\s*\(/);
    expect(fnIdx, 'deleteCalc handler must exist').toBeGreaterThan(-1);
    const fnBody = html.slice(fnIdx, fnIdx + 2000);
    // Must apply .eq('worker_name', WORKER_NAME) — pattern locked-in 2026-05-19
    expect(fnBody, 'deleteCalc must scope by WORKER_NAME (defense-in-depth)').toMatch(
      /\.eq\s*\(\s*['"]worker_name['"]\s*,\s*WORKER_NAME/
    );
  });

  test('I3_onclick_internal_role_guard: approve/reject/kick functions have internal HIVE_ROLE check', async () => {
    // WHY: skill rule security_inline_onclick_role_check_inside_fn
    // STATIC: every moderation function (approve|reject|kick|ban|moderate|flag) must include a HIVE_ROLE check
    // within its first ~300 chars (the typical position of the guard).
    const offenders: string[] = [];
    const fnDecl = /async\s+function\s+(approve|reject|kick|ban|moderate|flag|unban)\w*\s*\(/g;
    for (const f of listProductionHtmlAndJs()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      fnDecl.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = fnDecl.exec(content)) !== null) {
        // Capture the next ~300 chars after the function declaration.
        const window = content.slice(m.index, m.index + 400);
        // Two accepted role-check forms (both meet the security skill's intent):
        //   1) inline: HIVE_ROLE !== 'supervisor' / === 'supervisor'
        //   2) helper: isSupervisor() / isAdmin() / canModerate() / requireSupervisor()
        const hasInline = /HIVE_ROLE\s*[!=]==?\s*['"]/.test(window);
        const hasHelper = /(?:^|[^\w])(?:isSupervisor|isAdmin|canModerate|requireSupervisor|requireRole)\s*\(/.test(window);
        if (!hasInline && !hasHelper) {
          offenders.push(`${f}:${m.index} ${m[1]}* function lacks role check (no HIVE_ROLE or isSupervisor)`);
        }
      }
    }
    expect(offenders, 'every moderation function must include internal HIVE_ROLE check').toEqual([]);
  });

  test('I4_xss_escaped_in_user_text: escHtml escapes all 5 chars across canonical utils.js', async () => {
    // WHY: utils.js is the single source for escHtml (per security skill)
    // STATIC ASSERTION
    const utils = readFileSync(resolve(ROOT, 'utils.js'), 'utf-8');
    expect(utils, 'escHtml replaces &').toMatch(/replace\(\s*\/&\/g\s*,\s*['"]&amp;['"]/);
    expect(utils, 'escHtml replaces <').toMatch(/replace\(\s*\/<\/g\s*,\s*['"]&lt;['"]/);
    expect(utils, 'escHtml replaces >').toMatch(/replace\(\s*\/>\/g\s*,\s*['"]&gt;['"]/);
    expect(utils, 'escHtml replaces "').toMatch(/replace\(\s*\/"\/g\s*,\s*['"]&quot;['"]/);
    expect(utils, "escHtml replaces ' (the critical one)").toMatch(/replace\(\s*\/'\/g\s*,\s*['"]&#39;['"]/);
  });

  test('I5_no_service_role_in_frontend: service_role JWT never in HTML/JS', async () => {
    // WHY: service_role bypasses RLS; in frontend = full DB exposure
    // STATIC ASSERTION: pattern from skill_rules_manifest security_no_service_role_key_frontend
    const offenders: string[] = [];
    const pattern = /service_role[\s\S]{0,150}eyJ[A-Za-z0-9_-]{20,}/;
    for (const f of listProductionHtmlAndJs()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      if (pattern.test(content)) offenders.push(f);
    }
    expect(offenders, 'no frontend file should contain a service_role JWT').toEqual([]);
  });

  test('I6_stripe_webhook_signature_verifier_present: marketplace-webhook implements HMAC SHA-256 verification', async () => {
    // WHY: signature verification is the only barrier against forged webhooks (security skill)
    // STATIC: marketplace-webhook/index.ts must contain all 3 components (per validate_marketplace.webhook_signature)
    const fn = readFileSync(resolve(ROOT, 'supabase', 'functions', 'marketplace-webhook', 'index.ts'), 'utf-8');
    expect(fn, 'reads stripe-signature header').toMatch(/['"]stripe-signature['"]/i);
    expect(fn, 'uses HMAC SHA-256 via crypto.subtle').toMatch(/crypto\.subtle\.(?:importKey|sign)/);
    expect(fn, 'imports key with HMAC + SHA-256').toMatch(/HMAC[\s\S]{0,60}SHA-256/);
    // Raw body must be read via req.text() (not req.json() — that loses signed bytes).
    expect(fn, 'reads raw body via req.text() not req.json()').toMatch(/await\s+req\.text\(\)/);
  });
});
