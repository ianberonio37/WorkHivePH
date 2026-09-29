// w4_design_walk.js - the LOADER a design-lens MCP walk runs with `browser_run_code_unsafe { filename }` (2026-09-15).
// Like w4_navhub_walk.js it stays tiny (the MCP echoes the loaded file into the conversation on every run) and
// fetches the real walker, tools/w4_design_walk.body.js, from the local seeder. Parameters: .tmp/w4_args.json
// ({ id, page, lens, user, pass, castName, lang, shotDir, origin }).
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w4_design_walk.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const src = await res.text();
  const walk = eval('(' + src + '\n)');
  return walk(page);
}
