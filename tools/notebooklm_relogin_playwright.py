"""Embedded NotebookLM re-authentication via Playwright (no interactive CLI).

The lib's `notebooklm login` CLI uses interactive prompts (`input()`-style)
that hang when stdin is piped from Flask — confirmed in the field. This
script bypasses that entirely:

  1. Open the SAME persistent Chromium profile the lib uses
  2. Navigate to NotebookLM
  3. Poll the page until we detect the user is signed in
     (URL leaves /signin AND a notebook-list / new-notebook element appears)
  4. Save Playwright's storage state to the lib's expected JSON path
  5. Exit cleanly so Flask's status endpoint can see completion

Exit codes:
    0  Session saved
    1  Library not installed
    2  User closed browser before signing in
    3  Timed out waiting for sign-in (default 10 min)
    4  Internal Playwright / I/O error

Why a persistent context: the lib stores its browser data under
`<profile>/browser_profile` so subsequent runs remember cookies. We use
the same dir so the user's existing Google session (other than NotebookLM)
is preserved.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _paths() -> tuple[Path, Path]:
    base = Path.home() / ".notebooklm" / "profiles" / "default"
    base.mkdir(parents=True, exist_ok=True)
    profile_dir  = base / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    storage_file = base / "storage_state.json"
    return profile_dir, storage_file


async def _wait_for_signin(page, context, max_seconds: int = 600) -> bool:
    """Poll until the user is signed in to NotebookLM.

    A sign-in is confirmed when ALL of these are true:
      1. Page URL is on notebooklm.google.com (NOT a signin/accountchooser/login redirect)
      2. We see a post-login DOM element OR the auth cookies are set
      3. The page has been on that URL for >2s (avoid catching mid-redirect)

    Loose detection caused false positives on Google's redirect chain
    (notebooklm.google.com/login?continue=… briefly shows as "on NL" even
    though it's still a transitional URL).
    """
    deadline = asyncio.get_event_loop().time() + max_seconds
    SIGNED_OUT_PATTERNS = (
        "/signin/", "/v3/signin", "accountchooser",
        "/ServiceLogin", "myaccount.google", "/login?",
        "/oauth", "challenge",
    )
    POST_LOGIN_SELECTORS = [
        "button:has-text('New notebook')",
        "button:has-text('Create new')",
        "[role='button']:has-text('New')",
        "button:has-text('Try NotebookLM')",
        "[data-test-id*='notebook']",
        "[data-test-id*='create']",
        "[aria-label*='notebook' i]",
    ]
    last_url = ""
    stable_since = None
    while asyncio.get_event_loop().time() < deadline:
        try:
            url = page.url
        except Exception:
            return False                                  # page/browser closed
        if url != last_url:
            print(f"  [browser] {url}", flush=True)
            last_url = url
            stable_since = asyncio.get_event_loop().time()
        # Not on NotebookLM at all — keep waiting.
        if "notebooklm.google.com" not in url:
            await asyncio.sleep(2)
            continue
        # On NotebookLM domain but still on a transitional URL — keep waiting.
        if any(p in url for p in SIGNED_OUT_PATTERNS):
            await asyncio.sleep(2)
            continue
        # URL looks settled. Wait at least 2s on the same URL before
        # checking DOM/cookies so we don't catch a mid-redirect state.
        if stable_since is None or (asyncio.get_event_loop().time() - stable_since) < 2:
            await asyncio.sleep(1)
            continue
        # Check for sign-in evidence (any one of these passes):
        # (a) Auth cookies set for notebooklm/google
        try:
            cookies = await context.cookies("https://notebooklm.google.com/")
            cookie_names = {c.get("name", "") for c in cookies}
            if any(n in cookie_names for n in ("SAPISID", "__Secure-1PSID", "SID", "HSID")):
                print(f"  [signin] auth cookies present ({len(cookie_names)} cookies)", flush=True)
                return True
        except Exception as exc:
            print(f"  [signin] cookie check raised: {exc}", flush=True)
        # (b) Post-login DOM element visible
        for sel in POST_LOGIN_SELECTORS:
            try:
                el = await page.wait_for_selector(sel, timeout=800, state="attached")
                if el:
                    print(f"  [signin] DOM marker found: {sel}", flush=True)
                    return True
            except Exception:
                continue
        await asyncio.sleep(2)
    return False


def _clean_stale_profile_locks(profile_dir: Path) -> None:
    """Remove Chromium profile lock files left by aborted earlier runs.

    When the previous `notebooklm login` subprocess gets killed mid-session
    (we hit this exact scenario when forcibly terminating a hung lib CLI),
    Chromium leaves its profile dir locked. Subsequent Playwright launches
    hit exit code 21 with no useful error. The lock manifests as a few
    well-known files inside the user_data_dir.
    """
    lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket", "Default/lockfile"]
    for rel in lock_files:
        p = profile_dir / rel
        if p.exists():
            try:
                p.unlink()
                print(f"  [cleanup] removed stale lock: {p.name}", flush=True)
            except Exception as exc:
                print(f"  [cleanup] could not remove {p.name}: {exc}", flush=True)


async def _launch_browser(p, profile_dir: Path):
    """Use a fresh non-persistent Chromium context every time.

    We tried persistent contexts (sharing `browser_profile/` with the lib's
    own login flow) but ran into unrecoverable lock files from killed
    earlier processes — the lock survives Python process death because
    Windows file handles aren't released until the actual Chromium
    process exits, which can take a while or never if it was force-killed.

    Non-persistent context starts fresh every time. The user signs in
    from scratch (full credentials, no "Continue as X" shortcut), but the
    cookies still land in storage_state.json which is the ONLY file the
    lib actually reads.

    Window args force the Chromium window to be MAXIMIZED, top-most, and
    focused so the user can't miss it. We also set a custom window title
    so it's identifiable in alt-tab.
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",                     # full screen, can't miss it
        "--window-name=WorkHive NotebookLM Login",
    ]
    browser = await p.chromium.launch(
        headless=False,
        args=args,
        # no_viewport=True lets the maximized window actually use full screen
        # instead of being clamped to Playwright's default 1280x720 viewport.
    )
    context = await browser.new_context(no_viewport=True)
    print("  [browser] fresh non-persistent context up", flush=True)
    return context, browser


async def _run() -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        print(f"  [error] Playwright not installed: {exc}", file=sys.stderr)
        return 1

    profile_dir, storage_file = _paths()
    print(f"  [paths] profile={profile_dir}", flush=True)
    print(f"  [paths] storage={storage_file}", flush=True)

    # Always sweep stale locks before any launch attempt.
    _clean_stale_profile_locks(profile_dir)

    print("  [browser] launching Chromium…", flush=True)

    try:
        async with async_playwright() as p:
            context, browser = await _launch_browser(p, profile_dir)
            try:
                pages = context.pages
                page = pages[0] if pages else await context.new_page()
                print("  [browser] navigating to NotebookLM…", flush=True)
                await page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded")
                print("  [waiting] sign in to your Google account in the browser…", flush=True)
                signed_in = await _wait_for_signin(page, context, max_seconds=600)
                if not signed_in:
                    print("  [timeout] no sign-in detected within 10 minutes", file=sys.stderr)
                    return 3
                print("  [detected] signed-in state — saving storage…", flush=True)
                await context.storage_state(path=str(storage_file))
                print(f"  [saved] {storage_file}", flush=True)
                return 0
            finally:
                try:
                    await context.close()
                except Exception:
                    pass
                if browser is not None:
                    try:
                        await browser.close()
                    except Exception:
                        pass
    except Exception as exc:
        print(f"  [error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4


def main() -> int:
    _stdout_utf8()
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
