// wh-i18n-lite.js — the smallest thing that makes a static public page bilingual.
//
// ★WHY THIS FILE EXISTS: 60 CALCULATOR PAGES CARRIED A COMPLETE FILIPINO DICTIONARY THAT COULD NEVER BE
// APPLIED. Every one of them ends with, verbatim:
//
//     window.WH_FIL_PAGE = { calc_how: 'Paano ito gumagana', ... };
//     if (typeof whI18nApply === 'function' && window.WH_LANG === 'fil') whI18nApply(window.WH_FIL_PAGE);
//
// Both halves of that condition were permanently false, and nothing said so:
//
//   1. `whI18nApply` is defined ONLY in utils.js, and NONE of the 60 pages loads utils.js. The guard
//      `typeof whI18nApply === 'function'` reads as care and is in fact a silent no-op — no error, no
//      console warning, nothing in any gate. A dictionary written, translated and shipped, called by every
//      page, reachable by none.
//   2. `window.WH_LANG` is never SET on those pages either — utils.js is what reads `wh_lang` from
//      localStorage. So even a loaded swapper would have found the language undefined and returned.
//
// A Filipino-first reader met English on all 60 pages of the platform's most public surface.
//
// ★AND THE FIX IS NOT "LOAD utils.js". That file is 362 KB — an app bundle, pulled onto a static SEO
// landing page to swap eight headings, paid for by every English reader on every visit. This file is the
// same contract in the smallest form that honours it: it sets WH_LANG the way the platform sets it, defines
// whI18nApply under the SAME NAME so all 60 existing call sites work unchanged, and merges WH_FIL_COMMON
// when a page happens to have it. A page that later loads utils.js is unaffected: this defines nothing that
// is already defined.
(function whI18nLite() {
  'use strict';
  try {
    if (typeof window.WH_LANG === 'undefined') {
      window.WH_LANG = (localStorage.getItem('wh_lang') === 'fil') ? 'fil' : 'en';
    }
  } catch (_) {                       // private mode: persistence is best-effort, English is the floor
    if (typeof window.WH_LANG === 'undefined') window.WH_LANG = 'en';
  }

  if (typeof window._t !== 'function') {
    // _t(en, fil) - the platform's translator signature, falling back to EN when a phrase has no FIL yet
    window._t = function _t(en, fil) {
      return (window.WH_LANG === 'fil' && fil) ? fil : en;
    };
  }

  // The chrome every PUBLIC page repeats — breadcrumb, footer links, the freshness line. utils.js carries
  // WH_FIL_COMMON for the app's surfaces; the public pages never load it, so the handful of labels they
  // share live here. Natural Taglish, matching the calculator dictionaries: the domain words a Philippine
  // plant says in English stay English on purpose. A page's own dict still wins per key.
  // ★THE TWO WORDS THAT ASK A FILIPINO READER TO ACT WERE THE TWO LEFT IN ENGLISH (walked 2026-09-11,
  // learn hub + articles, FIL). Home and Learn were stamped data-i and swapped correctly; "Sign In" and
  // "Sign Up Free" carried no data-i on any of the 55 learn pages and no key lived here, so the whole
  // corpus rendered Filipino headings above an English call to action - the same shape as the provenance
  // chip that translated only its connective, and the four pages that answered in English under a
  // Filipino heading. The dictionary was complete for everything except the decision.
  // TRANSLATIONS ARE THE PLATFORM'S OWN, NOT MINE: 'Mag-sign In' and 'Mag-sign Up nang Libre' are what
  // i18n/marketplace.json and i18n/marketplace-seller.json already ship for these exact strings, and
  // 'Hive Ko' follows the possessive pattern of platform-actions.json's 'Hive Board Ko'. "Home" stays
  // "Home" because that is what the platform itself says (audit-log.json: 'Balik sa Home').
  window.WH_FIL_PUBLIC = window.WH_FIL_PUBLIC || {
    home: 'Home', learn: 'Matuto', faq: 'Mga madalas itanong', jointhehive: 'Sumali sa Hive',
    lastupdated: 'Huling na-update', readmore: 'Basahin pa', backtolearn: 'Bumalik sa Matuto',
    relatedreading: 'Kaugnay na babasahin', sources: 'Mga sanggunian', bytheeditorialteam: 'Ng WorkHive Editorial Team',
    tryit: 'Subukan ito', calculators: 'Mga calculator', guides: 'Mga gabay', contact: 'Makipag-ugnayan',
    signin: 'Mag-sign In', signup: 'Mag-sign Up nang Libre', myhive: 'Hive Ko',
  };

  if (typeof window.whI18nApply !== 'function') {
    // Swap the text of every [data-i] whose key the dictionary knows. EN is the markup itself, so this is
    // one-way: a reload restores English. A page dict wins per key over the shared common one.
    window.whI18nApply = function whI18nApply(dict) {
      if (window.WH_LANG !== 'fil') return;
      var merged = {};
      var k, src, i;
      // shared public chrome, then the app's common dict if utils.js is present, then the page's own —
      // each layer overriding the last per key, so a page can always say it differently
      var layers = [window.WH_FIL_PUBLIC || {}, window.WH_FIL_COMMON || {}];
      for (i = 0; i < layers.length; i++) {
        src = layers[i];
        for (k in src) if (Object.prototype.hasOwnProperty.call(src, k)) merged[k] = src[k];
      }
      for (k in (dict || {})) if (Object.prototype.hasOwnProperty.call(dict, k)) merged[k] = dict[k];
      var nodes = document.querySelectorAll('[data-i]');
      var swapped = 0;
      for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        var key = el.getAttribute('data-i');
        var val = merged[key];
        if (typeof val !== 'string' || !val) continue;
        // only the element's own text, so a label containing markup is left alone rather than flattened
        // ★AND THE SWAPPED LABEL DECLARES ITS OWN LANGUAGE (2026-09-11). Measured on a learn article in
        // FIL: the nav read "Matuto / Mag-sign In / Mag-sign Up nang Libre" under <html lang="en">, so a
        // screen reader announced Filipino words with English phonetics - WCAG 3.1.2, the same defect
        // C-AO found on platform-actions and ph-intelligence. The whole-document lang is deliberately
        // NOT flipped here: on an article the chrome becomes Filipino while the prose stays English, so
        // lang="fil" on <html> would be as untrue as lang="en" and the primary-language call is Ian's.
        // Language OF PARTS needs no such decision - each element this function actually changed says
        // what it now is, which is exactly what 3.1.2 asks and is true in both directions.
        if (el.children.length === 0) { el.textContent = val; el.lang = 'fil'; swapped++; }
      }
      window.__whI18nSwapped = (window.__whI18nSwapped || 0) + swapped;
      return swapped;
    };
  }
})();
