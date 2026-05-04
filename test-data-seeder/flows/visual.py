"""Visual regression flow — pixel-diff every public page against a baseline.

First run on each machine: captures baselines (no comparison, all "saved").
Subsequent runs: compares current screenshot to baseline. If diff exceeds
threshold, FAIL with diff image saved for inspection.

Baselines and diffs live in test-data-seeder/.tmp/ (gitignored).
To update baselines after an intentional UI change, delete the matching file
in .tmp/visual_baselines/ and re-run.
"""
from pathlib import Path
from PIL import Image, ImageChops

from .harness import BASE_URL, sign_in

PAGES = [
    "hive.html", "logbook.html", "inventory.html", "pm-scheduler.html",
    "analytics.html", "analytics-report.html", "skillmatrix.html", "community.html",
    "marketplace.html", "dayplanner.html", "engineering-design.html",
    "report-sender.html",
    "project-manager.html",
    "project-report.html",
]

BASELINES_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "visual_baselines"
DIFFS_DIR     = Path(__file__).resolve().parent.parent / ".tmp" / "visual_diffs"
BASELINES_DIR.mkdir(parents=True, exist_ok=True)
DIFFS_DIR.mkdir(parents=True, exist_ok=True)

# A pixel counts as "different" if any channel differs by more than this
PIXEL_CHANNEL_TOLERANCE = 12
# A page FAILs if more than this percentage of pixels differ
PAGE_DIFF_THRESHOLD_PCT = 1.5


def _diff_score(baseline_path: Path, current_path: Path) -> tuple[float, Path | None]:
    """Returns (% pixels different, saved diff image path or None)."""
    baseline = Image.open(baseline_path).convert("RGB")
    current = Image.open(current_path).convert("RGB")

    if baseline.size != current.size:
        return 100.0, None

    diff = ImageChops.difference(baseline, current)
    different = sum(
        1 for p in diff.getdata()
        if any(c > PIXEL_CHANNEL_TOLERANCE for c in p)
    )
    total = baseline.width * baseline.height
    pct = (different / total) * 100 if total else 0.0

    diff_path = None
    if pct > 0.05:
        diff_path = DIFFS_DIR / current_path.name
        # Amplify diff for human inspection
        amplified = diff.point(lambda v: min(255, v * 8))
        amplified.save(diff_path)

    return pct, diff_path


def run_in_visual_browser(playwright, log) -> dict:
    results = []
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
    page = context.new_page()

    try:
        sign_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"visual sign-in failed: {e}")]}

    log("Visual regression — comparing each page to baseline...")

    for filename in PAGES:
        try:
            page.goto(f"{BASE_URL}/workhive/{filename}", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1500)
        except Exception as e:
            results.append(("FAIL", f"{filename}: navigation error: {e}"))
            continue

        current_path = DIFFS_DIR / f"{filename.replace('.html', '')}_current.png"
        baseline_path = BASELINES_DIR / f"{filename.replace('.html', '')}.png"

        page.screenshot(path=str(current_path), full_page=True)

        if not baseline_path.exists():
            # First run: capture baseline (current becomes baseline)
            current_path.replace(baseline_path)
            results.append(("PASS", f"{filename}: baseline captured (first run)"))
            log(f"  ✓ {filename}: baseline saved")
            continue

        pct, diff_path = _diff_score(baseline_path, current_path)
        if pct <= PAGE_DIFF_THRESHOLD_PCT:
            results.append(("PASS", f"{filename}: {pct:.2f}% pixels differ (within {PAGE_DIFF_THRESHOLD_PCT}% threshold)"))
            log(f"  ✓ {filename}: {pct:.2f}% diff (OK)")
            # Clean up diff image since pass
            if diff_path and diff_path.exists():
                diff_path.unlink()
        else:
            results.append((
                "FAIL",
                f"{filename}: {pct:.2f}% pixels differ (over {PAGE_DIFF_THRESHOLD_PCT}% threshold). "
                f"Diff saved to {diff_path}. To accept the change, delete {baseline_path} and re-run.",
            ))
            log(f"  ✗ {filename}: {pct:.2f}% diff — see {diff_path}")

    context.close()
    browser.close()
    return {"results": results}
