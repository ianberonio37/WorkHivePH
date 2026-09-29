async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/probe_signin.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`HTTP ${res.status()}`] };
  return eval('(' + (await res.text()) + '\n)')(page);
}
