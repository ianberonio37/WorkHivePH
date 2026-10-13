// w3_journey_walk.js - the LOADER a W3-JN journey MCP walk runs with `browser_run_code_unsafe { filename }` (2026-10-07).
// Tiny on purpose (the MCP echoes the loaded file on every run): it fetches tools/w3_journey_walk.body.js from the local
// seeder and runs it in this vm. Parameters: .tmp/w3_args.json { id, mode, psql, files, rows }.
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w3_journey_walk.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const walk = eval('(' + (await res.text()) + '\n)');
  return walk(page);
}
