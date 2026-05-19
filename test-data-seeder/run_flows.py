"""Playwright UI flow runner.

Drives Chromium headless against http://127.0.0.1:5000/workhive/* (the proxy
that points at local Supabase). Sign in once as a seeded worker, then run
each flow module's checks.

Usage:  python run_flows.py
"""
import sys
import io

# Force UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

from flows.harness import browser_session, sign_in, SCREENSHOTS_DIR
from flows import smoke, logbook, community, analytics, isolation, signup, mobile
from flows import ai_assistant, ai_analytics, ai_semantic, ai_generation, ai_chains
from flows import visual, performance
from flows import hive_dashboard, logbook_crud, inventory_flow, pm_flow, skillmatrix_flow
from flows import marketplace_flow, dayplanner_flow, engineering_flow, assistant_flow
from flows import report_sender_flow, platform_health_flow, project_flow, cmms_ui_flow
from flows import intelligence_flow, static_pages_flow
from flows import achievements_flow
# Phase A onward: graph layer + intelligence + auto-staging
from flows import asset_hub_flow, alert_hub_flow, shift_brain_flow
from flows import qr_scanner_flow, global_search_flow
from flows import work_order_flow, ml_predictive_flow, auto_staging_flow
from flows import home_dashboard_flow
from flows import voice_action_router_flow
from flows import canonical_sources_flow

WITH_AI = "--with-ai" in sys.argv
WITH_VISUAL = "--with-visual" in sys.argv
WITH_PERF = "--with-perf" in sys.argv


def main():
    print("WorkHive Playwright UI runner")
    print(f"Screenshots will be saved to: {SCREENSHOTS_DIR}")
    print()

    section_results = []
    total_pass = total_fail = total_warn = 0

    with sync_playwright() as pw:
        with browser_session(pw, headless=True) as (page, errors, warnings):

            # 1. Sign in once at the start
            try:
                sign_in(page, log=print)
            except Exception as e:
                print(f"FATAL: sign-in failed: {type(e).__name__}: {e}")
                print("Make sure local Supabase is running and the seeder has run with auth users.")
                return 1

            # 2. Run smoke (open every page, count console errors)
            print("\n[Smoke test]")
            smoke_out = smoke.run(page, errors, warnings, log=print)
            section_results.append(("Smoke", smoke_out))
            total_fail += smoke_out["fail_count"]
            total_pass += smoke_out["total"] - smoke_out["fail_count"]

            # 3. Per-page deep checks
            for label, mod in [
                ("Hive Dashboard", hive_dashboard),
                ("Home Dashboard", home_dashboard_flow),
                ("Logbook CRUD",   logbook_crud),
                ("Inventory",      inventory_flow),
                ("PM Scheduler",   pm_flow),
                ("Skill Matrix",   skillmatrix_flow),
                ("Marketplace",    marketplace_flow),
                ("Day Planner",    dayplanner_flow),
                ("Engineering",    engineering_flow),
                ("AI Assistant",   assistant_flow),
                ("Report Sender",   report_sender_flow),
                ("Platform Health",  platform_health_flow),
                ("Project Manager",   project_flow),
                ("CMMS Integration",  cmms_ui_flow),
                ("PH Intelligence",    intelligence_flow),
                ("Static Pages",       static_pages_flow),
                ("Achievements",       achievements_flow),
                ("Asset Hub",          asset_hub_flow),
                ("Alert Hub",          alert_hub_flow),
                ("Shift Brain",        shift_brain_flow),
                ("QR Scanner",         qr_scanner_flow),
                ("Global Search",      global_search_flow),
                ("Work Order State",   work_order_flow),
                ("ML Predictive",      ml_predictive_flow),
                ("Auto-Staging",       auto_staging_flow),
                ("Voice Action Router", voice_action_router_flow),
                ("Canonical Sources",   canonical_sources_flow),
                ("Logbook",            logbook),
                ("Community",      community),
                ("Analytics",      analytics),
                ("Hive isolation", isolation),
            ]:
                print(f"\n[{label}]")
                try:
                    out = mod.run(page, errors, warnings, log=print)
                except Exception as e:
                    print(f"  ✗ flow crashed: {type(e).__name__}: {e}")
                    out = {"results": [("FAIL", f"crashed: {e}")]}
                section_results.append((label, out))
                for r in out.get("results", []):
                    if r[0] == "PASS": total_pass += 1
                    elif r[0] == "FAIL": total_fail += 1
                    elif r[0] == "WARN": total_warn += 1

            # 4. Sign-up edge cases (clears auth — runs LAST in this session so it
            # doesn't disturb the signed-in flows above)
            print("\n[Sign-up edge cases]")
            try:
                out = signup.run(page, errors, warnings, log=print)
            except Exception as e:
                print(f"  ✗ flow crashed: {type(e).__name__}: {e}")
                out = {"results": [("FAIL", f"crashed: {e}")]}
            section_results.append(("Signup", out))
            for r in out.get("results", []):
                if r[0] == "PASS": total_pass += 1
                elif r[0] == "FAIL": total_fail += 1
                elif r[0] == "WARN": total_warn += 1

        # 4a. Performance budgets — page load timings vs fixed budgets
        if WITH_PERF:
            print("\n[Performance budgets]")
            try:
                out = performance.run_in_perf_browser(pw, log=print)
            except Exception as e:
                print(f"  ✗ flow crashed: {type(e).__name__}: {e}")
                out = {"results": [("FAIL", f"crashed: {e}")]}
            section_results.append(("Performance", out))
            for r in out.get("results", []):
                if r[0] == "PASS": total_pass += 1
                elif r[0] == "FAIL": total_fail += 1
                elif r[0] == "WARN": total_warn += 1

        # 4b. Visual regression — pixel-diff baselines
        if WITH_VISUAL:
            print("\n[Visual regression]")
            try:
                out = visual.run_in_visual_browser(pw, log=print)
            except Exception as e:
                print(f"  flow crashed: {type(e).__name__}: {e}")
                out = {"results": [("FAIL", f"crashed: {e}")]}
            section_results.append(("Visual", out))
            for r in out.get("results", []):
                if r[0] == "PASS": total_pass += 1
                elif r[0] == "FAIL": total_fail += 1
                elif r[0] == "WARN": total_warn += 1

        # 4c. Platform Quality Loop — walkthrough capture + AI analyzer + L13 gate
        # Runs after pixel-diff so both visual signals are in the same gate pass.
        if WITH_VISUAL:
            print("\n[Platform Quality Loop — walkthrough + analyzer + L13]")
            import subprocess as _sp, os as _os, sys as _sys
            _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            _py   = _sys.executable
            _cwd  = "Z:\\" if _os.path.exists("Z:/playwright.config.ts") else _root
            _ansi = __import__("re").compile(r"\x1b\[[0-9;]*m")

            def _node_run(cmd, cwd):
                try:
                    proc = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                                     cwd=cwd, bufsize=1,
                                     text=True, encoding="utf-8", errors="replace",
                                     shell=True)
                    last = ""
                    for line in proc.stdout:
                        clean = _ansi.sub("", line.rstrip())
                        if clean:
                            print(f"  {clean}")
                            last = clean
                    proc.wait()
                    return proc.returncode, last
                except Exception as e:
                    print(f"  ERROR: {e}")
                    return 1, str(e)

            def _py_run(script):
                try:
                    proc = _sp.Popen([_py, "-u", script],
                                     stdout=_sp.PIPE, stderr=_sp.STDOUT,
                                     cwd=_root, bufsize=1,
                                     text=True, encoding="utf-8", errors="replace")
                    last = ""
                    for line in proc.stdout:
                        clean = _ansi.sub("", line.rstrip())
                        if clean:
                            print(f"  {clean}")
                            last = clean
                    proc.wait()
                    return proc.returncode, last
                except Exception as e:
                    print(f"  ERROR: {e}")
                    return 1, str(e)

            pql_results = []

            # Step 1: Walkthrough spec (capture screenshots + metadata)
            print("  [1/3] Running walkthrough spec (23 pages)...")
            rc1, _ = _node_run(
                ["npx", "playwright", "test",
                 "tests/plain-read-walkthrough.spec.ts",
                 "--reporter=line"],
                _cwd,
            )
            pql_results.append(("PASS" if rc1 == 0 else "WARN", f"Walkthrough capture rc={rc1}"))

            # Step 2: Analyzer (AI classifies findings + updates findings.json)
            print("  [2/3] Running walkthrough analyzer...")
            import os as _os2
            env = {**_os2.environ,
                   "SUPABASE_URL":      _os2.getenv("SUPABASE_URL", ""),
                   "SUPABASE_ANON_KEY": _os2.getenv("SUPABASE_ANON_KEY", "")}
            try:
                proc2 = _sp.Popen([_py, "-u", _os.path.join(_root, "tools", "analyze_walkthrough.py")],
                                   stdout=_sp.PIPE, stderr=_sp.STDOUT,
                                   cwd=_root, bufsize=1,
                                   text=True, encoding="utf-8", errors="replace",
                                   env=env)
                last2 = ""
                for line in proc2.stdout:
                    clean = _ansi.sub("", line.rstrip())
                    if clean:
                        print(f"  {clean}")
                        last2 = clean
                proc2.wait()
                pql_results.append(("PASS" if proc2.returncode == 0 else "WARN",
                                    f"Analyzer rc={proc2.returncode}: {last2[:60]}"))
            except Exception as e:
                pql_results.append(("WARN", f"Analyzer error: {e}"))

            # Step 3: L13 gate (findings closure check)
            print("  [3/3] Checking L13 staleness gate...")
            rc3, last3 = _py_run(_os.path.join(_root, "validate_playwright_staleness.py"))
            pql_results.append(("PASS" if rc3 == 0 else "FAIL", f"L13: {last3[:80]}"))

            pql_out = {"results": pql_results}
            section_results.append(("Platform Quality Loop", pql_out))
            for r in pql_results:
                if r[0] == "PASS": total_pass += 1
                elif r[0] == "FAIL": total_fail += 1
                elif r[0] == "WARN": total_warn += 1

        # 4d. Journey specs — behavioral end-to-end tests that exercise
        # actual user paths through the live browser + ai-gateway. Added
        # 2026-05-19 after the Rosa-offline regression: static validators
        # kept being added (ANON_OK_AGENTS, legacy-worker-decommission, ...)
        # but the bug only surfaces when a real fetch reaches the gateway.
        # The journey-voice-journal.spec.ts file owns the Sentinel Review
        # for that bug class (rosa-default-persona, ai-gateway anon-allow,
        # rosa-strategist-lens, james-technical-lens).
        try:
            import subprocess as _jsp, os as _jos, sys as _jsys, re as _jre
            _jroot = _jos.path.dirname(_jos.path.dirname(_jos.path.abspath(__file__)))
            _jcwd  = "Z:\\" if _jos.path.exists("Z:/playwright.config.ts") else _jroot
            _jansi = _jre.compile(r"\x1b\[[0-9;]*m")
            print("\n[Journey specs — Rosa/James end-to-end sentinel]")
            jproc = _jsp.Popen(
                ["npx", "playwright", "test",
                 "tests/journey-voice-journal.spec.ts",
                 "--reporter=line"],
                stdout=_jsp.PIPE, stderr=_jsp.STDOUT,
                cwd=_jcwd, bufsize=1,
                text=True, encoding="utf-8", errors="replace",
                shell=True,
            )
            jlast = ""
            for line in jproc.stdout:
                clean = _jansi.sub("", line.rstrip())
                if clean:
                    print(f"  {clean}")
                    jlast = clean
            jproc.wait()
            journey_status = "PASS" if jproc.returncode == 0 else "FAIL"
            journey_out = {"results": [(journey_status, f"journey-voice-journal rc={jproc.returncode}: {jlast[:80]}")]}
        except Exception as e:
            print(f"  ERROR: {e}")
            journey_out = {"results": [("FAIL", f"journey runner crashed: {e}")]}
        section_results.append(("Journey Specs", journey_out))
        for r in journey_out.get("results", []):
            if r[0] == "PASS": total_pass += 1
            elif r[0] == "FAIL": total_fail += 1
            elif r[0] == "WARN": total_warn += 1

        # 5. Mobile viewport — separate browser context (375x667, mobile UA)
        print("\n[Mobile viewport (375x667)]")
        try:
            out = mobile.run_in_mobile_browser(pw, log=print)
        except Exception as e:
            print(f"  ✗ flow crashed: {type(e).__name__}: {e}")
            out = {"results": [("FAIL", f"crashed: {e}")]}
        section_results.append(("Mobile", out))
        for r in out.get("results", []):
            if r[0] == "PASS": total_pass += 1
            elif r[0] == "FAIL": total_fail += 1
            elif r[0] == "WARN": total_warn += 1

        # 6. AI Full — only with --with-ai flag (uses Groq API, ~10 calls, ~$0)
        if WITH_AI:
            for label, mod in [
                ("AI Assistant", ai_assistant),
                ("AI Analytics", ai_analytics),
                ("AI Semantic Search", ai_semantic),
                ("AI Generation (BOM/SOW)", ai_generation),
                ("AI Chains (multi-agent RAG)", ai_chains),
            ]:
                print(f"\n[{label}]")
                try:
                    out = mod.run(None, [], [], log=print)
                except Exception as e:
                    print(f"  ✗ flow crashed: {type(e).__name__}: {e}")
                    out = {"results": [("FAIL", f"crashed: {e}")]}
                section_results.append((label, out))
                for r in out.get("results", []):
                    if r[0] == "PASS": total_pass += 1
                    elif r[0] == "FAIL": total_fail += 1
                    elif r[0] == "WARN": total_warn += 1

    print()
    print("=" * 60)
    print(f"  Summary  {total_pass} pass · {total_warn} warn · {total_fail} fail")
    print(f"  Screenshots: {SCREENSHOTS_DIR}")
    print("=" * 60)

    # Persist per-flow detail for the dashboard's drill-down
    try:
        from pathlib import Path as _P
        import json as _json
        from datetime import datetime as _dt, timezone as _tz
        sections_out = []
        for label, payload in section_results:
            tests = []
            for r in (payload or {}).get("results", []):
                if isinstance(r, tuple) and len(r) >= 2:
                    tests.append({"status": r[0], "message": str(r[1])})
            sections_out.append({"section": label, "tests": tests})
        out = _P(__file__).parent / ".tmp" / "last_ui_run.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps({
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "summary": {"pass": total_pass, "warn": total_warn, "fail": total_fail},
            "sections": sections_out,
        }, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  WARN: could not save UI detail JSON: {e}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
