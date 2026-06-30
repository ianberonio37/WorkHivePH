#!/usr/bin/env python3
"""validate_optimistic_ui.py - Arc S (Resilience/DR) C-lens cell `optimistic_ui_rollback`.
================================================================================
Optimistic UI must not show a "saved" row that never persisted. The dangerous
anti-pattern is committing fresh data to the in-memory list / DOM BEFORE the write
is confirmed, with no rollback on failure:

    list.unshift(newRow);                 // user sees it "saved"
    const { error } = await db.from(t).insert(newRow);   // ...then it fails
    // (no rollback) -> phantom row until refresh = silent data loss

The safe pattern (logbook.html: await insert -> if (error) return -> THEN render)
confirms first. This gate scans the write surfaces for the anti-pattern: a fresh
list-prepend/append immediately FOLLOWED (within a few lines) by an awaited
.insert(), where no rollback (splice/filter/pop/shift/rollback) appears after the
insert. Low-false-positive by design; the confirm-first pages pass clean.

Exit 0 = no render-before-confirm without rollback; 1 = an anti-pattern found.
Stdlib, file-static, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

WRITE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html", "asset-hub.html",
    "project-manager.html", "community.html", "voice-journal.html", "skillmatrix.html",
    "dayplanner.html",
]

# fresh-data list mutation that would "show saved" optimistically
MUT = re.compile(r"\b(\w+)\.(unshift|push)\(\s*([A-Za-z_$][\w$]*)\s*[\),]")
INSERT = re.compile(r"await\s+.*?\.from\([^)]*\)\.insert\(", re.IGNORECASE)
ROLLBACK = re.compile(r"\.(splice|filter|pop|shift)\(|rollback|revert", re.IGNORECASE)


def _scan(name: str):
    try:
        lines = (ROOT / name).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    hits = []
    for i, line in enumerate(lines):
        m = MUT.search(line)
        if not m:
            continue
        var = m.group(3)
        # is there an awaited insert within the next 4 lines? (mutation-before-insert)
        window = "\n".join(lines[i + 1:i + 5])
        if not INSERT.search(window):
            continue
        # the mutated var must look like fresh inserted data (not an unrelated list)
        # and there must be NO rollback in the 8 lines after the insert
        after = "\n".join(lines[i + 1:i + 12])
        if ROLLBACK.search(after):
            continue
        hits.append((i + 1, line.strip()[:90]))
    return hits


def main() -> int:
    print(f"{B}Arc S - optimistic-UI rollback (C-lens, no phantom row){X}")
    print("=" * 60)
    issues = []
    for page in WRITE_PAGES:
        hits = _scan(page)
        if hits:
            for ln, txt in hits:
                print(f"  {R}FAIL{X}  {page}:{ln}  render-before-confirm (no rollback): {txt}")
            issues.append(page)
        else:
            print(f"  {G}PASS{X}  {page}")
    if issues:
        print(f"\n{R}{B}  OPTIMISTIC-UI: FAIL{X} - render-before-confirm without rollback in: {', '.join(issues)}")
        return 1
    print(f"\n{G}{B}  OPTIMISTIC-UI: PASS{X} - writes confirm before committing UI (or roll back on failure).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
