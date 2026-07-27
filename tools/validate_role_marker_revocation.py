#!/usr/bin/env python3
"""
validate_role_marker_revocation.py — HK1 detector: a role marker must not outlive the role.

WHY THIS EXISTS (the H8 walk, 2026-07-27). hive.html paints `html.is-supervisor` early from the
CACHED role, deliberately, so supervisor-only chrome does not flash in after the async membership
check (a CLS optimisation). Nothing removed it. Deleting a member's row left her browser carrying a
supervisor marker on <html> with no supervisor membership behind it — a role marker outliving the
role. It was harmless ONLY because the board never renders for a removed member; the moment any
supervisor-only rule keys off that class on a view a removed member CAN reach, it misapplies.

THE RULE: if a role-derived class is added to a PERSISTENT root (documentElement / body), the same
file must also be able to REMOVE it. Root elements survive every view switch and every re-render, so
unlike a card or a button they are never cleaned up incidentally — the removal has to be written.

This is HK1's second assertion. The first ("a hidden element must be EMPTY, not display:none over
real data") is a DOM property and is checked by the live deepwalk, not statically; conflating the two
into one gate would let a static PASS imply a live guarantee it never made.

SCOPE, deliberately narrow so a PASS means something:
  - only `documentElement` / `body` targets (persistent roots)
  - only role-vocabulary markers (supervisor/admin/owner/...), so `is-loading` on a button is not
    swept up — that one is scoped to an element that gets replaced anyway
  - `toggle()` counts as a removal: it is add-and-remove by construction

Self-test: `--selftest` (pure text analysis, no files).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# A marker is "role-derived" if its name carries a role word. Keep this list explicit rather than
# clever: a false negative here is a missed bug, a false positive is a wrongly-blocked build.
ROLE_WORDS = ("supervisor", "admin", "owner", "manager", "worker", "member", "staff", "moderator", "seller")

# `<something>documentElement.classList.add('x','y')` or `document.body.classList.add(...)`.
ADD_RE = re.compile(
    r"(documentElement|document\.body|\bbody)\s*\.classList\s*\.\s*(add|toggle)\s*\(([^)]*)\)")
REMOVE_RE = re.compile(
    r"(documentElement|document\.body|\bbody)\s*\.classList\s*\.\s*(remove|toggle)\s*\(([^)]*)\)")
CLASS_LITERAL_RE = re.compile(r"['\"]([A-Za-z0-9_-]+)['\"]")

SKIP_DIRS = {"node_modules", ".git", ".playwright-mcp", "dist", "build", "__pycache__"}


def _is_role_marker(cls: str) -> bool:
    low = cls.lower()
    return any(w in low for w in ROLE_WORDS)


def analyze(text: str) -> tuple[set[str], set[str]]:
    """Return (role markers added to a root, role markers removable from a root)."""
    added, removable = set(), set()
    for m in ADD_RE.finditer(text):
        for cls in CLASS_LITERAL_RE.findall(m.group(3)):
            if _is_role_marker(cls):
                added.add(cls)
                if m.group(2) == "toggle":
                    removable.add(cls)
    for m in REMOVE_RE.finditer(text):
        for cls in CLASS_LITERAL_RE.findall(m.group(3)):
            if _is_role_marker(cls):
                removable.add(cls)
    return added, removable


def _iter_files():
    for path in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        if any(part in SKIP_DIRS or part.startswith(".") for part in path.relative_to(ROOT).parts[:-1]):
            continue
        yield path


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    # The exact H8 defect: added on a root, never removed.
    bad = "if (r === 'supervisor') document.documentElement.classList.add('is-supervisor');"
    a, r = analyze(bad)
    chk("unremoved root role marker is caught", (sorted(a), sorted(r)), (["is-supervisor"], []))

    # The shipped fix.
    good = (bad + "\n document.documentElement.classList.remove('is-supervisor');")
    a, r = analyze(good)
    chk("add + remove is clean", sorted(a - r), [])

    # toggle() is add-and-remove by construction.
    a, r = analyze("document.body.classList.toggle('is-admin', isAdmin);")
    chk("toggle counts as removable", sorted(a - r), [])

    # PINNED FALSE POSITIVE (button-lock.js): a non-role class on a non-root element.
    a, r = analyze("btn.classList.add('is-loading');")
    chk("is-loading on a button is not a role marker", (len(a), len(r)), (0, 0))

    # PINNED FALSE POSITIVE: a role-word class on a NON-root element is out of scope — that element
    # is re-rendered, so it cannot outlive anything the way <html> does.
    a, r = analyze("card.classList.add('is-supervisor-card');")
    chk("role word on a non-root element is out of scope", (len(a), len(r)), (0, 0))

    # Multiple classes in one call must each be examined.
    a, r = analyze("document.documentElement.classList.add('is-owner','theme-dark');")
    chk("multi-arg add picks only the role marker", sorted(a), ["is-owner"])

    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    violations, scanned, markers = [], 0, 0
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned += 1
        added, removable = analyze(text)
        markers += len(added)
        for cls in sorted(added - removable):
            violations.append((path.name, cls))

    print(f"{BOLD}Role marker revocation (a role marker must not outlive the role){RESET}")
    if violations:
        for fname, cls in violations:
            print(f"  {RED}FAIL{RESET}  {fname}: '{cls}' is added to a persistent root but never removed")
        print(f"\n  {YELLOW}Add a classList.remove('<marker>') on the path where the role is lost{RESET}"
              f" (sign-out, kicked/removed membership, role downgrade).")
        return 1
    print(f"  {GREEN}PASS{RESET}  {markers} root role marker(s) across {scanned} file(s), every one removable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
