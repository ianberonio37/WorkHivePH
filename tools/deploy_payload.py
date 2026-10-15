#!/usr/bin/env python3
"""deploy_payload.py - what every Vercel deployment uploads, held to what the site actually serves (2026-10-14).

Ian, 2026-10-14: *"I am not using these pages. do not just retire this, also remove this project completely, this is
just add to the Vercel storage allowed, I got email that I am almost 100% to the free tier Vercel."* The email
(Vercel, 2026-10-13, and the same one on 2026-09-29): the free team had used 75% of **Deployment Storage (10 GB)**.

Every deployment stores a full copy of what it uploads, and the upload was decided by a DENYLIST: .vercelignore named
the few things it knew were dev-only and everything else shipped. Measured the day of the email, each deployment
uploaded **611.8 MB in 5,953 files** - the live-walk evidence banks (250 MB), the critic and trajectory registries
(128 MB), test-run logs, 1,900 tool scripts, 787 migration and function files - while the site a person loads is a
small fraction of that. About twelve deployments fill three quarters of the allowance, and every new dev artifact
joined the next deployment by default, because a denylist only stops what someone remembered to name.

So .vercelignore is an ALLOWLIST (ignore everything at the root, re-include what the site serves), and this tool holds
it to the site, three ways:

  1. CLOSURE   every file a served page, script, stylesheet, manifest or the service worker references (src, href,
               fetch, importScripts, url(), the precache list, a string naming a local file) is in the payload. A file
               the site needs that the payload drops is a 404 in production - the gate fails on it, naming the page
               that asked for it.
  2. NO DEV    no Markdown, Python, log, JSONL, registry, bank, baseline, report or migration ships.
  3. BUDGET    the payload stays under BUDGET_MB, so the next forgotten artifact is a red gate, not a quota email.

The reference reader is deliberately generous (any quoted string that names a local file with a served extension),
so a MENTION - a filename inside a comment, a label map, an error message - can look like a fetch. Those are listed in
MENTIONS with the reason, never silently skipped: a name that leaves MENTIONS is checked again.

    python tools/deploy_payload.py              # the report: shipped vs served, the dead weight by kind
    python tools/deploy_payload.py --check      # the gate (exit 1 on a dropped file, a dev kind, or the budget)
    python tools/deploy_payload.py --ignore F   # evaluate a candidate ignore file instead of .vercelignore
    python tools/deploy_payload.py --self-test  # the reader and the checks against fixtures, teeth included
"""
from __future__ import annotations

import argparse
import io
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = ROOT / ".vercelignore"
BUDGET_MB = 40.0

SERVED_EXT = ("html", "js", "mjs", "css", "json", "webmanifest", "png", "jpg", "jpeg", "gif", "svg", "webp", "ico",
              "avif", "woff", "woff2", "ttf", "otf", "mp3", "mp4", "webm", "wav", "ogg", "txt", "xml", "pdf", "csv",
              "glb", "gltf")
TEXT_EXT = {"html", "js", "mjs", "css", "json", "webmanifest", "svg", "xml", "txt"}

# Whole kinds that are development evidence, never part of the site. A shipped file of one of these kinds fails rule 2.
DEV_KINDS = (
    (re.compile(r"\.(md|py|pyc|log|jsonl|sql|toml|ts|sh|ps1|bat|cmd|ipynb|lock)$", re.I), "source or log"),
    (re.compile(r"(^|/)(banks|test-runs|tools|supabase|substrate|tests|python-api|hive-baseline|page_bank_anatomy|"
                r"persona_corpus|sentinels|infra|workflows|canonical|evals|docker|scripts|__pycache__|"
                r"\.impeccable|\.github|\.vscode|_fixtures|test-data-seeder|video_marketing_app|remotion_scenes|"
                r"test-images|promo_posters)/"), "a development directory"),
    (re.compile(r"(_registry|_baseline|_report|_results|_manifest|_ledger|_corpus|_scoreboard|_bank)\.json$"),
     "a registry, baseline, report or bank"),
)

# The site's PAGES: every root page, the public folders' index pages, the 60 public calculators under tools/<slug>/
# (tools/ is otherwise the dev toolbox), and each page's llmstxt.org markdown mirror (<page>.md, index.html.md), which
# AI crawlers read in place of the HTML. A page is never a development kind, wherever it sits.
PUBLIC_PAGE = re.compile(r"^(?:[^/]+\.html|(?:about|feedback|privacy-policy|terms-of-service|learn)/index\.html"
                         r"|(?:learn|tools)/[^/]+/index\.html)(?:\.md)?$")
# Files the platform itself requests, not any page: crawlers, the PWA, the CDN config, the IndexNow key
# (tools/indexnow_submit.py names it as keyLocation; IndexNow fetches it to verify the site).
WELL_KNOWN = ("sw.js", "manifest.json", "robots.txt", "sitemap.xml", "llms.txt", "llms-full.txt", "favicon.ico",
              "favicon.svg", "vercel.json")
INDEXNOW_KEY = re.compile(r"^[0-9a-f]{32}\.txt$")
OWN_ORIGIN = re.compile(r"^https?://(?:www\.)?workhiveph\.com/", re.I)

# A quoted local filename that is NOT a fetch - a mention. Each entry says where and why; the check treats these
# as not-referenced. Anything not listed here that the reader finds is held to rule 1.
MENTIONS = {
    "platform_health.json": "never tracked (gitignored, local-only); founder-console reads it best-effort and shows "
                            "'not reachable' in production, and utils.js only labels it",
}

_LIT = re.compile(r"""["'`]((?:https?://(?:www\.)?workhiveph\.com/)?\.{0,2}/?[A-Za-z0-9_\-./]+\.(?:%s))(?:[?#][^"'`]*)?["'`]"""
                  % "|".join(SERVED_EXT), re.I)
_ATTR = re.compile(r"""\b(?:src|href|poster|data-src|content|action)\s*=\s*["']([^"'#?]+?\.(?:%s))(?:[?#][^"']*)?["']"""
                   % "|".join(SERVED_EXT), re.I)
_SRCSET = re.compile(r"""\bsrcset\s*=\s*["']([^"']+)["']""", re.I)
_CSSURL = re.compile(r"""url\(\s*["']?([^"')]+?)["']?\s*\)""")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"(?m)(?<![:\"'`\\/])//(?!/)[^\n]*$")


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return [f for f in out.stdout.decode("utf-8", "replace").split("\0") if f]


def tracked() -> list[str]:
    return _git("ls-files", "-c", "-z")


def shipped(ignore: Path = IGNORE) -> set[str]:
    """What a deployment uploads: the git tree minus what the ignore file matches (gitignore semantics, the same
    syntax Vercel reads, negation included)."""
    ignored = set(_git("ls-files", "-c", "-i", "-z", f"--exclude-from={ignore}"))
    return {f for f in tracked() if f not in ignored and (ROOT / f).is_file()}


def _strip_comments(text: str, ext: str) -> str:
    if ext in ("html",):
        text = _HTML_COMMENT.sub(" ", text)
    if ext in ("html", "js", "mjs", "css"):
        text = _BLOCK_COMMENT.sub(" ", text)
    if ext in ("html", "js", "mjs"):
        text = _LINE_COMMENT.sub("", text)
    return text


def refs_of(path: str, text: str) -> set[str]:
    """Every local file this file asks for, resolved to a repo path. External URLs, data: URIs and dynamic
    (template) paths are not files and are skipped."""
    ext = path.rsplit(".", 1)[-1].lower()
    text = _strip_comments(text, ext)
    raw: set[str] = set()
    if ext in ("html", "js", "mjs", "json", "webmanifest", "svg"):
        raw |= set(_LIT.findall(text))
    if ext in ("html", "svg"):
        raw |= set(_ATTR.findall(text))
        for ss in _SRCSET.findall(text):
            raw |= {p.strip().split(" ")[0] for p in ss.split(",") if p.strip()}
    if ext in ("html", "css", "svg"):
        raw |= {u for u in _CSSURL.findall(text) if "." in u.rsplit("/", 1)[-1]}
    base = posixpath.dirname(path)
    out: set[str] = set()
    for r in raw:
        r = OWN_ORIGIN.sub("/", r.strip())
        if not r or r.startswith(("http:", "https:", "//", "data:", "mailto:", "tel:", "javascript:", "blob:", "#")):
            continue
        if "${" in r or "{{" in r:
            continue
        r = r.split("?", 1)[0].split("#", 1)[0]
        p = posixpath.normpath(r.lstrip("/") if r.startswith("/") else posixpath.join(base, r))
        if p.startswith("..") or p in (".", ""):
            continue
        out.add(p)
    return out


_NOT_A_PAGE = re.compile(r"(\.backup\d*\.html|-test\.html|^index-[^/]*\.html)$")


def entries(universe: set[str]) -> set[str]:
    """Where a person, a crawler or the browser starts: every page in the REPO - not in the payload, so an ignore file
    that drops a real page is caught as a dropped file - plus the files the platform itself requests."""
    e = {f for f in universe if PUBLIC_PAGE.search(f) and not _NOT_A_PAGE.search(f)}
    e |= {f for f in WELL_KNOWN if f in universe}
    e |= {f for f in universe if INDEXNOW_KEY.match(f)}
    return e


def closure(universe: set[str]) -> tuple[set[str], dict[str, set[str]]]:
    """Breadth-first from the entries through every text file the site serves. Returns (needed files that exist
    in the repo, {needed file: the files that asked for it})."""
    asked: dict[str, set[str]] = defaultdict(set)
    seen: set[str] = set()
    todo = sorted(entries(universe))
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        if f.rsplit(".", 1)[-1].lower() not in TEXT_EXT or not (ROOT / f).is_file():
            continue
        try:
            text = io.open(ROOT / f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for r in refs_of(f, text):
            if r in MENTIONS or r not in universe:
                continue
            asked[r].add(f)
            if r not in seen:
                todo.append(r)
    needed = {f for f in seen if f in universe}
    return needed, asked


def shipped_at(ref: str) -> dict[str, int]:
    """What the deployment built from commit `ref` uploaded: its tree minus ITS OWN .vercelignore, asked of git's
    matcher through a temporary index (GIT_INDEX_FILE), so neither the working tree nor the real index is touched.
    Returns {path: bytes}. Empty when the ref does not resolve."""
    out = subprocess.run(["git", "ls-tree", "-r", "-l", "-z", ref], cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        return {}
    sizes: dict[str, int] = {}
    for rec in out.stdout.decode("utf-8", "replace").split("\0"):
        if "\t" not in rec:
            continue
        meta, path = rec.split("\t", 1)
        parts = meta.split()
        if len(parts) >= 4 and parts[1] == "blob":
            sizes[path] = int(parts[3]) if parts[3].isdigit() else 0
    rules = subprocess.run(["git", "show", f"{ref}:.vercelignore"], cwd=ROOT, capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        idx, rf = os.path.join(td, "index"), os.path.join(td, "vercelignore")
        io.open(rf, "w", encoding="utf-8").write(rules.stdout.decode("utf-8", "replace") if rules.returncode == 0 else "")
        env = dict(os.environ, GIT_INDEX_FILE=idx)
        subprocess.run(["git", "read-tree", ref], cwd=ROOT, env=env, capture_output=True, check=True)
        ign = subprocess.run(["git", "ls-files", "-c", "-i", "-z", f"--exclude-from={rf}"], cwd=ROOT, env=env,
                             capture_output=True).stdout.decode("utf-8", "replace").split("\0")
    ignored = {f for f in ign if f}
    return {p: s for p, s in sizes.items() if p not in ignored}


# A whole folder the site reads by a path it BUILDS at runtime (utils.js: fetch('i18n/pages/' + stem + '.fil.json')),
# so no literal names each file. It ships whole and is never dead weight.
DYNAMIC_DIRS = ("i18n/",)


def place_of(path: str) -> str:
    """The unit a person can name and a rule can exclude: a top-level folder, or a kind of file at the root."""
    if "/" in path:
        return path.split("/", 1)[0] + "/"
    return "(root) *." + (path.rsplit(".", 1)[-1].lower() if "." in path else "(no extension)")


def dead_weight_at(ref: str) -> list[dict]:
    """Every PLACE whose files the deployment built from `ref` stored while the site never asks for them - the BRH-N
    population. One entry per place: files, bytes, the largest file (the one to probe on the live origin)."""
    ship = shipped_at(ref)
    if not ship:
        return []
    needed, _ = closure(set(tracked()))
    groups: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for p, s in ship.items():
        if p in needed or p.startswith(DYNAMIC_DIRS):
            continue
        groups[place_of(p)].append((s, p))
    out = []
    for place, items in groups.items():
        items.sort(reverse=True)
        out.append({"place": place, "files": len(items), "bytes": sum(s for s, _ in items), "largest": items[0][1]})
    out.sort(key=lambda g: (-g["bytes"], g["place"]))
    return out


# 4. SERVED (2026-10-16). Rule 1 resolves a reference against the FILE's folder; the browser resolves it against the
# URL production SERVES. vercel.json's trailingSlash:false answers /learn/<slug>/ with a 308 to /learn/<slug>, so on
# every folder page (learn/<slug>/index.html, tools/<slug>/index.html, about/index.html ...) a relative reference
# climbs one level higher than the file suggests: <img src="fig-1.svg"> asks for /learn/fig-1.svg. Twelve article
# figures on six learn pages were a 404 on every reader's screen for five weeks while this gate and
# validate_image_asset_existence both read them as present. Found by the 2026-10-16 post-deploy smoke.
_DIR_HREF = re.compile(r"""\bhref\s*=\s*["']([^"'#?:]+/)["']""", re.I)


def _no_trailing_slash() -> bool:
    try:
        return json.loads(io.open(ROOT / "vercel.json", encoding="utf-8").read()).get("trailingSlash") is False
    except (OSError, ValueError):
        return False


def served_dir(path: str, no_slash: bool) -> str:
    """The folder the browser resolves a page's relative references against: the URL's, not the file's."""
    if no_slash and path.endswith("/index.html"):
        return posixpath.dirname("/" + path[: -len("/index.html")])
    return posixpath.dirname("/" + path)


def served_misses_of(path: str, text: str, ship: set[str], no_slash: bool) -> list[tuple[str, str]]:
    """Every relative reference in a page that names no shipped file once resolved against the served URL.
    Absolute ('/x'), external, data:, fragment and template references are not this rule's concern."""
    text = _strip_comments(text, "html")
    raw = set(_ATTR.findall(text)) | set(_DIR_HREF.findall(text))
    for ss in _SRCSET.findall(text):
        raw |= {p.strip().split(" ")[0] for p in ss.split(",") if p.strip()}
    raw |= {u for u in _CSSURL.findall(text) if "." in u.rsplit("/", 1)[-1]}
    base = served_dir(path, no_slash)
    out = []
    for r in sorted(raw):
        r = r.strip()
        if not r or r.startswith(("/", "http:", "https:", "data:", "mailto:", "tel:", "javascript:", "blob:", "#", "?")):
            continue
        if "${" in r or "{{" in r:
            continue
        r0 = r.split("?", 1)[0].split("#", 1)[0]
        # posixpath clamps "/.." at the root exactly as a browser does, so ../../utils.js from /learn/x is /utils.js
        p = posixpath.normpath(posixpath.join(base, r0)).lstrip("/").rstrip("/")
        if (p == "" and "index.html" in ship) or p in ship or f"{p}/index.html" in ship:
            continue
        out.append((r, "/" + p))
    return out


def served_misses(ship: set[str]) -> list[tuple[str, str, str]]:
    no_slash = _no_trailing_slash()
    out = []
    for f in sorted(ship):
        if not f.endswith(".html"):
            continue
        try:
            text = io.open(ROOT / f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        out += [(f, r, p) for r, p in served_misses_of(f, text, ship, no_slash)]
    return out


def dev_kind(path: str) -> str | None:
    if PUBLIC_PAGE.search(path):
        return None
    for rx, why in DEV_KINDS:
        if rx.search(path):
            return why
    return None


def size(paths) -> int:
    return sum((ROOT / p).stat().st_size for p in paths if (ROOT / p).is_file())


def evaluate(ignore: Path = IGNORE) -> dict:
    universe = set(tracked())
    ship = shipped(ignore)
    needed, asked = closure(universe)
    dropped = sorted(n for n in needed if n not in ship)
    dev = sorted((f, dev_kind(f)) for f in ship if dev_kind(f) and f not in needed)
    unused = sorted(f for f in ship if f not in needed)
    return {"ship": ship, "needed": needed, "asked": asked, "dropped": dropped, "dev": dev, "unused": unused,
            "served": served_misses(ship), "bytes": size(ship), "needed_bytes": size(needed)}


def report(ev: dict) -> None:
    mb = ev["bytes"] / 1e6
    print(f"deploy payload: {len(ev['ship'])} files, {mb:.1f} MB per deployment "
          f"(the site needs {len(ev['needed'])} files, {ev['needed_bytes'] / 1e6:.1f} MB)")
    print(f"  at 10 GB Deployment Storage that is room for {int(10_000 / max(mb, 0.001))} retained deployments")
    groups: dict[str, list[str]] = defaultdict(list)
    for f in ev["unused"]:
        groups[f.split("/")[0] + "/" if "/" in f else "(root) *." + f.rsplit(".", 1)[-1].lower()].append(f)
    if groups:
        print("  shipped but never served (by place):")
        for g, fs in sorted(groups.items(), key=lambda kv: -size(kv[1]))[:30]:
            print(f"    {size(fs) / 1e6:8.2f} MB  {len(fs):5d} files  {g}")
    for f in ev["dropped"]:
        print(f"  DROPPED (the site asks for it, the payload omits it): {f}  <- {', '.join(sorted(ev['asked'][f])[:3])}")
    for f, why in ev["dev"][:20]:
        print(f"  DEV KIND shipped: {f} ({why})")
    for f, r, p in ev["served"]:
        print(f"  SERVED-URL MISS: {f} asks for \"{r}\", which production resolves to {p} - not shipped")


def check(ev: dict) -> int:
    bad = 0
    for f in ev["dropped"]:
        print(f"FAIL deploy-payload: {f} is requested by {', '.join(sorted(ev['asked'][f])[:3])} but .vercelignore "
              f"leaves it out - a 404 in production")
        bad += 1
    for f, why in ev["dev"]:
        print(f"FAIL deploy-payload: {f} ships ({why}) - every deployment stores it")
        bad += 1
    for f, r, p in ev["served"]:
        print(f"FAIL deploy-payload: {f} asks for \"{r}\"; production serves the page without its trailing slash, so "
              f"the browser asks for {p} - a 404 (make the reference root-absolute)")
        bad += 1
    mb = ev["bytes"] / 1e6
    if mb > BUDGET_MB:
        print(f"FAIL deploy-payload: {mb:.1f} MB per deployment is over the {BUDGET_MB:.0f} MB budget")
        bad += 1
    if bad:
        return 1
    print(f"PASS deploy-payload - {len(ev['ship'])} files, {mb:.1f} MB per deployment (budget {BUDGET_MB:.0f} MB); "
          f"every file the site requests ships, no development artifact does, and every relative reference "
          f"resolves under the URL production serves")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    r = refs_of("learn/a/index.html", '<script src="../../utils.js"></script><img src="/icon-192.png">'
                '<a href="https://x.y/z.html"></a><!-- <script src="old.js"> --><link href="x.css?v=2">')
    t("relative, absolute and query refs resolve; external and commented ones do not",
      r == {"utils.js", "icon-192.png", "learn/a/x.css"})
    r = refs_of("sw.js", "const SHELL_FILES = ['/', '/index.html', '/i18n/pages/hive.fil.json'];\n"
                         "// '/old-page.html' was retired\nfetch(`${base}/x.json`)")
    t("a precache list is read, a line comment and a template path are not",
      r == {"index.html", "i18n/pages/hive.fil.json"})
    ship = {"index.html", "utils.js", "learn/a/index.html", "learn/a/fig.svg", "learn/b/index.html"}
    page = '<img src="{}"><script src="../../utils.js"></script><a href="../b/">b</a>'
    t("served URL: a bare figure on a folder page is a miss when production drops the trailing slash",
      served_misses_of("learn/a/index.html", page.format("fig.svg"), ship, True) == [("../b/", "/b"),
                                                                                    ("fig.svg", "/learn/fig.svg")])
    # teeth against the REAL page as it shipped in 73335a30: its two figures are the misses production 404'd
    slug = "learn/resume-builder-for-filipino-industrial-workers"
    old = subprocess.run(["git", "show", f"73335a30:{slug}/index.html"], cwd=ROOT, capture_output=True)
    real = shipped()
    t("served URL: the resume-builder article as shipped in 73335a30 misses both of its figures",
      old.returncode == 0 and sorted(r for r, _ in served_misses_of(f"{slug}/index.html", old.stdout.decode(
          "utf-8", "replace"), real, True)) == ["fig-builder-flow.svg", "fig-scan-path.svg"])
    t("served URL: a root-absolute figure and a ../../ script (clamped at the root, as a browser does) resolve",
      served_misses_of("learn/a/index.html", '<img src="/learn/a/fig.svg"><script src="../../utils.js"></script>',
                       ship, True) == [])
    t("served URL: with the trailing slash kept, the bare figure resolves against its own folder",
      served_misses_of("learn/a/index.html", page.format("fig.svg"), ship, False) == [])
    t("served URL: a root page is unaffected; a commented and a template reference are not read",
      served_misses_of("about.html", '<img src="learn/a/fig.svg"><!-- <img src="gone.svg"> -->'
                       '<img src="${x}.svg">', ship, True) == [])
    t("a source, a bank and a baseline are development kinds",
      bool(dev_kind("tools/x.py")) and bool(dev_kind("banks/hive_live_mcp_bank.json"))
      and bool(dev_kind("design_detector_baseline.json")) and not dev_kind("manifest.json") and not dev_kind("utils.js"))
    # teeth against the REAL tree: an ignore file that drops utils.js must fail rule 1, and the old denylist must
    # fail rules 2 and 3
    with tempfile.NamedTemporaryFile("w", suffix=".ignore", delete=False, encoding="utf-8") as fh:
        fh.write(io.open(IGNORE, encoding="utf-8").read() + "\n/utils.js\n")
        broken = Path(fh.name)
    try:
        ev = evaluate(broken)
        t("dropping utils.js from the payload is caught as a 404 the pages ask for", "utils.js" in ev["dropped"])
    finally:
        broken.unlink()
    with tempfile.NamedTemporaryFile("w", suffix=".ignore", delete=False, encoding="utf-8") as fh:
        fh.write("_fixtures/\n.tmp/\ntest-data-seeder/\n")
        deny = Path(fh.name)
    try:
        ev = evaluate(deny)
        t("a denylist that ships the banks and registries fails the dev-kind rule and the budget",
          any(f.startswith("banks/") for f, _ in ev["dev"]) and ev["bytes"] / 1e6 > BUDGET_MB)
    finally:
        deny.unlink()
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ignore", default=str(IGNORE))
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    ev = evaluate(Path(a.ignore))
    if a.json:
        print(json.dumps({"files": len(ev["ship"]), "bytes": ev["bytes"], "needed": sorted(ev["needed"]),
                          "dropped": ev["dropped"], "dev": [f for f, _ in ev["dev"]]}, indent=1))
        return 0
    if a.check:
        return check(ev)
    report(ev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
