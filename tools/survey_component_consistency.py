"""
survey_component_consistency.py  —  ① COMPONENT battery (Layer B, the spine).
================================================================================
The missing ALTITUDE from BATTERY_ARCHITECTURE.md. Page ② asks "is this SCREEN
right?"; this asks the level BELOW: **is this PART (a design-system primitive)
rendered CONSISTENTLY everywhere it appears?** This is Brad Frost's Interface
Inventory at the atom/molecule level — the thing a single-page battery is
structurally blind to (it only ever sees one page's copy).

GROUNDED on what the repo already declares:
  - the class-level primitives (`.simple-card` + `.sc-label/.sc-hero/.sc-sub/
    .sc-tag`, `.sum-card`, chips/pills, tabs) — the KPI/》control vocabulary;
  - the CAPABILITY REGISTRY (`<!-- capability: NAME — … -->` tags +
    `validate_capability_dedup.py` / `capability_dedup_report.json`) — the repo's
    own canonical list of visual primitives.

WHAT IT COMPUTES (deterministic, static — the live DOM-accurate confirm is the
`__UFAI.component(sel)` half, see ufai_battery.js v1.4.0):
  1. CENSUS — instances of each primitive per page (exact).
  2. SHAPE CONSISTENCY — for each instance, the set of recognized SUB-PARTS
     present in its block (windowed scan). The MODAL shape is the de-facto
     contract; an instance missing a REQUIRED sub-part, or holding a minority
     shape, is a consistency DRIFT candidate. (Static-window confidence; the live
     component() walks real DOM children to confirm.)
  3. CAPABILITY DECLARATIONS — every `<!-- capability: NAME -->` and where it
     lives, cross-referenced with the dedup report so a primitive built twice is
     visible at this altitude too.

DOCTRINE (same as every battery): SURFACES drift; never auto-edits markup. Real
DEFECTs (a card missing its label) are fixed inline by the agent; structural
TASTE (a one-off variant that maybe should converge) is queued as a critic
candidate → sweep_critiques.json → you dispose.

OUTPUT:
  - component_consistency_report.md          — the human report
  - component_consistency_corpus.json        — machine bridge (platform battery reads it)
  - component_consistency_candidates.json    — {candidates:[…]} → ufai_ingest.py

USAGE:  python tools/survey_component_consistency.py
"""

from __future__ import annotations

import datetime
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_RE = re.compile(
    r"(\.backup\d*\.html$|-test\.html$|test-.*\.html$|^index-.*-test|"
    r"observability|symbol-gallery|validator-catalog|architecture|"
    r"founder-console|platform-health|public-feed|llm-observability)",
    re.I,
)

# ── the design-system primitive registry (grounded in the live class vocabulary).
# Each: the marker class, the SUB-PARTS that define its shape (required vs
# optional), and how big a window to scan after the opening tag for them.
PRIMITIVES = {
    "simple-card": {
        "label": "KPI tile (.simple-card)",
        "required": ["sc-label", "sc-hero"],
        "optional": ["sc-sub", "sc-tag"],
        "window": 700,
    },
    "sum-card": {
        "label": "Count-chip summary (.sum-card → .sn/.sl)",
        "required": ["sn", "sl"],
        "optional": [],
        "window": 240,
    },
}
# lighter primitives we only CENSUS (shape contract not pinned) — surfaced so the
# inventory is complete; consistency of these is a live component() check.
CENSUS_ONLY = ["view-tab", "filter-chip", "phase-tab", "shift-pill", "chip", "pill", "stepper"]

CAP_RE = re.compile(r"<!--\s*capability:\s*([a-z0-9_]+)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def slug(p: str) -> str:
    return p.replace(".html", "")


def class_re(cls: str) -> re.Pattern:
    return re.compile(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"', re.I)


def opening_tags(html: str, cls: str):
    """Yield (start_index, opening_tag_text) for each element whose class list
    contains `cls`."""
    for m in re.finditer(r"<(\w+)\b[^>]*\bclass=\"([^\"]*)\"[^>]*>", html):
        classes = m.group(2).split()
        if cls in classes:
            yield m.start(), m.group(0), classes


def harvest_page(page: str, html: str) -> dict:
    prims = {}
    for cls, spec in PRIMITIVES.items():
        rows = list(opening_tags(html, cls))   # (start, tag, classes) in document order
        starts = [r[0] for r in rows]
        instances = []
        for i, (start, tag, classes) in enumerate(rows):
            # BOUND the window to this element's own block: stop at the next
            # instance of the SAME primitive (siblings) or a max cap — a fixed
            # window bleeds into the next card and falsely homogenizes the shape.
            cap = start + spec["window"]
            nxt = starts[i + 1] if i + 1 < len(starts) else len(html)
            window = html[start:min(cap, nxt)]
            present = [sp for sp in (spec["required"] + spec["optional"])
                       if class_re(sp).search(window)]
            modifiers = sorted(c for c in classes if c.startswith("tag-")
                               or c in ("critical", "high", "medium", "low", "ok"))
            instances.append({
                "shape": tuple(sorted(present)),
                "missing_required": [r for r in spec["required"] if r not in present],
                "modifiers": modifiers,
            })
        prims[cls] = instances
    census = {c: len(list(opening_tags(html, c))) for c in CENSUS_ONLY}
    caps = sorted(set(CAP_RE.findall(html)))
    return {"page": page, "primitives": prims, "census": census, "capabilities": caps}


def compute(corpus: dict) -> dict:
    # per-primitive cross-page shape distribution
    prim_report = {}
    candidates = []
    for cls, spec in PRIMITIVES.items():
        shapes: dict[tuple, list] = defaultdict(list)   # shape -> [(page, idx)]
        missing_hits = []                                # instances missing a required part
        total = 0
        for page, e in corpus.items():
            for i, inst in enumerate(e["primitives"].get(cls, [])):
                total += 1
                shapes[inst["shape"]].append(page)
                if inst["missing_required"]:
                    missing_hits.append({"page": page, "missing": inst["missing_required"],
                                         "shape": list(inst["shape"])})
        if total == 0:
            continue
        # modal shape = the de-facto contract
        ranked = sorted(shapes.items(), key=lambda kv: -len(kv[1]))
        modal = ranked[0][0] if ranked else ()
        minority = []
        for shape, pages in ranked[1:]:
            minority.append({"shape": list(shape), "count": len(pages),
                             "pages": sorted(set(slug(p) for p in pages)),
                             "delta_vs_modal": sorted(set(modal) ^ set(shape))})
        prim_report[cls] = {
            "label": spec["label"], "instances": total,
            "modal_shape": list(modal), "modal_count": len(ranked[0][1]) if ranked else 0,
            "distinct_shapes": len(shapes), "minority_shapes": minority,
            "missing_required": missing_hits,
        }
        # candidates: a missing REQUIRED part = a real shape DEFECT (queue as DEFECT-ish
        # but IA/TASTE per ufai_ingest doctrine = surfaced, agent fixes inline); a
        # minority shape = converge-or-justify TASTE.
        for mh in missing_hits[:20]:
            candidates.append({
                "key": f"sweep:component:{cls}:missing-{'-'.join(mh['missing'])}:{slug(mh['page'])}",
                "page": mh["page"], "wave": 0,
                "title": f".{cls} on {slug(mh['page'])} is missing required {', '.join('.'+x for x in mh['missing'])}",
                "pillar": "U/Component", "severity": "Minor", "effort": "S", "flag": "TASTE",
                "should_be": f"the .{cls} primitive's contract is {[ '.'+x for x in spec['required']]} "
                             f"(modal shape {['.'+x for x in modal]}); this instance drifts — add the "
                             "missing sub-part or justify the variant. (component battery, static-window; "
                             "confirm via __UFAI.component('." + cls + "')).",
            })
        if len(minority) >= 1 and len(modal) > 0:
            worst = minority[0]
            candidates.append({
                "key": f"sweep:component:{cls}:shape-variants",
                "page": (corpus and next(iter(corpus))) or "index.html", "wave": 0,
                "title": f".{cls} renders in {len(shapes)} different shapes across pages",
                "pillar": "U/Component", "severity": "Polish", "effort": "M", "flag": "TASTE",
                "should_be": f"the modal .{cls} shape is {['.'+x for x in modal]} ({prim_report[cls]['modal_count']} "
                             f"instances); {len(minority)} minority variant(s) exist e.g. on "
                             f"{', '.join(worst['pages'][:4])} (delta {['.'+x for x in worst['delta_vs_modal']]}). "
                             "Converge to one shape (Jakob/consistency) or document the intentional variant.",
            })

    # capability declarations + dedup cross-ref
    cap_pages: dict[str, list] = defaultdict(list)
    for page, e in corpus.items():
        for c in e["capabilities"]:
            cap_pages[c].append(slug(page))
    dedup = {}
    cdr = ROOT / "capability_dedup_report.json"
    if cdr.exists():
        try:
            dedup = json.loads(cdr.read_text(encoding="utf-8"))
        except Exception:
            dedup = {}

    # census rollup for the light primitives
    census_roll = {}
    for c in CENSUS_ONLY:
        pages = {slug(p): e["census"].get(c, 0) for p, e in corpus.items() if e["census"].get(c, 0)}
        if pages:
            census_roll[c] = {"pages": len(pages), "total": sum(pages.values()), "by_page": pages}

    return {"primitives": prim_report, "capabilities": {k: sorted(set(v)) for k, v in cap_pages.items()},
            "capability_dedup": {"clones": dedup.get("clones") or dedup.get("duplicates"),
                                 "note": dedup.get("note") or dedup.get("_README")},
            "census": census_roll, "candidates": candidates}


def render_md(corpus: dict, g: dict) -> str:
    L = []
    L.append("# Component Consistency Report — ① Component battery (Phase 1)\n")
    L.append("> **The altitude below the page.** Is each design-system PRIMITIVE rendered the same"
             " way everywhere? Static spine (windowed shape scan); the DOM-accurate confirm is"
             " `__UFAI.component('.simple-card')` live. SURFACES drift — fixes nothing.\n")
    L.append(f"- Pages: **{len(corpus)}**  ·  pinned primitives: **{len(g['primitives'])}**  ·  "
             f"census primitives: **{len(g['census'])}**  ·  capability tags: **{len(g['capabilities'])}**\n")

    L.append("## 1. Pinned primitives — shape consistency\n")
    for cls, r in g["primitives"].items():
        L.append(f"### `.{cls}` — {r['label']}\n")
        L.append(f"- **{r['instances']}** instances · modal shape "
                 f"{['.'+x for x in r['modal_shape']] or '(no sub-parts)'} "
                 f"({r['modal_count']} instances) · **{r['distinct_shapes']}** distinct shape(s).")
        if r["missing_required"]:
            L.append(f"- ⚠️ **{len(r['missing_required'])} instance(s) MISSING a required sub-part:** "
                     + "; ".join(f"{slug(m['page'])} missing {', '.join('.'+x for x in m['missing'])}"
                                 for m in r["missing_required"][:8]) + ".")
        if r["minority_shapes"]:
            L.append("- Minority shapes (converge or justify):")
            for ms in r["minority_shapes"][:6]:
                L.append(f"    - {['.'+x for x in ms['shape']]} ×{ms['count']} "
                         f"({', '.join(ms['pages'][:5])}) — Δ vs modal {['.'+x for x in ms['delta_vs_modal']]}")
        if not r["missing_required"] and not r["minority_shapes"]:
            L.append("- ✅ one consistent shape on every page.")
        L.append("")

    L.append("## 2. Capability registry (declared visual primitives)\n")
    L.append("_`<!-- capability: NAME -->` tags = the repo's own canonical primitive list."
             " Cross-referenced with `capability_dedup_report.json`._\n")
    if g["capabilities"]:
        L.append("| Capability | Declared on |")
        L.append("|---|---|")
        for cap, pages in sorted(g["capabilities"].items()):
            L.append(f"| `{cap}` | {', '.join(pages[:8])}{' …' if len(pages) > 8 else ''} |")
    else:
        L.append("_No `capability:` tags found._")
    L.append("")

    L.append("## 3. Census — light primitives (consistency = live component() check)\n")
    if g["census"]:
        L.append("| Primitive | Pages | Total instances |")
        L.append("|---|---|---|")
        for c, r in sorted(g["census"].items(), key=lambda kv: -kv[1]["total"]):
            L.append(f"| `.{c}` | {r['pages']} | {r['total']} |")
    L.append("")
    L.append("---")
    L.append(f"### Queue\n`python ufai_ingest.py component_consistency_candidates.json` → "
             f"{len(g['candidates'])} candidate(s) into `sweep_critiques.json`. "
             "Live confirm any shape drift with `__UFAI.component('.<primitive>')` (DOM-accurate).")
    return "\n".join(L) + "\n"


def main() -> int:
    nav_pages = set(re.findall(r"href:\s*'([a-z0-9-]+\.html)'",
                               (ROOT / "nav-hub.js").read_text(encoding="utf-8", errors="ignore")
                               if (ROOT / "nav-hub.js").exists() else ""))
    corpus = {}
    for p in sorted(ROOT.glob("*.html")):
        if EXCLUDE_RE.search(p.name):
            continue
        html = p.read_text(encoding="utf-8", errors="ignore")
        if not (class_re("simple-card").search(html) or p.name in nav_pages):
            continue
        corpus[p.name] = harvest_page(p.name, html)

    g = compute(corpus)

    (ROOT / "component_consistency_corpus.json").write_text(json.dumps({
        "_doc": "① Component battery corpus. Static spine; live DOM confirm = __UFAI.component().",
        "pages": sorted(corpus), "corpus": corpus, "groups": g,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "component_consistency_report.md").write_text(render_md(corpus, g), encoding="utf-8")
    (ROOT / "component_consistency_candidates.json").write_text(json.dumps({
        "_doc": "Component battery critic candidates (sweep_critiques schema). "
                "Route: python ufai_ingest.py component_consistency_candidates.json",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "candidates": g["candidates"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    miss = sum(len(r["missing_required"]) for r in g["primitives"].values())
    var = sum(1 for r in g["primitives"].values() if r["distinct_shapes"] > 1)
    print(f"Component battery -- {len(corpus)} pages, {len(g['primitives'])} pinned primitives")
    for cls, r in g["primitives"].items():
        print(f"  .{cls:12s} {r['instances']:3d} instances / {r['distinct_shapes']} shape(s)"
              + (f" / {len(r['missing_required'])} missing-required" if r["missing_required"] else ""))
    print(f"  {len(g['capabilities'])} capability tags, {len(g['census'])} census primitives")
    print(f"  {len(g['candidates'])} candidate(s) ({miss} missing-required, {var} multi-shape primitives)")
    print("  -> component_consistency_report.md + .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
