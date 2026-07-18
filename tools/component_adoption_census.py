"""
component_adoption_census.py — ① Component battery, ADOPTION axis (Layer F).
================================================================================
The sibling of survey_component_consistency.py: that tool asks "is each rendered
copy of a primitive the SAME SHAPE?"; this asks the FULLSTACK_COMPONENT_LIBRARY
question: "which pages that NEED a canonical primitive actually ADOPT it?"

FAMILY_UFAI §10's law, instrumented: a dim that fails on N pages is ONE unadopted
component. A component with 0% adoption is indistinguishable from one that does
not exist — except it already cost the build. This census makes that visible and
MEASURED, per primitive, per page, so the roadmap board is never asserted.

SSOT: design_component_registry.json  (the canonical library — detect + need rules)
      family_rubric_baseline.json     (the 32-page family — the denominator)

DETECTION (static, comment-stripped — a mention in a comment is NOT adoption;
see feedback_grep_matched_the_comment_not_the_link):
  css-class   — class token appears in a class="…" attribute
  js-call     — NAME( call-site in page script (definitions `function NAME(` excluded;
                pages must never redefine utils.js fns inline — redefinitions are
                reported as DRIFT, not adoption)
  js-ident    — NAME = assignment (e.g. window.WH_FIL_PAGE = {…})
  script-src  — <script src="FILE">
  delegated   — owned by another gate (validate_design_tokens.py); no % here

NEED (the denominator; each rule ∪ adopters so an adopted page always counts):
  family / async-data / renders-date / renders-number / peso / destructive /
  wide-table / interactive / kpi-cards / census-only (no %)

OUTPUT:
  component_adoption_baseline.json — per primitive: adopters, need, pct, gap pages
                                     (the forward-only floors the F-P2 gate reads)
  component_adoption_report.md     — the human board

USAGE:  python tools/component_adoption_census.py
"""

from __future__ import annotations

import datetime
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "design_component_registry.json"
FAMILY = ROOT / "family_rubric_baseline.json"
OUT_JSON = ROOT / "component_adoption_baseline.json"
OUT_MD = ROOT / "component_adoption_report.md"

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)


SCRIPT_STYLE_RE = re.compile(r"(<(script|style)\b[^>]*>)(.*?)(</\2>)", re.S | re.I)


def strip_comments(src: str) -> str:
    """HTML comments stripped globally; JS/CSS comments stripped ONLY inside
    <script>/<style> regions. Applying /*…*/ to raw markup swallows everything
    between a stray '/*' in page text and the next '*/' — it ate logbook's
    <details class="wh-disclose"> markup and false-gapped the census."""
    src = HTML_COMMENT_RE.sub("", src)

    def _clean(m: re.Match) -> str:
        body = BLOCK_COMMENT_RE.sub("", m.group(3))
        body = LINE_COMMENT_RE.sub("", body)
        return m.group(1) + body + m.group(4)

    return SCRIPT_STYLE_RE.sub(_clean, src)


def class_used(src: str, cls: str) -> bool:
    return re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"', src) is not None


def js_called(src: str, name: str) -> bool:
    return re.search(r"(?<!function )\b" + re.escape(name) + r"\s*\(", src) is not None


def js_redefined(src: str, name: str) -> bool:
    return re.search(r"\bfunction\s+" + re.escape(name) + r"\s*\(", src) is not None


def js_ident(src: str, name: str) -> bool:
    return re.search(r"\b" + re.escape(name) + r"\s*=", src) is not None


def script_src(src: str, file: str) -> bool:
    return re.search(r'<script[^>]*src="' + re.escape(file) + r'"', src) is not None


# ── need rules (denominator heuristics). Coarse by design; each is named in the
# registry so the board is honest about HOW "need" was measured.
NEED_FNS = {
    "family":         lambda s: True,
    "async-data":     lambda s: re.search(r"\.from\(\s*['\"`]|functions\.invoke", s) is not None,
    # renders-date counts RENDER calls only — `new Date(` alone is date MATH (diffs,
    # comparisons), not display; counting it over-stated the FD1a denominator by 16 pages.
    "renders-date":   lambda s: re.search(r"toLocaleDateString\(|toLocaleTimeString\(", s) is not None,
    # renders-number counts locale-DISPLAY sites only. `.toFixed(` is excluded: it is
    # ambiguous (fixed-dp strings feed exports/inputs/calcs where whFmtNum's thousands
    # separators would BREAK parsing — the display-vs-math split). Date-parted
    # toLocaleString calls belong to renders-date, not here.
    # timeZone-only opts = the TZ-shift COMPUTE trick (new Date(d.toLocaleString(…,{timeZone}))),
    # not a display site — alert-hub's phtNow taught this exclusion.
    "renders-number": lambda s: any(not re.search(r"month|year|day|hour|weekday|timeZone", m.group(1))
                                    for m in re.finditer(r"\.toLocaleString\(([^)]{0,80})\)", s)),
    "peso":           lambda s: "₱" in s,
    # empty-arg .delete() = a supabase row delete; Map/Set/searchParams .delete(x) take
    # an argument and are NOT destructive user actions (audit-log/voice-journal false hits).
    "destructive":    lambda s: re.search(r"\.delete\(\s*\)|(?<![\w.])confirm\(", s) is not None,
    "wide-table":     lambda s: "<table" in s,
    "interactive":    lambda s: "<button" in s,
    "kpi-cards":      lambda s: class_used(s, "simple-card"),
    "relative-time":  lambda s: re.search(r"'just now'|[mhd] ago'", s) is not None,
}


def detect_adoption(src: str, detects: list[dict]) -> tuple[bool, list[str]]:
    """Return (adopted, drift_notes) for one page against one component."""
    drift = []
    hit = False
    for d in detects:
        kind = d.get("kind")
        if kind == "css-class" and class_used(src, d["class"]):
            hit = True
        elif kind == "js-call":
            if js_called(src, d["name"]):
                hit = True
            # allow_redefine: utils.js itself sanctions the override (e.g. _t is defined
            # `if (typeof window._t !== 'function')` — pages may install a richer one).
            if js_redefined(src, d["name"]) and not d.get("allow_redefine"):
                drift.append(f"redefines function {d['name']}() inline (must use utils.js)")
        elif kind == "js-ident" and js_ident(src, d["name"]):
            hit = True
        elif kind == "script-src" and script_src(src, d["file"]):
            hit = True
    return hit, drift


def run_census() -> tuple[list[dict], list[dict], int]:
    """Recompute adoption LIVE from the registry + family pages. Returns
    (rows, drift_notes, n_pages). The F-P2 gate imports THIS (never a stale
    report file) so the ratchet always compares against reality."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fam = json.loads(FAMILY.read_text(encoding="utf-8"))
    pages = sorted(fam["pages"].keys() if isinstance(fam["pages"], dict) else fam["pages"])

    src_by_page = {}
    for p in pages:
        f = ROOT / p
        if not f.exists():
            print(f"  !! family page missing on disk: {p}")
            continue
        src_by_page[p] = strip_comments(f.read_text(encoding="utf-8", errors="ignore"))

    rows = []
    drift_notes = []
    for comp in reg["components"]:
        detects = comp["detect"]
        if any(d.get("kind") == "delegated" for d in detects):
            rows.append({
                "id": comp["id"], "class": comp["class"], "name": comp["name"],
                "satisfies": comp["satisfies"], "mode": "delegated",
                "gate": next(d["gate"] for d in detects if d.get("kind") == "delegated"),
            })
            continue

        adopters = []
        for p, src in src_by_page.items():
            hit, drift = detect_adoption(src, detects)
            if hit:
                adopters.append(p)
            for note in drift:
                drift_notes.append({"page": p, "component": comp["id"], "note": note})

        need_rule = comp["need"]
        if need_rule == "census-only":
            rows.append({
                "id": comp["id"], "class": comp["class"], "name": comp["name"],
                "satisfies": comp["satisfies"], "mode": "census-only",
                "adopters_n": len(adopters), "adopters": sorted(adopters),
            })
            continue

        need_fn = NEED_FNS[need_rule]
        # registry "exempt": [pages] — a JUSTIFIED opt-out (reason documented in the registry
        # row); exempt pages leave the denominator entirely (never counted as gap OR adopter).
        exempt = set(comp.get("exempt", []))
        adopters = [p for p in adopters if p not in exempt]
        need_pages = sorted(({p for p, src in src_by_page.items() if need_fn(src)} | set(adopters)) - exempt)
        gap = sorted(set(need_pages) - set(adopters))
        pct = round(100 * len(adopters) / len(need_pages)) if need_pages else None
        rows.append({
            "id": comp["id"], "class": comp["class"], "name": comp["name"],
            "satisfies": comp["satisfies"], "mode": "measured", "need_rule": need_rule,
            "adopters_n": len(adopters), "need_n": len(need_pages), "pct": pct,
            "adopters": sorted(adopters), "gap": gap,
            "status": comp.get("status", "built"),
        })
    return rows, drift_notes, len(src_by_page)


def main() -> int:
    rows, drift_notes, n_pages = run_census()
    measured = [r for r in rows if r["mode"] == "measured"]
    # FLOORS ONLY RATCHET UP, even from the census CLI: without this, re-running the
    # census after a regression would silently re-baseline DOWNWARD and the F-P2 gate
    # (validate_component_adoption.py) would never see the drop. The gate is the only
    # thing that fails on floor breaches; this writer must never erode its floors.
    prior_floors = {}
    if OUT_JSON.exists():
        try:
            prior_floors = json.loads(OUT_JSON.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            prior_floors = {}
    floors = {r["id"]: max(r["adopters_n"], prior_floors.get(r["id"], 0)) for r in measured}
    out = {
        "_doc": "Component adoption baseline (Layer F). Generated by tools/component_adoption_census.py "
                "from design_component_registry.json over the family_rubric_baseline.json pages. "
                "These are the forward-only floors validate_component_adoption.py ratchets on.",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "family_pages": n_pages,
        "rows": rows,
        "drift": drift_notes,
        "floors": floors,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    L = ["# Component Adoption Report — Layer F (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §2.2)\n",
         f"> MEASURED {datetime.date.today().isoformat()} over **{n_pages}** family pages. "
         "% = adopters / pages-that-need-it (need rule named per row; ∪ adopters). "
         "census-only rows have no denominator by design; delegated rows are owned by another gate.\n",
         "| ID | Class | Canonical primitive | Satisfies | Adoption | % | Gap (first 6) |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["mode"] == "delegated":
            L.append(f"| {r['id']} | {r['class']} | {r['name']} | {r['satisfies']} | → `{r['gate']}` | — | — |")
        elif r["mode"] == "census-only":
            L.append(f"| {r['id']} | {r['class']} | {r['name']} | {r['satisfies']} | {r['adopters_n']} page(s) | n/a | — |")
        else:
            gap_s = ", ".join(g.replace(".html", "") for g in r["gap"][:6]) + (" …" if len(r["gap"]) > 6 else "")
            L.append(f"| {r['id']} | {r['class']} | {r['name']} | {r['satisfies']} | "
                     f"**{r['adopters_n']}/{r['need_n']}** ({r['need_rule']}) | **{r['pct']}%** | {gap_s or '—'} |")
    if drift_notes:
        L.append("\n## ⚠️ Drift — inline redefinitions of canonical functions\n")
        for d in drift_notes:
            L.append(f"- `{d['page']}` [{d['component']}]: {d['note']}")
    L.append("\n---\nLive confirm any row: `__UFAI.component('.<class>')` (DOM-accurate) or a Playwright "
             "walk of the WORKED state. Ratchet: `python tools/validate_component_adoption.py`.")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"Adoption census -- {n_pages} family pages, {len(rows)} registry rows "
          f"({len(measured)} measured, {sum(1 for r in rows if r['mode']=='census-only')} census-only, "
          f"{sum(1 for r in rows if r['mode']=='delegated')} delegated)")
    for r in measured:
        print(f"  {r['id']:5s} {r['name'][:44]:44s} {r['adopters_n']:3d}/{r['need_n']:<3d} {str(r['pct'])+'%':>5s}")
    if drift_notes:
        print(f"  !! {len(drift_notes)} inline-redefinition drift note(s)")
    print("  -> component_adoption_baseline.json + component_adoption_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
