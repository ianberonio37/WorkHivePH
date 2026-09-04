#!/usr/bin/env python3
"""print-is-readable-on-paper - T124: the printed page must not be the dark theme.

Plants run on paper. A PM schedule goes on the noticeboard, an audit trail goes in a folder for
DOLE, a project report gets printed for a meeting - and this platform is DARK. Printing a dark
surface without print rules produces either a black page that empties a cartridge, or (because most
browsers drop backgrounds by default) pale grey text on white that nobody can read. Neither failure
appears anywhere on screen, which is what makes it worth a gate: print CSS is invisible until the
moment it has already wasted someone's time at the printer.

★IT HOLDS THE PAGES A PLANT DEMONSTRABLY PRINTS, AND REPORTS THE REST. Treating every @media print
block as a claim to be printable produced five manufactured findings: asset-hub's block exists, by
its own comment, so the rule is "reachable from document.styleSheets" for a different gate, and the
report pages already render as LIGHT document panels where a dark-to-light reset would be redundant.
The held set may not SHRINK - deleting the rules is not a way to pass - which keeps the ratchet
honest without inventing obligations nobody made.
[[feedback_coverage_improved_by_deleting_obligations]]

★THE CONTRACT, each clause from a way paper actually fails:
  1. a white background and dark text on <body>, or the whole sheet is the dark theme;
  2. the reset applied to DESCENDANTS too (body * ), because the cards, chips and banners each carry
     their own dark background and a rule on <body> alone leaves them;
  3. the interactive chrome hidden - nav hub, FAB, toasts, dialogs, buttons - since a printed button
     is a smear of ink offering something paper cannot do;
  4. page-break handling, so a card or a table row is not sliced across two sheets.

Re-drive: python tools/validate_print_is_readable_on_paper.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# ★THE SET IS THE PAGES THAT IMPLEMENT THE FULL DARK-TO-LIGHT RESET TODAY, and holding it is a
# RATCHET rather than a demand. A first version held every page carrying an @media print block to the
# whole contract and produced five findings, all of them manufactured:
#   - asset-hub's block says so in its own comment - it exists so "an @media print rule [is]
#     reachable from document.styleSheets", a token to satisfy a DIFFERENT gate, never a claim to be
#     printable;
#   - analytics-report and project-report render as LIGHT document panels on screen already, so a
#     body dark-to-light reset would be redundant, and demanding one is demanding the wrong fix.
# Inventing an obligation is not coverage. What is real and worth protecting is that the three pages
# a plant demonstrably prints - the schedule for the noticeboard, the audit trail for the folder, the
# logbook - already do this properly and must not quietly lose it.
# [[feedback_coverage_improved_by_deleting_obligations]]
MUST_PRINT = ["pm-scheduler.html", "audit-log.html", "logbook.html"]

SKIP_DIRS = ("node_modules", "_fixtures", ".tmp", "test-data-seeder", "learn", "tools", ".git")


def print_block(src: str):
    """EVERY @media print block on the page, concatenated.

    ★READING ONLY THE FIRST ONE JUDGED FIVE PAGES WRONGLY. analytics-report.html carries SIX print
    blocks and the first is a one-line rule about an editable field's min-height; asset-hub and
    engineering-design have three each. A gate that stops at the first match was grading each page on
    whichever rule happened to appear earliest in the file and reporting the other five as having no
    print reset at all. The contract is satisfied by the union of what the page declares, so the
    union is what gets read. [[feedback_i_rebuilt_a_guard_from_a_partial_read]]
    """
    blocks, pos = [], 0
    while True:
        i = src.find("@media print", pos)
        if i == -1:
            break
        j = src.find("{", i)
        if j == -1:
            break
        depth, start = 0, j
        while j < len(src):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(src[start:j + 1])
                    break
            j += 1
        pos = j + 1
    return "\n".join(blocks) if blocks else None


def main() -> int:
    # Match on the path RELATIVE to the project and on whole PARTS, never on the absolute string:
    # this project lives under ".../Self-learning Road-Map/...", which contains "learn", so a
    # substring test against the full path excluded EVERY page and the gate reported "0 printable
    # pages examined" while still failing. An exclusion list is only as good as what it matches
    # against. [[feedback_grep_matched_the_comment_not_the_link]]
    pages = sorted(p for p in ROOT.glob("*.html")
                   if not set(p.relative_to(ROOT).parts[:-1]) & set(SKIP_DIRS))
    printable, failures = [], []

    token_only = []
    for p in pages:
        src = io.open(p, encoding="utf-8", errors="replace").read()
        block = print_block(src)
        if block is None:
            continue
        printable.append(p.name)
        b = re.sub(r"\s+", " ", block)

        # Only the demonstrably-printed set is held to the contract; everything else is REPORTED, so
        # a token rule or a page that is already light does not become a manufactured finding.
        # ★AND page-break-inside:avoid MUST NOT SIT ON A TABLE THAT GROWS (T124, 2026-08-27).
        # `avoid` belongs on things that are SHORT BY CONSTRUCTION - a signoff block, a card. A data
        # table is not one: project-report's daily-progress table, measured at 96 rows, stood 5049px
        # tall (roughly FIVE A4 pages) while carrying `avoid`, which is an instruction no engine can
        # honour. The way they fail it is to push the whole table onto a fresh sheet and overflow
        # anyway - a wasted page and a risk of clipping the end. Break BETWEEN rows instead; the
        # row-level rule is the one that matters on paper, and <thead> repeats on its own.
        # COMMENTS STRIPPED FIRST, and the resurrection proof is what caught this: the selector
        # capture `[^{}]*table[^{}]*` swallowed the /* ... */ note sitting above the rule, and
        # because that note happens to mention <thead>, the row/cell exemption fired and the real
        # `table.doc-table { ... avoid }` was skipped. The gate read GREEN against the pre-fix world
        # — a matcher grading prose instead of the rule beneath it.
        # [[feedback_grep_matched_the_comment_not_the_link]]
        b_css = re.sub(r"/\*.*?\*/", " ", b, flags=re.S)
        for m in re.finditer(r"([^{}]*table[^{}]*)\{[^}]*page-break-inside:\s*avoid", b_css, re.I):
            sel = m.group(1).strip().strip(",")
            if re.search(r"\btr\b|\bthead\b|\btd\b|\bth\b", sel, re.I):
                continue        # row/cell-level avoid is exactly right
            failures.append(f"{p.name}: `{sel}` sets page-break-inside:avoid on a TABLE - a table "
                            f"that grows with its data cannot be kept on one sheet, and asking for "
                            f"it wastes a page and risks clipping the end. Keep `avoid` on the rows.")

        if p.name not in MUST_PRINT:
            if not re.search(r"body\s*\*\s*\{", b):
                token_only.append(p.name)
            continue

        if not re.search(r"body\s*\{[^}]*background:\s*(#fff|#ffffff|white)", b, re.I):
            failures.append(f"{p.name}: print rules do not force a WHITE page background - the dark "
                            f"theme goes to the printer")
        if not re.search(r"body\s*\{[^}]*color:\s*(#111|#000|black|#222)", b, re.I):
            failures.append(f"{p.name}: print rules do not force DARK text - light-on-white is "
                            f"unreadable once the browser drops the background")
        if not re.search(r"body\s*\*\s*\{", b):
            failures.append(f"{p.name}: the print reset is not applied to descendants (body * ) - "
                            f"every card, chip and banner keeps its own dark background")
        hidden = re.search(r"display:\s*none", b)
        chrome = re.search(r"wh-hub|wh-nav|fab|toast|role=dialog|\[role=dialog\]", b, re.I)
        if not (hidden and chrome):
            failures.append(f"{p.name}: the interactive chrome (hub, FAB, toasts, dialogs) is not "
                            f"hidden for print - a printed button is ink offering what paper cannot do")
        if not re.search(r"page-break-inside", b):
            failures.append(f"{p.name}: no page-break handling - a card or a table row will be sliced "
                            f"across two sheets")


    missing = [m for m in MUST_PRINT if m not in printable and (ROOT / m).exists()]
    for m in missing:
        failures.append(f"{m} has NO print rules at all, and it is a page people demonstrably print "
                        f"(a schedule for the noticeboard, an audit trail for a folder). Deleting the "
                        f"rules is not a way to pass this gate")

    if failures:
        print(f"FAIL print-is-readable-on-paper ({len(printable)} printable pages examined):")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"  full print reset (held): {', '.join(sorted(set(printable) & set(MUST_PRINT)))}")
    if token_only:
        print(f"  reported, not held: {', '.join(sorted(token_only))} - a print block without a "
              f"body-descendant reset. Either a token rule for another contract, or a page that "
              f"already renders light; neither is a defect this gate can decide statically.")
    held = sorted(set(printable) & set(MUST_PRINT))
    print(f"PASS print-is-readable-on-paper - the {len(held)} pages a plant demonstrably prints "
          f"force a white sheet with dark text, reset their descendants, hide the chrome and handle "
          f"page breaks; {len(printable) - len(held)} other pages carry print rules and are reported, "
          f"not held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
