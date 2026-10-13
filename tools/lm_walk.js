// lm_walk.js - the LOADER an LLM-layer (§LM) MCP walk runs with `browser_run_code_unsafe { filename }` (2026-10-07).
// Tiny on purpose (the MCP echoes the loaded file on every run): it fetches tools/lm_walk.body.js from the local
// seeder and runs it in this vm. Parameters: .tmp/lm_args.json, written by tools/lm_walk_args.py <id>.
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/lm_walk.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const walk = eval('(' + (await res.text()) + '\n)');
  return walk(page);
}
