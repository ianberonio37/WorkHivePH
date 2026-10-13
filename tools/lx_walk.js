// lx_walk.js - the LOADER a LAYER-UX (LXP / LXC) MCP walk runs with `browser_run_code_unsafe { filename }` (2026-10-08).
// Tiny on purpose (the MCP echoes the loaded file on every run): it fetches tools/lx_walk.body.js from the local
// seeder and runs it in this vm. Parameters: .tmp/lx_args.json, written by tools/lx_walk_args.py.
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/lx_walk.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const walk = eval('(' + (await res.text()) + '\n)');
  return walk(page);
}
