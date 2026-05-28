"""
Pre-Deploy Gate (P1 roadmap 2026-05-26)
=======================================
Single command that must pass before any production deploy. Wraps:

  1. Layer 0 Fast Guardian      (run_platform_checks.py --fast --workers 6)
  2. Sentinel coverage freeze   (run_sentinel_review.py --check-coverage)
  3. Layer 2 Tier 1 smoke       (Playwright critical-path specs)
  4. Migration ordering check   (validate_migration_order.py)
  5. Free-tier-only chain check (validate_ai_chain_mirror.py)
  6. Git working-tree clean     (no uncommitted changes)

Each stage prints a one-line PASS/FAIL summary. Exit code 0 only when
ALL stages pass. The script is intentionally additive — local-first
workflow still runs each step independently; this just enforces the
union for the "ready to push to prod" decision.

Usage:
  python tools/pre_deploy_gate.py            # full gate
  python tools/pre_deploy_gate.py --skip-l2  # skip Playwright (fast iteration)
"""
from __future__ import annotations
import io, os, subprocess, sys, time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

SKIP_L2 = "--skip-l2" in sys.argv
SKIP_GIT = "--skip-git" in sys.argv


def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def yellow(s):return f"\033[93m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"
def cyan(s):  return f"\033[96m{s}\033[0m"


def step(label: str, cmd: list[str], cwd: Path = ROOT, env_extra: dict | None = None) -> tuple[bool, float]:
    print(f"\n  {cyan('→')}  {bold(label)}")
    print(f"     $ {' '.join(cmd)}")
    t0 = time.time()
    env = os.environ.copy()
    if env_extra: env.update(env_extra)
    try:
        r = subprocess.run(cmd, cwd=str(cwd), env=env, timeout=900)
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    elapsed = time.time() - t0
    print(f"     {green('PASS') if ok else red('FAIL')}  ({elapsed:.1f}s)")
    return ok, elapsed


def git_clean() -> bool:
    if SKIP_GIT: return True
    try:
        r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True, text=True)
        dirty = [l for l in r.stdout.strip().splitlines() if not l.startswith("??")]
        return not dirty
    except Exception:
        return False


def main() -> int:
    print(bold("\n  PRE-DEPLOY GATE"))
    print("  " + "=" * 70)

    results: list[tuple[str, bool, float]] = []

    ok, t = step("Layer 0 Fast Guardian (parallel)",
                 [PY, "run_platform_checks.py", "--fast", "--workers", "6"])
    results.append(("L0 Fast Guardian", ok, t))

    ok, t = step("Migration ordering",
                 [PY, "validate_migration_order.py"])
    results.append(("Migration ordering", ok, t))

    ok, t = step("AI chain mirror (Python ↔ TS)",
                 [PY, "validate_ai_chain_mirror.py"])
    results.append(("AI chain mirror", ok, t))

    if (ROOT / "run_sentinel_review.py").exists():
        ok, t = step("Sentinel coverage freeze",
                     [PY, "run_sentinel_review.py", "--check-coverage"])
        results.append(("Sentinel coverage", ok, t))

    if not SKIP_L2:
        ok, t = step("Layer 2 Tier 1 smoke",
                     ["npx", "playwright", "test",
                      "tests/journey-logbook.spec.ts",
                      "tests/journey-inventory.spec.ts",
                      "tests/journey-pm.spec.ts",
                      "tests/journey-hive.spec.ts",
                      "--reporter=line", "--max-failures=5"])
        results.append(("L2 Tier 1 smoke", ok, t))

    git_ok = git_clean()
    print(f"\n  {cyan('→')}  {bold('Git working tree')}: {green('clean') if git_ok else red('dirty (commit before deploy)')}")
    results.append(("Git clean", git_ok, 0.0))

    print("\n  " + "=" * 70)
    print(bold("  SUMMARY"))
    all_ok = True
    total = 0.0
    for label, ok, t in results:
        icon = green('PASS') if ok else red('FAIL')
        print(f"  {icon}  {label:<32s}  {t:6.1f}s")
        all_ok = all_ok and ok
        total += t
    print(f"\n  Total: {total:.1f}s")
    print(f"  {bold('READY TO DEPLOY' if all_ok else 'BLOCKED — fix the FAIL items above first')}\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
