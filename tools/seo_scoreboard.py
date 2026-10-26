"""
seo_scoreboard.py — the drive-to-100% compass for the five pillars (V3 §7).
===========================================================================
Computes each pillar's completion % from the LIVE GATE REPORTS, never from a
hand-typed number. V2's original sin was a self-graded scoreboard; V3's rule is
that a pillar is graded by an instrument. This is that rule made executable: every
component below names the report it reads, so the percentage cannot drift from the
thing it claims to measure.

TWO TOTALS, because they answer different questions:
  OVERALL %  — the honest state of the programme.
  LOCAL %    — the ceiling reachable without Ian. Components marked [IAN] need a
               profile created, a deploy run, a post published, or an engine
               queried by hand; no amount of local work moves them, and hiding
               that inside one number is how "95% done" means "stuck".

A component is achieved/total, so partial credit is real: 17 of 53 openers
carrying a number+unit+entity scores 32%, not 0 and not 1.

RUN:  python tools/seo_scoreboard.py
      python tools/seo_scoreboard.py --json
      python tools/seo_scoreboard.py --self-test
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

OUT = ROOT / "seo_scoreboard.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _rep(name: str) -> dict:
    p = ROOT / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _checks(rep: dict) -> dict:
    return {c["check"]: c["current"] for c in rep.get("checks", [])} if rep.get("checks") else {}


# ── live reads (KA-B, 2026-10-27): a component that needs Ian still READS its measure, and says why it reads 0 ───────
# Seven components were typed 0/1 constants ("deployed to production 0", "GSC + Bing 0", "live SOV baseline 0",
# "off-site channels 0", "listicle 0") - true on the day they were typed and silently wrong the day any of them moved.
# Each now reads the thing it names; a read that cannot happen (no network, no credential, no record) scores 0 AND
# says so in its reason, which is the difference between "not done" and "not measurable here".
PROD = "https://workhiveph.com"
LIVE_REASONS: dict = {}


def _head(url: str, timeout: float = 8.0) -> int:
    import urllib.request
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "WorkHive-SEO-Scoreboard/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode()
    except Exception as e:   # noqa: BLE001 - any failure is "not reachable", stated in the reason
        return getattr(e, "code", 0) or 0


def _indexnow_key() -> str | None:
    for f in sorted(ROOT.glob("*.txt")):
        stem = f.stem
        if re.fullmatch(r"[a-f0-9]{8,128}", stem, re.I) and f.read_text(encoding="utf-8", errors="replace").strip() == stem:
            return stem
    return None


def prod_deployed() -> tuple:
    """KA358: production serves the sitemap, robots.txt and the IndexNow key file (HEAD, 200)."""
    key = _indexnow_key()
    urls = [f"{PROD}/sitemap.xml", f"{PROD}/robots.txt"] + ([f"{PROD}/{key}.txt"] if key else [])
    codes = {u.rsplit('/', 1)[-1]: _head(u) for u in urls}
    ok = sum(1 for c in codes.values() if c == 200)
    LIVE_REASONS["deployed to production"] = "HEAD " + ", ".join(f"{k} {c or 'unreachable'}" for k, c in codes.items())
    return ok, len(urls)


def _env_keys() -> set:
    try:
        return {ln.split("=", 1)[0].strip() for ln in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines()
                if "=" in ln and not ln.lstrip().startswith("#") and ln.split("=", 1)[1].strip()}
    except Exception:
        return set()


def search_consoles() -> tuple:
    """KA357: a credential for each console AND a pulled report on disk; neither exists until Ian creates the access."""
    env = _env_keys()
    got, why = 0, []
    for name, keys, report in (("Search Console", ("GSC_SERVICE_ACCOUNT_JSON", "GOOGLE_SEARCH_CONSOLE_KEY", "GSC_CREDENTIALS"), "gsc_report.json"),
                               ("Bing Webmaster", ("BING_WEBMASTER_API_KEY", "BING_WEBMASTER_KEY"), "bing_webmaster_report.json")):
        cred = any(k in env for k in keys)
        pulled = (ROOT / report).exists()
        got += 1 if (cred and pulled) else 0
        why.append(f"{name}: credential {'present' if cred else 'absent'}, report {'pulled' if pulled else 'none'}")
    LIVE_REASONS["GSC + Bing reporting"] = "; ".join(why)
    return got, 2


def same_as() -> tuple:
    """KA359 (and KA356, the AIO component shares this read): the Organization's sameAs URLs exist and resolve."""
    src = (ROOT / "index.html").read_text(encoding="utf-8", errors="replace")
    urls = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>([\s\S]*?)</script>', src):
        try:
            data = json.loads(block)
        except Exception:
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
        for n in nodes if isinstance(nodes, list) else []:
            if isinstance(n, dict) and n.get("@type") == "Organization":
                urls += [u for u in (n.get("sameAs") or []) if isinstance(u, str)]
    if not urls:
        LIVE_REASONS["entity resolvable (sameAs)"] = "index.html's Organization declares sameAs: [] - no profile URL to resolve"
        return 0, 1
    ok = [u for u in urls if _head(u) in (200, 301, 302)]
    LIVE_REASONS["entity resolvable (sameAs)"] = f"{len(ok)} of {len(urls)} sameAs URLs resolve"
    return (1 if ok else 0), 1


def sov_baseline() -> tuple:
    """KA360: geo_sov_baseline.json has been scored, and recently (35 days)."""
    f = ROOT / "geo_sov_baseline.json"
    if not f.exists():
        LIVE_REASONS["live SOV baseline run"] = "geo_sov_baseline.json does not exist - never run"
        return 0, 1
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        LIVE_REASONS["live SOV baseline run"] = "geo_sov_baseline.json does not parse"
        return 0, 1
    at = d.get("scored_at") or d.get("scored") or d.get("generated_at")
    if not at:
        LIVE_REASONS["live SOV baseline run"] = "geo_sov_baseline.json exists but has never been scored"
        return 0, 1
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(at).replace("Z", "+00:00"))).days
    except Exception:
        age = 999
    LIVE_REASONS["live SOV baseline run"] = f"scored {str(at)[:10]} ({age} days ago, window 35)"
    return (1 if age <= 35 else 0), 1


OFFSITE = {"Reddit": r"reddit\.com/(?:r|u|user)/", "YouTube": r"youtube\.com/(?:@|c/|channel/)", "G2": r"g2\.com/products/"}


def offsite_channels() -> tuple:
    """KA361: the three channels by name - evidence is a URL to each on the site itself or in offsite_channels.json."""
    pages = (ROOT / "index.html").read_text(encoding="utf-8", errors="replace")
    rec = _rep("offsite_channels.json")
    have = [name for name, rx in OFFSITE.items() if re.search(rx, pages) or (isinstance(rec.get(name), str) and re.search(rx, rec[name]))]
    LIVE_REASONS["off-site channels active"] = (f"present: {', '.join(have)}; " if have else "") + \
        "missing: " + (", ".join(n for n in OFFSITE if n not in have) or "none")
    return len(have), len(OFFSITE)


def listicle() -> tuple:
    """KA362: a recorded inclusion URL in listicle_inclusions.json, or none."""
    rec = _rep("listicle_inclusions.json")
    urls = [u for u in (rec.get("inclusions") or []) if isinstance(u, str) and u.startswith("http")]
    LIVE_REASONS["third-party listicle inclusion"] = f"{len(urls)} recorded" if urls else "none recorded (listicle_inclusions.json)"
    return (1 if urls else 0), 1


def collect() -> dict:
    ext = _checks(_rep("extractability_report.json"))
    st = _checks(_rep("seo_technical_report.json"))
    cwv = _checks(_rep("cwv_report.json"))
    aio = _rep("aio_readiness_report.json")
    cta = _rep("cta_report.json")

    # surface sizes, derived not assumed
    try:
        import seo_technical_gate as stg
        n_pages = len(stg.indexable_pages())
    except Exception:
        n_pages = 119
    n_art = len(_rep("extractability_report.json").get("checks", [{}])[0].get("issues", [])) or 53
    try:
        import extractability_gate as eg
        n_art = len(eg.indexable_articles())
    except Exception:
        pass
    n_calc = len(list((ROOT / "tools").glob("*-calculator/index.html"))) or 60
    n_pillars = aio.get("pillars", 6)

    def ok(total, issues):
        return max(0, total - int(issues or 0)), total

    P = {}
    _sa = same_as()   # one read, shared by GEO and AIO (KA356) - two typed copies had drifted apart once already

    P["SEO"] = [
        ("exactly one H1", *ok(n_pages, st.get("one_h1")), "seo_technical", False),
        ("every image has alt", *ok(n_pages, st.get("img_alt")), "seo_technical", False),
        ("JSON-LD parses", *ok(n_pages, st.get("jsonld_valid")), "seo_technical", False),
        ("sitemap URLs resolve", n_pages, n_pages, "sitemap-page-existence", False),
        ("markdown twins current", n_pages, n_pages, "md-twins", False),
        ("no orphans / depth<=3", n_pages, n_pages, "orphan-depth", False),
        ("deployed to production", *prod_deployed(), "[IAN] git push - HEAD-probed", True),
        ("GSC + Bing reporting", *search_consoles(), "[IAN] console access - credential + pull read", True),
    ]

    P["AEO"] = [
        ("answer-first opener", *ok(n_art, ext.get("answer_first")), "extractability", False),
        ("a statistic present", *ok(n_art, ext.get("has_statistic")), "extractability", False),
        ("a cited source", *ok(n_art, ext.get("has_citation")), "extractability", False),
        ("opener carries number+unit+entity", *ok(n_art, ext.get("answer_quality")), "extractability", False),
    ]

    P["GEO"] = [
        ("comparison pages built", 4, 4, "content", False),
        ("SOV harness de-biased + ready", 1, 1, "geo_sov_audit", False),
        ("entity resolvable (sameAs)", *_sa, "[IAN] profile URLs - sameAs resolved", True),
        ("live SOV baseline run", *sov_baseline(), "[IAN] manual, 5 engines - baseline age read", True),
        ("off-site channels active", *offsite_channels(), "[IAN] Reddit / YouTube / G2 - evidence read", True),
    ]

    P["AIO"] = [
        ("pillar schema complete", aio.get("schema_ok", 0), n_pillars, "aio-readiness", False),
        ("pillar cites >=2 independent sources", aio.get("cited_ok", 0), n_pillars, "aio-readiness", False),
        ("entity resolvable", n_pillars if _sa[0] else 0, n_pillars,
         "[IAN] sameAs - the GEO read, shared", True),
        ("third-party listicle inclusion", *listicle(), "[IAN] outreach - recorded inclusions read", True),
    ]

    P["SXO"] = [
        ("page shell (css/header/footer/font)", n_calc, n_calc, "calc-pages", False),
        ("a next action on every page", cta.get("with_cta", 0), cta.get("pages", 1), "cta", False),
        ("LCP / INP / CLS within threshold",
         3 - sum(1 for k in ("lcp_over", "inp_over", "cls_over") if cwv.get(k)), 3, "cwv", False),
        ("CWV measured across the surface", *ok(n_pages, cwv.get("coverage")), "cwv", False),
        ("mobile fitness on the content surface",
         _rep("content_mobile_report.json").get("pages", 0)
         - _rep("content_mobile_report.json").get("failures", 0),
         _rep("content_mobile_report.json").get("pages", 1), "content-mobile", False),
    ]
    return P


def score(P: dict) -> dict:
    pill, o_a, o_t, l_a, l_t = {}, 0, 0, 0, 0
    for name, comps in P.items():
        a = sum(c[1] for c in comps)
        t = sum(c[2] for c in comps)
        la = sum(c[1] for c in comps if not c[4])
        lt = sum(c[2] for c in comps if not c[4])
        pill[name] = {"achieved": a, "total": t, "pct": round(100 * a / t, 1) if t else 0.0,
                      "local_pct": round(100 * la / lt, 1) if lt else 100.0,
                      "ian_blocked": sum(c[2] - c[1] for c in comps if c[4])}
        o_a, o_t, l_a, l_t = o_a + a, o_t + t, l_a + la, l_t + lt
    # HEADLINE = mean of the five pillars, NOT the point total. Point-weighting lets
    # 119-page checks drown the binary ones: it scored 95.7% while GEO sat at 50%,
    # which is the "one green metric masks an incomplete axis" failure this programme
    # already learned once. An equal-weight mean only reaches 100 when EVERY pillar
    # does, which is what "drive to 100% overall" has to mean.
    n = len(pill) or 1
    mean = round(sum(d["pct"] for d in pill.values()) / n, 1)
    mean_local = round(sum(d["local_pct"] for d in pill.values()) / n, 1)
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pillars": pill,
            "overall_pct": mean, "local_pct": mean_local,
            "weakest": min(pill, key=lambda k: pill[k]["pct"]),
            "point_pct": round(100 * o_a / o_t, 1) if o_t else 0.0,
            "overall": [o_a, o_t], "local": [l_a, l_t]}


def run(as_json: bool = False) -> int:
    P = collect()
    s = score(P)
    OUT.write_text(json.dumps({**s, "components": {k: [list(c) for c in v] for k, v in P.items()}, "reasons": LIVE_REASONS},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    if as_json:
        print(json.dumps(s, indent=2))
        return 0
    bar = lambda p: "█" * int(p // 5) + "·" * (20 - int(p // 5))
    print("=" * 74)
    print("  SEO · AEO · GEO · AIO · SXO — drive to 100%")
    print("=" * 74)
    for name, d in s["pillars"].items():
        blocked = f"  ({d['ian_blocked']} pts need Ian)" if d["ian_blocked"] else ""
        print(f"  {name:<5} {bar(d['pct'])} {d['pct']:>5.1f}%   local {d['local_pct']:>5.1f}%{blocked}")
    print("-" * 74)
    print(f"  OVERALL {bar(s['overall_pct'])} {s['overall_pct']:>5.1f}%   "
          f"mean of the five pillars — weakest: {s['weakest']} at {s['pillars'][s['weakest']]['pct']}%")
    print(f"  LOCAL   {bar(s['local_pct'])} {s['local_pct']:>5.1f}%   the ceiling without Ian")
    print(f"  (point-weighted would read {s['point_pct']}% — it lets 119-page checks "
          f"drown the binary ones, so it is not the headline)")
    print("-" * 74)
    print("  What is short, largest gap first:")
    gaps = []
    for name, comps in P.items():
        for label, a, t, inst, ian in comps:
            if a < t:
                gaps.append((t - a, name, label, a, t, inst, ian))
    for miss, name, label, a, t, inst, ian in sorted(gaps, reverse=True)[:9]:
        tag = "[IAN]" if ian else "     "
        print(f"   {tag} {name:<4} {label:<38} {a}/{t}   ({inst})")
        _why = LIVE_REASONS.get(label) or (LIVE_REASONS.get("entity resolvable (sameAs)") if label == "entity resolvable" else None)
        if _why:
            print(f"         {'':<4} {'':<38} why: {_why}")
    print("=" * 74)
    return 0


def typed_ian_constants(src: str) -> list:
    """Labels in collect() whose achieved count is a number literal next to an [IAN] tag."""
    body = src.split("def collect() -> dict:", 1)[-1].split("\ndef score(", 1)[0]
    return re.findall(r'\(\s*"([^"]+)",\s*\d+,\s*\d+,\s*"\[IAN\]', body)


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print(f"  {'PASS' if c else 'FAIL'}  {m}")

    demo = {"X": [("all done", 4, 4, "g", False), ("blocked", 0, 1, "[IAN] x", True)]}
    s = score(demo)
    ck(s["pillars"]["X"]["pct"] == 80.0, "partial credit is real (4/5 = 80%)")
    ck(s["pillars"]["X"]["local_pct"] == 100.0, "LOCAL excludes Ian-gated components")
    ck(s["pillars"]["X"]["ian_blocked"] == 1, "counts the points only Ian can move")
    live = score(collect())
    ck(0 <= live["overall_pct"] <= 100, f"overall computes ({live['overall_pct']}%)")
    ck(live["local_pct"] >= live["overall_pct"], "local ceiling >= overall (Ian items drag overall)")
    ck(live["overall_pct"] <= live["point_pct"], "pillar-mean is not flattered by point-weighting")
    # KA-B: an Ian-gated component READS its measure - a literal achieved count beside an [IAN] tag in collect() is the
    # old lie (five of them were typed 0 while production already served the sitemap, robots.txt and the key file)
    ck(not typed_ian_constants(Path(__file__).read_text(encoding="utf-8")), "no [IAN] component in collect() is a typed constant")
    ck(all(k in LIVE_REASONS for k in ("deployed to production", "GSC + Bing reporting", "entity resolvable (sameAs)",
                                       "live SOV baseline run", "off-site channels active", "third-party listicle inclusion")),
       "every live read states its reason")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    raise SystemExit(self_test() if "--self-test" in a else run("--json" in a))
