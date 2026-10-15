#!/usr/bin/env python3
"""csp-covers-what-ships - the production headers must permit what the code actually does (2026-08-28).

Covers BOTH prod-only policy headers in `_headers`: Content-Security-Policy (what the pages may
load) and Permissions-Policy (what browser APIs the pages may call). They are one class, because
they fail the same way - silently, only in production, in a file with no local equivalent.

`_headers` is PROD-ONLY behavior: nothing in the local stack serves it, so a directive that blocks
a real subresource fails ONLY in production, silently, with the evidence confined to a browser
console nobody is watching. This file has now recorded FIVE incidents of exactly that:

    Permissions-Policy denied camera+microphone site-wide -> voice journal + photo capture dead
    script/connect-src predated GA4                       -> the shipped analytics never fired
    script/frame-src lacked Turnstile                     -> enabling bot defense would kill signup
    connect-src lacked tiles.openfreemap.org, no worker-src -> the marketplace map dead
    script-src lacked cdn.plot.ly / cdnjs                 -> analytics charts + PDF export dead

Every one was found by a person noticing, never by a check. Patching a sixth would leave the class
exactly as open as the first left it, so this gate asserts the policy against the code.

TWO INDEPENDENT CHECKS, because the failures arrive two different ways:

1. MECHANICAL - every external host in a <script src> or a stylesheet <link href> must appear in
   script-src / style-src. These are unambiguous: the browser will fetch them on page load, and a
   host that is not permitted is simply not fetched.

2. DOCUMENTARY - a source comment that STATES a CSP requirement must be honored by _headers.
   ★THIS IS THE CHECK THE MAP INCIDENT ASKED FOR. wh-map.js carries, in its own header, "Prod CSP
   needs connect-src https://tiles.openfreemap.org + worker-src blob:". The requirement was
   written down, correctly, by the person who knew it - and never reached the file that ENFORCES
   it. A note in the consumer is not a change in the policy. Anyone who writes that sentence again
   now gets a red gate instead of a silent outage.

DELIBERATELY NOT CHECKED: connect-src against every https:// literal in the source. Those literals
are dominated by things CSP does not govern (anchor hrefs, JSON-LD @context, canonical URLs,
placeholder examples), and a check with that much noise gets muted, which is worse than no check.
The documentary half covers connect-src where it matters, because a developer adding a remote API
is exactly the person who writes the requirement down.

Usage:      python tools/validate_csp_covers_what_ships.py
Self-test:  python tools/validate_csp_covers_what_ships.py --self-test
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"backup|^index-.*-test|\.bak", re.I)

SCRIPT_SRC = re.compile(r"<script[^>]*\bsrc\s*=\s*[\"'](https://[^\"']+)", re.I)
# ★MATCH THE WHOLE TAG, NEVER A WINDOW AROUND THE href. The first version of this gate read the
# 90 characters following the href and asked whether "stylesheet" appeared in them, which reached
# PAST the tag's own `>` into the NEXT <link> on the following line. Eight pages were reported as
# loading a remote stylesheet from supabase.co when every one was `rel="preconnect"` sitting above
# a real stylesheet link. `[^>]*` bounds the read to a single tag, so rel and href always belong
# to the same element - the kind of false positive that, banked, becomes eight fabricated defects.
LINK_TAG = re.compile(r"<link[^>]*>", re.I)
LINK_HREF_ATTR = re.compile(r"\bhref\s*=\s*[\"'](https://[^\"']+)", re.I)
STYLESHEET = re.compile(r"\brel\s*=\s*[\"'][^\"']*\bstylesheet\b", re.I)
# "CSP needs connect-src https://x + worker-src blob:" / "Prod CSP requires script-src https://y"
#
# ★THE TERMINATOR MUST NOT TREAT A DOT IN A HOSTNAME AS THE END OF A SENTENCE. The first version
# ended the match at the first ".", which lands INSIDE the URL - so wh-map.js's requirement was
# read as "connect-src https://tiles" and the "+ worker-src blob:" half of the same sentence was
# never parsed at all. The gate then silently checked one of the two things it was built to check,
# and reported a truncated host in its own failure message. A sentence ends at ". " or a line end,
# never mid-token.
DOC_REQ = re.compile(
    r"CSP\s+(?:needs|requires)\s+(.+?)(?:\.\s|\.$|\*/|\n\s*\*\s*\n|\n\s*\n|$)", re.I | re.S)
DIRECTIVE_VALUE = re.compile(r"\b(script-src|style-src|connect-src|img-src|font-src|frame-src|"
                             r"worker-src|child-src|media-src)\s+([^\s,;+]+)")


# ── Permissions-Policy: the SAME class, a different header ──────────────────────────────────────
# Each entry maps a browser API the code actually calls to the policy feature that gates it. An
# EMPTY allowlist - `feature=()` - denies every origin including our own pages, which is what made
# the camera/microphone incident and then, five weeks later, the geolocation one.
POLICY_FEATURES = {
    "geolocation": re.compile(r"navigator\.geolocation|getCurrentPosition|watchPosition"),
    "camera": re.compile(r"getUserMedia\s*\(\s*\{[^}]*video|capture\s*=\s*[\"'](?:user|environment)"),
    "microphone": re.compile(r"getUserMedia\s*\(\s*\{[^}]*audio|SpeechRecognition"),
}
# Vendored third-party libraries call these APIs for features we may never invoke; a policy is
# owed to OUR code, not to every branch of a bundled map renderer.
VENDORED = re.compile(r"maplibre-gl|\.min\.js$|plotly", re.I)

# ── 3. CAPABILITY - what the code DOES with a URL it made or was handed (2026-10-14) ──────────────
# ★THE SIXTH INCIDENT ARRIVED THROUGH A DOOR NEITHER CHECK ABOVE HAD. Two classes failed in production on every engine,
# and both only on a person's ACTION, so no page-load walk could see them: (a) a listing photo or a resume photo turned
# into an object URL and set as an <img> src - the shipped img-src granted `'self' data: https:` and never `blob:`, so
# the preview broke and the resume's compression Image never loaded; (b) the logbook's spoken answer, an <audio> from the
# tts-cache storage bucket (or a blob: from a local voice) - the policy declared NO media-src, so media inherited
# `default-src 'self'` and every voice was refused. Measured in real Chromium and WebKit under the shipped header: an
# `img-src blob` and a `media-src` violation each. A blob: rendered into an image needs img-src blob:; a played audio
# needs a media-src that names where it comes from.
BLOB_IMAGE = re.compile(
    r"createObjectURL\([^)]*\)[\s\S]{0,400}?\b(?:img|im|image|\w*[Ii]mg|preview\w*|thumb\w*)\.src\s*=|"
    r"new Image\(\)[\s\S]{0,160}?createObjectURL\(")
AUDIO_CALL = re.compile(r"new Audio\(([^)]*)\)")
DEV_ONLY_MEDIA = re.compile(r"EDGE_TTS|getEdgeTtsBase|edgeBase", re.I)


def parse_permissions_policy(headers: str) -> dict:
    m = re.search(r"Permissions-Policy:\s*([^\n]+)", headers)
    if not m:
        return {}
    out = {}
    for part in m.group(1).split(","):
        part = part.strip()
        pm = re.match(r"([a-z-]+)\s*=\s*\((.*)\)\s*$", part)
        if pm:
            out[pm.group(1)] = pm.group(2).strip()
    return out


def parse_csp(headers: str) -> dict:
    m = re.search(r"Content-Security-Policy:\s*([^\n]+)", headers)
    if not m:
        return {}
    out = {}
    for part in m.group(1).split(";"):
        part = part.strip()
        if part:
            bits = part.split()
            out[bits[0].lower()] = set(bits[1:])
    return out


def host_of(url: str) -> str:
    m = re.match(r"https://([^/\"'?]+)", url)
    return m.group(1) if m else ""


def permitted(csp: dict, directive: str, host: str) -> bool:
    """A host is permitted if its directive (or the default-src fallback) names it."""
    srcs = csp.get(directive)
    if srcs is None:
        srcs = csp.get("default-src", set())   # absent directive INHERITS default-src
    for s in srcs:
        if s in ("*", "https:"):
            return True
        if s.rstrip("/").endswith(host):
            return True
    return False


def audit(files, headers: str):
    csp = parse_csp(headers)
    if not csp:
        return [("FAIL", "no Content-Security-Policy in the shipped policy - nothing to audit against")], 0, 0

    problems, subresources, documented = [], 0, 0

    for path in files:
        name = Path(path).name
        src = io.open(path, encoding="utf-8", errors="replace").read()

        for m in SCRIPT_SRC.finditer(src):
            h = host_of(m.group(1))
            if not h:
                continue
            subresources += 1
            if not permitted(csp, "script-src", h):
                problems.append(f"{name}: <script src> loads {h}, which script-src does not permit "
                                f"- the script simply never runs in production")

        for tagm in LINK_TAG.finditer(src):
            tag = tagm.group(0)
            if not STYLESHEET.search(tag):
                continue           # preconnect/canonical/icon/manifest are not stylesheet fetches
            hrefm = LINK_HREF_ATTR.search(tag)
            if not hrefm:
                continue           # a same-origin stylesheet needs no external grant
            h = host_of(hrefm.group(1))
            if not h:
                continue
            subresources += 1
            if not permitted(csp, "style-src", h):
                problems.append(f"{name}: stylesheet <link> loads {h}, which style-src does not permit")

        # ── the documentary half ────────────────────────────────────────────────────────────
        for m in DOC_REQ.finditer(src):
            for directive, value in DIRECTIVE_VALUE.findall(m.group(1)):
                documented += 1
                srcs = csp.get(directive.lower())
                if srcs is None:
                    problems.append(f"{name}: its own comment states the prod CSP needs "
                                    f"`{directive} {value}`, and the shipped policy declares no {directive} "
                                    f"at all (so it inherits default-src and blocks it)")
                elif not any(value.rstrip("/") in s or s in value for s in srcs):
                    problems.append(f"{name}: its own comment states the prod CSP needs "
                                    f"`{directive} {value}`, which the shipped policy does not grant")

    # ── the capability half (2026-10-14): what the code does with a URL it made or was handed ──────
    def _grants(directive: str, token: str) -> bool:
        srcs = csp.get(directive)
        if srcs is None:
            srcs = csp.get("default-src", set())     # an absent directive inherits default-src
        return any(s == token or (token not in ("blob:", "data:") and s.rstrip("/").endswith(token)) for s in srcs)
    storage = next((host_of(s) for s in csp.get("connect-src", set()) if s.endswith(".supabase.co")), "")
    for path in files:
        name = Path(path).name
        if VENDORED.search(name):
            continue
        src = io.open(path, encoding="utf-8", errors="replace").read()
        m = BLOB_IMAGE.search(src)
        if m and not _grants("img-src", "blob:"):
            line = src[: m.start()].count("\n") + 1
            problems.append(f"{name}:{line}: renders an object URL (blob:) as an image, and img-src does not grant "
                            f"blob: - the preview breaks and an Image() waiting on it never loads, in every engine")
        for am in AUDIO_CALL.finditer(src):
            arg = am.group(1)
            if DEV_ONLY_MEDIA.search(src[max(0, am.start() - 1500): am.end()]):   # the enclosing function's opening lines
                continue                              # a local-dev voice server, never reached in production
            blobby = re.search(r"blob|createObjectURL|Blob\(", arg, re.I)
            need = "blob:" if blobby else storage
            if need and not _grants("media-src", need):
                line = src[: am.start()].count("\n") + 1
                problems.append(f"{name}:{line}: plays `new Audio({arg.strip()[:40]})` from "
                                f"{'an object URL' if blobby else 'the storage host ' + need}, which media-src does not "
                                f"grant{' (no media-src at all: media inherits default-src)' if 'media-src' not in csp else ''}"
                                f" - the person hears nothing")

    # ── the Permissions-Policy half ─────────────────────────────────────────────────────────────
    policy = parse_permissions_policy(headers)
    if policy:
        for feature, pattern in POLICY_FEATURES.items():
            users = []
            for path in files:
                nm = Path(path).name
                if VENDORED.search(nm):
                    continue
                body = io.open(path, encoding="utf-8", errors="replace").read()
                if pattern.search(body):
                    users.append(nm)
            if not users:
                continue
            allow = policy.get(feature)
            if allow is None:
                continue          # undeclared features default to allowing self
            if allow == "":
                problems.append(
                    f"{users[0]}: uses {feature}, and Permissions-Policy declares `{feature}=()` - an "
                    f"EMPTY allowlist denies every origin INCLUDING self, so the feature never "
                    f"starts in production ({len(users)} file(s) affected)")
            elif "self" not in allow and "*" not in allow:
                problems.append(
                    f"{users[0]}: uses {feature}, which Permissions-Policy grants only to "
                    f"`{allow}` - our own pages are not permitted")

    return problems, subresources, documented


def _self_test() -> int:
    good = ("  Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.ok.com; "
            "style-src 'self'; connect-src 'self' https://api.ok.com; worker-src 'self' blob:")
    page = '<script src="https://cdn.ok.com/a.js"></script>'
    bad_page = '<script src="https://evil.cdn.net/a.js"></script>'
    doc_ok = "/* Prod CSP needs connect-src https://api.ok.com + worker-src blob:. */"
    doc_bad = "/* Prod CSP needs connect-src https://tiles.missing.org. */"
    # a stylesheet link vs a preconnect/canonical link - only the first is a fetch we govern
    sheet = '<link rel="stylesheet" href="https://fonts.nope.com/x.css">'
    preconnect = '<link rel="preconnect" href="https://fonts.nope.com">'

    import tempfile
    cases = []
    with tempfile.TemporaryDirectory() as td:
        def mk(content):
            p = Path(td) / f"t{len(list(Path(td).iterdir()))}.html"
            p.write_text(content, encoding="utf-8")
            return [str(p)]
        cases = [
            ("permitted script passes", mk(page), 0),
            ("unpermitted script FAILs", mk(bad_page), 1),
            ("satisfied doc-requirement passes", mk(doc_ok), 0),
            ("unsatisfied doc-requirement FAILs", mk(doc_bad), 1),
            ("unpermitted stylesheet FAILs", mk(sheet), 1),
            ("preconnect is not a fetch, passes", mk(preconnect), 0),
        ]
        ok = True
        for label, files, expect in cases:
            probs, _, _ = audit(files, good)
            got = len(probs)
            hit = (got >= 1) == (expect >= 1)
            ok = ok and hit
            print(f"    {'ok ' if hit else 'BAD'}  {label}: {got} problem(s)")
        # a missing directive must be treated as inheriting default-src, not as permissive
        no_worker = "  Content-Security-Policy: default-src 'self'; script-src 'self'"
        probs, _, _ = audit(mk(doc_ok), no_worker)
        inherit_ok = any("declares no" in p for p in probs)
        print(f"    {'ok ' if inherit_ok else 'BAD'}  absent directive is a denial, not a pass")
        ok = ok and inherit_ok

        # ── Permissions-Policy: an empty allowlist denies SELF, which is the trap ──────────────
        geo_page = mk("navigator.geolocation.watchPosition(cb);")
        denied = good + "\n  Permissions-Policy: geolocation=()"
        granted = good + "\n  Permissions-Policy: geolocation=(self)"
        silent = good                                    # feature undeclared -> defaults to self
        empty_fails = any("EMPTY allowlist" in p for p in audit(geo_page, denied)[0])
        self_ok = not any("geolocation" in p for p in audit(geo_page, granted)[0])
        undeclared_ok = not any("geolocation" in p for p in audit(geo_page, silent)[0])
        for label, hit in (("empty allowlist FAILs", empty_fails),
                           ("(self) passes", self_ok),
                           ("undeclared feature is not flagged", undeclared_ok)):
            print(f"    {'ok ' if hit else 'BAD'}  permissions-policy: {label}")
            ok = ok and hit

        # ── capability (2026-10-14): a blob: image and a played audio, each against its directive ──────
        base = ("  Content-Security-Policy: default-src 'self'; img-src 'self' data: https:; "
                "connect-src 'self' https://abc.supabase.co")
        fixed = base.replace("img-src 'self' data: https:", "img-src 'self' data: blob: https:") + \
            "; media-src 'self' blob: https://abc.supabase.co"
        preview = mk("const u = URL.createObjectURL(file); if (previewImg) previewImg.src = u;")
        compress = mk("const img = new Image(); const url = URL.createObjectURL(file); img.src = url;")
        download = mk("const url = URL.createObjectURL(blob); a.href = url; a.download = 'x.csv';")
        tts = mk("const data = await r.json(); _audio = new Audio(data.url); _audio.play();")
        piper = mk("const blobUrl = URL.createObjectURL(new Blob([buf])); _audio = new Audio(blobUrl);")
        devtts = mk("const base = getEdgeTtsBase(); const u = base + data.url; _audio = new Audio(u);")
        cap = [("a blob: image preview FAILs without img-src blob:", any("blob:) as an image" in p for p in audit(preview, base)[0])),
               ("a compression Image() on a blob: FAILs too", any("blob:) as an image" in p for p in audit(compress, base)[0])),
               ("img-src blob: passes it", not audit(preview, fixed)[0]),
               ("a blob: download is not an image", not audit(download, base)[0]),
               ("storage audio FAILs with no media-src", any("storage host abc.supabase.co" in p for p in audit(tts, base)[0])),
               ("blob: audio FAILs with no media-src", any("an object URL" in p for p in audit(piper, base)[0])),
               ("media-src 'self' blob: <storage> passes both", not audit(tts, fixed)[0] and not audit(piper, fixed)[0]),
               ("a local-dev voice server is not owed a grant", not audit(devtts, base)[0])]
        for label, hit in cap:
            print(f"    {'ok ' if hit else 'BAD'}  capability: {label}")
            ok = ok and hit
        drift = parity(base, fixed)
        drift_ok = bool(drift) and not parity(fixed, fixed)
        print(f"    {'ok ' if drift_ok else 'BAD'}  parity: _headers != vercel.json FAILs ({len(drift)} directive(s))")
        ok = ok and drift_ok
    print(f"  self-test: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def vercel_policy_text(root: Path = ROOT) -> str:
    """vercel.json's CSP and Permissions-Policy in the `Name: value` form audit() reads - the policy that SHIPS.

    ★THIS GATE AUDITED THE FILE PRODUCTION NEVER READS (found 2026-10-14). It read `_headers`, the Cloudflare-format
    file the 2026-09-06 measurement proved INERT (workhiveph.com is Vercel; `_headers` now documents intent and
    vercel.json is what is served). So the realtime `wss:` fix landed in vercel.json alone, `_headers` drifted, and
    this gate kept checking a policy no browser received. It now audits vercel.json and fails when the two differ."""
    import json
    cfg = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
    out = []
    for blk in cfg.get("headers", []):
        for kv in blk.get("headers", []):
            if kv.get("key", "").lower() in ("content-security-policy", "permissions-policy") and \
                    not any(o.startswith(kv["key"]) for o in out):
                out.append(f"{kv['key']}: {kv['value']}")
    return "\n".join(out)


def per_page_audit() -> tuple[list, int]:
    """★EACH PAGE AGAINST ITS OWN POLICY (S3, 2026-10-15). vercel.json now serves every page the policy its own code
    needs (tools/build_csp_profiles.py), not one union for all, so auditing every file against the base rule checks a
    policy most pages are no longer served. Each served page's code (its HTML and every local script it loads) is
    audited against the headers the one matcher (serve_vercel_headers.headers_for) resolves for that page's path."""
    sys.path.insert(0, str(ROOT / "tools"))
    from build_csp_profiles import served_pages, code_closure   # noqa: E402
    from serve_vercel_headers import load_rules, headers_for     # noqa: E402
    rules = load_rules(ROOT)
    out, pages = [], 0
    for page in served_pages():
        hdr = headers_for("/" + page, rules)
        text = "\n".join(f"{k}: {v}" for k, v in hdr.items()
                         if k.lower() in ("content-security-policy", "permissions-policy"))
        files = [str(f) for f in code_closure(page) if not SKIP.search(f.name)]
        probs, _s, _d = audit(files, text)
        out += [f"{page} (its own policy): {p}" for p in probs]
        pages += 1
    return out, pages


def parity(intent: str, shipped: str) -> list:
    """Where `_headers` (the documented intent) and vercel.json (what ships) disagree, directive by directive."""
    out = []
    a, b = parse_csp(intent), parse_csp(shipped)
    for d in sorted(set(a) | set(b)):
        if a.get(d) != b.get(d):
            out.append(f"CSP {d}: _headers {' '.join(sorted(a.get(d) or [])) or '(absent)'} != vercel.json "
                       f"{' '.join(sorted(b.get(d) or [])) or '(absent)'}")
    if parse_permissions_policy(intent) != parse_permissions_policy(shipped):
        out.append("Permissions-Policy: _headers and vercel.json differ")
    return out


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()

    if not (ROOT / "vercel.json").exists():
        print("SKIP csp-covers-what-ships - no vercel.json at the repo root")
        return 0
    shipped = vercel_policy_text()

    files = [f for f in sorted(glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "*.js")))
             if not SKIP.search(Path(f).name)]
    if not files:
        print("FAIL csp-covers-what-ships - no shipped files found; the gate cannot measure nothing")
        return 1

    problems, subresources, documented = audit(files, shipped)
    page_problems, pages = per_page_audit()
    problems += page_problems
    headers_path = ROOT / "_headers"
    if headers_path.exists():
        problems += [f"drift - {d}" for d in parity(
            io.open(headers_path, encoding="utf-8", errors="replace").read(), shipped)]

    print(f"  external subresources declared in shipped code: {subresources} "
          f"| CSP requirements stated in source comments: {documented} "
          f"| files scanned: {len(files)} | served pages audited against their own policy: {pages}")

    if problems:
        print(f"FAIL csp-covers-what-ships - {len(problems)} shipped dependency(ies) the production "
              f"CSP blocks:")
        for p in problems[:12]:
            print("    - " + p)
        print("    The policy is PROD-ONLY: none of this fails locally, and the only symptom is a")
        print("    console message in someone else's browser. Grant exactly what ships, or stop")
        print("    shipping it.")
        return 1

    print(f"PASS csp-covers-what-ships - every external script/stylesheet, every CSP requirement written into the "
          f"source, every blob: image and every played audio is granted by the policy vercel.json SHIPS, and _headers "
          f"(the documented intent) matches it directive for directive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
