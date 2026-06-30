"""
content_substrate.py — Content Grounding Gate, Layer G-1.5 (Substrate) + G-1 (Discover).
========================================================================================

Mirrors the Mega Gate's substrate (9 miners → one manifest) and the Companion
Dev Tool's auto-discovery, pointed OUTWARD at the four content surfaces:

  1. Landing  — index.html (claims, counts, JSON-LD, feature cards)
  2. Learn    — the 36 learn/<slug>/index.html articles
  3. SEO/GEO  — sitemap.xml, llms.txt, robots.txt, JSON-LD featureList
  4. Video    — .tmp/video_ideas_backlog.json (each idea's solution_feature)

Two outputs, both built on the Platform Catalog keystone (platform_catalog.py):

  build_manifest() → content_substrate_manifest.json (+ .md)
      One aggregated view: catalog counts + per-surface scan + discover metrics.
      Informational (exit 0), like build_substrate_manifest.py.

  discover() → content_discover_report.json
      The coverage / orphan / gap map:
        • coverage — for every catalog feature, where it is (or isn't) surfaced
        • orphans  — content claims that DON'T resolve to a catalog feature
                     (feature drift: a renamed/removed/invented feature in copy)
        • gaps     — active features with no content (an SEO opportunity + the
                     coverage metric that feeds the 4-axis scorecard)

CLI:
    python tools/content_substrate.py            # build manifest + discover, write both
    python tools/content_substrate.py --discover # print the discover map
    python tools/content_substrate.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import platform_catalog as pc  # noqa: E402

MANIFEST_JSON = ROOT / "content_substrate_manifest.json"
MANIFEST_MD = ROOT / "content_substrate_manifest.md"
DISCOVER_JSON = ROOT / "content_discover_report.json"
VIDEO_BACKLOG = ROOT / ".tmp" / "video_ideas_backlog.json"

# Real, intentional auxiliary pages that are deliberately NOT standalone catalog
# features — the platform's own nav declares them so. A landing link to one of these
# is legitimate (it has backing), NOT "feature drift" (invented/renamed feature).
# Keep in sync with nav-hub.js: report-sender is folded under "Reports"; public-feed
# is the public-only page; marketplace-seller is the seller side of Marketplace.
LANDING_AUX_PAGES = {"report-sender.html", "public-feed.html", "marketplace-seller.html"}


# ── Surface scanners ──────────────────────────────────────────────────────────

def _landing_linked_pages() -> list[str]:
    """Real .html pages the landing page links to (feature cards + nav)."""
    content = pc._read(pc.INDEX_HTML)
    hrefs = re.findall(r'href="/?([a-z0-9-]+\.html)"', content)
    return sorted(set(hrefs))


def _learn_hub_linked_slugs() -> set[str]:
    """Article slugs the learn hub (learn/index.html) actually links to."""
    content = pc._read(pc.LEARN_DIR / "index.html")
    return {m for m in re.findall(r'href="/?learn/([a-z0-9-]+)/?"', content) if m and m != "index"}


def scan_surfaces(cat: dict) -> dict:
    idx = cat["public_surface"]["index"]
    sm = cat["public_surface"]["sitemap"]
    llms = cat["public_surface"]["llms_txt"]
    arts = cat["articles"]

    landing_linked = _landing_linked_pages()
    dated = [a for a in arts if a["date_modified"]]

    video = {"present": False, "ideas": 0}
    if VIDEO_BACKLOG.exists():
        try:
            data = json.loads(VIDEO_BACKLOG.read_text(encoding="utf-8"))
            ideas = data.get("ideas", data) if isinstance(data, dict) else data
            video = {"present": True, "ideas": len(ideas),
                     "solution_features": sorted({i.get("solution_feature", "") for i in ideas if i.get("solution_feature")})}
        except Exception as e:
            video = {"present": True, "error": str(e)[:120]}

    return {
        "landing": {
            "present":          idx.get("present", False),
            "linked_pages":     landing_linked,
            "linked_count":     len(landing_linked),
            "count_claims":     idx.get("count_claims", {}),
            "jsonld_types":     idx.get("jsonld_types", []),
            "faq_count":        idx.get("faq_count", 0),
            "has_feature_list": idx.get("has_feature_list", False),
        },
        "learn": {
            "present":      True,
            "article_count": len(arts),
            "dated":        len(dated),
            "undated":      len(arts) - len(dated),
        },
        "seo_geo": {
            "sitemap_urls":          sm["count"],
            "sitemap_learn_urls":    sm["learn_count"],
            "llms_present":          llms["present"],
            "llms_feature_bullets":  len(llms["feature_bullets"]),
            "robots_present":        cat["public_surface"]["robots_txt"]["present"],
            "jsonld_feature_list":   idx.get("has_feature_list", False),
        },
        "video": video,
    }


# ── Discover: coverage / orphans / gaps ───────────────────────────────────────

def discover(cat: dict | None = None) -> dict:
    cat = cat or pc.build_catalog()
    features = cat["features"]
    by_id = {f["id"]: f for f in features}
    llms = cat["public_surface"]["llms_txt"]
    idx = cat["public_surface"]["index"]
    arts = cat["articles"]

    landing_linked = set(_landing_linked_pages())
    llms_text = pc._read(pc.LLMS_TXT)
    llms_map_targets = {m.get("feature_id") for m in llms["maps"].values() if m.get("feature_id")}
    # Feature bullets in llms.txt resolved to feature ids (paraphrase-tolerant).
    llms_bullet_targets = {pc._resolve_label_to_feature(b, features) for b in llms["feature_bullets"]}
    llms_bullet_targets.discard(None)
    llms_named = llms_map_targets | llms_bullet_targets

    # Per-feature coverage across surfaces.
    by_feature = []
    for f in features:
        # "named in llms" = an article Maps to it, OR a feature bullet resolves to
        # it, OR its label/name appears verbatim — robust to paraphrase.
        named_in_llms = (
            f["id"] in llms_named
            or bool(f.get("nav_label") and f["nav_label"] in llms_text)
            or (f["name"] in llms_text)
        )
        row = {
            "id":               f["id"],
            "name":             f["name"],
            "route":            f["route"],
            "status":           f["status"],
            "has_article":      bool(f["articles"]),
            "article_slugs":    f["articles"],
            "on_landing":       (f["route"] in landing_linked) if f["route"] else False,
            "in_llms_maps":     f["id"] in llms_map_targets,
            "named_in_llms":    named_in_llms,
            "in_jsonld_features": f["name"] in idx.get("feature_list", []),
        }
        by_feature.append(row)

    active_routed = [r for r in by_feature if r["status"] == "active" and r["route"]]
    with_article = [r for r in active_routed if r["has_article"]]

    # ORPHANS — claims in content that don't resolve to a catalog feature.
    orphans = []
    # (a) llms.txt feature bullets that don't resolve.
    for bullet in llms["feature_bullets"]:
        if pc._resolve_label_to_feature(bullet, features) is None:
            orphans.append({"source": "llms.txt", "claim": bullet,
                            "reason": f"llms.txt feature bullet '{bullet}' resolves to no catalog feature"})
    # (b) llms.txt 'Maps to WorkHive X' labels that don't resolve.
    for slug, m in llms["maps"].items():
        if not m.get("feature_id"):
            orphans.append({"source": f"llms.txt:{slug}", "claim": m.get("label"),
                            "reason": f"article '{slug}' Maps to '{m.get('label')}' which resolves to no catalog feature"})
    # (c) JSON-LD featureList entries that don't resolve.
    for fl in idx.get("feature_list", []):
        if pc._resolve_label_to_feature(fl, features) is None:
            orphans.append({"source": "index.html#featureList", "claim": fl,
                            "reason": f"JSON-LD featureList '{fl}' resolves to no catalog feature"})
    # (d) landing page links to a page that isn't a catalog route.
    #     EXEMPT real, intentional auxiliary pages that are deliberately NOT standalone
    #     catalog features (the platform's own nav declares them so): a sub-page of a
    #     feature, a folded page, or a public-only page. Linking to a REAL intentional
    #     page is not "feature drift" (the check's intent = invented/renamed feature).
    #     Each must exist on disk (link_drift separately verifies non-retired existence).
    #       report-sender.html      — nav-hub folds it under "Reports" (match: report-sender)
    #       public-feed.html        — nav-hub: "public read-only page, linked from index, not app nav"
    #       marketplace-seller.html — the seller side of the Marketplace feature
    catalog_routes = {f["route"] for f in features if f["route"]}
    catalog_routes |= LANDING_AUX_PAGES
    for href in sorted(landing_linked):
        if href not in catalog_routes:
            orphans.append({"source": "index.html#link", "claim": href,
                            "reason": f"landing page links '{href}' which is not a catalog feature route"})
    # (e) video idea whose solution_feature isn't a catalog feature.
    surfaces = scan_surfaces(cat)
    for sf in surfaces["video"].get("solution_features", []):
        if pc._resolve_label_to_feature(sf, features) is None:
            orphans.append({"source": "video_ideas_backlog", "claim": sf,
                            "reason": f"video idea solution_feature '{sf}' resolves to no catalog feature"})

    # GAPS — MARKETED (intel-backed ecosystem) features that are under-covered.
    # Scoped to the ecosystem the platform actively markets, so internal report
    # utilities (Report Sender, Project Report, Analytics Report) don't cry wolf.
    intel_backed = {f["id"] for f in features if "intel" in f["sources"]}
    gaps = []
    for r in active_routed:
        if r["id"] not in intel_backed:
            continue
        if not r["has_article"]:
            gaps.append({"feature_id": r["id"], "kind": "no_article",
                         "reason": f"marketed feature '{r['name']}' ({r['route']}) has no /learn article — SEO/AEO content gap"})
        if not r["named_in_llms"]:
            gaps.append({"feature_id": r["id"], "kind": "absent_from_llms",
                         "reason": f"marketed feature '{r['name']}' is not named in llms.txt — GEO coverage gap"})

    # Informational: real nav tools the marketed ecosystem + SEO surfaces ignore
    # entirely (a tool exists but is invisible to search/AI discovery).
    nav_only_uncovered = [
        {"feature_id": r["id"], "name": r["name"], "route": r["route"],
         "reason": f"nav tool '{r['name']}' ({r['route']}) has no intel ecosystem entry, no article, and is not in llms.txt"}
        for r in active_routed
        if r["id"] not in intel_backed and r["route"] != "index.html"
        and not r["has_article"] and not r["named_in_llms"]
    ]

    cov_pct = round(100 * len(with_article) / len(active_routed), 1) if active_routed else 0.0

    # Learn-hub completeness: articles on disk not linked from the learn hub.
    hub_linked = _learn_hub_linked_slugs()
    learn_hub_unlisted = sorted(a["slug"] for a in arts if a["slug"] not in hub_linked)

    return {
        "generated_at":   datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalog_features": len(features),
        "coverage": {
            "by_feature": by_feature,
            "summary": {
                "active_routed":      len(active_routed),
                "with_article":       len(with_article),
                "article_coverage_pct": cov_pct,
                "on_landing":         sum(1 for r in active_routed if r["on_landing"]),
                "named_in_llms":      sum(1 for r in active_routed if r["named_in_llms"]),
            },
        },
        "orphans": orphans,
        "gaps":    gaps,
        "nav_only_uncovered": nav_only_uncovered,
        "learn_hub_unlisted": learn_hub_unlisted,
        "metrics": {
            "article_coverage_pct": cov_pct,
            "orphan_count":         len(orphans),
            "gap_count":            len(gaps),
            "nav_only_uncovered":   len(nav_only_uncovered),
            "learn_hub_unlisted":   len(learn_hub_unlisted),
        },
    }


# ── Manifest ──────────────────────────────────────────────────────────────────

def build_manifest() -> dict:
    cat = pc.build_catalog()
    surfaces = scan_surfaces(cat)
    disc = discover(cat)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator":    "content_substrate.py",
        "catalog_counts": cat["counts"],
        "surfaces":     surfaces,
        "discover":     disc["metrics"],
        "coverage_summary": disc["coverage"]["summary"],
        "alias_issues": cat["alias_issues"],
    }
    return manifest, disc  # type: ignore[return-value]


def write_all() -> tuple[dict, dict]:
    manifest, disc = build_manifest()
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    DISCOVER_JSON.write_text(json.dumps(disc, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_manifest_md(manifest, disc)
    return manifest, disc


def _write_manifest_md(manifest: dict, disc: dict) -> None:
    c = manifest["catalog_counts"]
    s = manifest["surfaces"]
    cov = manifest["coverage_summary"]
    lines = [
        f"# Content Substrate Manifest — {manifest['generated_at']}",
        "",
        "Aggregates the Platform Catalog + a scan of all four outward surfaces.",
        "",
        f"- Features: {c['features_total']} ({c['features_routed']} routed) · Articles: {c['learn_articles']}",
        f"- Article coverage of active routed features: **{cov['article_coverage_pct']}%** "
        f"({cov['with_article']}/{cov['active_routed']})",
        f"- Orphans (claims with no catalog backing): **{manifest['discover']['orphan_count']}**",
        f"- Gaps (under-covered features): **{manifest['discover']['gap_count']}**",
        "",
        "## Surfaces",
        "",
        "| Surface | Signal |",
        "|---|---|",
        f"| Landing | {s['landing']['linked_count']} feature links · "
        f"{s['landing']['faq_count']} FAQs · claims {s['landing']['count_claims']} |",
        f"| Learn | {s['learn']['article_count']} articles ({s['learn']['undated']} undated) |",
        f"| SEO/GEO | {s['seo_geo']['sitemap_urls']} sitemap urls · "
        f"llms.txt {'present' if s['seo_geo']['llms_present'] else 'MISSING'} · "
        f"featureList {'present' if s['seo_geo']['jsonld_feature_list'] else 'absent'} |",
        f"| Video | {s['video'].get('ideas', 0)} ideas |",
        "",
        "## How to use",
        "",
        "Run once per session. Orphans are drift candidates (content names a "
        "feature the platform no longer has); gaps are SEO opportunities (a real "
        "feature with no article). The drift validators (G0) turn orphans into "
        "gate failures; the loop (G3) turns gaps into regeneration candidates.",
        "",
        "Generated by `tools/content_substrate.py`.",
    ]
    MANIFEST_MD.write_text("\n".join(lines), encoding="utf-8")


# ── Self-test ─────────────────────────────────────────────────────────────────

def self_test() -> int:
    def ok(label):  print(f"  \033[92mPASS\033[0m  {label}")
    def bad(label): print(f"  \033[91mFAIL\033[0m  {label}")
    print("\n\033[1mcontent_substrate.py --self-test\033[0m")
    print("=" * 55)
    fails = 0

    def check(cond, label):
        nonlocal fails
        (ok if cond else bad)(label)
        if not cond:
            fails += 1

    cat = pc.build_catalog()
    surfaces = scan_surfaces(cat)
    disc = discover(cat)

    check(surfaces["landing"]["present"], "landing surface scanned")
    check(surfaces["learn"]["article_count"] >= 30,
          f"learn surface scanned ({surfaces['learn']['article_count']} articles)")
    check(surfaces["seo_geo"]["llms_present"], "seo/geo surface scanned (llms.txt present)")
    check(surfaces["video"]["present"], "video surface scanned (ideas backlog present)")

    cov = disc["coverage"]["summary"]
    check(cov["active_routed"] >= 15, f"coverage computed over active routed features ({cov['active_routed']})")
    check(0 <= cov["article_coverage_pct"] <= 100, "article coverage pct in [0,100]")
    check(isinstance(disc["orphans"], list), "orphans list produced")
    check(isinstance(disc["gaps"], list), "gaps list produced")

    # Discriminating self-test: a known-good claim must NOT be an orphan, and a
    # synthetic bogus claim MUST resolve to None (proving orphan detection bites).
    feats = cat["features"]
    check(pc._resolve_label_to_feature("Maintenance Logbook", feats) is not None,
          "real feature 'Maintenance Logbook' resolves (not a false orphan)")
    check(pc._resolve_label_to_feature("Quantum Flux Capacitor 9000", feats) is None,
          "bogus feature 'Quantum Flux Capacitor 9000' resolves to None (orphan detection has teeth)")

    # Count-claim SENSING is verified synthetically (the original live-drift
    # assertion broke the moment the "24 guides" drift was fixed 2026-06-10):
    # a stale claim injected into the parse must surface in the scan.
    _saved_idx = pc.parse_index_public
    def _fake_index():
        d = dict(_saved_idx()); d["count_claims"] = {"guide": [24]}
        return d
    pc.parse_index_public = _fake_index
    try:
        synth_cat = pc.build_catalog()
        synth_surf = scan_surfaces(synth_cat)
        gc = synth_surf["landing"]["count_claims"].get("guide")
        check(bool(gc) and synth_surf["learn"]["article_count"] != gc[0],
              f"count-claim sensing (synthetic stale claim {gc} vs live {synth_surf['learn']['article_count']})")
    finally:
        pc.parse_index_public = _saved_idx

    print("=" * 55)
    if fails == 0:
        print("\033[92m  self-test PASS\033[0m\n")
    else:
        print(f"\033[91m  self-test FAIL — {fails} check(s) failed\033[0m\n")
    return 1 if fails else 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_discover(disc: dict) -> None:
    cov = disc["coverage"]["summary"]
    print(f"\nContent Discover  ·  {disc['generated_at']}")
    print("=" * 64)
    print(f"  article coverage: {cov['article_coverage_pct']}% "
          f"({cov['with_article']}/{cov['active_routed']} active routed features)")
    print(f"  on landing: {cov['on_landing']}   named in llms.txt: {cov['named_in_llms']}")
    print(f"  orphans: {disc['metrics']['orphan_count']}   gaps: {disc['metrics']['gap_count']}")
    if disc["orphans"]:
        print("\n  \033[93mORPHANS (claims with no catalog backing):\033[0m")
        for o in disc["orphans"][:20]:
            print(f"    - [{o['source']}] {o['reason']}")
    if disc["gaps"]:
        print(f"\n  \033[93mGAPS ({len(disc['gaps'])}) — marketed features under-covered:\033[0m")
        for g in disc["gaps"][:12]:
            print(f"    - [{g['kind']}] {g['reason']}")
    if disc.get("nav_only_uncovered"):
        print(f"\n  \033[90mnav-only uncovered ({len(disc['nav_only_uncovered'])}) — tools invisible to SEO/GEO:\033[0m")
        for n in disc["nav_only_uncovered"]:
            print(f"    - {n['name']} ({n['route']})")
    if disc.get("learn_hub_unlisted"):
        u = disc["learn_hub_unlisted"]
        print(f"\n  \033[91mlearn-hub UNLISTED ({len(u)}) — articles on disk NOT linked from the learn hub:\033[0m")
        for s in u:
            print(f"    - {s}")
    print()


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if "--discover" in argv:
        _print_discover(discover())
        return 0
    manifest, disc = write_all()
    c = manifest["catalog_counts"]
    print(f"\nContent substrate: {c['features_total']} features / {c['learn_articles']} articles scanned.")
    print(f"  coverage {manifest['coverage_summary']['article_coverage_pct']}% · "
          f"orphans {manifest['discover']['orphan_count']} · gaps {manifest['discover']['gap_count']}")
    print(f"  → {MANIFEST_JSON.name} + {MANIFEST_MD.name} + {DISCOVER_JSON.name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
