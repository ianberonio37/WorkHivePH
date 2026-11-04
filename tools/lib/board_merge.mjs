// board_merge.mjs - splice a --page sweep's graded pages into the full family board, and recompute its aggregates.
// Pure (no browser, no file I/O), so it can be held by a self-test; family_rubric_sweep.mjs --merge calls it.
//
// The rules, each with teeth below:
//   * only pages ON THE BOARD'S ROSTER are taken (a scratch page never enters the full board);
//   * only a CLEAN grade is taken (overall not null, dims present) - an errored page never replaces a good record;
//   * every other page of the board is left exactly as it was;
//   * perDim and the summary counts are recomputed from the merged pages, never added to (a page re-graded must not
//     be counted twice), and the merge is recorded in summary.merged.
//
//   node tools/lib/board_merge.mjs --self-test

export function mergeIntoBoard(board, graded, roster, meta = {}) {
  const out = JSON.parse(JSON.stringify(board));
  const took = Object.keys(graded).filter((f) => roster.includes(f) && graded[f]
    && graded[f].overall !== null && graded[f].overall !== undefined && Array.isArray(graded[f].dims));
  for (const f of took) out.pages[f] = graded[f];
  const agg = {};
  for (const [f, p] of Object.entries(out.pages)) {
    for (const d of (p.dims || [])) {
      const a = (agg[d.dim] ||= { name: ((board.perDim || {})[d.dim] || {}).name, pcts: [], green: 0, fail: 0, na: 0, judged: 0, failPages: [] });
      if (d.kind === 'N/A') a.na++;
      else if (d.kind === 'JUDGED') a.judged++;
      else if (d.pct === null || d.pct === undefined) a.na++;
      else { a.pcts.push(d.pct); if (d.pct === 100) a.green++; else { a.fail++; a.failPages.push(`${f.replace('.html', '')} ${d.pct}`); } }
    }
  }
  for (const a of Object.values(agg)) { a.mean = a.pcts.length ? Math.round(a.pcts.reduce((s, x) => s + x, 0) / a.pcts.length) : null; delete a.pcts; }
  const ov = Object.values(out.pages).map((p) => p.overall).filter((v) => v !== null && v !== undefined);
  out.perDim = agg;
  out.summary = Object.assign({}, out.summary, {
    measuredPages: ov.length, mean: ov.length ? Math.round(ov.reduce((s, v) => s + v, 0) / ov.length) : null,
    ge90: ov.filter((v) => v >= 90).length, ge85: ov.filter((v) => v >= 85).length,
    pageErrors: Object.values(out.pages).reduce((s, p) => s + (p.errors ? p.errors.length : 0), 0),
  });
  if (took.length) out.summary.merged = (out.summary.merged || []).concat([{ pages: took, ...meta }]);
  return { board: out, took, refused: Object.keys(graded).filter((f) => !took.includes(f)) };
}

function selfTest() {
  const fails = [];
  const dim = (d, kind, pct) => ({ dim: d, kind, pct });
  const board = { summary: { measuredPages: 2, mean: 90, ranAt: 'T0', identity: 'x' },
    perDim: { I1: { name: 'Core Web Vitals' } },
    pages: { 'a.html': { overall: 100, dims: [dim('I1', 'MEASURED', 100)] }, 'b.html': { overall: 80, dims: [dim('I1', 'MEASURED', 60)] } } };
  const graded = {
    'about/index.html': { overall: 95, dims: [dim('I1', 'MEASURED', 100), dim('D2', 'MEASURED', 100)] },
    'scratch.html': { overall: 99, dims: [dim('I1', 'MEASURED', 100)] },
    'feedback/index.html': { overall: null, error: 'no result' },
  };
  const roster = ['a.html', 'b.html', 'about/index.html', 'feedback/index.html'];
  const { board: m, took, refused } = mergeIntoBoard(board, graded, roster, { ranAt: 'T1' });
  if (JSON.stringify(took) !== JSON.stringify(['about/index.html'])) fails.push(`only the clean roster page is taken: ${took}`);
  if (!refused.includes('scratch.html') || !refused.includes('feedback/index.html')) fails.push(`an off-roster page and an errored grade are refused: ${refused}`);
  if (m.pages['scratch.html'] || m.pages['feedback/index.html']) fails.push('a refused page must not enter the board');
  if (JSON.stringify(m.pages['b.html']) !== JSON.stringify(board.pages['b.html'])) fails.push('an untouched page must be left exactly as it was');
  if (m.summary.measuredPages !== 3 || m.summary.mean !== 92) fails.push(`the summary is recomputed from the pages: ${JSON.stringify(m.summary)}`);
  if (m.perDim.I1.green !== 2 || m.perDim.I1.fail !== 1 || m.perDim.I1.mean !== 87 || m.perDim.I1.name !== 'Core Web Vitals') fails.push(`perDim recomputed: ${JSON.stringify(m.perDim.I1)}`);
  if (!m.perDim.D2 || m.perDim.D2.green !== 1) fails.push('a dim only the merged page carries joins perDim');
  if (!m.summary.merged || m.summary.merged[0].ranAt !== 'T1' || m.summary.ranAt !== 'T0') fails.push('the merge is recorded, and the full run’s ranAt is kept');
  // merging the same page twice must not double-count it
  const again = mergeIntoBoard(m, { 'about/index.html': graded['about/index.html'] }, roster, { ranAt: 'T2' }).board;
  if (again.summary.measuredPages !== 3 || again.perDim.I1.green !== 2) fails.push('a re-merge of the same page must not count it twice');
  if (board.pages['about/index.html']) fails.push('the input board must not be mutated');
  console.log(fails.length ? 'FAIL board_merge self-test - ' + fails.join('; ')
    : 'self-test OK: only clean roster pages taken, off-roster and errored grades refused, untouched pages kept, summary and perDim recomputed (no double count on a re-merge), the merge recorded, the input unmutated');
  return fails.length ? 1 : 0;
}

if (process.argv[1] && process.argv[1].replace(/\\/g, '/').endsWith('tools/lib/board_merge.mjs') && process.argv.includes('--self-test')) {
  process.exit(selfTest());
}
