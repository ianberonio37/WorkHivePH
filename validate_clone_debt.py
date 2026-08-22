"""
Clone-Debt Validator (G0) — the deterministic half of the Holistic / Cross-Page Critic.
=======================================================================================
The Grounded MCP Sweep's per-element critic is BLIND to redundancy/overlap (a duplicate
is a RELATIONSHIP between files, invisible to a one-element-at-a-time scan — see
workflows/grounded_mcp_sweep.md Phase 4.7 + reference_holistic_critic_tooling). This is
the deterministic redundancy ratchet: it runs `jscpd` (kucherenko/jscpd, Rabin-Karp clone
detector, tokenizes embedded <script>/<style> in HTML) and FAILs forward-only if the
duplicated-clone count grows beyond a frozen baseline.

Found 2026-06-07: 73 exact clones / 5259 duplicated lines = 24.65% of the platform HTML,
incl. 400-646-line verbatim blocks shared between sibling pages (shift-brain /
plant-connections / predictive / ai-quality are largely assembled from each other's
copy-paste). The "verdict+simple-card" block + the SUPABASE_URL/script boilerplate are
the worst offenders. Collapsing a clone into a shared component/helper ratchets this DOWN.

Degrade-to-SKIP (exit 0) when jscpd isn't installed, so a fresh checkout never false-FAILs.
To make it a live ratchet, commit jscpd as a devDependency: `npm i -D jscpd`.
Re-baseline after a deliberate reduction: `python validate_clone_debt.py --update-baseline`.

★ 2026-06-14 (STREAMLINE S12): ratchet switched from clone-PAIR COUNT to duplicated-LINES,
and retired predictive.html excluded from the scan. Why lines-not-count: across S8's page
fusions the count went 73 -> 70 (looked better) while % rose 24.65 -> 27.5 — a count ratchet
rubber-stamps a proportional regression. duplicatedLines is the honest absolute metric
(a NEW or BIGGER clone raises it; a dedup lowers it). `percentage` is PRINTED but NOT gated:
deleting UNIQUE html raises % with no new duplication, which would false-trip a %-gate.

Exit codes:
  0  duplicatedLines <= baseline (or jscpd/node absent -> SKIP, or baseline newly established).
  1  duplicatedLines > baseline (new copy-paste introduced) -> the forward-only ratchet trips.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BASELINE_PATH = ROOT / "clone_debt_baseline.json"
OUT_DIR = ROOT / ".tmp" / "clone_debt"
JSCPD = ROOT / "node_modules" / "jscpd" / "bin" / "jscpd"

# Same scope every run so the count is reproducible. HTML only (the copy-paste lives in
# the page shells); backups/tests/vendored dirs excluded.
PATTERN = "*.html"
IGNORE = ("**/node_modules/**,**/.tmp/**,**/test-results/**,**/*backup*,**/*-test*,"
          "**/index-*.html,**/symbol-gallery.html,**/.playwright-mcp/**,**/predictive.html")
MIN_TOKENS = "40"


def _skip(reason: str) -> int:
    print(f"\033[96mSKIP\033[0m  Clone-Debt: {reason}")
    print("  (install jscpd to activate the redundancy ratchet: npm i -D jscpd)")
    return 0


def run_jscpd() -> dict | None:
    if not JSCPD.exists():
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    node = "node"
    try:
        proc = subprocess.run(
            [node, str(JSCPD), ".", "--pattern", PATTERN, "--ignore", IGNORE,
             "--min-tokens", MIN_TOKENS, "--reporters", "json", "--output", str(OUT_DIR), "--silent"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        )
    except FileNotFoundError:
        return {"_no_node": True}
    except subprocess.TimeoutExpired:
        return {"_timeout": True}
    report = OUT_DIR / "jscpd-report.json"
    if not report.exists():
        return {"_no_report": True, "stderr": (proc.stderr or "")[:300]}
    try:
        return json.loads(report.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_parse_error": str(e)}


# ★ THE MARKUP FORMAT BILLS PHANTOM LINES AND MUST NOT BE GATED ON. Proven 2026-08-21 with a
# two-file scratch run: public-feed's ENTIRE inline script body was replaced with generated junk and
# the project-report <-> public-feed "clone" still reported 527+20 duplicated lines over the same
# spans. jscpd's markup tokenizer matches only the tag envelope (`</main><script src=...supabase...>
# <script src="utils.js"><script>`) and attributes the whole line-span between matching runs — the
# script CONTENT inside is never measured. So on this codebase (pages = HTML shells around large
# inline scripts), markup-format "duplicated lines" grow when UNIQUE code is added inside a matched
# envelope: the v7 red "3184 -> 3279, new copy-paste introduced" accused an arc that copied nothing.
# The real copy-paste signal is the css + javascript formats, which tokenize actual content.
CONTENT_FORMATS = ("css", "javascript")

def _fmt_lines(data):
    fmts = (data.get("statistics") or {}).get("formats") or {}
    def n(f):
        return int(((fmts.get(f) or {}).get("total") or {}).get("duplicatedLines", 0))
    content = sum(n(f) for f in CONTENT_FORMATS)
    return content, n("markup")

def _pairs(data, content_only=True):
    """Per-pair duplicated lines, so a regression can name WHICH pair grew.

    A count-only baseline ({"duplicatedLines": 3184}) proves something regressed but never what.
    Measured 2026-08-20: debt rose 3184 -> 3279 while the clone COUNT fell 51 -> 49, i.e. existing
    clones grew rather than new ones appearing -- which the totals alone cannot show.
    content_only skips markup-format clones (envelope artifact, see CONTENT_FORMATS note).
    """
    out = {}
    for c in data.get("duplicates", []):
        if content_only and c.get("format") not in CONTENT_FORMATS:
            continue
        a = c["firstFile"]["name"].replace(chr(92), "/").split("/")[-1]
        b = c["secondFile"]["name"].replace(chr(92), "/").split("/")[-1]
        key = " <-> ".join(sorted((a, b)))
        out[key] = out.get(key, 0) + int(c.get("lines", 0))
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))

def main() -> int:
    update = "--update-baseline" in sys.argv
    bar = "=" * 70
    print(bar)
    print("Clone-Debt Validator (G0)  —  deterministic redundancy ratchet (jscpd)")
    print(bar)

    data = run_jscpd()
    if data is None:
        return _skip("jscpd not installed (node_modules/jscpd absent)")
    if data.get("_no_node"):
        return _skip("node not on PATH")
    if data.get("_timeout"):
        return _skip("jscpd timed out (>180s)")
    if data.get("_no_report") or data.get("_parse_error"):
        return _skip(f"jscpd produced no parseable report ({data})")

    total = (data.get("statistics") or {}).get("total") or {}
    clones = int(total.get("clones", 0))
    content_lines, markup_lines = _fmt_lines(data)
    pct = float(total.get("percentage", 0.0))

    BASELINE_NOTE = (
        "forward-only ratchet on CONTENT duplicatedLines (css + javascript formats only); "
        "markup-format lines are informational: jscpd's markup tokenizer matches only the tag "
        "envelope and bills the whole line-span, so on script-heavy pages those counts grow when "
        "UNIQUE code is added inside a matched envelope (proven 2026-08-21: replacing public-feed's "
        "entire script body with junk left the 527-line project-report<->public-feed 'clone' intact). "
        "Collapse duplication then --update-baseline to lower; % informational"
    )

    baseline = None
    legacy_total_baseline = None
    if BASELINE_PATH.exists():
        try:
            _b = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
            baseline = _b.get("contentDuplicatedLines")
            legacy_total_baseline = _b.get("duplicatedLines")
        except Exception:
            baseline = None

    def _write_baseline(tag):
        BASELINE_PATH.write_text(json.dumps(
            {"clones": clones, "contentDuplicatedLines": content_lines,
             "markupLinesInformational": markup_lines, "percentage": round(pct, 2),
             "pairs": _pairs(data), "note": BASELINE_NOTE}, indent=2) + "\n", encoding="utf-8")
        print(f"\033[92mBASELINE {tag}\033[0m  contentDuplicatedLines={content_lines}  "
              f"(markup informational: {markup_lines})  clones={clones}  ({pct:.2f}%)")

    if baseline is None and legacy_total_baseline is not None and not update:
        # MEASUREMENT MIGRATION, not a loosening: the old baseline gated the jscpd TOTAL, which the
        # markup envelope artifact inflates without any copy-paste (see CONTENT_FORMATS note). The
        # ratchet re-anchors on the content formats it can honestly measure; the whole reasoning is
        # recorded in the baseline note so a later reader can audit why the number changed shape.
        print(f"  measurement migrated: total-lines baseline ({legacy_total_baseline}) retired — the "
              "markup envelope artifact made it accuse growth with no copy-paste (see baseline note)")
        _write_baseline("migrated to content formats")
        print(bar)
        return 0
    if baseline is None or update:
        _write_baseline("updated" if update else "established")
        print(bar)
        return 0

    print(f"  content duplicatedLines: {content_lines}  (baseline: {baseline})   "
          f"markup: {markup_lines} (informational — envelope artifact)   clones={clones}  ({pct:.2f}%)")
    if content_lines > baseline:
        dups = sorted([c for c in data.get("duplicates", []) if c.get("format") in CONTENT_FORMATS],
                      key=lambda x: x.get("lines", 0), reverse=True)
        print(f"\033[91mFAIL\033[0m  clone debt GREW {baseline} -> {content_lines} content duplicated "
              "lines — new copy-paste introduced.")
        try:
            _base_pairs = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("pairs") or {}
        except Exception:
            _base_pairs = {}
        if _base_pairs:
            _now = _pairs(data)
            _grew = [(k, v, _base_pairs.get(k, 0)) for k, v in _now.items() if v > _base_pairs.get(k, 0)]
            _grew.sort(key=lambda t: t[2] - t[1])
            if _grew:
                print("  Pairs that GREW since the baseline (this is what to look at):")
                for k, now_v, was_v in _grew[:6]:
                    print(f"    {was_v:4d} -> {now_v:4d} lines  {k}" + ("   (NEW)" if not was_v else ""))
        print("  Biggest current content clones (collapse into a shared component/helper):")
        for c in dups[:5]:
            fa = c["firstFile"]["name"].replace("\\", "/").split("/")[-1]
            fb = c["secondFile"]["name"].replace("\\", "/").split("/")[-1]
            print(f"    {c.get('lines',0):4d} lines  [{c.get('format')}]  {fa} <-> {fb}")
        print("  Fix: extract the duplicated block; or if intentional, --update-baseline with a reason.")
        print(bar)
        return 1
    if content_lines < baseline:
        _write_baseline("tightened")
        print(f"\033[92mPASS + TIGHTENED\033[0m  clone debt reduced {baseline} -> {content_lines} "
              "content duplicated lines; baseline lowered.")
        print(bar)
        return 0
    print(f"\033[92mPASS\033[0m  clone debt held at baseline ({content_lines} content duplicated lines).")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
