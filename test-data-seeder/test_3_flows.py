"""Quick spot-check for 3 fixed flows: community edit, marketplace contact, auto-staging."""
import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from flows.harness import browser_session, sign_in
from flows import community, marketplace_flow, auto_staging_flow


def main():
    print("WorkHive 3-Flow Visual Spot-Check")
    print("=" * 60)
    print()

    results = {}

    with sync_playwright() as pw:
        with browser_session(pw, headless=True) as (page, errors, warnings):
            try:
                sign_in(page, log=print)
            except Exception as e:
                print(f"FATAL: sign-in failed: {type(e).__name__}: {e}")
                print("Make sure local Supabase and Flask server are running.")
                return 1

            # Test 1: Community (supervisor edit fix)
            print("\n[1/3] Community — Supervisor Edit Fix")
            print("-" * 60)
            try:
                out = community.run(page, errors, warnings, log=print)
                results["Community"] = out
                passed = sum(1 for r in out.get("results", []) if r[0] == "PASS")
                failed = sum(1 for r in out.get("results", []) if r[0] == "FAIL")
                print(f"✓ Result: {passed} PASS, {failed} FAIL")
            except Exception as e:
                print(f"✗ Community flow crashed: {type(e).__name__}: {e}")
                results["Community"] = {"results": [("FAIL", f"crashed: {e}")]}

            # Test 2: Marketplace (contact button flow)
            print("\n[2/3] Marketplace — Contact Button Flow")
            print("-" * 60)
            try:
                out = marketplace_flow.run(page, errors, warnings, log=print)
                results["Marketplace"] = out
                passed = sum(1 for r in out.get("results", []) if r[0] == "PASS")
                failed = sum(1 for r in out.get("results", []) if r[0] == "FAIL")
                print(f"✓ Result: {passed} PASS, {failed} FAIL")
            except Exception as e:
                print(f"✗ Marketplace flow crashed: {type(e).__name__}: {e}")
                results["Marketplace"] = {"results": [("FAIL", f"crashed: {e}")]}

            # Test 3: Auto-Staging (byte budget fix)
            print("\n[3/3] Auto-Staging — Byte Budget (80KB→300KB)")
            print("-" * 60)
            try:
                out = auto_staging_flow.run(page, errors, warnings, log=print)
                results["Auto-Staging"] = out
                passed = sum(1 for r in out.get("results", []) if r[0] == "PASS")
                failed = sum(1 for r in out.get("results", []) if r[0] == "FAIL")
                print(f"✓ Result: {passed} PASS, {failed} FAIL")
            except Exception as e:
                print(f"✗ Auto-Staging flow crashed: {type(e).__name__}: {e}")
                results["Auto-Staging"] = {"results": [("FAIL", f"crashed: {e}")]}

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_pass = sum(sum(1 for r in out.get("results", []) if r[0] == "PASS") for out in results.values())
    total_fail = sum(sum(1 for r in out.get("results", []) if r[0] == "FAIL") for out in results.values())
    total_warn = sum(sum(1 for r in out.get("results", []) if r[0] == "WARN") for out in results.values())

    print(f"Total: {total_pass} PASS, {total_fail} FAIL, {total_warn} WARN")

    if total_fail > 0:
        print("\n❌ FAILURES DETECTED:")
        for flow, out in results.items():
            for r in out.get("results", []):
                if r[0] == "FAIL":
                    print(f"  {flow}: {r[1]}")
        return 1
    else:
        print("\n✓ All 3 flows passed visual spot-check!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
