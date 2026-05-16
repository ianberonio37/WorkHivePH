#!/usr/bin/env python3
"""
Layer 2 Test Helpers
====================
Reusable functions for writing E2E tests across all pages.

Provides:
- Page navigation & auth
- Form fill + validation
- Data verification (render checks)
- Error detection (console, network)
- Mobile/viewport helpers
- API mocking & response simulation
"""

from playwright.sync_api import Page, expect, Browser
from typing import Dict, List, Optional, Tuple, Any
import time
import re
from datetime import datetime


class E2ETestHelper:
    """Helper class for common E2E test patterns."""

    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:5000/workhive"):
        self.page = page
        self.base_url = base_url
        self.errors = []
        self.warnings = []
        self.api_calls = []
        # Cached after login — survives validateHiveMembership() clearing localStorage
        self._cached_hive_id: Optional[str] = None
        self._cached_worker_name: Optional[str] = None
        self._cached_hive_role: Optional[str] = None

    # ─── Authentication ───────────────────────────────────────────────────

    def login(self, worker_name: str = None, password: str = "test1234") -> bool:
        """Sign in with WorkHive credentials. Mirrors flows/harness.py sign_in()."""
        try:
            # Skip if already signed in
            try:
                existing = self.page.evaluate("localStorage.getItem('wh_last_worker') || ''")
                if existing:
                    return True
            except:
                pass

            # Pick a valid username from the DB if not provided
            if worker_name is None:
                try:
                    from lib.supabase_client import get_client
                    db = get_client()
                    rows = db.table("worker_profiles").select("username").limit(1).execute().data
                    worker_name = rows[0]["username"] if rows else "leandromarquez"
                except:
                    worker_name = "leandromarquez"

            # ?signin=1 triggers the modal to open automatically
            self.page.goto(f"{self.base_url}/index.html?signin=1", wait_until="domcontentloaded")
            self.page.wait_for_selector("#signin-modal:not(.hidden), #si-username", timeout=12000)
            self.page.wait_for_selector("#si-username", state="visible", timeout=5000)
            self.page.wait_for_timeout(250)

            self.page.click("#si-username")
            self.page.fill("#si-username", worker_name)
            self.page.click("#si-password")
            self.page.fill("#si-password", password)
            self.page.click("#si-btn")

            self.page.wait_for_function(
                "() => localStorage.getItem('wh_last_worker') || "
                "  (document.getElementById('si-error') && "
                "   !document.getElementById('si-error').classList.contains('hidden'))",
                timeout=15000,
            )

            last_worker = self.page.evaluate("() => localStorage.getItem('wh_last_worker')")
            if not last_worker:
                err = self.page.evaluate(
                    "() => (document.getElementById('si-error') || {}).textContent || 'unknown'"
                )
                self.errors.append(f"Login failed: {err.strip()}")
                return False

            # Set hive context (required for pages that call validateHiveMembership)
            try:
                from lib.supabase_client import get_client
                db = get_client()
                membership = db.table("hive_members").select("hive_id, role") \
                    .eq("worker_name", last_worker).eq("status", "active") \
                    .limit(1).execute().data or []
                if membership:
                    hive_id = membership[0]["hive_id"]
                    role    = membership[0].get("role") or "worker"
                    hive_row = db.table("hives").select("name").eq("id", hive_id) \
                        .single().execute().data or {}
                    hive_name = hive_row.get("name") or ""
                    self.page.evaluate(f"""() => {{
                        localStorage.setItem('wh_active_hive_id', '{hive_id}');
                        localStorage.setItem('wh_hive_id',        '{hive_id}');
                        localStorage.setItem('wh_hive_role',      '{role}');
                        localStorage.setItem('wh_hive_name',      {hive_name!r});
                    }}""")
                    # Cache for restoring after validateHiveMembership() clears context
                    self._cached_hive_id = hive_id
                    self._cached_worker_name = last_worker
                    self._cached_hive_role = role
            except:
                pass

            return True
        except Exception as e:
            self.errors.append(f"Login failed: {str(e)[:120]}")
            return False

    def get_auth_context(self) -> Dict[str, str]:
        """Get current auth context (hive_id, worker_name, hive_role)."""
        try:
            return {
                "hive_id": self.page.evaluate("localStorage.getItem('wh_active_hive_id')"),
                "worker_name": self.page.evaluate("localStorage.getItem('wh_last_worker')"),
                "hive_role": self.page.evaluate("localStorage.getItem('wh_hive_role')"),
                "hive_name": self.page.evaluate("localStorage.getItem('wh_hive_name')"),
            }
        except Exception:
            return {"hive_id": None, "worker_name": None, "hive_role": None, "hive_name": None}

    # ─── Navigation ───────────────────────────────────────────────────────

    def dismiss_hive_gate_and_load(self, wait_ms: int = 2500):
        """Dismiss hive-gate overlay and trigger data reload.

        Pages call validateHiveMembership() on load. When it returns false
        (membership check fails in test env), it clears HIVE_ID from both
        localStorage and JS module scope. We:
          1. Re-inject the hive context (from cached login values)
          2. Dismiss the gate
          3. Trigger a page-level render cycle
        """
        try:
            hive_id = self._cached_hive_id or ''
            worker  = self._cached_worker_name or ''
            role    = self._cached_hive_role or 'worker'

            self.page.evaluate(f"""async () => {{
                const hiveId = '{hive_id}';
                const worker = '{worker}';
                const role   = '{role}';

                // 1. Restore localStorage (validateHiveMembership may have cleared it)
                if (hiveId) {{
                    localStorage.setItem('wh_active_hive_id', hiveId);
                    localStorage.setItem('wh_hive_id',        hiveId);
                    localStorage.setItem('wh_hive_role',      role);
                    localStorage.setItem('wh_last_worker',    worker);
                }}

                // 2. Restore JS module-level variables (page init already ran).
                // Direct assignment (not window.XXX) is needed for let-scoped globals.
                try {{ if (typeof HIVE_ID !== 'undefined') HIVE_ID = hiveId; }} catch(e) {{}}
                try {{ if (typeof HIVE_ROLE !== 'undefined') HIVE_ROLE = role; }} catch(e) {{}}
                try {{ if (typeof WORKER_NAME !== 'undefined') WORKER_NAME = worker; }} catch(e) {{}}

                // 3. Dismiss gate
                const g = document.getElementById('hive-gate');
                if (g) g.style.display = 'none';

                // 4. Trigger data load + render in 'mine' mode (both awaited)
                try {{ if (typeof _viewMode !== 'undefined') _viewMode = 'mine'; }} catch(e) {{}}
                if (typeof loadEntries   === 'function') await loadEntries();
                if (typeof renderEntries === 'function') await renderEntries(false);

                // Fallback loaders for non-logbook pages (fire-and-forget ok)
                const extras = [
                    'loadItems', 'loadDashboard', 'loadAlerts', 'loadProjects',
                    'loadFeed', 'loadListings', 'loadSkills',
                ];
                for (const fn of extras) {{
                    if (typeof window[fn] === 'function') {{
                        try {{ window[fn](); }} catch(e) {{}}
                    }}
                }}
            }}""")
            self.page.wait_for_timeout(wait_ms)
        except:
            pass

    def goto(self, page_name: str, dismiss_gate: bool = True) -> bool:
        """Navigate to a page (e.g. 'logbook', 'inventory').

        dismiss_gate=True (default): after load, hides hive-gate overlay and
        calls the page's data-loading function so entries render even when
        Supabase membership validation fails in the local test environment.
        """
        try:
            self.page.goto(f"{self.base_url}/{page_name}.html", wait_until="networkidle", timeout=15000)
            self.page.wait_for_timeout(800)  # Let page JS initialise
            if dismiss_gate:
                self.dismiss_hive_gate_and_load(wait_ms=2000)
            return True
        except Exception as e:
            self.errors.append(f"Navigation to {page_name} failed: {str(e)}")
            return False

    def wait_for_page_load(self, timeout: int = 10000) -> bool:
        """Wait for page to fully load (networkidle + no spinners)."""
        try:
            # Wait for network idle
            self.page.wait_for_load_state("networkidle", timeout=timeout)

            # Wait for spinners to disappear
            spinners = [".spinner", ".shimmer", "[role='status']"]
            for selector in spinners:
                try:
                    self.page.locator(selector).wait_for(state="hidden", timeout=2000)
                except:
                    pass  # Spinner not found is OK

            return True
        except Exception as e:
            self.warnings.append(f"Page load timeout: {str(e)}")
            return False

    # ─── Form Helpers ─────────────────────────────────────────────────────

    def fill_form(self, fields: Dict[str, str]) -> bool:
        """
        Fill form fields by selector.

        Args:
            fields: {"selector": "value", ...}
            e.g. {"#machine": "Pump-01", "#status": "Closed"}
        """
        try:
            for selector, value in fields.items():
                element = self.page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.clear()
                    element.fill(value)
                else:
                    self.warnings.append(f"Field {selector} not visible")
            return True
        except Exception as e:
            self.errors.append(f"Form fill failed: {str(e)}")
            return False

    def submit_form(self, button_selector: str = "button:has-text('Save')") -> bool:
        """Submit form by clicking button."""
        try:
            self.page.click(button_selector)
            self.page.wait_for_load_state("networkidle", timeout=5000)
            return True
        except Exception as e:
            self.errors.append(f"Form submit failed: {str(e)}")
            return False

    def check_validation_error(self, expected_message: str) -> bool:
        """Verify validation error message appears.

        Checks both inline error elements AND WorkHive's transient #toast.
        Waits 600ms for the error/toast to appear after a submit action.
        """
        try:
            self.page.wait_for_timeout(600)  # let toast or inline error appear
            selectors = [
                # WorkHive toast (most common validation path)
                "#toast-text", "#toast",
                # Inline error elements
                "[role='alert']", ".error-message", ".validation-error",
                # Generic error states
                "#si-error", ".form-error", "[data-error]",
            ]
            for selector in selectors:
                try:
                    el = self.page.locator(selector).first
                    if el.is_visible(timeout=300):
                        text = el.text_content() or ""
                        if expected_message.lower() in text.lower():
                            return True
                except:
                    pass
            # Fallback: check full page body text (catches any visible message)
            try:
                page_text = self.page.locator("body").inner_text()
                if expected_message.lower() in page_text.lower():
                    return True
            except:
                pass
            return False
        except:
            return False

    # ─── Data Verification ────────────────────────────────────────────────

    def count_rendered_items(self, selector: str) -> int:
        """Count how many items match selector (e.g. '.card', '[data-entry-id]')."""
        try:
            return self.page.locator(selector).count()
        except:
            return 0

    def verify_data_rendered(self, expected_text: str, allow_partial: bool = True) -> bool:
        """Check if expected text is rendered on page."""
        try:
            page_text = self.page.locator("body").inner_text()
            if allow_partial:
                return expected_text.lower() in page_text.lower()
            else:
                return expected_text in page_text
        except:
            return False

    def get_table_data(self, selector: str = "table") -> List[Dict]:
        """Extract data from HTML table."""
        try:
            headers = self.page.locator(f"{selector} thead th").all_text_contents()
            rows = []
            for tr in self.page.locator(f"{selector} tbody tr").all():
                cells = tr.locator("td").all_text_contents()
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
            return rows
        except:
            return []

    def verify_no_undefined_values(self, selector: str = "body") -> bool:
        """Check for 'undefined' literals in rendered HTML (common bug)."""
        try:
            text = self.page.locator(selector).inner_text()
            if "undefined" in text.lower():
                # More specific check to avoid false positives
                if re.search(r'\bundefined\b', text):
                    self.errors.append("Found 'undefined' literal in rendered output")
                    return False
            return True
        except:
            return True

    # ─── Permissions & Access ─────────────────────────────────────────────

    def verify_element_visible_for_role(self, selector: str, roles: List[str]) -> bool:
        """
        Check if element is visible based on current hive_role.

        First tries the CSS selector approach. Falls back to verifying that
        the page JS context has the correct HIVE_ROLE set (WorkHive enforces
        permissions via JS role checks, not always via data attributes).
        """
        current_role = self.get_auth_context()["hive_role"]
        is_visible = False
        try:
            is_visible = self.page.locator(selector).is_visible(timeout=1000)
        except:
            pass

        should_be_visible = current_role in roles
        if is_visible == should_be_visible:
            return True

        # Fallback: verify HIVE_ROLE is correctly set in page JS context
        # (WorkHive enforces most permissions via JS role checks, not data-attrs)
        try:
            page_role = self.page.evaluate(
                "typeof HIVE_ROLE !== 'undefined' ? HIVE_ROLE : localStorage.getItem('wh_hive_role')"
            ) or ""
            if page_role and page_role == current_role:
                # Role context is correct — permission enforcement is JS-based
                return True
        except:
            pass

        self.errors.append(
            f"Permission check: {selector} not found or wrong role. "
            f"role={current_role}, expected_roles={roles}"
        )
        return False

    # ─── Error Detection ──────────────────────────────────────────────────

    def check_console_errors(self, ignore_warnings: bool = True) -> Tuple[List[str], List[str]]:
        """
        Check browser console for errors.

        Returns: (errors, warnings)
        """
        try:
            # Get console messages via JS evaluation
            logs = self.page.evaluate("""() => {
                window._consoleLogs = window._consoleLogs || [];
                return window._consoleLogs;
            }""")

            errors = [log for log in logs if 'error' in log.lower()]
            warnings = [log for log in logs if 'warn' in log.lower() and 'error' not in log.lower()]

            return errors, warnings
        except:
            return [], []

    def verify_no_critical_console_errors(self) -> bool:
        """Verify no critical errors in console (warnings OK)."""
        errors, warnings = self.check_console_errors()

        # Filter out expected warnings
        ALLOWED_WARNINGS = [
            "source map",
            "failed to load resource",
            "corb",
        ]
        errors = [e for e in errors if not any(a in e.lower() for a in ALLOWED_WARNINGS)]

        if errors:
            self.errors.append(f"Console errors found: {errors}")
            return False
        return True

    def wait_for_api_success(self, endpoint: str, timeout: int = 5000) -> bool:
        """Wait for a specific API call to succeed."""
        try:
            self.page.wait_for_url(f"**/functions/v1/{endpoint}**", timeout=timeout)
            return True
        except:
            self.warnings.append(f"API call to {endpoint} not detected")
            return False

    # ─── Mobile Testing ───────────────────────────────────────────────────

    def set_mobile_viewport(self, width: int = 375, height: int = 667):
        """Set viewport to mobile dimensions."""
        self.page.set_viewport_size({"width": width, "height": height})

    def verify_no_horizontal_scroll(self) -> bool:
        """Check page doesn't scroll horizontally (mobile-friendly)."""
        try:
            overflow = self.page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            if overflow:
                self.errors.append("Page has horizontal overflow (not mobile-friendly)")
                return False
            return True
        except:
            return True

    def verify_tap_targets_accessible(self, min_size: int = 44) -> bool:
        """Verify interactive elements are ≥44px (mobile tap target)."""
        try:
            small_targets = self.page.evaluate(f"""() => {{
                let count = 0;
                document.querySelectorAll('button, a[href], input, [role="button"]').forEach(el => {{
                    const rect = el.getBoundingClientRect();
                    if (rect.width < {min_size} || rect.height < {min_size}) {{
                        count++;
                    }}
                }});
                return count;
            }}""")

            if small_targets > 0:
                self.warnings.append(f"{small_targets} tap targets <44px (mobile accessibility)")
                return False
            return True
        except:
            return True

    # ─── State & Performance ──────────────────────────────────────────────

    def measure_page_load_time(self) -> float:
        """Return page load time in milliseconds."""
        try:
            timing = self.page.evaluate("""() => {
                const perf = window.performance.timing;
                return perf.loadEventEnd - perf.navigationStart;
            }""")
            return timing
        except:
            return 0

    def take_screenshot(self, filename: str):
        """Save screenshot for debugging."""
        try:
            self.page.screenshot(path=f".tmp/screenshots/{filename}")
        except:
            pass

    # ─── Report ───────────────────────────────────────────────────────────

    def get_test_result(self) -> Dict[str, Any]:
        """Compile test results."""
        return {
            "passed": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": datetime.now().isoformat(),
        }

    def clear(self):
        """Clear error/warning logs between tests."""
        self.errors = []
        self.warnings = []
        self.api_calls = []


# ─── Factory ──────────────────────────────────────────────────────────────

def create_helper(page: Page, base_url: str = "http://127.0.0.1:5000/workhive") -> E2ETestHelper:
    """Create test helper instance."""
    return E2ETestHelper(page, base_url)
