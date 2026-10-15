#!/usr/bin/env python3
"""build_csp_profiles.py - SL sub-layer S3 (2026-10-15): every served page gets a CSP naming exactly the origins its
own code can reach, sockets included, and nothing more.

WHY. vercel.json shipped ONE policy for every page: the union of every origin any page needs. So the landing page
named the chart library only analytics loads, every calculator named the PDF service only engineering-design calls,
and `img-src https:` named every origin on the internet - while the images the product shows come from four places
('self', data:, blob: and the project's own storage). A policy that names more than the page loads is not a policy
for that page.

HOW. The base rule's policy (`/(.*)` in vercel.json) stays the UNIVERSE: the generator never invents an origin, it
narrows the universe per page to the origins that page's code uses, in the directive it uses them through.
  - a page's code = its HTML plus every local script it loads, transitively: a <script src>, an import, and any quoted
    literal naming a local .js file (how nav-hub injects the companion, how marketplace loads the map). Over-including
    a script only widens a page's policy back toward the universe, which is the safe direction - a missed script is a
    production outage, the class csp-covers-what-ships records five times. A service worker is not page code (it runs
    under its own response's policy).
  - a host is kept in a directive only when the code loads it THAT way: a <script src> or a .js URL for script-src, a
    stylesheet for style-src, an API base or a fetch for connect-src, the socket form only when the code can open a
    socket; a library's own dependents follow it (gtag.js reports to Google Analytics' collectors, a Google Fonts
    stylesheet loads its faces from fonts.gstatic.com, Turnstile's script draws its challenge in an iframe).
  - a scheme wildcard (`https:`) is never "exactly": img-src's stood for the project's storage images, so it is
    replaced by that origin, for the pages whose code touches storage.
  - a page the live measurement (tools/prove_csp_exact.mjs --measure) saw load an origin its code read missed gets it
    too, and is reported: covering a missed path beats breaking it.
Pages with identical policies are grouped into one rule, written after every other rule so it wins (vercel.json
applies every match in order, later keys winning); the base rule stays for any page the roster does not hold.

  python tools/build_csp_profiles.py              # report the profiles, write nothing
  python tools/build_csp_profiles.py --write      # rewrite vercel.json's generated CSP rules
  python tools/build_csp_profiles.py --check      # the gate: vercel.json's rules equal what the code needs today
  python tools/build_csp_profiles.py --json PATH  # per-page policy and evidence, for the S3 prover
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
VERCEL = ROOT / "vercel.json"
MEASURE = ROOT / ".tmp" / "csp_exact_measure.json"
BASE_SOURCE = "/(.*)"
CSP_KEY = "Content-Security-Policy"
SOURCE_MAX = 900
WILDCARDS = {"https:", "http:", "*", "wss:", "ws:"}
SOCKET_USE = re.compile(r"\.channel\(|new WebSocket\(")
_JS_LITERAL = re.compile(r"""['"`]((?:\.{0,2}/)?[\w./-]+?\.m?js)(?:\?[^'"`]*)?['"`]""")
_SCRIPT_SRC = re.compile(r"""<script\b[^>]*\bsrc=["']([^"']+)["']""", re.I)
_IMPORT = re.compile(r"""(?:from|import)\s*\(?\s*['"]([^'"]+\.m?js)['"]""")
# a service worker runs under its own response's policy, not the page's: its file is not page code
NOT_PAGE_CODE = {"sw.js"}

# How the code USES a host decides the directive that must name it - a host is never kept in a directive the code does
# not load it through (the universe names fonts.googleapis.com in script-src too, and no page loads a script from it).
_USE = {
    "script-src": (r"""<script\b[^>]*\bsrc=["']https://{h}""", r"""["'`]https://{h}/[^"'`\s]*\.m?js\b""",
                   r"""loadScript\(\s*["'`]https://{h}"""),
    "style-src": (r"""<link\b[^>]*\bhref=["']https://{h}""", r"""@import\s+(?:url\()?["']?https://{h}""",
                  r"""["'`]https://{h}/[^"'`\s]*\.css\b"""),
    "frame-src": (r"""<iframe\b[^>]*\bsrc=["']https://{h}""",),
    "img-src": (r"""<img\b[^>]*\bsrc=["']https://{h}""",),
    "font-src": (r"""url\(\s*["']?https://{h}[^)]*\.(?:woff2?|ttf|otf)""",),
}
# connect-src: an https literal of the host that is an API base or a fetch, or its socket form
_CONNECT = r"""["'`]https://{h}(?:/[^"'`\s]*)?["'`]|fetch\(\s*["'`]https://{h}|wss://{h}"""
# a library's own dependents, by the directive it was loaded through: what it reaches that no page's code names
DEPENDENT_USE = {
    ("script-src", "www.googletagmanager.com"): [("connect-src", "https://www.google-analytics.com"),
                                                 ("connect-src", "https://analytics.google.com"),
                                                 ("connect-src", "https://www.googletagmanager.com"),
                                                 ("img-src", "https://www.googletagmanager.com")],
    ("style-src", "fonts.googleapis.com"): [("font-src", "https://fonts.gstatic.com")],
    ("script-src", "challenges.cloudflare.com"): [("frame-src", "https://challenges.cloudflare.com")],
}
# the project's storage serves the images and recordings a page shows; a page that never touches storage names neither
_STORAGE = re.compile(r"\.storage\s*\.\s*from\(|/storage/v1/|getPublicUrl")


def parse_csp(value: str) -> list[tuple[str, list[str]]]:
    out = []
    for part in value.split(";"):
        bits = part.split()
        if bits:
            out.append((bits[0], bits[1:]))
    return out


def serialize(dirs: list[tuple[str, list[str]]]) -> str:
    return "; ".join((d + " " + " ".join(s)).strip() for d, s in dirs)


def load_vercel() -> dict:
    return json.loads(VERCEL.read_text(encoding="utf-8"))


def universe(cfg: dict) -> list[tuple[str, list[str]]]:
    for rule in cfg["headers"]:
        if rule["source"] == BASE_SOURCE:
            for h in rule["headers"]:
                if h["key"] == CSP_KEY:
                    return parse_csp(h["value"])
    raise SystemExit("vercel.json has no base CSP rule")


def served_pages() -> list[str]:
    """Every page the deploy ships a person to: the served roster, plus the SL program's own classes (production,
    founder, public) - the founder surfaces are served too, and five of them carry S3 rows the served roster omits."""
    sys.path.insert(0, str(ROOT / "tools"))
    from seed_expansion_wave4 import served_pages as sp  # noqa: E402
    from sublayer_inventory import page_classes            # noqa: E402
    pages = {p for cls in sp().values() for p in cls} | {p for cls in page_classes().values() for p in cls}
    return sorted(p for p in pages if (ROOT / p).is_file())


def _resolve(ref: str, base_dir: Path) -> Path | None:
    ref = ref.split("?", 1)[0].split("#", 1)[0]
    if ref.startswith(("http://", "https://", "//", "data:", "blob:")):
        return None
    cands = [ROOT / ref.lstrip("/")] if ref.startswith("/") else [base_dir / ref, ROOT / ref]
    for cand in cands:
        try:
            c = cand.resolve()
        except OSError:
            continue
        if c.is_file() and ROOT in c.parents:
            return c
    return None


def code_closure(page: str) -> list[Path]:
    start = ROOT / page
    seen: list[Path] = []
    queue = [start]
    while queue:
        f = queue.pop()
        if f in seen or not f.is_file():
            continue
        seen.append(f)
        text = f.read_text(encoding="utf-8", errors="replace")
        refs = set(_SCRIPT_SRC.findall(text)) | set(_IMPORT.findall(text)) | set(_JS_LITERAL.findall(text))
        for r in refs:
            p = _resolve(r, f.parent)
            if p is not None and p.suffix in (".js", ".mjs") and p not in seen and p.name not in NOT_PAGE_CODE:
                queue.append(p)
    return seen


def measured() -> dict[str, dict[str, list[str]]]:
    if not MEASURE.exists():
        return {}
    d = json.loads(MEASURE.read_text(encoding="utf-8"))
    return {r["page"]: r.get("used") or {} for r in d.get("results", [])}


def _attribute(need: set, files: list[Path], project: str) -> dict[str, str]:
    """Why each origin is in the page's policy, named: the first file whose code loads it that way, or the library it
    follows. This is the receipt for "nothing more": an origin with no basis would not be there."""
    texts = [(str(f.relative_to(ROOT)).replace("\\", "/"), f.read_text(encoding="utf-8", errors="replace")) for f in files]
    dep_of = {x: f"{d.replace('-src', '')} {h}" for (d, h), deps in DEPENDENT_USE.items() for x in deps}
    out = {}
    for d, s in sorted(need):
        host = re.escape(urlparse(s).netloc)
        pats = [_CONNECT] if d in ("connect-src", "media-src") else list(_USE.get(d, ()))
        hit = next((name for name, t in texts for rx in pats if re.search(rx.format(h=host), t, re.I)), None)
        if s.startswith("wss://"):
            opener = next((name for name, t in texts if "vendor/" not in name and SOCKET_USE.search(t)), None)
            out[f"{d} {s}"] = f"a realtime channel the page's code opens ({opener})"
            continue
        if (d, s) in dep_of and not hit:
            out[f"{d} {s}"] = f"loaded by the library it follows ({dep_of[(d, s)]})"
        elif d in ("img-src", "media-src") and urlparse(s).netloc == project:
            out[f"{d} {s}"] = "the project's storage, which this page's code reads and writes (storage.from / getPublicUrl)"
        else:
            out[f"{d} {s}"] = f"{hit}" if hit else "measured live"
    return out


def policy_for(page: str, uni: list[tuple[str, list[str]]], seen_live: dict) -> tuple[str, dict]:
    files = code_closure(page)
    text = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
    project = next((urlparse(s).netloc for d, srcs in uni if d == "connect-src" for s in srcs if s.startswith("wss://")), "")
    # a socket is opened by the PRODUCT's code (a realtime channel); the bundled client library always carries the
    # realtime code, so reading it would give every page that loads supabase-js a socket it never opens
    own = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files if "vendor" not in f.parts)
    sockets = bool(SOCKET_USE.search(own))
    storage = bool(_STORAGE.search(text))
    named = {(d, s) for d, srcs in uni for s in srcs}
    need: set[tuple[str, str]] = set()
    for d, srcs in uni:
        for s in srcs:
            if "://" not in s:
                continue
            host = urlparse(s).netloc
            h = re.escape(host)
            if s.startswith("wss://"):
                if sockets and re.search(_CONNECT.format(h=h), text):
                    need.add((d, s))
            elif d == "connect-src":
                if re.search(_CONNECT.format(h=h), text):
                    need.add((d, s))
            elif d == "media-src":
                if host == project and storage and re.search(_CONNECT.format(h=h), text):
                    need.add((d, s))
            elif d in _USE and any(re.search(rx.format(h=h), text, re.I) for rx in _USE[d]):
                need.add((d, s))
    for (d, host), deps in DEPENDENT_USE.items():
        if (d, "https://" + host) in need:
            need |= {x for x in deps if x in named}
    if project and storage and ("connect-src", "https://" + project) in need:
        need.add(("img-src", "https://" + project))       # the wildcard img-src stood for these storage images
    evidence: dict = {"files": [str(f.relative_to(ROOT)).replace("\\", "/") for f in files], "measured_only": []}
    for d, origins in seen_live.get(page, {}).items():
        for o in origins:
            if o in ("'self'", "data:", "blob:") or (d, o) in need:
                continue
            if (d, o) in named or (d == "img-src" and o == "https://" + project):
                need.add((d, o))
                evidence["measured_only"].append(f"{d} {o}")
            else:
                evidence.setdefault("not_in_universe", []).append(f"{d} {o}")
    evidence["basis"] = _attribute(need, files, project)
    for m in evidence["measured_only"]:
        evidence["basis"][m] = "measured live (the page loaded it; its code read did not show the path)"
    out = []
    for d, srcs in uni:
        keep = [s for s in srcs if "://" not in s and s not in WILDCARDS]   # 'self', 'unsafe-inline', data:, blob:
        keep += [s for s in srcs if "://" in s and (d, s) in need]
        if d == "img-src" and ("img-src", "https://" + project) in need and "https://" + project not in keep:
            keep.append("https://" + project)
        if not keep:
            keep = ["'none'"]
        out.append((d, keep))
    return serialize(out), evidence


def _source_for(pages: list[str]) -> list[str]:
    """Request paths a page is served at (cleanUrls false: /x.html; a directory page also at /dir and /dir/), grouped
    the way this vercel.json already ships them: one group with alternation."""
    alts = []
    for p in pages:
        if p == "index.html":
            continue
        alts.append(p)
        if p.endswith("/index.html"):
            d = p[: -len("/index.html")]
            alts += [d, d + "/"]
    # Vercel caps a `source` string's length (its config schema; a rule over it fails the deploy), and 60 calculators
    # x 3 request paths ran to 8,135 characters - so a group is split into rules of at most SOURCE_MAX, same policy.
    srcs, cur = [], []
    for alt in alts:
        if cur and len("/(" + "|".join(cur + [alt]) + ")") > SOURCE_MAX:
            srcs.append("/(" + "|".join(cur) + ")")
            cur = []
        cur.append(alt)
    if cur:
        srcs.append("/(" + "|".join(cur) + ")")
    if "index.html" in pages:
        srcs += ["/", "/index.html"]
    return srcs


def build(cfg: dict) -> tuple[list[dict], dict]:
    uni = universe(cfg)
    live = measured()
    by_policy: dict[str, list[str]] = {}
    per_page = {}
    for page in served_pages():
        pol, ev = policy_for(page, uni, live)
        per_page[page] = {"csp": pol, **ev}
        by_policy.setdefault(pol, []).append(page)
    rules = []
    for pol, pages in sorted(by_policy.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        for src in _source_for(sorted(pages)):
            rules.append({"source": src, "headers": [{"key": CSP_KEY, "value": pol}]})
    return rules, per_page


def _is_generated(rule: dict) -> bool:
    return rule["source"] != BASE_SOURCE and [h["key"] for h in rule.get("headers", [])] == [CSP_KEY]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    cfg = load_vercel()
    rules, per_page = build(cfg)
    if a.json:
        Path(a.json).write_text(json.dumps(per_page, indent=1, ensure_ascii=False), encoding="utf-8")
    current = [r for r in cfg["headers"] if _is_generated(r)]
    if a.check:
        if current != rules:
            print(f"FAIL csp-exact-profiles - vercel.json's per-page CSP rules ({len(current)}) are not what the code "
                  f"needs today ({len(rules)}): run python tools/build_csp_profiles.py --write")
            return 1
        print(f"PASS csp-exact-profiles - {len(per_page)} served pages, {len({v['csp'] for v in per_page.values()})} "
              f"policies, each naming only the origins its own code reaches; no scheme wildcard")
        return 0
    if a.write:
        cfg["headers"] = [r for r in cfg["headers"] if not _is_generated(r)] + rules
        VERCEL.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {len(rules)} generated CSP rule(s) into vercel.json")
    pols: dict[str, list[str]] = {}
    for p, v in per_page.items():
        pols.setdefault(v["csp"], []).append(p)
    for pol, pages in sorted(pols.items(), key=lambda kv: -len(kv[1])):
        print(f"\n{len(pages)} page(s): {', '.join(pages[:6])}{' ...' if len(pages) > 6 else ''}\n   {pol}")
    mo = {p: v["measured_only"] for p, v in per_page.items() if v["measured_only"]}
    if mo:
        print("\nMEASURED BUT NOT IN THE CODE READ (covered, and a path the static read missed):")
        for p, m in mo.items():
            print(f"   {p}: {', '.join(m)}")
    nu = {p: v["not_in_universe"] for p, v in per_page.items() if v.get("not_in_universe")}
    if nu:
        print("\nLOADED BUT NAMED NOWHERE IN THE UNIVERSE (production would block these):")
        for p, m in nu.items():
            print(f"   {p}: {', '.join(m)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
