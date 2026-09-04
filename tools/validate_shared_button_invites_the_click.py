#!/usr/bin/env python3
"""A shared button class must carry its own cursor, not borrow one from the page (T179).

AFFORDANCE PARITY, measured live 2026-08-27: 601 interactive elements across 12 signed-in pages
(button / a[href] / [onclick] / [role=button], rendered and enabled), and exactly ONE did not
render with cursor:pointer -- marketplace's "Preview as buyer" .btn-ghost. It accepted a click it
never invited.

★THE INTERESTING PART IS WHY IT WAS ALONE. `.btn-ghost` and `.btn-secondary` are used on 16 pages.
tokens.css owned their 44px tap floor but said nothing about the cursor, and 15 of those pages
happened to declare a cursor in their own local rule. Marketplace never did, so its one ghost
button fell through to the browser default. The shared contract was incomplete and fifteen
independent local rules had been hiding it -- the same shape as a shared CSS contract leaving two
pages behind, except here the contract left ONE page behind and the other fifteen were quietly
carrying it.

So the fix went into tokens.css, not marketplace: patching the instance would have left the trap
armed for the next page that uses .btn-ghost without a local rule, which is precisely how this one
arrived. This gate holds the CONTRACT, so no future page can inherit an incomplete one.

★AND THE DISABLED HALF IS THE OTHER DIRECTION OF THE SAME PROPERTY. A control that will refuse the
click must not invite it either, so the disabled rule pairs with the enabled one. A gate that
checked only 'pointer exists' would go green on a stylesheet that offered pointer to a disabled
button.

This is a CONTRACT check on the shared stylesheet, deliberately not a live sweep: the live probe
is what discovered the defect and is re-runnable (.tmp/affordance.mjs), but the durable property
is that the shared class declares its own affordance rather than depending on each page to
remember.

TEETH: synthetic negatives -- each half of the contract removed in turn.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tokens.css"

SHARED_CLASSES = ("btn-ghost", "btn-secondary")


def _rule_for(src: str, cls: str, disabled: bool) -> str:
    """Return the declaration block of the shared rule naming this class."""
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", src):
        sel, body = m.group(1), m.group(2)
        if cls not in sel:
            continue
        has_disabled = ("disabled" in sel)
        if has_disabled == disabled:
            return body
    return ""


def audit(src: str) -> list:
    out = []
    for cls in SHARED_CLASSES:
        enabled_body = _rule_for(src, cls, disabled=False)
        if not enabled_body:
            out.append(f"tokens.css: no shared rule for .{cls} at all - every page using it must "
                       f"remember the affordance on its own, which is the failure this gate exists "
                       f"for")
            continue
        if "cursor" not in enabled_body:
            out.append(f"tokens.css: the shared .{cls} rule sets no cursor - a page that uses the "
                       f"class without a local cursor rule renders a button that accepts a click "
                       f"it never invites (marketplace's 'Preview as buyer', 2026-08-27)")
        elif not re.search(r"cursor\s*:\s*pointer", enabled_body):
            out.append(f"tokens.css: the shared .{cls} rule sets a cursor that is not pointer")

        disabled_body = _rule_for(src, cls, disabled=True)
        if not disabled_body:
            out.append(f"tokens.css: .{cls} has no disabled-state cursor rule - a control that "
                       f"will REFUSE the click still invites it")
        elif not re.search(r"cursor\s*:\s*(not-allowed|default)", disabled_body):
            out.append(f"tokens.css: the disabled .{cls} rule does not neutralise the cursor")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real tokens.css is clean", src, 0)]
    cases.append(("the enabled cursor removed is caught",
                  src.replace("box-sizing: border-box; cursor: pointer;", "box-sizing: border-box;"), 1))
    cases.append(("a non-pointer enabled cursor is caught",
                  src.replace("cursor: pointer;", "cursor: default;"), 1))
    cases.append(("the whole disabled rule removed is caught",
                  re.sub(r"[^{}]*disabled[^{}]*\{[^{}]*\}", "", src), 1))
    cases.append(("a disabled rule that still invites is caught",
                  src.replace("cursor: not-allowed;", "cursor: pointer;"), 1))
    cases.append(("the shared rule vanishing entirely is caught",
                  src.replace("a.btn-secondary, button.btn-secondary, a.btn-ghost, button.btn-ghost",
                              ".unused-legacy-selector"), 1))
    bad = 0
    for label, s, want in cases:
        f = audit(s)
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not SRC.exists():
        print("FAIL - tokens.css is gone; re-point this gate")
        return 1
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    users = sorted(p.name for p in ROOT.glob("*.html")
                   if any(c in io.open(p, encoding="utf-8", errors="replace").read()
                          for c in SHARED_CLASSES))
    findings = audit(src)
    print("shared-button-invites-the-click - a shared button class carries its own affordance")
    print(f"  classes: {', '.join('.' + c for c in SHARED_CLASSES)} | pages using them: {len(users)}")
    if findings:
        print("\nFAIL - the shared contract is incomplete, so each page must remember it:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - the shared classes invite the click when enabled and withdraw it when not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
