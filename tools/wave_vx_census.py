#!/usr/bin/env python3
"""wave_vx_census.py - Wave VX's cells, measured (2026-11-14). Read-only: it prints, it writes nothing.

Ian, 2026-11-14: "we have to plan to add more numbers of trajectories to our trajectories roadmap ... based on the ufai
ui ux, group of personas, full stack architectural layers, diverse journey scenarios, view ports, llm, seo aeo geo xeo."

WHAT THE CUBE LEFT OUT (measured on the union of every registry shard, 50,593 live rows, the day this was written):
  device    43,327 rows say `any`; tablet-768 has 41, wide-1920 308, and no row is a phone turned sideways
  journeys  the scenarios are walked under normal conditions; "slow 3G" appears in 3 rows
  LLM       the LM rows are cast as `any`, so no persona GROUP has its own answer from a page's AI
  search    no row says XEO; llms.txt appears in 7, Perplexity in 7
So Wave VX is six families of cells. A cell is EMPTY when no live row already covers it; the seeder (a later step)
writes one row per EMPTY cell. THE NUMBER IS DERIVED, NEVER TYPED: pages and layers come from sublayer_inventory,
admitted personas from cube_census (the journey-paths gate), scenarios from group_journey_census, AI surfaces from the
LM rows, search coverage from the KA / SE rows. The constants below are the NEW decisions only, each with its reason.

    python tools/wave_vx_census.py                    # the table
    python tools/wave_vx_census.py --family VX-X      # one family, with its breakdown
    python tools/wave_vx_census.py --json             # the machine population (one entry per EMPTY cell)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

# ── the new decisions (2026-11-14) ─────────────────────────────────────────────────────────────────────────────────────
# Persona groups: the people who read a page the same way. adversary keeps its own waves (its rows are attacks, not reads).
VX_GROUPS = OrderedDict([
    ("field", ("worker", "driver-worker", "returner", "new-user")),        # on the floor, phone in hand
    ("lead", ("supervisor", "fleet-supervisor", "solo-owner")),            # decides and assigns
    ("market", ("buyer", "seller")),                                       # trades parts and services
    ("outside", ("anon", "assistive-tech", "machine-client", "oversight")),  # not a member's working session
])
# Widths: the five the registry already names plus a phone turned sideways, which no row has ever read.
VX_WIDTHS = ("narrow-320", "phone-390", "tablet-768", "landscape-844", "desktop-1280", "wide-1920")
# Conditions a journey meets in the field that the walks so far met only one at a time, if at all.
VX_CONDITIONS = OrderedDict([
    ("offline-mid-task", r"offline"),
    ("slow-3g", r"slow[- ]?3g|throttl"),
    ("rate-limited-429", r"\b429\b|rate[- ]?limit"),
    ("session-expired", r"session (has )?expir|expired session|token expir|signed out mid"),
    ("second-device", r"second device|two devices|another device|other device"),
    ("returning-after-30-days", r"30 days|a month away|returning after|after a month"),
])
# What a page's AI must do, per persona group, at the two widths the LM walks use.
VX_LLM_MODES = OrderedDict([
    ("grounded-answer", r"ground|cites? (the|its)|from the page's (real|own)|real numbers|confabulat"),
    ("refusal", r"refus|declin|must not answer|out of scope|leak|instructions hidden"),
    ("no-data", r"no data|nothing to (say|answer)|empty (hive|page)|when there is none"),
    ("provider-down", r"provider|outage|\b5\d\d\b|time[sd]? out|fails? (soft|closed)|degrad"),
    ("long-input", r"long (input|question|message|paste)|truncat|token limit|length"),
])
VX_LLM_WIDTHS = ("phone-390", "desktop-1280")
# The search face of a public page, split by the engine kind that reads it.
VX_SEARCH = OrderedDict([
    ("VX-S", OrderedDict([("title-meta", r"\btitle\b|meta description"), ("canonical", r"canonical"),
                          ("structured-data", r"json-ld|structured data|schema\.org"),
                          ("internal-links", r"internal link|inbound link|orphan"),
                          ("cwv-390", r"\blcp\b|\bcls\b|\binp\b|core web vital|\bcwv\b")])),
    ("VX-A", OrderedDict([("answer-first", r"answer[- ]first"),
                          ("extractable-figure", r"extractable|quotable|a figure an engine")])),
    ("VX-G", OrderedDict([("cited-source", r"\bcit(e|ed|es|ation)"), ("markdown-twin", r"markdown twin|md twin|\.md\b"),
                          ("llms-txt-listed", r"llms\.txt")])),
])
# Cross-engine (XEO): the same page against each answer engine, by the crawler names that engine publishes.
VX_ENGINES = OrderedDict([
    ("google-ai-overviews", ("Googlebot", "Google-Extended")),
    ("bing-copilot", ("Bingbot",)),
    ("chatgpt-search", ("OAI-SearchBot", "GPTBot")),
    ("perplexity", ("PerplexityBot",)),
    ("gemini", ("Google-Extended",)),
    ("claude", ("ClaudeBot", "Claude-SearchBot")),
])
VX_ENGINE_RX = {"google-ai-overviews": r"ai overview|googlebot|google-extended", "bing-copilot": r"\bbing|copilot",
                "chatgpt-search": r"chatgpt|oai-searchbot|gptbot", "perplexity": r"perplexity",
                "gemini": r"\bgemini", "claude": r"claudebot|claude-searchbot|\bclaude\b"}
VX_MILESTONES = OrderedDict([
    ("M14", {"name": "Wave VX: every width and every field condition", "families": ["VX-V", "VX-J"]}),
    ("M15", {"name": "Wave VX: a page's AI, per persona group", "families": ["VX-L"]}),
    ("M16", {"name": "Wave VX: the search face across engines (SEO, AEO, GEO, XEO)", "families": ["VX-S", "VX-A", "VX-G", "VX-X"]}),
])
FAMILIES = ("VX-V", "VX-J", "VX-L", "VX-S", "VX-A", "VX-G", "VX-X")


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _target(r: dict):
    p = r.get("pages") or []
    return p[-1] if p else None


def _text(r: dict) -> str:
    return f"{r.get('title') or ''} {r.get('story') or ''} {r.get('note') or ''}".lower()


def _wave_tag(r: dict) -> str:
    return str(r.get("wave") or "")


def _groups_on(page: str, admitted: dict) -> "OrderedDict[str, list[str]]":
    """{group: [admitted members]} for the groups with at least one member admitted on the page."""
    ps = set(admitted.get(page, []))
    out = OrderedDict()
    for g, members in VX_GROUPS.items():
        m = [p for p in members if p in ps]
        if m:
            out[g] = m
    return out


# ── the families ───────────────────────────────────────────────────────────────────────────────────────────────────────
def viewport_cells(rows, classes, layers, admitted) -> list[dict]:
    have = set()
    for r in rows:
        have.add((_target(r), r.get("device"), r.get("persona")))
    out = []
    for cls, ps in classes.items():
        for page in ps:
            for g, members in _groups_on(page, admitted).items():
                for w in VX_WIDTHS:
                    if any((page, w, p) in have for p in members):
                        continue
                    out.append({"family": "VX-V", "cls": cls, "page": page, "group": g, "persona": members[0],
                                "device": w, "layers": ["F"], "ufai": ["A"]})
    return out


def journey_cells(rows) -> list[dict]:
    import group_journey_census as gc
    scen = []
    for sc in gc.SCENARIOS:
        pages = list(OrderedDict.fromkeys(h[0] for h in sc["hops"]))
        scen.append({"key": sc["code"], "kind": "group", "title": sc["title"], "pages": pages,
                     "persona": next(iter(sc["cast"].values()))[0], "where": list(sc.get("where") or [])})
    solo = OrderedDict()
    for r in rows:
        w = _wave_tag(r)
        if w.startswith("W3-JN"):
            stem = re.split(r" [-·] ", r.get("title") or "")[0].strip()[:90]
            if stem and stem not in solo:
                j = r.get("journey") or {}
                solo[stem] = {"key": r["id"], "kind": "solo", "title": stem, "pages": r.get("pages") or [],
                              "persona": r.get("persona") or "worker", "entry": r.get("entry") or "hub-nav",
                              "pair": j.get("pair") or "", "vertical": j.get("vertical") or "",
                              "signed_in_as": r.get("signed_in_as"), "archetype": j.get("archetype") or ""}
    scen += list(solo.values())
    # rows that belong to a scenario: GJ rows by their scenario code, solo rows by their title stem
    by_key: dict[str, list[dict]] = defaultdict(list)
    codes = {s["key"] for s in scen if s["kind"] == "group"}
    for r in rows:
        gj = r.get("gj") or {}
        code = gj.get("code") or gj.get("scenario")
        if code in codes:
            by_key[code].append(r)
        else:
            stem = re.split(r" [-·] ", r.get("title") or "")[0].strip()[:90]
            if stem in solo:
                by_key[solo[stem]["key"]].append(r)
    out = []
    for s in scen:
        mine = by_key.get(s["key"], [])
        for cond, rx in VX_CONDITIONS.items():
            # ★MATCHED ON WHAT THE ROW IS ABOUT, NEVER ON LENS BOILERPLATE (Fable review, 2026-11-15): every GJ H-layer story
            # says "headers, caching and offline included", which read as offline-covered for all 34 group scenarios
            hit = any(((r.get("journey") or {}).get("condition") == cond)
                      or re.search(rx, f"{r.get('title') or ''} {(r.get('gj') or {}).get('what') or ''}".lower())
                      for r in mine)
            if hit:
                continue
            out.append({"family": "VX-J", "scenario": s["key"], "kind": s["kind"], "title": s["title"],
                        "pages": s["pages"], "persona": s["persona"], "condition": cond,
                        "device": "any" if s["persona"] == "machine-client" else "phone-390",
                        "where": s.get("where", []), "entry": s.get("entry"), "pair": s.get("pair", ""),
                        "vertical": s.get("vertical", ""), "signed_in_as": s.get("signed_in_as"),
                        "archetype": s.get("archetype", ""),
                        "layers": ["A", "F"], "ufai": ["U", "F"]})
    return out


def llm_cells(rows, admitted) -> list[dict]:
    # ★THE AI SURFACE IS lx.page, NOT THE ROUTE'S LAST PAGE (Fable review, 2026-11-15): 394 of 560 LM rows end elsewhere
    lm = [r for r in rows if (r.get("lx") or {}).get("kind") == "llm" and (r.get("lx") or {}).get("page")]
    surfaces = sorted({r["lx"]["page"] for r in lm if r["lx"]["page"] != "companion"})
    by_page: dict[str, list[dict]] = defaultdict(list)
    for r in lm:
        by_page[r["lx"]["page"]].append(r)
    out = []
    for page in surfaces:
        groups = _groups_on(page, admitted) or OrderedDict([("outside", ["anon"])])
        for g, members in groups.items():
            for mode, rx in VX_LLM_MODES.items():
                for w in VX_LLM_WIDTHS:
                    num = w.split("-")[1]
                    covered = any(r.get("persona") in members and re.search(rx, _text(r))
                                  and (r.get("device") == w or (r.get("device") == "any" and num in _text(r)))
                                  for r in by_page[page])
                    if covered:
                        continue
                    out.append({"family": "VX-L", "page": page, "group": g, "persona": members[0], "mode": mode,
                                "device": w, "layers": ["LM"], "ufai": ["U", "F", "I"]})
    return surfaces, out


def search_cells(rows, classes) -> list[dict]:
    pub = list(classes.get("public", []))
    seo = defaultdict(list)
    for r in rows:
        if _wave_tag(r).startswith(("KA", "SE")) and _target(r) in pub:
            seo[_target(r)].append(_text(r))
    out = []
    for fam, checks in VX_SEARCH.items():
        for page in pub:
            for chk, rx in checks.items():
                if any(re.search(rx, t) for t in seo[page]):
                    continue
                out.append({"family": fam, "page": page, "check": chk, "persona": "anon",
                            "device": "phone-390" if chk == "cwv-390" else "any",
                            "layers": ["F", "H"], "ufai": ["F", "A"]})
    return out


def cluster_of(page: str) -> str:
    return page.split("/")[0] + "/" if "/" in page else "(top level)"


def xeo_cells(rows, classes) -> list[dict]:
    pub = list(classes.get("public", []))
    clusters: dict[str, list[str]] = defaultdict(list)
    for p in pub:
        clusters[cluster_of(p)].append(p)
    text_by_page = defaultdict(list)
    for r in rows:
        if _target(r) in pub:
            text_by_page[_target(r)].append(_text(r))
    out = []
    for cl in sorted(clusters):
        for eng, bots in VX_ENGINES.items():
            rx = VX_ENGINE_RX[eng]
            if any(re.search(rx, t) and "xeo" in t for p in clusters[cl] for t in text_by_page[p]):
                continue
            out.append({"family": "VX-X", "cluster": cl, "pages": sorted(clusters[cl]), "engine": eng,
                        "crawlers": list(bots), "persona": "machine-client", "device": "any",
                        "layers": ["H", "F"], "ufai": ["F", "A"]})
    return clusters, out


# ── the census ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def cell_key(fam: str, cell: dict) -> tuple:
    """The identity of a VX cell, the same whether read from the census or from a seeded row's vx.cell."""
    return (fam,) + tuple(str(cell.get(k)) for k in ("page", "cluster", "scenario", "group", "device", "mode", "check",
                                                      "engine", "condition"))


def census(rows: list[dict] | None = None) -> dict:
    import cube_census as cc
    if rows is None:
        from registry_io import load_doc
        rows = load_doc()["trajectories"]
    rows = [t for t in rows if t.get("status") != "descoped"]
    seeded = {cell_key(t["vx"]["family"], t["vx"]["cell"]) for t in rows if (t.get("vx") or {}).get("kind") == "wave-vx"}
    classes = cc.page_classes()
    layers = cc.applicable_layers(classes)
    admitted = cc.admitted_personas(classes, rows)
    fam: dict[str, dict] = OrderedDict()

    v = viewport_cells(rows, classes, layers, admitted)
    v_cells = sum(len(_groups_on(p, admitted)) * len(VX_WIDTHS) for ps in classes.values() for p in ps)
    fam["VX-V"] = {"cells": v_cells, "rows": v,
                   "by": {"cls": Counter(c["cls"] for c in v), "device": Counter(c["device"] for c in v),
                          "group": Counter(c["group"] for c in v)}}

    j = journey_cells(rows)
    import group_journey_census as gc
    solo_total = len({re.split(r" [-·] ", r.get("title") or "")[0].strip()[:90] for r in rows
                      if _wave_tag(r).startswith("W3-JN") and (r.get("title") or "").strip()})
    fam["VX-J"] = {"cells": (len(gc.SCENARIOS) + solo_total) * len(VX_CONDITIONS), "rows": j,
                   "by": {"kind": Counter(c["kind"] for c in j), "condition": Counter(c["condition"] for c in j)},
                   "scenarios": {"group": len(gc.SCENARIOS), "solo": solo_total}}

    surfaces, l = llm_cells(rows, admitted)
    l_cells = sum(max(1, len(_groups_on(p, admitted))) * len(VX_LLM_MODES) * len(VX_LLM_WIDTHS) for p in surfaces)
    fam["VX-L"] = {"cells": l_cells, "rows": l, "surfaces": surfaces,
                   "by": {"mode": Counter(c["mode"] for c in l), "group": Counter(c["group"] for c in l)}}

    s = search_cells(rows, classes)
    npub = len(classes.get("public", []))
    for f, checks in VX_SEARCH.items():
        mine = [c for c in s if c["family"] == f]
        fam[f] = {"cells": npub * len(checks), "rows": mine, "by": {"check": Counter(c["check"] for c in mine)}}

    clusters, x = xeo_cells(rows, classes)
    fam["VX-X"] = {"cells": len(clusters) * len(VX_ENGINES), "rows": x, "clusters": {k: len(v) for k, v in clusters.items()},
                   "by": {"engine": Counter(c["engine"] for c in x)}}

    # ★RE-RUNNABLE (Fable review, 2026-11-15): a cell a VX row already carries is not EMPTY again
    for f in fam.values():
        f["rows"] = [c for c in f["rows"] if cell_key(c["family"], c) not in seeded]
    return {"live_rows": len(rows), "families": fam, "classes": classes, "admitted": admitted,
            "total_cells": sum(f["cells"] for f in fam.values()),
            "total_empty": sum(len(f["rows"]) for f in fam.values())}


LABEL = {"VX-V": "viewports: page x width x persona group", "VX-J": "journeys under a field condition",
         "VX-L": "a page's AI, per persona group, mode and width", "VX-S": "SEO: a public page's search face",
         "VX-A": "AEO: an answer an engine can lift", "VX-G": "GEO: a source a generative engine can cite",
         "VX-X": "XEO: a page cluster against each answer engine"}


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population (one entry per EMPTY cell)")
    ap.add_argument("--family", choices=FAMILIES, help="print one family with its breakdown")
    a = ap.parse_args()
    t0 = time.time()
    c = census()
    if a.json:
        print(json.dumps({"families": {k: {"cells": v["cells"], "empty": len(v["rows"]), "rows": v["rows"]}
                                       for k, v in c["families"].items()},
                          "total_cells": c["total_cells"], "total_empty": c["total_empty"]}, ensure_ascii=False))
        return 0
    print(f"\nWAVE VX - what the cube left out, measured on {c['live_rows']:,} live rows (never typed)")
    print("=" * 100)
    print(f"  {'family':<6} {'cells':>7} {'EMPTY':>7}  what one row is")
    for k, v in c["families"].items():
        if a.family and k != a.family:
            continue
        print(f"  {k:<6} {v['cells']:>7,} {len(v['rows']):>7,}  {LABEL[k]}")
        if a.family:
            for dim, cnt in v.get("by", {}).items():
                print(f"         by {dim}: " + ", ".join(f"{n} {x}" for x, n in sorted(cnt.items(), key=lambda kv: -kv[1])))
            for extra in ("scenarios", "surfaces", "clusters"):
                if extra in v:
                    print(f"         {extra}: {v[extra]}")
    if not a.family:
        print(f"  {'TOTAL':<6} {c['total_cells']:>7,} {c['total_empty']:>7,}  rows the seeder would write (one per EMPTY cell)")
    print(f"  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
