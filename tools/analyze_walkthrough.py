"""
tools/analyze_walkthrough.py — WorkHive Walkthrough Analyzer (Enhanced)
========================================================================
Implements all 5 hardening-loop patterns:

  Pattern 1 — Seeder awareness:
    Reads per-page metadata JSON (card_heroes, has_data) written by the
    walkthrough spec. Tells the AI whether zeros are empty states or bugs.

  Pattern 2 — Journey coverage cross-reference:
    Before calling the edge fn, checks if tests/journey-<slug>.spec.ts
    exists and contains assertions for the finding class. Auto-sets
    has_test=true and skips the proposal generator for already-covered bugs.

  Pattern 3 — Gate context injection:
    Reads platform_health.json (written by run_platform_checks.py --fast).
    Injects currently-failing Sentinel Agent validator names into the edge
    fn payload so the AI can classify "already tracked" vs "new finding".

  Pattern 4 — Settlement timeout detection:
    Reads settlement_timed_out from the metadata JSON. Pages that timed out
    get a pre-built partial_capture finding (no AI call) and are otherwise
    skipped to prevent false positives.

  Pattern 5 — Structured validator decision (handled in edge fn):
    The edge function now returns validator_decision:{action, target_file,
    target_layer, reason} instead of a free-text proposed_gate string.
    This file writes that structured output into findings.json.

Usage:
  python tools/analyze_walkthrough.py
  python tools/analyze_walkthrough.py --dry-run

After running: python validate_playwright_staleness.py to check L13b.

Skills consulted: ai-engineer (callAI chain via edge fn, no provider SDK),
platform-guardian (hardening loop patterns, findings.json memory layer).
"""

import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

WALKTHROUGH_DIR   = Path(".tmp") / "walkthrough"
PW_REPORT         = Path("playwright-report.json")
FINDINGS_FILE     = Path("findings.json")
PLATFORM_HEALTH   = Path("platform_health.json")
TESTS_DIR         = Path("tests")

SUPABASE_URL      = os.getenv("SUPABASE_URL", "https://hzyvnjtisfgbksicrouu.supabase.co")
SUPABASE_ANON     = os.getenv("SUPABASE_ANON_KEY", "")
EDGE_FN_URL       = f"{SUPABASE_URL}/functions/v1/walkthrough-analyzer"

DRY_RUN           = "--dry-run" in sys.argv
TODAY             = date.today().isoformat()

# Pages that don't have Plain-Read contract — chip/verdict not expected
NO_PLAIN_READ     = {"logbook", "voice-journal", "engineering-design",
                     "community", "audit-log", "assistant"}

# Journey spec assertions that signal coverage for a finding type
CHIP_ASSERTIONS   = ("source-chip", "wh-source-chip", "renderSourceChip", "chip_texts")
VERDICT_ASSERTIONS= ("verdict-label", "verdict settles", "verdict settled", "ss-verdict")
CARD_ASSERTIONS   = ("sc-hero", "card_heroes", "hero should not be", "cards have")


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[analyzer] warning: could not load {path}: {e}")
        return None


def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def png_to_b64(path: Path) -> str | None:
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Pattern 2: Journey coverage cross-reference ───────────────────────────────

def get_journey_coverage(slug: str) -> dict:
    """Check if a journey spec exists for this page and what it covers."""
    # Common slug → spec file mappings (some differ from page slug)
    slug_map = {
        "alert-hub":   "journey-alerts",
        "pm-scheduler":"journey-pm",
    }
    spec_stem = slug_map.get(slug, f"journey-{slug}")
    spec_path = TESTS_DIR / f"{spec_stem}.spec.ts"

    if not spec_path.exists():
        return {"has_spec": False, "covers_chip": False, "covers_verdict": False, "covers_cards": False}

    try:
        content = spec_path.read_text(encoding="utf-8")
    except Exception:
        return {"has_spec": True, "covers_chip": False, "covers_verdict": False, "covers_cards": False}

    return {
        "has_spec":      True,
        "spec_file":     str(spec_path),
        "covers_chip":   any(a in content for a in CHIP_ASSERTIONS),
        "covers_verdict":any(a in content for a in VERDICT_ASSERTIONS),
        "covers_cards":  any(a in content for a in CARD_ASSERTIONS),
    }


# ── Pattern 3: Gate context injection ────────────────────────────────────────

def get_failing_validators() -> list[str]:
    """Read platform_health.json and return list of currently-failing validator IDs."""
    health = load_json(PLATFORM_HEALTH)
    if not health:
        return []
    failing: list[str] = []
    for entry in health.get("results", []):
        if entry.get("status") in ("FAIL", "REGRESSION"):
            failing.append(entry.get("id", "?"))
    return failing[:10]  # cap at 10 to keep prompt size manageable


# ── Pattern 4: Settlement timeout auto-finding ───────────────────────────────

def make_partial_capture_finding(slug: str, meta: dict) -> dict:
    """Generate a pre-built partial_capture finding — no AI needed."""
    verdict = meta.get("verdict_text", "unknown")
    return {
        "source":         "render_state",
        "page":           slug,
        "description":    (
            f"Page '{slug}' was captured before settling — waitForFunction timed out. "
            f"Verdict showed: '{verdict}'. Screenshot may show a loading state rather than "
            f"real data. Investigate why chip or hero cards are slow to populate."
        ),
        "severity":       "low",
        "domain":         "Performance Guardian",
        "sentinel_agent": "Performance Guardian (loading state)",
        "proposed_gate":  "Add page-specific settled condition or increase timeout in walkthrough spec",
        "validator_decision": {
            "action":       "improve_existing",
            "target_file":  "tests/plain-read-walkthrough.spec.ts",
            "target_layer": "waitForFunction settle condition",
            "reason":       f"Page {slug} consistently times out — needs a custom settle signal",
        },
    }


# ── Pattern 2: Auto-gate finding if journey spec covers it ───────────────────

def auto_gate_finding(f: dict, coverage: dict) -> dict:
    """If the journey spec already covers this finding class, auto-set has_test."""
    desc = f.get("description", "").lower()
    if not coverage.get("has_spec"):
        return f

    covers = False
    if any(k in desc for k in ("chip", "source chip", "wh-source-chip")) and coverage.get("covers_chip"):
        covers = True
    elif any(k in desc for k in ("verdict", "verdict text")) and coverage.get("covers_verdict"):
        covers = True
    elif any(k in desc for k in ("card", "hero", "zero value", "loading")) and coverage.get("covers_cards"):
        covers = True

    if covers:
        f["_auto_gated"] = True
        f["has_test"]   = True
        f["test_file"]  = coverage.get("spec_file", "")
        f["status"]     = "acknowledged"
        f["root_cause"] = (
            f"Auto-gated: journey spec {coverage.get('spec_file','')} already covers "
            f"this finding class. No new gate needed."
        )
    return f


# ── Edge function call ────────────────────────────────────────────────────────

def call_edge_function(payload: dict) -> dict | None:
    if not SUPABASE_ANON:
        print("[analyzer] SUPABASE_ANON_KEY not set — skipping edge fn call")
        return None

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        EDGE_FN_URL, data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {SUPABASE_ANON}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[analyzer] edge fn HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return None
    except Exception as e:
        print(f"[analyzer] edge fn error: {e}")
        return None


def make_finding_id(slug: str, description: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", description.lower())[:60].strip("-")
    return f"{slug}-{clean}"


def merge_findings(existing: list[dict], new_findings: list[dict]) -> tuple[list[dict], int]:
    existing_ids = {f["id"] for f in existing}
    added, merged = 0, list(existing)
    for f in new_findings:
        fid = f.get("id", make_finding_id(f.get("page", "?"), f.get("description", "?")))
        if fid in existing_ids:
            continue
        entry = {
            "id":              fid,
            "page":            f.get("page", "?"),
            "session":         TODAY,
            "severity":        f.get("severity", "low"),
            "issue":           f.get("description", ""),
            "domain":          f.get("domain", "Unknown"),
            "sentinel_agent":  f.get("sentinel_agent", ""),
            "root_cause":      f.get("root_cause",
                                     "Detected automatically by walkthrough-analyzer."),
            "has_test":        f.get("has_test", False),
            "test_file":       f.get("test_file"),
            "has_validator":   f.get("has_validator", False),
            "validator_layer": f.get("validator_layer"),
            "status":          f.get("status", "open"),
            "fix_commit":      None,
            "_proposed_gate":  f.get("proposed_gate", ""),
            "_validator_decision": f.get("validator_decision"),  # Pattern 5
            "_source":         f.get("source", "auto"),
            "_auto_gated":     f.get("_auto_gated", False),
        }
        merged.append(entry)
        existing_ids.add(fid)
        added += 1
    return merged, added


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\nWalkthrough Analyzer (Enhanced — 5 hardening-loop patterns)")
    print("=" * 62)

    # ── Load supporting data ──────────────────────────────────────────────────
    pw_report    = load_json(PW_REPORT)
    if not pw_report:
        print(f"[analyzer] {PW_REPORT} not found — console errors unavailable")

    # Pattern 3: failing validators from last gate run
    failing_validators = get_failing_validators()
    if failing_validators:
        print(f"  Gate context: {len(failing_validators)} failing validators injected")
    else:
        print(f"  Gate context: platform_health.json not found — run gate first for richer context")

    findings_data = load_json(FINDINGS_FILE)
    if not findings_data or "findings" not in findings_data:
        findings_data = {"_meta": {}, "findings": []}
    existing_findings: list[dict] = findings_data["findings"]

    if not WALKTHROUGH_DIR.exists():
        print(f"[analyzer] {WALKTHROUGH_DIR} does not exist — run walkthrough spec first")
        sys.exit(1)

    top_pngs = sorted(WALKTHROUGH_DIR.glob("page-*-top.png"))
    if not top_pngs:
        print(f"[analyzer] no page-*-top.png files in {WALKTHROUGH_DIR}")
        sys.exit(1)

    print(f"  Pages to analyze: {len(top_pngs)}\n")

    all_new:     list[dict] = []
    skipped_ai:  int        = 0
    auto_gated:  int        = 0
    total_added: int        = 0

    for png_path in top_pngs:
        name  = png_path.stem
        parts = name.split("-")
        slug  = "-".join(parts[2:-1])
        if not slug:
            continue

        # ── Pattern 1+4: Read metadata sidecar ───────────────────────────────
        meta_path = WALKTHROUGH_DIR / f"{name.replace('-top','-meta')}.json"
        meta      = load_json(meta_path) or {}
        card_heroes        = meta.get("card_heroes", [])
        chip_texts         = meta.get("chip_texts", [])
        has_data           = meta.get("has_data", slug not in NO_PLAIN_READ)
        chip_populated     = meta.get("chip_populated", slug not in NO_PLAIN_READ)
        verdict_text       = meta.get("verdict_text")
        settlement_timeout = meta.get("settlement_timed_out", False)

        # ── Pattern 2: Journey coverage check ────────────────────────────────
        coverage = get_journey_coverage(slug)

        print(f"  {slug:<25}", end=" ", flush=True)

        # ── Pattern 4: Skip AI on partial captures ────────────────────────────
        if settlement_timeout:
            print(f"PARTIAL CAPTURE — pre-built finding, no AI call")
            skipped_ai += 1
            if not DRY_RUN:
                pf = make_partial_capture_finding(slug, meta)
                pf = auto_gate_finding(pf, coverage)
                all_new.append(pf)
            continue

        if DRY_RUN:
            print(f"[dry-run] meta={bool(meta)} coverage={coverage['has_spec']} data={has_data}")
            continue

        # ── Build enriched payload (Patterns 1, 2, 3) ────────────────────────
        b64 = png_to_b64(png_path)
        payload = {
            "page_slug":          slug,
            "page_file":          f"{slug}.html",
            "screenshot_b64":     b64,
            "console_errors":     [],       # kept for future — PW report parsing TBD
            "verdict_text":       verdict_text,
            "card_heroes":        card_heroes,          # Pattern 1
            "chip_texts":         chip_texts,           # Pattern 1
            "has_data":           has_data,             # Pattern 1
            "cards_settled":      bool(card_heroes) and has_data,
            "chip_populated":     chip_populated,
            "failing_validators": failing_validators,   # Pattern 3
            "has_journey_spec":   coverage["has_spec"], # Pattern 2
            "journey_covers_chip":    coverage.get("covers_chip", False),
            "journey_covers_verdict": coverage.get("covers_verdict", False),
            "journey_covers_cards":   coverage.get("covers_cards", False),
        }

        result = call_edge_function(payload)
        if not result:
            print(f"no response from edge fn")
            continue

        findings   = result.get("findings", [])
        model_used = result.get("model_used", "unknown")

        if not findings:
            print(f"clean ({model_used})")
        else:
            # Pattern 2: auto-gate findings already covered by journey specs
            for f in findings:
                f = auto_gate_finding(f, coverage)
                if f.get("_auto_gated"):
                    auto_gated += 1

            visible = [f for f in findings if not f.get("_auto_gated")]
            print(f"{len(findings)} finding(s) [{len(visible)} new, "
                  f"{len(findings)-len(visible)} auto-gated] ({model_used})")

            for f in visible:
                sev  = f.get("severity", "?")
                desc = f.get("description", "")[:75]
                vd   = f.get("validator_decision", {})
                act  = vd.get("action", "?") if vd else "?"
                print(f"    [{sev.upper()}] {desc}")
                if vd:
                    print(f"           -> {act}: {vd.get('target_file','')}")
            all_new.extend(findings)

    if DRY_RUN:
        print(f"\n[dry-run] no changes written")
        return

    merged, added = merge_findings(existing_findings, all_new)
    total_added   = added

    findings_data["findings"] = merged
    save_json(FINDINGS_FILE, findings_data)

    print(f"\n{'-' * 62}")
    print(f"  Pages analyzed:    {len(top_pngs)}")
    print(f"  AI calls skipped:  {skipped_ai}  (partial captures — Pattern 4)")
    print(f"  Auto-gated:        {auto_gated}  (journey spec already covers — Pattern 2)")
    print(f"  New findings:      {total_added}")
    print(f"  Total in registry: {len(merged)}")

    if total_added > 0:
        print(f"\n  New findings in {FINDINGS_FILE}.")
        print(f"  Run: python validate_playwright_staleness.py")
    else:
        print(f"\n  No new findings.")


if __name__ == "__main__":
    main()
