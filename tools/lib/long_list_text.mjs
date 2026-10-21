// long_list_text.mjs - what a page SAYS includes every row of its long lists (SL LB3, 2026-10-22).
//
// A long list (utils.js whRenderRows long:true, class wh-rows-cv) lets the browser skip drawing the rows that are off
// screen (content-visibility:auto). A skipped row has no innerText, and the page's innerText leaves it out entirely:
// on the live logbook at 390, document.body.innerText held the words of 2 of Bryan Garcia's 20 entries. A prover that
// reads what a page says with innerText saw a tenth of the list - a "this must not appear" check passed over the rest.
//
// A prover that reads a page's text installs ALL_ROWS_DRAWN on its context (or page) before the page loads:
//     await context.addInitScript(ALL_ROWS_DRAWN);
// and every long-list row is drawn, so innerText holds every row a person can scroll to. Find-in-page and the
// accessibility tree always had them; this gives innerText the same.
//
// Never on a prover that MEASURES rendering (task timing, layout shift, paint): there the skipping is the thing being
// measured. Such a prover reads its text with pageText() instead, which leaves the rendering as it is.
// The gate prover-reads-whole-list (tools/validate_prover_reads_whole_list.py) holds both.

export const ALL_ROWS_DRAWN = () => {
  const put = () => {
    if (document.getElementById('wh-prover-all-rows')) return;
    const st = document.createElement('style');
    st.id = 'wh-prover-all-rows';
    st.textContent = '.wh-rows-cv>*{content-visibility:visible!important}';
    (document.head || document.documentElement).appendChild(st);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', put, { once: true });
  else put();
};

// The page's text with the rows it is not drawing put back, read without changing how the page renders: the
// innerText of the page, then the words of each long-list row that has none (a skipped row's innerText is empty).
export const PAGE_TEXT = () => {
  const skipped = [...document.querySelectorAll('.wh-rows-cv > *')].filter((r) => !r.innerText && r.textContent.trim());
  return [document.body.innerText, ...skipped.map((r) => r.textContent.replace(/\s+/g, ' ').trim())].join('\n');
};
export const pageText = (page) => page.evaluate(PAGE_TEXT);
