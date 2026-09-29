// w4_design_audit.js - the LOADER the audit lens runs with `browser_run_code_unsafe { filename }` (2026-09-15).
// Like w4_design_walk.js it stays tiny (the MCP echoes the loaded file into the conversation on every run) and fetches
// the real probe, tools/w4_design_audit.body.js, from the local seeder. Parameters: .tmp/w4_args.json ({ id, page, lang, origin }).
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w4_design_audit.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the audit body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const src = await res.text();
  const probe = eval('(' + src + '\n)');
  return probe(page);
}
