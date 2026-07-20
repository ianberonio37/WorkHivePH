// arc_w_visual.mjs — Arc W (VISUAL UI/UX): the 9-lens visual-quality probe + scorers.
//
// WHY (VISUAL_UIUX_ROADMAP.md): Arc V proved the "feels shallow / cluttered" instinct is NOT
// interaction-cost (clicks/hops/dead-ends all measured green). Its home is the VISUAL axis:
// depth, focal hierarchy, breathing room, grouping, consistency, dashboard clarity, color/type
// restraint, motion/state craft, iconography. This module makes that axis MEASURABLE: a
// deterministic per-page DOM probe (runs in-browser via page.evaluate) + node-side scorers that
// turn the raw metrics into per-lens FLOORS that ratchet.
//
// THE 9 LENSES (roadmap §"measurement model"):
//   D  depth/elevation     H  focal hierarchy   W  whitespace/clutter   G  grouping/grid
//   C  consistency         V  dashboard clarity  T  color/type restraint M/S motion+state
//   I  iconography
//
// GATE PHILOSOPHY (same staged discipline that calibrated Arc V's L/C/F lenses 3×): "gate the
// STABLE signal, RANK with the soft one." Every proxy here is computed from deterministic
// computed-style / layout numbers (font px, box-shadow, bg-luminance, gaps, element counts) →
// run-to-run stable given the seeded DOM → safe to freeze as a ratchet ceiling/floor. Per-page
// raw metrics are also emitted so the vision-judge can RANK what to fix first; Ian's eye is the
// final arbiter (proxies hold a regression floor, they don't claim "looks crafted").
//
// REUSE (WAT How-to-Operate #1 — apply/extend, never rebuild): the navy ladder
// (--wh-navy/-mid/-light), the 8px --wh-space-* scale, and .wh-skeleton + reduced-motion ALL
// already exist in components.css; Arc W MEASURES adherence to them, it does not reinvent them.
// The harness recipe (signIn/makeHelpers/contexts/@390+1280) is reused from effortless_sweep.mjs.

// ─────────────────────────────────────────────────────────────────────────────
// ARC_W_PROBE — runs INSIDE the page (page.evaluate). Must be fully self-contained
// (no closures over node scope). Returns one raw-metrics record for the current viewport.
// ─────────────────────────────────────────────────────────────────────────────
export const ARC_W_PROBE = () => {
  const VW = window.innerWidth, VH = window.innerHeight || 800;

  // ancestor-aware visibility (same discipline as the Arc V LOAD_PROBE — kills opacity:0 /
  // hidden-ancestor false positives like closed modals).
  const vis = (el) => {
    const b = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    if (!(b.width > 1 && b.height > 1 && s.visibility !== 'hidden' && s.display !== 'none')) return false;
    return !el.checkVisibility || el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true });
  };
  const aboveFold = (el) => { const b = el.getBoundingClientRect(); return b.top < VH && b.bottom > 0; };

  // relative luminance (WCAG) of a CSS color string; null if fully transparent.
  const lum = (rgb) => {
    const m = (rgb || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    if (p.length >= 4 && p[3] === 0) return null;            // fully transparent → no surface
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(p[0]) + 0.7152 * f(p[1]) + 0.0722 * f(p[2]);
  };
  // luminance of the nearest ancestor that actually paints a background (the visual "parent surface").
  const parentSurfaceLum = (el) => {
    let n = el.parentElement;
    while (n && n !== document.documentElement) {
      const L = lum(getComputedStyle(n).backgroundColor);
      if (L != null) return L;
      n = n.parentElement;
    }
    return lum(getComputedStyle(document.body).backgroundColor);
  };

  // ── D — layered depth / surface-tint elevation ─────────────────────────────
  // A card-like surface "floats" if it has a real box-shadow OR sits lighter than its parent
  // surface by ΔL ≥ 0.03 (Material 3 tonal elevation; the dark-mode-correct primary cue). FLAT
  // = neither → coplanar. R0 measured 0/50 + 0/116 shadowed on index/marketplace.
  const CARD_SEL = '.simple-card,.card,[class*="-card"],.panel,[class*="-panel"],.tile,[class*="-tile"],.widget,[class*="-widget"],.modal,.modal-content,[role="dialog"],.wh-card';
  const cardSet = new Set([...document.querySelectorAll(CARD_SEL)].filter(vis));
  const cards = [...cardSet];
  let flat = 0, shadowed = 0, tinted = 0;
  for (const c of cards) {
    const s = getComputedStyle(c);
    const hasShadow = !!s.boxShadow && s.boxShadow !== 'none';
    const ownL = lum(s.backgroundColor);
    const parL = parentSurfaceLum(c);
    const tintLift = (ownL != null && parL != null) && (ownL - parL) >= 0.03;
    if (hasShadow) shadowed++;
    if (tintLift) tinted++;
    if (!hasShadow && !tintLift) flat++;
  }

  // ── text inventory (feeds H focal + T type-restraint) ──────────────────────
  // only elements with their OWN direct text (not wrappers) so the size distribution is real.
  const textEls = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,span,a,button,td,th,li,label,strong,b,div')].filter(el => {
    if (!vis(el)) return false;
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    return own.length > 0;
  });
  const sizes = textEls.map(el => parseFloat(getComputedStyle(el).fontSize)).filter(n => n > 0).sort((a, b) => a - b);
  const medianFont = sizes.length ? sizes[Math.floor(sizes.length / 2)] : 0;
  const maxFont = sizes.length ? sizes[sizes.length - 1] : 0;
  const focalRatio = medianFont ? Math.round(100 * maxFont / medianFont) / 100 : 0;
  const distinctFontSizes = new Set(sizes.map(n => Math.round(n))).size;

  // ── W — whitespace / clutter (gap adherence to the 8px scale) ──────────────
  // The platform owns --wh-space-1..8 (4/8/12/16/24/32...). Gaps OFF that scale read as random
  // density. We count visible layout-container gaps (flex/grid gap + margin-bottom) that are NOT
  // on the scale. Also the headline clutter signal: section-gap ÷ child-gap (≥1.5 = real grouping).
  const SCALE = new Set([0, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64, 72, 80, 96]);
  const LAYOUT_SEL = 'main,section,.section,[class*="-section"],.container,.grid,[class*="-grid"],.row,.col,.stack,[class*="-stack"],.flex,[class*="-list"]';
  const layoutBoxes = [...document.querySelectorAll(LAYOUT_SEL)].filter(vis);
  let offScaleGaps = 0, totalGaps = 0;
  for (const box of layoutBoxes) {
    const s = getComputedStyle(box);
    for (const g of [s.rowGap, s.columnGap]) {
      const v = parseFloat(g);
      if (!isNaN(v) && v > 0) { totalGaps++; if (!SCALE.has(Math.round(v))) offScaleGaps++; }
    }
    const mb = parseFloat(s.marginBottom);
    if (!isNaN(mb) && mb > 0) { totalGaps++; if (!SCALE.has(Math.round(mb))) offScaleGaps++; }
  }
  // grouping-ratio (roadmap W gate): SEPARATOR-gap (the visual vertical gap BETWEEN top-level
  // section blocks in the main column) ÷ GROUP-gap (within-card padding). Rect-based so it captures
  // the real gap regardless of margin vs flex-gap mechanism. < 1.5 = sections sit as tight as a
  // card's interior → the eye reads no grouping ("wall of equal boxes"). (Redesigned 2026-06-25 —
  // the prior version compared a container's intra-rowGap to card padding, both WITHIN-group
  // measures, so it never captured section SEPARATION — it always read ~0.5 regardless of layout.)
  const med = (arr) => { if (!arr.length) return 0; const a = [...arr].sort((x, y) => x - y); return a[Math.floor(a.length / 2)]; };
  const mainCol = document.querySelector('main, [role="main"], .page, #app, .container') || document.body;
  const topKids = [...mainCol.children].filter(el => vis(el) && el.getBoundingClientRect().height > 24);
  const sectionGaps = [];
  for (let i = 1; i < topKids.length; i++) {
    const a = topKids[i - 1].getBoundingClientRect(), b = topKids[i].getBoundingClientRect();
    const g = Math.round(b.top - a.bottom);
    if (g >= 0 && g < 240) sectionGaps.push(g);
  }
  const childGaps = [];
  for (const c of cards) { const v = parseFloat(getComputedStyle(c).paddingTop); if (!isNaN(v) && v > 0) childGaps.push(v); }
  const groupingRatio = (med(childGaps) && sectionGaps.length) ? Math.round(100 * med(sectionGaps) / med(childGaps)) / 100 : 0;

  // ── G — grouping & grid discipline ─────────────────────────────────────────
  // peer-panels: distinct card-like PANELS under ONE parent column (the "wall of widgets" signal,
  // e.g. hive board = 19). With LIST-RUN COLLAPSE: a run of ≥4 same-class card-like siblings is a
  // data LIST (one logical group — 30 asset rows, 27 part cards, 20 log entries), counted as 1, NOT
  // as 30 ungrouped panels. Heterogeneous/distinct siblings each still count, so a genuine wall of
  // different widgets is preserved. (Calibrated 2026-06-25 — evidence: asset-hub's 30 = the asset
  // list, inventory's 27 = the part-card list; the raw count over-flagged lists like Arc V density.)
  const byParent = new Map();
  for (const c of cards) {
    const p = c.parentElement; if (!p) continue;
    const cls = (typeof c.className === 'string' && c.className.trim()) ? c.className.trim() : c.tagName;
    let m = byParent.get(p); if (!m) { m = new Map(); byParent.set(p, m); }
    m.set(cls, (m.get(cls) || 0) + 1);
  }
  let maxPeerPanels = 0, maxPeerRaw = 0;
  for (const m of byParent.values()) {
    let panels = 0, raw = 0;
    for (const n of m.values()) { panels += (n >= 4 ? 1 : n); raw += n; }  // ≥4 same-class = a list → 1
    maxPeerPanels = Math.max(maxPeerPanels, panels);
    maxPeerRaw = Math.max(maxPeerRaw, raw);
  }
  const leftEdges = new Set(cards.filter(aboveFold).map(c => Math.round(c.getBoundingClientRect().left / 4) * 4)); // 4px bucket
  const distinctLeftEdges = leftEdges.size;

  // ── C — consistency (per-page component variance; cross-page spread done in the rollup) ────
  const radii = new Set(cards.map(c => Math.round(parseFloat(getComputedStyle(c).borderTopLeftRadius) || 0)));
  const pads = new Set(cards.map(c => Math.round(parseFloat(getComputedStyle(c).paddingTop) || 0)));
  const shadows = new Set(cards.map(c => { const sh = getComputedStyle(c).boxShadow; return sh === 'none' ? 'none' : sh.slice(0, 40); }));

  // ── T — color & type restraint + V — dashboard clarity (accent-hue diversity) ──────────────
  // distinct accent HUES among above-fold interactive + heading elements (background + bold text).
  // ≤ ~3 (brand + 2) is restrained; marketplace measured 7. Greys (low chroma) are not accents.
  const accentHue = (rgb) => {
    const m = (rgb || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    if (p.length >= 4 && p[3] < 0.2) return null;
    const [r, g, b] = p, mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    if (mx - mn < 28) return null;                          // near-grey → not an accent
    let h;
    if (mx === r) h = ((g - b) / (mx - mn)) % 6;
    else if (mx === g) h = (b - r) / (mx - mn) + 2;
    else h = (r - g) / (mx - mn) + 4;
    h = Math.round(h * 60); if (h < 0) h += 360;
    return Math.round(h / 30) * 30;                          // 30° buckets
  };
  const interactive = [...document.querySelectorAll('button,a[href],[role="button"],.btn,input,select,textarea')].filter(el => vis(el) && aboveFold(el));
  const headings = [...document.querySelectorAll('h1,h2,h3,h4')].filter(el => vis(el) && aboveFold(el));
  const accentHues = new Set();
  for (const el of interactive) { const h = accentHue(getComputedStyle(el).backgroundColor); if (h != null) accentHues.add(h); }
  for (const el of [...interactive, ...headings]) { const h = accentHue(getComputedStyle(el).color); if (h != null) accentHues.add(h); }
  const distinctAccentHues = accentHues.size;
  // T lens is "≤2 DECORATIVE accent hues" (roadmap) — BRAND (orange ~30°, blue ~180-210°) and
  // SEMANTIC STATUS (red 0°, amber 30-60°, green 120-150°) hues are the design system + functional
  // signals, NOT decorative spend. Count only hues OUTSIDE those bands (purple/cyan/pink/etc.) so
  // the gate measures real chroma sprawl, not the brand+status palette. (Calibrated 2026-06-25.)
  const BRAND_STATUS = new Set([0, 30, 60, 120, 150, 180, 210]);
  const distinctDecorativeHues = [...accentHues].filter(h => !BRAND_STATUS.has(h)).length;
  // accent-element ratio (T): % of above-fold interactive+text that carry an accent fill.
  const accentEls = interactive.filter(el => accentHue(getComputedStyle(el).backgroundColor) != null).length;
  const accentRatio = interactive.length ? Math.round(1000 * accentEls / interactive.length) / 10 : 0;
  // V — status-hue purity: status colors (red/amber/green hues) used as a decorative BACKGROUND on
  // a non-status element dilute the "what's the #1 status?" read. Approx: count above-fold els whose
  // bg hue is in the status bands {0,30(amber),120(green)} but that are plain buttons/links (not
  // .badge/.status/.alert/.pill/.tag). Informational v1 (heuristic) — ranked, gated only by total.
  const STATUS_HUES = new Set([0, 30, 120, 150]);
  const isStatusRole = (el) => /badge|status|alert|pill|tag|chip|label|toast|banner/i.test(el.className || '');
  let statusHueMisuse = 0;
  for (const el of interactive) { const h = accentHue(getComputedStyle(el).backgroundColor); if (h != null && STATUS_HUES.has(h) && !isStatusRole(el)) statusHueMisuse++; }

  // ── M/S — motion + state (page-observable part; the CSS :active/:focus-visible existence is
  //    asserted statically in validate_arc_w_visual.py against components.css) ────────────────
  const controls = [...document.querySelectorAll('button,.btn,a.btn,[role="button"]')].filter(vis);
  const withTransition = controls.filter(el => { const t = getComputedStyle(el).transitionDuration; return !!t && t !== '0s' && !/^0s(,\s*0s)*$/.test(t); }).length;
  const hasSkeleton = !!document.querySelector('.wh-skeleton,.wh-skeleton-row,.skeleton');

  // ── I — iconography consistency ────────────────────────────────────────────
  // how many icon SOURCES coexist (emoji glyph vs inline-SVG vs small <img>) — 1 = unified.
  // Extended_Pictographic counts ©®™ℹ‼⁉ as "emoji" — but those are TYPOGRAPHIC symbols (a footer
  // copyright is not an icon), so strip them + the VS16 selector before judging icon presence.
  const emojiRe = /\p{Extended_Pictographic}/u;
  const NON_ICON = /[©®™ℹ‼⁉️]/g;
  let emojiIcons = 0;
  for (const el of textEls) { const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').replace(NON_ICON, ''); if (emojiRe.test(own)) emojiIcons++; }
  // svgIcons = only genuine ICON-sized SVGs. EXCLUDE non-icon graphics: charts (large/>40px),
  // avatars, rating stars, sparklines, QR — those are data-viz/identity, not the icon SYSTEM.
  const svgIcons = [...document.querySelectorAll('svg')].filter(vis).filter(s => {
    const b = s.getBoundingClientRect();
    if (b.width > 40 || b.height > 40) return false;                 // charts / big graphics
    if (b.width < 10 && b.height < 10) return false;                 // tiny status dots / bullets — decoration, not an icon glyph
    if (s.closest('.wh-avatar,.avatar,[class*="avatar"],.stars,.wh-fb-star,.rating,[class*="chart"],[class*="spark"],[class*="qr"]')) return false;
    return true;
  }).length;
  let imgIcons = 0;
  for (const el of [...document.querySelectorAll('img')].filter(vis)) { const b = el.getBoundingClientRect(); if (b.width <= 56 && b.height <= 56) imgIcons++; }
  // I lens — count GLYPH icon systems only: emoji vs inline-SVG-icon. A small <img> is a logo/avatar/
  // thumbnail, NOT part of the icon SYSTEM (informational imgIcons, not gated). REVERSED 2026-07-19
  // (Ian: "I prefer the emojis now"): the target is now ONE icon system = EMOJI — a page whose icon
  // glyphs are emoji + the central `.ic` library (CSS ::before) = 1 source = pass; a page that still
  // MIXES emoji with leftover inline-SVG ICONS = 2 = flag (the emoji-first rollout drives it to 1).
  const iconSources = [emojiIcons > 0, svgIcons > 0].filter(Boolean).length;

  // is this a KPI/dashboard page? (the H focal gate is "per KPI page" — a chat/feed/log/form page
  // doesn't need a 2.3× hero metric, so focal_floor only gates pages that HAVE a KPI grid.)
  const hasKpiGrid = !!document.querySelector('.simple-row, .sc-hero');

  return {
    vw: VW,
    // D
    cards: cards.length, flat, shadowed, tinted,
    // H
    medianFont, maxFont, focalRatio, distinctFontSizes, hasKpiGrid,
    // W
    offScaleGaps, totalGaps, groupingRatio,
    // G
    maxPeerPanels, maxPeerRaw, distinctLeftEdges,
    // C (per-page sets serialized as sizes; cross-page spread computed node-side from these arrays)
    radii: [...radii], pads: [...pads], shadowVariants: shadows.size,
    // T / V
    distinctAccentHues, distinctDecorativeHues, accentRatio, accentEls, interactiveAboveFold: interactive.length, statusHueMisuse,
    // M/S
    controls: controls.length, withTransition, hasSkeleton,
    // I
    emojiIcons, svgIcons, imgIcons, iconSources,
  };
};

// ─────────────────────────────────────────────────────────────────────────────
// node-side scorers — turn a raw-metrics record into per-lens FLOORS.
// Two ratchet directions (both teeth-provable):
//   • CEILINGS (violation counts; target ↓): depth/whitespace/grouping/color/icon/focal floors.
//   • FLOORS-UP (good things; target ↑): handled in the python gate (CSS :active/:focus-visible).
// ─────────────────────────────────────────────────────────────────────────────

// per-page targets (the "good" thresholds the W-phases drive toward).
export const TARGETS = {
  focalRatio: 2.3,        // H — biggest text ÷ median body (Refactoring UI)
  groupingRatio: 1.5,     // W — separator-gap ÷ group-gap (Gestalt; <1.5 = "wall of equal boxes")
  peerPanels: 6,          // G — ungrouped sibling panels per column (Miller-adjacent)
  decorativeHues: 2,      // T — non-brand, non-status decorative accent hues (Refactoring UI restraint)
  iconSources: 1,         // I — one icon system per view
};

export function scoreArcW(raw) {
  if (!raw || raw.__err) return { __err: (raw && raw.__err) || 'no-probe' };
  const depth_floor = raw.flat;                                                  // flat card-like surfaces
  // H lens — gated "per KPI page" (roadmap): a page with a KPI grid must land the eye on ONE hero
  // metric (max÷median ≥ 2.3). Non-KPI pages (chat/feed/log/form) are EXEMPT — a forced hero is
  // wrong design there; their hierarchy is judged by the vision-judge, not this proxy. (2026-06-25.)
  const focal_floor = (raw.hasKpiGrid && raw.focalRatio > 0 && raw.focalRatio < TARGETS.focalRatio) ? 1 : 0;
  // W lens — the roadmap's stated gate is the grouping-RATIO (separator-gap ÷ within-group gap ≥ 1.5
  // = a real breathing-room signal that the eye reads as "groups"). The raw off-scale-gap COUNT is
  // kept INFORMATIONAL only (raw.offScaleGaps): it's a diffuse computed-marginBottom tally across
  // hundreds of list/row els (inventory: 110/607) that over-flags the platform's tuned de-facto
  // 14px — gating it would force CLS-risky churn of legitimate values for ~zero felt gain. Same
  // calibration discipline that demoted Arc V's raw `density` to informational. (2026-06-25 W2.)
  const whitespace_floor = (raw.groupingRatio > 0 && raw.groupingRatio < TARGETS.groupingRatio) ? 1 : 0;
  const grouping_floor = Math.max(0, raw.maxPeerPanels - TARGETS.peerPanels);    // peer-panels over 6
  const color_floor = Math.max(0, raw.distinctDecorativeHues - TARGETS.decorativeHues); // decorative hues over 2
  const icon_floor = Math.max(0, raw.iconSources - TARGETS.iconSources);         // icon sources over 1
  const lens_floor = depth_floor + focal_floor + whitespace_floor + grouping_floor + color_floor + icon_floor;
  return {
    ...raw,
    depth_floor, focal_floor, whitespace_floor, grouping_floor, color_floor, icon_floor,
    lens_floor,
  };
}

// roll the per-(page,viewport) scored records into the platform scoreboard.
export function rollupArcW(records) {
  const ok = records.filter(r => r.scored && !r.scored.__err);
  const sum = (k) => ok.reduce((s, r) => s + (r.scored[k] || 0), 0);
  // cross-page CONSISTENCY (C lens): distinct component variants platform-wide (radius/pad combos
  // + shadow variants). The ratchet forbids the variant set from GROWING (new cousins of an
  // existing component). Built from the per-page radii/pads arrays.
  const radiusSet = new Set(), padSet = new Set(), comboSet = new Set();
  let shadowVariantMax = 0;
  for (const r of ok) {
    for (const v of (r.scored.radii || [])) radiusSet.add(v);
    for (const v of (r.scored.pads || [])) padSet.add(v);
    for (const a of (r.scored.radii || [])) for (const b of (r.scored.pads || [])) comboSet.add(a + ':' + b);
    shadowVariantMax = Math.max(shadowVariantMax, r.scored.shadowVariants || 0);
  }
  return {
    pages_probed: new Set(ok.map(r => r.page)).size,
    records: ok.length,
    errored: records.length - ok.length,
    // CEILINGS (per-lens platform violation totals; target ↓) — these freeze as baseline ceilings.
    depth_floor: sum('depth_floor'),
    focal_floor: sum('focal_floor'),
    whitespace_floor: sum('whitespace_floor'),
    grouping_floor: sum('grouping_floor'),
    color_floor: sum('color_floor'),
    icon_floor: sum('icon_floor'),
    lens_floor: sum('lens_floor'),                 // the headline Arc W floor (sum of all gated lenses)
    // C lens cross-page spread (ceiling: must not grow)
    consistency_radius_variants: radiusSet.size,
    consistency_pad_variants: padSet.size,
    consistency_combo_variants: comboSet.size,
    consistency_shadow_variants_max: shadowVariantMax,
    // INFORMATIONAL aggregates (ranking only; not gated)
    total_cards: sum('cards'),
    total_flat: sum('flat'),
    total_status_hue_misuse: sum('statusHueMisuse'),
  };
}
