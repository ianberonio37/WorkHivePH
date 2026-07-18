#!/usr/bin/env python3
# DEEPWALK-CELL: * D23
# DEEPWALK-CELL: content:* D23
"""
validate_plain_language.py  --  LOCK against user-facing jargon / acronyms.

Ian (2026-07-06): "why is it we are using acronyms such as KYB, or any jargons, what is
also escrow? and so many more in my platforms?" The platform tagline is "Free Industrial
Tools for Every Filipino Worker" — the audience is the FULL spectrum (workers, technicians,
engineers, supervisors), not just engineers, so consumer-tech shorthand (KYB) and internal
engineering terms (RLS/IDOR/CRUD) must never reach the UI, and vestigial terms from the
REMOVED payment system (escrow/refund/commission — Stripe deleted 2026-06-30, marketplace is
free/contact-only) must be gone.

This gate scans the STATIC user-facing text of each page — headings, labels, static copy, and
visible attributes (alt/title/placeholder/aria-label) — after stripping <script>, <style>, and
<!-- comments -->. It does NOT scan code identifiers or comments, so DB columns like
`kyb_verified` and code like `RLS` in a JS comment are correctly ignored; only text a human
READS is checked.

NOTE (known gap): text generated inside JS template literals (e.g. dynamically-built badges) is
inside <script> and thus not scanned here — those are covered by manual review + the live
Playwright walk. This gate locks the large surface of STATIC copy (article prose, section
headings, static labels, meta descriptions) where most jargon actually lives.

Two severities:
  BLOCK  — never acceptable in any user-facing copy (fails the gate).
  WARN   — legitimate industrial-domain term; allowed, but should be expanded on first use.

Usage:  python tools/validate_plain_language.py [--json] [--warn] [--selftest]
Exit 0 = clean (no BLOCK hits), 1 = BLOCK hits found (or self-test failure).
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent

# BLOCK: consumer-tech jargon + internal engineering terms + removed-payment vestige.
# Each entry: display token (regex, case-sensitive unless noted) -> plain-language guidance.
BLOCK = [
    (r"\bKYB\b",                 "say 'ID-verified' / 'Verified seller' (KYB = engineering shorthand)"),
    (r"(?i)\bescrow\b",          "REMOVED payment system — marketplace is free/contact-only since 2026-06-30"),
    (r"(?i)\b2307\b",            "removed-payment tax jargon; marketplace is free/contact-only"),
    (r"(?i)\bIDOR\b",            "internal security term — never user-facing"),
    (r"\bRLS\b",                 "internal security term (row-level security) — never user-facing"),
    (r"(?i)\bidempoten\w*\b",    "internal engineering term — never user-facing"),
    (r"\btsvector\b",            "internal DB term — never user-facing"),
    (r"\bIDaaS\b",               "internal jargon — say 'sign-in'"),
    (r"\bGMV\b",                 "removed-payment metric (gross merchandise value) — say 'sales'"),
]

# WARN: real industrial-maintenance terms the engineer audience uses — allowed, but the FULL
# audience needs a first-use expansion (e.g. "MTBF (mean time between failures)").
WARN = [
    (r"\bMTBF\b", "mean time between failures"),
    (r"\bMTTR\b", "mean time to repair"),
    (r"\bOEE\b",  "overall equipment effectiveness"),
    (r"\bRCM\b",  "reliability-centered maintenance"),
    (r"\bFMEA\b", "failure modes and effects analysis"),
    (r"\bLOTO\b", "lock-out / tag-out"),
    (r"\bRUL\b",  "remaining useful life"),
    (r"\bP-F\b",  "potential-to-functional-failure interval"),
]

# PENDING content review exemptions (empty). The marketplace MARKETING articles that described
# the REMOVED paid-escrow model were rewritten to the free/contact-only reality on 2026-07-06
# (Ian approved the full rewrite), so NO page is exempt — the gate enforces plain language with
# zero exceptions. Re-add a (page, term) pair here only for a genuine, reviewed exception.
PENDING_REVIEW = {}

SCRIPT_RE  = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
STYLE_RE   = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
# visible attributes whose values a user reads
ATTR_RE    = re.compile(r"""\b(?:alt|title|placeholder|aria-label)\s*=\s*(['"])(.*?)\1""", re.S | re.I)
TAG_RE     = re.compile(r"<[^>]+>")


def app_pages():
    skip = ("-test.html", "backup", "offline-fallback", "symbol-gallery")
    seen = set()
    # root app pages + learn/about/policy content pages (all user-facing)
    for pat in ("*.html", "learn/**/*.html", "about/**/*.html",
                "privacy-policy/**/*.html", "terms-of-service/**/*.html"):
        for p in sorted(ROOT.glob(pat)):
            if any(s in p.name or s in str(p) for s in skip):
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p


def visible_text(html):
    """Static user-facing text: strip script/style/comments, keep tag text + visible attrs."""
    attrs = " ".join(m.group(2) for m in ATTR_RE.finditer(html))
    body = COMMENT_RE.sub(" ", html)
    body = SCRIPT_RE.sub(" ", body)
    body = STYLE_RE.sub(" ", body)
    body = TAG_RE.sub(" ", body)
    return body + " \n " + attrs


def scan_text(text):
    block_hits, warn_hits = [], []
    for pat, guide in BLOCK:
        for m in re.finditer(pat, text):
            block_hits.append((m.group(0), guide))
    for pat, exp in WARN:
        if re.search(pat, text):
            warn_hits.append((re.search(pat, text).group(0), exp))
    return block_hits, warn_hits


def scan(path):
    html = path.read_text(encoding="utf-8", errors="ignore")
    text = visible_text(html)
    return scan_text(text)


def selftest():
    cases = [
        ("block: static KYB heading", "<h2>KYB-Verified Sellers</h2>", True),
        ("block: escrow in prose", "<p>funds held in escrow until release</p>", True),
        ("ok: kyb_verified DB column in a comment", "<!-- select kyb_verified from sellers -->", False),
        ("ok: RLS inside a <script>", "<script>// RLS policy check\nconst x=1;</script>", False),
        ("ok: plain verified copy", "<h2>ID-Verified Sellers</h2>", False),
    ]
    ok = True
    for name, html, expect_block in cases:
        block, _ = scan_text(visible_text(html))
        got = bool(block)
        status = "PASS" if got == expect_block else "FAIL"
        if got != expect_block:
            ok = False
        print(f"  selftest {status}: {name} (expected block={expect_block}, got={got})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("plain-language selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    show_warn = "--warn" in sys.argv
    block_report, warn_report = {}, {}
    for p in app_pages():
        block, warn = scan(p)
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        exempt = {t.lower() for t in PENDING_REVIEW.get(rel, set())}
        if exempt:
            block = [(t, g) for (t, g) in block if t.lower() not in exempt]
        if block:
            block_report[rel] = block
        if warn:
            warn_report[rel] = warn
    total_block = sum(len(v) for v in block_report.values())
    if as_json:
        print(json.dumps({
            "block_hits": total_block,
            "block": {k: [{"term": t, "fix": g} for t, g in v] for k, v in block_report.items()},
            "warn_pages": {k: sorted({t for t, _ in v}) for k, v in warn_report.items()},
        }, indent=2))
    else:
        print("plain-language (no consumer-tech jargon / removed-payment vestige in user-facing copy)")
        if not block_report:
            print(f"  PASS: 0 BLOCK-level jargon terms in static user copy across {len(list(app_pages()))} pages")
        else:
            print(f"  FAIL: {total_block} BLOCK-level jargon term(s) in user-facing copy across {len(block_report)} page(s):")
            for page, hits in block_report.items():
                terms = ", ".join(sorted({t for t, _ in hits}))
                print(f"    {page}  ->  {terms}")
        if show_warn and warn_report:
            print(f"  WARN: {len(warn_report)} page(s) use industrial acronyms (expand on first use):")
            for page, hits in warn_report.items():
                print(f"    {page}: {', '.join(sorted({t for t, _ in hits}))}")
    return 1 if block_report else 0


if __name__ == "__main__":
    sys.exit(main())
