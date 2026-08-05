"""
build_pillar_pages.py — cluster PILLAR page generator (SEO_AEO_GEO_STRATEGY_V2 Pillar 3.3).
=============================================================================================
Builds the ~3 MISSING topical-authority pillar articles the cluster map (playbook §3.3)
identified — comprehensive hubs that tie each cluster's existing /learn articles together
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

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARN = ROOT / "learn"
SITE = "https://workhiveph.com"
PUB = "2026-08-05"

# ── shared inline styles (verbatim from the article template) ─────────────────
STYLE = """  <style>
    * { font-family: 'Poppins', sans-serif; } body { background: #162032; color: #F4F6FA; }
    .hex-pattern { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='92' viewBox='0 0 80 92'%3E%3Cpath d='M40 0 L80 23 L80 69 L40 92 L0 69 L0 23 Z' fill='none' stroke='%23ffffff08' stroke-width='1.5'/%3E%3C/svg%3E"); background-size: 80px 92px; }
    .prose-wh { color: rgba(244,246,250,0.78); font-size: 1.05rem; line-height: 1.8; }
    .prose-wh h2 { color: #F4F6FA; font-size: 1.75rem; font-weight: 800; line-height: 1.25; letter-spacing: -0.015em; margin-top: 3rem; margin-bottom: 1rem; scroll-margin-top: 80px; }
    .prose-wh h3 { color: #F4F6FA; font-size: 1.2rem; font-weight: 700; margin-top: 2rem; margin-bottom: 0.5rem; }
    .prose-wh p  { margin-bottom: 1.25rem; }
    .prose-wh ul, .prose-wh ol { padding-left: 1.5rem; margin-bottom: 1.25rem; }
    .prose-wh li { margin-bottom: 0.5rem; }
    .prose-wh ul li { list-style: disc; } .prose-wh ol li { list-style: decimal; }
    .prose-wh strong { color: #F4F6FA; font-weight: 700; }
    .prose-wh a { color: #5FCCE8; text-decoration: underline; text-underline-offset: 3px; } .prose-wh a:hover { color: #29B6D9; }
    .prose-wh blockquote { border-left: 3px solid #F7A21B; padding: 0.5rem 0 0.5rem 1.25rem; margin: 1.5rem 0; color: rgba(244,246,250,0.7); font-style: italic; background: rgba(247,162,27,0.04); }
    .prose-wh table { width: 100%; border-collapse: collapse; margin: 1.5rem 0; font-size: 0.95rem; }
    .prose-wh th, .prose-wh td { padding: 12px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.08); vertical-align: top; }
    .prose-wh th { background: rgba(31,46,69,0.6); font-weight: 700; color: #F4F6FA; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .prose-wh code { background: rgba(31,46,69,0.7); border: 1px solid rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 6px; font-family: 'Consolas','Courier New',monospace; font-size: 0.92rem; color: #FDB94A; }
    .toc { background: rgba(31,46,69,0.55); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; padding: 22px 26px; margin: 2rem 0 3rem; }
    .toc h4 { color: rgba(244,246,250,0.55); font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 12px; }
    .toc ol { padding-left: 1.5rem; margin: 0; } .toc li { margin-bottom: 6px; font-size: 0.92rem; }
    .toc a { color: rgba(244,246,250,0.75); text-decoration: none; } .toc a:hover { color: #F7A21B; }
    .answer-first { background: rgba(247,162,27,0.08); border-left: 3px solid #F7A21B; border-radius: 8px; padding: 18px 22px; margin-bottom: 2rem; font-size: 1.05rem; line-height: 1.75; color: rgba(244,246,250,0.85); }
    .callout { background: rgba(41,182,217,0.06); border-left: 3px solid #29B6D9; border-radius: 8px; padding: 18px 22px; margin: 2rem 0; font-size: 0.98rem; line-height: 1.7; color: rgba(244,246,250,0.78); }
    .callout strong { color: #5FCCE8; }
    .pill { display: inline-block; font-size: 0.65rem; font-weight: 700; padding: 3px 10px; border-radius: 100px; letter-spacing: 0.05em; text-transform: uppercase; }
    .pill-orange { background: rgba(247,162,27,0.18); color: #F7A21B; border: 1px solid rgba(247,162,27,0.35); }
    .faq-item { background: rgba(31,46,69,0.55); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; margin-bottom: 12px; }
    .faq-item[open] { border-color: rgba(247,162,27,0.35); background: rgba(31,46,69,0.85); }
    .faq-item summary { cursor: pointer; list-style: none; padding: 16px 20px; font-weight: 600; color: #F4F6FA; display: flex; justify-content: space-between; gap: 14px; }
    .faq-item summary::-webkit-details-marker { display: none; }
    .faq-item summary::after { content: '+'; font-size: 1.4rem; color: #F7A21B; } .faq-item[open] summary::after { content: '\\2212'; }
    .faq-item .faq-answer { padding: 0 20px 18px; color: rgba(244,246,250,0.7); line-height: 1.7; font-size: 0.95rem; }
    .author-card { background: rgba(31,46,69,0.5); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; padding: 20px 24px; margin: 2rem 0; display: flex; gap: 16px; align-items: center; }
    .author-card .avatar { width: 52px; height: 52px; border-radius: 50%; background: linear-gradient(135deg, #F7A21B, #FDB94A); display: flex; align-items: center; justify-content: center; font-weight: 800; color: #162032; font-size: 1.1rem; flex-shrink: 0; }
    .author-card .meta p:first-child { font-weight: 700; color: #F4F6FA; font-size: 0.95rem; margin-bottom: 2px; }
    .author-card .meta p:last-child { font-size: 0.82rem; color: rgba(244,246,250,0.5); }
    nav a.nav-link { font-size: 0.9rem; color: rgba(244,246,250,0.65); font-weight: 500; } nav a.nav-link:hover { color: #F4F6FA; }
    .breadcrumb { font-size: 0.85rem; color: rgba(244,246,250,0.45); margin-bottom: 1.5rem; }
    .breadcrumb a { color: rgba(244,246,250,0.55); text-decoration: none; } .breadcrumb a:hover { color: #F7A21B; }
    .breadcrumb span { margin: 0 8px; opacity: 0.4; }
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
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=2, ensure_ascii=False)


def _page(p: dict) -> str:
    e = html.escape
    url = f"{SITE}/learn/{p['slug']}/"
    toc = "\n".join(f'          <li><a href="#{s["id"]}">{e(s["h2"])}</a></li>' for s in p["sections"]) \
        + '\n          <li><a href="#faq">Frequently asked questions</a></li>'
    body = "\n\n      ".join(f'<h2 id="{s["id"]}">{e(s["h2"])}</h2>\n      {s["html"]}' for s in p["sections"])
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

  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{ theme: {{ extend: {{ colors: {{
      orange: {{ wh: '#F7A21B', dark: '#D88A0E', light: '#FDB94A' }},
      blue:   {{ wh: '#29B6D9', dark: '#1A9ABF', light: '#5FCCE8' }},
      navy:   {{ wh: '#162032', mid: '#1F2E45', light: '#2A3D58' }},
      steel: '#7B8794', cloud: '#F4F6FA',
    }} }} }} }};
  </script>
{STYLE}
{URL_BRIDGE}
{GA4}
</head>
<body class="bg-navy-wh text-white antialiased">

<header class="border-b border-white/[0.06]" style="background: rgba(13,24,36,0.85);">
  <div class="max-w-6xl mx-auto px-5 sm:px-8 py-4 flex items-center justify-between">
    <a href="/" class="flex items-center gap-3">
      <img src="/brand_assets/workhive-logo-transparent.png" alt="WorkHive" style="height: 36px; width: auto;" />
      <span class="font-black text-lg tracking-tight">WorkHive</span>
    </a>
    <nav class="flex items-center gap-6">
      <a href="/" class="nav-link">Home</a>
      <a href="/learn/" class="nav-link">Learn</a>
      <a href="/#join" class="nav-link">Join the Hive</a>
    </nav>
  </div>
</header>

<article class="hex-pattern">
  <div class="max-w-3xl mx-auto px-5 sm:px-8 py-14 lg:py-20">

    <div class="breadcrumb">
      <a href="/">Home</a><span>/</span><a href="/learn/">Learn</a><span>/</span><span>{e(p['crumb'])}</span>
    </div>

    <span class="pill pill-orange">{e(p['pill'])}</span>
    <h1 class="text-3xl sm:text-4xl font-black tracking-tight mt-4 mb-4" style="line-height:1.15;">{e(p['h1'])}</h1>
    <p class="text-white/50 text-sm mb-8">By WorkHive Editorial Team · Updated {PUB} · {p['readmins']} min read</p>

    <div class="answer-first">{p['answer_first']}</div>

    <div class="toc">
      <h4>On this page</h4>
      <ol>
{toc}
      </ol>
    </div>

    <div class="prose-wh">

      {body}

      <h2 id="faq">Frequently asked questions</h2>

{faqs}

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
</article>

<footer class="py-10 border-t border-white/[0.06]" style="background: rgba(13,24,36,0.85);">
  <div class="max-w-4xl mx-auto px-5 sm:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-white/60">
    <p>© 2026 WorkHive Platform · workhiveph.com · Last updated <time datetime="{PUB}">{PUB}</time></p>
    <div class="flex items-center gap-6">
      <a href="/" class="hover:text-white/60 transition-colors">Home</a>
      <a href="/#faq" class="hover:text-white/60 transition-colors">FAQ</a>
      <a href="/#join" class="hover:text-white/60 transition-colors">Join the Hive</a>
    </div>
  </div>
</footer>

<script defer src="../../wh-feedback-fab.js"></script>
</body>
</html>
"""


def main() -> int:
    from pillar_content import PILLARS  # sibling data module
    built = []
    for p in PILLARS:
        d = LEARN / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(_page(p), encoding="utf-8")
        built.append(p["slug"])
        print(f"  built /learn/{p['slug']}/  ({len((d/'index.html').read_text(encoding='utf-8'))} bytes)")
    print(f"\n{len(built)} pillar page(s) written to learn/. Add to sitemap.xml, then run_platform_checks.")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
