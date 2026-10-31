#!/usr/bin/env python3
"""prove_cache_contract.py - SL sub-layers CA2 and H2 (2026-10-15): every page, and every asset it loads, is served the
cache header its class needs - HTML fresh, scripts and stylesheets revalidated with a validator, images long-lived -
at the edge and locally alike.

WHAT IT WALKS. Every page of the CA2/H2 roster, over HTTP against tools/serve_vercel_headers.py (the local substitute
for the Vercel edge: vercel.json's own rules, every match in order, later keys winning), at EVERY path a person reaches
it by: /x.html, and for a directory page the path the deploy serves it at (vercel.json trailingSlash) as well as
/dir/index.html. Then every local asset the page loads - every script in its code closure (build_csp_profiles'
reading: its HTML and every script it loads, transitively), every stylesheet and image its HTML names - and sw.js.

THE CONTRACT, by class (the one vercel.json states):
  HTML              max-age=0 + must-revalidate (a page is never served stale after a deploy)
  script, style     max-age=0 + must-revalidate AND a validator (ETag or Last-Modified), so revalidating is a 304 and
                    never a re-download - the scripts are not content-hashed (2026-10-14: an hour-long max-age let a
                    phone run a new page with its old utils.js for an hour after every deploy)
  image, icon       max-age=31536000 + immutable
  sw.js             no-store

"LOCALLY ALIKE". The local half is the edge substitute above, which serves vercel.json's rules exactly. The dev
seeder on :5000 is a rewriting test proxy that answers no-store for everything (fresher than every class's contract,
never stale) and is not a surface a person is served from; it is not the local half of this contract.

TEETH, judged by the same code against two other policies: vercel.json at the last commit before the directory-page
rule (every directory page then had NO cache header at its served path - its freshness rested on a platform default
the config never stated), and today's vercel.json with the script rule put back to an hour (the 2026-10-14 incident).
Both must fail, or this prover cannot tell a contract kept from one broken.

  python tools/prove_cache_contract.py [--page a.html,...] [--json .tmp/cache_contract_results.json] [--no-teeth]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prove_deploy_headers import PORT, head, listening  # noqa: E402
from serve_vercel_headers import headers_for, load_rules  # noqa: E402
from build_csp_profiles import code_closure  # noqa: E402

TEETH_COMMIT = "a8ffe363"
_CSS = re.compile(r"""<link\b[^>]*\bhref=["']([^"'?#]+\.css)""", re.I)
_IMG = re.compile(r"""(?:src|href)=["']([^"'?#]+\.(?:png|svg|ico|webp|jpg|jpeg))""", re.I)


def classify(path: str) -> str:
    p = path.split("?", 1)[0].lower()
    if p.endswith("/sw.js"):
        return "sw"
    if p.endswith((".js", ".mjs", ".css")):
        return "code"
    if p.endswith((".png", ".svg", ".ico", ".webp", ".jpg", ".jpeg", ".woff2")):
        return "image"
    return "html"


def contract_problem(cls: str, cc: str) -> str | None:
    cc = (cc or "").lower()
    if cls == "html" and not ("max-age=0" in cc and "must-revalidate" in cc):
        return f"HTML Cache-Control '{cc or '(none)'}' - expected max-age=0, must-revalidate"
    if cls == "code" and not ("max-age=0" in cc and "must-revalidate" in cc):
        return f"script/style Cache-Control '{cc or '(none)'}' - expected max-age=0, must-revalidate (not content-hashed)"
    if cls == "image" and not ("max-age=31536000" in cc and "immutable" in cc):
        return f"image Cache-Control '{cc or '(none)'}' - expected a year, immutable"
    if cls == "sw" and "no-store" not in cc:
        return f"sw.js Cache-Control '{cc or '(none)'}' - expected no-store"
    return None


def _trailing():
    """vercel.json's trailingSlash - it decides the path a directory page is SERVED at."""
    try:
        return json.loads((Path(__file__).resolve().parent.parent / "vercel.json").read_text(encoding="utf-8")).get("trailingSlash")
    except (OSError, ValueError):
        return None


def page_paths(page: str) -> list[str]:
    # a directory page is served at /dir/ with trailingSlash true (2026-10-30: the canonicals, og:url, JSON-LD @id and
    # the sitemap all name the slash form), at /dir with false, at both when unset
    if page.endswith("/index.html"):
        d = "/" + page[: -len("/index.html")]
        t = _trailing()
        served = [d + "/"] if t is True else [d] if t is False else [d, d + "/"]
        return served + [d + "/index.html"]
    return ["/" + page]


def asset_paths(page: str) -> list[str]:
    html = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    base = "/" + page.rsplit("/", 1)[0] + "/" if "/" in page else "/"
    refs = set()
    for f in code_closure(page)[1:]:
        refs.add("/" + str(f.relative_to(ROOT)).replace("\\", "/"))
    for r in _CSS.findall(html) + _IMG.findall(html):
        if r.startswith(("http://", "https://", "//", "data:")):
            continue
        refs.add(r if r.startswith("/") else (base + r).replace("//", "/"))
    return sorted(p for p in refs if (ROOT / p.lstrip("/")).is_file())


def judge(page: str, rules: list, over_http: bool) -> dict:
    problems, checked = [], []
    for path in page_paths(page) + asset_paths(page) + ["/sw.js"]:
        cls = classify(path)
        cc = headers_for(path, rules).get("Cache-Control", "")
        bad = contract_problem(cls, cc)
        if bad:
            problems.append(f"{path}: {bad}")
        if over_http and not (cls == "html" and not path.endswith(".html")):
            st, h, _ = head(path)        # a clean directory path is the edge's redirect target; its file form is fetched
            if st != 200:
                problems.append(f"{path}: HTTP {st}")
            elif h.get("cache-control", "") != cc:
                problems.append(f"{path}: the server sent '{h.get('cache-control')}' where vercel.json says '{cc}'")
            elif cls == "code" and not (h.get("etag") or h.get("last-modified")):
                problems.append(f"{path}: no ETag or Last-Modified, so revalidating would re-download it")
        checked.append((path, cls))
    by = {c: sum(1 for _p, k in checked if k == c) for c in ("html", "code", "image", "sw")}
    return {"page": page, "checked": by, "problems": problems, "ok": not problems}


def roster() -> dict[str, str]:
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    out = {}
    for t in reg["trajectories"]:
        s = t.get("sl") or {}
        if s.get("sublayer") in ("CA2", "H2") and t.get("status") != "descoped":
            out.setdefault(s["page"], t.get("persona"))
    return out


def teeth(pages: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        old = subprocess.run(["git", "show", f"{TEETH_COMMIT}:vercel.json"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8").stdout
        (Path(d) / "vercel.json").write_text(old, encoding="utf-8")
        old_rules = load_rules(Path(d))
        cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        for r in cfg["headers"]:
            if r["source"] == "/(.*).(js|css)":
                for h in r["headers"]:
                    if h["key"] == "Cache-Control":
                        h["value"] = "public, max-age=3600"
        (Path(d) / "vercel.json").write_text(json.dumps(cfg), encoding="utf-8")
        hour_rules = load_rules(Path(d))
    dirs = [p for p in pages if p.endswith("/index.html")]
    a = [p for p in dirs if not judge(p, old_rules, False)["ok"]]
    b = [p for p in pages if not judge(p, hour_rules, False)["ok"]]
    return {"commit": TEETH_COMMIT, "directory_pages": len(dirs), "failed_under_commit": len(a),
            "pages": len(pages), "failed_with_hour_scripts": len(b),
            "bit": bool(dirs) and len(a) == len(dirs) and len(b) == len(pages)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "cache_contract_results.json"))
    ap.add_argument("--no-teeth", action="store_true")
    a = ap.parse_args()
    cast = roster()
    pages = a.page.split(",") if a.page else sorted(cast)
    started = None
    if not listening():
        started = subprocess.Popen([sys.executable, str(ROOT / "tools" / "serve_vercel_headers.py"), "--port", str(PORT)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if listening():
                break
            time.sleep(0.25)
    rules = load_rules(ROOT)
    results = []
    try:
        for p in pages:
            r = judge(p, rules, True)
            r.update({"engine": "http", "condition": "as-served", "cast": cast.get(p)})
            results.append(r)
            c = r["checked"]
            print(f"  {'ok  ' if r['ok'] else 'FAIL'} {p:<52} html {c['html']} code {c['code']} image {c['image']}"
                  + ("" if r["ok"] else "\n         " + "\n         ".join(r["problems"][:4])))
    finally:
        if started:
            started.terminate()
    t = None if a.no_teeth else teeth(pages)
    if t:
        print(f"\n  teeth - under {t['commit']}'s vercel.json {t['failed_under_commit']}/{t['directory_pages']} directory page(s) "
              f"had no cache header at their served path; with scripts cached an hour {t['failed_with_hour_scripts']}/{t['pages']} "
              f"page(s) fail: {'BIT' if t['bit'] else 'DID NOT BITE'}")
    failed = sum(1 for r in results if not r["ok"]) + (1 if t and not t["bit"] else 0)
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayers": ["CA2", "H2"],
                               "served_by": "tools/serve_vercel_headers.py (vercel.json applied locally)",
                               "pages": len(results), "failed": failed, "teeth": t, "results": results}, indent=1),
                   encoding="utf-8")
    print(f"\n{'FAIL' if failed else 'PASS'} cache-contract - {len(results) - sum(1 for r in results if not r['ok'])}/"
          f"{len(results)} page(s) and every asset they load carry their class's cache header -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
