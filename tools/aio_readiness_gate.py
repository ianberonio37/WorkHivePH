"""
aio_readiness_gate.py — the AIO pillar's instrument (SEO_AEO_GEO_V3 §5).
========================================================================
AIO is Google's AI Overview / Bing Copilot surface, split out from GEO in V3
because the levers differ. Three of its four are already built (topical authority,
semantic relevance, entity optimisation-pending). The fourth — **multi-source
credibility** — is the one our own pages cannot supply, and nothing measured it.

WHAT IT MEASURES, per cluster pillar:
  pillar_exists      the hub page is on disk
  schema_complete    Article + FAQPage + BreadcrumbList in its JSON-LD
  external_cited     >= 2 INDEPENDENT external domains, LINKED (not merely named)
  entity_resolvable  the homepage Organization carries a non-empty sameAs

WHY "LINKED, NOT NAMED" IS THE BAR: at first run every pillar named standards
bodies in prose (SMRP, ISO, DOE, NFPA) and linked **zero** of them. A claim that
says "per SMRP" with no destination cannot be verified by a reader or corroborated
by an engine — an AI Overview assembles agreeing INDEPENDENT sources, and a cluster
whose every link points back to workhiveph.com reads as one unverified source.

RATCHETED, not pass/fail-on-day-one. The honest initial state is mostly failing,
and a permanently-red gate teaches everyone to ignore it (feedback_red_gate_may_be
_inaccuracy_not_backlog). So it records today's score and fails only on REGRESSION,
while printing the distance to done in full.

CLI:
    python tools/aio_readiness_gate.py
    python tools/aio_readiness_gate.py --self-test
    python tools/aio_readiness_gate.py --update-baseline
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
BASELINE = ROOT / "aio_readiness_baseline.json"
REPORT = ROOT / "aio_readiness_report.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# The cluster hubs. A pillar is where an AI Overview looks for the topical answer.
PILLARS = [
    "maintenance-metrics-reliability-guide",
    "start-digital-maintenance-guide",
    "ph-plant-compliance-guide",
    "reduce-unplanned-downtime-guide",
    "free-engineering-calculators-philippine-plants",
    "what-is-workhive-complete-platform-guide",
]

MIN_EXTERNAL = 2

# infrastructure/CDN hosts are not citations
_NOT_A_SOURCE = ("workhiveph", "schema.org", "fonts.googleapis", "fonts.gstatic",
                 "cdn.tailwindcss", "googletagmanager", "google-analytics")


def external_domains(html: str) -> set[str]:
    """Independent domains this page LINKS to (a named source with no href is not one)."""
    out = set()
    for href in re.findall(r'href="(https?://[^"]+)"', html):
        dom = href.split("//", 1)[1].split("/", 1)[0].lower()
        dom = dom[4:] if dom.startswith("www.") else dom
        if not any(x in dom for x in _NOT_A_SOURCE):
            out.add(dom)
    return out


def entity_resolvable() -> bool:
    """The homepage Organization must carry a non-empty sameAs — entity resolution
    runs BEFORE content retrieval, so an unresolvable brand is not citable at all."""
    idx = ROOT / "index.html"
    if not idx.exists():
        return False
    t = idx.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'"sameAs"\s*:\s*\[(.*?)\]', t, re.S)
    return bool(m and re.search(r'https?://', m.group(1)))


def audit() -> dict:
    ent = entity_resolvable()
    rows = []
    for slug in PILLARS:
        f = ROOT / "learn" / slug / "index.html"
        if not f.exists():
            rows.append({"pillar": slug, "pillar_exists": False, "schema_complete": False,
                         "external_cited": 0, "entity_resolvable": ent, "ready": False})
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        types = set(re.findall(r'"@type":\s*"(\w+)"', t))
        schema_ok = {"Article", "FAQPage", "BreadcrumbList"} <= types
        ext = external_domains(t)
        row = {"pillar": slug, "pillar_exists": True, "schema_complete": schema_ok,
               "external_cited": len(ext), "external_domains": sorted(ext)[:6],
               "entity_resolvable": ent}
        row["ready"] = bool(schema_ok and len(ext) >= MIN_EXTERNAL and ent)
        rows.append(row)
    ready = sum(1 for r in rows if r["ready"])
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pillars": len(rows), "ready": ready,
            "entity_resolvable": ent,
            "cited_ok": sum(1 for r in rows if r["external_cited"] >= MIN_EXTERNAL),
            "schema_ok": sum(1 for r in rows if r["schema_complete"]),
            "rows": rows}


def run() -> int:
    rep = audit()
    REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    prior = base.get("ready", rep["ready"])
    regressed = rep["ready"] < prior

    print("=" * 66)
    print("  AIO READINESS — AI Overview / Copilot (V3 §5)")
    print("=" * 66)
    print(f"  pillars ready: {rep['ready']}/{rep['pillars']}   (baseline {prior})")
    print(f"    schema complete            {rep['schema_ok']}/{rep['pillars']}")
    print(f"    >= {MIN_EXTERNAL} independent sources LINKED  {rep['cited_ok']}/{rep['pillars']}")
    print(f"    entity resolvable (sameAs) {'yes' if rep['entity_resolvable'] else 'NO — blocks every pillar'}")
    print("-" * 66)
    for r in rep["rows"]:
        flag = "READY" if r["ready"] else "    ."
        why = []
        if not r["pillar_exists"]:
            why.append("missing")
        else:
            if not r["schema_complete"]:
                why.append("schema")
            if r["external_cited"] < MIN_EXTERNAL:
                why.append(f"cites {r['external_cited']}/{MIN_EXTERNAL} external")
            if not r["entity_resolvable"]:
                why.append("no sameAs")
        print(f"  {flag}  {r['pillar'][:46]:48s} {'· '.join(why)}")
    print("=" * 66)
    if regressed:
        print(f"  FAIL — readiness fell {prior} -> {rep['ready']}")
        return 1
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"ready": rep["ready"],
                                        "established": rep["generated_at"]}, indent=2), encoding="utf-8")
        print(f"  baseline established at {rep['ready']}/{rep['pillars']} — forward-only from here.")
    else:
        BASELINE.write_text(json.dumps({"ready": max(prior, rep["ready"]),
                                        "established": base.get("established", rep["generated_at"])},
                                       indent=2), encoding="utf-8")
        print("  PASS — no regression.")
    if rep["ready"] < rep["pillars"]:
        print(f"  Distance to done: {rep['pillars'] - rep['ready']} pillar(s). "
              f"Multi-source credibility is the lever our own pages cannot supply (V3 §5.1).")
    return 0


def self_test() -> int:
    ok = True

    def ck(c, label):
        nonlocal ok
        ok &= bool(c)
        print(f"  {'PASS' if c else 'FAIL'}  {label}")

    ck(external_domains('<a href="https://smrp.org/x">SMRP</a>') == {"smrp.org"},
       "a linked external domain counts")
    ck(external_domains('<a href="https://www.iso.org/a">ISO</a>') == {"iso.org"},
       "www. is normalised")
    ck(external_domains('<a href="https://workhiveph.com/learn/">self</a>') == set(),
       "our own domain is not an independent source")
    ck(external_domains('<a href="https://cdn.tailwindcss.com">x</a>') == set(),
       "CDN/infrastructure hosts are not citations")
    ck(external_domains("<p>Per SMRP and ISO 14224.</p>") == set(),
       "a source NAMED in prose but not linked does not count — the whole point")
    ck(external_domains('<a href="https://a.org/1">a</a><a href="https://a.org/2">b</a>') == {"a.org"},
       "two links to one domain is one independent source")
    rep = audit()
    ck(rep["pillars"] == len(PILLARS), f"audits every pillar ({rep['pillars']})")
    ck(all("ready" in r for r in rep["rows"]), "every row carries a verdict")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        raise SystemExit(self_test())
    if "--update-baseline" in a:
        r = audit()
        BASELINE.write_text(json.dumps({"ready": r["ready"], "established": r["generated_at"]}, indent=2),
                            encoding="utf-8")
        print(f"baseline set to {r['ready']}/{r['pillars']}")
        raise SystemExit(0)
    raise SystemExit(run())
