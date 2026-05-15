"""
tools/analyze_walkthrough.py — WorkHive Walkthrough Analyzer
=============================================================
Phase 2 of the self-improving test architecture.

Reads the screenshots captured by tests/plain-read-walkthrough.spec.ts
(from .tmp/walkthrough/), the Playwright JSON report (playwright-report.json),
and calls the walkthrough-analyzer Supabase edge function for each page.

The edge function uses the platform's own callAI / callAIMultimodal chain
(Groq Scout, OpenRouter Gemma, etc.) — no external API keys required here.

For each page:
  - Reads page-NN-<slug>-top.png (base64)
  - Reads console errors from playwright-report.json
  - Calls walkthrough-analyzer edge function
  - Receives structured findings
  - Merges new findings into findings.json (skips duplicates by id)

Usage:
  python tools/analyze_walkthrough.py
  python tools/analyze_walkthrough.py --dry-run   # print findings, don't write

After this runs, check findings.json and run validate_playwright_staleness.py
to see if L13b (finding closure) is still satisfied. New open findings will
cause L13b to FAIL (ratchet) until they are gated by a test or validator.

Skills consulted: ai-engineer (callAI chain via edge fn, no provider SDK),
platform-guardian (findings.json as memory layer, L13 gate contract).
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

WALKTHROUGH_DIR  = Path(".tmp") / "walkthrough"
PW_REPORT        = Path("playwright-report.json")
FINDINGS_FILE    = Path("findings.json")

SUPABASE_URL     = os.getenv("SUPABASE_URL", "https://hzyvnjtisfgbksicrouu.supabase.co")
SUPABASE_ANON    = os.getenv("SUPABASE_ANON_KEY", "")
EDGE_FN_URL      = f"{SUPABASE_URL}/functions/v1/walkthrough-analyzer"

DRY_RUN          = "--dry-run" in sys.argv
TODAY            = date.today().isoformat()

# Pages that don't render verdict/cards — chip timeout is expected
NO_CHIP_PAGES    = {"logbook", "voice-journal", "engineering-design", "community", "audit-log"}

# Severity ordering for dedup (higher wins)
SEV_ORDER        = {"critical": 4, "high": 3, "medium": 2, "low": 1}


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


def extract_console_errors(report: dict | None, slug: str) -> list[str]:
    """Extract console pageerror messages for a specific page from the PW report."""
    if not report:
        return []
    errors: list[str] = []
    for suite in report.get("suites", []):
        for spec in suite.get("specs", []) + [suite]:
            for test in spec.get("tests", []):
                title = test.get("title", "")
                if slug not in title.lower():
                    continue
                for result in test.get("results", []):
                    for attachment in result.get("attachments", []):
                        if "error" in attachment.get("name", "").lower():
                            body = attachment.get("body", "")
                            if body:
                                errors.append(body[:300])
    return errors[:10]


def call_edge_function(payload: dict) -> dict | None:
    """Call the walkthrough-analyzer edge function. Returns findings dict or None."""
    if not SUPABASE_ANON:
        print("[analyzer] SUPABASE_ANON_KEY not set — skipping edge fn call (dry-run mode)")
        return None

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        EDGE_FN_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SUPABASE_ANON}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[analyzer] edge fn HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"[analyzer] edge fn error: {e}")
        return None


def make_finding_id(slug: str, description: str) -> str:
    """Generate a stable slug-based finding ID."""
    clean = re.sub(r"[^a-z0-9]+", "-", description.lower())[:60].strip("-")
    return f"{slug}-{clean}"


def merge_findings(existing: list[dict], new_findings: list[dict]) -> tuple[list[dict], int]:
    """Merge new findings into existing list, skipping exact-ID duplicates.
    Returns (merged_list, count_added)."""
    existing_ids = {f["id"] for f in existing}
    added = 0
    merged = list(existing)
    for f in new_findings:
        fid = f.get("id", make_finding_id(f.get("page", "?"), f.get("description", "?")))
        if fid in existing_ids:
            continue
        # Build a clean finding entry
        entry = {
            "id":             fid,
            "page":           f.get("page", "?"),
            "session":        TODAY,
            "severity":       f.get("severity", "low"),
            "issue":          f.get("description", ""),
            "domain":         f.get("domain", "Unknown"),
            "sentinel_agent": f.get("sentinel_agent", ""),
            "root_cause":     "Detected automatically by walkthrough-analyzer. Investigate before gating.",
            "has_test":       False,
            "test_file":      None,
            "has_validator":  False,
            "validator_layer": None,
            "status":         "open",
            "fix_commit":     None,
            "_proposed_gate": f.get("proposed_gate", ""),
            "_source":        f.get("source", "auto"),
        }
        merged.append(entry)
        existing_ids.add(fid)
        added += 1
    return merged, added


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\nWalkthrough Analyzer — Phase 2 self-improving test architecture")
    print("=" * 62)

    # Load PW report for console error extraction
    pw_report = load_json(PW_REPORT)
    if not pw_report:
        print(f"[analyzer] {PW_REPORT} not found — console errors will be empty. Run the walkthrough spec first.")

    # Load existing findings
    findings_data = load_json(FINDINGS_FILE)
    if not findings_data or "findings" not in findings_data:
        print(f"[analyzer] {FINDINGS_FILE} not found — creating fresh registry")
        findings_data = {"_meta": {}, "findings": []}
    existing_findings: list[dict] = findings_data["findings"]

    # Discover captured pages from walkthrough output directory
    if not WALKTHROUGH_DIR.exists():
        print(f"[analyzer] {WALKTHROUGH_DIR} does not exist. Run the walkthrough spec first:")
        print("  npx playwright test tests/plain-read-walkthrough.spec.ts")
        sys.exit(1)

    top_pngs = sorted(WALKTHROUGH_DIR.glob("page-*-top.png"))
    if not top_pngs:
        print(f"[analyzer] no page-*-top.png files in {WALKTHROUGH_DIR}")
        sys.exit(1)

    print(f"  Found {len(top_pngs)} page screenshots to analyze\n")

    all_new: list[dict] = []
    total_added = 0

    for png_path in top_pngs:
        # Extract slug from filename: page-01-hive-top.png → hive
        name = png_path.stem  # "page-01-hive-top"
        parts = name.split("-")
        # parts[0]="page", parts[1]=NN, parts[2..N-1]=slug words, parts[-1]="top"
        slug = "-".join(parts[2:-1])
        if not slug:
            continue

        print(f"  Analyzing page: {slug} ...", end=" ", flush=True)

        # Build payload
        b64 = png_to_b64(png_path)
        console_errors = extract_console_errors(pw_report, slug)

        # Read the walkthrough spec to get basic render metadata
        # (simplified: just flag common known states)
        payload = {
            "page_slug":      slug,
            "page_file":      f"{slug}.html",
            "screenshot_b64": b64,
            "console_errors": console_errors,
            "verdict_text":   None,   # analyzer infers from screenshot
            "cards_settled":  slug not in NO_CHIP_PAGES,
            "chip_populated": slug not in NO_CHIP_PAGES,
        }

        if DRY_RUN:
            print(f"[dry-run] would call edge fn for {slug}")
            continue

        result = call_edge_function(payload)
        if not result:
            print(f"no response from edge fn")
            continue

        findings = result.get("findings", [])
        model    = result.get("model_used", "unknown")

        if not findings:
            print(f"clean ({model})")
        else:
            print(f"{len(findings)} finding(s) ({model})")
            for f in findings:
                sev = f.get("severity", "?")
                desc = f.get("description", "")[:80]
                print(f"    [{sev.upper()}] {desc}")
            all_new.extend(findings)

    if DRY_RUN:
        print("\n[dry-run] no changes written")
        return

    # Merge new findings
    merged, added = merge_findings(existing_findings, all_new)
    total_added += added

    # Write back
    findings_data["findings"] = merged
    save_json(FINDINGS_FILE, findings_data)

    print(f"\n{'-' * 62}")
    print(f"  Pages analyzed:   {len(top_pngs)}")
    print(f"  New findings:     {total_added}")
    print(f"  Total in registry: {len(merged)}")

    if total_added > 0:
        print(f"\n  New findings written to {FINDINGS_FILE}.")
        print(f"  Run validate_playwright_staleness.py to check if L13b is still satisfied.")
        print(f"  Each new finding needs has_test=true OR has_validator=true to clear the gate.")
    else:
        print(f"\n  No new findings. {FINDINGS_FILE} unchanged.")


if __name__ == "__main__":
    main()
