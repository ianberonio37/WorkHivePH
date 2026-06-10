"""
platform_catalog.py — the KEYSTONE of the Content Grounding Gate.
================================================================

One auto-derived `platform_catalog.json` that every outward-facing surface
(landing page, /learn articles, SEO/AEO/GEO artifacts, video marketing) reads
INSTEAD of carrying its own baked-in snapshot of the platform. The catalog is
generated from the platform's OWN live artifacts, so it cannot drift from
reality:

  features[]       ← nav-hub.js TOOLS (real routes) ENRICHED by
                     platform_intel.FEATURE_ECOSYSTEM (loop_role, connects_to,
                     tables, edge_fns, audience) joined via a live-checked alias
  articles[]       ← the 36 learn/<slug>/index.html (title, dateModified,
                     maps_to feature, features_referenced)
  public_surface   ← index.html (JSON-LD @types, featureList, FAQ count,
                     count claims), sitemap.xml, llms.txt, robots.txt
  counts           ← derived live numbers content asserts (#tools/#articles/#FAQs)

GROUNDING GUARANTEE (why this is not "a hand-kept list"):
  • The feature LIST is derived live every run — add a page to nav-hub.js or an
    article to /learn and it flows into the catalog automatically.
  • The 21-entry INTEL_TO_ROUTE alias only JOINS two live sources; every run
    asserts each aliased href still exists in nav and each intel name still
    exists in FEATURE_ECOSYSTEM. A dangling alias is reported as drift, so the
    alias is a SENSOR, not a static catalog.

Public API:
    build_catalog() -> dict
    write_catalog(path=ROOT/"platform_catalog.json") -> Path
    self_test() -> int          # 0 = ok, 1 = fail

CLI:
    python tools/platform_catalog.py            # build + write platform_catalog.json
    python tools/platform_catalog.py --print    # build + print a human summary
    python tools/platform_catalog.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
import html
from pathlib import Path
from datetime import datetime, timezone

# ── Paths + UTF-8 console ─────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import platform_intel  # noqa: E402  (lives beside this file in tools/)

FEATURE_ECOSYSTEM = platform_intel.FEATURE_ECOSYSTEM

CATALOG_PATH = ROOT / "platform_catalog.json"
NAV_HUB_JS = ROOT / "nav-hub.js"
INDEX_HTML = ROOT / "index.html"
SITEMAP_XML = ROOT / "sitemap.xml"
LLMS_TXT = ROOT / "llms.txt"
ROBOTS_TXT = ROOT / "robots.txt"
LEARN_DIR = ROOT / "learn"

CATALOG_VERSION = 1

# Pages that were retired — referencing them anywhere is feature drift.
RETIRED_PAGES = {"parts-tracker.html", "checklist.html"}

# ── The live-checked join alias (intel marketed name → real nav route) ────────
# The ONLY hand-declared mapping in the file. It does not enumerate features
# (nav + intel do that live); it only resolves the join for the 21 marketed
# features whose names differ from their page label, and disambiguates the
# analytics/predictive cluster that token matching cannot separate. Every run
# asserts each href below is still a live nav tool and each key is still a live
# FEATURE_ECOSYSTEM entry — a dangling entry is reported, never silently kept.
INTEL_TO_ROUTE = {
    "Maintenance Logbook":          "logbook.html",
    "PM Checklist":                 "pm-scheduler.html",
    "Inventory Management":         "inventory.html",
    "AI Maintenance Assistant":     "assistant.html",
    "Hive Dashboard":               "hive.html",
    "Shift Handover Report":        None,   # generated inside Logbook/Shift Brain — no standalone page
    "Day Planner":                  "dayplanner.html",
    "Engineering Design Calculator":"engineering-design.html",
    "Skill Matrix":                 "skillmatrix.html",
    "Marketplace":                  "marketplace.html",
    "Community Forum":              "community.html",
    "Analytics & OEE Dashboard":    "analytics.html",
    "Predictive Analytics":         "predictive.html",
    "Asset Brain":                  "asset-hub.html",
    "Shift Brain":                  "shift-brain.html",
    "Achievements":                 "achievements.html",
    "Alert Hub":                    "alert-hub.html",
    "PH Industry Intelligence":     "ph-intelligence.html",
    "CMMS Integrations":            "integrations.html",
    "Project Manager":              "project-manager.html",
    "Audit Log & Compliance":       "audit-log.html",
    "Resume Builder":               "resume.html",
}

_STOPWORDS = {"the", "and", "a", "of", "for", "workhive", "tool", "to", "your", "&"}

# ── Video-journey join (the catalog OWNS the storyboard/recorder route truth) ──
# The marketing video pipeline (storyboard.py + ui_recorder.py) used to hard-code
# JOURNEY_URLS = {key: "/workhive/<page>.html"} — a snapshot that silently breaks
# the screen recording when a page is renamed (the drift bug the plan calls out).
# These narration-detection semantic keys differ from route stems (e.g.
# "ai_assistant"->"assistant", "pm_checklist"->"pm-scheduler",
# "shift_handover"->"shift-brain"), so the join is curated here but LIVE-checked:
# build_journey_index() resolves each to the catalog feature's CURRENT route, and
# self_test fails on any dangling entry. One source, never a stale copy.
JOURNEY_KEY_TO_FEATURE = {
    "logbook":          "logbook",
    "shift_handover":   "logbook",      # handover report is generated from the logbook (no standalone page)
    "ai_assistant":     "assistant",
    "pm_checklist":     "pm-scheduler",
    "inventory":        "inventory",
    "predictive":       "predictive",
    "analytics":        "analytics",
    "skill_matrix":     "skillmatrix",
    "marketplace":      "marketplace",
    "community":        "community",
    "day_planner":      "dayplanner",
    "asset_brain":      "asset-hub",
    "shift_brain":      "shift-brain",
    "achievements":     "achievements",
    "alert_hub":        "alert-hub",
    "ph_intelligence":  "ph-intelligence",
    "integrations":     "integrations",
    "project_manager":  "project-manager",
    "audit_log":        "audit-log",
    "hive_dashboard":   "hive",
    "engineering_calc": "engineering-design",
    "resume_builder":   "resume",
}


# ── Small text helpers ────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _norm_tokens(s: str) -> set:
    s = (s or "").lower().replace("&", " and ")
    toks = re.split(r"[^a-z0-9]+", s)
    return {t for t in toks if t and t not in _STOPWORDS}


def _href_stem(href: str) -> str:
    return re.sub(r"\.html$", "", (href or "").strip().lstrip("/"))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


# ── nav-hub.js TOOLS parsing (the real routes) ────────────────────────────────

def parse_nav_tools(nav_content: str | None = None) -> list[dict]:
    """Parse the TOOLS array from nav-hub.js into structured tool dicts.

    Captures everything the catalog needs about a real route: label, href,
    match[], section, hidden, roles[], accent, has_icon.
    """
    nav_content = nav_content if nav_content is not None else _read(NAV_HUB_JS)
    tools: list[dict] = []
    m = re.search(r"const TOOLS\s*=\s*\[([\s\S]+?)\];", nav_content)
    if not m:
        return tools
    block = m.group(1)
    for obj_m in re.finditer(r"\{([^{}]+)\}", block, re.DOTALL):
        obj = obj_m.group(1)
        label_m = re.search(r"label:\s*['\"]([^'\"]+)['\"]", obj)
        href_m = re.search(r"href:\s*['\"]([^'\"]+)['\"]", obj)
        if not (label_m and href_m):
            continue
        match_m = re.search(r"match:\s*\[([^\]]+)\]", obj)
        section_m = re.search(r"section:\s*['\"]([^'\"]+)['\"]", obj)
        roles_m = re.search(r"roles:\s*\[([^\]]+)\]", obj)
        tools.append({
            "label":    label_m.group(1),
            "href":     href_m.group(1),
            "match":    re.findall(r"['\"]([^'\"]+)['\"]", match_m.group(1)) if match_m else [],
            "section":  section_m.group(1) if section_m else None,
            "hidden":   bool(re.search(r"hidden:\s*true", obj)),
            "accent":   bool(re.search(r"accent:\s*true", obj)),
            "roles":    re.findall(r"['\"]([^'\"]+)['\"]", roles_m.group(1)) if roles_m else [],
            "has_icon": bool(re.search(r"\bicon\s*:", obj)),
        })
    return tools


# ── Feature assembly (nav-anchored, intel-enriched) ───────────────────────────

def _feature_token_set(f: dict) -> set:
    cand = _norm_tokens(f["name"]) | _norm_tokens(f.get("nav_label") or "") | {_href_stem(f["route"] or "")}
    return {c for c in cand if c}


def _resolve_label_to_feature(label: str, features: list[dict]) -> str | None:
    """Resolve a free-text feature label (e.g. an llms.txt 'Maps to WorkHive X')
    to a catalog feature id by best IDF-weighted token overlap.

    Plain token-count overlap mis-resolves labels that share a domain-ubiquitous
    word — e.g. 'Predictive Maintenance' shares 'maintenance' with both
    'Maintenance Logbook' and 'Predictive Analytics'. Weighting each shared token
    by inverse document frequency across the feature corpus makes the DISTINCTIVE
    token ('predictive', df=1) outweigh the common one ('maintenance', df≥2), so
    the resolve lands on the right feature.
    """
    import math
    want = _norm_tokens(label)
    if not want:
        return None
    cand_sets = [(f["id"], _feature_token_set(f)) for f in features]
    df: dict[str, int] = {}
    for _, cand in cand_sets:
        for t in cand:
            df[t] = df.get(t, 0) + 1
    n = len(features) or 1

    def weight(t: str) -> float:
        return math.log(1 + n / (1 + df.get(t, 0)))

    best, best_score = None, 0.0
    for fid, cand in cand_sets:
        shared = want & cand
        if not shared:
            continue
        # IDF-weighted overlap, with a tiny specificity tiebreak.
        score = sum(weight(t) for t in shared) + 0.01 * len(shared) / (len(cand) + 1)
        if score > best_score:
            best, best_score = fid, score
    return best


def build_features(nav_tools: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (features, alias_issues).

    One feature per real nav route, enriched with intel ecosystem metadata via
    the live-checked alias; intel-only marketed features (no route) appended.
    """
    alias_issues: list[dict] = []
    nav_by_href = {t["href"]: t for t in nav_tools}

    # Reverse the alias: route -> intel name (for the nav-anchored pass).
    route_to_intel = {v: k for k, v in INTEL_TO_ROUTE.items() if v}

    # Validate the alias against the two live sources.
    for intel_name, href in INTEL_TO_ROUTE.items():
        if intel_name not in FEATURE_ECOSYSTEM:
            alias_issues.append({"kind": "alias_intel_missing", "feature": intel_name,
                                 "reason": f"alias key '{intel_name}' is no longer in FEATURE_ECOSYSTEM"})
        if href and href not in nav_by_href:
            alias_issues.append({"kind": "alias_route_missing", "feature": intel_name, "href": href,
                                 "reason": f"alias route '{href}' for '{intel_name}' is no longer a nav tool"})

    features: list[dict] = []

    # Pass 1 — one feature per nav tool (route is certain).
    for t in nav_tools:
        href = t["href"]
        fid = _href_stem(href) or _slug(t["label"])
        intel_name = route_to_intel.get(href)
        intel = FEATURE_ECOSYSTEM.get(intel_name, {}) if intel_name else {}
        status = "deprecated" if href in RETIRED_PAGES else "active"
        feat = {
            "id":          fid,
            "name":        intel_name or t["label"],
            "route":       href,
            "url":         "/" if href == "index.html" else f"/{href}",
            "status":      status,
            "capability":  (intel.get("loop_role") or "").strip(),
            "connects_to": intel.get("connects_to", []),
            "tables":      intel.get("tables", []),
            "edge_fns":    intel.get("edge_fns", []),
            "audience":    intel.get("audience", []),
            "nav_label":   t["label"],
            "nav_section": t["section"],
            "nav_hidden":  t["hidden"],
            "nav_roles":   t["roles"],
            "journey_key": _href_stem(href).replace("-", "_"),
            "sources":     ["nav"] + (["intel"] if intel_name else []),
            "articles":    [],   # filled after articles are parsed
        }
        features.append(feat)

    # Pass 2 — intel marketed features with no standalone route (route=None).
    for intel_name, href in INTEL_TO_ROUTE.items():
        if href is not None:
            continue
        if intel_name not in FEATURE_ECOSYSTEM:
            continue
        intel = FEATURE_ECOSYSTEM[intel_name]
        features.append({
            "id":          _slug(intel_name),
            "name":        intel_name,
            "route":       None,
            "url":         None,
            "status":      "active",
            "capability":  (intel.get("loop_role") or "").strip(),
            "connects_to": intel.get("connects_to", []),
            "tables":      intel.get("tables", []),
            "edge_fns":    intel.get("edge_fns", []),
            "audience":    intel.get("audience", []),
            "nav_label":   None,
            "nav_section": None,
            "nav_hidden":  False,
            "nav_roles":   [],
            "journey_key": _slug(intel_name).replace("-", "_"),
            "sources":     ["intel"],
            "articles":    [],
        })

    # Report any intel ecosystem feature not represented at all (would be a gap
    # between the marketed ecosystem and what the catalog can ground).
    represented = {route_to_intel.get(f["route"]) for f in features if f["route"]}
    represented |= {f["name"] for f in features if "intel" in f["sources"]}
    for intel_name in FEATURE_ECOSYSTEM:
        if intel_name not in INTEL_TO_ROUTE:
            alias_issues.append({"kind": "intel_unaliased", "feature": intel_name,
                                 "reason": f"FEATURE_ECOSYSTEM has '{intel_name}' with no alias entry — add it to INTEL_TO_ROUTE"})

    return features, alias_issues


# ── Video-journey index (consumed by storyboard.py + ui_recorder.py) ──────────

def build_journey_index(catalog: dict | None = None) -> dict:
    """Map each video-journey semantic key to the LIVE catalog route.

    Returns {key: {feature_id, route, url, label, status}}. `url` carries the
    "/workhive/<route>" form the recorder navigates. A dangling key (feature
    renamed/removed) is omitted here and flagged by self_test — so the storyboard
    and recorder follow the platform instead of a frozen snapshot.
    """
    cat = catalog or build_catalog()
    by_id = {f["id"]: f for f in cat["features"]}
    index: dict[str, dict] = {}
    for key, fid in JOURNEY_KEY_TO_FEATURE.items():
        f = by_id.get(fid)
        if not f or not f["route"]:
            continue
        index[key] = {
            "feature_id": fid,
            "route":      f["route"],
            "url":        "/workhive/" + f["route"],
            "label":      f["name"],
            "status":     f["status"],
        }
    return index


# ── /learn articles ───────────────────────────────────────────────────────────

def _article_dates(content: str) -> str | None:
    dates = re.findall(r'"date(?:Modified|Published)"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})"', content)
    dates += re.findall(r'<time[^>]*datetime="([0-9]{4}-[0-9]{2}-[0-9]{2})"', content)
    return max(dates) if dates else None


def _article_title(content: str) -> str:
    m = re.search(r"<title>(.*?)</title>", content, re.DOTALL | re.I)
    if not m:
        return ""
    t = html.unescape(m.group(1)).strip()
    return re.sub(r"\s*\|\s*WorkHive\s*$", "", t).strip()


def parse_learn_articles(features: list[dict], llms_maps: dict) -> list[dict]:
    articles: list[dict] = []
    if not LEARN_DIR.exists():
        return articles
    for idx in sorted(LEARN_DIR.glob("*/index.html")):
        slug = idx.parent.name
        content = _read(idx)
        body_norm = _norm_tokens(content)
        referenced = []
        for f in features:
            ftoks = _norm_tokens(f["name"]) | _norm_tokens(f.get("nav_label") or "")
            sig = {t for t in ftoks if len(t) > 3}
            if sig and sig <= body_norm:
                referenced.append(f["id"])
        articles.append({
            "slug":          slug,
            "title":         _article_title(content),
            "url":           f"/learn/{slug}/",
            "date_modified": _article_dates(content),
            "maps_to":       llms_maps.get(slug, {}).get("feature_id"),
            "maps_to_label": llms_maps.get(slug, {}).get("label"),
            "features_referenced": referenced,
        })
    # Back-link articles onto their features.
    by_id = {f["id"]: f for f in features}
    for a in articles:
        for fid in filter(None, [a["maps_to"], *a["features_referenced"]]):
            if fid in by_id and a["slug"] not in by_id[fid]["articles"]:
                by_id[fid]["articles"].append(a["slug"])
    return articles


# ── llms.txt ──────────────────────────────────────────────────────────────────

def parse_llms_txt(features: list[dict]) -> dict:
    content = _read(LLMS_TXT)
    if not content:
        return {"present": False, "feature_bullets": [], "articles": [], "maps": {}}

    # "## What WorkHive does" bullets (the feature claims).
    feature_bullets = []
    does_m = re.search(r"##\s*What WorkHive does\s*(.*?)(?:\n##\s|\Z)", content, re.DOTALL | re.I)
    if does_m:
        feature_bullets = re.findall(r"^\s*-\s*\*\*(.+?)\*\*", does_m.group(1), re.MULTILINE)

    # Learn page links + their "Maps to WorkHive X" hint.
    maps: dict = {}
    learn_links = []
    for lm in re.finditer(
        r"\[([^\]]+)\]\(https?://workhiveph\.com/learn/([a-z0-9-]+)/\):\s*(.*)", content
    ):
        title, slug, desc = lm.group(1), lm.group(2), lm.group(3)
        learn_links.append(slug)
        mm = re.search(r"Maps to WorkHive ([A-Za-z0-9 +/&.\-]+?)(?:\s+tool\b|\s*\(|\.)", desc)
        if mm:
            label = mm.group(1).strip()
            maps[slug] = {"label": label, "feature_id": _resolve_label_to_feature(label, features)}

    return {
        "present": True,
        "feature_bullets": feature_bullets,
        "articles": learn_links,
        "maps": maps,
    }


# ── index.html public surface ─────────────────────────────────────────────────

def parse_index_public() -> dict:
    content = _read(INDEX_HTML)
    if not content:
        return {"present": False}

    ld_types = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', content)))

    # featureList (Schema.org) — currently absent; parse if/when added.
    feature_list: list[str] = []
    fl_m = re.search(r'"featureList"\s*:\s*\[(.*?)\]', content, re.DOTALL)
    if fl_m:
        feature_list = re.findall(r'"([^"]+)"', fl_m.group(1))

    faq_questions = re.findall(r'"@type"\s*:\s*"Question"\s*,\s*"name"\s*:\s*"([^"]+)"', content)

    # Count claims in human copy: "24 guides", "30+ calculators", "33 tools".
    count_claims: dict[str, list[int]] = {}
    for cm in re.finditer(
        r"(\d+)\s*\+?\s*(?:free\s+)?(guides?|tools?|calculators?|articles?|features?)", content, re.I
    ):
        noun = cm.group(2).lower().rstrip("s")
        count_claims.setdefault(noun, []).append(int(cm.group(1)))

    sw_desc = ""
    sw_m = re.search(r'"@type"\s*:\s*"SoftwareApplication".*?"description"\s*:\s*"([^"]+)"', content, re.DOTALL)
    if sw_m:
        sw_desc = sw_m.group(1)

    return {
        "present":              True,
        "jsonld_types":         ld_types,
        "feature_list":         feature_list,
        "has_feature_list":     bool(feature_list),
        "faq_count":            len(faq_questions),
        "faq_questions":        faq_questions,
        "count_claims":         count_claims,
        "software_description": sw_desc,
    }


# ── sitemap.xml / robots.txt ──────────────────────────────────────────────────

def parse_sitemap() -> dict:
    content = _read(SITEMAP_XML)
    if not content:
        return {"present": False, "urls": [], "count": 0, "learn_count": 0}
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", content)
    learn = [u for u in urls if "/learn/" in u and not u.rstrip("/").endswith("/learn")]
    return {"present": True, "urls": urls, "count": len(urls), "learn_count": len(learn)}


# ── Assemble ──────────────────────────────────────────────────────────────────

def build_catalog() -> dict:
    nav_tools = parse_nav_tools()
    features, alias_issues = build_features(nav_tools)
    llms = parse_llms_txt(features)
    articles = parse_learn_articles(features, llms["maps"])
    index = parse_index_public()
    sitemap = parse_sitemap()

    active = [f for f in features if f["status"] == "active"]
    counts = {
        "nav_tools_total":   len(nav_tools),
        "nav_tools_visible": sum(1 for t in nav_tools if not t["hidden"]),
        "nav_tools_hidden":  sum(1 for t in nav_tools if t["hidden"]),
        "features_total":    len(features),
        "features_active":   len(active),
        "features_routed":   sum(1 for f in features if f["route"]),
        "learn_articles":    len(articles),
        "sitemap_urls":      sitemap["count"],
        "sitemap_learn_urls":sitemap["learn_count"],
        "faqs_index":        index.get("faq_count", 0),
        "intel_features":    len(FEATURE_ECOSYSTEM),
    }

    return {
        "generator":    "platform_catalog.py",
        "version":      CATALOG_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features":     features,
        "articles":     articles,
        "public_surface": {
            "index":    index,
            "sitemap":  sitemap,
            "llms_txt": {
                "present":         llms["present"],
                "feature_bullets": llms["feature_bullets"],
                "articles":        llms["articles"],
                "maps":            llms["maps"],
            },
            "robots_txt": {"present": ROBOTS_TXT.exists()},
        },
        "counts":         counts,
        "alias_issues":   alias_issues,
    }


def write_catalog(path: Path = CATALOG_PATH) -> Path:
    cat = build_catalog()
    path.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Self-test ─────────────────────────────────────────────────────────────────

def self_test() -> int:
    def ok(label):  print(f"  \033[92mPASS\033[0m  {label}")
    def bad(label): print(f"  \033[91mFAIL\033[0m  {label}")

    print("\n\033[1mplatform_catalog.py --self-test\033[0m")
    print("=" * 55)
    cat = build_catalog()
    fails = 0

    def check(cond, label):
        nonlocal fails
        (ok if cond else bad)(label)
        if not cond:
            fails += 1

    feats = cat["features"]
    by_id = {f["id"]: f for f in feats}
    arts = cat["articles"]
    counts = cat["counts"]

    check(len(feats) >= 20, f"at least 20 features derived (got {len(feats)})")
    check(all(f.get("id") for f in feats), "every feature has an id")
    check(all(f.get("status") in {"active", "beta", "deprecated"} for f in feats),
          "every feature has a valid status")
    check(all("route" in f for f in feats), "every feature carries a route key (may be null)")

    # Grounded spot-checks — known features must resolve to known routes.
    check("logbook" in by_id and by_id["logbook"]["route"] == "logbook.html"
          and by_id["logbook"]["status"] == "active",
          "logbook → logbook.html, active")
    check("pm-scheduler" in by_id and "PM Checklist" == by_id["pm-scheduler"]["name"],
          "pm-scheduler enriched with intel name 'PM Checklist'")
    check("intel" in by_id.get("predictive", {}).get("sources", []),
          "predictive route enriched from intel (analytics/predictive cluster split correctly)")
    check(by_id.get("analytics", {}).get("name") == "Analytics & OEE Dashboard",
          "analytics route maps to 'Analytics & OEE Dashboard' (not Predictive)")

    # Articles: filesystem count must match what we parsed.
    fs_articles = len(list(LEARN_DIR.glob("*/index.html"))) if LEARN_DIR.exists() else 0
    check(len(arts) == fs_articles and fs_articles >= 30,
          f"articles parsed == filesystem learn dirs ({len(arts)} == {fs_articles})")
    check(all(a.get("slug") for a in arts), "every article has a slug")
    check(any(a.get("maps_to") for a in arts),
          "at least one article resolved a 'Maps to WorkHive X' feature link")

    # Public surface populated.
    ps = cat["public_surface"]
    check(ps["index"].get("present") and ps["index"]["jsonld_types"],
          f"index.html JSON-LD parsed ({len(ps['index'].get('jsonld_types', []))} @types)")
    check(ps["sitemap"]["present"] and ps["sitemap"]["count"] > 0,
          f"sitemap parsed ({ps['sitemap']['count']} urls)")
    check(ps["llms_txt"]["present"], "llms.txt parsed")

    # Counts present + internally consistent.
    check(counts["learn_articles"] == len(arts), "counts.learn_articles consistent")
    check(counts["features_routed"] >= 20, f"≥20 routed features (got {counts['features_routed']})")

    # The alias must not dangle (live-checked join is the grounding guarantee).
    dangling = [i for i in cat["alias_issues"] if i["kind"] in {"alias_intel_missing", "alias_route_missing"}]
    check(not dangling,
          "no dangling alias entries (every aliased intel name + href still live)"
          + ("" if not dangling else f" — {[i['reason'] for i in dangling]}"))

    # The video-journey index must resolve every semantic key to a live route
    # (the storyboard/recorder grounding guarantee — no frozen /workhive/<page>).
    jidx = build_journey_index(cat)
    journey_dangling = [k for k in JOURNEY_KEY_TO_FEATURE if k not in jidx]
    check(not journey_dangling,
          f"journey index resolves all {len(JOURNEY_KEY_TO_FEATURE)} keys to live routes"
          + ("" if not journey_dangling else f" — dangling: {journey_dangling}"))
    check(jidx.get("pm_checklist", {}).get("url") == "/workhive/pm-scheduler.html",
          "journey 'pm_checklist' → live /workhive/pm-scheduler.html (catalog-derived, not a literal)")

    print("=" * 55)
    if fails == 0:
        print("\033[92m  self-test PASS\033[0m\n")
    else:
        print(f"\033[91m  self-test FAIL — {fails} check(s) failed\033[0m\n")
    return 1 if fails else 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_summary(cat: dict) -> None:
    c = cat["counts"]
    print(f"\nPlatform Catalog  ·  generated {cat['generated_at']}")
    print("=" * 64)
    print(f"  features: {c['features_total']} ({c['features_routed']} routed, "
          f"{c['features_active']} active)   articles: {c['learn_articles']}")
    print(f"  nav tools: {c['nav_tools_total']} ({c['nav_tools_visible']} visible / "
          f"{c['nav_tools_hidden']} hidden)   intel ecosystem: {c['intel_features']}")
    print(f"  sitemap urls: {c['sitemap_urls']} ({c['sitemap_learn_urls']} learn)   "
          f"index FAQs: {c['faqs_index']}")
    cc = cat["public_surface"]["index"].get("count_claims", {})
    if cc:
        print(f"  index count CLAIMS: {dict(cc)}   (live articles = {c['learn_articles']})")
    if cat["alias_issues"]:
        print(f"\n  \033[93m{len(cat['alias_issues'])} alias note(s):\033[0m")
        for i in cat["alias_issues"]:
            print(f"    - [{i['kind']}] {i['reason']}")
    print()


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    cat = build_catalog()
    if "--print" in argv:
        _print_summary(cat)
        return 0
    path = write_catalog()
    _print_summary(cat)
    print(f"  → wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
