"""
Supabase Client Singleton Validator -- WorkHive Platform
=========================================================
Catches the regression class "page creates multiple Supabase clients in
the same browser context." The Supabase JS SDK prints a warning when
more than one GoTrueClient instance shares the same storage key — they
race on the auth token and can produce undefined behavior under
concurrent reads.

Found 2026-05-13 walkthrough: index.html had THREE separate
supabase.createClient() calls (one per IIFE: auth, early-access signup,
ops home dashboard). Each created a fresh GoTrueClient → console warning.

Rules enforced:

  L1  Each HTML page contains AT MOST ONE inline
      `supabase.createClient(...)` call. Pages with multiple should
      use the shared singleton helper `window.getDb(url, key)` from
      utils.js.

  L2  Each shared JS module (nav-hub.js, companion-launcher.js, etc.) MUST NOT
      call `supabase.createClient` at module top level. Loaded scripts
      should reuse the page's existing client (via `window._whSupabaseClient`
      or accept a `db` argument).

OPT_OUT supports pages with a documented reason (e.g. an admin tool
that talks to a different project). Add with reason in the dict below.

Usage:  python validate_supabase_singleton.py
Output: supabase_singleton_report.json
"""
from __future__ import annotations

import os
import re
import json
import sys
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


ROOT = os.path.dirname(os.path.abspath(__file__))

# HTML pages that legitimately need >1 client. Empty by default; add
# entries with a one-line reason if a real use case emerges.
OPT_OUT_HTML: dict[str, str] = {}

# Shared JS modules (loaded on multiple pages) that MUST NOT create a
# top-level client. These are checked separately under L2.
SHARED_JS_FILES = [
    "utils.js",
    "nav-hub.js",
    "companion-launcher.js",
    "connectivity-widget.js",
    "form-autosave.js",
    "session-timeout.js",
    "device-fingerprint.js",
    "offline-queue.js",
    "offline-banner.js",
    "worker-drawer.js",
    "oc-helper.js",
    "maturity-gate.js",
    "wh-capture-validate.js",
]

CREATE_CLIENT_RE = re.compile(
    r"""(?<![A-Za-z0-9_$])
        supabase\s*\.\s*createClient\s*\(""",
    re.VERBOSE,
)


def _live_html_pages() -> list[str]:
    """Every HTML file in the project root that isn't a test / backup."""
    pages = []
    for f in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        name = os.path.basename(f)
        if name.endswith(("-test.html", ".backup.html", "_backup.html")):
            continue
        pages.append(name)
    return pages


def check_html_singleton(pages: list[str]) -> list[dict]:
    issues: list[dict] = []
    for page in pages:
        if page in OPT_OUT_HTML:
            continue
        src = read_file(os.path.join(ROOT, page)) or ""
        matches = list(CREATE_CLIENT_RE.finditer(src))
        if len(matches) <= 1:
            continue
        # Multiple direct calls. Build a friendly issue with line numbers.
        lines = []
        for m in matches:
            line_no = src.count("\n", 0, m.start()) + 1
            lines.append(str(line_no))
        issues.append({
            "check":  "html_singleton",
            "skip":   False,
            "reason": (
                f"{page}: {len(matches)} direct supabase.createClient() calls "
                f"at lines {', '.join(lines)}. Multiple clients share the "
                f"same auth storage key and race — the SDK warns "
                f"'Multiple GoTrueClient instances detected'. Replace each "
                f"call with `window.getDb(url, key)` from utils.js so the "
                f"page shares one client across IIFEs."
            ),
        })
    return issues


def _strip_js_comments(src: str) -> str:
    """Replace JS line and block comments with same-length whitespace to
    preserve line numbers, so we don't false-positive-match strings inside
    documentation comments like '// supabase.createClient(...)'."""
    def repl_block(m):
        return " " * len(m.group(0))
    def repl_line(m):
        return " " * len(m.group(0))
    src = re.sub(r"/\*[\s\S]*?\*/", repl_block, src)
    src = re.sub(r"//[^\n]*", repl_line, src)
    return src


def check_shared_js_no_top_level(modules: list[str]) -> list[dict]:
    issues: list[dict] = []
    for mod in modules:
        path = os.path.join(ROOT, mod)
        if not os.path.exists(path):
            continue
        raw = read_file(path) or ""
        src = _strip_js_comments(raw)
        for m in CREATE_CLIENT_RE.finditer(src):
            line_no = src.count("\n", 0, m.start()) + 1
            # Allow inside `function getDb` (the singleton helper itself)
            head = src[max(0, m.start() - 200): m.start()]
            if "getDb" in head or "_whSupabaseClient" in head:
                continue
            issues.append({
                "check":  "shared_js_no_top_level",
                "skip":   False,
                "reason": (
                    f"{mod}:{line_no} shared JS module calls supabase.createClient. "
                    f"Shared modules MUST reuse the page's existing client "
                    f"(via `window._whSupabaseClient`) or accept a `db` argument. "
                    f"Each module-level createClient adds a fresh GoTrueClient "
                    f"to every page that loads this module."
                ),
            })
    return issues


CHECK_NAMES  = ["html_singleton", "shared_js_no_top_level"]
CHECK_LABELS = {
    "html_singleton":          "L1  Each HTML page has at most one inline supabase.createClient()",
    "shared_js_no_top_level":  "L2  Shared JS modules don't create top-level Supabase clients",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSupabase Client Singleton Validator (2-layer)"))
    print("=" * 60)

    pages   = _live_html_pages()
    modules = SHARED_JS_FILES
    print(f"  {len(pages)} HTML page(s), {len(modules)} shared JS module(s) scanned.\n")

    issues: list[dict] = []
    issues += check_html_singleton(pages)
    issues += check_shared_js_no_top_level(modules)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    with open(os.path.join(ROOT, "supabase_singleton_report.json"), "w", encoding="utf-8") as f:
        json.dump({
            "validator": "supabase_singleton",
            "pages":     pages,
            "modules":   modules,
            "issues":    [i for i in issues if not i.get("skip")],
            "passed":    n_pass,
            "warned":    n_warn,
            "failed":    n_fail,
        }, f, indent=2, default=str)

    if n_fail == 0 and n_warn == 0:
        print(f"\n  \033[92mAll {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\n  \033[91m{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
