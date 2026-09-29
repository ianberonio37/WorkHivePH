// w4_action_walk.js - the LOADER a wave-4 ACTION MCP walk runs with `browser_run_code_unsafe { filename }`
// (2026-09-23). Like w4_navhub_walk.js and w4_design_walk.js it stays tiny, because the MCP echoes the loaded
// file into the conversation on EVERY run - the real walker, tools/w4_action_walk.body.js, is fetched from the
// local seeder instead. Parameters: .tmp/w4_args.json ({ id, pages, actions, user, pass, castName, lang,
// width, height, origin, api, anonKey, sigs, hiveId, anon }).
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w4_action_walk.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const src = await res.text();
  const walk = eval('(' + src + '\n)');
  return walk(page);
}
