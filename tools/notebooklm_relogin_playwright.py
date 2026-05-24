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


async def _wait_for_signin(page, max_seconds: int = 600) -> bool:
    """Poll the page until the user is clearly signed in to NotebookLM.

    Signed-in detection: URL is NOT on a signin/accountchooser page AND
    we can find at least one element that only appears post-login (new
    notebook button, notebooks list container, or the NotebookLM nav).
    """
    deadline = asyncio.get_event_loop().time() + max_seconds
    SIGNED_OUT_URLS = ("signin", "accountchooser", "myaccount.google", "ServiceLogin")
    POST_LOGIN_SELECTORS = [
        "button:has-text('New notebook')",
        "button:has-text('Create new')",
        "[role='button']:has-text('New')",
        "[data-test-id*='notebook']",
        "[data-test-id*='create']",
        "nav",
    ]
    last_url = ""
    while asyncio.get_event_loop().time() < deadline:
        try:
            url = page.url
        except Exception:
            return False                                  # page closed
        if url != last_url:
            print(f"  [browser] {url}", flush=True)
            last_url = url
        if any(t in url for t in SIGNED_OUT_URLS):
            await asyncio.sleep(2)
            continue
        if "notebooklm.google.com" not in url:
            await asyncio.sleep(2)
            continue
        # On NotebookLM and NOT on a signin page — confirm by finding a
        # post-login element. Selectors are unreliable individually so we
        # try several.
        for sel in POST_LOGIN_SELECTORS:
            try:
                el = await page.wait_for_selector(sel, timeout=1500, state="attached")
                if el:
                    return True
            except Exception:
                continue
        await asyncio.sleep(2)
    return False


async def _run() -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        print(f"  [error] Playwright not installed: {exc}", file=sys.stderr)
        return 1

    profile_dir, storage_file = _paths()
    print(f"  [paths] profile={profile_dir}", flush=True)
    print(f"  [paths] storage={storage_file}", flush=True)
    print("  [browser] launching Chromium…", flush=True)

    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                # Some Google flows refuse to render in headless / automation
                # mode. Make us look as much like a normal Chrome as possible.
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            try:
                pages = context.pages
                page = pages[0] if pages else await context.new_page()
                print("  [browser] navigating to NotebookLM…", flush=True)
                await page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded")
                print("  [waiting] sign in to your Google account in the browser…", flush=True)
                signed_in = await _wait_for_signin(page, max_seconds=600)
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
    except Exception as exc:
        print(f"  [error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4


def main() -> int:
    _stdout_utf8()
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
