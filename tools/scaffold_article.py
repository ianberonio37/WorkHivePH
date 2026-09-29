"""
End-to-end /learn/ article scaffold.

Pipeline (per article):
  1. Look up slug in wh_pages.LEARN_ARTICLES (must be added there first).
  2. Call article_generator.generate_article(...) -> AI-drafted content dict.
  3. Render full HTML using the canonical template (matches the 24 existing
     Wave 1 articles' structure: meta + JSON-LD + GA4-injection-point + body).
  4. Write to learn/<slug>/index.html.
  5. Insert <url> entry into sitemap.xml (idempotent).
  6. Insert article entry into llms.txt under ## Pages (idempotent).
  7. Inject GA4 snippet by running wire_ga4.py for the new file.

Usage:
    # One article at a time
    python tools/scaffold_article.py reliability-centered-maintenance-philippine-plants \
        --brief "Cover RCM origins, the 7 RCM questions, P-F intervals, FMEA tie-in, and a 90-day rollout for a PH plant with no CMMS."

    # Or scaffold every Wave 2 article that doesn't yet have a file on disk
    python tools/scaffold_article.py --all-missing

CRITICAL: do not modify the JSON-LD or GA4 emission logic here without also
updating the corresponding validators (validate_seo, validate_ga4_coverage,
validate_llms_sync, validate_sitemap_sync) so they stay in lockstep.
"""

import sys
import re
import json
import argparse
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from wh_pages import (
    LEARN_ARTICLES, article_tool_map, article_title_map,
)
from tools.article_generator import generate_article

# Wave 2 article briefs (used when --all-missing is invoked). Each brief tells
# the AI what specific angle to take so the 12 articles cover distinct
# territory instead of overlapping.
WAVE_2_BRIEFS = {
    "reliability-centered-maintenance-philippine-plants":
        "Cover RCM origins (Nowlan and Heap), the 7 RCM questions, "
        "P-F intervals, FMEA tie-in, and a 90-day rollout for a PH plant "
        "with no CMMS. Include a worked example for a Cabuyao bottling-line "
        "pump. Show how WorkHive PM Scheduler captures RCM-derived tasks.",
    "fmea-worked-example-philippine-bottling-line":
        "Walk through FMEA on a real Calabarzon bottling line filler. Show "
        "the 7-column FMEA worksheet, calculation of RPN (Severity x "
        "Occurrence x Detection), how to pick the top 3 failure modes to "
        "fix first, and how Asset Hub stores the FMEA output. Include a "
        "PHP cost-of-downtime calculation per failure mode.",
    "loto-procedures-dole-oshs-template":
        "Full LOTO procedure template aligned to DOLE OSHS Rule 1063, with "
        "the 7-step lockout sequence, a sample equipment-specific LOTO "
        "procedure for a 480V Pump P-204B, sign-off requirements, and how "
        "the WorkHive Audit Log captures every LOTO event for inspector "
        "review. Include a downloadable-template framing.",
    "vibration-analysis-on-a-phone-budget":
        "Realistic PdM for a PH plant with no $10,000 vibration analyzer. "
        "Cover phone-based apps (ISO 10816 thresholds), what they can and "
        "cannot detect (bearing wear yes, gear-mesh frequencies no), a "
        "weekly walkdown route using Voice Journal to log readings, and "
        "the 3 failure modes phone vibration actually catches.",
    "thermography-for-pm-philippine-plants":
        "Practical infrared thermography for PH plants: handheld IR camera "
        "selection (FLIR ONE Pro, Seek Thermal), critical scan targets "
        "(MCCB connections, motor windings, bearings, steam traps), reading "
        "thresholds, integration into the monthly PM Scheduler route. "
        "Include the IIEE thermography Code of Practice reference.",
    "ra-11285-energy-efficiency-plant-checklist":
        "Plant-floor compliance checklist for Republic Act 11285 (Energy "
        "Efficiency and Conservation Act). Cover the DOE Designated "
        "Establishment threshold (4,000 MWh/year), the annual energy report "
        "requirement, energy audit triggers, and how the WorkHive Audit "
        "Log captures energy-related actions. Include penalty figures.",
    "tesda-nc-mapping-to-skill-matrix":
        "How a PH plant maps TESDA National Certificates (NC II, NC III) "
        "for Industrial Maintenance, Mechanical Maintenance, Electrical "
        "Maintenance, and Welding into the WorkHive Skill Matrix. Show "
        "the assessment-to-badge mapping, the 4-level competency scale "
        "(aware/assisted/independent/instructor) tied to TESDA levels.",
    "ofw-engineer-portable-portfolio":
        "How an OFW-track Filipino engineer builds a verifiable maintenance "
        "portfolio using WorkHive's Skill Matrix + Solo Mode. Cover the "
        "use case (apply to a Saudi refinery with proof of 5 years of "
        "fault history), what the portfolio export includes, how Logbook "
        "entries become portable evidence, and what overseas employers "
        "actually look for.",
    "psme-iiee-piche-which-association-to-join":
        "Decision guide for a Filipino engineer or maintenance professional "
        "choosing among PSME (mechanical), IIEE (electrical), PIChE "
        "(chemical), and adjacent associations (MAP, ASEAN Federation). "
        "Cover membership cost, CPD credits, exam pathways, networking "
        "events, and how the WorkHive Community surfaces PH-association "
        "discussion threads. Include a chooser matrix.",
    "food-beverage-plant-maintenance-philippines":
        "Maintenance specifics for Philippine F&B plants: sanitary design "
        "(3-A, EHEDG), HACCP intersection, cleaning-in-place (CIP) cycle "
        "PM, conveyor and filler reliability targets, the regulatory "
        "context (FDA, BAFS, BAI), how the WorkHive Hive segments "
        "sanitary-zone vs utility-zone work orders. Worked example for a "
        "Calabarzon dairy plant.",
    "power-plant-reliability-metrics-philippines":
        "Reliability metrics that matter for Philippine power plants "
        "(coal, geothermal, solar, hydro): EAF, EFOR, NCF, heat rate, "
        "RAM benchmarks. ERC reporting requirements. How WorkHive "
        "Analytics computes these from logbook + PM data. Worked example "
        "for a Mindanao coal-fired plant with seasonal availability swings.",
    "bms-facilities-maintenance-peza-buildings":
        "BMS (Building Management System) and facilities maintenance in "
        "PEZA-registered buildings (BPO towers, ecozone factories, mixed-"
        "use developments). Cover the BMS scope (HVAC, lighting, "
        "elevators, life-safety, security), tenant SLA frameworks, "
        "monthly PM cadence, and how the WorkHive Hive handles multi-"
        "tenant facility teams. PEZA-specific compliance angles included.",
}

# ── HTML template ─────────────────────────────────────────────────────────────
# Mirrors the structure of the existing 24 Wave 1 articles. Single string
# with {{placeholders}} that get filled in. Kept inline (not a separate file)
# so the scaffold is one-file-runnable.

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="theme-color" content="#F7A21B" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>{TITLE} | WorkHive</title>
  <meta name="description" content="{META_DESCRIPTION}" />
  <meta name="keywords" content="{KEYWORDS}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="https://workhiveph.com/learn/{SLUG}/" />
  <link rel="manifest" href="/manifest.json" />

  <meta property="og:title" content="{TITLE}" />
  <meta property="og:description" content="{META_DESCRIPTION}" />
  <meta property="og:image" content="https://workhiveph.com/brand_assets/og-social.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:alt" content="WorkHive: Free industrial tools for every Filipino worker" />
  <meta property="og:url" content="https://workhiveph.com/learn/{SLUG}/" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="WorkHive" />
  <meta property="article:published_time" content="{ISO_DATE}T00:00:00+08:00" />
  <meta property="article:modified_time" content="{ISO_DATE}T00:00:00+08:00" />
  <meta property="article:author" content="WorkHive Editorial Team" />
  <meta property="article:section" content="Maintenance" />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{TITLE}" />
  <meta name="twitter:description" content="{META_DESCRIPTION}" />
  <meta name="twitter:image" content="https://workhiveph.com/brand_assets/og-social.png" />
  <meta name="twitter:image:alt" content="WorkHive: Free industrial tools for every Filipino worker" />

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@graph": [
      {{
        "@type": "Article",
        "@id": "https://workhiveph.com/learn/{SLUG}/#article",
        "headline": {TITLE_JSON},
        "description": {META_DESCRIPTION_JSON},
        "image": "https://workhiveph.com/brand_assets/workhive-logo-transparent.png",
        "author": {{ "@type": "Organization", "name": "WorkHive Editorial Team", "url": "https://workhiveph.com/" }},
        "publisher": {{ "@id": "https://workhiveph.com/#organization" }},
        "datePublished": "{ISO_DATE}",
        "dateModified": "{ISO_DATE}",
        "mainEntityOfPage": "https://workhiveph.com/learn/{SLUG}/",
        "inLanguage": "en-PH",
        "articleSection": "Maintenance",
        "wordCount": {WORD_COUNT},
        "keywords": {KEYWORDS_JSON}
      }},
      {{
        "@type": "FAQPage",
        "@id": "https://workhiveph.com/learn/{SLUG}/#faq",
        "mainEntity": [
{FAQ_JSON_ITEMS}
        ]
      }},
      {{
        "@type": "BreadcrumbList",
        "@id": "https://workhiveph.com/learn/{SLUG}/#breadcrumbs",
        "itemListElement": [
          {{ "@type": "ListItem", "position": 1, "name": "WorkHive", "item": "https://workhiveph.com/" }},
          {{ "@type": "ListItem", "position": 2, "name": "Learn",    "item": "https://workhiveph.com/learn/" }},
          {{ "@type": "ListItem", "position": 3, "name": {TITLE_JSON}, "item": "https://workhiveph.com/learn/{SLUG}/" }}
        ]
      }}
    ]
  }}
  </script>

  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=optional" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      theme: {{ extend: {{ colors: {{
        orange: {{ wh: '#F7A21B', dark: '#D88A0E', light: '#FDB94A' }},
        blue:   {{ wh: '#29B6D9', dark: '#1A9ABF', light: '#5FCCE8' }},
        navy:   {{ wh: '#162032' }},
      }} }} }}
    }};
  </script>
  <style>
    /* T3 (2026-09-10): every NEW article ships tap-responsive. Found by walking the RA 11285 guide in
       Filipino on a 390px phone - it graded T3 0% ("legacy ~300ms click delay + double-tap-zoom not
       suppressed"), and 53 of the 54 existing articles were the same, because the learn pages share no
       screen stylesheet (learn-print.css is media="print") and nothing put the rule in the scaffold.
       The 53 were repaired by tools/fix_learn_touch_action.py; this line is why the 55th will not need
       repairing. Changes no geometry - it only tells the browser not to wait for a possible second tap. */
    html, body, a, button {{ touch-action: manipulation; }}
    /* wh-learn-contrast-remap (C2, 2026-09-10): these pages load Tailwind from the CDN, so they miss the
       white-opacity remap wh-tw.css applies app-wide - the byline's 12px text-white/45 measured 4.27:1
       against the 4.5:1 it owes. Same seven values as wh-tw.css; body-scoped (0,1,1) so it beats the
       CDN utility whatever the injection order, with no !important. Applied to the existing 54 by
       tools/fix_learn_contrast_remap.py; this is why the 55th ships correct. */
    body .text-white\\/45 {{ color: rgb(255 255 255 / 0.8); }}
    body .text-white\\/50 {{ color: rgb(255 255 255 / 0.8); }}
    body .text-white\\/55 {{ color: rgb(255 255 255 / 0.8); }}
    body .text-white\\/60 {{ color: rgb(255 255 255 / 0.8); }}
    body .text-white\\/65 {{ color: rgb(255 255 255 / 0.85); }}
    body .text-white\\/70 {{ color: rgb(255 255 255 / 0.85); }}
    body .text-white\\/75 {{ color: rgb(255 255 255 / 0.85); }}
    body {{ font-family: 'Poppins', sans-serif; }}
    .hex-pattern {{ background-image: radial-gradient(circle, rgba(247,162,27,0.04) 1px, transparent 1px); background-size: 28px 28px; }}
    .audience-block {{ background: linear-gradient(135deg, rgba(41,182,217,0.10), rgba(41,182,217,0.04)); border: 1px solid rgba(41,182,217,0.22); border-radius: 14px; padding: 18px 22px; margin: 1.75rem 0; }}
    .audience-label {{ font-size: 11px; font-weight: 700; color: #5FCCE8; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }}
    .audience-block ul {{ margin: 0; padding-left: 1.2rem; color: rgba(244,246,250,0.78); font-size: 0.92rem; line-height: 1.7; }}
    .answer-first {{ background: rgba(247,162,27,0.06); border-left: 3px solid #F7A21B; padding: 18px 22px; border-radius: 0 12px 12px 0; margin: 1.5rem 0; color: rgba(244,246,250,0.85); font-size: 1.02rem; line-height: 1.65; }}
    .toc {{ background: rgba(31,46,69,0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 18px 22px; margin: 2rem 0; }}
    /* ~W46101: BOTH tags. The label has been an h2 and an h4 at different times and the
       selector was once coupled to the tag - when the tag moved and the selector did not,
       45 of 54 published articles rendered this label at the browser default 16px for as
       long as nobody asked why the type ramp had nine steps. Matching both tags means the
       styling cannot come apart from the markup again. Tracking is 0.04em per DESIGN.md,
       which caps all-caps labels there. */
    .toc h2, .toc h4 {{ margin: 0 0 8px; font-size: 13px; color: rgba(244,246,250,0.6); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
    .toc ol {{ margin: 0; padding-left: 1.2rem; color: rgba(244,246,250,0.75); font-size: 0.92rem; line-height: 1.85; }}
    .toc a {{ color: rgba(244,246,250,0.75); }}
    .toc a:hover {{ color: #FDB94A; }}
    .prose-wh h2 {{ font-size: 1.55rem; font-weight: 800; color: #F4F6FA; margin: 2.25rem 0 0.85rem; letter-spacing: -0.01em; }}
    .prose-wh p {{ font-size: 1.005rem; color: rgba(244,246,250,0.78); line-height: 1.75; margin: 0.85rem 0; }}
    .prose-wh strong {{ color: #F4F6FA; }}
    .prose-wh a {{ color: #5FCCE8; text-decoration: underline; text-underline-offset: 3px; }}
    .prose-wh ol, .prose-wh ul {{ color: rgba(244,246,250,0.78); padding-left: 1.4rem; margin: 0.85rem 0; line-height: 1.75; }}
    .prose-wh table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0; font-size: 0.95rem; }}
    .prose-wh th, .prose-wh td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.08); }}
    .prose-wh th {{ background: rgba(31,46,69,0.6); font-weight: 700; color: #F4F6FA; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .callout {{ background: rgba(41,182,217,0.06); border-left: 3px solid #29B6D9; border-radius: 8px; padding: 18px 22px; margin: 2rem 0; font-size: 0.98rem; line-height: 1.7; color: rgba(244,246,250,0.78); }}
    .callout strong {{ color: #5FCCE8; }}
    .article-fig {{ margin: 1.75rem 0; }}
    .article-fig img {{ width: 100%; height: auto; display: block; }}
    .article-fig figcaption {{ margin-top: 8px; font-size: 0.85rem; color: rgba(244,246,250,0.55); line-height: 1.55; }}
    .tool-cta {{ background: linear-gradient(135deg, rgba(247,162,27,0.14), rgba(247,162,27,0.04)); border: 1px solid rgba(247,162,27,0.32); border-radius: 14px; padding: 22px 26px; margin: 2.25rem 0; }}
    .tool-cta a {{ display: inline-block; margin-top: 10px; background: linear-gradient(135deg, #F7A21B, #FDB94A); color: #162032; font-weight: 700; padding: 10px 22px; border-radius: 10px; text-decoration: none; transition: transform 0.15s; }}
    .tool-cta a:hover {{ transform: translateY(-1px); }}
    .faq-item {{ background: rgba(31,46,69,0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 16px 20px; margin: 0.7rem 0; }}
    .faq-item summary {{ cursor: pointer; font-weight: 600; color: #F4F6FA; font-size: 1rem; }}
    .faq-item[open] summary {{ color: #FDB94A; }}
    .faq-item .faq-answer {{ margin-top: 12px; color: rgba(244,246,250,0.78); font-size: 0.97rem; line-height: 1.7; }}
    .sources-list {{ list-style: none; padding: 0; }}
    .sources-list li {{ padding: 8px 0; border-bottom: 1px dashed rgba(255,255,255,0.07); color: rgba(244,246,250,0.65); font-size: 0.9rem; }}
  </style>
</head>
<body class="bg-navy-wh text-white antialiased">

<nav class="border-b border-white/10" style="background: rgba(13,24,36,0.85);">
  <div class="max-w-5xl mx-auto px-5 sm:px-8 h-14 flex items-center justify-between">
    <a href="/" class="flex items-center gap-2 text-sm font-bold tracking-tight">
      <img src="/brand_assets/workhive-logo-transparent.png" alt="WorkHive" class="h-7 w-auto" />
      <span class="text-white">WorkHive</span>
    </a>
    <div class="flex items-center gap-5 text-xs sm:text-sm">
      <a href="/learn/" class="text-white/55 hover:text-white transition-colors">Learn</a>
      <a href="/" class="text-white/55 hover:text-white transition-colors">Home</a>
      <a href="/#join" class="bg-orange-wh text-navy-wh px-4 py-1.5 rounded-lg font-semibold text-xs hover:bg-orange-light transition-colors">Join</a>
    </div>
  </div>
</nav>

<article class="hex-pattern">
  <div class="max-w-3xl mx-auto px-5 sm:px-8 py-10 sm:py-14">

    <p class="text-xs uppercase tracking-[0.18em] text-orange-wh font-bold mb-3">WorkHive Learn · Philippines</p>
    <h1 class="text-3xl sm:text-4xl lg:text-[2.7rem] font-black leading-[1.15] tracking-[-0.02em] mb-5">{TITLE}</h1>
    <div class="flex items-center gap-3 text-xs text-white/45 mb-7">
      <span>By WorkHive Editorial Team</span>
      <span class="opacity-40">·</span>
      <time datetime="{ISO_DATE}">{HUMAN_DATE}</time>
      <span class="opacity-40">·</span>
      <span>{READ_MIN} min read</span>
    </div>

    <div class="answer-first"><strong>Short answer:</strong> {INTRO}</div>

    <div class="audience-block">
      <p class="audience-label">Who this is for</p>
      <ul>
{AUDIENCE_LIST_HTML}
      </ul>
    </div>

    <div class="toc">
      <!-- ~W46129: h2, not h4-with-aria-level. This label is a PEER of the article's h2
           sections. It was <h4 aria-level="2"> on 49 published articles - the ARIA level
           was correct and the TAG was not, so `impeccable detect` reported a false
           skipped-heading on every one while the walk (which honours aria-level) measured
           zero. An <h2> IS level 2: markup, accessibility tree and detector now agree, and
           `.toc h2, .toc h4` styles it either way. -->
      <h2>What's in this guide</h2>
      <ol>
{TOC_HTML}
      </ol>
    </div>

    <div class="prose-wh">
{SECTIONS_HTML}

      <div class="tool-cta">
        <p style="margin:0; font-size:0.95rem; color:rgba(244,246,250,0.85);"><strong>Open the tool:</strong> {TOOL_NAME} is the WorkHive surface this guide funnels into. It is free at the worker tier, works offline, and is built for Philippine plants.</p>
        <a href="{TOOL_URL}">Open {TOOL_NAME} &rarr;</a>
      </div>

      <h2 id="faq">Frequently asked questions</h2>
{FAQ_HTML}

      <h2 id="sources">Sources</h2>
      <ul class="sources-list">
{SOURCES_HTML}
      </ul>
    </div>

  </div>
</article>

<footer class="py-10 border-t border-white/[0.06]" style="background: rgba(13,24,36,0.85);">
  <div class="max-w-5xl mx-auto px-5 sm:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-white/60">
    <p>Practical writing for the Philippine plant floor. Email <a href="mailto:admin@workhiveph.com" style="color:#5FCCE8;">admin@workhiveph.com</a> with corrections or contributions.</p>
    <div class="flex gap-5">
      <a href="/" class="hover:text-white/65 transition-colors">Home</a>
      <a href="/learn/" class="hover:text-white/65 transition-colors">All guides</a>
      <a href="/about/" class="hover:text-white/65 transition-colors">About</a>
    </div>
  </div>
</footer>

<script defer src="../../wh-feedback-fab.js"></script>
</body>
</html>
"""

# ── Rendering helpers ─────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """Basic HTML escape for text content."""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _render_html(slug: str, title: str, tool_url: str, tool_name: str,
                 article: dict) -> str:
    """Fill the template with the AI-generated content."""
    today = date.today()
    iso   = today.isoformat()
    human = today.strftime("%-d %B %Y") if sys.platform != "win32" \
            else today.strftime("%#d %B %Y")

    # Body word count (figure markup excluded: alt text is not prose)
    body_words = sum(
        len(re.findall(r"\b\w+\b", p))
        for s in article["sections"] for p in s["paragraphs"]
        if not p.lstrip().startswith("<figure")
    )
    read_min = max(5, int(round(body_words / 220)))   # 220 wpm

    audience_html = "\n".join(
        f"        <li>{_esc(a)}</li>" for a in article["audience"]
    )
    toc_html = "\n".join(
        f'        <li><a href="#{_esc(anchor)}">{_esc(label)}</a></li>'
        for anchor, label in article["toc"]
    )
    sections_html = "\n".join(
        f'      <h2 id="{_esc(s["id"])}">{_esc(s["h2"])}</h2>\n'
        + "\n".join(f"      {p}" for p in s["paragraphs"])
        for s in article["sections"]
    )
    faq_html = "\n".join(
        f'      <details class="faq-item"><summary>{_esc(q["q"])}</summary>'
        f'<div class="faq-answer">{_esc(q["a"])}</div></details>'
        for q in article["faq"]
    )
    sources_html = "\n".join(
        f"        <li>{_esc(s)}</li>" for s in article["sources"]
    )
    faq_json_items = ",\n".join(
        '          {{ "@type": "Question", "name": {q}, "acceptedAnswer": '
        '{{ "@type": "Answer", "text": {a} }} }}'.format(
            q=json.dumps(item["q"]), a=json.dumps(item["a"])
        )
        for item in article["faq"]
    )

    return HTML_TEMPLATE.format(
        TITLE                = _esc(title),
        TITLE_JSON           = json.dumps(title),
        SLUG                 = slug,
        META_DESCRIPTION     = _esc(article["description"]),
        META_DESCRIPTION_JSON= json.dumps(article["description"]),
        KEYWORDS             = _esc(article["keywords"]),
        KEYWORDS_JSON        = json.dumps(article["keywords"]),
        ISO_DATE             = iso,
        HUMAN_DATE           = human,
        READ_MIN             = read_min,
        WORD_COUNT           = body_words,
        INTRO                = _esc(article["intro"]),
        AUDIENCE_LIST_HTML   = audience_html,
        TOC_HTML             = toc_html,
        SECTIONS_HTML        = sections_html,
        FAQ_HTML             = faq_html,
        FAQ_JSON_ITEMS       = faq_json_items,
        SOURCES_HTML         = sources_html,
        TOOL_NAME            = _esc(tool_name),
        TOOL_URL             = tool_url,
    )


# ── Registry updaters (sitemap.xml + llms.txt) ────────────────────────────────

def _update_sitemap(slug: str, title: str):
    """Insert <url> entry for /learn/<slug>/ into sitemap.xml if not present."""
    sm_path = ROOT / "sitemap.xml"
    if not sm_path.exists():
        print(f"  [scaffold] sitemap.xml not found at {sm_path}")
        return
    content = sm_path.read_text(encoding="utf-8")
    url = f"https://workhiveph.com/learn/{slug}/"
    if url in content:
        return   # already present, idempotent
    today = date.today().isoformat()
    entry = (f"  <url>\n"
             f"    <loc>{url}</loc>\n"
             f"    <lastmod>{today}</lastmod>\n"
             f"    <changefreq>monthly</changefreq>\n"
             f"    <priority>0.7</priority>\n"
             f"  </url>\n")
    new = content.replace("</urlset>", entry + "</urlset>", 1)
    sm_path.write_text(new, encoding="utf-8")
    print(f"  [scaffold] sitemap.xml: added {url}")


def _update_llms_txt(slug: str, title: str, description: str):
    """Append a one-line article entry under ## Pages in llms.txt if not present."""
    lt_path = ROOT / "llms.txt"
    if not lt_path.exists():
        print(f"  [scaffold] llms.txt not found at {lt_path}")
        return
    content = lt_path.read_text(encoding="utf-8")
    url_path = f"/learn/{slug}/"
    if url_path in content:
        return   # already present
    # Compose the one-liner the same way Wave-1 entries are formatted
    line = (f"- [{title}](https://workhiveph.com{url_path}): "
            f"{description}\n")
    # Insert at end of ## Pages section (before the next ## heading or EOF)
    if "\n## Notes for AI assistants" in content:
        new = content.replace("\n## Notes for AI assistants",
                              line + "\n## Notes for AI assistants", 1)
    elif "\n## Contact" in content:
        new = content.replace("\n## Contact", line + "\n## Contact", 1)
    else:
        new = content + line
    lt_path.write_text(new, encoding="utf-8")
    print(f"  [scaffold] llms.txt: added {url_path}")


def _wire_ga4(slug: str):
    """Inject the GA4 snippet into the new article. Reuses wire_ga4.py logic."""
    from tools import wire_ga4 as wg4
    path = ROOT / "learn" / slug / "index.html"
    result = wg4.wire_page(path, "G-ENMGLTFR2J")
    print(f"  [scaffold] GA4 wire: {result}")


# ── Main entrypoint ───────────────────────────────────────────────────────────

def _render_figures(slug: str, article: dict):
    """Render the generator's validated figure specs to learn/<slug>/fig-N.svg
    and append a <figure> block to the section each one belongs to."""
    figures = article.get("figures") or []
    if not figures:
        return
    from tools.article_viz import render_figure, figure_text
    by_id = {s["id"]: s for s in article["sections"]}
    for n, spec in enumerate(figures, 1):
        sec = by_id.get(spec.get("section_id")) or article["sections"][0]
        fname = f"fig-{n}-{spec['kind'].replace('_', '-')}.svg"
        try:
            render_figure(spec, ROOT / "learn" / slug / fname)
        except Exception as exc:
            print(f"  [scaffold] figure {n} ({spec['kind']}) failed: {exc}; skipped")
            continue
        alt = _esc(figure_text(spec))[:360]
        cap = _esc(spec.get("title", ""))
        if spec.get("source"):
            cap += f" Source: {_esc(spec['source'])}."
        sec["paragraphs"].append(
            f'<figure class="article-fig"><img src="{fname}" alt="{alt}" '
            f'width="660" height="440" loading="lazy" />'
            f"<figcaption>{cap}</figcaption></figure>")
        print(f"  [scaffold] figure {n}: {fname} -> section '{sec['h2'][:40]}'")


def scaffold_one(slug: str, brief: str):
    tmap = article_tool_map()
    titles = article_title_map()
    if slug not in tmap:
        raise SystemExit(f"slug '{slug}' not in wh_pages.LEARN_ARTICLES")
    tool_url, tool_name = tmap[slug]
    title = titles[slug]

    print(f"\n=== {slug} ===")
    print(f"  title:     {title}")
    print(f"  tool:      {tool_name} ({tool_url})")

    article = generate_article(slug, title, tool_name, brief)
    _render_figures(slug, article)
    html = _render_html(slug, title, tool_url, tool_name, article)

    out_path = ROOT / "learn" / slug / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    word_re   = re.compile(r"\b\w+\b")
    body_words = sum(
        len(word_re.findall(p))
        for s in article["sections"] for p in s["paragraphs"]
    )
    print(f"  wrote:     {out_path.relative_to(ROOT)} ({body_words} body words)")

    _update_sitemap(slug, title)
    _update_llms_txt(slug, title, article["description"])
    _wire_ga4(slug)

    if article.get("_remaining_warnings"):
        print(f"  WARN: {len(article['_remaining_warnings'])} validation issues remain:")
        for w in article["_remaining_warnings"][:5]:
            print(f"     - {w}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?", help="article slug (omit if using --all-missing)")
    ap.add_argument("--brief", help="brief for the AI generator")
    ap.add_argument("--all-missing", action="store_true",
                    help="scaffold every Wave 2 slug whose file doesn't yet exist")
    args = ap.parse_args()

    if args.all_missing:
        for slug, brief in WAVE_2_BRIEFS.items():
            out = ROOT / "learn" / slug / "index.html"
            if out.exists():
                print(f"  [skip] {slug} already exists")
                continue
            scaffold_one(slug, brief)
    else:
        if not args.slug:
            ap.error("provide a slug or use --all-missing")
        brief = args.brief or WAVE_2_BRIEFS.get(args.slug)
        if not brief:
            ap.error(f"no brief provided and no default for slug '{args.slug}'")
        scaffold_one(args.slug, brief)


if __name__ == "__main__":
    main()
