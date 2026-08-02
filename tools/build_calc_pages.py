"""
build_calc_pages.py — the programmatic-SEO calculator page generator (Pillar 3).
================================================================================
Emits ONE static-HTML landing page per engineering calculator at
`/tools/<slug>/`, each answer-first with a REAL worked example computed at BUILD
time (not client-side JS) + SoftwareApplication/HowTo/FAQPage schema.

WHY static HTML with baked-in numbers:
  AI crawlers (ChatGPT, Claude, CCBot) FETCH JavaScript but DO NOT EXECUTE it
  [substrate/external/external-ai-crawlers-fetch-but-do-not-execute-javascript-].
  The live calculators live in engineering-design.js (client-side, noindex) — so
  to an AI crawler they are a blank page. These pages put the formula + a worked
  numeric example in the HTML itself, so the calc surface becomes citable.
  Stat-rich content raises AI-citation likelihood ~41%
  [external-generative-engine-optimization-statistics-2026-a].

Grounding: SoftwareApplication schema for B2B SaaS + FAQPage for AI Overviews +
static site generation, deployed in staged batches
[external-programmatic-seo-pages-step-by-step-implementati]. Genuine utility per
page (real formula + real worked numbers) avoids the thin-page penalty
[external-programmatic-seo-strategy-calculator-tool-pages-].

RUN (needs the calc deps — use the python-api venv):
    test-data-seeder/venv/Scripts/python.exe tools/build_calc_pages.py [--all] [--slug pump-tdh-calculator]

Output goes to `seo_assets/calc_pages_staging/<slug>/index.html` — STAGING, not
the site root. Nothing ships until Ian reviews + moves it. Validate with
`tools/validate_calc_pages.py`.
"""
from __future__ import annotations

import sys
import html
import json
import importlib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
PYAPI = ROOT / "python-api"
OUT_DIR = ROOT / "seo_assets" / "calc_pages_staging"
SITE = "https://workhiveph.com"

if str(PYAPI) not in sys.path:
    sys.path.insert(0, str(PYAPI))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── Per-calc specs ────────────────────────────────────────────────────────────
# Each spec: the calc module under python-api/calcs, the page identity, a REAL
# example input set (the generator runs the calc to bake the worked numbers), the
# answer-first sentence (templated with the computed results), the plain formula,
# HowTo steps, FAQs, discipline pillar + sibling links. Seeded fully for the
# exemplar; extend one spec per calc to grow the batch (the framework runs any
# spec that has module + example_inputs + answer()).
#
# answer(r) receives the calc's result dict and returns the answer-first sentence.

CALC_SPECS: dict[str, dict] = {
    "pump-tdh-calculator": {
        "module": "pump_tdh",
        "title": "Pump TDH Calculator",
        "h1": "Pump Total Dynamic Head (TDH) Calculator",
        "discipline": "Plumbing & Pumps",
        "keyword": "pump total dynamic head calculator",
        "meta": "Free pump TDH (total dynamic head) calculator with a worked example. "
                "Size a pump and motor from flow, static head, pipe, and fittings — "
                "ISO 9906 / PSME Code. Built for Philippine plants by WorkHive.",
        "example_inputs": {
            "flow_rate": 200, "static_head": 15, "pipe_diameter": 50,
            "pipe_length": 60, "pipe_material": "PVC", "fluid_temp_c": 30,
            "pump_efficiency": 70, "motor_efficiency": 90,
        },
        "example_desc": "a 200 L/min pump lifting water 15 m through 60 m of 50 mm PVC pipe",
        "answer": lambda r: (
            f"To size a pump, calculate Total Dynamic Head (TDH) = static head + friction head "
            f"+ velocity head. For {{example}}, TDH ≈ {r['TDH']} m at "
            f"{r['pipe_velocity']} m/s ({r['velocity_zone'].split(' - ')[0].lower()} velocity), "
            f"needing about a {r['recommended_kw']} kW ({r['recommended_hp']} HP) motor and "
            f"NPSH available of {r['npsh_available']} m (per {r['standard']})."
        ),
        "formula": "TDH = H_static + H_friction + H_velocity, where friction head uses "
                   "Darcy–Weisbach with the Colebrook–White friction factor and real "
                   "water properties (density, viscosity) at the operating temperature.",
        "steps": [
            "Measure the required flow rate (L/min) and the vertical static lift (m).",
            "Record the pipe: diameter (mm), total length (m), and material (for roughness).",
            "Compute friction head from Darcy–Weisbach + Colebrook–White (velocity, Reynolds number, friction factor).",
            "Add static + friction + velocity head to get TDH (m).",
            "Size the motor from hydraulic power ÷ pump efficiency ÷ motor efficiency, then round up to the next standard IEC/PEC size.",
        ],
        "faqs": [
            ("What is total dynamic head (TDH)?",
             "TDH is the total equivalent height a pump must overcome: the static lift plus friction losses in the pipe plus the velocity head. It sets the pump and motor size."),
            ("How do I calculate pump head?",
             "Add static head + friction head + velocity head. Friction head comes from the Darcy–Weisbach equation using the Colebrook–White friction factor for the pipe material and flow."),
            ("What motor size do I need for a 200 L/min pump?",
             "For a typical 200 L/min duty at ~18 m TDH, a 1.1 kW (1.5 HP) motor is usually enough after applying pump and motor efficiency and a service-factor margin. Always confirm against the manufacturer curve."),
            ("What is NPSH available and why does it matter?",
             "NPSH available is the suction-side pressure margin before cavitation. It must exceed the pump's NPSH required, or the pump cavitates and wears out. It falls with elevation and hot water."),
        ],
        "pillar": ("/learn/free-engineering-calculators-philippine-plants/", "Free Engineering Calculators for Philippine Plants"),
        "siblings": [
            ("/tools/pipe-sizing-calculator/", "Pipe Sizing Calculator"),
            ("/tools/duct-sizing-calculator/", "Duct Sizing Calculator"),
        ],
        "related_article": ("/learn/predictive-maintenance-on-a-budget-philippines/", "Predictive maintenance on a budget"),
    },
}


def _run_calc(spec: dict) -> dict:
    mod = importlib.import_module(f"calcs.{spec['module']}")
    return mod.calculate(dict(spec["example_inputs"]))


def _jsonld(spec: dict, url: str, answer_text: str) -> str:
    faq = {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in spec["faqs"]
        ],
    }
    howto = {
        "@type": "HowTo",
        "name": f"How to use the {spec['title']}",
        "step": [{"@type": "HowToStep", "position": i + 1, "text": s}
                 for i, s in enumerate(spec["steps"])],
    }
    app = {
        "@type": "SoftwareApplication",
        "name": spec["title"],
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "url": url,
        "description": spec["meta"],
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "PHP"},
        "publisher": {"@type": "Organization", "name": "WorkHive", "url": SITE},
    }
    graph = {"@context": "https://schema.org", "@graph": [app, howto, faq]}
    return json.dumps(graph, indent=2, ensure_ascii=False)


def _html_page(spec: dict) -> str:
    slug = spec["_slug"]
    url = f"{SITE}/tools/{slug}/"
    r = _run_calc(spec)
    answer_text = spec["answer"](r).replace("{example}", spec["example_desc"])
    e = html.escape
    faq_html = "\n".join(
        f'      <details class="faq"><summary>{e(q)}</summary><p>{e(a)}</p></details>'
        for q, a in spec["faqs"]
    )
    steps_html = "\n".join(f"        <li>{e(s)}</li>" for s in spec["steps"])
    sib_html = "\n".join(
        f'        <li><a href="{e(u)}">{e(t)}</a></li>' for u, t in spec["siblings"]
    )
    pillar_url, pillar_t = spec["pillar"]
    rel_url, rel_t = spec["related_article"]
    jsonld = _jsonld(spec, url, answer_text)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(spec['title'])} — Free Online + Worked Example | WorkHive</title>
<meta name="description" content="{e(spec['meta'])}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(spec['title'])} | WorkHive">
<meta property="og:description" content="{e(spec['meta'])}">
<meta property="og:url" content="{e(url)}">
<meta property="og:type" content="website">
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
  <main>
    <nav aria-label="Breadcrumb"><a href="{e(pillar_url)}">{e(pillar_t)}</a> &rsaquo; {e(spec['title'])}</nav>
    <h1>{e(spec['h1'])}</h1>

    <!-- answer-first: the worked-example stat AI cites -->
    <p class="answer-first"><strong>{e(answer_text)}</strong></p>

    <section aria-labelledby="formula">
      <h2 id="formula">The formula</h2>
      <p>{e(spec['formula'])}</p>
    </section>

    <section aria-labelledby="worked">
      <h2 id="worked">Worked example ({e(spec['discipline'])})</h2>
      <p>Inputs: {e(spec['example_desc'])}.</p>
      <table>
        <thead><tr><th>Result</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td>Total Dynamic Head (TDH)</td><td>{r['TDH']} m</td></tr>
          <tr><td>Pipe velocity</td><td>{r['pipe_velocity']} m/s ({e(r['velocity_zone'])})</td></tr>
          <tr><td>Friction head</td><td>{r['friction_head']} m</td></tr>
          <tr><td>Recommended motor</td><td>{r['recommended_kw']} kW ({r['recommended_hp']} HP)</td></tr>
          <tr><td>NPSH available</td><td>{r['npsh_available']} m</td></tr>
        </tbody>
      </table>
      <p><small>Computed with {e(r['calculation_source'])}; standard: {e(r['standard'])}.</small></p>
    </section>

    <section aria-labelledby="howto">
      <h2 id="howto">How to calculate it</h2>
      <ol>
{steps_html}
      </ol>
    </section>

    <section aria-labelledby="faq">
      <h2 id="faq">FAQ</h2>
{faq_html}
    </section>

    <section aria-labelledby="try">
      <h2 id="try">Run it on your own numbers</h2>
      <p><a href="/workhive/#/tools/engineering-design" class="cta">Open the interactive {e(spec['title'])} in WorkHive</a> — free, no sign-up needed for the calculators.</p>
    </section>

    <section aria-labelledby="related">
      <h2 id="related">Related</h2>
      <ul>
        <li><a href="{e(pillar_url)}">{e(pillar_t)}</a> (pillar)</li>
{sib_html}
        <li><a href="{e(rel_url)}">{e(rel_t)}</a></li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


def build(slugs: list[str]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = 0
    for slug in slugs:
        spec = CALC_SPECS[slug]
        spec["_slug"] = slug
        page = _html_page(spec)
        d = OUT_DIR / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        print(f"  built /tools/{slug}/  ({len(page)} bytes)")
        built += 1
    print(f"\n{built} page(s) staged in {OUT_DIR.relative_to(ROOT)} "
          f"(NOT shipped — review, then move to /tools/).")
    print(f"Specs available: {len(CALC_SPECS)} / 58 calc modules "
          f"(seed more CALC_SPECS to grow the batch).")
    return built


def main() -> int:
    args = sys.argv[1:]
    if "--slug" in args:
        i = args.index("--slug")
        slugs = [args[i + 1]]
    else:  # default + --all: every fully-specced calc
        slugs = list(CALC_SPECS.keys())
    if not slugs:
        print("No specced calculators to build.")
        return 1
    build(slugs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
