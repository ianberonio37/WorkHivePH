"""
build_pillar_pages.py: cluster PILLAR page generator (SEO_AEO_GEO_STRATEGY_V2 Pillar 3.3).
=============================================================================================
Builds the ~3 MISSING topical-authority pillar articles the cluster map (playbook §3.3)
identified: comprehensive hubs that tie each cluster's existing /learn articles together
and link the /tools/ calculator surface. Matches the /learn/ article template exactly
(head + JSON-LD @graph Article/FAQPage/BreadcrumbList + shared styles + header/footer)
so the pages are indistinguishable from the 45 existing articles.

Grounding: content clusters lift organic traffic ~40% via topical authority; every cluster
page links its pillar with keyword-rich anchors [external-topic-cluster-pillar-page-topical-
authority-cont]. Answer-first + a statistic + a cited source per article (Princeton GEO triad,
enforced by tools/extractability_gate.py) [external-generative-engine-optimization-princeton-
playboo].

Output → learn/<slug>/index.html (the live location; publish="." serves /learn/<slug>/).
After running: add each to sitemap.xml + verify with run_platform_checks (extractability,
meta, sitemap gates). Commit is Ian's gate.

RUN:  python tools/build_pillar_pages.py
"""
from __future__ import annotations

import re
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARN = ROOT / "learn"

# The table scroll region is DEFINED by the sweep that maintains it across all 115 public pages, so
# the generator borrows it rather than keeping a second copy that can drift out of step.
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from wrap_public_tables import wrap as _wrap_tables  # noqa: E402
SITE = "https://workhiveph.com"
PUB = "2026-08-05"

# ── shared inline styles (verbatim from the article template) ─────────────────
STYLE = """  <style>
    * { font-family: 'Poppins', sans-serif; } body { background: #162032; color: #F4F6FA; }
    .hex-pattern { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='92' viewBox='0 0 80 92'%3E%3Cpath d='M40 0 L80 23 L80 69 L40 92 L0 69 L0 23 Z' fill='none' stroke='%23ffffff08' stroke-width='1.5'/%3E%3C/svg%3E"); background-size: 80px 92px; }
    .prose-wh { color: rgba(244,246,250,0.78); font-size: 1.05rem; line-height: 1.8; }
    /* craft floor (W46284, 2026-09-16, measured live at 390 and 1280): `small` took the UA default 0.8em of the
       16.8px body and rendered 13.4px - a size off the six-step ramp that no font-size declaration could show,
       because a ramp is what the page RENDERS. And the measure ran to 76ch at 1280, one over the 65-75 floor,
       so the text caps itself; below ~1100px the column is already narrower than the cap and nothing moves. */
    .prose-wh small { font-size: 0.85rem; }
    .prose-wh p, .prose-wh li { max-width: 72ch; }
    .prose-wh h2 { color: #F4F6FA; font-size: 1.75rem; font-weight: 800; line-height: 1.25; letter-spacing: -0.015em; margin-top: 3rem; margin-bottom: 1rem; scroll-margin-top: 80px; }
    .prose-wh h3 { color: #F4F6FA; font-size: 1.25rem; font-weight: 700; margin-top: 2rem; margin-bottom: 0.5rem; }
    .prose-wh p  { margin-bottom: 1.25rem; }
    .prose-wh ul, .prose-wh ol { padding-left: 1.5rem; margin-bottom: 1.25rem; }
    .prose-wh li { margin-bottom: 0.5rem; }
    .prose-wh ul li { list-style: disc; } .prose-wh ol li { list-style: decimal; }
    .prose-wh strong { color: #F4F6FA; font-weight: 700; }
    .prose-wh a { color: #5FCCE8; text-decoration: underline; text-underline-offset: 3px; } .prose-wh a:hover { color: #29B6D9; }
    /* ★THE TEMPLATE WAS BEHIND ITS OWN OUTPUT, AND A REBUILD REVERTED THREE PAGES (2026-09-19,
       W46073). Adding the <main> landmark here meant rebuilding the three pillar pages, and the
       detector ratchet immediately caught all three gaining side-tab x2 and skipped-heading x1 -
       defects the fix_learn_* sweeps had repaired in the OUTPUT files while this generator kept
       emitting them. Every rebuild had been silently reintroducing them. Ported here so the two
       agree: .answer-first and .callout take a full hairline instead of a 3px left edge on a
       rounded box (DESIGN.md's side-tab don't), and the table-of-contents h4 declares
       aria-level=2 so the outline runs h1 -> 2 without a jump. The blockquote below KEEPS its
       left rule: a quotation mark in the margin is what a blockquote IS, and the detector does
       not flag it - the don't is about a CARD wearing a coloured tab, not about a quote. */
    .prose-wh blockquote { border-left: 3px solid #F7A21B; padding: 0.5rem 0 0.5rem 1.25rem; margin: 1.5rem 0; color: rgba(244,246,250,0.7); font-style: italic; background: rgba(247,162,27,0.04); }
    .prose-wh table { width: 100%; border-collapse: collapse; margin: 1.5rem 0; font-size: 0.95rem; }
    .prose-wh th, .prose-wh td { padding: 12px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.08); vertical-align: top; }
    .prose-wh th { background: rgba(31,46,69,0.6); font-weight: 700; color: #F4F6FA; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em;
      /* the [data-table-scroll] wrapper announces a scrollable region and could never scroll: the table is
         pinned to width:100%, so it crushed columns instead - at 390 the headers "Product" and "Paid entry"
         wrapped to THREE lines in 66px (W46083, 2026-09-16). One line here is what makes the wrapper real. */
      white-space: nowrap; }
    .prose-wh code { background: rgba(31,46,69,0.7); border: 1px solid rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 6px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 0.95rem; color: #FDB94A; }
    .toc { background: rgba(31,46,69,0.55); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; padding: 24px 26px; margin: 2rem 0 3rem; }
    .toc h2, .toc h4 { color: rgba(244,246,250,0.55); font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 12px; }
    .toc ol { padding-left: 1.5rem; margin: 0; } .toc li { margin-bottom: 6px; font-size: 0.95rem; }
    .toc a { color: rgba(244,246,250,0.75); text-decoration: none; } .toc a:hover { color: #F7A21B; }
    .answer-first { background: rgba(247,162,27,0.08); border: 1px solid rgba(247,162,27,0.30); border-radius: 8px; padding: 20px 22px; margin-bottom: 2rem; font-size: 1.05rem; line-height: 1.75; color: rgba(244,246,250,0.85); }
    .callout { background: rgba(41,182,217,0.06); border: 1px solid rgba(41,182,217,0.28); border-radius: 8px; padding: 20px 22px; margin: 2rem 0; font-size: 0.95rem; line-height: 1.7; color: rgba(244,246,250,0.78); }
    .callout strong { color: #5FCCE8; }
    .pill { display: inline-block; font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 100px; letter-spacing: 0.05em; text-transform: uppercase; }
    .pill-orange { background: rgba(247,162,27,0.18); color: #F7A21B; border: 1px solid rgba(247,162,27,0.35); }
    .faq-item { background: rgba(31,46,69,0.55); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; margin-bottom: 12px; }
    .faq-item[open] { border-color: rgba(247,162,27,0.35); background: rgba(31,46,69,0.85); }
    .faq-item summary { cursor: pointer; list-style: none; padding: 16px 20px; font-weight: 600; color: #F4F6FA; display: flex; justify-content: space-between; gap: 14px; }
    .faq-item summary::-webkit-details-marker { display: none; }
    .faq-item summary::after { content: '+'; font-size: 1.25rem; color: #F7A21B; } .faq-item[open] summary::after { content: '\\2212'; }
    .faq-item .faq-answer { padding: 0 20px 20px; color: rgba(244,246,250,0.7); line-height: 1.7; font-size: 0.95rem; }
    .author-card { background: rgba(31,46,69,0.5); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; padding: 20px 24px; margin: 2rem 0; display: flex; gap: 16px; align-items: center; }
    .author-card .avatar { width: 52px; height: 52px; border-radius: 50%; background: linear-gradient(135deg, #F7A21B, #FDB94A); display: flex; align-items: center; justify-content: center; font-weight: 800; color: #162032; font-size: 1.05rem; flex-shrink: 0; }
    .author-card .meta p:first-child { font-weight: 700; color: #F4F6FA; font-size: 0.95rem; margin-bottom: 2px; }
    .author-card .meta p:last-child { font-size: 0.85rem; color: rgba(244,246,250,0.5); }
    nav a.nav-link { font-size: 0.95rem; color: rgba(244,246,250,0.82); font-weight: 500; display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 0 0.25rem; } @media (max-width: 400px) { nav.flex { gap: 0.5rem; } } /* control-within-viewport (2026-09-05): at the floor viewport the gap-6 nav pushed 'Sign Up Free' 3px past the edge */ /* 44px targets + Lc 60 at 14px (F1/K2/Z3/C5, 2026-09-05) */ header a, footer a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; } nav a.nav-link:hover { color: #F4F6FA; }
    .breadcrumb { font-size: 0.85rem; color: rgba(244,246,250,0.55); margin-bottom: 1.5rem; }
    .breadcrumb a { color: rgba(244,246,250,0.55); text-decoration: none; } .breadcrumb a:hover { color: #F7A21B; }
    .breadcrumb span { margin: 0 8px; }
  </style>"""

URL_BRIDGE = """  <script>
    (function(){
      if (!location.pathname.startsWith('/workhive/')) return;
      var ROOT_PATHS = ['/learn/', '/engineering-design.html', '/logbook.html', '/pm-scheduler.html',
        '/skillmatrix.html', '/hive.html', '/assistant.html', '/analytics.html'];
      function rewrite(){
        document.querySelectorAll('a[href]').forEach(function(a){
          var h = a.getAttribute('href');
          if (!h || h[0] !== '/') return;
          if (h.indexOf('/workhive/') === 0 || h.indexOf('/brand_assets/') === 0 || h === '/manifest.json') return;
          var matched = false;
          for (var i = 0; i < ROOT_PATHS.length; i++) { if (h === ROOT_PATHS[i] || h.indexOf(ROOT_PATHS[i]) === 0) { matched = true; break; } }
          if (!matched && h !== '/' && h.indexOf('/#') !== 0) return;
          var newHref = '/workhive' + h;
          if (newHref.endsWith('/')) newHref += 'index.html';
          else if (h === '/') newHref = '/workhive/index.html';
          else if (h.indexOf('/#') === 0) newHref = '/workhive/index.html' + h.substring(1);
          a.setAttribute('href', newHref);
        });
      }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', rewrite); else rewrite();
    })();
  </script>"""

GA4 = """  <!-- WorkHive GA4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-ENMGLTFR2J"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-ENMGLTFR2J', { anonymize_ip: true });
  </script>
  <script src="/wh-ga4.js" defer></script>
  <!-- /WorkHive GA4 -->"""


def _jsonld(p: dict) -> str:
    url = f"{SITE}/learn/{p['slug']}/"
    graph = [
        {"@type": "Article", "@id": url + "#article", "headline": p["title"],
         "description": p["description"], "image": f"{SITE}/brand_assets/workhive-logo-transparent.png",
         "author": {"@type": "Organization", "name": "WorkHive Editorial Team", "url": SITE + "/"},
         "publisher": {"@id": SITE + "/#organization"}, "datePublished": PUB, "dateModified": PUB,
         "mainEntityOfPage": url, "inLanguage": "en-PH", "articleSection": p["section"],
         "keywords": p["keywords"]},
        {"@type": "FAQPage", "@id": url + "#faq",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in p["faqs"]]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Learn", "item": SITE + "/learn/"},
            {"@type": "ListItem", "position": 3, "name": p["crumb"], "item": url}]},
    ]
    # Comparison pages carry an ItemList of the products compared: an explicit machine-
    # readable matrix beats making the model reconstruct the comparison from prose
    # [external-programmatic-seo-pages-step-by-step-implementati].
    if p.get("item_list"):
        graph.append({
            "@type": "ItemList",
            "@id": url + "#itemlist",
            "name": p.get("item_list_name", "Products compared"),
            "itemListOrder": "https://schema.org/ItemListUnordered",
            "numberOfItems": len(p["item_list"]),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "item": {"@type": "SoftwareApplication", "name": name,
                          "applicationCategory": "BusinessApplication",
                          "operatingSystem": "Web", **({"url": u} if u else {})}}
                for i, (name, u) in enumerate(p["item_list"])],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=2, ensure_ascii=False)


_ENTITY_RE = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]{1,10}|#\d{2,5});")

# Fields below are html.escape()d before they reach the page, so an HTML entity written
# into one renders as LITERAL TEXT ("Step 1 &mdash; measure" instead of "Step 1 — measure").
# Body `html` is NOT escaped, so entities there are correct — which is exactly why the
# mistake is easy to make and invisible in the source. Caught live on the downtime guide
# (8 occurrences). Fail loudly rather than ship it.
_ESCAPED_FIELDS = ("title", "h1", "crumb", "pill", "description")


def _assert_no_entities(p: dict) -> None:
    bad = []
    for f in _ESCAPED_FIELDS:
        if isinstance(p.get(f), str) and _ENTITY_RE.search(p[f]):
            bad.append(f"{f}={p[f]!r}")
    for s in p.get("sections", []):
        if _ENTITY_RE.search(s.get("h2", "")):
            bad.append(f"section h2={s['h2']!r}")
    for q, _a in p.get("faqs", []):
        if _ENTITY_RE.search(q):
            bad.append(f"faq question={q!r}")
    if bad:
        raise ValueError(
            f"{p['slug']}: HTML entity in an escaped field: it will render as literal text. "
            f"Use the character itself (: … ’). Offenders: " + "; ".join(bad))


# ── SHARED SITE CHROME ────────────────────────────────────────────────────────
# Extracted so tools/build_calc_pages.py renders the SAME shell. The 60 calculator
# pages shipped with none of this — no CSS, header, footer or fonts — which is the
# SXO defect V3 opens with. Import these; never re-author the markup, or the two
# surfaces drift the first time either changes.
HEAD_ASSETS = """  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <!-- display=optional, NOT swap. T160: the learn template shifted 0.384 CLS at 390 - nearly 4x the
       0.1 bar - and the measurement isolated the font swap as the whole cause (0.182 shift at 903ms,
       document.fonts.ready at 907ms; blocking the stylesheet took CLS to 0.000). `optional` gives the
       font ~100ms then never swaps, so the page cannot jump, and it still renders Poppins on a real
       load. This generator hardcoded `swap` and so REVERTED the fix on all three pillar pages every
       time it ran - which is exactly what happened on 2026-09-21 when a rebuild for the RA 11285
       correction silently un-fixed T160 across ph-plant-compliance-guide,
       maintenance-metrics-reliability-guide and start-digital-maintenance-guide. -->
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=optional" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = { theme: { extend: {
      /* the platform's six-step ramp plus one display step, declared where the utilities read it
         (W46084, 2026-09-16): text-sm rendered 14px - 0.4px from 13.6 and 1.2px from 15.2, noise
         rather than a step - and the h1 ran 30 -> 36 -> 43.2px across three breakpoints. Pinning the
         scale here rather than overriding each class matters because `sm:text-4xl` compiles inside a
         media query, and a media query adds no specificity. */
      fontSize: { xs: '0.75rem', sm: '0.95rem', base: '1.05rem', lg: '1.25rem', xl: '1.25rem',
                  '2xl': '1.75rem', '3xl': '2.25rem', '4xl': '2.25rem', '5xl': '2.25rem' },
      colors: {
      orange: { wh: '#F7A21B', dark: '#D88A0E', light: '#FDB94A' },
      blue:   { wh: '#29B6D9', dark: '#1A9ABF', light: '#5FCCE8' },
      navy:   { wh: '#162032', mid: '#1F2E45', light: '#2A3D58' },
      steel: '#7B8794', cloud: '#F4F6FA',
    } } } };
  </script>
  <style>
    /* The header nav must fit the platform's narrowest stated width. Measured at 320px (W46077,
       2026-09-19): documentElement.scrollWidth 328 on a 320 viewport - "Sign Up Free" ended at 327.7,
       so the narrowest phone got a horizontal scrollbar on a public guide. Four 24px gaps cost 96px
       there; .75rem buys back 48 and the row measures inside the viewport. Above 400px the nav keeps
       its full gap-6 rhythm.
       `nav.flex`, not `nav`: the gap being overridden is Tailwind's `gap-6` utility CLASS, and a media
       query adds no specificity - the element-only selector lost to it and still measured 328px.
       The /*wh-brand-header-gap*/ marker is what tools/fix_learn_brand_header.py looks for, so the
       sweep recognises the template's own copy instead of appending a second one after every build. */
    /*wh-brand-header-gap*/@media (max-width:399px){header nav.flex{gap:.75rem;}}
  </style>"""

SITE_HEADER = """<header class="border-b border-white/[0.06]" style="background: rgba(13,24,36,0.85);">
  <div class="max-w-6xl mx-auto px-5 sm:px-8 py-4 flex items-center justify-between">
    <a href="/" class="flex items-center gap-3">
      <img src="/brand_assets/workhive-logo-transparent.png" alt="WorkHive" style="height: 36px; width: auto;" />
      <!-- aria-hidden because the logo's alt already names this link: without it a screen reader
           announces the brand twice, "WorkHive WorkHive" (measured, W46077). The alt carries the name
           at every width, including the phone widths where this span is display:none. -->
      <span class="font-extrabold tracking-tight hidden sm:inline" style="font-size: 1.25rem" aria-hidden="true">WorkHive</span>
    </a>
    <nav class="flex items-center gap-6">
      <a href="/" class="nav-link">Home</a>
      <a href="/learn/" class="nav-link">Learn</a>
      <a href="/?signin=1" class="nav-link" data-i="signin">Sign In</a>
      <a href="/?signup=1" class="nav-link" data-i="signup">Sign Up Free</a>
    </nav>
  </div>
</header>"""

def site_footer(pub: str) -> str:
    return """<footer class="py-10 border-t border-white/[0.06]" style="background: rgba(13,24,36,0.85);">
  <div class="max-w-4xl mx-auto px-5 sm:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-white/60">
    <p>© 2026 WorkHive Platform · workhiveph.com · Last updated <time datetime="%s">%s</time></p>
    <div class="flex items-center gap-6">
      <a href="/" class="hover:text-white/60 transition-colors">Home</a>
      <a href="/#faq" class="hover:text-white/60 transition-colors">FAQ</a>
      <a href="/?signup=1" class="hover:text-white/60 transition-colors" data-i="jointhehive">Join the Hive</a>
    </div>
  </div>
</footer>""" % (pub, pub)


# ── The next action (SXO, V3 §6) ──────────────────────────────────────────────
# 13 content pages ended with nowhere to go: a reader arrives from an AI answer,
# reads to the end, and finds only more reading. Winning the citation is the
# expensive half; losing the visitor at the bottom of the page is the cheap loss.
# Links an ACTION surface (a tool or the join flow) — never another article.
DEFAULT_CTA = ("/?signup=1", "Start free with WorkHive",
               "Free at the worker tier, works offline, no card.")


def cta_block(p: dict) -> str:
    href, label, sub = p.get("cta", DEFAULT_CTA)
    # NOT "&mdash;": this is displayed copy, and an em dash here re-opened the No-Em-Dash
    # ratchet on all three generated pages every time the generator ran.
    return (f'<div class="callout"><strong><a href="{href}">{label}</a></strong>: {sub}</div>')


def _page(p: dict) -> str:
    _assert_no_entities(p)
    e = html.escape
    url = f"{SITE}/learn/{p['slug']}/"
    toc = "\n".join(f'          <li><a href="#{s["id"]}">{e(s["h2"])}</a></li>' for s in p["sections"]) \
        + '\n          <li><a href="#faq">Frequently asked questions</a></li>'
    # A raw <table> in pillar_content is 378px wide and its container is 335px, so an unwrapped one
    # makes the WHOLE DOCUMENT scroll sideways at 320 and 390 (measured: documentElement.scrollWidth
    # 398 at both, W46077). tools/wrap_public_tables.py had already fixed this in the OUTPUT file; the
    # W46073 rebuild then reverted it, which is the same fuse that row named - a sweep that rewrites
    # generated files is a fix with a date on it. Wrapping here, with THAT sweep's own wrap(), keeps
    # one definition of the region and makes a rebuild carry the fix instead of undoing it.
    body = "\n\n      ".join(
        f'<h2 id="{s["id"]}">{e(s["h2"])}</h2>\n      {_wrap_tables(s["html"])[0]}'
        for s in p["sections"])
    faqs = "\n".join(
        f'      <details class="faq-item">\n        <summary>{e(q)}</summary>\n        <div class="faq-answer">{e(a)}</div>\n      </details>'
        for q, a in p["faqs"])
    sources = "\n".join(f"        <li>{s}</li>" for s in p["sources"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="theme-color" content="#F7A21B" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>{e(p['title'])} | WorkHive</title>
  <meta name="description" content="{e(p['description'])}" />
  <meta name="keywords" content="{e(p['keywords'])}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{url}" />
  <link rel="manifest" href="/manifest.json" />

  <meta property="og:title" content="{e(p['title'])}" />
  <meta property="og:description" content="{e(p['description'])}" />
  <meta property="og:image" content="{SITE}/brand_assets/og-social.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:alt" content="WorkHive: Free industrial tools for every Filipino worker" />
  <meta property="og:url" content="{url}" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="WorkHive" />
  <meta property="article:published_time" content="{PUB}T00:00:00+08:00" />
  <meta property="article:modified_time" content="{PUB}T00:00:00+08:00" />
  <meta property="article:author" content="WorkHive Editorial Team" />
  <meta property="article:section" content="{e(p['section'])}" />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{e(p['title'])}" />
  <meta name="twitter:description" content="{e(p['description'])}" />
  <meta name="twitter:image" content="{SITE}/brand_assets/og-social.png" />
  <meta name="twitter:image:alt" content="WorkHive: Free industrial tools for every Filipino worker" />

  <script type="application/ld+json">
{_jsonld(p)}
  </script>

{HEAD_ASSETS}
{STYLE}
{URL_BRIDGE}
{GA4}
</head>
<body class="bg-navy-wh text-white antialiased">

<!-- ★FIFTY-FIVE PUBLIC GUIDES WITH NO <main> AND NO SKIP LINK (2026-09-19, W46073 audit lens, walked on
     the AI-work-assistant guide). Measured: document.querySelector('main') null, [role=main] null, no
     skip link, and the first focusable element is the WorkHive wordmark. So a keyboard or screen-reader
     reader arriving at any guide in the library had to travel the whole header and nav before reaching
     the article, every time, with no landmark to jump to - on the pages this platform publishes to be
     FOUND, which is where a first-time visitor using assistive tech is most likely to meet it.
     Both fixed in the TEMPLATE rather than in 55 files, which is the only version of this fix that
     survives the next rebuild. The skip link matches the platform's shared one in wayfinding.js
     (amber on navy, 44px, hidden until focused) rather than inventing a second look; these pages do
     not load that file, so it is inlined here. -->
<a class="wh-skip-link" href="#wh-main-content"
   style="position:fixed;top:0;left:0;z-index:10001;transform:translateY(-120%);background:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032);padding:0 20px;min-height:44px;display:inline-flex;align-items:center;font-weight:700;font-size:14px;text-decoration:none;border-radius:0 0 10px 0;box-shadow:0 4px 16px rgba(0,0,0,.35);transition:transform .15s cubic-bezier(0.23,1,0.32,1);box-sizing:border-box;"
   onfocus="this.style.transform='translateY(0)'" onblur="this.style.transform='translateY(-120%)'">Skip to main content</a>

{SITE_HEADER}

<main id="wh-main-content"><article class="hex-pattern">
  <div class="max-w-3xl mx-auto px-5 sm:px-8 py-14 lg:py-20">

    <div class="breadcrumb">
      <a href="/">Home</a><span>/</span><a href="/learn/">Learn</a><span>/</span><span>{e(p['crumb'])}</span>
    </div>

    <span class="pill pill-orange">{e(p['pill'])}</span>
    <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight mt-4 mb-4" style="line-height:1.15;">{e(p['h1'])}</h1>
    <!-- W46098 (2026-09-21): this says PUBLISHED, not "Updated", and the distinction is
         load-bearing. The generator writes datePublished = dateModified = PUB, but a later
         edit wave moves dateModified while this byline stays baked at PUB - measured on 5 of
         these 8 pages, which showed a reader 2026-08-05 while telling a crawler 2026-08-24.
         The UPDATE date already reaches the reader through the footer line that
         fix_learn_freshness.py guarantees, lifted from each page's own dateModified. -->
    <p class="text-white/50 text-sm mb-8">By WorkHive Editorial Team · Published {PUB} · {p['readmins']} min read</p>

    <div class="answer-first">{p['answer_first']}</div>

    <div class="toc">
      <h2>On this page</h2>
      <ol>
{toc}
      </ol>
    </div>

    <div class="prose-wh">

      {body}

      <h2 id="faq">Frequently asked questions</h2>

{faqs}

      {cta_block(p)}

      <h2 id="sources">Sources</h2>
      <ul>
{sources}
      </ul>

      <div class="author-card">
        <div class="avatar">WH</div>
        <div class="meta">
          <p>WorkHive Editorial Team</p>
          <p>Practical writing for the Philippine plant floor. Email <a href="mailto:admin@workhiveph.com" style="color:#5FCCE8;">admin@workhiveph.com</a> with corrections or contributions.</p>
        </div>
      </div>

    </div>

    <div class="pt-8 border-t border-white/[0.06] mt-12">
      <a href="/learn/" class="text-sm text-white/55 hover:text-orange-wh transition-colors">&larr; Back to all guides</a>
    </div>

  </div>
</article></main>

{site_footer(PUB)}

<script defer src="../../wh-feedback-fab.js"></script>
</body>
</html>
"""


# ── The sweeps this generator's output must satisfy ──────────────────────────
# ★THIS TEMPLATE HAS FALLEN BEHIND ITS OWN OUTPUT TWICE, AND THE SECOND TIME IT
# TOOK THREE PUBLISHED PAGES WITH IT (~W46153, 2026-09-20). The three pages this
# file emits are the three that missed fix_breadcrumb_contrast (a WCAG AA failure
# live for ten days), fix_learn_chrome (breadcrumb links at 41x19 against 44x44 on
# every sibling) and fix_mono_stack_unify. They were not unlucky: a sweep patches
# learn/*/index.html and a rebuild here silently reverts it, so these three are
# permanently one generation behind every fix the other 51 articles receive.
#
# Four of those fixes are now IN the template above - breadcrumb alpha, the
# breadcrumb span opacity, the TOC label rule and its tag. The rest live in sweeps
# that own their own definition and are idempotent, and duplicating their payload
# here would just create a second copy to drift. So the generator RUNS them, and
# its output is correct by construction rather than by someone remembering.
#
# Adding a new learn-wide sweep? Add it here too, or the pillar pages will miss it.
_POST_BUILD_SWEEPS = (
    "fix_learn_chrome.py",            # bilingual labels + 44px standalone tap targets
    "fix_learn_toc_label.py",         # TOC label styled, selector matches both tags
    "fix_learn_cta_heading.py",       # heading tag agrees with its aria-level
    "fix_learn_callout_rule.py",      # .callout is defined wherever it is used
    "fix_learn_prose_base_size.py",   # .prose-wh carries a base size for its lists
    "fix_breadcrumb_contrast.py",     # breadcrumb colour clears WCAG AA
    "fix_breadcrumb_span_opacity.py",  # no opacity compounded onto that colour
    "fix_mono_stack_unify.py",        # one monospace stack, the one DESIGN.md records
    # A no-op today: the pillar template already carries W46083's th nowrap. It is in the list
    # anyway, because "the template happens to have it" is a fact about the template, not a
    # guarantee about the output — and this generator proved the point on 2026-09-21 by silently
    # reverting T160's display=optional on all three pages. A sweep that RUNS beats a rule someone
    # has to remember. See gate learn-th-nowrap (W46205).
    "fix_learn_th_nowrap.py",         # [data-table-scroll] can only scroll if th holds one line
)


def _run_post_build_sweeps() -> int:
    """Re-apply the idempotent learn sweeps so a rebuild cannot revert them."""
    import subprocess
    here = Path(__file__).resolve().parent
    failed = []
    print("\n  re-applying the learn sweeps so this rebuild does not revert them:")
    for name in _POST_BUILD_SWEEPS:
        script = here / name
        if not script.exists():
            failed.append(f"{name} (MISSING)")
            continue
        r = subprocess.run([_sys.executable, str(script), "--apply"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        tail = (r.stdout or "").strip().splitlines()
        print(f"    {name:<34} {'ok ' if r.returncode == 0 else 'FAIL'} "
              f"{tail[-1].strip()[:70] if tail else ''}")
        if r.returncode != 0:
            failed.append(name)
    if failed:
        print("  SWEEPS THAT DID NOT SUCCEED: " + ", ".join(failed))
        return 1
    return 0


def main() -> int:
    from pillar_content import PILLARS  # sibling data module
    built = []
    for p in PILLARS:
        d = LEARN / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(_page(p), encoding="utf-8")
        built.append(p["slug"])
        print(f"  built /learn/{p['slug']}/  ({len((d/'index.html').read_text(encoding='utf-8'))} bytes)")
    rc = _run_post_build_sweeps()
    print(f"\n{len(built)} pillar page(s) written to learn/. Add to sitemap.xml, then run_platform_checks.")
    return rc


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
