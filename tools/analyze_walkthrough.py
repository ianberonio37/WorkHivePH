"""
tools/analyze_walkthrough.py -- WorkHive Walkthrough Analyzer
==============================================================
Unified analyzer that closes the hardening loop by combining:

  INPUT 1: Visual walkthrough screenshots (.tmp/walkthrough/page-NN-slug-top.png)
  INPUT 2: Page DOM metadata (.tmp/walkthrough/page-NN-slug-meta.json)
           Written by the walkthrough spec: verdict_text, card_heroes,
           chip_texts, has_data, chip_populated, settlement_timed_out
  INPUT 3: Journey test results (playwright-report.json)
           Parsed for: test failures, soft-skips, scenario coverage
  INPUT 4: Platform gate results (platform_health.json)
           Written by run_platform_checks.py --fast

FINDING CLASSES produced:
  visual_finding  -- AI vision classified something wrong in the screenshot
  test_failure    -- A journey scenario failed outright
  soft_skip       -- A journey scenario found no element and returned early;
                     signals a seeder gap or a missing DOM element

HARDENING LOOP INTEGRATION:
  Step 1 (Coverage audit)    -- soft_skip + test_failure findings
  Step 2 (Seeder fill)       -- soft_skip findings pointing at seeder
  Step 3 (Playwright enh.)   -- specific new-scenario proposals per finding
  Step 4 (Full gate)         -- platform_health.json enriches domain context
  Step 5 (Visual)            -- visual_finding on ALL pages (never skip)
  Step 6 (Validator decision)-- every finding has validator_decision struct

CLOSED LOOP:
  After writing findings.json, runs validate_playwright_staleness.py
  automatically. For ungated findings, auto-calls proposal generator.

Run order (full hardening loop steps 4-6):
  python run_platform_checks.py --fast
  npx playwright test tests/plain-read-walkthrough.spec.ts tests/journey-*.spec.ts
  python tools/analyze_walkthrough.py
"""

import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

# ---- Config ------------------------------------------------------------------

WALKTHROUGH_DIR = Path(".tmp") / "walkthrough"
PW_REPORT       = Path("playwright-report.json")
FINDINGS_FILE   = Path("findings.json")
PLATFORM_HEALTH = Path("platform_health.json")
TESTS_DIR       = Path("tests")

SUPABASE_URL    = os.getenv("SUPABASE_URL", "https://hzyvnjtisfgbksicrouu.supabase.co")
SUPABASE_ANON   = os.getenv("SUPABASE_ANON_KEY", "")
EDGE_FN_URL     = f"{SUPABASE_URL}/functions/v1/walkthrough-analyzer"

DRY_RUN         = "--dry-run" in sys.argv
TODAY           = date.today().isoformat()

# Journey spec stem -> page slug
SPEC_SLUG_MAP = {
    "journey-alerts":  "alert-hub",
    "journey-pm":      "pm-scheduler",
    "journey-pm-mgr":  "project-manager",
}


# ---- Helpers -----------------------------------------------------------------

def load_json(path):
    if not Path(path).exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[analyzer] warning: could not load {path}: {e}")
        return None


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def png_to_b64(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def make_id(slug, description):
    clean = re.sub(r"[^a-z0-9]+", "-", description.lower())[:60].strip("-")
    return f"{slug}-{clean}"


def page_slug_from_spec(spec_file):
    stem = Path(spec_file).stem
    return SPEC_SLUG_MAP.get(stem, stem.replace("journey-", "").replace("-spec", ""))


# ---- INPUT 3: Journey test parser --------------------------------------------

def _walk(node, file_ctx="", title_ctx="", failures=None, skips=None):
    if failures is None: failures = []
    if skips    is None: skips    = []
    if not isinstance(node, (dict, list)):
        return

    if isinstance(node, list):
        for item in node:
            _walk(item, file_ctx, title_ctx, failures, skips)
        return

    file  = node.get("file",  file_ctx)  or file_ctx
    title = node.get("title", title_ctx) or title_ctx

    for r in node.get("results", []):
        status = r.get("status", "")
        if status in ("failed", "timedOut"):
            err = ""
            if r.get("error"):
                err = str(r["error"].get("message", ""))[:300]
            failures.append({
                "spec_file":  file,
                "test_title": title,
                "status":     status,
                "error":      err,
                "page_slug":  page_slug_from_spec(file),
            })
        for stdout_item in r.get("stdout", []):
            text = (stdout_item.get("text") or "").strip()
            if re.search(r"\[journey[-\w]+\].*skip", text, re.IGNORECASE):
                skips.append({
                    "spec_file":    file,
                    "test_title":   title,
                    "skip_message": text[:200],
                    "page_slug":    page_slug_from_spec(file),
                })

    for k, v in node.items():
        if k in ("suites", "specs", "tests"):
            _walk(v, file, title, failures, skips)

    return failures, skips


def parse_journey_results(pw_report):
    if not pw_report:
        return [], []
    failures, skips = [], []
    _walk(pw_report, failures=failures, skips=skips)
    return failures, skips


# ---- INPUT 4: Gate context ---------------------------------------------------

def get_failing_validators():
    health = load_json(PLATFORM_HEALTH)
    if not health:
        return []
    return [
        e.get("id", "?")
        for e in health.get("results", [])
        if e.get("status") in ("FAIL", "REGRESSION")
    ][:10]


# ---- Edge function calls -----------------------------------------------------

def call_edge_fn(payload):
    if not SUPABASE_ANON:
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
        print(f"[analyzer] HTTP {e.code}: {e.read().decode('utf-8','replace')[:150]}")
        return None
    except Exception as e:
        print(f"[analyzer] error: {e}")
        return None


def generate_proposal(finding):
    result = call_edge_fn({"action": "propose", "finding": finding})
    return result.get("proposal") if result else None


# ---- Finding builders --------------------------------------------------------

def build_failure_finding(f):
    slug = f["page_slug"]
    desc = f"Journey test FAILED on {slug}: {f['test_title'][:60]}"
    if f.get("error"):
        desc += f" -- {f['error'][:60]}"
    return {
        "source":         "test_failure",
        "page":           slug,
        "description":    desc,
        "severity":       "high",
        "domain":         "Frontend Fidelity",
        "sentinel_agent": "Frontend Fidelity (journey test)",
        "root_cause":     f"Test '{f['test_title']}' failed: {f.get('error','?')[:150]}",
        "has_test":       True,
        "test_file":      f["spec_file"],
        "validator_decision": {
            "action":       "improve_existing",
            "target_file":  f["spec_file"],
            "target_layer": f"fix failing test: {f['test_title'][:50]}",
            "reason":       "Test failure regression -- fix root cause",
        },
    }


def build_softskip_finding(s):
    slug = s["page_slug"]
    msg  = s["skip_message"]

    is_seeder = any(k in msg.lower() for k in [
        "no uncompleted", "empty", "no assets", "no items", "no posts",
        "no entries", "no cards", "no template", "no plan",
    ])

    domain  = "Data Guardian" if is_seeder else "Frontend Fidelity"
    agent   = "Data Guardian (seeder fill)" if is_seeder else "Frontend Fidelity (DOM)"
    target  = "test-data-seeder/seeders/*.py" if is_seeder else s["spec_file"]
    layer   = "ensure test data for this scenario" if is_seeder else "fix element selector"

    return {
        "source":         "soft_skip",
        "page":           slug,
        "description":    f"Soft-skip in {slug} journey: {msg[:100]}",
        "severity":       "medium",
        "domain":         domain,
        "sentinel_agent": agent,
        "root_cause":     (
            "Seeder does not guarantee required data for this scenario"
            if is_seeder else "DOM element or condition missing in test env"
        ),
        "has_test":       True,
        "test_file":      s["spec_file"],
        "validator_decision": {
            "action":       "improve_existing",
            "target_file":  target,
            "target_layer": layer,
            "reason":       f"Soft-skip prevents scenario from asserting: {msg[:80]}",
        },
    }


# ---- Finding registry --------------------------------------------------------

def merge_findings(existing, new_findings):
    existing_ids = {f["id"] for f in existing}
    added, merged = 0, list(existing)
    for f in new_findings:
        fid = f.get("id", make_id(f.get("page", "?"), f.get("description", "?")))
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
            "root_cause":      f.get("root_cause", "Detected automatically."),
            "has_test":        f.get("has_test", False),
            "test_file":       f.get("test_file"),
            "has_validator":   f.get("has_validator", False),
            "validator_layer": f.get("validator_layer"),
            "status":          f.get("status", "open"),
            "fix_commit":      None,
            "_validator_decision": f.get("validator_decision"),
            "_source":         f.get("source", "auto"),
        }
        merged.append(entry)
        existing_ids.add(fid)
        added += 1
    return merged, added


# ---- Main --------------------------------------------------------------------

def main():
    print("\nWalkthrough Analyzer -- Unified Hardening Loop (Steps 1-6)")
    print("=" * 62)

    pw_report          = load_json(PW_REPORT)
    failing_validators = get_failing_validators()

    if pw_report:
        print("  Journey results:  playwright-report.json found")
    else:
        print("  Journey results:  NOT found -- run journey tests for full analysis")
        print("    npx playwright test tests/journey-*.spec.ts")

    if failing_validators:
        print(f"  Gate context:     {len(failing_validators)} failing validators injected")
    else:
        print("  Gate context:     no platform_health.json -- run gate first")

    findings_data = load_json(FINDINGS_FILE) or {"_meta": {}, "findings": []}
    existing: list = findings_data.get("findings", [])

    if not WALKTHROUGH_DIR.exists():
        print(f"\n[analyzer] {WALKTHROUGH_DIR} missing -- run walkthrough spec first")
        sys.exit(1)

    top_pngs = sorted(WALKTHROUGH_DIR.glob("page-*-top.png"))
    if not top_pngs:
        print(f"[analyzer] no PNGs in {WALKTHROUGH_DIR}")
        sys.exit(1)

    print(f"  Screenshots:      {len(top_pngs)} pages\n")
    all_new = []

    # -- INPUT 3: Journey test failures + soft-skips ---------------------------
    failures, soft_skips = parse_journey_results(pw_report)

    if failures:
        print(f"  TEST FAILURES ({len(failures)}):")
        for f in failures:
            print(f"    [FAIL] [{f['page_slug']}] {f['test_title'][:65]}")
            all_new.append(build_failure_finding(f))

    if soft_skips:
        print(f"\n  SOFT SKIPS ({len(soft_skips)}) -- seeder/DOM gaps:")
        for s in soft_skips:
            print(f"    [SKIP] [{s['page_slug']}] {s['skip_message'][:80]}")
            all_new.append(build_softskip_finding(s))

    if pw_report and not failures and not soft_skips:
        print("  Journey tests:    all passed, no soft-skips")

    # -- INPUT 1+2: Visual analysis -- ALL pages, no skipping ------------------
    print(f"\n  VISUAL ANALYSIS ({len(top_pngs)} pages):")

    for png_path in top_pngs:
        name  = png_path.stem
        parts = name.split("-")
        slug  = "-".join(parts[2:-1])
        if not slug:
            continue

        meta_path = WALKTHROUGH_DIR / f"{name.replace('-top', '-meta')}.json"
        meta      = load_json(meta_path) or {}

        card_heroes        = meta.get("card_heroes", [])
        chip_texts         = meta.get("chip_texts", [])
        has_data           = meta.get("has_data", True)
        chip_populated     = meta.get("chip_populated", True)
        verdict_text       = meta.get("verdict_text")
        settlement_timeout = meta.get("settlement_timed_out", False)

        print(f"    {slug:<28}", end=" ", flush=True)

        if DRY_RUN:
            print(f"[dry-run] timeout={settlement_timeout} data={has_data}")
            continue

        # Context for the AI -- settlement_timeout and has_data are CONTEXT not filters.
        # We analyze ALL pages. The AI uses context to focus on what matters.
        partial_note = (
            "PARTIAL CAPTURE: page was captured mid-load. "
            "Focus on STRUCTURAL issues (missing chips, obvious crashes, layout breaks). "
            "Do NOT flag empty data values -- page may still be loading."
            if settlement_timeout else ""
        )
        data_note = (
            "NO SEEDER DATA: has_data=false -- empty cards/verdict are expected. "
            "Focus only on structural/layout issues."
            if not has_data else
            f"Seeder data present. card_heroes={card_heroes}. chips={chip_texts[:1]}"
        )
        gate_note = (
            f"Currently failing validators: {', '.join(failing_validators)}"
            if failing_validators else "Gate passing."
        )

        b64 = png_to_b64(png_path)
        payload = {
            "page_slug":          slug,
            "page_file":          f"{slug}.html",
            "screenshot_b64":     b64,
            "console_errors":     [],
            "verdict_text":       verdict_text,
            "card_heroes":        card_heroes,
            "chip_texts":         chip_texts,
            "has_data":           has_data,
            "cards_settled":      bool(card_heroes) and has_data and not settlement_timeout,
            "chip_populated":     chip_populated,
            "partial_capture":    settlement_timeout,
            "partial_note":       partial_note,
            "data_note":          data_note,
            "gate_note":          gate_note,
            "failing_validators": failing_validators,
        }

        result = call_edge_fn(payload)
        if not result:
            print("no response")
            continue

        findings   = result.get("findings", [])
        model_used = result.get("model_used", "unknown")

        if not findings:
            pfx = "(partial) " if settlement_timeout else ""
            print(f"clean {pfx}({model_used})")
        else:
            print(f"{len(findings)} finding(s) ({model_used})")
            for f in findings:
                sev = f.get("severity", "?")
                vd  = f.get("validator_decision") or {}
                print(f"      [{sev.upper()}] {f.get('description','')[:70]}")
                if vd.get("action"):
                    print(f"             -> {vd['action']}: {vd.get('target_file','')}")
            all_new.extend(findings)

    if DRY_RUN:
        print(f"\n[dry-run] {len(all_new)} findings would be written")
        return

    # -- Write findings --------------------------------------------------------
    merged, added = merge_findings(existing, all_new)
    findings_data["findings"] = merged
    save_json(FINDINGS_FILE, findings_data)

    # -- Auto-propose for ungated findings ------------------------------------
    ungated = [
        f for f in merged
        if f.get("status") == "open"
        and not f.get("has_test")
        and not f.get("has_validator")
        and not f.get("_validator_decision")
        and f.get("severity") in ("critical", "high", "medium")
    ]

    if ungated and SUPABASE_ANON:
        print(f"\n  AUTO-PROPOSE: {len(ungated)} ungated finding(s)...")
        for f in ungated[:5]:
            proposal = generate_proposal(f)
            if proposal:
                f["_validator_decision"] = proposal
                action = proposal.get("action", "?")
                target = proposal.get("target_file", "")
                print(f"    [{f['severity'].upper()}] [{f['page']}] -> {action}: {target}")
        save_json(FINDINGS_FILE, findings_data)

    # -- Summary ---------------------------------------------------------------
    ungated_count = sum(
        1 for f in merged
        if f.get("status") == "open"
        and not f.get("has_test")
        and not f.get("has_validator")
        and f.get("severity") in ("critical", "high", "medium")
    )

    print(f"\n{'-' * 62}")
    print(f"  Failures:     {len(failures)}")
    print(f"  Soft-skips:   {len(soft_skips)}")
    print(f"  New findings: {added}")
    print(f"  Ungated open: {ungated_count}")
    print(f"  Registry:     {len(merged)} total")

    # -- Closed loop: run L13 -------------------------------------------------
    print(f"\n  Running L13 gate...")
    r = subprocess.run(
        [sys.executable, "validate_playwright_staleness.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in ["PASS", "FAIL", "WARN", "open:", "total:", "All "]):
            print(f"  {line.strip()}")

    if r.returncode == 0:
        print("\n  Loop CLOSED -- L13 passing.")
    else:
        print("\n  Loop OPEN -- L13 failing. Check findings.json for ungated findings.")


if __name__ == "__main__":
    main()
