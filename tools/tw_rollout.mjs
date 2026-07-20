/* tw_rollout.mjs — swap the Tailwind CDN <script> (+ its tailwind.config block) for the
 * self-hosted <link href="wh-tw.css"> across the 8 remaining pages. Zero markup/class change.
 * The config block MUST go too — without the CDN, `tailwind.config = {...}` throws
 * "tailwind is not defined". wh-tw.css already bakes in the merged custom theme.
 * Idempotent: skips a page already migrated. Prints a per-page diff summary. */
import fs from 'fs';

const PAGES = ['hive', 'logbook', 'inventory', 'pm-scheduler', 'dayplanner',
               'engineering-design', 'assistant', 'voice-journal'];

const LINK = '<link rel="stylesheet" href="wh-tw.css"><!-- was cdn.tailwindcss.com Play CDN; self-hosted subset, no console warning (tools/tw_extract_build.mjs) -->';
// CDN script, optionally followed by the tailwind.config <script> block.
const RE = /<script src="https:\/\/cdn\.tailwindcss\.com"><\/script>(\s*<script>[\s\S]*?tailwind\.config[\s\S]*?<\/script>)?/;

for (const p of PAGES) {
  const f = p + '.html';
  let t;
  try { t = fs.readFileSync(f, 'utf8'); } catch { console.log(`SKIP ${f} (not found)`); continue; }
  if (t.includes('wh-tw.css')) { console.log(`SKIP ${f} (already migrated)`); continue; }
  if (!RE.test(t)) { console.log(`WARN ${f} — CDN pattern not matched, left untouched`); continue; }
  const hadConfig = /<script src="https:\/\/cdn\.tailwindcss\.com"><\/script>\s*<script>[\s\S]*?tailwind\.config/.test(t);
  const out = t.replace(RE, LINK);
  fs.writeFileSync(f, out);
  const cdnGone = !out.includes('cdn.tailwindcss.com');
  const cfgGone = !/tailwind\.config\s*=/.test(out);
  console.log(`OK   ${f} — CDN removed:${cdnGone}  config-block-removed:${cfgGone}  (had config:${hadConfig})`);
}
