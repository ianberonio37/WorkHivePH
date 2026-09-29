async (page) => {
  const res = await page.request.get('http://localhost:5000/workhive/tools/w4_probe_wilo_untimed.body.js', { timeout: 8000 });
  if (!res.ok()) return { problems: [`HTTP ${res.status()} loading the probe body`] };
  return eval('(' + (await res.text()) + '\n)')(page);
}
