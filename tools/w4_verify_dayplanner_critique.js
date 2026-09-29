// Loader for the W45908 live verification. Stays tiny because the MCP echoes the loaded file back
// into the conversation on every run; the real probe is fetched from the local seeder.
async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w4_verify_dayplanner_critique.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the probe body: HTTP ${res.status()} (is the seeder up on localhost:5000?)`] };
  const src = await res.text();
  const probe = eval('(' + src + '\n)');
  return probe(page);
}
