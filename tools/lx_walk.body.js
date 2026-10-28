// lx_walk.body.js - LAYER-UX browser rows (LXP / LXC), walked through the Playwright MCP as the row's PERSONA, at a
// true phone-390 and a true desktop-1280, one CELL (persona x page) at a time. Loaded by tools/lx_walk.js;
// parameters from .tmp/lx_args.json (tools/lx_walk_args.py). The banker (tools/bank_lx_walk.py) judges each row from
// the raw readings this records - the walk measures, it does not grade.
//
// WHY ONE WALK ANSWERS SEVERAL ROWS. An LX row asks ONE layer's question of ONE page as ONE person. The person, the
// arrival and the settled page are the same for every layer of that cell, so the cell is walked once per viewport and
// each layer is READ through its own lens from that walk - never inferred from another page or another person.
//
// WHAT IS READ, per viewport, on the row's own page (the text a sighted reader sees; for assistive-tech, the text the
// ACCESSIBILITY TREE exposes - aria-hidden and inert subtrees removed, visually-hidden text kept):
//   CA  the crew's own words on the page, and any developer word leaking into it (undefined, NaN, a raw uuid ...)
//   C   the figures shown, whether the page read dated domain rows to make them, and whether it names the PERIOD and
//       the CLOCK (timezone) they belong to
//   D   every provenance line (the source chip and its kin): reachable or not, announced or not, and whether it says
//       BOTH where the data came from and when it last changed
//   LB  time to content, long tasks, DOM size, the largest rendered list, and whether a long list is bounded on screen
//   CI  uncaught exceptions, console errors, and the page's own requests that answered 400/404/5xx or failed - the
//       regressions a person would meet right now
//   L   the write controls this person is offered on the page (the trail behind them is read in postgres by the banker)
//   AV  a SECOND load in which every model function answers a confidently WRONG claim: did the page show it, and did
//       it mark it as a machine's answer (a source, a confidence, an "AI" label, a caveat)
//   A   a THIRD load with the page's data reads refused (503) and a FOURTH with them answering 8 s late: does the page
//       name the failure / offer a retry instead of a blank or a fake "nothing here", and does it show it is working
//
// ★NO LIVE OR PAID MODEL CALL, EVER, AND NOTHING IS SENT. Every model function is answered by a CONTEXT stub (a
// neutral answer on the healthy load, the wrong claim on the AV load), and so is every function whose name says it
// sends, pushes, notifies, emails, exports, invites or charges. ★AND THE WALK WRITES NOTHING: every table write and
// every mutating RPC the page attempts is held (answered 201 []) and recorded - a walk reads; only a person presses.
// ★ITS OWN CONTEXTS. Each viewport is a fresh browser context in the MCP's own browser (true device metrics,
// service workers blocked, storage isolated), so no other walker's session in the shared browser is touched.
async (mcpPage) => {
  const SEED = 'http://localhost:5000';
  let P = {};
  try {
    const ar = await mcpPage.request.get(SEED + '/workhive/.tmp/lx_args.json', { timeout: 8000 });
    if (ar.ok()) P = await ar.json();
  } catch (e) { void e; }
  if (!P.batch || !P.batch.length) return { problems: ['no .tmp/lx_args.json batch - run tools/lx_walk_args.py first'] };
  const started = new Date().toISOString();
  const browser = mcpPage.context().browser();
  const MODEL = new Set(P.modelFns || []);
  const SENDS = /send|push|notify|email|export|invite|payment|webhook|reset|sms|whatsapp|resend/i;
  const MUTATING_RPC = /^(deactivate_|claim_|notify_|set_|report_|ensure_|insert|update|delete|create|mark_|accept_|reject_|grant_|revoke_|publish_|submit_|send_|bind_|record_|log_|dismiss_|award_|redeem_|spend_|charge_|cancel_|archive_|reset_|register_|join_|leave_|invite_|approve_|assign_|complete_|close_|open_|start_|stop_|toggle_|upsert_|save_|add_|remove_|increment_|touch_|apply_)/i;
  const AV_MARK = 'LXW' + Math.random().toString(36).slice(2, 7).toUpperCase();
  const WRONG_TXT = AV_MARK + ' Replace every bearing on all lines today: failure is certain within 24 hours.';
  const NEUTRAL_TXT = 'No new insight for this view right now.';
  const fill = (v) => ({ answer: v, text: v, summary: v, result: v, message: v, briefing: v, reply: v, description: v,
    content: v, draft: v, title: v, headline: v, narrative: v, insight: v, recommendation: v });
  const stubBody = (v) => Object.assign({ ok: true, data: Object.assign(fill(v), { actions: [], items: [], cited: [] }) }, fill(v));

  // the readings that run INSIDE the page
  const READ = (arg) => {
    // the persona, and (since 2026-10-28) the cast's hive as a person reads its name - the S/U reading asks if the page says it
    const persona = arg && typeof arg === 'object' ? arg.persona : arg;
    const hiveName = arg && typeof arg === 'object' ? String(arg.hive || '') : '';
    const at = persona === 'assistive-tech';
    const hiddenUp = (el) => { for (let n = el; n && n.nodeType === 1; n = n.parentElement) { if (n.getAttribute('aria-hidden') === 'true' || n.hasAttribute('inert')) return true; } return false; };
    const shown = (el) => { try { return typeof el.checkVisibility === 'function' ? el.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true }) : el.offsetParent !== null; } catch (e) { return true; } };
    const srOnly = (el) => { try { const cs = getComputedStyle(el); return (cs.position === 'absolute' && (cs.clip !== 'auto' || cs.clipPath !== 'none') && el.getBoundingClientRect().width <= 2); } catch (e) { return false; } };
    // the accessibility-tree text: every text node not under aria-hidden/inert, rendered OR visually hidden
    const srOnlyNear = (el) => { for (let q = el, k = 0; q && k < 4; q = q.parentElement, k++) { if (srOnly(q)) return true; } return false; };
    // ★THE PAGE'S OWN WORDS, NOT THE CHROME AROUND THEM (2026-10-08). The nav hub, the companion launcher and the
    // connectivity widget are shared by 30 pages and graded once as their own subjects; read from <body>, their
    // tile names inflated every page's crew vocabulary and their badge counts became the page's "figures". The
    // page's region is its <main> (every family page has one); a page without one is read whole.
    const root = document.querySelector('main, [role=main]') || document.body;
    const atText = () => {
      const out = [];
      const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = tw.nextNode())) {
        const p = n.parentElement;
        if (!p || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(p.tagName)) continue;
        if (hiddenUp(p)) continue;
        if (!shown(p) && !srOnlyNear(p)) continue;
        const t = (n.nodeValue || '').trim();
        if (t) out.push(t);
      }
      root.querySelectorAll('[aria-label]').forEach((e) => { if (!hiddenUp(e) && !(e.innerText || '').trim()) out.push(e.getAttribute('aria-label')); });
      return out.join(' ').replace(/\s+/g, ' ');
    };
    // long-list-text: PAGE_TEXT of tools/lib/long_list_text.mjs, inlined. This walk times the page's long tasks (its LB
    // verdict), so the rows stay as the page renders them; a long list's off-screen rows carry no innerText
    // (content-visibility:auto), so their words are put back from textContent (SL LB3, 2026-10-22)
    const visText = [document.body.innerText || '', ...[...document.querySelectorAll('.wh-rows-cv > *')]
      .filter((r) => !r.innerText && r.textContent.trim()).map((r) => r.textContent)].join('\n').replace(/\s+/g, ' ').trim();
    const ownText = (root.innerText || '').replace(/\s+/g, ' ').trim();
    const text = at ? atText() : ownText;
    const low = ' ' + text.toLowerCase() + ' ';
    // a plural counts as its word ("assets", "repairs", "shifts" never had - 2026-10-09); the list holds singulars only
    const word = (w) => new RegExp('(^|[^a-z])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:s|es)?([^a-z]|$)', 'i').test(low);
    // CA - the crew's words: tools/ca_crew_words.json, written into this line by tools/sync_ca_crew_words.py (edit the
    // JSON, never this literal - the gate --check fails on drift); developer words leaking are the JARGON list below
    const CREW = ['preventive maintenance', 'work order', 'breakdown', 'downtime', 'spare part', 'spares', 'lockout', 'loto', 'permit', 'ptw', 'shift', 'handover', 'checklist', 'mtbf', 'mttr', 'oee', 'supervisor', 'technician', 'crew', 'hive', 'logbook', 'asset', 'machine', 'inspection', 'repair', 'fault', 'plant', 'maintenance', 'pm schedule', 'pm task', 'root cause', 'failure', 'safety', 'calibration', 'equipment', 'job', 'task', 'team', 'worker', 'report', 'alert', 'log', 'entry', 'record', 'schedule', 'part', 'tool', 'inventory', 'stock', 'restock', 'fix', 'work', 'workshop', 'factory', 'operator', 'foreman', 'engineer', 'manual', 'sop', 'procedure', 'compliance', 'incident', 'hazard', 'mechanical', 'electrical', 'instrumentation', 'skill', 'discipline', 'switchgear', 'facilities', 'production line', 'pump', 'motor', 'bearing', 'compressor', 'conveyor', 'boiler', 'generator', 'lubrication', 'vibration', 'welding', 'electrician', 'mechanic', 'certification'];
    const crew = CREW.filter(word);
    const JARGON = [/\bundefined\b/i, /\bNaN\b/, /\[object Object\]/, /(^|[^a-z])null([^a-z]|$)/i, /\bRLS\b/, /\bJWT\b/, /\bPostgREST\b/i, /\bsupabase\b/i, /\b(TypeError|ReferenceError|SyntaxError)\b/, /\bstack trace\b/i, /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i, /\{\{\s*\w+\s*\}\}/, /\$\{\w+\}/];
    const jargon = [];
    for (const rx of JARGON) { const m = text.match(rx); if (m) jargon.push(m[0].trim().slice(0, 40)); }
    // C - figures and their window
    const FIG = /(?<![\w/.-])\d[\d,]*(?:\.\d+)?(?![\w/.-])/g;
    // ★AN EXAMPLE'S NUMBERS ARE NOT DATA (2026-10-28, hive.html x solo-owner). The no-hive screen says "A hive in use
    // reads like this: ... 8 members · 3 jobs open today ..." - an illustration, marked data-wh-example - and its four
    // numbers made a page that shows this person no data read as one owing provenance for four figures.
    const exampleFigs = [...root.querySelectorAll('[data-wh-example]')]
      .filter((e) => shown(e)).reduce((s, e) => s + ((e.innerText || '').match(FIG) || []).length, 0);
    const figures = Math.max(0, (text.match(FIG) || []).length - exampleFigs);
    const PERIOD = /\b(last|past|previous|this|next)\s+(7|14|30|60|90|\d{1,3})?\s*(day|days|week|weeks|month|months|year|years|hours|hrs)\b|\b(today|yesterday|this week|this month|this year|month[- ]to[- ]date|year[- ]to[- ]date|ytd|mtd)\b|\b(since|between|from)\s+\w+\s+\d{1,2}\b|\b(all[- ]time|lifetime|rolling\s+\d+)\b/i;
    const CLOCK = /\b(UTC|GMT|PHT|PST|Asia\/Manila|Manila time|local time|your time|server time|philippine (?:standard )?time|UTC[+\-]\d|GMT[+\-]\d)\b/i;
    const per = text.match(PERIOD), clk = text.match(CLOCK);
    // a ROLLING window anchored at now ("last 90 days (rolling, ending now)") vs a CALENDAR one ("this week", "today")
    const ROLLING = /\b(last|past|previous)\s+\d+\s*(day|days|week|weeks|month|months|hour|hours|hrs)\b[^.|]{0,60}?\b(rolling|ending now|up to now|until now|to date)\b|\brolling\s+\d+\s*(day|days|week|weeks|month|months)\b/i;
    const CALENDAR = /\b(today|yesterday|this week|this month|this year|month[- ]to[- ]date|year[- ]to[- ]date|ytd|mtd)\b/i;
    // a live count's window is the INSTANT it was read ("as of 08:45 PHT", the source chip, 2026-10-09) - it still owes
    // the clock beside it, so an "as of" with no PHT/UTC fails exactly as before. A SNAPSHOT's window is the instant it
    // was COMPUTED, and saying so with its date is the same claim (2026-10-09, the maturity card: "the daily snapshot ...
    // computed 9 Oct, 11:28 PHT") - "as of"/"computed"/"calculated", an optional "9 Oct," and the HH:MM. A generated
    // REPORT states its instant as "Generated: Oct 9, 2026, 11:53 AM PHT" (project-report's cover, 2026-10-09)
    // - and a stale plan's "plan generated Sep 11, 12:09 PM PHT" (shift-brain, no year: the same claim)
    const INSTANT = /\b(?:as of|computed|calculated|generated:?)\s+(?:[a-z]{3}\s+\d{1,2},(?:\s+\d{4},?)?\s+|\d{1,2}\s+[a-z]{3},?\s+)?(?:at\s+)?\d{1,2}:\d{2}\b/i;
    const rollingM = text.match(ROLLING), calM = text.match(CALENDAR), instM = text.match(INSTANT);
    // D - provenance (tools/prove_lxp_d_provenance.mjs's probe, unchanged in what it counts)
    const sel = '.wh-source-chip, [data-wh-fresh], .wh-freshness, [class*="freshness"], [class*="source-chip"]';
    const chips = [...document.querySelectorAll(sel)];
    const CLAIM = /based on|source|updated|refreshed|as of|live|cached|saved copy|snapshot|last\s+\w+\s+ago|\bago\b/i;
    // + summary (2026-10-09): a disclosure's <summary> is the line a person reads while the rest is folded away -
    // assistant.html states its provenance there, and a scan of p/span/div never looked at it
    const loose = [...document.querySelectorAll('p, span, div, footer, small, summary')].filter((e) => e.children.length === 0 && CLAIM.test(e.textContent || '') && !chips.includes(e)).slice(0, 40);
    const describe = (e) => ({ text: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160), role: e.getAttribute('role'), live: e.getAttribute('aria-live'), visible: shown(e), hidden: hiddenUp(e) });
    const prov = [...chips.map(describe), ...loose.map(describe)];
    const reach = prov.filter((c) => c.visible && !c.hidden);
    const ptxt = reach.map((c) => c.text).join(' | ');
    const d = { chips: chips.length, loose: loose.length, reachable: reach.length,
      announced: reach.filter((c) => c.role === 'status' || c.live).length,
      // (+ "a snapshot / summary / tally / digest OF your ..." - 2026-10-28, ph-intelligence: "the daily snapshot of your
      // hive's records" names its source as plainly as "from your hive's records", and read as saying nothing)
      saysSource: /based on|source|\bfrom (your|the|this|its|their|our|each|every)\b|drawn from|computed from|read from|pulled from|\b(snapshot|summary|tally|digest) of (your|the|this|its|their|our)\b/i.test(ptxt),
      // + calculated / on demand (2026-10-09): engineering-design's "Calculated on demand" says the figures are made at
      // the moment the person runs them - that is their recency, as much as "refreshed" or "as of"
      saysRecency: /updated|refreshed|recomputed|recompute|computed|calculated|on demand|generated|synced|as of|live|\bago\b|just now|moments ago|cached|saved copy|snapshot|today/i.test(ptxt),
      samples: reach.slice(0, 3).map((c) => c.text), hiddenButRendered: prov.filter((c) => c.visible && c.hidden).length,
      // the page's own "how this is computed" disclosures a person can open (renderSourceChip's methodology)
      method: [...document.querySelectorAll('details.wh-method, details[class*="method"], details[class*="how"]')].filter((e) => shown(e) && !hiddenUp(e)).length };
    // LB - what the page renders
    // ★A LIST IS WHAT REPEATS, NOT WHAT IS TAGGED <ul> (2026-10-08). The first cut counted only semantic list
    // containers, and a page painting 400 cards into a <div> grid would have read "largest list 0 items" and passed -
    // a selector is a claim about coverage. Any visible container whose children mostly share one tag and one class
    // is a rendered list, whatever it is called.
    const sig = (c) => c.tagName + '.' + ((typeof c.className === 'string' ? c.className.trim().split(/\s+/)[0] : '') || '');
    const lists = [...document.querySelectorAll('body *')]
      // a <select>'s options and a chart's marks repeat too, and neither is a list a person scrolls through
      .filter((el) => el.children.length >= 6 && !/^(SELECT|DATALIST|OPTGROUP)$/.test(el.tagName) && !(el.closest && el.closest('svg')) && shown(el))
      .map((el) => {
        const kids = [...el.children];
        const counts = {};
        for (const k of kids) counts[sig(k)] = (counts[sig(k)] || 0) + 1;
        const top = Math.max(...Object.values(counts));
        const semantic = /^(UL|OL|TBODY)$/.test(el.tagName) || /^(list|grid|table|feed|listbox)$/.test(el.getAttribute('role') || '');
        return { n: (semantic || top >= kids.length * 0.8) ? top : 0, tag: el.tagName.toLowerCase(), id: el.id || '',
                 cls: (typeof el.className === 'string' ? el.className.split(/\s+/)[0] : '') || '' };
      })
      .filter((x) => x.n > 0)
      .sort((a, b) => b.n - a.n);
    const BOUND_TXT = /load more|show more|see all|view all|showing (the )?(first|latest|most recent|\d)|page \d+ of|next page|\d+\s*[-–]\s*\d+\s+of\s+\d+|first \d+ of|older entries|previous page/i;
    const bounded = BOUND_TXT.test(visText) || !!document.querySelector('.pagination, [class*="paginat"], [class*="load-more"], [id*="load-more"], [aria-label*="next page" i], [aria-label*="load more" i]');
    // RL - the page telling its reader a list is a slice: the walker's own BOUND_TXT plus the phrases
    // tools/prove_consumption_bound.py (SAYS) accepts, so the live reading and the static prover agree on the words
    // (+ "latest 30 events", "... are not listed here" and "at least <n>" - a figure said to be a floor, 2026-10-28: achievements' recent-activity head says exactly
    // that - "latest 30 events; older events are not listed here" - and this read it as a cap shown as a total)
    const SAYS_RX = /showing\s+(?:the\s+)?(?:first|most recent|latest|top)\b|first\s+\d+\s+of\b|most recent\s+\d+|newest\s+\d+|latest\s+\d+\s+(?:events|entries|items|rows|records)\b|(?:is|are)\s+not\s+listed\b|\bat\s+least\s+[+]?[\d,]+|capped\s+at|up\s+to\s+\d+\s+(?:rows|items|entries)|only\s+the\s+(?:first|latest|most recent)|over (?:a|the) (?:slice|sample)|of the latest \d+|\b\d+\s+(?:most recent|newest|latest)\s+of\s+[\d,]+/i;
    const rlSaysM = visText.match(SAYS_RX) || visText.match(BOUND_TXT);
    const rlSays = rlSaysM ? rlSaysM[0].slice(0, 60) : (bounded ? 'a pagination / load-more control' : null);
    // ★A LIST FOLDED AWAY SHOWS NO TOTAL (2026-10-28, dayplanner x phone). The PM rail ("30 of 80 PMs ... Showing the 30
    // most urgent of 80") lives in the open-items panel, which starts FOLDED on a phone: the list and its slice sentence
    // are hidden together, so nothing on screen claims 30 is the total - and the walk read it as "a cap shown as a total".
    // When no slice sentence is visible, find one inside a part of the page that is not rendered, and count the list rows
    // that same folded part holds: the banker accepts it only when the hidden part carries the capped list with it.
    let rlFolded = null;
    if (!rlSays) {
      const shown = (el) => !!el && el.getClientRects().length > 0;
      const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = tw.nextNode(); n && !rlFolded; n = tw.nextNode()) {
        const p = n.parentElement;
        // a script's or a template's text is never shown to anybody - it is not a sentence the page says
        // the same two vocabularies the visible check reads ("Showing the 30 most urgent of 80" is BOUND_TXT's)
        const t = n.textContent || '';
        if (!p || p.closest('script, style, noscript, template') || shown(p) || !(SAYS_RX.test(t) || BOUND_TXT.test(t))) continue;
        let fold = p;
        while (fold.parentElement && fold.parentElement !== document.body && !shown(fold.parentElement)) fold = fold.parentElement;
        // folded, not hidden: a control on screen OPENS it (aria-controls names it, and it says it is not expanded)
        const opener = fold.id ? [...document.querySelectorAll('[aria-controls]')].find((b) => shown(b)
          && b.getAttribute('aria-controls').split(/\s+/).includes(fold.id) && b.getAttribute('aria-expanded') === 'false') : null;
        rlFolded = { says: (t.match(SAYS_RX) || t.match(BOUND_TXT) || [''])[0].slice(0, 60),
                     rows: fold.querySelectorAll('li, tr, [role="listitem"], [class*="card"]').length,
                     at: (fold.id ? '#' + fold.id : fold.tagName.toLowerCase()),
                     opener: opener ? ((opener.getAttribute('aria-label') || opener.innerText || '').trim().slice(0, 40) || '#' + opener.id) : null };
      }
    }
    const nav = performance.getEntriesByType('navigation')[0] || {};
    const lt = window.__lxLongTasks || [];
    // L - the write controls this person is offered
    // a VERB that changes something, whole-word: a tab called "Reports" or "Logbook" is navigation, and "Close" /
    // "Cancel" dismiss a dialog - none of them is a change this person makes (2026-10-08, analytics-report x solo-owner)
    // (+ seen / unsee / snooze / handled / acknowledge / dismiss / resolve / register, 2026-10-28: alert-hub's triage controls
    // change hive state under the actor's name and read as "no write")
    const WRITE_RX = /^(save|submit|add|create|post|log|record|delete|remove|approve|reject|update|edit|send|upload|assign|complete|mark|confirm|publish|claim|join|request|book|order|buy|sell|rate|reply|comment|vote|flag|invite|accept|decline|apply|redeem|reserve|archive|restore|pin|follow|revoke|grant|upgrade|generate|new|seen|unsee|snooze|handled|acknowledge|dismiss|resolve|register)\b(?!s\b)|^\+\s*[a-z]/i;   // "+ Add", "+Schedule" - never "+60": a tappable figure is not a write (2026-10-28)
    const writes = [...document.querySelectorAll('button, [role=button], input[type=submit], a.btn, a[class*="button"]')]
      // a control the page declares LOCAL (data-wh-local: it changes only what is on screen - assistant's New Chat)
      // is not a write, whatever its label; the declaration sits beside the code it describes, for review
      .filter((b) => shown(b) && !hiddenUp(b) && !b.disabled && b.getAttribute('data-wh-local') !== 'true')
      .map((b) => (b.innerText || b.value || b.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim())
      // a label led by a symbol ("👁 Seen", "💾 Save", "✓ Handled") is judged on its first WORD; "+" stays, it is the "+ Add" form
      .map((t) => t.replace(/^[^\p{L}\p{N}+]+/u, ''))
      .filter((t) => t && t.length < 40 && WRITE_RX.test(t));
    // AV - machine output and its honesty marks
    const MODEL_TXT = /\bAI\b|insight|predicted|prediction|forecast|recommend|risk score|anomaly|suggested|generated|summary by|assistant/i;
    // what a model or a pipeline PRODUCED and the page presents as a reading - never a page title or a feature name
    const MODEL_OUT = /\b(AI[- ](suggest\w*|summar\w*|says|answer\w*|draft\w*|generated|insight\w*|recommend\w*|brief\w*)|predicted|prediction|forecast(ed)?|risk score|anomal(y|ies|ous)|recommended (action|next|fix)|likely (cause|failure)|probab(le|ility) of)\b/i;
    const HONESTY = /based on|grounded|source|citation|confidence|estimated|may vary|approximate|assumption|indicative|projected|\brange\b|not a substitute|verify|review before|double-?check|caveat|could ?n.?t|unavailable|try again|low confidence|±|~|AI[- ](generated|drafted|suggest)|machine|model/i;
    const cardOf = (el) => { let c = el; for (let i = 0; i < 4 && c.parentElement && c.parentElement !== document.body; i++) c = c.parentElement; return (c.innerText || '').replace(/\s+/g, ' ').slice(0, 400); };
    const markEl = [...document.querySelectorAll('body *')].find((e) => e.children.length === 0 && (e.textContent || '').includes(window.__lxAvMark || '\u0000'));
    const markCard = markEl ? cardOf(markEl) : '';
    // the first piece of machine output a person can SEE, and whether ITS card carries an honesty mark - a caveat
    // three screens away does not qualify the number in front of the reader
    // ★A FEATURE DESCRIBED IS NOT A READING SHOWN (2026-10-08). The locked ai-quality card says "You will see your
    // fallback rate ... predicted savings" - a sentence ABOUT machine output, not machine output - and it was read as an
    // unmarked prediction. A reading carries a value (a digit) and is not the copy of a gate or a promise.
    const PROMISE = /unlock|locked|will see|will appear|once (enough|you)|coming soon|reach stair|needs? (more|real)|not (yet|enough)|available (at|when|once)/i;
    const modelEl = [...root.querySelectorAll('*')].find((e) => { const t = e.textContent || ''; return e.children.length === 0 && shown(e) && !hiddenUp(e) && !/^H[1-6]$/.test(e.tagName) && MODEL_OUT.test(t) && /\d/.test(t) && !PROMISE.test(t) && t.length < 300; });
    const modelCard = modelEl ? cardOf(modelEl) : '';
    // A - the degraded page's own words
    const FAIL_RX = /try again|could ?n.?t|could not|unavailable|went wrong|failed|offline|no connection|not load|did ?n.?t load|lost connection|reconnect|error loading|can.?t reach|cannot reach|slow|timed? ?out|problem loading/i;
    const RETRY = [...document.querySelectorAll('button, [role=button], a')].filter((b) => shown(b) && /retry|try again|reload|refresh/i.test(b.innerText || b.getAttribute('aria-label') || '')).map((b) => (b.innerText || b.getAttribute('aria-label') || '').trim().slice(0, 30));
    const EMPTY_RX = /\bno [a-z ]{2,30} yet\b|nothing (here|to show|yet)|\b0 (results|items|entries|records)\b|is empty|no data/i;
    const busy = !!document.querySelector('[aria-busy="true"]') || [...document.querySelectorAll('[class*="spinner"], [class*="skeleton"], [class*="loading"], .loader')].some(shown);
    const LOADING_RX = /\b(loading|please wait|fetching|getting your|one moment|checking|computing|calculating|preparing|syncing|refreshing|crunching|gathering|working on)\b|…\s*$|\.\.\.\s*$/i;
    // F - the page's RENDER CONTRACT: the shapes, the states and the escapes it promises (2026-10-28). The LXP F rows were
    // read by hand through the chrome-devtools MCP (2026-10-06); the cube asks the same sentence of every production
    // cell, so the walk takes the same reading itself and every cell is judged on one set of checks. Sizes are LAYOUT
    // sizes (offsetWidth/Height): a transform:scale on chrome shrinks the rect of a real 44px control.
    // in the accessibility tree: no aria-hidden/inert above it, and RENDERED - an ancestor's display:none removes the whole
    // subtree (assistant.html keeps one h1 per screen and shows one screen; reading the h1's OWN display counted both,
    // 2026-10-28). checkVisibility() walks the ancestors and still counts a clipped sr-only node, which IS exposed.
    const exposed = (el) => { if (hiddenUp(el)) return false; try { return typeof el.checkVisibility === 'function' ? el.checkVisibility({ visibilityProperty: true }) : el.getClientRects().length > 0; } catch (e) { return true; } };
    const INTER = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], [role=switch], [tabindex]:not([tabindex="-1"])';
    const inter = [...document.querySelectorAll(INTER)].filter((e) => e instanceof HTMLElement && shown(e) && exposed(e) && !e.disabled);
    const nameOf = (e) => ((e.getAttribute('aria-label') || '').trim()
      || (e.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean).map((id) => (document.getElementById(id) || {}).textContent || '').join(' ').trim()
      || (e.labels && e.labels.length ? [...e.labels].map((l) => l.textContent).join(' ').trim() : '')
      || (e.innerText || '').trim() || (e.getAttribute('title') || '').trim()
      || [...e.querySelectorAll('img[alt], svg[aria-label]')].map((i) => i.alt || i.getAttribute('aria-label')).join(' ').trim()
      || (/^(submit|button|reset)$/i.test(e.type || '') ? (e.value || '').trim() : '')
      || (e.getAttribute('placeholder') || '').trim());
    const tag = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '');
    // ★WHERE A TAP LANDS, BY THE RULES tools/prove_viewport_overflow.mjs ALREADY HOLDS - one rule, not two (2026-10-28).
    // The first cut measured each number's text box and failed achievements on its "+20" figures (22x15) - which answer
    // a 48px area through utils.js's empty positioned ::after, as WCAG 2.5.8 counts it. So, as that prover does: only an
    // ACTIONABLE element is a target (a tabindex region is read, not tapped), a positioned generated pseudo box widens it,
    // a checkbox's target is its label, and a link inside prose is the inline exception.
    const ACT_ROLE = /^(button|link|tab|switch|checkbox|radio|menuitem|menuitemcheckbox|menuitemradio|option|combobox|slider|spinbutton)$/;
    const actionable = (e) => (e.tagName === 'A' ? e.hasAttribute('href') : /^(BUTTON|INPUT|SELECT|TEXTAREA|SUMMARY)$/.test(e.tagName)
      || ACT_ROLE.test((e.getAttribute('role') || '').toLowerCase()) || e.hasAttribute('onclick'));
    const hitRect = (e) => {
      const r = e.getBoundingClientRect();
      let L = r.left, T = r.top, Rt = r.right, B = r.bottom;
      try {
        const st = getComputedStyle(e);
        if (st.position !== 'static') {
          const bl = parseFloat(st.borderLeftWidth) || 0, bt = parseFloat(st.borderTopWidth) || 0;
          const br = parseFloat(st.borderRightWidth) || 0, bb = parseFloat(st.borderBottomWidth) || 0;
          for (const pe of ['::before', '::after']) {
            const ps = getComputedStyle(e, pe);
            if (!ps || ps.content === 'none' || ps.content === 'normal' || ps.position !== 'absolute'
              || ps.display === 'none' || ps.pointerEvents === 'none' || ps.visibility === 'hidden') continue;
            const t = parseFloat(ps.top), l = parseFloat(ps.left), rr = parseFloat(ps.right), b = parseFloat(ps.bottom);
            if ([t, l, rr, b].some((x) => !isFinite(x))) continue;
            L = Math.min(L, r.left + bl + l); T = Math.min(T, r.top + bt + t);
            Rt = Math.max(Rt, r.right - br - rr); B = Math.max(B, r.bottom - bb - b);
          }
        }
      } catch (_) { /* the element's own box stands */ }
      if (/^(checkbox|radio)$/i.test(e.type || '')) {
        const lab = e.closest('label') || (e.id ? document.querySelector('label[for="' + CSS.escape(e.id) + '"]') : null);
        if (lab && shown(lab)) { const q = lab.getBoundingClientRect(); L = Math.min(L, q.left); T = Math.min(T, q.top); Rt = Math.max(Rt, q.right); B = Math.max(B, q.bottom); }
      }
      return [Math.round(Rt - L), Math.round(B - T)];
    };
    const inProse = (e) => { if (e.tagName !== 'A') return false; const par = e.closest('p,li,small,figcaption,td'); return !!par && (par.textContent || '').trim().length > (e.textContent || '').trim().length + 12; };
    // a link inside a clipped sr-only region (index's crawlable tool-catalog mirror, 2026-10-28) is reached by keyboard and
    // by crawlers, never by a pointer - 2.5.8 is about pointer targets, so the ANCESTOR's clip counts too, not only its own
    const small = inter.filter((e) => actionable(e) && !inProse(e) && !srOnlyNear(e)).map((e) => [e, ...hitRect(e)])
      .filter(([, w, h]) => w >= 8 && h >= 8 && (w < 24 || h < 24))   // under 8px is collapsed or visually hidden, not a target
      .map(([e, w, h]) => `${tag(e)} "${nameOf(e).slice(0, 24)}" ${w}x${h}`);
    const unnamed = inter.filter((e) => actionable(e) && !nameOf(e)).map(tag);
    const vw0 = innerWidth, docW = document.documentElement.scrollWidth;
    const inScroll = (el) => { for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) { const ox = getComputedStyle(n).overflowX; if (ox !== 'visible') return true; } return false; };
    const overflow = docW > vw0 + 1 ? [...document.querySelectorAll('body *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > vw0 + 1 && shown(e) && !inScroll(e) && !e.closest('table, svg, pre, [role=toolbar]'); })
      .slice(0, 3).map((e) => `${tag(e)} reaches ${Math.round(e.getBoundingClientRect().right)}px`) : [];
    const h1s = [...document.querySelectorAll('h1, [role=heading][aria-level="1"]')].filter(exposed);
    const mainEl = document.querySelector('main, [role=main]');
    const skip = [...document.querySelectorAll('a[href^="#"]')].find((a) => /skip/i.test((a.textContent || '') + ' ' + (a.getAttribute('aria-label') || '')));
    const idCount = {};
    document.querySelectorAll('[id]').forEach((e) => { if (e.id) idCount[e.id] = (idCount[e.id] || 0) + 1; });
    // busy is a claim only where a person can see it: a display:none region marked aria-busy is not "stuck" on screen
    const stuckEl = [...document.querySelectorAll('[aria-busy="true"], [class*="spinner"], [class*="skeleton"], .loader')].find((e) => shown(e) && exposed(e) && e.getClientRects().length > 0);
    const describeEl = (e) => { const up = e.parentElement && e.parentElement.closest('[id]'); const cls = (typeof e.className === 'string' ? e.className.trim().split(/\s+/)[0] : '') || '';
      return tag(e) + (cls ? '.' + cls : '') + (e.getAttribute('aria-busy') === 'true' ? '[aria-busy]' : '') + (up ? ' in #' + up.id : ''); };
    // an ESCAPE is a way off this page that a person can see: a back / home / close control, a link to another page, or
    // the shared nav hub
    const ESC_RX = /\b(back|home|close|cancel|exit|done|dashboard|menu)\b/i;
    const escapes = [...document.querySelectorAll('a[href], button, [role=button]')].filter((e) => shown(e) && exposed(e)
      && (ESC_RX.test(nameOf(e)) || (e.tagName === 'A' && /(\.html|\/)(\?|#|$)/.test(e.getAttribute('href') || '') && !/^#/.test(e.getAttribute('href') || ''))))
      .map((e) => nameOf(e).slice(0, 30));
    const hubFab = document.getElementById('wh-hub-fab');
    const f = { controls: inter.length, small: small.slice(0, 8), smallCount: small.length, unnamed: unnamed.slice(0, 8),
      unnamedCount: unnamed.length, overflow, docW, vw: vw0, h1: h1s.length, h1Text: h1s[0] ? (h1s[0].innerText || h1s[0].textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60) : null,
      main: !!mainEl && exposed(mainEl), skip: skip ? skip.getAttribute('href') : null,
      skipTarget: skip ? !!document.getElementById(decodeURIComponent(skip.getAttribute('href').slice(1))) : null,
      dupIds: Object.entries(idCount).filter(([, n]) => n > 1).map(([k, n]) => `${k} x${n}`).slice(0, 6),
      stuck: stuckEl ? describeEl(stuckEl) : null,
      escape: [...new Set(escapes)].slice(0, 3).concat(hubFab && shown(hubFab) ? ['the nav hub'] : []) };
    // U on the contract layers (2026-10-28) - what the PERSON can tell, read from the settled page. S: whose rows these are
    // (the hive named, or "your ...") or that something was withheld; L: who did what, on the records or one tap away.
    // (AU's idle prompt and H's offline banner are induced after the healthy read.)
    const SCOPE_YOURS = /\byour (?:own )?(?:hive|team|crew|plant|site|records?|logbook|log|entries|assets?|machines?|jobs?|tasks?|projects?|listings?|shop|schedule|profile|skills?|history|account|resume|day|shift|plan|alerts?|parts?|stock|inventory|reports?|growth|xp|achievements?|badges?)\b/i;
    const REFUSE_RX = /not visible to you|no access|don.?t have access|do not have access|not a member|no longer a member|supervisors? only|only (?:a |the |your )?supervisors?|sign in to|ask (?:its|your|the) (?:manager|supervisor|owner)|belongs to (?:another|a hive)|isn.?t yours|not yours|join (?:a|your) hive|you need a hive|without a hive|no hive yet|create (?:a|your) hive/i;
    // who did what: "logged by X" / "X logged" / a record's meta line "Ben Ocampo · 2h ago"
    // the "<verb> by <Name>" form in any case ("Seen by Rosa dela Cruz" leads with a capital), the name forms case-exact
    const ATTR_BY_RX = /\b(?:logged|added|edited|updated|closed|created|completed|assigned|approved|signed off|reported|posted|recorded|scheduled|resolved|submitted|changed|removed|requested|accepted|rejected|handled|snoozed|seen|acknowledged|hidden|dismissed|marked)\s+by\s+(?:you\b|[A-Z][\w.'-]+)/i;
    const ATTR_RX = /\b(?:You|[A-Z][a-z]+\s+(?:(?:dela|de|del)\s+)?[A-Z][a-z]+)\s+(?:logged|added|edited|updated|closed|created|completed|posted|recorded|approved|changed|requested|replied|reacted)\b|\b[A-Z][a-z]+\s+(?:(?:dela|de|del)\s+)?[A-Z][a-z]+\s*[·•|—–-]\s*[^·•|\n]{0,30}?\b(?:\d+\s*(?:m|h|d|min|mins|hr|hrs|hours?|days?)\s+ago|ago|today|yesterday|just now|\d{1,2}:\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})/;
    // a control whose NAME is about who-did-what (its label, not a card's whole text - an entry card that mentions a fault
    // history is not a history control); logbook's "Team Feed" is where each entry carries the name of who logged it
    const HIST_RX = /^(?:view |see |open |show )?(?:the |this |team |hive )?(?:history|activity(?: log)?|audit(?: log| trail)?|change log|timeline|team feed|who changed)\b/i;
    const histEl = [...document.querySelectorAll('a[href], button, [role=button], [role=tab], summary')].find((e) => shown(e) && !hiddenUp(e)
      && (/audit-log\.html/.test(e.getAttribute('href') || '')
        || [e.getAttribute('aria-label') || '', e.innerText || ''].some((s) => HIST_RX.test(s.replace(/^[^\p{L}\p{N}]+/u, '').trim()))));
    const u = { hiveNamed: !!(hiveName && visText.toLowerCase().includes(hiveName.toLowerCase())) ? hiveName : null,
      yours: (ownText.match(SCOPE_YOURS) || [null])[0], refusal: (visText.match(REFUSE_RX) || [null])[0],
      attrib: (visText.match(ATTR_BY_RX) || visText.match(ATTR_RX) || [null])[0],
      history: histEl ? (histEl.innerText || histEl.getAttribute('aria-label') || histEl.getAttribute('href') || '').replace(/\s+/g, ' ').trim().slice(0, 40) : null };
    return {
      f, u,
      url: location.pathname.split('/').pop(), chars: visText.length, ownChars: ownText.length, region: root === document.body ? 'body' : 'main', atChars: at ? text.length : null,
      worker: localStorage.getItem('wh_last_worker'),
      session: Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || '')),
      vw: innerWidth, mobile: matchMedia('(max-width: 430px)').matches,
      ca: { crew: crew.slice(0, 14), crewCount: crew.length, jargon },
      c: { figures, period: per ? per[0].slice(0, 40) : instM ? instM[0].slice(0, 40) : null, clock: clk ? clk[0].slice(0, 30) : null,
        rolling: rollingM ? rollingM[0].slice(0, 70) : null, calendar: calM ? calM[0].slice(0, 30) : null },
      d,
      rl: { says: rlSays, folded: rlFolded },
      lb: { dcl: Math.round(nav.domContentLoadedEventEnd || 0), load: Math.round(nav.loadEventEnd || 0),
        longTasks: { count: lt.length, total: Math.round(lt.reduce((s, x) => s + x, 0)), max: Math.round(Math.max(0, ...lt)) },
        nodes: document.getElementsByTagName('*').length, maxList: lists[0] || null, bounded },
      l: { writes: [...new Set(writes)].slice(0, 12) },
      av: { modelText: (text.match(MODEL_TXT) || [null])[0], honesty: (text.match(HONESTY) || [null])[0],
        markShown: !!markEl, markCard, markHonest: markCard ? HONESTY.test(markCard.replace(window.__lxAvMark || '', '').replace(/Replace every bearing on all lines today: failure is certain within 24 hours\./, '')) : null,
        modelCard, modelCardHonest: modelCard ? HONESTY.test(modelCard.replace(MODEL_OUT, '')) : null,
        modelLeaf: modelEl ? (modelEl.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160) : null },
      a: { saysFailure: (visText.match(FAIL_RX) || [null])[0], retry: RETRY.slice(0, 3), fakeEmpty: (visText.match(EMPTY_RX) || [null])[0],
        busy, loadingWords: LOADING_RX.test(visText) || null, blank: visText.length < 120 },
    };
  };

  const out = { started, mark: AV_MARK, cells: [] };
  const steps = [];
  for (const cell of P.batch) {
    const layers = new Set(cell.rows.map((r) => r.layer));
    const C = { persona: cell.persona, page: cell.page, vertical: cell.vertical, cast: cell.castName, castRole: cell.castRole,
                rows: cell.rows, path: cell.path, vps: [], problems: [] };
    for (const vp of P.viewports) {
      const V = { viewport: vp.name, problems: [], held: [], stubbed: [], reads: [], http: [], console: [], pageErrors: [], rl: [], scope: [] };
      let ctx = null;
      try {
        ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.mobile,
          hasTouch: !!vp.mobile, deviceScaleFactor: vp.mobile ? 2 : 1, serviceWorkers: 'block', locale: 'en-PH' });
        await ctx.addInitScript(() => {
          try { window.__lxLongTasks = []; new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lxLongTasks.push(e.duration); }).observe({ type: 'longtask', buffered: true }); } catch (e) { void e; }
        });
        // ── modes the routes obey: 'healthy' | 'wrong' (AV) | 'down' (A, not at all) | 'slow' (A, slowly) ──
        let mode = 'healthy';
        // the page the person is ON - every event is tagged with it, so a row is judged from its OWN page's calls
        let curPage = 'index.html';
        const cors = (rq) => ({ 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET, POST, PATCH, DELETE, OPTIONS',
          'access-control-allow-headers': rq.headers()['access-control-request-headers'] || 'authorization, x-client-info, apikey, content-type, prefer, range' });
        await ctx.route('**/functions/v1/**', async (route) => {
          const rq = route.request();
          const fn = (rq.url().split('/functions/v1/')[1] || '').split(/[?/#]/)[0];
          if (rq.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors(rq) });
          if (MODEL.has(fn) || SENDS.test(fn)) {
            V.stubbed.push(mode + ':' + fn);
            if (mode === 'down') return route.fulfill({ status: 503, contentType: 'application/json', headers: cors(rq), body: '{"error":"Service unavailable (the walk refused this call)"}' });
            return route.fulfill({ status: 200, contentType: 'application/json', headers: cors(rq), body: JSON.stringify(stubBody(mode === 'wrong' ? WRONG_TXT : NEUTRAL_TXT)) });
          }
          if (mode === 'down') return route.fulfill({ status: 503, contentType: 'application/json', headers: cors(rq), body: '{"error":"Service unavailable (the walk refused this call)"}' });
          if (mode === 'slow') await new Promise((r) => setTimeout(r, 8000));
          return route.fallback();
        });
        await ctx.route('**/rest/v1/**', async (route) => {
          const rq = route.request();
          const tbl = (rq.url().split('/rest/v1/')[1] || '').split('?')[0];
          const isRpc = tbl.startsWith('rpc/');
          const write = rq.method() !== 'GET' && rq.method() !== 'HEAD' && rq.method() !== 'OPTIONS'
            && (!isRpc || MUTATING_RPC.test(tbl.replace(/^rpc\//, '')));
          if (write) { V.held.push(rq.method() + ' ' + tbl); return route.fulfill({ status: 201, contentType: 'application/json', headers: cors(rq), body: '[]' }); }
          if (mode === 'down') return route.fulfill({ status: 503, contentType: 'application/json', headers: cors(rq), body: '{"message":"Service unavailable (the walk refused this read)"}' });
          if (mode === 'slow') await new Promise((r) => setTimeout(r, 8000));
          return route.fallback();
        });
        const page = await ctx.newPage();
        page.on('pageerror', (e) => { V.pageErrors.push({ mode, pg: curPage, t: Date.now(), msg: String(e.message || e).slice(0, 200) }); });
        page.on('console', (m) => { if (m.type() === 'error') V.console.push({ mode, pg: curPage, t: Date.now(), msg: m.text().slice(0, 200) }); });
        page.on('response', (r) => {
          try {
            const u = r.url();
            if (!/127\.0\.0\.1:54321|localhost:5000/.test(u)) return;
            const st = r.status();
            const isData = /\/rest\/v1\/|\/functions\/v1\//.test(u);
            if (isData && r.request().method() !== 'OPTIONS') V.reads.push({ mode, pg: curPage, st, u: u.replace(/^https?:\/\/[^/]+/, '').split('?')[0].slice(0, 80), m: r.request().method() });
            if (st >= 400) V.http.push({ mode, pg: curPage, st, u: u.replace(/^https?:\/\/[^/]+/, '').slice(0, 120), m: r.request().method() });
            // ── RL: what each read ASKED for (its limit) and what came BACK (PostgREST's Content-Range), so the judge
            // can tell a bound that binds - a slice the page must say is a slice - from one that never reached its cap.
            // Read live because static reading could not resolve a cap that lives in a shared script (2026-10-12).
            if (mode === 'healthy' && st < 400 && /\/rest\/v1\//.test(u)) {
              const rq = r.request(), meth = rq.method();
              const isRpc = /\/rest\/v1\/rpc\//.test(u);
              if ((meth === 'GET' && !isRpc) || (meth === 'POST' && isRpc)) {
                const url = new URL(u);
                const tbl = url.pathname.split('/rest/v1/')[1] || '';
                let lim = url.searchParams.get('limit');
                if (isRpc) { try { const b = JSON.parse(rq.postData() || '{}'); lim = b.p_limit ?? b.limit ?? b.p_max ?? null; } catch (e) { void e; } }
                const cr = (r.headers()['content-range'] || '').trim();
                const m = cr.match(/^(\d+)-(\d+)\/(\d+|\*)$/);
                const got = m ? (+m[2] - +m[1] + 1) : (/^\*\/(\d+|\*)$/.test(cr) ? 0 : null);
                V.rl.push({ pg: curPage, t: tbl.slice(0, 60), lim: lim != null && lim !== '' ? +lim : null, off: +(url.searchParams.get('offset') || 0),
                  got, total: m && m[3] !== '*' ? +m[3] : null, single: /vnd\.pgrst\.object/.test(rq.headers()['accept'] || '') });
                // ── I (a cube row's "this persona may, and may not"): WHICH HIVES' rows each read handed this person -
                // the banker compares them with the cast's own hives and the reads that are public by design
                const pgNow = curPage, tNow = tbl.slice(0, 60);
                // what the read ASKED for (its hive / identity filters, decoded from the query string) and what came BACK
                const q = decodeURIComponent(url.search.replace(/\+/g, ' '));   // a query string's + is a space ("Bryan+Garcia")
                const pick = (col) => [...new Set([...q.matchAll(new RegExp(col + '(?:=|\\.)eq\\.("?)([^,)&"]+)\\1', 'g'))].map((x) => x[2]))].slice(0, 6);
                const asked = { hive: pick('hive_id'), uid: pick('auth_uid'), name: pick('worker_name') };
                r.json().then((b) => {
                  const rows = Array.isArray(b) ? b : (b && typeof b === 'object' ? [b] : []);
                  const withHive = rows.filter((x) => x && typeof x === 'object' && Object.prototype.hasOwnProperty.call(x, 'hive_id'));
                  V.scope.push({ pg: pgNow, t: tNow, rows: rows.length, asked,
                    hives: [...new Set(withHive.map((x) => (x.hive_id === null ? 'null' : String(x.hive_id))))].slice(0, 8) });
                }).catch(() => {});
              }
            }
          } catch (e) { void e; }
        });
        page.on('requestfailed', (rq) => {
          try { const u = rq.url(); if (/127\.0\.0\.1:54321|localhost:5000/.test(u)) V.http.push({ mode, pg: curPage, st: 0, u: u.replace(/^https?:\/\/[^/]+/, '').slice(0, 120), m: rq.method(), fail: (rq.failure() || {}).errorText }); } catch (e) { void e; }
        });
        const read = async () => page.evaluate(READ, { persona: cell.persona, hive: cell.castHive || '' }).catch((e) => ({ error: String(e.message || e).slice(0, 120), chars: 0 }));
        const settle = async (min = 300, tries = 8) => {
          let r = await read(); let prev = -1;
          for (let i = 0; i < tries && (r.chars < min || r.chars !== prev); i++) { prev = r.chars; await page.waitForTimeout(1200); r = await read(); }
          return r;
        };
        const first = cell.path[0];
        const atPath = (h) => new RegExp('/' + String(h).split('.').join('[.]') + '(?:[?#]|$)');
        // ── a RETURNER comes back to a session that has EXPIRED - the wall must not trust it ──
        if (cell.persona === 'returner') {
          await page.goto(`${P.origin}/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
          V.returner = await page.evaluate(({ name }) => {
            try {
              const k = Object.keys(localStorage).find((x) => /^sb-.*-auth-token$/.test(x)) || 'sb-127-auth-token';
              const stale = { access_token: 'expired.' + Date.now(), refresh_token: 'expired', expires_at: Math.floor(Date.now() / 1000) - 21 * 86400, token_type: 'bearer', user: { id: '00000000-0000-0000-0000-000000000000' } };
              localStorage.setItem(k, JSON.stringify(stale));
              localStorage.setItem('wh_last_worker', name);
              return { seededStaleSessionDaysAgo: 21 };
            } catch (e) { return { error: String(e) }; }
          }, { name: cell.castName }).catch((e) => ({ error: String(e.message || e).slice(0, 80) }));
        }
        const hasSession = () => page.evaluate(() => Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || '') && !/expired\./.test(localStorage.getItem(k) || ''))).catch(() => false);
        // ★A VISITOR IS WALKED SIGNED OUT (2026-10-28). The anon persona - 2,948 cube rows - had no path of its own: every
        // cell went through the wall and signed in, so a visitor's page would have been judged as a member's (the same
        // wrong-person reading as the worker rows walked as a supervisor). The context is fresh for each viewport, so no
        // session exists; the visitor arrives straight on the route, and every hop must STILL hold no session.
        const anon = cell.persona === 'anon';
        let sess = anon;
        if (!anon) {
        // ── arrive as the person: the wall, then the path ──
        await page.goto(`${P.origin}/index.html?signin=1&return=${first}`, { waitUntil: 'load', timeout: 45000 }).catch(() => {});
        await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
        const wallShown = await page.locator('#si-username').isVisible().catch(() => false);
        if (cell.persona === 'returner') V.returner = Object.assign(V.returner || {}, { wallShown });
        const w0 = await read();
        steps.push({ cell: cell.persona + ':' + cell.page, page: 'index.html', viewport: vp.name, chars: w0.chars, identityKept: true, note: 'the sign-in wall' });
        }
        for (let attempt = 1; attempt <= 2 && !sess; attempt++) {
          if (attempt === 2) {
            V.problems.push('the first sign-in left no session; tried the wall once more');
            await page.goto(`${P.origin}/index.html?signin=1&return=${first}`, { waitUntil: 'load', timeout: 45000 }).catch(() => {});
            await page.waitForSelector('#si-username', { state: 'visible', timeout: 30000 }).catch(() => {});
          }
          if (await page.locator('#si-username').isVisible().catch(() => false)) {
            await page.fill('#si-username', cell.user, { timeout: 8000 }).catch(() => {});
            await page.fill('#si-password', cell.pass, { timeout: 8000 }).catch(() => {});
            await page.click('#si-btn', { timeout: 10000 }).catch(() => page.press('#si-password', 'Enter').catch(() => {}));
          }
          for (let i = 0; i < 30 && !sess; i++) { sess = await hasSession(); if (!sess) await page.waitForTimeout(1000); }
        }
        if (!sess) { V.problems.push(`not signed in as ${cell.castName} - no session after the wall (tried twice); this viewport proves nothing`); throw new Error('signed out'); }
        if (!anon) await page.waitForTimeout(1200);
        // ★a page about ONE thing is opened on one thing (2026-10-09): the query its own inbound link composes
        // (?worker= from a marketplace seller link, ?project_id= from Project Manager's Print report), written by
        // lx_walk_args.arrival() from the database. Opened bare, both pages showed only "No ... specified".
        const arrive = (p) => ((cell.arrive || {})[p] || '');
        for (const p of cell.path) {
          curPage = p;
          const here = await page.evaluate(() => location.pathname.replace(/^\/workhive\//, '').replace(/^\//, '')).catch(() => '');
          if (here !== p || arrive(p)) await page.goto(`${P.origin}/${p}${arrive(p)}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => V.problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`));
          let r = p === cell.page ? await settle(300, 10) : await settle(200, 2);
          // ★A HOP READ MID-RENDER IS NOT A LOST IDENTITY (2026-10-12, skillmatrix x returner at 390). The first hop after
          // the wall is the wall's own page (index.html), so the walk does not navigate - and it read the page while it
          // was still swapping the wall for the home view: 0 characters after two 1.2 s tries, recorded as "identity did
          // not survive every hop", which turned six readings that held on the row's own page into red receipts. 1280
          // read the same hop at 888 characters. A blank hop gets a longer settle, then one reload; only a hop that is
          // STILL blank after that is a finding.
          if (p !== cell.page && !r.chars) {
            r = await settle(200, 6);
            if (!r.chars) {
              await page.goto(`${P.origin}/${p}${arrive(p)}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
              r = await settle(200, 6);
            }
          }
          // a visitor's identity is KEPT when the hop still holds no session (a page that signed them in would be the finding)
          const kept = anon ? !(await hasSession()) : (!!r.worker && r.worker === cell.castName);
          steps.push({ cell: cell.persona + ':' + cell.page, page: p, viewport: vp.name, chars: r.chars, identityKept: kept,
            note: p === cell.page ? 'the row\'s own page, settled' + (arrive(p) ? ', opened as ' + p + arrive(p) : '') : 'a hop on the row\'s route' });
          if (p === cell.page) V.healthy = r;
        }
        curPage = cell.page;
        if (!V.healthy) { await page.goto(`${P.origin}/${cell.page}${arrive(cell.page)}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {}); V.healthy = await settle(300, 10); }
        // ── L, who did what ONE TAP AWAY (2026-10-28). A register's first screen is its list; who added, changed or
        // completed a record is on the record (asset-hub's detail timeline: "PM completed by ..."). When the settled page
        // names nobody and offers no history control, open the FIRST record the way a person does - one tap - read it,
        // and come back. Writes are held by the route above, so opening a record changes nothing.
        if (cell.rows.some((r) => r.pillar === 'U' && r.layer === 'L') && V.healthy && V.healthy.u && !V.healthy.u.attrib && !V.healthy.u.history) {
          const opened = await page.evaluate(() => {
            const sel = '[data-entry-id], [data-node-id], .asset-card, .entry-card, [role=button][aria-label^="Open"], [onclick*="openDetail"], [onclick*="openModal"], [onclick*="openEntry"]';
            const el = [...document.querySelectorAll(sel)].find((x) => x.getClientRects().length && !x.closest('[aria-hidden="true"], [inert]'));
            if (!el) return null;
            const label = (el.getAttribute('aria-label') || el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);
            el.click();
            return label || '(a record)';
          }).catch(() => null);
          if (opened) {
            await page.waitForTimeout(2500);
            const r2 = await read();
            V.oneTap = { opened, attrib: (r2.u || {}).attrib || null, history: (r2.u || {}).history || null };
            await page.goto(`${P.origin}/${cell.page}${arrive(cell.page)}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
            await settle(300, 6);
          } else {
            V.oneTap = { opened: null };
          }
        }
        // ── AV: the model answers confidently WRONG; does the page say it is a machine's answer? ──
        if (layers.has('AV')) {
          mode = 'wrong';
          await page.evaluate((m) => { window.__lxAvMark = m; }, AV_MARK).catch(() => {});
          await ctx.addInitScript((m) => { window.__lxAvMark = m; }, AV_MARK);
          await page.reload({ waitUntil: 'load', timeout: 60000 }).catch(() => {});
          V.av = await settle(300, 8);
          V.av.modelCalls = V.stubbed.filter((s) => s.startsWith('wrong:')).length;
          mode = 'healthy';
        }
        // ── A: the service answers not at all, then slowly ──
        if (layers.has('A')) {
          mode = 'down';
          await page.reload({ waitUntil: 'load', timeout: 60000 }).catch(() => {});
          let r = await read();
          // ★A STANDING CONTROL IS NOT AN ANSWER (2026-10-08, alert-hub at 390). The wait ended the moment a "retry"-shaped
          // control was on the page - and alert-hub carries a standing "↻ Refresh" from its first paint, so the phone
          // reading was taken a breath after reload, still loading, and read as "no failure words". Wait for the page
          // to SAY something, or to stop working (no busy region), for up to 20 s.
          for (let i = 0; i < 20 && !(r.a && (r.a.saysFailure || (!r.a.busy && i >= 4))); i++) { await page.waitForTimeout(1000); r = await read(); }
          V.down = r;
          mode = 'slow';
          await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
          await page.waitForTimeout(2500);
          const early = await read();
          let late = early;
          for (let i = 0; i < 16; i++) { await page.waitForTimeout(1000); late = await read(); if (late.chars >= Math.max(200, (V.healthy.chars || 0) * 0.6) && !late.a.busy) break; }
          V.slow = { early: { chars: early.chars, busy: early.a.busy, loadingWords: early.a.loadingWords }, late: { chars: late.chars, busy: late.a.busy || !!late.a.loadingWords }, healthyChars: V.healthy.chars };
          mode = 'healthy';
        }
        // the layers whose U ("the person can tell") rows this cell answers - only those pay for an induction below
        const uLayers = new Set(cell.rows.filter((r) => r.pillar === 'U').map((r) => r.layer));
        // ── AU, what the PERSON is told (2026-10-28): the platform's own idle path - session-timeout.js's documented
        // WH_IDLE_TIMEOUT_OVERRIDE hook, set before the script runs, on a SECOND tab of this signed-in context so the main
        // reading above was never raced by a prompt. The reading is the one tools/prove_lxp_au_session_identity.mjs takes:
        // is the ending announced (a role), named, and given focus. The hard clear stays at an hour, so nothing signs out.
        if (uLayers.has('AU') && !anon) {
          const p2 = await ctx.newPage();
          try {
            await p2.addInitScript(() => { window.WH_IDLE_TIMEOUT_OVERRIDE = { idle: 1500, hard: 3600000, check: 400 }; });
            await p2.goto(`${P.origin}/${cell.page}${arrive(cell.page)}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
            let idle = null;
            for (let i = 0; i < 20 && !(idle && idle.prompt); i++) {
              await p2.waitForTimeout(700);
              idle = await p2.evaluate(() => {
                const ov = [...document.querySelectorAll('[role=alertdialog], [role=dialog], [role=alert], [aria-live]')]
                  .find((e) => e.getClientRects().length && /still (?:here|there|working)|are you still|sign(?:ed)? (?:you )?out|session|inactive|idle/i.test(e.innerText || ''));
                if (!ov) return { prompt: false };
                const lb = ov.getAttribute('aria-labelledby');
                const name = (ov.getAttribute('aria-label') || (lb ? lb.split(/\s+/).map((id) => (document.getElementById(id) || {}).textContent || '').join(' ') : '')).replace(/\s+/g, ' ').trim();
                return { prompt: true, role: ov.getAttribute('role'), live: ov.getAttribute('aria-live'), name: name.slice(0, 80),
                         focusIn: ov.contains(document.activeElement), text: (ov.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160) };
              }).catch(() => null);
            }
            V.idle = idle || { prompt: false };
          } finally { await p2.close().catch(() => {}); }
        }
        // ── H, what the PERSON is told (2026-10-28): the network goes away under the open page, then comes back. Walk
        // contexts block service workers, so this reads the platform's own signal (offline-banner.js, the hub's connection
        // pill) and counts only what APPEARED - a page whose copy already says "works offline" is not thereby telling anyone.
        if (uLayers.has('H')) {
          const OFF = "you are offline|you'?re offline|\\boffline\\b|no connection|not connected|no internet|lost connection|connection lost|saved copy|reconnecting";
          const offRead = () => page.evaluate((src) => {
            const t = document.body.innerText || '';
            const live = [...document.querySelectorAll('[aria-live], [role=status], [role=alert]')]
              .filter((e) => e.getClientRects().length && new RegExp(src, 'i').test(e.innerText || '')).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 90));
            const all = t.match(new RegExp(src, 'gi')) || [];
            return { n: all.length, live, sample: (t.match(new RegExp('[^.\\n]{0,40}(?:' + src + ')[^.\\n]{0,40}', 'i')) || [null])[0] };
          }, OFF).catch(() => ({ n: 0, live: [], sample: null }));
          const before = await offRead();
          await ctx.setOffline(true).catch(() => {});
          let after = before;
          for (let i = 0; i < 10; i++) { await page.waitForTimeout(600); after = await offRead(); if (after.n > before.n || after.live.length > before.live.length) break; }
          await ctx.setOffline(false).catch(() => {});
          let back = null;
          for (let i = 0; i < 8 && !back; i++) {
            await page.waitForTimeout(600);
            back = await page.evaluate(() => ((document.body.innerText || '').match(/back online|you'?re (?:back )?online|reconnected|connection (?:is )?(?:back|restored)|online again/i) || [null])[0]).catch(() => null);
          }
          V.offline = { said: (after.n > before.n || after.live.length > before.live.length) ? (after.live.find((x) => !before.live.includes(x)) || after.sample) : null,
                        announced: after.live.length > before.live.length, back };
        }
      } catch (err) {
        if (String(err.message || err) !== 'signed out') V.problems.push('the walk threw: ' + String(err.message || err).split('\n')[0].slice(0, 140));
      } finally {
        if (ctx) await ctx.close().catch(() => {});
      }
      C.vps.push(V);
    }
    out.cells.push(C);
  }
  out.finished = new Date().toISOString();
  let wrote = '';
  try {
    const id = 'LXB' + Date.now();
    const r = await mcpPage.request.post(SEED + '/api/w4/steps', { data: { id, steps, records: out } });
    wrote = r.ok() ? (await r.json()).path : `POST /api/w4/steps -> ${r.status()}`;
    out.batchId = id;
  } catch (e) { wrote = 'could not post the receipt: ' + String(e.message || e).slice(0, 80); }
  return { batchId: out.batchId, wrote, cells: out.cells.map((c) => ({ cell: c.persona + ':' + c.page, cast: c.cast,
    vps: c.vps.map((v) => ({ vp: v.viewport, chars: v.healthy && v.healthy.chars, signedIn: v.healthy && v.healthy.session, problems: v.problems.slice(0, 2) })) })) };
}
