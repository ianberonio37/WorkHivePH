#!/usr/bin/env python3
"""validate_modal_back_contract.py — T42's lock: modals trap the hardware-Back gesture.

Walked live 2026-09-02 (critic T42): opening inventory's Add-Part modal pushed NO history entry,
so the phone Back gesture — a constant on Android — navigated away from the WHOLE page mid-form
(inventory → logbook; task and typed input gone). No page implemented modal-back-to-close.

The fix lives in the ONE shared primitive every hand-rolled modal already opts into
(whModalA11y / whSheetA11y): activate() pushes a history entry, a shared popstate handler closes
the top open modal via its OWN close path (the same logic Escape uses), and deactivate() gives the
entry back when the modal closed any other way (X, backdrop, save).

★2026-10-12 (UFAI W4791): THE GIVE-BACK WAS A POPSTATE EVERY LISTENER TOOK FOR A PERSON'S BACK.
skillmatrix's "Take Exam" closes the lesson and opens the exam in one click; the lesson's
history.back() fired a popstate, and two other listeners closed the exam that had just opened -
the skill exam could not be taken. Teaching only those listeners then sent the click to index.html,
because Chrome resolves a back() against the entry before the exam's pushState. The contract is
now six legs:
  1 push-on-activate        activate() pushes {whModalBack: true}
  2 popstate-closer         the shared handler closes the top modal from __whModalBackStack
  3 give-back-deferred      deactivate() counts a pending give-back and issues it a task later,
                            as ONE whBookkeepingBack(n)
  4 same-turn-takeover      activate() takes over a pending give-back instead of pushing
  5 bookkeeping-primitive   whBookkeepingBack counts the traversal (history.go(-n)) and
                            whIsBookkeepingBack answers "is this popstate a give-back?"
  6 every-listener-asks     EVERY popstate listener in a shipped page or shared script asks
                            whIsBookkeepingBack before acting - or is the primitive's own counter,
                            or is marked `wh-popstate-reconciler` (it only reconciles the URL and
                            closes nothing, so it must run on every move)
Self-test: each leg's removal reddens, and a naked popstate listener planted in a page reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["modal-back-contract"]

LEGS = [
    # activate()'s own push is the `else` arm after the take-over branches (__whModalBackFlush also pushes,
    # so a bare pushState match would survive the removal of activate's)
    ("push-on-activate",
     re.compile(r"else\s+history\.pushState\(\s*\{\s*whModalBack:\s*true\s*\}"),
     "activate() no longer pushes the modal's history entry - hardware Back exits the page mid-form again"),
    ("popstate-closer",
     re.compile(r"addEventListener\(\s*['\"]popstate['\"][\s\S]{0,400}?__whModalBackStack"),
     "the shared popstate handler is gone - Back no longer closes the top open modal"),
    ("give-back-deferred",
     re.compile(r"__whModalBackPending\s*=\s*\(window\.__whModalBackPending\s*\|\s*0\)\s*\+\s*1;[\s\S]{0,700}?whBookkeepingBack\(n\)"),
     "deactivate() no longer gives its entry back as ONE deferred whBookkeepingBack(n) - a ghost entry is left "
     "per X-close, or an immediate back() lands before the next modal's push (the W4791 exam that vanished)"),
    ("same-turn-takeover",
     re.compile(r"if\s*\(\(window\.__whModalBackPending\s*\|\s*0\)\s*>\s*0\)\s*window\.__whModalBackPending--;"),
     "activate() no longer takes over a pending give-back - a modal opened as another closes (lesson -> exam) "
     "is closed by, or loses its entry to, the closing modal's give-back"),
    ("bookkeeping-primitive",
     re.compile(r"window\.whBookkeepingBack\s*=\s*function[\s\S]{0,500}?history\.go\(-n\)[\s\S]{0,700}?"
                r"window\.whIsBookkeepingBack\s*=\s*function"),
     "the give-back primitive is gone - nothing tells a listener that a popstate was a modal tidying its "
     "entry, not the person pressing Back"),
]

# Shipped surfaces: every page and every shared script at the site root and its page folders. Tooling,
# tests, vendored packages and scratch output are not shipped.
_SKIP_DIRS = {"node_modules", ".tmp", "tests", "tools", "test-data-seeder", "playwright-report",
              "supabase", ".git", "substrate", "test-results", ".claude"}
_LISTENER = re.compile(r"addEventListener\(\s*['\"]popstate['\"]\s*,")
_ASKS = re.compile(r"whIsBookkeepingBack|__whModalBackSuppress")
_RECONCILER = "wh-popstate-reconciler"


def shipped_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if p.suffix not in (".html", ".js") or not p.is_file():
            continue
        rel = p.relative_to(ROOT).parts
        if any(part in _SKIP_DIRS for part in rel[:-1]):
            continue
        if p.name == "sw.js":
            continue
        out.append(p)
    return out


def naked_listeners(src: str, label: str) -> list[str]:
    """Each popstate listener must ask whIsBookkeepingBack in its handler, be the primitive's own counter,
    or be annotated as a URL reconciler just above. A named-function handler is read as not asking."""
    bad = []
    for m in _LISTENER.finditer(src):
        body = src[m.end(): m.end() + 700]
        before = src[max(0, m.start() - 900): m.start()]
        if _ASKS.search(body) or _RECONCILER in before:
            continue
        line = src.count("\n", 0, m.start()) + 1
        bad.append(f"{label}:{line} - a popstate listener that does not ask whIsBookkeepingBack(): a modal's "
                   f"give-back (X/backdrop/save close) will reach it as if the person pressed Back")
    return bad


def check(utils_src: str, pages: dict[str, str]) -> list[str]:
    problems = [msg for _, rx, msg in LEGS if not rx.search(utils_src)]
    for label, src in pages.items():
        problems.extend(naked_listeners(src, label))
    return problems


def _load() -> tuple[str, dict[str, str]]:
    utils = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    pages = {}
    for p in shipped_files():
        try:
            src = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "popstate" in src:
            pages[str(p.relative_to(ROOT)).replace("\\", "/")] = src
    return utils, pages


def main() -> int:
    utils, pages = _load()
    problems = check(utils, pages)
    if problems:
        print("FAIL modal-back-contract - the Back-traps-modals contract lost a leg:")
        for p in problems:
            print(f"    {p}")
        return 1
    n = sum(len(_LISTENER.findall(s)) for s in pages.values())
    print("PASS modal-back-contract - whModalA11y pushes one entry per open, Back closes the top modal through "
          "its own close path, an X/backdrop/save close gives the entry back a task later as one counted "
          f"traversal (a modal opening in the same turn takes it over), and all {n} popstate listeners in "
          f"{len(pages)} shipped files ask whether a popstate is a give-back before acting.")
    return 0


def self_test() -> int:
    utils, pages = _load()
    fails = []
    if check(utils, pages):
        fails.append("HEAD must PASS: " + "; ".join(check(utils, pages))[:400])
    for name, rx, _ in LEGS:
        broken = rx.sub("/* leg removed */", utils, count=1)
        if not check(broken, pages):
            fails.append(f"removing leg '{name}' must redden")
    planted = dict(pages)
    planted["planted.html"] = "<script>window.addEventListener('popstate', function () { closeAll(); });</script>"
    if not any("planted.html" in p for p in check(utils, planted)):
        fails.append("a naked popstate listener in a page must redden")
    named = dict(pages)
    named["named.html"] = "<script>window.addEventListener('popstate', _releaseSheets);</script>"
    if not any("named.html" in p for p in check(utils, named)):
        fails.append("a named-function popstate handler (cannot be read as asking) must redden")
    marked = dict(pages)
    marked["marked.html"] = ("<script>/* only fixes the URL (wh-popstate-reconciler) */\n"
                             "window.addEventListener('popstate', function () { fixUrl(); });</script>")
    if any("marked.html" in p for p in check(utils, marked)):
        fails.append("an annotated URL reconciler must pass")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_modal_back_contract self-test (each of the 5 utils legs reddens on removal; a naked or "
          "named popstate listener in a page reddens; an annotated reconciler passes; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
