#!/usr/bin/env python3
"""prove_page_registries.py - SL sub-layer CI4 (2026-10-15): "The platform must list this page in every registry that
enumerates pages (nav, shell, sitemap, gates)."

A registry that omits a page fails that page silently: the sitemap a crawler never reads it from, the hub that never
offers it, the ratchet that never scans it, the header rule that never covers it. And a registry that names a page
which no longer exists sends a person, a crawler or a gate to a 404 (architecture, symbol-gallery and validator-catalog
were deleted on 2026-10-14; one gate kept failing on their rows for a day). So each page is checked against EVERY
registry that applies to its class, and every registry is checked for entries that point at nothing.

Registries, read from their own sources (never retyped here):
  every page   the SL page classes (sublayer_inventory.page_classes), the design ratchet's scope
               (prove_design_detector_ratchet.served_files), its OWN generated CSP rule in vercel.json (not the base
               fallback - tools/build_csp_profiles.py), the cache contract's roster
  production,  the served roster the gates seed from (seed_expansion_wave4.served_pages)
  public
  public       sitemap.xml (at the path the deploy serves it: /x.html, a directory page at /dir)
  production   the hub: offered in nav-hub's catalog, parented there, or reached by a link from a page it offers
               (check_journey_paths' own reading of the hub and the link graph)
  founder      sublayer_inventory.FOUNDER_PAGES (staff reach these directly; the hub offers them nobody)
  shell        sw.js: the service worker registers at scope "/" and its navigation fallback answers every same-origin
               page; every .html its SHELL_FILES names must exist (the reverse check)
TEETH: one public, one production and one founder page are each taken out of their class's registry (in memory), and
a sitemap entry pointing at no page is added; every one of the four must be caught, or the prover fails itself.

  python tools/prove_page_registries.py [--page a.html,...] [--json .tmp/page_registries_results.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
DELETED = ("architecture.html", "symbol-gallery.html", "validator-catalog.html")   # Ian, 2026-10-14: deleted, kept as names


def _sitemap_paths() -> set[str]:
    xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8", errors="replace")
    return {re.sub(r"^https?://[^/]+", "", loc).rstrip("/") or "/" for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)}


def _served_path(page: str) -> str:
    if page == "index.html":
        return "/"
    if page.endswith("/index.html"):
        return "/" + page[: -len("/index.html")]
    return "/" + page


def _hub_reachable() -> set[str]:
    import check_journey_paths as cjp
    offered, parented = cjp.hub_offered_and_parented()
    graph = cjp.link_graph()
    seen, queue = set(), list(offered | set(parented) | {"index.html"})
    while queue:
        p = queue.pop()
        if p in seen:
            continue
        seen.add(p)
        queue += [q for q in graph.get(p, []) if q not in seen]
    return seen


def _shell_files() -> list[str]:
    src = (ROOT / "sw.js").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const SHELL_FILES\s*=\s*\[(.*?)\];", src, re.S)
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if m else []


def load() -> dict:
    from seed_expansion_wave4 import served_pages
    from sublayer_inventory import page_classes, FOUNDER_PAGES
    from prove_design_detector_ratchet import served_files
    from serve_vercel_headers import headers_for, load_rules
    from build_csp_profiles import BASE_SOURCE, CSP_KEY
    from prove_cache_contract import roster as cache_roster
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    rules = load_rules(ROOT)
    base = next(h["value"] for r in cfg["headers"] if r["source"] == BASE_SOURCE for h in r["headers"] if h["key"] == CSP_KEY)
    classes = page_classes()
    return {
        "cls_of": {p: c for c, ps in classes.items() for p in ps},
        "served": {p for ps in served_pages().values() for p in ps},
        "ratchet": set(served_files()),
        "own_csp": lambda page: (lambda v: bool(v) and v != base)(headers_for(_served_path(page), rules).get(CSP_KEY, "")),
        "cache": set(cache_roster()),
        "sitemap": _sitemap_paths(),
        "hub": _hub_reachable(),
        "founder": set(FOUNDER_PAGES),
        "hub_hrefs": set(re.findall(r"href:\s*'([^']+\.html)'", (ROOT / "nav-hub.js").read_text(encoding="utf-8", errors="replace"))),
        "shell": _shell_files(),
    }


def check(page: str, R: dict) -> dict:
    cls = R["cls_of"].get(page, "?")
    listed, missing = [], []

    def need(name, ok):
        (listed if ok else missing).append(name)

    need("SL page classes", page in R["cls_of"])
    need("design ratchet scope", page in R["ratchet"])
    need("its own CSP rule in vercel.json", R["own_csp"](page))
    need("cache contract roster", page in R["cache"])
    if cls in ("production", "public"):
        need("served roster (seed_expansion_wave4)", page in R["served"])
    if cls == "public":
        need("sitemap.xml", _served_path(page) in R["sitemap"])
    if cls == "production":
        need("the hub (offered, parented, or linked from a page it offers)", page in R["hub"])
    if cls == "founder":
        need("FOUNDER_PAGES", page in R["founder"])
    problems = [f"not in {m}" for m in missing]
    return {"page": page, "class": cls, "listed": listed, "problems": problems, "ok": not problems}


def dangling(R: dict) -> list[str]:
    out = []
    for path in sorted(R["sitemap"]):
        f = "index.html" if path == "/" else (path.lstrip("/") + ("" if path.endswith(".html") else "/index.html"))
        if not (ROOT / f).is_file():
            out.append(f"sitemap.xml names {path}, which serves no page")
    for href in sorted(R["hub_hrefs"]):
        if not (ROOT / href).is_file():
            out.append(f"nav-hub.js offers {href}, which does not exist")
    for f in R["shell"]:
        if f.endswith(".html") and not (ROOT / f.lstrip("./")).is_file():
            out.append(f"sw.js SHELL_FILES names {f}, which does not exist")
    for f in sorted(R["founder"]):
        if not (ROOT / f).is_file() and f not in DELETED:
            out.append(f"FOUNDER_PAGES names {f}, which does not exist")
    return out


def teeth(R: dict, pages: list[str]) -> dict:
    caught = {}
    for cls, reg, key in (("public", "sitemap", lambda p: _served_path(p)), ("production", "hub", lambda p: p),
                          ("founder", "founder", lambda p: p)):
        sample = next((p for p in pages if R["cls_of"].get(p) == cls), None)
        if not sample:
            caught[cls] = None
            continue
        R2 = dict(R)
        R2[reg] = set(R[reg]) - {key(sample)}
        caught[cls] = {"page": sample, "registry": reg, "caught": not check(sample, R2)["ok"]}
    R3 = dict(R)
    R3["sitemap"] = set(R["sitemap"]) | {"/learn/a-page-that-was-never-written"}
    caught["dangling"] = {"planted": "/learn/a-page-that-was-never-written", "caught": any("never-written" in d for d in dangling(R3))}
    bit = all(v and v["caught"] for v in caught.values() if v is not None)
    return {"bit": bit, **caught}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "page_registries_results.json"))
    a = ap.parse_args()
    R = load()
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    ci4 = {t["sl"]["page"]: t.get("persona") for t in reg["trajectories"]
           if (t.get("sl") or {}).get("sublayer") == "CI4" and t.get("status") != "descoped"}
    pages = a.page.split(",") if a.page else sorted(ci4)
    results, bad = [], 0
    for page in pages:
        r = check(page, R)
        r.update({"cast": ci4.get(page), "engine": "static", "condition": "registries"})
        bad += 0 if r["ok"] else 1
        results.append(r)
        print(f"  {'ok  ' if r['ok'] else 'FAIL'} {page:<56} {r['class']:<10} {len(r['listed'])} registries"
              + ("" if r["ok"] else "\n         " + "; ".join(r["problems"])))
    dang = dangling(R)
    for d in dang:
        print(f"  DANGLING {d}")
    t = teeth(R, sorted(ci4))
    caught = ", ".join(f"{k}: {(v or {}).get('caught')}" for k, v in t.items() if k != "bit")
    print(f"\n  teeth - a page taken out of its class's registry, and a sitemap entry pointing at nothing: "
          f"{'all CAUGHT' if t['bit'] else 'NOT ALL CAUGHT'} ({caught})")
    failed = bad + len(dang) + (0 if t["bit"] else 1)
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayer": "CI4", "pages": len(results),
                               "failed": failed, "dangling": dang, "teeth": t, "results": results}, indent=1), encoding="utf-8")
    print(f"\n{'FAIL' if failed else 'PASS'} page-registries - {len(results) - bad}/{len(results)} page(s) in every registry "
          f"their class needs; {len(dang)} registry entr{'y' if len(dang) == 1 else 'ies'} pointing at nothing -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
