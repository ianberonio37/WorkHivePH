"""
User-Facing Jargon Validator (L0, ratcheted) — STREAMLINE §13/§14 E1.
======================================================================
Ian, with screenshots (2026-06-14): "why do we have these sloppy details in my
platform… irrelevant details my users can't even understand." Dashboard captions
were leaking the platform's INTERNALS onto the glass — DB view names, RPC/edge-fn
names, code identifiers, internal doc filenames, raw SQL predicates — e.g.

  Source: v_logbook_truth + v_risk_truth · PMs Overdue: shared _pmOverdueCount
  (from loadPMHealth) · Stock Issues: qty_on_hand <= 0 OR qty_on_hand <= min_qty
  · Empty values dimmed via hideZeroStat() · see KPI_ENGINE.md

A Filipino plant supervisor/technician cannot read ANY of that. The provenance
layer is a GOOD principle (show where a number came from = trust + anti-fabrication),
but each string was authored in ENGINEER voice. This gate keeps jargon off the glass
forward-only, the same S12/D7-style ratchet used elsewhere.

WHAT IT SCANS (user-VISIBLE strings only)
  (a) renderSourceChip({...}) calls — the `freshness`, `window`, and `notes[]`
      fields ONLY. The `source:` field is EXEMPT: it stays canonical (raw view
      names) because validate_source_chip_truth.py verifies it against real
      .from() reads, and renderSourceChip TRANSLATES it through WH_SOURCE_LABELS
      at render time (utils.js), so the user never sees the raw name. That is the
      single sanctioned channel for a v_*_truth token.
  (b) Visible HTML body text — the "How these are derived" / data-source explainer
      <details> blocks and any static <p class="wh-source-chip"> prose.

WHAT IT IGNORES (not user-visible)
  - <script>, <style>, HTML comments, JS // and /* */ comments
  - <code> and <pre> blocks (intentional code samples)
  - the renderSourceChip `source:` field (see above)
  - an inline `jargon-allow: <reason>` marker within ±400 chars (documented opt-out)

FORBIDDEN CLASSES (FAIL) — the platform internals, never for users
  view      : v_<name>_truth                              -> WH_SOURCE_LABELS label
  snake_id  : lower_snake_case ident (column/table/enum)  -> plain words
  upper_id  : UPPER_SNAKE constant / SQL keyword token     -> plain words
  camel_id  : camelCase / _camelCase helper ident          -> plain words
  call      : someFunc()                                    -> plain words
  doc       : *.md internal doc reference                   -> remove or link a help page
  plumbing  : "edge fn", "via Postgres RPCs", named edge fns

Output
  user_facing_jargon_report.json (machine)
  user_facing_jargon_baseline.json (ratchet floor)
  Exit 1 when total > baseline; 0 otherwise.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT          = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "user_facing_jargon_report.json"
BASELINE_PATH = ROOT / "user_facing_jargon_baseline.json"
PROV_PATH     = ROOT / "display_provenance.json"
IMPACT_PATH   = ROOT / "field_impact_preview.json"

# Pages with user-facing dashboard chrome. Mirrors validate_source_chip_truth.py's
# list; any *.html with renderSourceChip is also picked up via the glob below.
PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
    "engineering-design.html",
]

# Internal OPS / ADMIN dashboards — these DOCUMENT the platform's internals by
# design (they list validators by their .py filename, show EXPECTED_SCHEMA dicts,
# etc.) and are founder-gated, never shown to a plant supervisor/technician. They
# are not "the glass" the jargon audit is about, so they're out of scope.
EXCLUDE_PAGES = {
    "platform-health.html",
    "founder-console.html",
    # admin/dev/ops internal pages — technical terms ARE the plain language for these audiences
    # (same cohort already exempted from i18n; not worker-facing "glass"). 2026-07-18.
    "agentic-rag-observability.html",  # isPlatformAdmin AI-observability dashboard
    "design-system.html",              # internal dev/design component showcase
    "status.html",                     # internal ops status page
}

# ── Forbidden-pattern classes ────────────────────────────────────────────────
# Each is (class_name, compiled regex). Order matters: `view` before `snake_id`
# so a v_*_truth token is reported as the more specific class.
RULES = [
    ("view",     re.compile(r"\bv_[a-z0-9_]+_truth\b")),
    # named edge fns / RPC plumbing phrases
    ("plumbing", re.compile(
        r"\bedge fn\b|via Postgres RPCs|\bRPC:|supabase_realtime|"
        r"\b(?:failure-signature-scan|benchmark-compute|engineering-calc-agent|"
        r"ai-orchestrator|ai-gateway|walkthrough-analyzer)\b",
        re.IGNORECASE)),
    ("doc",      re.compile(r"\b[A-Za-z][\w-]*\.md\b")),
    ("call",     re.compile(r"\b[A-Za-z_]\w*\(\)")),
    ("snake_id", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
    ("upper_id", re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")),
    ("camel_id", re.compile(r"\b_?[a-z]+[A-Z][A-Za-z0-9]*\b")),
]

# A few legitimate user-facing tokens that the broad patterns would otherwise
# catch. Keep this list SHORT and justified — it is the escape hatch, not a dumping
# ground. Matched case-insensitively as whole tokens.
ALLOW_TOKENS = {
    "loto/ptw",        # domain shorthand (lockout-tagout / permit-to-work) users know
    # Product / platform names that the camelCase pattern catches but are real words:
    "iphone", "ipad", "ios", "macos", "youtube", "github", "linkedin",
    "javascript", "gcash", "paypal", "workhive",
}

ALLOW_MARKER_RE = re.compile(r"jargon-allow", re.IGNORECASE)

# ── Stripping helpers ────────────────────────────────────────────────────────
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
SCRIPT_RE       = re.compile(r"<script\b[^>]*>[\s\S]*?</script>", re.IGNORECASE)
STYLE_RE        = re.compile(r"<style\b[^>]*>[\s\S]*?</style>", re.IGNORECASE)
CODE_RE         = re.compile(r"<code\b[^>]*>[\s\S]*?</code>", re.IGNORECASE)
PRE_RE          = re.compile(r"<pre\b[^>]*>[\s\S]*?</pre>", re.IGNORECASE)
TAG_RE          = re.compile(r"<[^>]+>")

# renderSourceChip({...}) body capture (same shape source_chip_truth uses)
CHIP_CALL_RE = re.compile(r"renderSourceChip\s*\(\s*\{(?P<body>[^{}]{0,2500}?)\}\s*\)", re.DOTALL)
# string-literal fields inside a chip body
FRESHNESS_RE = re.compile(r"\bfreshness\s*:\s*(['\"`])(?P<v>.*?)\1", re.DOTALL)
WINDOW_RE    = re.compile(r"\bwindow\s*:\s*(['\"`])(?P<v>.*?)\1", re.DOTALL)
NOTES_RE     = re.compile(r"\bnotes\s*:\s*\[(?P<arr>.*?)\]", re.DOTALL)
STR_LIT_RE   = re.compile(r"(['\"`])(?P<v>(?:\\.|(?!\1).)*?)\1", re.DOTALL)


def _scan_text(text: str) -> list[str]:
    """Return the forbidden tokens found in one user-visible string."""
    found: list[str] = []
    for cls, rx in RULES:
        for m in rx.finditer(text):
            tok = m.group(0)
            if tok.lower() in ALLOW_TOKENS:
                continue
            found.append(f"{cls}:{tok}")
    return found


# User-visible tag attributes — TAG_RE strips these from the body text, but they
# ARE shown to the user (tooltips, a11y labels, input placeholders). Scan them.
USER_ATTR_RE = re.compile(r'\b(?:title|aria-label|placeholder)\s*=\s*"([^"]*)"', re.IGNORECASE)


def _markup_no_script(raw: str) -> str:
    """Strip ONLY <script>/<style>/comments and genuine multi-line <pre> code
    blocks — but KEEP <code> (the platform uses <code> to *style* inline jargon
    tokens like KPI_ENGINE.md / hideZeroStat(), not as real code samples, so those
    ARE on the glass) and keep tags (so attributes can still be scanned)."""
    body = HTML_COMMENT_RE.sub(" ", raw)
    body = SCRIPT_RE.sub(" ", body)
    body = STYLE_RE.sub(" ", body)
    body = PRE_RE.sub(" ", body)
    return body


def _visible_html(raw: str) -> str:
    # NOTE: <code> is intentionally NOT stripped — see _markup_no_script.
    return TAG_RE.sub(" ", _markup_no_script(raw))


def _scan_page(page: Path) -> list[dict]:
    try:
        raw = page.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    issues: list[dict] = []

    # (a) chip fields: freshness / window / notes[] — NOT source.
    for m in CHIP_CALL_RE.finditer(raw):
        body = m.group("body")
        # documented opt-out within ±400 chars of the call
        win_lo = max(0, m.start() - 400)
        win_hi = min(len(raw), m.end() + 400)
        if ALLOW_MARKER_RE.search(raw[win_lo:win_hi]):
            continue

        chip_strings: list[str] = []
        fm = FRESHNESS_RE.search(body)
        if fm:
            chip_strings.append(fm.group("v"))
        wm = WINDOW_RE.search(body)
        if wm:
            chip_strings.append(wm.group("v"))
        nm = NOTES_RE.search(body)
        if nm:
            for sm in STR_LIT_RE.finditer(nm.group("arr")):
                chip_strings.append(sm.group("v"))

        for s in chip_strings:
            hits = _scan_text(s)
            if hits:
                issues.append({
                    "where":  "chip",
                    "string": s[:160],
                    "tokens": sorted(set(hits)),
                })

    # (c) user-visible tag attributes (title / aria-label / placeholder) — these
    # render to the user (tooltips, screen-reader labels, input hints) but TAG_RE
    # strips them from (b). Scan the markup with <script>/<style> removed.
    markup = _markup_no_script(raw)
    for m in USER_ATTR_RE.finditer(markup):
        val = m.group(1)
        if not val or ALLOW_MARKER_RE.search(val):
            continue
        hits = _scan_text(val)
        if hits:
            issues.append({"where": "attr", "string": val[:160], "tokens": sorted(set(hits))})

    # (b) visible HTML body text (explainer blocks, static chips, <code>-styled jargon)
    visible = _visible_html(raw)
    # scan line-by-line-ish on sentence chunks so error strings stay short
    for chunk in re.split(r"[\n\r]+|(?<=[.!?])\s{2,}", visible):
        chunk = chunk.strip()
        if not chunk or len(chunk) > 600:
            # skip whitespace and giant blobs (likely minified/no real prose)
            if len(chunk) > 600:
                continue
            continue
        # `jargon-allow` opt-out on the chunk
        if ALLOW_MARKER_RE.search(chunk):
            continue
        hits = _scan_text(chunk)
        if hits:
            issues.append({
                "where":  "html",
                "string": chunk[:160],
                "tokens": sorted(set(hits)),
            })

    return issues


def _scan_provenance() -> list[dict]:
    """Scan the runtime 'where did this come from?' hover content (display_provenance.json,
    Interactive-Lineage E2) for developer jargon. ONLY the RENDERED fields (lines / rung_label /
    label) are scanned; the canonical `source` field is EXEMPT — it's the sanctioned machine-
    plane channel (translated to plain words at build time via build_display_provenance.py's
    SOURCE_PLAIN / USER_LABELS maps), exactly like the renderSourceChip `source:` field. This
    puts the provenance popover — its own 'glass' on 20 pages — under the SAME jargon authority,
    so a future build can't re-leak a view name / column / camelCase helper into the popover."""
    if not PROV_PATH.exists():
        return []
    try:
        data = json.loads(PROV_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    issues: list[dict] = []
    for page, ents in (data.get("pages") or {}).items():
        if page in EXCLUDE_PAGES:
            continue  # internal/ops pages document internals by design
        for eid, e in (ents or {}).items():
            strings = list(e.get("lines") or []) + [e.get("rung_label") or "", e.get("label") or ""]
            for s in strings:
                hits = _scan_text(s)
                if hits:
                    issues.append({"where": "provenance",
                                   "string": f"{page}/{eid}: {s}"[:160],
                                   "tokens": sorted(set(hits))})
    return issues


def _scan_impact_preview() -> list[dict]:
    """Scan the runtime 'this save updates N pages' hint (field_impact_preview.json,
    Interactive-Lineage D2) for developer jargon. RENDERED fields only — `headline` and
    `cascades_plain` (the user-voice cascade list). The canonical `cascades` (raw table
    names) and `recompute_fns` (internal edge-fn names, never rendered) are EXEMPT."""
    if not IMPACT_PATH.exists():
        return []
    try:
        data = json.loads(IMPACT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    surfaces = data.get("surfaces", data)
    issues: list[dict] = []
    for surf, info in (surfaces or {}).items():
        if not isinstance(info, dict):
            continue
        strings = [info.get("headline") or ""] + list(info.get("cascades_plain") or [])
        for s in strings:
            hits = _scan_text(s)
            if hits:
                issues.append({"where": "impact_preview",
                               "string": f"{surf}: {s}"[:160], "tokens": sorted(set(hits))})
    return issues


CHECK_NAMES = ["user_facing_jargon"]


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def main() -> int:
    seen: set[str] = set(EXCLUDE_PAGES)   # excluded pages never enter the list
    page_names = []
    for n in PAGES:
        if n not in seen:
            seen.add(n)
            page_names.append(n)
    # also pick up any *.html with a chip not already in the list
    for p in sorted(ROOT.glob("*.html")):
        if p.name in seen:
            continue
        try:
            if "renderSourceChip" in p.read_text(encoding="utf-8", errors="replace"):
                seen.add(p.name)
                page_names.append(p.name)
        except Exception:
            pass

    per_page: list[dict] = []
    total = 0
    for name in page_names:
        page = ROOT / name
        if not page.exists():
            continue
        issues = _scan_page(page)
        if issues:
            per_page.append({"page": name, "count": len(issues), "issues": issues})
            total += len(issues)

    # The provenance hover + impact-preview hint are runtime "glass" too — scan them.
    prov_issues = _scan_provenance()
    if prov_issues:
        per_page.append({"page": "display_provenance.json", "count": len(prov_issues), "issues": prov_issues})
        total += len(prov_issues)
    impact_issues = _scan_impact_preview()
    if impact_issues:
        per_page.append({"page": "field_impact_preview.json", "count": len(impact_issues), "issues": impact_issues})
        total += len(impact_issues)

    # Baseline ratchet
    baseline = total
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("issues", total)
        except Exception:
            baseline = total
    else:
        BASELINE_PATH.write_text(json.dumps({"issues": total, "established": True}, indent=2), encoding="utf-8")

    if total < baseline:
        baseline = total
        BASELINE_PATH.write_text(json.dumps({"issues": total, "tightened": True}, indent=2), encoding="utf-8")

    report = {
        "summary": {"pages_with_jargon": len(per_page), "total_issues": total, "baseline": baseline},
        "per_page": per_page,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("User-Facing Jargon Validator (L0)"))
    print("=" * 60)
    print(f"  pages with jargon: {len(per_page)}")
    print(f"  jargon strings:    {total}  (baseline: {baseline})")

    if total == 0:
        print()
        print(_green("PASS — no developer jargon on the glass. Every chip/explainer reads in user language."))
        return 0

    print()
    print("Jargon found in user-visible text (translate to plain language):")
    for p in per_page[:40]:
        print(f"  {p['page']}  ({p['count']})")
        for i in p["issues"][:12]:
            print(f"    [{i['where']}] {', '.join(i['tokens'][:6])}")
            print(f"        “{i['string'][:90]}”")

    if total > baseline:
        print()
        print(_red(f"FAIL — count {total} > baseline {baseline} (new jargon introduced onto the glass)"))
        print("Fix: rewrite the string in user language. Source-chip view names are translated")
        print("via WH_SOURCE_LABELS in utils.js — put the canonical name in the source: field, not notes.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by translating one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
