#!/usr/bin/env python3
"""enhancement_inventory.py - the MEASURED population for the ENHANCEMENT wave (ENH), 2026-10-14.

Ian, 2026-10-14, beside the sub-layer wave: improve the overall UFAI UI/UX of every production and public page - and,
by name, a SOLAR POWER-STATION PLANNER: list the appliances, add up the daily watt-hours, size for the surge, choose
the days of autonomy, size the battery and the inverter, use the peak sun hours of the person's own province, size
the charge controller, then save, share and print the plan.

A bug wave asks "what is broken"; this wave asks "what is MISSING that a person would feel". The number is DERIVED,
never typed: every cell is a capability a page's own source does not contain, measured by the regexes below
(measured and approved 2026-10-14, kept verbatim so the number Ian saw is the number seeded).

  S  the solar power-station planner   12 planner capabilities against the two solar surfaces: the calculator
                                       (tools/solar-pv-calculator) and the Solar PV calc type in engineering-design
                                       (its neighbourhood in engineering-design.js); one cell per capability missing
  P  calculator planner features       four features against every calculator: a recommendation, export/print,
                                       share/save, scenario compare. A metric/imperial toggle was measured (58
                                       missing) and is NOT seeded: the Philippines works in SI (PEC 2017), so it is
                                       not a gain a PH crew would feel. The solar calculator's recommendation,
                                       export and share cells are carried by S's planner rows, not twice.
  L  a learn guide -> its tool         a guide whose source never links a calculator or the learn-link CTA
  J  a production page with no live journey  live_page_journeys_results.json has no entry for the page
  C  an open critic cell, signed in    a (production page, rubric dim) a signed-in critic walk left critiqued with
                                       a finding (critic_registry.json), N1 excluded
  R  provenance out of the top         (Ian, 2026-10-19: "all that provenance should be all relocated somewhere that is
                                       not getting space on the upper part where the user's attention the most ... at
                                       the bottom most of the page") - a production, founder or public page whose
                                       source carries provenance (a source chip: renderSourceChip / .wh-source-chip, or
                                       a "How we compute this" disclosure) and no bottom Sources area (data-wh-sources).
                                       A learn ARTICLE's dated byline is its header, not a data source, and its sources
                                       already sit at its foot - articles are not measured; the learn index is (a chip).

Deterministic: page sources + committed artifacts. J and C read artifacts that move as work lands, which is why the
seeder's replay is ANCHORED to the registry (the BRP/BRH rule): a cell that closes never renumbers a row.

    python tools/enhancement_inventory.py            # the human report
    python tools/enhancement_inventory.py --json     # the machine population (what the seeder reads)
    python tools/enhancement_inventory.py --self-test
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

JOURNEYS = ROOT / "live_page_journeys_results.json"
CRITIC = ROOT / "critic_registry.json"
CLASSES = OrderedDict([
    ("S", ("the solar power-station planner", "F")),
    ("P", ("calculator planner features", "F")),
    ("L", ("a learn guide sends its reader to the tool", "F")),
    ("J", ("a production page with no live journey", "CI")),
    ("C", ("an open critic cell on a production page, signed in", "F")),
    ("R", ("provenance moves out of the top, to a Sources area at the foot", "F")),
])
# capability: (regex, the ask's verb phrase). Order is the planner's own order, appliance list first.
SOLAR_CAPS = OrderedDict([
    ("appliance list builder", (r"appliance", "list the appliances the station will power, each with its watts and "
                                              "its hours a day")),
    ("daily energy Wh", (r"wh/day|watt-hour|kwh/day|daily (energy|consumption)",
                         "add the list up to the daily energy in watt-hours, with the losses stated")),
    ("peak & surge W", (r"surge|peak (load|watt)|starting (current|watt)",
                        "size for the peak load and the starting surge of motors and compressors")),
    ("autonomy days", (r"autonomy|days? of backup|backup days",
                       "ask how many days without sun the station must carry the load")),
    ("battery bank (DoD, chemistry)", (r"depth of discharge|\bdod\b|lifepo4|lead.acid|battery (bank|capacity)",
                                       "size the battery bank by chemistry and depth of discharge")),
    ("inverter sizing", (r"inverter", "size the inverter for the continuous load and the surge")),
    ("peak sun hours by location", (r"peak sun|psh|irradian|insolation",
                                    "use the peak sun hours of the person's own province (PAGASA)")),
    ("array Wp & panel count", (r"panel (count|wattage|quantity)|number of panels|array (size|wp)",
                                "turn the daily energy into array watts and a panel count")),
    ("charge controller", (r"charge controller|mppt|pwm",
                           "size the charge controller, MPPT or PWM, for the array and the battery voltage")),
    ("cost estimate ₱", (r"₱|php|cost estimate|budget", "estimate what the station costs in pesos, part by part")),
    ("save/share the plan", (r"share|copy link|save (this|your)|permalink", "save the plan and share it by link")),
    ("printable spec sheet", (r"print|pdf|spec sheet",
                              "print a spec sheet a supplier or an electrician can quote from")),
])
# (the page a person walks, the file whose text is measured, how the text is cut)
SOLAR_SURFACES = (("tools/solar-pv-calculator/index.html", "tools/solar-pv-calculator/index.html", None),
                  ("engineering-design.html", "engineering-design.js", "Solar PV System"))
CALC_FEATURES = OrderedDict([
    ("recommendation", (r"\brecommend|you (will )?need|suggested|what to buy|sizing result",
                        "say what to buy or do with the result, not only the number")),
    ("export/print", (r"print|pdf|export|download",
                      "print or export the result with its inputs and the standard it follows")),
    ("share/save", (r"share|copy link|save (this|your)|permalink", "save the calculation and share it by link")),
    ("scenario compare", (r"compare|scenario|what-if|versus", "compare two scenarios side by side")),
])
SOLAR_CALC = "solar-pv-calculator"
PLANNER = "solar-planner.js"   # the planner both solar surfaces load (ENH-S, 2026-10-22)
SOLAR_COVERS = frozenset(("recommendation", "export/print", "share/save"))   # carried by the S planner rows
LEARN_CTA = r'href="/tools/|learn-link'
# R: what counts as provenance in a page's source, and the marker of the bottom Sources area that ends the cell
PROVENANCE = re.compile(r'renderSourceChip\(|class="wh-source-chip"|How (we compute|this is computed|it.s computed|we calculate)',
                        re.I)
SOURCES_AREA = 'data-wh-sources'
CRITIC_DIM = re.compile(r"^(?P<page>[\w./-]+?)(?:\.html)?:\s*(?P<dim>[A-Z]{1,2}\d)\s+\d+%")


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _read(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def production_pages() -> list[str]:
    """The LX production roster (served root minus LX_NON_PRODUCTION) - the 30 pages the J and C classes measure."""
    from seed_expansion_wave4 import LX_NON_PRODUCTION, served_pages
    return sorted(p for p in served_pages()["root"] if p not in LX_NON_PRODUCTION)


def _solar(sources: dict | None) -> list[dict]:
    out = []
    for page, measured, anchor in SOLAR_SURFACES:
        s = sources.get(measured, "") if sources is not None else _read(measured)
        # ENH-S (2026-10-22): the planner is built ONCE in solar-planner.js and both surfaces load it - a surface that
        # loads it carries its capabilities, so they are measured in the script it loads, not looked for in its own text
        planner = "solar-planner.js" in s
        if anchor:
            i = s.find(anchor)
            s = s[max(0, i - 3000): i + 12000] if i >= 0 else ""     # the calc type's neighbourhood
        if planner:
            s += "\n" + (sources.get(PLANNER, "") if sources is not None else _read(PLANNER))
        for cap, (rx, ask) in SOLAR_CAPS.items():
            if not re.search(rx, s, re.I):
                out.append({"cls": "S", "page": page, "key": cap, "ask": ask,
                            "detail": f"the solar planner on {page} has no {cap} (measured in {measured})"})
    return out


def _calculators(sources: dict | None) -> list[dict]:
    out = []
    calcs = sorted(sources) if sources is not None else sorted(
        p.replace(os.sep, "/") for p in glob.glob(str(ROOT / "tools" / "*" / "index.html")))
    for f in calcs:
        rel = f.replace(str(ROOT).replace(os.sep, "/") + "/", "") if sources is None else f
        if not (rel.startswith("tools/") and rel.endswith("/index.html")):
            continue
        name = rel.split("/")[1]
        s = sources[f] if sources is not None else _read(rel)
        for feat, (rx, ask) in CALC_FEATURES.items():
            if name == SOLAR_CALC and feat in SOLAR_COVERS:
                continue
            if not re.search(rx, s, re.I):
                out.append({"cls": "P", "page": rel, "key": feat, "ask": ask,
                            "detail": f"the {name} calculator has no {feat}"})
    return out


def _guides(sources: dict | None) -> list[dict]:
    out = []
    guides = sorted(p for p in (sources or {}) if p.startswith("learn/")) if sources is not None else sorted(
        p.replace(os.sep, "/").replace(str(ROOT).replace(os.sep, "/") + "/", "")
        for p in glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    for g in guides:
        s = sources[g] if sources is not None else _read(g)
        if not re.search(LEARN_CTA, s, re.I):
            out.append({"cls": "L", "page": g, "key": "tool cta",
                        "ask": "send the reader of this guide to the tool it is about, from the guide itself",
                        "detail": f"{g} links no calculator and carries no learn-link CTA"})
    return out


def _journeys(prod: list[str]) -> list[dict]:
    if not JOURNEYS.exists():
        return []
    j = json.loads(JOURNEYS.read_text(encoding="utf-8"))
    have = {p.get("page") for p in (j.get("per_page") or [])}
    return [{"cls": "J", "page": p, "key": "live journey",
             "ask": "keep a live journey on this page that a person's real path passes, in Chromium and WebKit",
             "detail": f"{p} has no entry in live_page_journeys_results.json"} for p in prod if p not in have]


def _critic(prod: list[str]) -> list[dict]:
    if not CRITIC.exists():
        return []
    stems = {p[:-5] for p in prod}
    doc = json.loads(CRITIC.read_text(encoding="utf-8"))
    rows = doc["rows"] if isinstance(doc, dict) and "rows" in doc else doc
    cells: dict[tuple, Counter] = {}
    for x in rows:
        if x.get("status") != "critiqued":
            continue
        cell = x.get("cell") or ""
        persona = cell.split("|")[1] if "|" in cell else ""
        if persona == "anon":
            continue
        for f in (x.get("findings") or []):
            m = CRITIC_DIM.match(str(f.get("evidence", "")))
            if not m:
                continue
            pg, dim = m.group("page").split("/")[-1], m.group("dim")
            if pg in stems and dim != "N1":
                cells.setdefault((pg, dim), Counter())[x.get("id")] += 1
    return [{"cls": "C", "page": f"{pg}.html", "key": dim,
             "ask": f"close the critic finding {dim} on this page and keep it closed",
             "detail": f"critic dim {dim} on {pg}.html left critiqued with a finding by "
                       f"{len(ids)} signed-in walk(s): {', '.join(sorted(ids)[:4])}"}
            for (pg, dim), ids in sorted(cells.items())]


def _provenance(sources: dict | None) -> list[dict]:
    """R: one cell per page (production, founder or public, learn articles excepted) whose source carries provenance
    and no bottom Sources area. The cell ends when the page's provenance moves into its data-wh-sources area."""
    if sources is not None:
        pages = sorted(p for p in sources if p.endswith(".html") and not (p.startswith("learn/") and p != "learn/index.html"))
    else:
        from sublayer_inventory import page_classes
        pages = sorted(p for v in page_classes().values() for p in v
                       if not (p.startswith("learn/") and p != "learn/index.html"))
    out = []
    for p in pages:
        s = sources[p] if sources is not None else _read(p)
        if PROVENANCE.search(s) and SOURCES_AREA not in s:
            out.append({"cls": "R", "page": p, "key": "provenance at the foot",
                        "ask": ("keep its source lines and its how-it-is-computed notes out of the space a person reads "
                                "first, in one Sources area at the foot of the page"),
                        "detail": f"{p} shows its provenance where a person's attention is, and has no Sources area at "
                                  f"its foot"})
    return out


def collect(sources: dict | None = None) -> list[dict]:
    """Every measured cell, class-major in CLASSES order, then page, then key (the planner's own order for S)."""
    sites = _solar(sources) + _calculators(sources) + _guides(sources) + _provenance(sources)
    if sources is None:
        prod = production_pages()
        sites += _journeys(prod) + _critic(prod)
    order = list(CLASSES)
    caps, feats = list(SOLAR_CAPS), list(CALC_FEATURES)

    def k(s):
        sub = caps.index(s["key"]) if s["cls"] == "S" else feats.index(s["key"]) if s["cls"] == "P" else s["key"]
        return (order.index(s["cls"]), s["page"] if s["cls"] != "S" else "", str(sub).zfill(3), s["page"])
    sites.sort(key=k)
    return sites


def self_test() -> int:
    sources = {
        "tools/solar-pv-calculator/index.html": "<p>Array size 121 kWp. Cost estimate ₱</p>",
        "engineering-design.js": "x" * 10 + "Solar PV System inverter battery bank autonomy peak sun array size",
        "tools/solar-pv-calculator/index.html#": "",
        "tools/fan-calculator/index.html": "<p>We recommend a 2 kW fan. Print this.</p>",
        "learn/a/index.html": '<a href="/tools/fan-calculator/">Try it</a>',
        "learn/b/index.html": "<p>no link</p>",
        "inventory.html": "<p id=\"x\"></p><script>x.innerHTML = renderSourceChip({source:'v'})</script>",
        "hive.html": "<section data-wh-sources><p class=\"wh-source-chip\">Based on</p></section>",
    }
    got = collect(sources)
    by = Counter(s["cls"] for s in got)
    solar_calc = {s["key"] for s in got if s["cls"] == "S" and s["page"].startswith("tools/")}
    ed = {s["key"] for s in got if s["cls"] == "S" and s["page"] == "engineering-design.html"}
    p_solar = {s["key"] for s in got if s["cls"] == "P" and SOLAR_CALC in s["page"]}
    p_fan = {s["key"] for s in got if s["cls"] == "P" and "fan" in s["page"]}
    ok = ("array Wp & panel count" not in solar_calc and "cost estimate ₱" not in solar_calc and len(solar_calc) == 10
          and "inverter sizing" not in ed and "appliance list builder" in ed
          and p_solar == {"scenario compare"} and p_fan == {"share/save", "scenario compare"}
          and by["L"] == 1
          and {s["page"] for s in got if s["cls"] == "R"} == {"inventory.html"})
    print(("PASS" if ok else "FAIL") + f" enhancement inventory self-test - {dict(by)}")
    return 0 if ok else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    sites = collect()
    if args.json:
        print(json.dumps(sites, indent=1, ensure_ascii=False))
        return 0
    by = Counter(s["cls"] for s in sites)
    pub = sum(1 for s in sites if "/" in s["page"])
    print("\nENHANCEMENT INVENTORY - one cell per capability a page's own source lacks")
    print("=" * 84)
    for c, (label, layer) in CLASSES.items():
        extra = ""
        if c == "S":
            extra = "  (" + " · ".join(f"{pg} {sum(1 for s in sites if s['cls'] == 'S' and s['page'] == pg)}"
                                       for pg, _m, _a in SOLAR_SURFACES) + ")"
        if c == "P":
            extra = "  (" + " · ".join(f"{f} {sum(1 for s in sites if s['cls'] == 'P' and s['key'] == f)}"
                                       for f in CALC_FEATURES) + ")"
        print(f"  {c} · {label:<52} (layer {layer:<2}): {by.get(c, 0):>4}{extra}")
    print(f"  = {len(sites)} cells · public {pub} · production {len(sites) - pub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
