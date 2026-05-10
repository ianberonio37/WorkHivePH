"""
Realtime Subscription Cleanup Validator — WorkHive Platform
=============================================================
WorkHive uses Supabase Realtime channels on 11+ pages. Each `db.channel(...)`
opens a WebSocket subscription that holds resources on both client and
server until explicitly torn down via `db.removeChannel(...)` or
`.unsubscribe()`. When pages create channels but never tear them down:

  - Memory leaks: handler closures + DOM refs held forever.
  - Realtime quota: Supabase's free tier caps concurrent connections.
  - Stale handlers: navigating away then back can leave old handlers
    listening on stale state, firing toasts/updates against detached UI.
  - Battery drain on mobile (idle tabs keep WebSockets warm).

This is the cleanup-side counterpart of validate_realtime_payload_contract
(which gates the contract shape). Same gate family, different failure
mode: contract drift = silent wrong data; cleanup gap = silent resource
leak.

  Layer 1 — Cleanup pairing
    1.  Every file that creates `db.channel(...)` has at least one
        `db.removeChannel(...)` or `.unsubscribe()` somewhere in the
        same file.
    [FAIL] Channel created with no teardown — guaranteed leak.

  Layer 2 — Lifecycle wiring
    2.  At least one cleanup call in the file is reachable from a
        page-lifecycle event handler: `beforeunload`, `pagehide`,
        `visibilitychange`, or `unload`. Either inline within the
        handler, or via a cleanup function called from the handler.
    [FAIL] Cleanup exists but never fires on navigation — leak on
    every page transition.

  Layer 3 — Channel variable mutability
    3.  Every channel assigned to a variable that gets passed to
        removeChannel uses `let` or `var` (so the same variable can
        hold the active channel reference across re-subscribes), not
        `const`. Pages that re-subscribe within the session need to
        reassign the variable when the previous channel is removed.
    [WARN] `const ch = db.channel(...)` — re-subscribing leaks the old
    channel because the variable can't be reassigned.

  Layer 4 — Cleanup hygiene metric (informational)
    4.  Track per-file channel count vs cleanup count. Discrepancies
        often indicate an asymmetry that's not strictly a bug but
        worth eyeballing (e.g., 5 subscribes, 1 cleanup function that
        only handles 3 of them).
    [INFO] List of pages where channel count != cleanup-target count.

Usage:  python validate_realtime_cleanup.py
Output: realtime_cleanup_report.json
"""
from __future__ import annotations
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))


# Files we don't gate (test copies, retired pages).
SKIP_FILES = {
    "engineering-design-test.html",
    "hive-test.html",
}

LIFECYCLE_EVENTS = ("beforeunload", "pagehide", "visibilitychange", "unload")

# Files that LEGITIMATELY don't pair `db.channel(...)` with cleanup because
# they intentionally keep a channel open for the page's full lifetime
# (e.g., session-long presence channels). Documented case-by-case if added.
CLEANUP_OPT_OUT: dict = {}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _list_caller_files() -> list[str]:
    out: list[str] = []
    for fname in os.listdir(ROOT):
        if fname in SKIP_FILES:
            continue
        if not (fname.endswith(".html") or fname.endswith(".js")):
            continue
        out.append(os.path.join(ROOT, fname))
    return out


# ─── Pattern parsing ────────────────────────────────────────────────────────

# Match `<var> = db.channel(...)` (possibly chained). Captures the variable
# name (left of =) and the line.
CHANNEL_ASSIGN_RE = re.compile(
    r"""(?:^|;|\n)\s*
        (?:let\s+|var\s+|const\s+)?      # optional declaration keyword
        ([A-Za-z_]\w*)                    # variable name
        \s*=\s*
        \w+\.channel\s*\(""",
    re.MULTILINE | re.VERBOSE,
)
# Bare channel without assignment — `db.channel(...).on(...).subscribe();`
# These can never be cleaned up. Catch as a leak.
CHANNEL_BARE_RE = re.compile(
    r"(?<![=\w])\w+\.channel\s*\("
)
# Assignments declared with const (subset of CHANNEL_ASSIGN_RE matches).
CHANNEL_CONST_RE = re.compile(
    r"\bconst\s+([A-Za-z_]\w*)\s*=\s*\w+\.channel\s*\(",
)
# removeChannel / unsubscribe sites
REMOVE_RE = re.compile(r"\bremoveChannel\s*\(\s*([A-Za-z_]\w*)")
UNSUBSCRIBE_RE = re.compile(r"\b([A-Za-z_]\w*)\.unsubscribe\s*\(\s*\)")


def _extract_channel_creations(src: str) -> list[dict]:
    """Find every channel creation. Returns list of {var, line, declared}.
    `declared` is one of: 'let'/'var'/'const'/'reassign' (no decl keyword)."""
    out: list[dict] = []
    for m in CHANNEL_ASSIGN_RE.finditer(src):
        var = m.group(1)
        line = src[: m.start()].count("\n") + 1
        # Check for the declaration keyword preceding the var
        prefix = src[max(0, m.start()): m.start(1)]
        decl = "reassign"
        if "const" in prefix: decl = "const"
        elif "let" in prefix: decl = "let"
        elif "var" in prefix: decl = "var"
        out.append({"var": var, "line": line, "declared": decl})
    return out


def _has_lifecycle_cleanup(src: str) -> bool:
    """True if the file has at least one removeChannel/unsubscribe call
    inside (or referenced from) a page-lifecycle handler. Uses a simple
    heuristic: search for `addEventListener('<event>'` near a removeChannel
    OR an inline arrow that references removeChannel/unsubscribe."""
    for ev in LIFECYCLE_EVENTS:
        # Look for `addEventListener('event', ...)` or `on<event> =`
        pat = re.compile(
            rf"""(?:addEventListener\s*\(\s*['"`]{ev}['"`]|on{ev}\s*=)
                 [\s\S]{{0,800}}?
                 (?:removeChannel|\.unsubscribe\s*\(\s*\))""",
            re.VERBOSE,
        )
        if pat.search(src):
            return True
    # Alternate pattern: a cleanup function `function cleanup() { removeChannel ... }`
    # bound to an event later. We check if a function body contains removeChannel
    # AND the file later has `addEventListener('<event>', cleanup)` or similar.
    for ev in LIFECYCLE_EVENTS:
        fn_with_cleanup_re = re.compile(
            r"""function\s+(\w+)\s*\([^)]*\)\s*\{[\s\S]{0,600}?
                 (?:removeChannel|\.unsubscribe\s*\(\s*\))[\s\S]{0,300}?\}""",
            re.VERBOSE,
        )
        for fn_m in fn_with_cleanup_re.finditer(src):
            cleanup_fn_name = fn_m.group(1)
            bind_pat = re.compile(
                rf"addEventListener\s*\(\s*['\"`]{ev}['\"`][^,]*,\s*{re.escape(cleanup_fn_name)}\b"
            )
            if bind_pat.search(src):
                return True
    return False


# ─── Layer checks ────────────────────────────────────────────────────────────

def check_cleanup_pairing(file_data: list[dict]) -> list[dict]:
    """L1: Every file with channels has at least one removeChannel /
    unsubscribe call."""
    issues: list[dict] = []
    for fd in file_data:
        if not fd["channels"]:
            continue
        if fd["file"] in CLEANUP_OPT_OUT:
            continue
        if fd["cleanup_count"] > 0:
            continue
        issues.append({
            "check":  "realtime_cleanup_paired",
            "file":   fd["file"],
            "channel_count": len(fd["channels"]),
            "reason": (
                f"{fd['file']} creates {len(fd['channels'])} db.channel(...) "
                f"subscription(s) but has NO removeChannel(...) or "
                f".unsubscribe() call anywhere in the file. The channels are "
                f"guaranteed to leak on page navigation — handler closures + "
                f"DOM refs held forever, Supabase realtime quota burned per "
                f"reload. Add a removeChannel(<var>) call inside a "
                f"beforeunload / pagehide / visibilitychange handler."
            ),
        })
    return issues


def check_lifecycle_wiring(file_data: list[dict]) -> list[dict]:
    """L2: Cleanup must be reachable from a page-lifecycle event."""
    issues: list[dict] = []
    for fd in file_data:
        if not fd["channels"]:
            continue
        if fd["file"] in CLEANUP_OPT_OUT:
            continue
        if fd["cleanup_count"] == 0:
            continue   # already flagged by L1
        if fd["lifecycle_wired"]:
            continue
        issues.append({
            "check":  "realtime_cleanup_lifecycle",
            "file":   fd["file"],
            "channel_count":  len(fd["channels"]),
            "cleanup_count":  fd["cleanup_count"],
            "reason": (
                f"{fd['file']} has {fd['cleanup_count']} cleanup call(s) but "
                f"none are reachable from a page-lifecycle event handler "
                f"({', '.join(LIFECYCLE_EVENTS)}). Cleanup only fires on "
                f"explicit user-driven paths (e.g. button click); navigating "
                f"away leaks the channel. Wire a cleanup function to "
                f"window.addEventListener('beforeunload', ...) or similar."
            ),
        })
    return issues


def check_channel_const_pattern(file_data: list[dict]) -> list[dict]:
    """L3: Channel vars declared `const` can't be reassigned when re-
    subscribing — the previous channel reference is lost without first
    calling removeChannel on it."""
    issues: list[dict] = []
    for fd in file_data:
        for ch in fd["channels"]:
            if ch["declared"] != "const":
                continue
            issues.append({
                "check": "realtime_channel_const_decl", "skip": True,
                "file":  fd["file"], "line": ch["line"], "var": ch["var"],
                "reason": (
                    f"{fd['file']}:{ch['line']} uses `const {ch['var']} = "
                    f"db.channel(...)`. If the page later re-subscribes "
                    f"(e.g., switching active asset/hive), the const can't "
                    f"be reassigned — the new channel either errors on "
                    f"redeclaration or stomps the variable in a fresh "
                    f"scope, leaking the original channel. Use `let` or `var` "
                    f"at module scope so removeChannel + reassign is possible."
                ),
            })
    return issues


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "realtime_cleanup_paired",
    "realtime_cleanup_lifecycle",
    "realtime_channel_const_decl",
]
CHECK_LABELS = {
    "realtime_cleanup_paired":     "L1  Every file with channels has at least one removeChannel/unsubscribe",
    "realtime_cleanup_lifecycle":  "L2  Cleanup is wired to a page-lifecycle event handler",
    "realtime_channel_const_decl": "L3  No channels declared `const` (prevents reassignment on re-subscribe)  [WARN]",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nRealtime Subscription Cleanup Validator (4-layer)"))
    print("=" * 65)

    file_data: list[dict] = []
    for path in _list_caller_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        channels = _extract_channel_creations(src)
        cleanup_count = (
            len(REMOVE_RE.findall(src)) +
            len(UNSUBSCRIBE_RE.findall(src))
        )
        # Skip files with neither channels nor cleanup entirely
        if not channels and cleanup_count == 0:
            continue
        file_data.append({
            "file":            rel,
            "channels":        channels,
            "cleanup_count":   cleanup_count,
            "lifecycle_wired": _has_lifecycle_cleanup(src) if channels else False,
        })

    pages_with_ch = sum(1 for fd in file_data if fd["channels"])
    print(f"  {pages_with_ch} pages with realtime channels, "
          f"{sum(len(fd['channels']) for fd in file_data)} channel creations, "
          f"{sum(fd['cleanup_count'] for fd in file_data)} cleanup calls.\n")

    all_issues: list[dict] = []
    all_issues += check_cleanup_pairing(file_data)
    all_issues += check_lifecycle_wiring(file_data)
    all_issues += check_channel_const_pattern(file_data)

    by_check: dict = defaultdict(list)
    for i in all_issues:
        by_check[i["check"]].append(i)

    n_pass = n_warn = n_fail = 0
    for name in CHECK_NAMES:
        items = by_check.get(name, [])
        warns = [i for i in items if i.get("skip")]
        fails = [i for i in items if not i.get("skip")]
        label = CHECK_LABELS[name]
        if not items:
            print(f"  \033[92mPASS\033[0m  {label}")
            n_pass += 1
        elif not fails:
            print(f"  \033[93mSKIP\033[0m  {label}")
            n_warn += 1
        else:
            print(f"  \033[91mFAIL\033[0m  {label}")
            n_fail += 1

    # L4 metric (informational)
    asymmetric = [
        fd for fd in file_data
        if fd["channels"] and fd["cleanup_count"] > 0
        and fd["cleanup_count"] != len(fd["channels"])
    ]
    print(f"  \033[96mINFO\033[0m  L4  Channel/cleanup ratio: "
          f"{len(asymmetric)} page(s) where cleanup count != channel count "
          f"(may be intentional via shared cleanup, worth eyeballing)")

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")

    report = {
        "validator":  "realtime_cleanup",
        "summary":    {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "files":      file_data,
        "issues":     [i for i in all_issues if not i.get("skip")],
        "warnings":   [i for i in all_issues if i.get("skip")],
        "asymmetric_files": [fd["file"] for fd in asymmetric],
    }
    out = os.path.join(ROOT, "realtime_cleanup_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
