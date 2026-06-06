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

Exit codes:
  0  clones <= baseline (or jscpd/node absent -> SKIP, or baseline newly established).
  1  clones > baseline (new copy-paste introduced) -> the forward-only ratchet trips.
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
          "**/index-*.html,**/symbol-gallery.html,**/.playwright-mcp/**")
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
    dup_lines = int(total.get("duplicatedLines", 0))
    pct = float(total.get("percentage", 0.0))

    baseline = None
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("clones")
        except Exception:
            baseline = None

    if baseline is None or update:
        BASELINE_PATH.write_text(json.dumps(
            {"clones": clones, "duplicatedLines": dup_lines, "percentage": round(pct, 2),
             "note": "forward-only ratchet; collapse duplication then --update-baseline to lower"},
            indent=2) + "\n", encoding="utf-8")
        print(f"\033[92mBASELINE {'updated' if update else 'established'}\033[0m  clones={clones}  "
              f"dupLines={dup_lines}  ({pct:.2f}%)")
        print(bar)
        return 0

    print(f"  clones: {clones}  (baseline: {baseline})   dupLines={dup_lines}  ({pct:.2f}%)")
    if clones > baseline:
        dups = sorted(data.get("duplicates", []), key=lambda x: x.get("lines", 0), reverse=True)
        print(f"\033[91mFAIL\033[0m  clone debt GREW {baseline} -> {clones} — new copy-paste introduced.")
        print("  Biggest current clones (collapse into a shared component/helper):")
        for c in dups[:5]:
            fa = c["firstFile"]["name"].replace("\\", "/").split("/")[-1]
            fb = c["secondFile"]["name"].replace("\\", "/").split("/")[-1]
            print(f"    {c.get('lines',0):4d} lines  {fa} <-> {fb}")
        print("  Fix: extract the duplicated block; or if intentional, --update-baseline with a reason.")
        print(bar)
        return 1
    if clones < baseline:
        BASELINE_PATH.write_text(json.dumps(
            {"clones": clones, "duplicatedLines": dup_lines, "percentage": round(pct, 2),
             "note": "forward-only ratchet; tightened automatically on reduction"},
            indent=2) + "\n", encoding="utf-8")
        print(f"\033[92mPASS + TIGHTENED\033[0m  clone debt reduced {baseline} -> {clones}; baseline lowered.")
        print(bar)
        return 0
    print(f"\033[92mPASS\033[0m  clone debt held at baseline ({clones}).")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
