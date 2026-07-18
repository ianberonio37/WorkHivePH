"""
validate_pareto_content.py  —  Arc P (Pareto Page Revamp) content gate.
================================================================================
Measures the P1-P6 Pareto rubric statically across every user-facing nav page and
the shared JS renderers, and RATCHETS the one hard signal Ian named: DISPLAYED
DEFENSIVE COPY count = 0 platform-wide ("kill 'we won't fake this'").

WHY THIS EXISTS / the R0 lesson it encodes (2026-07-02 live walk, PARETO_R0_FINDINGS.md):
  The defensive-copy §2 priors were 3x over-counted because a naive grep hit THREE
  non-displayed sources: (1) JS **code comments**, (2) **JSON-LD** structured-data
  duplicates, (3) embedded **AI system prompts**. And the WORST real offender is
  NOT in any HTML at all — it's a template literal in `maturity-gate.js`
  (`<h1>We won't fake this.</h1>`, rendered on 5 pages). So this gate:
    - HTML: strips <script>, <style>, <!-- -->, and JSON-LD BEFORE counting, then
      scans the remaining VISIBLE text.
    - JS:  strips // and /* */ comments, then scans the remaining code (natural-
      language lexicon only matches inside string/template literals) — this is how
      the shared-renderer "We won't fake this" is caught.
  => match RENDERED/displayed text only, never comments or machine-data blocks.

THE SIGNALS (skill_devops: split HARD-defect from RATCHET; AUDIT distinct from VALIDATOR):
  HARD / RATCHET (gates):  total DISPLAYED defensive-phrase count. Baseline is
    frozen in pareto_content_baseline.json and obeys Rule B (auto-tightens DOWN on
    reduction; FAILS only when the count RISES above baseline). Exit target = 0
    (roadmap §2 "P4 gate floor = 0 platform-wide"). Starts as a ratchet because
    Wave 0 (the maturity-gate.js fix) hasn't landed yet.
  REPORTED (informational, per page — the P1/P2/P3 instruments for the revamp waves,
    NOT hard-gated because they need a browser to score precisely):
      visible_words, has_verdict_marker (P1), primary_cta_count (P3),
      snakecase_in_text (P4 raw-DB-name leak), long_inline_list flag (P2).

USAGE:
  python validate_pareto_content.py                 # report to stdout + JSON, exit 0
  python validate_pareto_content.py --gate          # ratchet: exit 1 if defensive RISES
  python validate_pareto_content.py --update-baseline  # freeze current as the new baseline

OUTPUTS:
  pareto_content_report.json    — machine-readable per-file findings + metrics
  pareto_content_baseline.json  — frozen ratchet baseline (Rule B)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

# Windows cp1252 console can't encode the box/arrow glyphs — same guard as the
# other tools. The .json files are written UTF-8 regardless.
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "pareto_content_report.json"
BASELINE = ROOT / "pareto_content_baseline.json"

# ── SCOPE ─────────────────────────────────────────────────────────────────────
# Auto-discover so a NEW page can't slip past the gate. Root HTML = the user-facing
# surfaces (mirror of nav-hub.js "ALL TOOLS"); root JS = shared renderers that
# inject user-facing copy (maturity-gate.js is why the JS scan exists). The
# out-of-scope set matches PARETO_PAGE_REVAMP_ROADMAP.md §3 (test/backup/utility).
HTML_EXCLUDE = re.compile(
    r"(-test|\.backup|^status|^symbol-gallery|^validator-catalog|^promo-poster|^offline-fallback|^test-)",
    re.IGNORECASE,
)
JS_EXCLUDE = re.compile(r"(\.min\.js$|\.test\.|\.spec\.)", re.IGNORECASE)
# R0 lesson #3 (PARETO_R0_FINDINGS.md): embedded AI SYSTEM PROMPTS are string
# literals indistinguishable from UI strings by regex, but they are LLM
# instructions, NOT displayed copy — so "honestly/honest answer" inside them is
# legitimate prompt-engineering, not a P4 defect. These files hold the companion's
# system prompt + knowledge base; exclude them from the displayed-copy scan. (The
# DOM renderers like maturity-gate.js stay IN scope — that's the whole point.)
JS_PROMPT_FILES = {"voice-handler.js", "companion-launcher.js"}

# ── P4 DISPLAYED-DEFENSIVE LEXICON ──────────────────────────────────────────────
# Precise, natural-language patterns that only match displayed copy (not code).
# Each is the anti-pattern class the roadmap §2 names: prior-fakery implications +
# distrust-signalling hedges + internal-QA voice leaking to the UI.
DEFENSIVE = [
    (re.compile(r"\bwe\s+won'?t\s+fake\b", re.I),           "won't fake (implies prior fakery)"),
    (re.compile(r"\bwon'?t\s+fake\s+th", re.I),             "won't fake this"),
    (re.compile(r"\bnot\s+faking\b", re.I),                  "not faking"),
    (re.compile(r"\brefuses?\s+to\s+(fake|show|fabricate)", re.I), "refuse to fake/show (defensive)"),
    (re.compile(r"\bwe\s+refuse\s+to\b", re.I),              "we refuse to (defensive)"),
    (re.compile(r"\bwould\s+mislead\b", re.I),               "would mislead (distrust framing)"),
    (re.compile(r"\bhonest\s+empty\s+state\b", re.I),        "HONEST EMPTY STATE (internal-QA voice in UI)"),
    (re.compile(r"\bhonest\s+answer\b", re.I),               "honest answer (hedge)"),
    (re.compile(r"\bhonestly[,\.\s]", re.I),                 "honestly (hedge)"),
    (re.compile(r"\bto\s+be\s+honest\b", re.I),              "to be honest (hedge)"),
    (re.compile(r"\btrust\s+us\b", re.I),                    "trust us (distrust signal)"),
    (re.compile(r"\bwe\s+promise\b", re.I),                  "we promise (hedge)"),
    (re.compile(r"\bfor\s+real\b(?![\w-])", re.I),           "for real (hedge)"),
    (re.compile(r"\bno\s+BS\b", re.I),                       "no BS (hedge)"),
]

# P1 verdict/keypoint markers (a page PASSES glance-first when one is present near top)
VERDICT_MARKERS = re.compile(
    r"(what\s+to\s+do\s+next|all\s+clear|needs\s+your\s+attention|at\s+risk|verdict|"
    r"key\s+points?|headline|executive\s+summary|stacking\s+up|on\s+track)",
    re.I,
)
# P3 primary-CTA styling heuristics (solid-orange primary is the platform convention)
PRIMARY_CTA = re.compile(r"class=\"[^\"]*(btn-primary|primary-cta|cta-primary|wh-btn-primary)[^\"]*\"", re.I)
# P4 raw-DB-name leak: snake_case token in a VISIBLE text node (rough; reported, not gated)
SNAKE = re.compile(r"\b[a-z]{2,}_[a-z][a-z_]*\b")
SNAKE_ALLOW = {"target_type", "utm_source", "utm_medium"}  # tolerated / not user-copy


def strip_js_comments(js: str) -> str:
    """Remove // line and /* */ block comments so the lexicon only hits string
    literals (the false-positive lesson: comments over-counted 'honest'/'not just')."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    js = re.sub(r"(^|[^:])//[^\n]*", r"\1 ", js)  # keep http:// intact (needs a non-: prefix)
    return js


def html_visible_text(html: str) -> str:
    """Displayed text only: drop <script> (incl JSON-LD), <style>, <!-- -->, tags."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def html_inline_scripts(html: str) -> str:
    """Inline <script> bodies EXCEPT application/ld+json (JSON-LD = machine data,
    R0 false-positive #2). Needed because pages inject defensive copy via a JS
    call — e.g. ph-intelligence/ai-quality pass their own 'we refuse to…' `why`
    string to renderMaturityHonestEmpty() from an inline script."""
    out = []
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"type\s*=\s*[\"']application/ld\+json", attrs, re.I):
            continue
        out.append(body)
    return "\n".join(out)


def scan_text(text: str, source: str):
    hits = []
    for rx, label in DEFENSIVE:
        for m in rx.finditer(text):
            s = max(0, m.start() - 30)
            e = min(len(text), m.end() + 30)
            hits.append({"source": source, "label": label,
                         "match": m.group(0), "context": text[s:e].strip()})
    return hits


def main():
    ap = argparse.ArgumentParser(description="Arc P Pareto content gate (defensive-copy ratchet + P1-P6 metrics)")
    ap.add_argument("--gate", action="store_true", help="ratchet mode: exit 1 if defensive count RISES above baseline")
    ap.add_argument("--update-baseline", action="store_true", help="freeze current counts as the new baseline")
    args = ap.parse_args()

    html_files = sorted(p for p in ROOT.glob("*.html") if not HTML_EXCLUDE.search(p.name))
    js_files = sorted(p for p in ROOT.glob("*.js")
                      if not JS_EXCLUDE.search(p.name) and p.name not in JS_PROMPT_FILES)

    all_hits = []
    per_file = {}
    metrics = {}

    for p in html_files:
        raw = p.read_text(encoding="utf-8", errors="replace")
        text = html_visible_text(raw)
        hits = scan_text(text, p.name)
        # Scan the page's inline JS ONLY when it invokes the maturity-gate renderer
        # — that's the single known inline injection of defensive copy (the caller
        # `why` overrides on ph-intelligence/ai-quality). This deliberately skips
        # pages that embed an AI SYSTEM PROMPT inline (e.g. assistant.html), whose
        # "honestly/honest" is prompt-engineering, not displayed copy (R0 lesson #3).
        if re.search(r"renderMaturityHonestEmpty|checkMaturityGate|MaturityHonestEmpty", raw):
            hits += scan_text(strip_js_comments(html_inline_scripts(raw)), p.name + " (inline js)")
        per_file[p.name] = len(hits)
        all_hits.extend(hits)
        words = text.split()
        snake = sorted({t for t in SNAKE.findall(text) if t not in SNAKE_ALLOW})
        metrics[p.name] = {
            "visible_words": len(words),
            "has_verdict_marker": bool(VERDICT_MARKERS.search(text)),   # P1
            "primary_cta_count": len(PRIMARY_CTA.findall(raw)),          # P3
            "snakecase_in_text": snake[:12],                            # P4 raw-DB leak
            "defensive": len(hits),
        }

    for p in js_files:
        raw = p.read_text(encoding="utf-8", errors="replace")
        code = strip_js_comments(raw)
        hits = scan_text(code, p.name)
        if hits or p.name in ("maturity-gate.js",):
            per_file[p.name] = len(hits)
        all_hits.extend(hits)

    defensive_total = len(all_hits)

    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    base_total = base.get("defensive_total")

    report = {
        "generated": "static-scan",
        "defensive_total": defensive_total,
        "baseline_total": base_total,
        "per_file": {k: v for k, v in sorted(per_file.items()) if v},
        "hits": all_hits,
        "metrics": metrics,
        "html_scanned": len(html_files),
        "js_scanned": len(js_files),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ── console ──
    print(f"\n  Arc P — Pareto content gate")
    print(f"  {'-'*54}")
    print(f"  HTML pages scanned : {len(html_files)}")
    print(f"  JS renderers scanned: {len(js_files)}")
    print(f"  DISPLAYED defensive-copy phrases: {defensive_total}"
          + (f"  (baseline {base_total})" if base_total is not None else "  (no baseline yet)"))
    if report["per_file"]:
        print(f"\n  Defensive copy by file:")
        for f, n in sorted(report["per_file"].items(), key=lambda kv: -kv[1]):
            print(f"    {n:>3}  {f}")
        # show the shared-component finding explicitly
        for h in all_hits[:12]:
            print(f"      - [{h['source']}] {h['label']}: \"{h['match']}\"")
    else:
        print("  P4 FLOOR MET: 0 displayed defensive phrases platform-wide.")

    # ── baseline write / ratchet ──
    if args.update_baseline:
        BASELINE.write_text(json.dumps({"defensive_total": defensive_total, "per_file": per_file}, indent=2),
                            encoding="utf-8")
        print(f"\n  Baseline frozen at {defensive_total} defensive phrases.")
        return 0

    if args.gate:
        if base_total is None:
            # first run establishes the ratchet floor
            BASELINE.write_text(json.dumps({"defensive_total": defensive_total, "per_file": per_file}, indent=2),
                                encoding="utf-8")
            print(f"\n  [GATE] baseline established at {defensive_total}. Target = 0 (Wave 0).")
            return 0
        if defensive_total > base_total:
            print(f"\n  [GATE] FAIL — defensive copy ROSE {base_total} -> {defensive_total}. "
                  f"New defensive phrase introduced; revert or rewrite it confidently.")
            return 1
        if defensive_total < base_total:
            # Rule B: auto-tighten DOWN
            BASELINE.write_text(json.dumps({"defensive_total": defensive_total, "per_file": per_file}, indent=2),
                                encoding="utf-8")
            print(f"\n  [GATE] PASS + ratchet TIGHTENED {base_total} -> {defensive_total}. ")
            return 0
        print(f"\n  [GATE] PASS (held at {defensive_total}).")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
