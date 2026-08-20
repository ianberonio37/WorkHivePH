"""
Em-Dash Validator — WorkHive Platform
======================================
Enforces the standing rule [[feedback-no-em-dashes]]: every public page must
use colons, commas, parentheses, or restructure instead of em dashes (` — `).

Em dashes degrade the natural-language quality of AI-generated answer
extraction (Perplexity, ChatGPT) and look inconsistent with our copy style.
This validator catches regressions before they ship.

What counts as a violation: any literal em-dash character (`—`, U+2014)
appearing inside visible body text. We skip JSON-LD blocks because schema.org
authors sometimes legitimately use em-dashes inside `description` strings,
but flag everything in HTML body / paragraph / heading text.

Usage:  python validate_em_dash.py
Output: em_dash_report.json
"""
import re, json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result
from wh_pages import all_public_pages

ALL_PUBLIC = all_public_pages()

# Em-dash characters: U+2014 and the rarer U+2013 (en-dash) when surrounded
# by spaces (the visible " – " pattern). We DO NOT flag bare hyphens.
# An en-dash only counted when SPACE-WRAPPED, which is not how real copy writes a range:
# index.html ships "₱800K–₱2.4M in knowledge walks out the door" in marketing text and
# "Username must be 3–30 characters" in a message a person reads, and BOTH slipped through.
# A bare en-dash between word characters is the range form, so it is caught now too.
EM_DASH_RE = re.compile(r"[—–]")  # ANY em/en dash: the name says "no em or en dashes", and now that block + trailing comments and the placeholder glyph are stripped, no qualifier is needed

# Strip JSON-LD <script type="application/ld+json">...</script> blocks first
# because schema authors sometimes legitimately use em-dashes inside strings.
JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>.*?</script>',
    re.DOTALL | re.IGNORECASE,
)

# Strip HTML comments — they're authoring notes (e.g. `canonical-allow: ...`),
# not user-visible body text, and authors legitimately use em-dashes inside
# them for readability. AEO/GEO crawlers don't index comment content.
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")

# Strip JS line comments — same logic: code comments are not user-visible
# body text. `canonical-allow:` markers and developer notes routinely
# contain em-dashes for readability.
# Line comments were only stripped when the // started the LINE, so a TRAILING comment
# (`const d = x; // 4–6s`) still counted as body text -- and /* */ BLOCK comments were never
# stripped at all, so two long contrast notes in index.html were reported as public copy.
# Measured 2026-08-20: all 3 of this gate's hits on index.html were comments or the
# placeholder glyph, while the 2 REAL user-visible en-dashes went unreported. Same rationale
# the file already states: code comments are not user-visible body text.
JS_LINE_COMMENT_RE = re.compile(r"(?<!:)//[^\n]*")
JS_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
# The platform renders a bare em-dash as its EMPTY-VALUE glyph (textContent = "—"). That is a
# UI convention, not prose, so it is not a violation.
PLACEHOLDER_GLYPH_RE = re.compile(r"""['"]—['"]""")


def check_em_dashes(pages):
    """Every public page must use plain ASCII punctuation, no em or en dashes
    in body text. Reason: AEO/GEO answer-extraction quality + brand voice."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Strip JSON-LD blocks + HTML comments + JS line comments before scanning
        scannable = JSON_LD_RE.sub("", content)
        scannable = HTML_COMMENT_RE.sub("", scannable)
        scannable = JS_BLOCK_COMMENT_RE.sub("", scannable)
        scannable = JS_LINE_COMMENT_RE.sub("", scannable)
        scannable = PLACEHOLDER_GLYPH_RE.sub("", scannable)
        matches = list(EM_DASH_RE.finditer(scannable))
        if matches:
            # Sample first 3 matches with surrounding context for the report
            samples = []
            for m in matches[:3]:
                start = max(0, m.start() - 35)
                end   = min(len(scannable), m.end() + 35)
                snippet = scannable[start:end].replace("\n", " ").strip()
                samples.append(snippet)
            sample_text = " | ".join(samples)
            issues.append({"check": "em_dashes", "page": page,
                           "reason": (f"{page} has {len(matches)} em-dash(es). "
                                      f"Use colons, commas, parentheses, or restructure. "
                                      f"Samples: {sample_text}")})
    return issues


CHECK_NAMES  = ["em_dashes"]
CHECK_LABELS = {"em_dashes": "L1  No em or en dashes in public body text"}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEm-Dash Validator"))
    print("=" * 55)

    all_issues = check_em_dashes(ALL_PUBLIC)
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed across {len(ALL_PUBLIC)} pages.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "em_dash",
        "total_checks": len(CHECK_NAMES),
        "pages_scanned": len(ALL_PUBLIC),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("em_dash_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
