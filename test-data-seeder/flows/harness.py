"""Shared Playwright harness — page setup, sign-in, console error capture."""
from contextlib import contextmanager
from pathlib import Path

BASE_URL = "http://127.0.0.1:5000"
DEFAULT_PASSWORD = "test1234"

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def pick_test_username():
    """Return any valid username from worker_profiles. Imports lazily to avoid
    pulling supabase-py into Playwright workers that don't need it."""
    from lib.supabase_client import get_client
    db = get_client()
    rows = db.table("worker_profiles").select("username").limit(1).execute().data
    if not rows:
        raise RuntimeError("No worker_profiles rows — run the seeder first.")
    return rows[0]["username"]


@contextmanager
def browser_session(playwright, headless=True):
    """Spin up a Chromium browser context with console error capture."""
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    errors: list = []
    warnings: list = []

    def on_console(msg):
        text = msg.text
        if msg.type == "error":
            errors.append(text)
        elif msg.type == "warning":
            warnings.append(text)

    def on_page_error(err):
        errors.append(f"PAGE ERROR: {err}")

    def on_request_failed(req):
        # Captures URL of failed network requests so we can identify 404s
        errors.append(f"REQUEST FAILED ({req.failure}): {req.url}")

    def on_response(resp):
        if resp.status >= 400:
            errors.append(f"HTTP {resp.status}: {resp.url}")

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)

    try:
        yield page, errors, warnings
    finally:
        context.close()
        browser.close()


def sign_in(page, username=None, password=DEFAULT_PASSWORD, log=print):
    if username is None:
        username = pick_test_username()
    """Drive the platform's sign-in modal. Lands on the landing page, signed in."""
    log(f"  signing in as {username}...")
    page.goto(f"{BASE_URL}/workhive/index.html?signin=1", wait_until="domcontentloaded")

    # Modal opens via the ?signin=1 query param. Wait for the Sign In panel inputs.
    page.wait_for_selector("#si-username", timeout=10000, state="visible")

    page.fill("#si-username", username)
    page.fill("#si-password", password)
    page.click("#si-btn")

    # Wait for either success (localStorage set) or visible error message
    try:
        page.wait_for_function(
            "() => localStorage.getItem('wh_last_worker') || "
            "  (document.getElementById('si-error') && "
            "   !document.getElementById('si-error').classList.contains('hidden'))",
            timeout=15000,
        )
    except Exception as e:
        raise RuntimeError(f"sign-in took >15s and produced no error or success signal: {e}")

    # Did we actually succeed?
    last_worker = page.evaluate("() => localStorage.getItem('wh_last_worker')")
    if not last_worker:
        # Capture the error message
        err = page.evaluate(
            "() => (document.getElementById('si-error') || {}).textContent || 'unknown'"
        )
        raise RuntimeError(f"sign-in failed: {err.strip()}")

    log(f"  ✓ signed in as {last_worker}")


def screenshot(page, name: str):
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path
