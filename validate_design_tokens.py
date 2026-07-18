"""
Design-Token Validator (L0) — STREAMLINE §14 E4.
=================================================
The designer SKILL.md defines a canonical palette / type / spacing, but the
values were pasted as raw hex inline on every page — so a wrong orange (#e8920a)
once drifted into parts-tracker + assistant before anyone noticed. E4 promotes
the palette to CSS custom properties in components.css (ONE source of truth) and
this gate keeps it honest:

  L1  Token-block integrity (FAIL) — components.css :root must declare EVERY
      canonical token with its exact value. The palette can't be deleted or
      silently re-valued.
  L2  Drift-hex ban (FAIL) — the documented non-brand hex (#e8920a) must never
      appear in user-facing CSS/markup. It is a real bug (wrong orange), not a
      shade choice.
  L4  Family-resemblance ratchet (forward-only, rubric class S) — count DECLARED
      corner radii outside the token vocabulary (8/12/16/pill/0). Ian, 2026-07-15:
      "my pages would look like not different personalities." Driving conformance
      by hand is a seesaw; this makes a rogue corner only ever go DOWN. Measured
      a phantom 10px on 5 pages, a 6px on alert-hub, a 9px on logbook.
  L3  Raw-brand-hex ratchet (forward-only) — count raw canonical-brand-hex
      literals used inline on pages (NOT the components.css :root definitions).
      Baseline = current; FAIL on increase. Pages that link components.css
      should use var(--wh-*); this tracks the migration without a big-bang edit.

Output: design_tokens_report.json + design_tokens_baseline.json (L3 floor).
Exit 1 on any L1/L2 failure or an L3 increase; 0 otherwise.
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
COMPONENTS    = ROOT / "components.css"
TOKENS_CSS    = ROOT / "tokens.css"      # E4: the SINGLE brand-palette source (L1 gates this)
REPORT_PATH   = ROOT / "design_tokens_report.json"
BASELINE_PATH = ROOT / "design_tokens_baseline.json"

# Canonical palette (designer SKILL.md). token -> exact hex.
CANONICAL_TOKENS = {
    "--wh-orange":       "#F7A21B",
    "--wh-orange-dark":  "#D88A0E",
    "--wh-orange-light": "#FDB94A",
    "--wh-blue":         "#29B6D9",
    "--wh-blue-dark":    "#1A9ABF",
    "--wh-blue-light":   "#5FCCE8",
    "--wh-navy":         "#162032",
    "--wh-navy-mid":     "#1F2E45",
    "--wh-navy-light":   "#2A3D58",
    "--wh-steel":        "#7B8794",
    "--wh-cloud":        "#F4F6FA",
}
BRAND_HEX = {v.upper() for v in CANONICAL_TOKENS.values()}
DRIFT_HEX = {"#E8920A"}  # documented non-brand orange (designer SKILL.md anti-pattern)

HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
CSS_COMMENT_RE  = re.compile(r"/\*[\s\S]*?\*/")
HEX_RE          = re.compile(r"#[0-9A-Fa-f]{6}\b")

# User-facing surfaces (skip internal ops/admin dashboards + tests).
# The family (rubric class S / NN/g #4 internal consistency) is what USERS see. These are
# dev/ops tooling that never ship a webfont and are not part of the product's look; grading
# them would make the family metric answer a question nobody asked. Ian's call 2026-07-15,
# extending the same basis on which platform-health + founder-console were already excluded.
EXCLUDE = {
    "platform-health.html", "founder-console.html",
    "architecture.html",        # internal architecture diagram viewer
    "validator-catalog.html",   # internal gate catalogue (3570 system-font nodes)
    "llm-observability.html",   # internal AI ops dashboard
    "symbol-gallery.html",      # internal engineering-symbol reference
}


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def check_token_block() -> list[str]:
    """L1 — every canonical token present with its exact value in tokens.css :root
    (the SINGLE palette source; components.css @imports it, every page <link>s it)."""
    issues = []
    if not TOKENS_CSS.exists():
        return ["tokens.css is missing — the design-token source of truth is gone"]
    css = TOKENS_CSS.read_text(encoding="utf-8", errors="replace")
    if ":root" not in css:
        return ["tokens.css has no :root block — design tokens are undefined"]
    for tok, hexv in CANONICAL_TOKENS.items():
        # match `--wh-orange : #F7A21B` (case-insensitive on the hex)
        if not re.search(re.escape(tok) + r"\s*:\s*" + re.escape(hexv) + r"\b", css, re.IGNORECASE):
            issues.append(f"{tok} missing or not = {hexv} in tokens.css :root")
    return issues


def _strip_comments(text: str) -> str:
    return CSS_COMMENT_RE.sub(" ", HTML_COMMENT_RE.sub(" ", text))


def scan_drift_and_rawhex():
    """L2 (drift hex) + L3 (raw brand hex) across user-facing html + css."""
    drift_hits = []   # (file, hex)
    rawhex_count = 0
    rawhex_by_file = {}

    files = sorted(list(ROOT.glob("*.html"))) + [COMPONENTS]
    for f in files:
        # Skip non-user-facing files: explicit excludes, test harnesses, and ANY
        # backup variant (index.backup.html, index.backup2.html, *_backup.html, ...).
        # A backup is not a live page, so its inline hexes must not inflate the
        # migration count (the prior `.backup.html` suffix missed `.backup2.html`).
        if f.name in EXCLUDE or f.name.endswith("-test.html") or "backup" in f.name.lower():
            continue
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        body = _strip_comments(raw)

        # L2 drift hex anywhere (case-insensitive)
        for m in HEX_RE.finditer(body):
            if m.group(0).upper() in DRIFT_HEX:
                drift_hits.append({"file": f.name, "hex": m.group(0)})

        # L3 raw brand hex — but NOT the components.css :root token DEFINITIONS
        # (those SHOULD be raw hex; they are the source of truth). For
        # components.css, only count brand hex OUTSIDE the :root block.
        scan_text = body
        if f.name == COMPONENTS.name:
            root_m = re.search(r":root\s*\{[\s\S]*?\}", body)
            if root_m:
                scan_text = body[:root_m.start()] + body[root_m.end():]
        cnt = 0
        for m in HEX_RE.finditer(scan_text):
            if m.group(0).upper() in BRAND_HEX:
                cnt += 1
        if cnt:
            rawhex_by_file[f.name] = cnt
            rawhex_count += cnt

    return drift_hits, rawhex_count, rawhex_by_file



# -- L4 . Family resemblance (rubric class S) --------------------------------
# Ian: "my pages would look like not different personalities ... same and similar
# theme." Driving S1 to 100% BY HAND is a seesaw: the next `border-radius: 10px`
# silently re-opens it. This ratchet is the anti-seesaw lock: a rogue corner can
# only ever go DOWN. Measured 2026-07-15: a phantom 10px (index/analytics/asset-hub/
# inventory/logbook), a 6px (alert-hub), a 9px (logbook) -- none of them tokens.
# NN/g Heuristic #4 internal consistency.
# [external-consistency-and-standards-heuristic-internal-ext]
LEGAL_RADIUS = {
    "0", "0px", "0%", "50%", "inherit", "initial", "unset",
    "8px", "12px", "16px", "999px", "9999px",
    "0.5rem", "0.75rem", "1rem",          # 8 / 12 / 16 at the 16px root
}
RADIUS_RE = re.compile(r"border[a-z-]*radius:\s*([^;}\n]+)")


def scan_rogue_radius():
    """Count DECLARED corner radii that are neither var(--wh-*) nor a legal literal."""
    rogue_by_file, total = {}, 0
    for f in sorted(list(ROOT.glob("*.html")) + list(ROOT.glob("*.css"))):
        if f.name in EXCLUDE or f.name.endswith("-test.html") or "backup" in f.name.lower():
            continue
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        body = _strip_comments(raw)
        # tokens.css :root DEFINES the radius vocabulary -- those literals are the
        # source of truth, not drift. Same carve-out L3 makes for the palette.
        if f.name == "tokens.css":
            root_m = re.search(r":root\s*\{[\s\S]*?\}", body)
            if root_m:
                body = body[:root_m.start()] + body[root_m.end():]
        cnt = 0
        for m in RADIUS_RE.finditer(body):
            val = m.group(1).strip().rstrip('"').rstrip("'").strip()
            if "var(" in val:                       # drawing from the system = correct
                continue
            parts = [x for x in re.split(r"[\s/]+", val) if x]
            if parts and all(x in LEGAL_RADIUS for x in parts):
                continue
            cnt += 1
        if cnt:
            rogue_by_file[f.name] = cnt
            total += cnt
    return total, rogue_by_file


CHECK_NAMES = ["design_token_integrity", "design_token_drift_hex", "design_token_rawhex_ratchet",
               "design_token_family_resemblance"]


def main() -> int:
    l1 = check_token_block()
    drift_hits, rawhex_count, rawhex_by_file = scan_drift_and_rawhex()

    baseline = rawhex_count
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("rawhex", rawhex_count)
        except Exception:
            baseline = rawhex_count
    else:
        BASELINE_PATH.write_text(json.dumps({"rawhex": rawhex_count, "established": True}, indent=2), encoding="utf-8")
    if rawhex_count < baseline:
        baseline = rawhex_count
        BASELINE_PATH.write_text(json.dumps({"rawhex": rawhex_count, "tightened": True}, indent=2), encoding="utf-8")

    # L4 — family resemblance (rubric class S). Forward-only, same shape as L3.
    rogue_radius, rogue_by_file = scan_rogue_radius()
    rad_baseline = rogue_radius
    if BASELINE_PATH.exists():
        try:
            rad_baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("rogue_radius", rogue_radius)
        except Exception:
            rad_baseline = rogue_radius
    if rogue_radius < rad_baseline:
        rad_baseline = rogue_radius

    l1_fail   = len(l1) > 0
    l2_fail   = len(drift_hits) > 0
    l3_fail   = rawhex_count > baseline
    l4_fail   = rogue_radius > rad_baseline

    # Persist BOTH ratchets together so a tightening of either is remembered.
    BASELINE_PATH.write_text(json.dumps(
        {"rawhex": baseline, "rogue_radius": rad_baseline, "tightened": True}, indent=2), encoding="utf-8")

    report = {
        "summary": {
            "token_integrity_issues": len(l1),
            "drift_hex_hits":         len(drift_hits),
            "rawhex_count":           rawhex_count,
            "rawhex_baseline":        baseline,
            "rogue_radius":           rogue_radius,
            "rogue_radius_baseline":  rad_baseline,
        },
        "token_integrity": l1,
        "drift_hex": drift_hits,
        "rawhex_by_file": rawhex_by_file,
        "rogue_radius_by_file": rogue_by_file,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("Design-Token Validator (L0) — STREAMLINE E4"))
    print("=" * 60)
    print(f"  L1 token-block integrity: {'OK' if not l1_fail else str(len(l1)) + ' missing/drifted'}")
    print(f"  L2 drift-hex (#e8920a):   {'none' if not l2_fail else str(len(drift_hits)) + ' hits'}")
    print(f"  L3 raw brand-hex inline:  {rawhex_count}  (baseline {baseline})")
    print(f"  L4 family resemblance:    {rogue_radius} rogue radius decls  (baseline {rad_baseline})")

    if l1_fail:
        print(_red("\nL1 FAIL — canonical tokens missing/changed in components.css:"))
        for i in l1:
            print("  " + i)
    if l2_fail:
        print(_red("\nL2 FAIL — non-brand drift hex on the glass (use var(--wh-orange)):"))
        for h in drift_hits[:20]:
            print(f"  {h['file']}: {h['hex']}")
    if l3_fail:
        print(_red(f"\nL3 FAIL — raw brand-hex count {rawhex_count} > baseline {baseline} (use var(--wh-*) instead of a raw brand hex)"))
    if l4_fail:
        print(_red(f"\nL4 FAIL — rogue radius decls {rogue_radius} > baseline {rad_baseline}"))
        print(_red("  A corner outside the token vocabulary is how pages drift into different"))
        print(_red("  personalities. Use var(--wh-radius-sm|--wh-radius|--wh-radius-lg)."))
        for fn, c in sorted(rogue_by_file.items(), key=lambda x: -x[1])[:8]:
            print(f"    {fn}: {c}")

    if not (l1_fail or l2_fail or l3_fail or l4_fail):
        print(_green("\nPASS — token layer intact, no drift hex, raw-hex + rogue-radius at/below baseline."))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
