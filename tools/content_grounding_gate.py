"""
content_grounding_gate.py — Content Grounding Gate, Layer G0/G1 (drift validators).
====================================================================================

The semantic layer the existing structural SEO validators lack: every drift type
the plan enumerates, each checked against the auto-derived Platform Catalog
(platform_catalog.py) and the live surfaces, with a per-check forward-only
ratcheted baseline (the same convention as validate_meta_description_coverage.py
and the ~80 L0 ratchets in run_platform_checks.py).

Lives in tools/ (not a root validate_*.py) because it is the Content Grounding
Gate's OWN validator — invoked by content_dev.py / phase_content, not the
platform validator registry. (run_platform_checks.py's auto-discovery only
requires ROOT-level validate_*.py to be registered.)

Drift checks (the taxonomy from CONTENT_GROUNDING_GATE.md):
  feature_drift       content names a feature that resolves to no ACTIVE catalog
                      feature (orphan) or to a DEPRECATED one
  count_drift         a homepage guide/article count claim != live article count
  link_drift          an internal .html / /learn/<slug>/ link does not resolve, or
                      points at a retired page
  learn_hub_unlisted  an article on disk is not linked from the learn hub
  sitemap_drift       an article on disk is missing from sitemap.xml
  schema_featurelist  a JSON-LD featureList entry not ⊆ the catalog
  undated_articles    an article carries no dateModified (freshness signal)

Ratchet semantics (forward-only):
  • first run establishes the baseline at the current (pre-existing) drift count
    so the gate does NOT block on drift that already existed — but records it;
  • a check FAILs only when its current count EXCEEDS its baseline (NEW drift);
  • a baseline only ratchets DOWN (when drift is fixed), never up;
  • --strict ignores the baseline and FAILs on ANY drift > 0 (the "should be
    clean" posture — used to demonstrate teeth and as the regen target);
  • --update-baseline lowers the baseline to current (only downward).

CLI:
    python tools/content_grounding_gate.py                 # ratcheted run
    python tools/content_grounding_gate.py --strict        # fail on any drift
    python tools/content_grounding_gate.py --update-baseline
    python tools/content_grounding_gate.py --self-test
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

import platform_catalog as pc          # noqa: E402
import content_substrate as cs         # noqa: E402
import page_evidence as pe             # noqa: E402
import render_public_surface as rps    # noqa: E402  (D1 derive-and-render guard)

BASELINE_PATH = ROOT / "content_grounding_baseline.json"
REPORT_PATH = ROOT / "content_grounding_report.json"

CHECK_ORDER = [
    "feature_drift", "count_drift", "link_drift",
    "learn_hub_unlisted", "sitemap_drift", "schema_featurelist", "undated_articles",
    "capability_drift", "affordance_repetition", "wall_of_text",
    "surface_render_drift", "llms_article_completeness",
]

# Verbs that mark a sentence as ATTRIBUTING a capability to the product (vs stating
# general domain knowledge). A WorkHive-attributed sentence with one of these is a
# "product claim" that must trace to the page's real affordances.
CAPABILITY_VERBS = {
    "generate", "generates", "generated", "auto", "automatically", "alert", "alerts",
    "notify", "notifies", "flag", "flags", "show", "shows", "display", "displays",
    "track", "tracks", "log", "logs", "record", "records", "calculate", "calculates",
    "reserve", "reserves", "predict", "predicts", "send", "sends", "create", "creates",
    "sync", "syncs", "export", "exports", "scan", "scans", "detect", "detects",
    "recommend", "recommends", "schedule", "schedules", "assign", "assigns", "score",
    "scores", "suggest", "suggests", "lets", "allows", "enables", "tap", "click",
    "button", "screen", "dashboard", "tab", "field", "form",
}
# Capability claims whose distinctive content tokens overlap the page vocab by at
# least this fraction are considered grounded. 0 distinctive overlap = invented.
_CAP_MIN_OVERLAP = 1   # require >=1 distinctive token present in the page evidence


# ── Drift checks ──────────────────────────────────────────────────────────────

def _public_surface_files() -> list[Path]:
    files = [pc.INDEX_HTML, pc.LEARN_DIR / "index.html"]
    files += sorted(pc.LEARN_DIR.glob("*/index.html"))
    return [f for f in files if f.exists()]


_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _article_visible_text(slug: str) -> str:
    body = pc._read(pc.LEARN_DIR / slug / "index.html")
    body = _SCRIPT_STYLE.sub(" ", body)
    return pe._WS.sub(" ", pe._TAG.sub(" ", body))


def _platform_vocab(cat: dict, evidence: dict) -> set:
    """The WHOLE platform's real vocabulary: every page's affordances + every
    feature name. A product claim is INVENTED only if its distinctive words trace
    to NONE of this — i.e. the platform genuinely cannot do what's claimed. This
    is the conservative grounding (Ian's 'prefer false-negative') — it does not
    police WHICH feature an affordance belongs to (that's the opt-in LLM judge),
    only whether the affordance exists ANYWHERE on the real platform."""
    vocab = set()
    for ev in evidence.values():
        vocab |= set(ev.get("vocab", []))
        for bucket in ("headings", "actions", "fields", "tabs"):
            for item in ev.get(bucket, []):
                vocab |= pe._toks(item)
    for f in cat["features"]:
        vocab |= pe._toks(f.get("name", "")) | pe._toks(f.get("nav_label") or "")
    return vocab


def _capability_drift_issues(cat: dict, evidence: dict) -> list:
    """A WorkHive-ATTRIBUTED capability sentence whose distinctive content words
    exist NOWHERE in the real platform vocabulary = invented.

    Conservative by design (Ian's rule): only product claims (WorkHive/feature
    attribution + a capability verb) are grounded; general/domain knowledge is
    never touched; a claim is flagged only when the whole platform has ZERO
    vocabulary for its distinctive content (≥2 distinctive tokens, all absent)."""
    issues = []
    by_id = {f["id"]: f for f in cat["features"]}
    platform_vocab = _platform_vocab(cat, evidence)
    for a in cat["articles"]:
        fid = a.get("maps_to")
        if not fid or fid not in evidence:
            continue
        f = by_id.get(fid, {})
        name_toks = pe._toks(f.get("name", "")) | pe._toks(f.get("nav_label") or "")
        label_low = (f.get("nav_label") or "").lower()
        name_low = (f.get("name") or "").lower()
        for sent in _SENT_SPLIT.split(_article_visible_text(a["slug"])):
            low = sent.lower()
            if len(low) < 20 or len(low) > 320:
                continue
            attributed = ("workhive" in low) or (label_low and label_low in low) or (name_low and name_low in low)
            if not attributed:
                continue
            if not any(v in re.split(r"[^a-z]+", low) for v in CAPABILITY_VERBS):
                continue
            # distinctive content tokens (drop the feature name + capability verbs +
            # proper-noun colour: PH places / equipment IDs carry digits or are
            # article flavour, not capability claims).
            distinctive = {t for t in pe._toks(sent)
                           if len(t) > 4 and t not in name_toks and t not in CAPABILITY_VERBS
                           and not any(ch.isdigit() for ch in t)}
            if len(distinctive) < 2:
                continue
            # Conservative (Ian's rule, prefer false-negative): flag ONLY when the
            # claim's distinctive content has NO word anywhere on the real platform —
            # a clear invention. The harder mixed real+invented sentence is left to
            # the opt-in Tier-2 LLM judge (capability_issues_for_text use_llm=True);
            # terse-UI-vocab vs descriptive-prose mismatch makes a fraction rule
            # over-flag legit synonyms, so we do not use one here.
            if not (distinctive & platform_vocab):
                issues.append({
                    "article": a["slug"], "feature": fid,
                    "claim": sent.strip()[:200],
                    "reason": f"'{a['slug']}' attributes a capability to {f.get('name', fid)} whose "
                              f"distinctive content ({sorted(distinctive)[:5]}) exists NOWHERE on the real platform",
                })
    return issues


# ── Readability drift (the 2026-06-10 resume-article lesson) ─────────────────
# Padding is a drift class: the generator's old 1500-word floor + paragraphs-only
# rule produced articles that re-explained the same real controls in 4 sections
# and carried zero scannable structure. Both are measurable, so both are gated.

_PROSE_START = re.compile(r'class="prose-wh"')
_H2_SPLIT = re.compile(r"<h2\b")
_NORM_RE = re.compile(r"[^a-z0-9]+")
_STRUCT_TAGS = ("<table", "<ol", "<ul", "<figure", "<h3", 'class="callout"')
_WALL_MIN_WORDS = 700      # short articles can be pure prose; long ones cannot
_REPEAT_MAX_SECTIONS = 2   # an affordance may appear in at most 2 body sections


def _norm_text(s: str) -> str:
    return _NORM_RE.sub(" ", (s or "").lower()).strip()


def _article_prose_region(slug: str) -> str:
    """The article's BODY region: from the prose-wh wrapper to the FAQ heading.
    Excludes head/nav/TOC/audience (before) and FAQ/sources/footer (after).
    Every live article carries both markers (verified across all 37)."""
    body = pc._read(pc.LEARN_DIR / slug / "index.html")
    m = _PROSE_START.search(body)
    if not m:
        return ""
    start = m.end()
    end = body.find('id="faq"', start)
    return body[start:end if end != -1 else len(body)]


def _substantial_affordances(ev: dict) -> list:
    """The page's >=2-word control labels (actions + fields), normalized.
    Template fragments (contain $ or {) are not labels."""
    labels = set()
    for bucket in ("actions", "fields"):
        for item in ev.get(bucket, []):
            if "$" in item or "{" in item:
                continue
            norm = _norm_text(item)
            if len(norm.split()) >= 2:
                labels.add(norm)
    return sorted(labels)


def _affordance_repetition_issues(cat: dict, evidence: dict) -> list:
    """An article that walks through the SAME real control in 3+ body sections
    is padding, not teaching (the resume article explained 'Auto-fill from my
    WorkHive data' in 5 of 6 sections). Explain once, reference thereafter."""
    issues = []
    for a in cat["articles"]:
        fid = a.get("maps_to")
        ev = evidence.get(fid) if fid else None
        if not ev:
            continue
        region = _article_prose_region(a["slug"])
        if not region:
            continue
        sec_norms = [_norm_text(pe._TAG.sub(" ", chunk))
                     for chunk in _H2_SPLIT.split(region) if chunk.strip()]
        for label in _substantial_affordances(ev):
            hits = sum(1 for sn in sec_norms if label in sn)
            if hits > _REPEAT_MAX_SECTIONS:
                issues.append({
                    "article": a["slug"], "affordance": label, "sections": hits,
                    "reason": f"'{a['slug']}' re-explains control '{label}' in {hits} body "
                              f"sections (max {_REPEAT_MAX_SECTIONS}): explain once, reference thereafter",
                })
    return issues


def _wall_of_text_issues(articles: list) -> list:
    """A long article body with ZERO scannable structure (no table, list,
    callout, figure, or h3) reads as a wall. NN/g: users read ~20-28% of words;
    structure is what lets the other 72% still land."""
    issues = []
    for a in articles:
        region = _article_prose_region(a["slug"])
        if not region:
            continue
        words = len(re.findall(r"\b\w+\b", pe._TAG.sub(" ", _SCRIPT_STYLE.sub(" ", region))))
        n_struct = sum(region.count(t) for t in _STRUCT_TAGS)
        if words > _WALL_MIN_WORDS and n_struct == 0:
            issues.append({
                "article": a["slug"], "body_words": words,
                "reason": f"'{a['slug']}' body is {words} words with ZERO structural elements "
                          f"(table/list/callout/figure/h3): wall of text",
            })
    return issues


def _attributed_capability_sentences(text: str, feature: dict) -> list:
    """Sentences that ATTRIBUTE a capability to this feature (attribution cue +
    a capability verb). These are the product claims a grounding judge rules on."""
    label_low = (feature.get("nav_label") or "").lower()
    name_low = (feature.get("name") or "").lower()
    out = []
    for sent in _SENT_SPLIT.split(text):
        low = sent.lower().strip()
        if len(low) < 20 or len(low) > 320:
            continue
        attributed = ("workhive" in low) or (label_low and label_low in low) or (name_low and name_low in low)
        if not attributed:
            continue
        if any(v in re.split(r"[^a-z]+", low) for v in CAPABILITY_VERBS):
            out.append(sent.strip())
    return out


def _llm_says_unsupported(claim: str, feature: dict, ev: dict) -> bool:
    """Tier-2, ONE sentence at a time (reliable even on a weak free-tier model).
    Returns True if the judge says the claim is outside what the real tool does."""
    try:
        try:
            from ai_chain import call_ai_chain
        except ImportError:
            from tools.ai_chain import call_ai_chain
    except Exception:
        return False
    prompt = f"""WorkHive is an INDUSTRIAL MAINTENANCE web app. Its "{feature.get('name')}" page
({ev.get('route')}) really offers only: {ev.get('headings', [])[:10]} | {ev.get('actions', [])[:14]}.

Does the following sentence claim WorkHive does something a maintenance web app CANNOT do, or an
invented screen/button/capability not in that list? Booking dentist appointments, brewing coffee,
teleporting or moving physical objects = YES (invented). General maintenance knowledge or normal
software actions (log, record, track, search, export, schedule) = NO.

SENTENCE: "{claim}"

Answer with ONLY one word: YES (invented / cannot do) or NO (plausible)."""
    try:
        out = (call_ai_chain(prompt, max_tokens=6, json_mode=False) or "").strip().upper()
        return out.startswith("YES")
    except Exception:
        return False


def _llm_judge_unsupported(claims: list, feature: dict, ev: dict) -> list:
    return [c for c in claims if _llm_says_unsupported(c, feature, ev)]


def capability_issues_for_text(text: str, feature_id: str, cat: dict | None = None,
                               evidence: dict | None = None, use_llm: bool | None = None) -> list:
    """Run the capability-grounding check on ARBITRARY text (a generated article,
    a video script) mapped to a feature — the generation-time grounding hook.

    Tier-1 (deterministic, always): flags claims whose distinctive content exists
    NOWHERE on the platform. Tier-2 (opt-in LLM judge): catches the harder case —
    a mostly-real sentence with an invented clause — that token overlap can't.
    Enable Tier-2 with use_llm=True or env CONTENT_LLM_JUDGE=1."""
    import os
    cat = cat or pc.build_catalog()
    evidence = evidence or pe.load_evidence()
    if use_llm is None:
        use_llm = os.getenv("CONTENT_LLM_JUDGE", "").strip().lower() in ("1", "true", "yes", "on")

    synth_cat = {"features": cat["features"], "articles": [{"slug": "_probe", "maps_to": feature_id}]}
    saved = globals().get("_article_visible_text")
    globals()["_article_visible_text"] = lambda _slug: text
    try:
        tier1 = _capability_drift_issues(synth_cat, evidence)
    finally:
        globals()["_article_visible_text"] = saved

    if not use_llm or feature_id not in evidence:
        return tier1

    feature = {f["id"]: f for f in cat["features"]}.get(feature_id, {})
    tier1_claims = {i["claim"] for i in tier1}
    name_toks = pe._toks(feature.get("name", "")) | pe._toks(feature.get("nav_label") or "")
    platform_vocab = _platform_vocab(cat, evidence)

    # Pre-filter to the genuinely SUSPICIOUS sentences: those that carry distinctive
    # content the whole platform has no word for. A fully-grounded article yields
    # zero of these (so zero LLM calls); only a mixed real+invented sentence (the
    # case Tier-1 misses) reaches the judge.
    candidates = []
    for s in _attributed_capability_sentences(text, feature):
        if s[:200] in tier1_claims:
            continue
        distinctive = {t for t in pe._toks(s)
                       if len(t) > 4 and t not in name_toks and t not in CAPABILITY_VERBS
                       and not any(ch.isdigit() for ch in t)}
        # Suspicious = ≥2 distinctive tokens with no word anywhere on the platform.
        # Legit prose rarely clears this (it reuses platform/domain words); an
        # invented clause does. Keeps the per-sentence judge to a tiny, sharp set.
        if len(distinctive - platform_vocab) >= 2:
            candidates.append(s)
    unsupported = _llm_judge_unsupported(candidates[:12], feature, evidence[feature_id])
    tier2 = [{"article": "_probe", "feature": feature_id, "claim": c[:200],
              "reason": f"LLM judge: claim not supported by {feature.get('route')} real affordances"}
             for c in unsupported]
    return tier1 + tier2


def run_checks() -> dict:
    cat = pc.build_catalog()
    disc = cs.discover(cat)
    features = cat["features"]
    by_id = {f["id"]: f for f in features}
    live_articles = len(cat["articles"])
    catalog_routes = {f["route"] for f in features if f["route"]}
    evidence = pe.load_evidence()

    checks: dict[str, dict] = {}

    # 1. feature_drift — orphans (no catalog backing) + references to deprecated.
    issues = list(disc["orphans"])
    for slug, m in cat["public_surface"]["llms_txt"]["maps"].items():
        fid = m.get("feature_id")
        if fid and by_id.get(fid, {}).get("status") == "deprecated":
            issues.append({"source": f"llms.txt:{slug}", "claim": m.get("label"),
                           "reason": f"article '{slug}' Maps to '{m.get('label')}' which is a DEPRECATED feature"})
    checks["feature_drift"] = {"count": len(issues), "issues": issues}

    # 2. count_drift — homepage guide/article count claims vs live article count.
    cc = cat["public_surface"]["index"].get("count_claims", {})
    issues = []
    for noun in ("guide", "article"):
        for val in sorted(set(cc.get(noun, []))):
            if val != live_articles:
                issues.append({"claim": f"{val} {noun}s", "live": live_articles,
                               "reason": f"index.html claims {val} {noun}s but {live_articles} articles are live"})
    checks["count_drift"] = {"count": len(issues), "issues": issues}

    # 3. link_drift — internal links that don't resolve, or point at a retired page.
    issues = []
    seen = set()
    for f in _public_surface_files():
        body = pc._read(f)
        src = f.relative_to(ROOT).as_posix()
        for href in re.findall(r'href="(/?[a-z0-9][a-z0-9-]*\.html)"', body):
            target = href.lstrip("/")
            key = (src, target)
            if key in seen:
                continue
            seen.add(key)
            if target in pc.RETIRED_PAGES:
                issues.append({"source": src, "href": href,
                               "reason": f"{src} links retired page '{target}'"})
            elif not (ROOT / target).exists():
                issues.append({"source": src, "href": href,
                               "reason": f"{src} links '{target}' which does not exist on disk"})
        for slug in re.findall(r'href="/?learn/([a-z0-9-]+)/?"', body):
            if slug == "index":
                continue
            key = (src, f"learn/{slug}")
            if key in seen:
                continue
            seen.add(key)
            if not (pc.LEARN_DIR / slug / "index.html").exists():
                issues.append({"source": src, "href": f"/learn/{slug}/",
                               "reason": f"{src} links '/learn/{slug}/' which has no article on disk"})
    checks["link_drift"] = {"count": len(issues), "issues": issues}

    # 4. learn_hub_unlisted — articles on disk not linked from the learn hub.
    unlisted = disc.get("learn_hub_unlisted", [])
    checks["learn_hub_unlisted"] = {
        "count": len(unlisted),
        "issues": [{"slug": s, "reason": f"article '{s}' exists on disk but is not linked from the learn hub"} for s in unlisted],
    }

    # 5. sitemap_drift — articles on disk missing from sitemap.xml.
    sitemap_urls = cat["public_surface"]["sitemap"]["urls"]
    sitemap_slugs = set(re.findall(r"/learn/([a-z0-9-]+)/?", " ".join(sitemap_urls)))
    issues = [{"slug": a["slug"], "reason": f"article '{a['slug']}' is not in sitemap.xml"}
              for a in cat["articles"] if a["slug"] not in sitemap_slugs]
    checks["sitemap_drift"] = {"count": len(issues), "issues": issues}

    # 6. schema_featurelist — JSON-LD featureList entries not ⊆ catalog.
    fl = cat["public_surface"]["index"].get("feature_list", [])
    issues = [{"entry": e, "reason": f"JSON-LD featureList '{e}' resolves to no catalog feature"}
              for e in fl if pc._resolve_label_to_feature(e, features) is None]
    checks["schema_featurelist"] = {"count": len(issues), "issues": issues}

    # 7. undated_articles — freshness signal (articles with no dateModified).
    issues = [{"slug": a["slug"], "reason": f"article '{a['slug']}' carries no dateModified"}
              for a in cat["articles"] if not a["date_modified"]]
    checks["undated_articles"] = {"count": len(issues), "issues": issues}

    # 8. capability_drift — a product claim (flow/how-to/capability) that the
    #    mapped page has no real affordance for = invented (the provenance layer).
    issues = _capability_drift_issues(cat, evidence)
    checks["capability_drift"] = {"count": len(issues), "issues": issues}

    # 9. affordance_repetition — the same real control walked through in 3+
    #    body sections = padding drift (the 2026-06-10 resume-article lesson).
    issues = _affordance_repetition_issues(cat, evidence)
    checks["affordance_repetition"] = {"count": len(issues), "issues": issues}

    # 10. wall_of_text — long body, zero scannable structure.
    issues = _wall_of_text_issues(cat["articles"])
    checks["wall_of_text"] = {"count": len(issues), "issues": issues}

    # 11. surface_render_drift — a catalog-derived marker region on a public
    #     surface (index.html / llms.txt / learn hub) whose rendered value no
    #     longer matches the catalog (D1 derive-and-render guard). A drift here
    #     means someone hand-edited a machine-managed fact; heal with
    #     `python tools/render_public_surface.py --apply`.
    issues = [{"surface": i["surface"], "key": i["key"], "reason": i["reason"]}
              for i in rps.check(rps.render_values(cat))]
    checks["surface_render_drift"] = {"count": len(issues), "issues": issues}

    # 12. llms_article_completeness — every learn article must be named in llms.txt.
    #     GEO surface: AI crawlers read llms.txt; an article absent from it is
    #     invisible to them (D1 found the AI-Companion article missing → the 37-vs-38).
    llms_raw = pc._read(pc.LLMS_TXT)
    llms_slugs = set(re.findall(r"/learn/([a-z0-9-]+)/", llms_raw))
    issues = [{"slug": a["slug"], "reason": f"article '{a['slug']}' is not named in llms.txt (GEO gap — invisible to AI crawlers)"}
              for a in cat["articles"] if a["slug"] not in llms_slugs]
    checks["llms_article_completeness"] = {"count": len(issues), "issues": issues}

    return checks


# ── Ratchet engine ────────────────────────────────────────────────────────────

def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def evaluate(strict: bool = False, update_baseline: bool = False) -> tuple[int, dict]:
    checks = run_checks()
    prior = _load_baseline().get("checks", {})
    new_base: dict[str, int] = {}
    rows = []
    fails = []
    for name in CHECK_ORDER:
        cur = checks[name]["count"]
        base = prior.get(name, cur)            # first-seen establishes at current
        ratcheted = min(base, cur)             # forward-only: only ever lower
        over = cur > ratcheted
        if strict:
            failing = cur > 0
            shown_base = 0
        else:
            failing = over
            shown_base = ratcheted
        if failing:
            fails.append(name)
        new_base[name] = ratcheted
        rows.append({"check": name, "current": cur, "baseline": shown_base,
                     "status": "FAIL" if failing else ("OK" if cur == 0 else "HELD"),
                     "issues": checks[name]["issues"]})

    total_drift = sum(checks[n]["count"] for n in CHECK_ORDER)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode":         "strict" if strict else "ratchet",
        "total_drift":  total_drift,
        "failed_checks": fails,
        "checks":       rows,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Persist the (only-ever-lower) baseline unless running strict.
    if not strict:
        established = BASELINE_PATH.exists()
        BASELINE_PATH.write_text(json.dumps({
            "checks": new_base,
            "established": (_load_baseline().get("established") if established else datetime.now(timezone.utc).isoformat(timespec="seconds")),
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
    elif update_baseline:
        BASELINE_PATH.write_text(json.dumps({
            "checks": {n: checks[n]["count"] for n in CHECK_ORDER},
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")

    return (1 if fails else 0), report


# ── Pretty print ──────────────────────────────────────────────────────────────

def _print_report(report: dict) -> None:
    def c(code, s): return f"\033[{code}m{s}\033[0m"
    print(f"\nContent Grounding Gate ({report['mode']})  ·  {report['generated_at']}")
    print("=" * 68)
    for r in report["checks"]:
        tag = {"FAIL": c("91", "FAIL"), "HELD": c("93", "HELD"), "OK": c("92", "OK")}[r["status"]]
        print(f"  {tag}  {r['check']:<20} current={r['current']:<3} baseline={r['baseline']}")
        if r["status"] != "OK":
            for iss in r["issues"][:6]:
                print(f"          - {iss.get('reason')}")
            if len(r["issues"]) > 6:
                print(f"          … +{len(r['issues']) - 6} more")
    n_fail = len(report["failed_checks"])
    if n_fail == 0:
        print(c("92", f"\n  PASS — no check exceeds its baseline (total drift recorded: {report['total_drift']}).\n"))
    else:
        print(c("91", f"\n  FAIL — {n_fail} check(s) over baseline: {', '.join(report['failed_checks'])}\n"))


# ── Self-test ─────────────────────────────────────────────────────────────────

def self_test() -> int:
    def ok(label):  print(f"  \033[92mPASS\033[0m  {label}")
    def bad(label): print(f"  \033[91mFAIL\033[0m  {label}")
    print("\n\033[1mcontent_grounding_gate.py --self-test\033[0m")
    print("=" * 55)
    fails = 0

    def check(cond, label):
        nonlocal fails
        (ok if cond else bad)(label)
        if not cond:
            fails += 1

    checks = run_checks()
    check(set(checks) == set(CHECK_ORDER), "all drift checks ran")
    check(all("count" in v and "issues" in v for v in checks.values()),
          "every check reports a count + issues list")

    # Teeth proofs are SYNTHETIC (monkeypatched), never dependent on live drift —
    # the original live-drift assertions broke the moment the drift was FIXED
    # (caught in the cockpit mega run right after the 2026-06-10 hub/count fix).
    _saved_hub = cs._learn_hub_linked_slugs
    cs._learn_hub_linked_slugs = lambda: set()          # hub "lost" every link
    try:
        synth = run_checks()
        check(synth["learn_hub_unlisted"]["count"] >= 30,
              f"learn_hub_unlisted teeth (synthetic empty hub → {synth['learn_hub_unlisted']['count']} flagged)")
    finally:
        cs._learn_hub_linked_slugs = _saved_hub

    _saved_idx = pc.parse_index_public
    def _fake_index():
        d = _saved_idx()
        d = dict(d); d["count_claims"] = {"guide": [24]}   # stale claim, whatever live is
        return d
    pc.parse_index_public = _fake_index
    try:
        synth = run_checks()
        check(synth["count_drift"]["count"] >= 1,
              "count_drift teeth (synthetic stale '24 guides' claim flagged)")
    finally:
        pc.parse_index_public = _saved_idx

    # Clean checks should be clean (no false positives on a correct surface).
    check(checks["sitemap_drift"]["count"] == 0,
          f"sitemap_drift clean ({checks['sitemap_drift']['count']}) — no false positive")

    # capability_drift teeth: a synthetic catalog+evidence where one article makes
    # an invented WorkHive capability claim must be flagged; a grounded one must not.
    synth_cat = {
        "features": [{"id": "logbook", "name": "Maintenance Logbook", "nav_label": "Logbook", "route": "logbook.html"}],
        "articles": [
            {"slug": "_grounded_probe", "maps_to": "logbook"},
            {"slug": "_invented_probe", "maps_to": "logbook"},
        ],
    }
    synth_ev = {"logbook": {"route": "logbook.html", "headings": ["Log a Repair", "My Open Jobs"],
                            "actions": ["Register Asset", "Analyze with AI"], "fields": [], "tabs": [],
                            "links_to": [], "vocab": ["repair", "asset", "breakdown", "anomaly", "logbook", "register", "analyze"]}}
    import types
    saved = globals().get("_article_visible_text")
    texts = {
        "_grounded_probe": "WorkHive lets you log every repair and register each asset in the logbook.",
        "_invented_probe": "WorkHive automatically books your dentist appointment and brews espresso from the logbook.",
    }
    globals()["_article_visible_text"] = lambda slug: texts.get(slug, "")
    try:
        synth_issues = _capability_drift_issues(synth_cat, synth_ev)
    finally:
        globals()["_article_visible_text"] = saved
    flagged = {i["article"] for i in synth_issues}
    check("_invented_probe" in flagged, "capability_drift FLAGS an invented WorkHive capability (dentist/espresso)")
    check("_grounded_probe" not in flagged, "capability_drift does NOT flag a grounded claim (log repair / register asset)")

    # affordance_repetition + wall_of_text teeth: SYNTHETIC article regions
    # (monkeypatched _article_prose_region), never live-drift dependent.
    synth_cat2 = {
        "features": [{"id": "logbook", "name": "Maintenance Logbook", "nav_label": "Logbook", "route": "logbook.html"}],
        "articles": [
            {"slug": "_repeat_probe", "maps_to": "logbook"},
            {"slug": "_concise_probe", "maps_to": "logbook"},
        ],
    }
    synth_ev2 = {"logbook": {"route": "logbook.html", "headings": [], "tabs": [], "links_to": [],
                             "actions": ["Register Asset", "Analyze with AI"], "fields": [], "vocab": []}}
    sec_repeat = "<h2>A</h2><p>Tap Register Asset to begin.</p>"
    regions = {
        "_repeat_probe": sec_repeat * 4,                       # same control in 4 sections
        "_concise_probe": sec_repeat + "<h2>B</h2><p>Reference Register Asset by name only here is fine in a second section.</p><h2>C</h2><p>Other content.</p>",
        "_wall_probe": "<h2>A</h2>" + "<p>" + ("word " * 800) + "</p>",
        "_scannable_probe": "<h2>A</h2><table><tr><td>x</td></tr></table>" + "<p>" + ("word " * 800) + "</p>",
    }
    saved_region = globals()["_article_prose_region"]
    globals()["_article_prose_region"] = lambda slug: regions.get(slug, "")
    try:
        rep_issues = _affordance_repetition_issues(synth_cat2, synth_ev2)
        wall_issues = _wall_of_text_issues([{"slug": "_wall_probe"}, {"slug": "_scannable_probe"}])
    finally:
        globals()["_article_prose_region"] = saved_region
    rep_flagged = {i["article"] for i in rep_issues}
    check("_repeat_probe" in rep_flagged, "affordance_repetition FLAGS a control re-explained in 4 sections")
    check("_concise_probe" not in rep_flagged, "affordance_repetition allows explain-once + one reference")
    wall_flagged = {i["article"] for i in wall_issues}
    check("_wall_probe" in wall_flagged, "wall_of_text FLAGS 800 structureless words")
    check("_scannable_probe" not in wall_flagged, "wall_of_text passes the same length WITH structure")

    # Strict mode must FAIL on ANY drift (teeth). Proven with SYNTHETIC drift (an
    # empty learn hub → every article flagged), so the assertion is live-state-
    # INDEPENDENT: it must hold even when the live platform is fully clean — which
    # is the goal state. A green platform must never starve this teeth test (the
    # old form read live drift and broke the day the last real drift was healed).
    _orig_hub = cs._learn_hub_linked_slugs
    cs._learn_hub_linked_slugs = lambda: set()
    try:
        rc_strict, rep_strict = evaluate(strict=True)
    finally:
        cs._learn_hub_linked_slugs = _orig_hub
    check(rc_strict == 1 and rep_strict["total_drift"] > 0,
          "strict mode FAILs on synthetic drift (gate has teeth, live-state-independent)")

    # Ratchet mode establishes a baseline and PASSes on pre-existing drift.
    rc_ratchet, rep_ratchet = evaluate(strict=False)
    check(rc_ratchet == 0, "ratchet mode PASSes (forward-only baseline absorbs pre-existing drift)")
    check(BASELINE_PATH.exists(), "baseline file written by ratchet run")

    # Teeth-on-NEW-drift: with a 0 baseline, SYNTHETIC drift (empty hub) must
    # exceed it — proving a regression would trip the ratchet. State-independent.
    cs._learn_hub_linked_slugs = lambda: set()
    try:
        cur = run_checks()["learn_hub_unlisted"]["count"]
        check(cur > 0, "synthetic NEW drift exceeds a 0 baseline (regression teeth, live-state-independent)")
    finally:
        cs._learn_hub_linked_slugs = _saved_hub

    print("=" * 55)
    if fails == 0:
        print("\033[92m  self-test PASS\033[0m\n")
    else:
        print(f"\033[91m  self-test FAIL — {fails} check(s) failed\033[0m\n")
    return 1 if fails else 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    strict = "--strict" in argv
    update = "--update-baseline" in argv
    rc, report = evaluate(strict=strict, update_baseline=update)
    _print_report(report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
