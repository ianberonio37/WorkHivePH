#!/usr/bin/env python3
"""
page-log-tags — "the log is greppable" on the reference surfaces (P-K, 2026-09-05: P431 symbol-gallery,
P438 llm-observability, P452 founder-console). These pages call no edge function, so the trace-id gate
(log-correlation) has nothing to correlate; what a support engineer greps is the BROWSER console. Every
console.error / console.warn a reference page emits must start with its own tag - "[<page>] ..." - so a
line in a user's screenshot or a captured console names the page that wrote it. A page with zero
emitters is n/a and is listed so a silent page is visible, never mistaken for a tagged one.
Exit 0 = PASS, 1 = FAIL. `--self-test` proves the gate bites.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["validator-catalog.html", "symbol-gallery.html", "design-system.html", "llm-observability.html", "founder-console.html", "architecture.html", "offline-fallback.html",
         "platform-actions.html", "agentic-rag-observability.html", "plant-connections.html"]   # P434/P435/P439 (2026-09-05)
CALL_RE = re.compile(r"console\.(?:error|warn)\(\s*(['\"`])(.{0,80}?)\1", re.S)


def audit(src: str, page: str) -> tuple[int, list[str]]:
    tag = "[" + page.replace(".html", "") + "]"
    total = 0; bad: list[str] = []
    for m in CALL_RE.finditer(src):
        total += 1
        if not m.group(2).startswith(tag):
            line = src.count("\n", 0, m.start()) + 1
            bad.append(f"{page}:{line} {m.group(2)[:50]!r} lacks {tag}")
    # a call whose first argument is not a string literal (a variable / template) cannot be checked here
    untyped = len(re.findall(r"console\.(?:error|warn)\(\s*[^'\"`\s)]", src))
    if untyped:
        bad.append(f"{page}: {untyped} console.error/warn call(s) start with a non-literal - put the tag first as a literal")
    return total, bad


def self_test() -> None:
    assert audit("console.error('[x] failed')", "x.html") == (1, []), "tagged call passes"
    t, b = audit("console.error('failed')", "x.html"); assert t == 1 and b, "untagged call fails"
    t, b = audit("console.warn(err)", "x.html"); assert b, "non-literal first arg is flagged"
    assert audit("", "x.html") == (0, []), "no emitters = n/a"
    print("self-test OK: bites on an untagged / non-literal console.error, passes tagged, n/a on silence")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test(); return 0
    bad: list[str] = []; silent: list[str] = []; checked = 0
    for p in PAGES:
        f = ROOT / p
        if not f.exists():
            bad.append(f"{p}: MISSING (roster drift)"); continue
        total, b = audit(io.open(f, encoding="utf-8", errors="replace").read(), p)
        if total == 0:
            silent.append(p)
        else:
            checked += 1
        bad += b
    if bad:
        print(f"FAIL page-log-tags - {len(bad)} console line(s) a support engineer could not attribute:")
        for x in bad[:20]:
            print("  " + x)
        return 1
    print(f"PASS page-log-tags - {checked} page(s) tag every console.error/warn with their own name; silent (no emitters, n/a): {', '.join(silent) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
