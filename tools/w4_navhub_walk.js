// w4_navhub_walk.js - the LOADER an MCP walk runs with `browser_run_code_unsafe { filename }`. The MCP echoes the
// whole loaded file into the conversation on every run, so this file stays tiny: it fetches the real walker
// (tools/w4_navhub_walk.body.js, the single source of truth - also what tools/prove_w4_navhub.mjs runs as the
// ratchet) from the local seeder and evaluates it in this same vm. Parameters: .tmp/w4_args.json (served).
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w4_navhub_walk.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const src = await res.text();
  const walk = eval('(' + src + '\n)');
  return walk(page);
}
