"""
survey_ia_redundancy.py  —  Layer B of the IA-streamlining surveyor (Phase 1).
================================================================================
WHY: the UFAI battery is SINGLE-PAGE → blind to cross-page redundancy. jscpd
(validate_clone_debt.py, ~70 clones / 27.5%) catches TEXTUAL code clones, NOT
the user-facing "the same KPI / action is surfaced on N pages" SEMANTIC
redundancy that makes a product feel repetitive and confusing (Brad Frost
Interface Inventory; NN/g Content Audit). This tool closes that gap.

METHOD (the spine, all deterministic — Phase 1 has NO judgment calls):
  - Brad Frost "Interface Inventory": catalog every unique info-unit + affordance.
  - NN/g "Content Inventory": harvest units, group by MEANING (semantic
    fingerprint), surface where each repeats. (keep/consolidate/move/remove +
    UX-law severity = Phase 2's rubric — NOT computed here.)

GROUNDED on what the codebase ALREADY tags:
  - [data-rag-tile="page:key"] + [data-rag-label="Human label"]  (the canonical
    info-unit registry, ~89 tiles across 16 pages — see tools/tag_all_rag_tiles.py)
  - page-body <a href="*.html"> cross-links + inline onclick handlers (affordances)
  - the .simple-card / .sum-card / :detail_panel structural families (presentational)
  - clone_debt_baseline.json (jscpd) — cross-referenced, not recomputed

TWO INPUTS, ONE CORPUS:
  - STATIC (always): parse the product HTML. Fully reproducible, no browser/DB.
  - LIVE (optional): if .tmp/ia_inventory/<pageId>.json dumps exist (produced by
    __UFAI.inventory() — Layer A, ufai_battery.js v1.3.0), merge their rendered
    values + live CTAs (which a static parse can't see) into the corpus.

OUTPUT (Phase 1 = the redundancy MAP only):
  - ia_inventory_corpus.json   — machine-readable corpus + computed groups (the
                                 bridge Phase 2's rubric reads; no re-parse needed)
  - streamlining_survey.md     — the human-readable redundancy map

DOCTRINE: SURFACES redundancy; a human disposes. This tool NEVER edits a page and
NEVER recommends a collapse (regression-prone + a product-judgment call). Phase 2
layers keep/consolidate/move/remove + canonical-home + UX-law + severity on top of
ia_inventory_corpus.json.

USAGE:  python tools/survey_ia_redundancy.py [--min-pages 2]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── page scope ───────────────────────────────────────────────────────────────
# The "real product surface": a page that is either nav-registered (nav-hub.js)
# or carries ≥1 data-rag-tile. Backups / *-test / observability demos / galleries
# are NOT user-facing dashboards → excluded so the map isn't polluted.
EXCLUDE_RE = re.compile(
    r"(\.backup\d*\.html$|-test\.html$|test-.*\.html$|^index-.*-test|"
    r"observability|symbol-gallery|validator-catalog|architecture|"
    r"founder-console|platform-health|public-feed|llm-observability|"
    r"^predictive\.html$)",   # T4: predictive.html retired Phase 4 (kept on disk so old deep-links don't 404, delisted from nav); its 7 tiles were polluting every survey
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def norm_key(s: str) -> str:
    """Semantic comparison key — mirrors ufai_battery.js _normKey(): lowercase,
    punctuation/parentheticals → spaces, collapse whitespace. So "Pending
    approval" == "pending approval" and "OEE (avg, partial)" → "oee avg partial".
    Cross-page dedup is by MEANING, not by exact markup."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


def strip_tags(s: str) -> str:
    return norm(re.sub(r"<[^>]+>", " ", s or ""))


# ── nav registry (the INTENTIONAL global menu — same on every page by design;
#    its destinations are NOT a redundancy finding, but we use the set to scope
#    which pages are "product" and to tell in-body links apart from the nav). ───
def load_nav_pages() -> set[str]:
    navjs = ROOT / "nav-hub.js"
    if not navjs.exists():
        return set()
    txt = navjs.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r"href:\s*['\"]([a-z0-9-]+\.html)['\"]", txt))


# ── semantic theme buckets (deterministic keyword clusters) — catch redundancy
#    across DIFFERENT labels that mean the same job-to-be-done (e.g. an "overdue"
#    family spanning "Overdue tasks" / "Overdue PMs" / "Past end date"). These are
#    flagged as CANDIDATE clusters (lower confidence than an exact-key match). ──
THEME_BUCKETS = {
    "late / overdue": [r"\boverdue\b", r"past (end )?date", r"past due", r"\blate\b"],
    # require a task/PM/due CONTEXT for the temporal words — bare "this week"
    # also matches gamification stats ("XP this week"), a false cluster member.
    "due soon / upcoming": [r"due (this )?(week|soon|today)", r"\bupcoming\b", r"pms? due", r"tasks? (today|this week)"],
    "risk / hot / critical": [r"\brisk\b", r"\bhot\b", r"\bcritical\b", r"high.?severity", r"\banomaly\b", r"top risk"],
    "healthy / on-track": [r"\bhealthy\b", r"on track", r"on target", r"\bgood\b"],
    "pending approval": [r"pending approval", r"awaiting approval", r"\bapproval\b"],
    "stock / inventory level": [r"out of stock", r"low stock", r"in stock", r"stockout", r"\breorder\b"],
    "detail breakdown panel": [r"detail (breakdown|panel)", r"\bdetail\b"],
}


def theme_of(label_key: str, key_key: str) -> str | None:
    hay = (label_key + " " + (key_key or "")).strip()
    for theme, pats in THEME_BUCKETS.items():
        if any(re.search(p, hay) for p in pats):
            return theme
    return None


# ── per-page static harvest ──────────────────────────────────────────────────
TILE_TAG_RE = re.compile(r"<[^>]*\bdata-rag-tile=\"[^\"]+\"[^>]*>")
TILE_RE = re.compile(r"data-rag-tile=\"([^\"]+)\"")
LABEL_RE = re.compile(r"data-rag-label=\"([^\"]+)\"")
LINK_RE = re.compile(r"<a\b[^>]*\bhref=\"([^\"]*\.html[^\"]*)\"[^>]*>(.*?)</a>", re.I | re.S)
ONCLICK_RE = re.compile(r"onclick=\"\s*([A-Za-z_$][\w$]*)\s*\(")
SIMPLE_CARD_RE = re.compile(r"class=\"[^\"]*\bsimple-card\b")
SUM_CARD_RE = re.compile(r"class=\"[^\"]*\bsum-card\b")


def harvest_page(page: str, html: str) -> dict:
    info_units = []
    for m in TILE_TAG_RE.finditer(html):
        tag = m.group(0)
        tile = TILE_RE.search(tag)
        if not tile:
            continue
        unit_id = tile.group(1)
        lab = LABEL_RE.search(tag)
        label = norm(lab.group(1)) if lab else ""
        key_suffix = unit_id.split(":", 1)[1] if ":" in unit_id else unit_id
        label_key = norm_key(label)
        key_key = norm_key(key_suffix.replace("_", " "))
        info_units.append({
            "kind": "rag-tile", "unitId": unit_id, "keySuffix": key_suffix,
            "label": label, "labelKey": label_key, "keyKey": key_key,
            "fingerprint": label_key or key_key,
            "theme": theme_of(label_key, key_key),
        })

    # page-body cross-links (the nav is JS-injected → static <a href> are
    # page-authored, an EXTRA path to a destination beyond the global nav).
    links = []
    for m in LINK_RE.finditer(html):
        href = m.group(1).split("?")[0].split("#")[0].split("/")[-1]
        if not href.endswith(".html"):
            continue
        links.append({"dest": href, "text": strip_tags(m.group(2))[:40]})

    onclick_fns = sorted(set(ONCLICK_RE.findall(html)))

    return {
        "page": page,
        "infoUnits": info_units,
        "links": links,
        "onclickFns": onclick_fns,
        "structural": {
            "simpleCardBlocks": len(SIMPLE_CARD_RE.findall(html)),
            "sumCardBlocks": len(SUM_CARD_RE.findall(html)),
            "hasDetailPanel": any(u["keySuffix"] == "detail_panel" for u in info_units),
        },
        "source": "static",
    }


# ── optional live enrichment (Layer A dumps) ─────────────────────────────────
def merge_live(corpus: dict) -> int:
    live_dir = ROOT / ".tmp" / "ia_inventory"
    if not live_dir.exists():
        return 0
    merged = 0
    for f in sorted(live_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        page = (data.get("pageId") or f.stem) + ".html"
        page = page.replace(".html.html", ".html")
        entry = corpus.setdefault(page, {"page": page, "infoUnits": [], "links": [],
                                         "onclickFns": [], "structural": {}, "source": "live-only"})
        # add untagged KPIs + rendered values the static parse can't see
        have_keys = {(u.get("unitId"), u.get("labelKey")) for u in entry["infoUnits"]}
        for u in data.get("infoUnits", []):
            u.setdefault("theme", theme_of(u.get("labelKey", ""), u.get("keyKey", "") or ""))
            k = (u.get("unitId"), u.get("labelKey"))
            if u.get("kind") == "kpi-untagged" or k not in have_keys:
                u["_live"] = True
                entry["infoUnits"].append(u)
        entry["liveAffordances"] = data.get("affordances", [])
        merged += 1
    return merged


# ── redundancy computation ───────────────────────────────────────────────────
def compute(corpus: dict, min_pages: int) -> dict:
    # R1a: info-unit redundancy by EXACT label key (high confidence)
    by_label: dict[str, list] = defaultdict(list)
    by_keysuffix: dict[str, list] = defaultdict(list)
    by_theme: dict[str, list] = defaultdict(list)
    for page, e in corpus.items():
        for u in e.get("infoUnits", []):
            if u.get("labelKey"):
                by_label[u["labelKey"]].append({"page": page, "unitId": u.get("unitId"), "label": u.get("label")})
            if u.get("keySuffix"):
                by_keysuffix[norm_key(u["keySuffix"].replace("_", " "))].append({"page": page, "unitId": u.get("unitId"), "label": u.get("label")})
            if u.get("theme"):
                by_theme[u["theme"]].append({"page": page, "unitId": u.get("unitId"), "label": u.get("label")})

    def group_multi(d):
        out = []
        for key, rows in d.items():
            pages = sorted({r["page"] for r in rows})
            if len(pages) >= min_pages:
                out.append({"key": key, "pageCount": len(pages), "pages": pages,
                            "labels": sorted({r["label"] for r in rows if r["label"]}),
                            "units": rows})
        return sorted(out, key=lambda g: (-g["pageCount"], g["key"]))

    label_groups = group_multi(by_label)
    key_groups = group_multi(by_keysuffix)
    theme_groups = group_multi(by_theme)

    # R2: affordance overlap — a destination reached from N pages' BODIES (an
    # extra path beyond the global nav), and an onclick handler shared across pages.
    dest_pages: dict[str, set] = defaultdict(set)
    fn_pages: dict[str, set] = defaultdict(set)
    for page, e in corpus.items():
        for ln in e.get("links", []):
            if ln["dest"] != page:  # ignore self-links / anchors
                dest_pages[ln["dest"]].add(page)
        for fn in e.get("onclickFns", []):
            fn_pages[fn].add(page)
    affordance_dest = sorted(
        [{"dest": d, "pageCount": len(ps), "pages": sorted(ps)} for d, ps in dest_pages.items() if len(ps) >= min_pages],
        key=lambda g: (-g["pageCount"], g["dest"]))
    # shared onclick handlers are mostly shell utilities (toggleX, openModal) →
    # informational only, capped, not a redundancy verdict.
    affordance_fn = sorted(
        [{"fn": f, "pageCount": len(ps), "pages": sorted(ps)} for f, ps in fn_pages.items() if len(ps) >= max(3, min_pages)],
        key=lambda g: (-g["pageCount"], g["fn"]))[:30]

    # R3: presentational clones — jscpd cross-ref + structural card families.
    jscpd = {}
    cb = ROOT / "clone_debt_baseline.json"
    if cb.exists():
        try:
            jscpd = json.loads(cb.read_text(encoding="utf-8"))
        except Exception:
            jscpd = {}
    detail_panel_pages = sorted(p for p, e in corpus.items() if e.get("structural", {}).get("hasDetailPanel"))
    simple_card_pages = sorted(
        ({"page": p, "blocks": e["structural"].get("simpleCardBlocks", 0)}
         for p, e in corpus.items() if e.get("structural", {}).get("simpleCardBlocks", 0) >= 3),
        key=lambda x: -x["blocks"])
    sum_card_pages = sorted(p for p, e in corpus.items() if e.get("structural", {}).get("sumCardBlocks", 0) >= 1)

    return {
        "info_redundancy_by_label": label_groups,
        "info_redundancy_by_key": key_groups,
        "info_theme_clusters": theme_groups,
        "affordance_overlap_destinations": affordance_dest,
        "affordance_shared_handlers": affordance_fn,
        "presentational": {
            "jscpd": {"clones": jscpd.get("clones"), "duplicatedLines": jscpd.get("duplicatedLines"),
                      "percentage": jscpd.get("percentage")},
            "detail_panel_family": {"pageCount": len(detail_panel_pages), "pages": detail_panel_pages},
            "simple_card_family": simple_card_pages,
            "sum_card_family": {"pageCount": len(sum_card_pages), "pages": sum_card_pages},
        },
    }


# ── markdown report ──────────────────────────────────────────────────────────
def render_md(corpus: dict, groups: dict, min_pages: int, live_merged: int) -> str:
    n_pages = len(corpus)
    n_units = sum(len(e.get("infoUnits", [])) for e in corpus.values())
    L = []
    L.append("# Streamlining Survey — Cross-Page IA Redundancy Map (Phase 1)\n")
    L.append("> **Deterministic. SURFACES redundancy — disposes nothing.** This is the grounded")
    L.append("> _map_ (Brad Frost Interface Inventory + NN/g Content Inventory). The")
    L.append("> keep/consolidate/move/remove recommendation, the canonical home, the UX-law")
    L.append("> citation and the severity are **Phase 2's rubric** — not in this map.\n")
    L.append(f"- Pages surveyed: **{n_pages}**  ·  info-units catalogued: **{n_units}**  ·  "
             f"min-pages threshold: **{min_pages}**")
    L.append(f"- Live-inventory dumps merged: **{live_merged}** "
             f"(`.tmp/ia_inventory/*.json` from `__UFAI.inventory()`; 0 = static-only run)")
    L.append("- Complements `clone_debt_baseline.json` (jscpd = textual code clones). This map ="
             " user-facing **semantic** redundancy.\n")

    # ── 1. Information redundancy (exact key) ──
    L.append("## 1. Information redundancy — the SAME info-unit on N pages\n")
    L.append("### 1a. Exact-label matches (high confidence)\n")
    lg = groups["info_redundancy_by_label"]
    if lg:
        L.append("| Info-unit (label) | Pages | Where |")
        L.append("|---|---|---|")
        for g in lg:
            disp = (g["labels"] or [g["key"]])[0]
            L.append(f"| {disp} | {g['pageCount']} | {', '.join(p.replace('.html','') for p in g['pages'])} |")
    else:
        L.append("_None at this threshold._")
    L.append("")
    L.append("### 1b. Same tile-key suffix across pages (high confidence)\n")
    L.append("_The `page:KEY` convention — an identical KEY suffix = the same unit replicated._\n")
    kg = groups["info_redundancy_by_key"]
    if kg:
        L.append("| Tile key | Pages | Where |")
        L.append("|---|---|---|")
        for g in kg:
            L.append(f"| `{g['key'].replace(' ', '_')}` | {g['pageCount']} | "
                     f"{', '.join(p.replace('.html','') for p in g['pages'])} |")
    else:
        L.append("_None at this threshold._")
    L.append("")
    L.append("### 1c. Semantic theme clusters (CANDIDATES — different labels, same job)\n")
    L.append("_Lower confidence: keyword-bucketed families. A human confirms each is true"
             " redundancy vs. legitimately distinct (e.g. PM-overdue ≠ project-overdue)._\n")
    tg = groups["info_theme_clusters"]
    if tg:
        L.append("| Theme | Pages | Member units (label · page) |")
        L.append("|---|---|---|")
        for g in tg:
            members = "; ".join(f"{u['label']} ({u['page'].replace('.html','')})"
                                for u in g["units"] if u["label"])[:300]
            L.append(f"| {g['key']} | {g['pageCount']} | {members} |")
    else:
        L.append("_None at this threshold._")
    L.append("")

    # ── 2. Affordance overlap ──
    L.append("## 2. Affordance overlap — the same action reachable from N places (Hick's law)\n")
    L.append("_Page-BODY cross-links only; the global nav-hub is excluded (it links everywhere"
             " by design). A body link to a page that ALSO sits in the nav = an extra path._\n")
    ad = groups["affordance_overlap_destinations"]
    if ad:
        L.append("| Destination | Linked from (bodies) | Where |")
        L.append("|---|---|---|")
        for g in ad:
            L.append(f"| {g['dest'].replace('.html','')} | {g['pageCount']} | "
                     f"{', '.join(p.replace('.html','') for p in g['pages'])} |")
    else:
        L.append("_No in-body destination is linked from ≥%d pages._" % min_pages)
    L.append("")
    af = groups["affordance_shared_handlers"]
    if af:
        L.append("<details><summary>Shared inline onclick handlers (informational — mostly shell"
                 " utilities like toggles/modals; not a redundancy verdict)</summary>\n")
        L.append("| Handler | Pages |")
        L.append("|---|---|")
        for g in af:
            L.append(f"| `{g['fn']}()` | {g['pageCount']} |")
        L.append("\n</details>")
    L.append("")

    # ── 3. Presentational clones ──
    L.append("## 3. Presentational clones — same block, copy-pasted\n")
    p = groups["presentational"]
    j = p["jscpd"]
    L.append(f"- **jscpd (textual):** {j.get('clones')} clones · {j.get('duplicatedLines')} "
             f"duplicated lines · {j.get('percentage')}% (see `clone_debt_baseline.json`). "
             "Tracked separately; this map adds the SEMANTIC layer below.")
    dp = p["detail_panel_family"]
    L.append(f"- **`:detail_panel` family:** the same \"detail breakdown\" panel structure on "
             f"**{dp['pageCount']}** pages — {', '.join(x.replace('.html','') for x in dp['pages'])}.")
    sf = p["sum_card_family"]
    if sf["pageCount"]:
        L.append(f"- **`.sum-card` 4-tile summary block:** on **{sf['pageCount']}** pages — "
                 f"{', '.join(x.replace('.html','') for x in sf['pages'])}.")
    sc = p["simple_card_family"]
    if sc:
        L.append("- **`.simple-card` KPI block density (≥3 per page):** "
                 + ", ".join(f"{x['page'].replace('.html','')}={x['blocks']}" for x in sc) + ".")
    L.append("")

    L.append("---")
    L.append("### Next: Phase 2 (rubric)")
    L.append("Read `ia_inventory_corpus.json` (no re-parse) and, per redundant unit, score"
             " **keep / consolidate / move / remove** + the ONE canonical home (single source"
             " of truth, deep-link elsewhere) + the UX-law citation (Hick / Tesler / Jakob /"
             " Miller / progressive-disclosure) + severity → `streamlining_plan.md` + critic"
             " candidates into `sweep_critiques.json`. **No UI is collapsed without your sign-off.**")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 1 cross-page IA redundancy surveyor.")
    ap.add_argument("--min-pages", type=int, default=2,
                    help="report a unit/affordance only if it appears on ≥N pages (default 2)")
    args = ap.parse_args()

    nav_pages = load_nav_pages()
    corpus: dict[str, dict] = {}
    for p in sorted(ROOT.glob("*.html")):
        name = p.name
        if EXCLUDE_RE.search(name):
            continue
        html = p.read_text(encoding="utf-8", errors="ignore")
        has_tile = TILE_RE.search(html) is not None
        if not (has_tile or name in nav_pages):
            continue
        corpus[name] = harvest_page(name, html)

    live_merged = merge_live(corpus)
    groups = compute(corpus, args.min_pages)

    out_json = ROOT / "ia_inventory_corpus.json"
    out_json.write_text(json.dumps({
        "_doc": "Phase 1 cross-page IA redundancy corpus. SURFACE-only; Phase 2 rubric reads this.",
        "minPages": args.min_pages, "liveMerged": live_merged,
        "pagesSurveyed": sorted(corpus.keys()),
        "corpus": corpus, "groups": groups,
    }, indent=2), encoding="utf-8")

    out_md = ROOT / "streamlining_survey.md"
    out_md.write_text(render_md(corpus, groups, args.min_pages, live_merged), encoding="utf-8")

    # stdout summary
    n_label = len(groups["info_redundancy_by_label"])
    n_key = len(groups["info_redundancy_by_key"])
    n_theme = len(groups["info_theme_clusters"])
    n_aff = len(groups["affordance_overlap_destinations"])
    print(f"IA redundancy survey -- {len(corpus)} pages, "
          f"{sum(len(e['infoUnits']) for e in corpus.values())} info-units"
          + (f" (+{live_merged} live dumps merged)" if live_merged else " (static-only)"))
    print(f"  R1 info redundancy : {n_label} exact-label / {n_key} same-key / {n_theme} theme clusters")
    print(f"  R2 affordance      : {n_aff} destinations reached from >={args.min_pages} bodies")
    print(f"  R3 presentational  : detail_panel x{groups['presentational']['detail_panel_family']['pageCount']} pages, "
          f"jscpd {groups['presentational']['jscpd'].get('clones')} clones")
    print(f"  -> {out_md.name} + {out_json.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
