#!/usr/bin/env python3
"""Arc P · P4 lens — NO EM DASH in displayed copy (the standing no-em-dash rule).

Em dashes are banned in user-facing product copy (use colons, commas, parentheses,
or restructure). They hide in three displayed surfaces that the empty-state walks
miss: (1) static HTML text, (2) title=/aria-label=/placeholder= attribute values,
(3) inline <script> DISPLAY strings (verdict/action/toast render literals — where
the ph-intelligence/ai-quality em dashes lived).

This is a candidate FINDER: it reports prose em dashes for human disposition, and
ratchets on the count (Rule B: FAILS only when the displayed em-dash count RISES
above the frozen baseline; auto-tightens DOWN as pages are cleaned). Placeholder /
decorator glyphs (a lone "—" in an empty element or bracketing "— none —") are
excluded — only PROSE em dashes (a word on BOTH sides of one dash) are counted.

Usage:
  python validate_no_em_dash.py                 # report + metrics
  python validate_no_em_dash.py --gate          # ratchet: exit 1 if count RISES
  python validate_no_em_dash.py --update-baseline
"""
from __future__ import annotations
import argparse, json, re, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "no_em_dash_report.json"
BASELINE = ROOT / "no_em_dash_baseline.json"

# Same user-facing scope as the pareto gate (test/backup/utility surfaces excluded).
HTML_EXCLUDE = re.compile(
    r"(-test|\.backup|^status|^symbol-gallery|^validator-catalog|^promo-poster|^offline-fallback|^test-)",
    re.IGNORECASE,
)
# Non-display JS files (AI system prompts / knowledge base): em dashes there are not UI copy.
# wh-persona.js builds the AI persona/system-prompt block (window.getCompanionBlock() prepends it
# to the model prompt — never rendered to the DOM), exactly like voice-handler/companion-launcher.
JS_PROMPT_FILES = {"voice-handler.js", "companion-launcher.js", "wh-persona.js"}
# Non-display JS: test harnesses / batteries / validators / specs are internal tooling,
# not user-facing product copy — their em dashes are out of the P4 rule's scope.
JS_NONDISPLAY_FILE = re.compile(r"(battery|harness|validator|_test|\.test\.|\.spec\.|mega[_-]?gate|survey_ufai_rubric)", re.I)

# PROSE em dash: a 2+ letter word, then <=40 non-dash/non-tag chars, an em dash,
# then <=40 non-dash/non-tag chars, then another 2+ letter word. Excludes lone
# placeholder glyphs (">—<") and "— none —" decorators (no letter-word straddling
# a SINGLE dash within the same text run).
PROSE_EMDASH = re.compile(r"[A-Za-z]{2,}[^—<>\n]{0,40}—[^—<>\n]{0,40}[A-Za-z]{2,}")

# JS lines that are clearly NOT displayed copy (avoid false positives on the JS scan).
# A regex-method call (.replace(/…/)/.match(/…/) etc.) with an em-dash is a REGEX char-class (code,
# e.g. wayfinding's title-strip /[·|—-]/), never displayed — skip those lines.
JS_NONDISPLAY = re.compile(
    r"(console\.|throw\s|//|/\*|https?:|\bimport\b|\brequire\(|\.(?:replace|match|test|split|search|exec)\(\s*/)",
    re.I,
)


def strip_js_comments(js: str) -> str:
    # HTML comments live inside JS template literals that build markup (nav-hub.js etc.);
    # they are comments, never rendered — strip them so they aren't counted as display copy.
    js = re.sub(r"<!--.*?-->", " ", js, flags=re.S)
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    js = re.sub(r"(^|[^:])//[^\n]*", r"\1 ", js)
    return js


def html_text_runs(html: str) -> list[str]:
    """Individual displayed text RUNS (the text between one tag and the next), NOT a
    collapsed blob. Per-run matters: collapsing joins distinct UI elements (a "Loading"
    stat card + a "Past end date" card) so a placeholder "—" between them false-matches
    as prose. Scanning each run means a lone "—" element (or "—" adjacent to a tag) has
    no straddling word and is correctly ignored; only a real in-sentence em dash flags."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    runs = []
    for run in re.split(r"<[^>]+>", html):
        run = re.sub(r"\s+", " ", run).strip()
        if run and "—" in run:
            runs.append(run)
    return runs


def attr_values(html: str) -> str:
    """title= / aria-label= / placeholder= values — displayed (tooltip / a11y / hint)."""
    vals = []
    for m in re.finditer(r'(?:title|aria-label|placeholder)\s*=\s*"([^"]*)"', html, re.I):
        vals.append(m.group(1))
    return " • ".join(vals)


def inline_js_display(html: str) -> str:
    """Inline <script> bodies (minus JSON-LD + comments), line-filtered to drop
    obvious non-display lines (console/throw/imports/urls) so the em-dash scan
    lands on render/toast/verdict string literals, not internal messages."""
    out = []
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"type\s*=\s*[\"']application/ld\+json", attrs, re.I):
            continue
        body = strip_js_comments(body)
        for line in body.splitlines():
            if "—" in line and not JS_NONDISPLAY.search(line):
                out.append(line.strip())
    return "\n".join(out)


# Calc-type IDENTITY keys (used in === comparisons + as object keys; whCalcLabel colon-renders them
# for display, so the em-dash is NEVER shown to a user). Memento (project_pareto_page_revamp_arc):
# changing these strings BREAKS LOGIC — so they are EXCLUDED here, not "fixed". Any NEW calc-type must
# use a colon, not an em-dash, in its id.
CALC_ID_EMDASH = ("System — Air Cooled", "System — Water Cooled")


def scan(text: str, source: str, sink: list):
    for m in PROSE_EMDASH.finditer(text):
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        if any(cid in s for cid in CALC_ID_EMDASH):
            continue  # internal colon-rendered calc-id key, never displayed as an em-dash
        sink.append({"source": source, "context": s})


def main():
    ap = argparse.ArgumentParser(description="Arc P no-em-dash displayed-copy ratchet")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    html_files = sorted(p for p in ROOT.glob("*.html") if not HTML_EXCLUDE.search(p.name))
    js_files = sorted(p for p in ROOT.glob("*.js")
                      if p.name not in JS_PROMPT_FILES and not p.name.endswith(".min.js")
                      and not JS_NONDISPLAY_FILE.search(p.name))

    per_file: dict[str, list] = {}
    total = 0
    for p in html_files:
        raw = p.read_text(encoding="utf-8", errors="replace")
        # Normalize entity-encoded em dashes so the scan catches them too (the literal-char
        # scan missed &mdash; in project-report.html's Appendix heading, 2026-07-03).
        raw = raw.replace('&mdash;', '—').replace('&#8212;', '—').replace('&#x2014;', '—')
        hits: list = []
        for run in html_text_runs(raw):
            scan(run, "text", hits)
        scan(attr_values(raw), "attr", hits)
        scan(inline_js_display(raw), "js", hits)
        if hits:
            per_file[p.name] = hits
            total += len(hits)
    for p in js_files:
        raw = p.read_text(encoding="utf-8", errors="replace").replace('&mdash;', '—').replace('&#8212;', '—').replace('&#x2014;', '—')
        raw = strip_js_comments(raw)
        hits = []
        for line in raw.splitlines():
            if "—" in line and not JS_NONDISPLAY.search(line):
                scan(line, "js", hits)
        if hits:
            per_file[p.name] = per_file.get(p.name, []) + hits
            total += len(hits)

    REPORT.write_text(json.dumps({"total": total, "per_file": {k: v for k, v in sorted(per_file.items(), key=lambda kv: -len(kv[1]))}}, indent=2, ensure_ascii=False), encoding="utf-8")

    base = 0
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text(encoding="utf-8")).get("total", 0)

    out = sys.stdout
    out.write("\n  Arc P — No-Em-Dash displayed-copy gate\n")
    out.write("  " + "-" * 54 + "\n")
    out.write(f"  pages/files with displayed em dashes: {len(per_file)}\n")
    out.write(f"  PROSE em dashes in displayed copy: {total}  (baseline {base})\n")
    for f, hits in sorted(per_file.items(), key=lambda kv: -len(kv[1]))[:12]:
        out.write(f"    {len(hits):>3}  {f}\n")

    if args.update_baseline:
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")
        out.write(f"\n  Baseline frozen at {total}.\n")
        return 0
    if args.gate:
        if total > base:
            out.write(f"\n  FAIL — displayed em dashes ROSE {base} -> {total} (Rule B ratchet).\n")
            return 1
        if total < base:
            BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")
            out.write(f"\n  PASS + auto-tightened baseline {base} -> {total}.\n")
        else:
            out.write(f"\n  PASS — held at {total}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
