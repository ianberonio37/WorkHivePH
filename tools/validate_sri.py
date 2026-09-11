#!/usr/bin/env python3
"""
validate_sri.py - Arc R (S-lens, OWASP A08): Subresource Integrity on third-party CDN scripts.
==============================================================================================
A <script src="https://cdn.../lib.js"> with no `integrity=` lets a CDN compromise inject arbitrary
JS into every authenticated page (token/RLS-session theft). The platform had ZERO `integrity=`
attributes anywhere (Hunter S, Arc R).

FOUR buckets, because "add a hash" is not possible for all of them:
  PINNED   - URL carries an exact version (plotly-basic-2.26.0, xlsx@0.18.5). Hashable TODAY, so a
             pinned third-party script WITHOUT integrity is a hard FAIL.
  FLOATING - no exact version. SRI needs pinning first (behaviour-affecting = Ian-reviewable), so it
             is a tracked backlog NOTE, not a fail.
  UN-SRI-ABLE BY THE PROVIDER - Tailwind Play CDN (a runtime JIT with no versioned artifact) and
             Cloudflare Turnstile (one unversioned endpoint, must load live). Reported separately so
             the line never implies "just add a hash"; the levers are a built CSS file / nothing.
  WORKER   - a cross-origin worker is fetched from a URL STRING, so no element can carry `integrity`.
             SRI cannot apply at all; the lever is self-hosting the file.
Exempt: Google Fonts/gtag (Google-managed); connection HINTS (`rel=preconnect|dns-prefetch`) fetch no
subresource; same-origin and own-domain URLs.

THREE REACHES, because one library arrives in more than one shape (added 2026-09-10 after this gate
reported PASS over eleven live violations of its own rule - see the ★ notes below):
  1. a static `<script src>` / `<link href>` tag;
  2. an element BUILT in JS - `s.src = '<url>'` / `s.setAttribute('src', '<url>')`;
  3. a URL passed to a loader HELPER - `vehLoadScript('<url>')` - including one bound to a constant
     and loaded elsewhere (`const PDFJS_SRC = ...` / `loadScript(PDFJS_SRC, PDFJS_SRI)`).
A URL's verdict is min() over its call sites: protected only if EVERY occurrence carries a hash, so
one hashed call cannot vouch for an unhashed one (this is a real shape - `xlsx` in integrations.html).

SCOPE is derived, never hand-listed: Vercel deploys the git-tracked tree minus `.vercelignore`, so
that is the page set (~169). Root-only missed `feedback/index.html`; a bare rglob over-corrected to
551 by sweeping `.tmp/`, `*_bak/` and Flask template dirs.

Self-test (--self-test): each reach has a positive and a negative case, a URL in a comment is not a
load, an order-reversal case proves min() over call sites, and the scope set must contain a
subdirectory page while containing no backup/fixture/vendored tree.
Exit 0 = no pinned CDN script lacks SRI. Exit 1 = a pinned script is unprotected (or self-test fail).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_sri"]

TAG = re.compile(r"<(script|link)\b[^>]*>", re.IGNORECASE)
SRC = re.compile(r'(?:src|href)\s*=\s*"(https://[^"]+)"', re.IGNORECASE)
HAS_INTEGRITY = re.compile(r'\bintegrity\s*=', re.IGNORECASE)
# Exempt hosts: Google-managed fonts/analytics (SRI not applicable).
EXEMPT_HOST = re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com|googletagmanager\.com|google-analytics\.com")
# Same-origin / own domain - not third-party.
OWN_HOST = re.compile(r"workhiveph\.com|supabase\.co/storage|hzyvnjtisfgbksicrouu\.supabase\.co")
# A version pin: @x.y.z  OR /x.y.z/  OR -x.y.z. (e.g. plotly-basic-2.26.0)
PINNED = re.compile(r"@\d+\.\d+\.\d+|/\d+\.\d+\.\d+/|-\d+\.\d+\.\d+")
# Tailwind Play CDN: a runtime JIT compiler with NO versioned artifact — it cannot be SRI-hashed at all
# (pinning is not the fix; migrating to a built static CSS file is). Reported DISTINCTLY from pin-first so
# the backlog line doesn't imply "just add a hash." (Arc R R3, 2026-07-03.)
PLAY_CDN = re.compile(r"cdn\.tailwindcss\.com")
# A hint, not a subresource: `<link rel="preconnect|dns-prefetch">` opens a connection and fetches
# NOTHING, so there is no response for a hash to describe. Reporting it as "a floating ref that can
# be pinned" sends the reader to fix a line that is already correct.
HINT_REL = re.compile(r'rel\s*=\s*["\']?(?:preconnect|dns-prefetch|preload\s+as=["\']?font)', re.I)
# Un-SRI-able by the PROVIDER's design, the same category as the Tailwind Play CDN and reported
# beside it: Cloudflare serves Turnstile from one unversioned endpoint and documents that it must be
# loaded live, so there is no artifact to pin. "Add a hash" is not the lever; nothing is.
UNPINNABLE_BY_DESIGN = re.compile(r"challenges\.cloudflare\.com/turnstile")

# ★A TAG-ONLY READER CANNOT SEE A SCRIPT BUILT IN JAVASCRIPT (2026-09-10).
# Five founder-gate pages (architecture, llm-observability, agentic-rag-observability,
# validator-catalog, symbol-gallery) never wrote a <script src> for the Supabase client - they did
# `var s1 = document.createElement('script'); s1.src = 'https://cdn.jsdelivr.net/npm/@supabase/
# supabase-js@2';`. FLOATING and with no integrity at all: the weakest contract on the platform,
# inside the admin check itself, and this gate reported those pages CLEAN for as long as it existed
# because it only ever read tag text. The blind spot was not the rule; it was the reach.
JS_SRC = re.compile(r"""(\w+)\.src\s*=\s*['"](https://[^'"]+)['"]""")
JS_SRC_ATTR = re.compile(r"""(\w+)\.setAttribute\(\s*['"]src['"]\s*,\s*['"](https://[^'"]+)['"]""")
JS_INTEGRITY = re.compile(
    r"""(\w+)\.integrity\s*=|(\w+)\.setAttribute\(\s*['"]integrity['"]""")

# ...and a THIRD shape, found the moment the second one worked: the URL is a FUNCTION ARGUMENT.
# `vehLoadScript('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/...')` builds the element inside a helper,
# so neither the tag reader nor the `.src =` reader sees the URL. Eight such calls sat in
# integrations.html and resume.html - pdfjs, mammoth, xlsx, papaparse, jszip - every one version-
# PINNED and therefore in this gate's hard-FAIL tier, in the two pages that ingest user documents.
# The rule that covers all three shapes without naming a helper: any https string LITERAL that ends
# in .js/.mjs is a script this page can load. A literal inside a // or /* */ comment is not a load.
JS_URL_LITERAL = re.compile(r"""['"](https://[^'"\s]+\.m?js)(?:\?[^'"\s]*)?['"]""")
# ★THE COMMENT STRIPPER ATE THE EVIDENCE: a bare `//[^\n]*` treats the `//` in `https://` as the
# start of a line comment and blanks the rest of the line - so the very URLs this reach exists to
# find were removed before it looked. The gate reported 0 pinned-without-SRI while eight sat in the
# tree. Same shape as the `accept="image/*"` stripper that blanked 15.8% of a log. The lookbehind
# says a comment marker is not a comment marker when it is part of a scheme.
COMMENT = re.compile(r"(?<![:'\"])//[^\n]*|/\*.*?\*/", re.DOTALL)


# A web worker is fetched by the browser FROM A URL STRING, so no element exists to carry an
# `integrity` attribute and SRI cannot cover it at all. `pdf.worker.min.js` is loaded exactly this
# way on both document-ingesting pages. It gets its own bucket rather than a FAIL, because "add a
# hash" is not a thing that can be done here - the lever is self-hosting the worker file.
WORKER_SRC = re.compile(r"\.worker(\.min)?\.m?js$|workerSrc", re.IGNORECASE)
# An SRI hash passed as a sibling ARGUMENT, the shape `loadScriptOnce(url, 'sha384-...')` already
# uses on this platform - the helper sets s.integrity from it, so the URL is protected.
SRI_LITERAL = re.compile(r"['\"]sha(?:256|384|512)-[A-Za-z0-9+/=]{20,}['\"]")
# ...or as a NAMED constant holding one, e.g. `loadScript(PDFJS_SRC, PDFJS_SRI)`.
SRI_IDENT = re.compile(r"\b\w*(?:_SRI|SRI_|INTEGRITY|_HASH)\w*\b")
CONST_DECL = re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*['\"]https://")


def classify_tag(tag: str) -> str | None:
    """Return 'pinned-no-sri' | 'floating-no-sri' | None (ok/exempt)."""
    if HINT_REL.search(tag):
        return None                      # preconnect/dns-prefetch fetches no subresource
    if "stylesheet" in tag.lower() and "<link" in tag.lower():
        pass  # CSS link still counts if third-party JS-adjacent; fonts excluded below
    m = SRC.search(tag)
    if not m:
        return None
    url = m.group(1)
    if EXEMPT_HOST.search(url) or OWN_HOST.search(url):
        return None
    if HAS_INTEGRITY.search(tag):
        return None
    return "pinned-no-sri" if PINNED.search(url) else "floating-no-sri"


def _stmt_window(text: str, m) -> str:
    """The statement a match sits in: its line, plus ONE continuation line when the line does not
    close the statement. Never the following statement - that is what let a hash on the next call
    protect the unhashed call above it."""
    ls = text.rfind("\n", 0, m.start()) + 1
    le = text.find("\n", m.end())
    le = len(text) if le == -1 else le
    if ";" in text[m.end():le]:
        return text[ls:le]
    nl = text.find("\n", le + 1)
    return text[ls:(len(text) if nl == -1 else nl)]


def scan(text: str) -> tuple[list[str], list[str], list[str]]:
    pinned, floating, workers = [], [], []
    for m in TAG.finditer(text):
        tag = m.group(0)
        cls = classify_tag(tag)
        url_m = SRC.search(tag)
        url = url_m.group(1) if url_m else "?"
        if cls == "pinned-no-sri":
            pinned.append(url)
        elif cls == "floating-no-sri":
            floating.append(url)

    # Second reach: scripts BUILT in JavaScript. A var that is given an `integrity` anywhere in the
    # file counts as protected - deliberately coarse, and coarse in the SAFE direction only for a
    # file that already sets integrity on some element; it never invents a hit that is not there.
    protected = {g for mm in JS_INTEGRITY.finditer(text) for g in mm.groups() if g}
    seen_js: set[str] = set()
    for rx in (JS_SRC, JS_SRC_ATTR):
        for m in rx.finditer(text):
            var, url = m.group(1), m.group(2)
            seen_js.add(url)          # record BEFORE any skip, so the third reach cannot re-find it
            if var in protected or EXEMPT_HOST.search(url) or OWN_HOST.search(url):
                continue
            (workers if WORKER_SRC.search(url) else
             (pinned if PINNED.search(url) else floating)).append(url + "  [JS-injected]")

    # Third reach: an https .js literal anywhere in the page's script, minus comments. Any URL
    # already tallied above, or already carried by a tag with integrity, is not counted twice.
    tagged_with_sri = {m.group(1) for m in SRC.finditer(text)
                       if HAS_INTEGRITY.search(text[max(0, m.start() - 400):m.end() + 400])}
    # ★AN UNPROTECTED PATH MUST NOT BE HIDDEN BY A PROTECTED ONE. `xlsx.full.min.js` is loaded TWICE
    # in integrations.html: once through `loadScriptOnce(url, 'sha384-...')` and once through
    # `vehLoadScript(url)` with no hash. Deduplicating a URL on first sight would certify whichever
    # call site happened to come first - a max() over call sites. The verdict per URL is min():
    # protected only if EVERY occurrence carries a hash.
    stripped = COMMENT.sub(" ", text)
    helper: dict[str, bool] = {}
    for m in JS_URL_LITERAL.finditer(stripped):
        url = m.group(1)
        if url in seen_js or url in tagged_with_sri:
            continue
        if (EXEMPT_HOST.search(url) or OWN_HOST.search(url) or PLAY_CDN.search(url)
                or UNPINNABLE_BY_DESIGN.search(url)):
            continue
        if f'src="{url}"' in text or f"src='{url}'" in text:
            continue                                  # it is a static tag; tier 1 already judged it
        ls = stripped.rfind("\n", 0, m.start()) + 1
        le = stripped.find("\n", m.end())
        le = len(stripped) if le == -1 else le
        # The window is THIS statement, never the next one. A wrapped call is allowed exactly one
        # continuation line, and only when this line does not already close the statement - without
        # that condition, the hash on the FOLLOWING call protects the unhashed call above it, and
        # the verdict flips purely on the order the two call sites appear in.
        if ";" in stripped[m.end():le]:
            window = stripped[ls:le]
        else:
            nl = stripped.find("\n", le + 1)
            window = stripped[ls:(len(stripped) if nl == -1 else nl)]
        prot = bool(SRI_LITERAL.search(window)) or bool(SRI_IDENT.search(window))

        # A URL bound to a constant is loaded at that constant's CALL SITES, not at its declaration:
        # `const PDFJS_SRC = '<url>'` ... `loadScript(PDFJS_SRC, PDFJS_SRI)`. Judging the declaration
        # line alone reports an unprotected load that is in fact protected. Follow the name, and
        # apply the same min() over its call sites - every one must carry a hash.
        decl = CONST_DECL.search(window)
        if decl and not prot:
            name = decl.group(1)
            uses = [u for u in re.finditer(r"[(,]\s*" + re.escape(name) + r"\s*[,)]", stripped)]
            if uses:
                prot = all(SRI_LITERAL.search(_stmt_window(stripped, u)) or
                           SRI_IDENT.search(_stmt_window(stripped, u)) for u in uses)
        helper[url] = helper.get(url, True) and prot

    for url, protected_here in helper.items():
        if protected_here:
            continue
        seen_js.add(url)
        if WORKER_SRC.search(url):
            # A worker is fetched by the browser from a URL string, not from an element, so there is
            # no `integrity` attribute to carry a hash - SRI genuinely cannot cover it. Telling the
            # reader to "add SRI" here would be wrong advice, so it gets its own bucket: the lever
            # is self-hosting the worker file, the same move made for the Supabase client.
            workers.append(url)
            continue
        (pinned if PINNED.search(url) else floating).append(url + "  [JS-loaded via helper]")
    return pinned, floating, workers


def _vercelignore_patterns() -> list[str]:
    f = ROOT / ".vercelignore"
    if not f.exists():
        return []
    return [ln.strip() for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def _ignored(rel: str, patterns: list[str]) -> bool:
    import fnmatch
    for pat in patterns:
        if pat.endswith("/"):
            if rel == pat[:-1] or rel.startswith(pat):
                return True
        elif fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel.rsplit("/", 1)[-1], pat):
            return True
    return False


def pages_to_scan():
    """The pages the site actually SERVES - derived, not hand-listed.

    Two failures bracket this function, and both were about reach rather than rules:
      - too narrow: `ROOT.glob('*.html')` saw only the root, so `feedback/index.html` carried a
        third-party tag that this gate reported clean for as long as it existed;
      - too wide: `rglob` then swept `.tmp/`, `.hexvar_bak/`, `.palette_bak/` and Flask template
        dirs, inflating the backlog with copies nothing serves.
    The served surface is derivable: Vercel deploys the git-tracked tree minus `.vercelignore`, so
    that is the definition used here. `git ls-files` also means an untracked scratch copy can never
    re-inflate the number. Fallback (no git) errs toward the served set by dropping dot-dirs."""
    import subprocess
    patterns = _vercelignore_patterns()
    rels: list[str] = []
    try:
        out = subprocess.run(["git", "ls-files", "*.html"], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            rels = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        rels = []
    if not rels:                                    # no git: keep going, but say so in the report
        rels = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.html")
                if not any(part.startswith(".") or part in ("node_modules", "vendor")
                           for part in p.relative_to(ROOT).parts)]
    for rel in sorted(set(rels)):
        if _ignored(rel, patterns) or "backup" in rel or "-test" in rel:
            continue
        p = ROOT / rel
        if p.exists():
            yield p


def self_test() -> bool:
    ok = True
    p, *_ = scan('<script src="https://cdn.plot.ly/plotly-basic-2.26.0.min.js"></script>')
    if not p:
        print(f"{R}self-test FAIL: missed pinned-no-SRI.{X}"); ok = False
    p2, *_ = scan('<script src="https://cdn.plot.ly/plotly-basic-2.26.0.min.js" integrity="sha384-x" crossorigin="anonymous"></script>')
    if p2:
        print(f"{R}self-test FAIL: flagged a tag that HAS integrity.{X}"); ok = False
    _, fl, _ = scan('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>')
    if not fl:
        print(f"{R}self-test FAIL: did not classify floating tag.{X}"); ok = False
    p3, *_ = scan('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?x">')
    if p3:
        print(f"{R}self-test FAIL: flagged exempt Google Fonts.{X}"); ok = False

    # --- the JS-injected reach: the shape that was invisible until 2026-09-10 ---
    _, fl2, _ = scan("var s1 = document.createElement('script');\n"
                  "s1.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2';")
    if not fl2:
        print(f"{R}self-test FAIL: missed a FLOATING script built in JS.{X}"); ok = False
    p4, *_ = scan("var s1 = document.createElement('script');\n"
                 "s1.src = 'https://cdn.plot.ly/plotly-basic-2.26.0.min.js';")
    if not p4:
        print(f"{R}self-test FAIL: missed a PINNED script built in JS.{X}"); ok = False
    p5, f5, _ = scan("var s1 = document.createElement('script');\n"
                  "s1.src = 'https://cdn.plot.ly/plotly-basic-2.26.0.min.js';\n"
                  "s1.integrity = 'sha384-x';")
    if p5 or f5:
        print(f"{R}self-test FAIL: flagged a JS-built script that DOES set integrity.{X}"); ok = False
    p6, f6, _ = scan("s1.src = 'vendor/supabase-js-2.110.0.min.js';")
    if p6 or f6:
        print(f"{R}self-test FAIL: flagged a same-origin relative src.{X}"); ok = False
    p7, *_ = scan("s1.setAttribute('src', 'https://cdn.plot.ly/plotly-basic-2.26.0.min.js');")
    if not p7:
        print(f"{R}self-test FAIL: missed setAttribute('src', ...).{X}"); ok = False

    # --- the helper-argument reach, and the comment-stripper trap that hid it ---
    p8, *_ = scan("await vehLoadScript('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js');")
    if not p8:
        print(f"{R}self-test FAIL: missed a PINNED url passed to a loader helper "
              f"(the `//` in https:// must not read as a comment).{X}"); ok = False
    p9, *_ = scan("// loadScript('https://cdn.plot.ly/plotly-basic-2.26.0.min.js') - the old way\n")
    if p9:
        print(f"{R}self-test FAIL: counted a URL that only appears in a comment.{X}"); ok = False
    p10, *_ = scan("/* see https://cdn.plot.ly/plotly-basic-2.26.0.min.js */\n")
    if p10:
        print(f"{R}self-test FAIL: counted a URL inside a block comment.{X}"); ok = False
    p11, *_ = scan("await loadScriptOnce('https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js', "
                   "'sha384-D/t0ZMqQW31H3az8ktEiNb39wyKnS82iFY52QPACM+IjKW3jDUhyIgh2PApRqJZs');")
    if p11:
        print(f"{R}self-test FAIL: flagged a helper call that DOES pass an SRI hash.{X}"); ok = False

    # Two call sites for ONE url, one hashed and one not: the verdict is min(), not max().
    both = ("await loadScriptOnce('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js', 'sha384-"
            "vtjasyidUo0kW94K5MXDXntzOJpQgBKXmE7e2Ga4LG0skTTLeBi97eFAXsqewJjw');\n"
            "await vehLoadScript('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js');")
    p12, *_ = scan(both)
    if not p12:
        print(f"{R}self-test FAIL: a hashed call site masked an unhashed one for the same URL.{X}"); ok = False
    p13, *_ = scan("\n".join(reversed(both.split("\n"))))
    if not p13:
        print(f"{R}self-test FAIL: order of call sites changed the verdict.{X}"); ok = False

    p14, f14, _ = scan('<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin />')
    if p14 or f14:
        print(f"{R}self-test FAIL: flagged a preconnect hint, which fetches no subresource.{X}"); ok = False
    p15, f15, _ = scan('<link rel="stylesheet" href="https://cdn.example.com/x-1.2.3.css">')
    if not p15:
        print(f"{R}self-test FAIL: a real pinned third-party stylesheet must still be caught.{X}"); ok = False

    # --- the reach itself: a subdirectory page must be in scope at all ---
    names = {str(p.relative_to(ROOT)).replace("\\", "/") for p in pages_to_scan()}
    if not any("/" in n for n in names):
        print(f"{R}self-test FAIL: scan set is root-only - a subdirectory page cannot be seen.{X}"); ok = False
    if "feedback/index.html" not in names:
        print(f"{R}self-test FAIL: the subdirectory page that started this is not in scope.{X}"); ok = False
    if not any(n.startswith("learn/") for n in names) or not any(n.startswith("tools/") for n in names):
        print(f"{R}self-test FAIL: learn/ or tools/ pages are not in scope.{X}"); ok = False
    leaked = sorted(n for n in names
                    if n.startswith((".", "_fixtures/", "vendor/", "node_modules/"))
                    or "_bak/" in n or n.startswith(".tmp/"))
    if leaked:
        print(f"{R}self-test FAIL: scan set includes non-served trees: {leaked[:3]}{X}"); ok = False
    print((G + "self-test PASS - SRI detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    pinned_hits: dict[str, list] = {}
    pin_first_urls: list[str] = []   # floating but pinnable+SRI-able (freeze to current-resolved)
    play_cdn_urls: list[str] = []    # floating AND un-SRI-able (Tailwind Play CDN — migrate to built CSS)
    worker_urls: list[tuple[str, str]] = []   # SRI does not apply at all - self-hosting is the lever
    scanned = 0
    for p in pages_to_scan():
        scanned += 1
        name = str(p.relative_to(ROOT)).replace("\\", "/")
        pinned, floating, page_workers = scan(p.read_text(encoding="utf-8", errors="replace"))
        if pinned:
            pinned_hits[name] = pinned
        for u in page_workers:
            worker_urls.append((u, name))
        for u in floating:
            # Carry the FILE with the URL: a backlog line naming only a URL cannot be acted on.
            unpinnable = PLAY_CDN.search(u) or UNPINNABLE_BY_DESIGN.search(u)
            (play_cdn_urls if unpinnable else pin_first_urls).append((u, name))

    pinned_n = sum(len(v) for v in pinned_hits.values())
    print(f"{B}SRI gate (Arc R / S-lens, OWASP A08){X}")
    for fn, urls in pinned_hits.items():
        for u in urls:
            print(f"  {R}FAIL{X} {fn}: pinned CDN script w/o SRI -> {u}")
    print(f"  scanned {scanned} page(s) incl. subdirectories · reads BOTH <script src> tags and scripts built in JS")
    print(f"  pinned-without-SRI: {pinned_n}  ·  pin-first backlog (Ian-reviewable): {len(pin_first_urls)}"
          f"  ·  Play-CDN un-SRI-able (migrate to built CSS): {len(play_cdn_urls)}")
    if pin_first_urls:
        by_url: dict[str, list[str]] = {}
        for u, fn in pin_first_urls:
            by_url.setdefault(u, []).append(fn)
        print(f"  {Y}NOTE{X} {len(pin_first_urls)} floating ref(s) CAN be pinned+SRI'd (freeze to current-resolved, "
              f"hash-verify):")
        for u in sorted(by_url):
            files = sorted(set(by_url[u]))
            shown = ", ".join(files[:4]) + (f" (+{len(files) - 4} more)" if len(files) > 4 else "")
            print(f"      {u}\n        in {shown}")
    if worker_urls:
        wf = sorted({fn for _, fn in worker_urls})
        wu = sorted({u.split("  [")[0] for u, _ in worker_urls})
        print(f"  {Y}NOTE{X} {len(worker_urls)} cross-origin WORKER script(s) in {', '.join(wf)} — a worker is "
              f"fetched from a URL string, so no element can carry integrity and SRI cannot apply; the lever is "
              f"self-hosting the worker file: " + ", ".join(wu))
    if play_cdn_urls:
        tw_files = sorted({fn for u, fn in play_cdn_urls if PLAY_CDN.search(u)})
        n_tw = sum(1 for u, _ in play_cdn_urls if PLAY_CDN.search(u))
        n_cf = len(play_cdn_urls) - n_tw
        if n_cf:
            print(f"  {Y}NOTE{X} {n_cf} ref(s) un-SRI-able by the PROVIDER's design (Cloudflare Turnstile is served "
                  f"from one unversioned endpoint and must be loaded live) — no hash exists to add.")
        print(f"  {Y}NOTE{X} {n_tw}x cdn.tailwindcss.com across {len(tw_files)} page(s) — Tailwind Play "
              f"CDN is a runtime JIT with no versioned artifact; SRI is not the lever, migrating to a built static "
              f"CSS file is (own Ian-gated unit).")
    if pinned_n:
        print(f"{R}FAIL: {pinned_n} version-pinned third-party CDN script(s) lack integrity= .{X}")
        return 1
    print(f"{G}PASS - every version-pinned CDN script has SRI.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
