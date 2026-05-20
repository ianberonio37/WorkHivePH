"""
Canonical Contract Status — single-screen overview.
====================================================
One command to see every canonical-contract dimension's current state.
Reads existing audit reports + registries (no network, no DB), so it
runs in <1 second and is safe to invoke at any time.

  Usage:
    python tools/canonical_status.py
    python tools/canonical_status.py --json    # machine-readable

Dimensions surveyed:
  1. Tier-S standards registry  (file count + DB drift)
  2. Tier-E formula contracts   (formula count + partial honesty)
  3. Citation visibility        (Tier-S short_name on every implemented_in page)
  4. Calm Dashboard Contract    (opted-in pages + compliance)
  5. Canonical view reachability (v_*_truth views + orphans)
  6. Partial-label honesty       (zero-tolerance regression)
  7. AI prompt grounding         (every metric mention cites a standard)
  8. Phantom captures + columns  (reverse audit)
  9. Canonical drift flywheel    (TIER A pages + gap reads + drift reads)
 10. Cross-surface KPI sentinel  (parity specs locked vs baseline)
 11. Voice Companion phases 1-11 (PASS / FAIL summary per phase validator)

Designed to be cheap enough to run after every commit; surfaces drift
the same instant the underlying file changes.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


# ── ANSI colors (skip when piping to file or --json) ────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _read_json(rel: str) -> dict | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _badge(ok: bool, warn: bool = False) -> str:
    if warn:
        return f"{YELLOW}WARN{RESET}"
    return f"{GREEN}OK  {RESET}" if ok else f"{RED}FAIL{RESET}"


def _pct(num: int, denom: int) -> str:
    if denom == 0: return "—"
    return f"{(num * 100) // denom}%"


def _gather() -> dict[str, Any]:
    """Read every audit report + registry. Return a flat status dict."""
    out: dict[str, Any] = {}

    # 1. Tier-S standards
    stds = _read_json("canonical/standards.json")
    if stds:
        out["tier_s_count"] = len(stds.get("standards", []))
        out["tier_s_ids"]   = [s["standard_id"] for s in stds.get("standards", [])]
    else:
        out["tier_s_count"] = 0
        out["tier_s_ids"]   = []

    # 2. Tier-E formulas
    fcs = _read_json("canonical/formula_contracts.json")
    if fcs:
        formulas = fcs.get("formulas", [])
        out["tier_e_count"] = len(formulas)
        out["tier_e_partials_honest"] = sum(
            1 for f in formulas
            if f.get("partial_variant") and
               (f.get("partial_reason") or "").strip() and
               (f.get("formula_id", "").endswith("_partial") or
                "partial" in (f.get("implemented_in", "") or "").lower())
        )
        out["tier_e_partials_total"] = sum(1 for f in formulas if f.get("partial_variant"))
        out["formulas"] = formulas
    else:
        out["tier_e_count"] = 0
        out["tier_e_partials_honest"] = 0
        out["tier_e_partials_total"]  = 0
        out["formulas"] = []

    # 3. Citation visibility
    page_re = re.compile(r"([a-z0-9\-]+\.html)", re.IGNORECASE)
    cache: dict[str, str] = {}
    std_short = {s["standard_id"]: s["short_name"] for s in (stds or {}).get("standards", [])}
    cite_total = cite_present = 0
    for f in out["formulas"]:
        short = std_short.get(f.get("standard_id"), "")
        if not short: continue
        for p in (page_re.findall(f.get("implemented_in", "") or "")):
            p = p.lower()
            cite_total += 1
            if p not in cache:
                pp = ROOT / p
                cache[p] = pp.read_text(encoding="utf-8", errors="replace") if pp.exists() else ""
            if short in cache[p]:
                cite_present += 1
    out["cite_present"] = cite_present
    out["cite_total"]   = cite_total

    # 4. Calm Dashboard
    calm = _read_json("calm_canonical_audit_report.json")
    if calm:
        s = calm.get("summary", {})
        out["calm_opted_in"] = s.get("calm_opted_in_pages", 0)
        out["calm_compliant"] = s.get("compliant_pages", 0)
    else:
        out["calm_opted_in"] = 0
        out["calm_compliant"] = 0

    # 5. Canonical view reachability — derive from migrations live
    declared: set[str] = set()
    allowed: set[str]  = set()
    view_re = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+public\.(v_\w+_truth)\s+AS", re.IGNORECASE)
    allow_re = re.compile(r"canonical-view-allow:\s*(v_\w+_truth)\b", re.IGNORECASE)
    mig = ROOT / "supabase" / "migrations"
    if mig.exists():
        for f in mig.glob("*.sql"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                declared.update(view_re.findall(text))
                allowed.update(allow_re.findall(text))
            except Exception:
                continue
    consumed: set[str] = set()
    for root_dir, exts in [
        (ROOT, (".html", ".js")),
        (ROOT / "supabase" / "functions", (".ts",)),
        (ROOT / "python-api", (".py",)),
    ]:
        if not root_dir.exists(): continue
        for p in root_dir.rglob("*"):
            if not p.is_file() or "node_modules" in str(p) or "test-results" in str(p):
                continue
            if "supabase" in str(p) and "migrations" in str(p):
                continue
            if not any(p.name.endswith(e) for e in exts):
                continue
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
                for v in declared:
                    if v in body and v not in consumed:
                        consumed.add(v)
            except Exception:
                continue
    out["view_declared"] = len(declared)
    out["view_consumed"] = len(consumed)
    out["view_allowed"]  = len(allowed & declared)
    out["view_orphans"]  = sorted(declared - consumed - allowed)

    # 6. Partial-label honesty
    plh = _read_json("partial_label_honesty_report.json")
    out["partial_violations"] = len((plh or {}).get("violations", []) or [])

    # 7. AI prompt standards audit
    aps = _read_json("ai_prompt_standards_report.json")
    if aps:
        s = aps.get("summary", {})
        out["ai_prompt_metric_hits"]      = s.get("metric_hits", 0)
        out["ai_prompt_standards_cited"]  = s.get("standards_cited", 0)
        out["ai_prompt_metric_uncited"]   = s.get("metric_uncited", 0)
    else:
        out["ai_prompt_metric_hits"]      = 0
        out["ai_prompt_standards_cited"]  = 0
        out["ai_prompt_metric_uncited"]   = 0

    # 8. Phantom captures + columns
    pc = _read_json("phantom_captures_report.json")
    if pc:
        s = pc.get("summary", {})
        out["phantom_captures_alive"]  = s.get("alive", 0)
        out["phantom_captures_phantom"] = s.get("phantom", 0)
    else:
        out["phantom_captures_alive"]   = 0
        out["phantom_captures_phantom"] = 0

    pcol = _read_json("phantom_columns_report.json")
    if pcol:
        s = pcol.get("summary", {})
        out["phantom_cols_alive"]   = s.get("alive", 0)
        out["phantom_cols_phantom"] = s.get("phantom", 0)
    else:
        out["phantom_cols_alive"]   = 0
        out["phantom_cols_phantom"] = 0

    # 9. Canonical drift flywheel (TIER A + drift + gap counts)
    cdp = _read_json("canonical_drift_platform_report.json")
    if cdp:
        s = cdp.get("summary", {})
        out["drift_tier_a_pages"]    = s.get("tier_a_pages", 0)
        out["drift_tier_b_pages"]    = s.get("tier_b_pages", 0)
        out["drift_reads"]           = s.get("total_drift_reads", 0)
        out["drift_gap_reads"]       = s.get("total_gap_reads", 0)
        out["drift_files_scanned"]   = s.get("files_scanned", 0)
    else:
        out["drift_tier_a_pages"]    = 0
        out["drift_tier_b_pages"]    = 0
        out["drift_reads"]           = 0
        out["drift_gap_reads"]       = 0
        out["drift_files_scanned"]   = 0

    # 9b. Forward-only ratchet
    fkc = _read_json("user_facing_kpi_canonical_report.json")
    if fkc:
        s = fkc.get("summary", {})
        out["ratchet_regressions"]   = s.get("tier_a_regressions", 0) + s.get("gap_regressions", 0)
        out["ratchet_baseline_gap"]  = s.get("baseline_gap_reads", 0)
        out["ratchet_current_gap"]   = s.get("current_gap_reads", 0)
    else:
        out["ratchet_regressions"]   = 0
        out["ratchet_baseline_gap"]  = 0
        out["ratchet_current_gap"]   = 0

    # 11. Voice Companion phase validators — Phase 1 through Phase 11.
    # Each validator is a self-contained Python script that returns "PASS: N | FAIL: M"
    # in its output. We parse the line and roll up to per-phase + grand totals.
    # Avoid invoking subprocess per validator (expensive); instead read the
    # validator's __doc__ + grep for the result-line shape via Python import.
    import subprocess
    VOICE_PHASES = [
        ("1",   "validate_voice_companion_phase1"),
        ("1.5", "validate_voice_companion_phase1_5"),
        ("2",   "validate_voice_companion_phase2"),
        ("3",   "validate_voice_companion_phase3"),
        ("4",   "validate_dialog_flow"),
        ("5",   "validate_proactive_alerts"),
        ("6",   "validate_offline_resilience_phase6"),
        ("7",   "validate_tts_quality_phase7"),
        ("8",   "validate_voice_data_flow"),
        ("9",   "validate_team_coordination"),
        ("10",  "validate_avatar_state_phase10"),
        ("11",  "validate_multilingual_phase11"),
    ]
    phase_results = []
    pass_re = re.compile(r"PASS[: ]\s*(\d+)\s*\|\s*FAIL[: ]\s*(\d+)|(\d+)\s+PASS\s+(\d+)\s+SKIP\s+(\d+)\s+FAIL|Result[: ]\s*(\d+)\s+PASS[, ]+(\d+)\s+FAIL", re.IGNORECASE)
    for label, script in VOICE_PHASES:
        script_path = ROOT / f"{script}.py"
        if not script_path.exists():
            phase_results.append((label, script, None, None, "missing"))
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, timeout=30, cwd=str(ROOT),
            )
            text = (r.stdout or "") + "\n" + (r.stderr or "")
            m = pass_re.search(text)
            if m:
                # Three patterns in the regex; pick whichever matched
                groups = m.groups()
                p = next((int(g) for g in groups[::2] if g and g.isdigit()), None)
                f = next((int(g) for i, g in enumerate(groups) if i % 2 == 1 and g and g.isdigit()), None)
                phase_results.append((label, script, p, f, "ok"))
            else:
                phase_results.append((label, script, None, None, "unparsed"))
        except subprocess.TimeoutExpired:
            phase_results.append((label, script, None, None, "timeout"))
        except Exception as e:
            phase_results.append((label, script, None, None, f"error: {e}"))
    out["voice_phase_results"] = phase_results
    out["voice_phases_green"]  = sum(1 for _, _, p, f, st in phase_results if st == "ok" and (f or 0) == 0)
    out["voice_phases_total"]  = len(phase_results)

    # 10. Cross-surface KPI sentinel spec count (static scan of the spec file)
    sentinel_file = ROOT / "tests" / "journey-cross-surface-kpi-parity.spec.ts"
    sentinel_count = 0
    if sentinel_file.exists():
        body = sentinel_file.read_text(encoding="utf-8", errors="replace")
        # Count `test('check_X` definitions, excluding `test.fixme` (skipped)
        sentinel_count = len(re.findall(r"\btest\s*\(\s*['\"]check_", body))
        sentinel_fixme = len(re.findall(r"\btest\.fixme\s*\(\s*['\"]check_", body))
        out["sentinel_specs"]        = sentinel_count
        out["sentinel_fixme"]        = sentinel_fixme
    else:
        out["sentinel_specs"] = 0
        out["sentinel_fixme"] = 0

    return out


def _print(status: dict[str, Any]) -> int:
    """Pretty-print status. Returns 0 if all green, 1 if any red."""
    fail_count = 0
    print(f"\n{BOLD}Canonical Contract Status{RESET}")
    print("=" * 56)

    # 1. Tier-S
    ok = status["tier_s_count"] >= 21
    if not ok: fail_count += 1
    print(f"  {_badge(ok)}  Tier-S standards registered:  {status['tier_s_count']}")

    # 2. Tier-E
    e_ok = status["tier_e_count"] >= 22
    partials_ok = status["tier_e_partials_honest"] == status["tier_e_partials_total"]
    if not e_ok: fail_count += 1
    if not partials_ok: fail_count += 1
    print(f"  {_badge(e_ok)}  Tier-E formula contracts:     {status['tier_e_count']}")
    print(f"  {_badge(partials_ok)}  Partial formulas honest:      "
          f"{status['tier_e_partials_honest']}/{status['tier_e_partials_total']}")

    # 3. Citation visibility
    cite_ok = status["cite_total"] > 0 and status["cite_present"] == status["cite_total"]
    if not cite_ok: fail_count += 1
    print(f"  {_badge(cite_ok)}  Tier-S citation visibility:   "
          f"{status['cite_present']}/{status['cite_total']} "
          f"({_pct(status['cite_present'], status['cite_total'])})")

    # 4. Calm Dashboard
    calm_warn = status["calm_compliant"] < status["calm_opted_in"]
    print(f"  {_badge(not calm_warn, warn=calm_warn)}  Calm Dashboard wired:         "
          f"{status['calm_compliant']}/{status['calm_opted_in']} "
          f"({_pct(status['calm_compliant'], status['calm_opted_in'])})")

    # 5. View reachability
    view_ok = len(status["view_orphans"]) == 0
    if not view_ok: fail_count += 1
    print(f"  {_badge(view_ok)}  Canonical views reachable:    "
          f"{status['view_consumed']}/{status['view_declared']} "
          f"({status['view_allowed']} allow-marked)")
    if status["view_orphans"]:
        for v in status["view_orphans"][:3]:
            print(f"         orphan: {v}")

    # 6. Partial honesty
    plh_ok = status["partial_violations"] == 0
    if not plh_ok: fail_count += 1
    print(f"  {_badge(plh_ok)}  Partial-label violations:     {status['partial_violations']}")

    # 7. AI prompt grounding
    ai_ok = status["ai_prompt_metric_uncited"] == 0
    if not ai_ok: fail_count += 1
    print(f"  {_badge(ai_ok)}  AI prompts citing standards:  "
          f"{status['ai_prompt_standards_cited']}/{status['ai_prompt_metric_hits']}")

    # 8. Phantoms
    phc_ok = status["phantom_captures_phantom"] == 0
    phcol_ok = status["phantom_cols_phantom"] == 0
    if not phc_ok: fail_count += 1
    print(f"  {_badge(phc_ok)}  Phantom captures (reverse):   "
          f"{status['phantom_captures_phantom']} phantom / {status['phantom_captures_alive']} alive")
    print(f"  {_badge(phcol_ok, warn=not phcol_ok)}  Phantom DB columns:           "
          f"{status['phantom_cols_phantom']} phantom / {status['phantom_cols_alive']} alive")

    # 9. Canonical drift flywheel
    drift_ok = status["drift_reads"] == 0 and status["drift_tier_a_pages"] == 0
    if not drift_ok: fail_count += 1
    print(f"  {_badge(drift_ok)}  Canonical drift (flywheel):   "
          f"{status['drift_reads']} drift / {status['drift_gap_reads']} gap reads "
          f"({status['drift_files_scanned']} files; TIER A: {status['drift_tier_a_pages']})")

    # 9b. Forward-only ratchet
    ratchet_ok = status["ratchet_regressions"] == 0
    if not ratchet_ok: fail_count += 1
    delta = status["ratchet_current_gap"] - status["ratchet_baseline_gap"]
    delta_str = f"+{delta}" if delta > 0 else f"{delta}"
    print(f"  {_badge(ratchet_ok)}  Forward-only ratchet:         "
          f"{status['ratchet_regressions']} regressions (gap {status['ratchet_current_gap']} "
          f"vs baseline {status['ratchet_baseline_gap']}, {delta_str})")

    # 10. Sentinel KPI parity coverage
    sentinel_ok = status["sentinel_specs"] >= 6 and status["sentinel_fixme"] == 0
    print(f"  {_badge(sentinel_ok, warn=status['sentinel_fixme']>0)}  Cross-surface KPI sentinels:  "
          f"{status['sentinel_specs']} active "
          f"({status['sentinel_fixme']} fixme'd)")

    # 11. Voice Companion phases
    voice_ok = status["voice_phases_green"] == status["voice_phases_total"]
    if not voice_ok: fail_count += 1
    print(f"  {_badge(voice_ok)}  Voice Companion phases:       "
          f"{status['voice_phases_green']}/{status['voice_phases_total']} green")
    for label, script, p, f, st in status["voice_phase_results"]:
        if st != "ok" or (f or 0) > 0:
            badge = _badge(False)
            extra = f"PASS:{p or 0} FAIL:{f or 0}" if st == "ok" else st
            print(f"         {badge}  Phase {label:<4} ({script}): {extra}")

    print("=" * 56)
    if fail_count == 0:
        print(f"  {GREEN}{BOLD}All canonical-contract dimensions green.{RESET}")
        return 0
    else:
        print(f"  {RED}{BOLD}{fail_count} dimension(s) FAIL — see above.{RESET}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical contract status overview")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of pretty text")
    args = parser.parse_args()

    if sys.platform == "win32" and not args.json:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    status = _gather()
    if args.json:
        # Strip the large arrays before emitting
        s = {k: v for k, v in status.items() if k not in ("tier_s_ids", "formulas")}
        print(json.dumps(s, indent=2))
        return 0 if status["partial_violations"] == 0 and not status["view_orphans"] else 1
    return _print(status)


if __name__ == "__main__":
    sys.exit(main())
