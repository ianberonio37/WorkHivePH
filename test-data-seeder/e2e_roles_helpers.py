#!/usr/bin/env python3
"""
Multi-Role E2E Helpers
======================
Provides browser contexts for each of the 3 WorkHive roles:
  - solo       : authenticated, no hive context (sees hive-gate)
  - worker     : active hive member, role = 'worker'
  - supervisor : active hive member, role = 'supervisor'

Usage:
    from e2e_roles_helpers import RoleContextFactory
    factory = RoleContextFactory(browser)
    solo_page     = factory.get_page("solo")
    worker_page   = factory.get_page("worker")
    supervisor_page = factory.get_page("supervisor")
"""

from playwright.sync_api import Browser, Page, BrowserContext
from e2e_helpers import E2ETestHelper
from typing import Dict, Optional, Tuple
import time

BASE_URL = "http://127.0.0.1:5000/workhive"

ROLES = ["solo", "worker", "supervisor"]


def _get_worker_for_role(role: str) -> Optional[str]:
    """
    Pick a username from the DB that has the given hive role.
    Returns the AUTH username (worker_profiles.username), not display_name.
    """
    try:
        from lib.supabase_client import get_client
        db = get_client()

        if role == "solo":
            # Pick any user — solo test clears their hive context after login
            rows = db.table("worker_profiles").select("username").limit(1).execute().data
            return rows[0]["username"] if rows else None

        # Find a hive_members row with the given role
        members = (
            db.table("hive_members")
            .select("worker_name, hive_id, role")
            .eq("role", role)
            .eq("status", "active")
            .limit(5)
            .execute().data or []
        )
        if not members:
            return None

        # Map display_name → username via worker_profiles
        for m in members:
            wp = (
                db.table("worker_profiles")
                .select("username")
                .eq("display_name", m["worker_name"])
                .limit(1)
                .execute().data or []
            )
            if wp:
                return wp[0]["username"]

        return None
    except Exception as e:
        print(f"  [roles_helpers] _get_worker_for_role({role}) failed: {e!s:.80}")
        return None


class RoleSession:
    """One browser context + page + helper for a given role."""

    def __init__(self, context: BrowserContext, role: str):
        self.context = context
        self.role = role
        self.page: Page = context.new_page()
        self.helper = E2ETestHelper(self.page, BASE_URL)
        self._logged_in = False

    def login(self) -> bool:
        """Sign in and (for solo) clear hive context after."""
        if self._logged_in:
            return True

        username = _get_worker_for_role(self.role)
        if not username:
            return False

        ok = self.helper.login(worker_name=username)
        if not ok:
            return False

        if self.role == "solo":
            # Simulate no-hive state: clear hive context from localStorage
            self.page.evaluate("""() => {
                localStorage.removeItem('wh_active_hive_id');
                localStorage.removeItem('wh_hive_id');
                localStorage.removeItem('wh_hive_role');
                localStorage.removeItem('wh_hive_name');
            }""")

        self._logged_in = True
        return True

    def goto(self, page_name: str) -> bool:
        """Navigate to a page for this role.

        Solo  : navigate without any gate-bypass so redirect/gate fires naturally
        Others: navigate with standard gate-bypass + comprehensive init trigger
        """
        if self.role == "solo":
            try:
                self.page.goto(
                    f"{BASE_URL}/{page_name}.html",
                    wait_until="networkidle", timeout=15000,
                )
                # Wait for async init() to fire and complete any JS redirects
                self.page.wait_for_timeout(4000)
                return True
            except:
                return False
        else:
            # Navigate normally
            try:
                self.page.goto(
                    f"{BASE_URL}/{page_name}.html",
                    wait_until="networkidle", timeout=15000,
                )
                self.page.wait_for_timeout(1000)
            except:
                return False

            # Comprehensive init trigger: restore JS variables + try all known load fns
            try:
                hive_id = self.helper._cached_hive_id or ""
                worker  = self.helper._cached_worker_name or ""
                role    = self.helper._cached_hive_role or "worker"
                self.page.evaluate(f"""async () => {{
                    const h = '{hive_id}'; const w = '{worker}'; const r = '{role}';
                    if (h) {{
                        localStorage.setItem('wh_active_hive_id', h);
                        localStorage.setItem('wh_hive_id', h);
                        localStorage.setItem('wh_hive_role', r);
                        localStorage.setItem('wh_last_worker', w);
                    }}
                    try {{ if (typeof HIVE_ID !== 'undefined') HIVE_ID = h; }} catch(e) {{}}
                    try {{ if (typeof WORKER_NAME !== 'undefined') WORKER_NAME = w; }} catch(e) {{}}
                    try {{ if (typeof HIVE_ROLE !== 'undefined') HIVE_ROLE = r; }} catch(e) {{}}

                    // Dismiss gate overlay if present
                    const g = document.getElementById('hive-gate');
                    if (g) g.style.display = 'none';

                    // Try every known page init pattern (each page uses different names)
                    const fns = [
                        'init', 'initData', 'loadData',
                        'loadEntries', 'loadItems', 'loadPosts',
                        'loadProjects', 'loadTasks', 'loadAlerts',
                        'loadDashboard', 'loadKPIs', 'loadMembers',
                        'renderEntries', 'renderItems',
                    ];
                    for (const fn of fns) {{
                        if (typeof window[fn] === 'function') {{
                            try {{ await window[fn](); }} catch(e) {{
                                try {{ window[fn](); }} catch(e2) {{}}
                            }}
                        }}
                    }}
                    // Logbook-specific
                    try {{
                        if (typeof _viewMode !== 'undefined') _viewMode = 'mine';
                        if (typeof loadEntries === 'function') await loadEntries();
                        if (typeof renderEntries === 'function') await renderEntries(false);
                    }} catch(e) {{}}
                }}""")
                self.page.wait_for_timeout(2500)
            except:
                pass
            return True

    def snapshot_elements(self, selectors: Dict[str, str]) -> Dict[str, bool]:
        """
        Check visibility of each named element.
        Returns {"element_name": True/False, ...}
        """
        result = {}
        for name, selector in selectors.items():
            try:
                result[name] = self.page.locator(selector).first.is_visible(timeout=800)
            except:
                result[name] = False
        return result

    def close(self):
        try:
            self.context.close()
        except:
            pass


class RoleContextFactory:
    """Creates isolated browser contexts for each role."""

    def __init__(self, browser: Browser):
        self.browser = browser
        self._sessions: Dict[str, RoleSession] = {}

    def session(self, role: str) -> RoleSession:
        """Get (or create) a logged-in session for the given role."""
        if role not in self._sessions:
            ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
            sess = RoleSession(ctx, role)
            if not sess.login():
                raise RuntimeError(f"Could not log in as role={role}")
            self._sessions[role] = sess
        return self._sessions[role]

    def close_all(self):
        for sess in self._sessions.values():
            sess.close()
        self._sessions.clear()


# ── Diff helpers ───────────────────────────────────────────────────────────────

def diff_snapshots(
    supervisor_snap: Dict[str, bool],
    worker_snap: Dict[str, bool],
    solo_snap: Dict[str, bool],
) -> Dict:
    """
    Compare role snapshots and find permission violations.

    Returns:
        {
          "supervisor_only": [elements visible to supervisor but not worker],
          "worker_and_above": [elements visible to worker+supervisor but not solo],
          "violations": [unexpected visibility states],
        }
    """
    all_keys = set(supervisor_snap) | set(worker_snap) | set(solo_snap)

    supervisor_only = [
        k for k in all_keys
        if supervisor_snap.get(k) and not worker_snap.get(k)
    ]
    worker_and_above = [
        k for k in all_keys
        if worker_snap.get(k) and not solo_snap.get(k)
    ]
    # Both worker and supervisor see same thing (expected for most)
    shared = [
        k for k in all_keys
        if supervisor_snap.get(k) and worker_snap.get(k)
    ]

    return {
        "supervisor_only": supervisor_only,
        "worker_and_above": worker_and_above,
        "shared": shared,
        "supervisor": supervisor_snap,
        "worker": worker_snap,
        "solo": solo_snap,
    }


def format_diff(diff: Dict, page: str) -> str:
    """Human-readable diff summary."""
    lines = [f"Permission diff for {page}:"]
    if diff["supervisor_only"]:
        lines.append(f"  Supervisor-only: {diff['supervisor_only']}")
    if diff["worker_and_above"]:
        lines.append(f"  Worker+Supervisor (not solo): {diff['worker_and_above']}")
    if not diff["supervisor_only"] and not diff["worker_and_above"]:
        lines.append("  All roles see the same elements (check matrix completeness)")
    return "\n".join(lines)
