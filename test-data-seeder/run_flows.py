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
from flows import ai_assistant, ai_analytics, ai_semantic, ai_generation

WITH_AI = "--with-ai" in sys.argv


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
                ("Logbook", logbook),
                ("Community", community),
                ("Analytics", analytics),
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

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
