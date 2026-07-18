"""
Modal A11y — Forward-Only Debt Ratchet (Grounded Sweep critique C7).
====================================================================
The Grounded MCP Sweep found a SYSTEMIC gap: hand-rolled modal overlays across
the platform skip the dialog a11y contract that utils.js whConfirm/whPrompt
already model — no role="dialog", no aria-modal, no ESC-to-close, no focus trap.
The shell's sign-in modal was fixed inline (Wave 0); logbook (8 modals) and
others remain. Retrofitting them all at once is owner-disposed (critique C7), so
this validator does NOT demand zero today — it RATCHETS:

  - It counts hand-rolled modal overlays missing role="dialog"+aria-modal.
  - It freezes today's count as a DEBT CEILING in modal_a11y_baseline.json.
  - It FAILs only if the debt GROWS (a new non-a11y modal ships) — new modals
    must meet the bar.
  - As C7 retrofits land, lower the baseline (--update-baseline) to lock the
    gain forward-only — the gate can never silently slide back.

A modal overlay = a `<div id="...modal...">` (or class containing "modal") that
is a full-screen overlay (`fixed inset-0`). Compliant = its opening tag declares
both role="dialog" and aria-modal. (whConfirm/whPrompt build their dialog in JS
with the attributes already set, so pages that only use the helper carry no
hand-rolled overlay and contribute 0.)

Usage:
  python validate_modal_a11y.py                  # compare to baseline (gate mode)
  python validate_modal_a11y.py --update-baseline  # freeze current as the new ceiling

Exit codes:
  0  modal-a11y debt <= baseline ceiling (no new non-a11y modal).
  1  debt grew — a new hand-rolled modal shipped without role/aria-modal.
"""
from __future__ import annotations
import io, json, re, sys, glob, os
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "modal_a11y_baseline.json"

# Backups / throwaway test shells are out of scope (consistent with the sweep's
# excluded list in GROUNDED_SWEEP_ROADMAP.md).
SKIP_RE = re.compile(r"(\.backup\d*\.html$|-test\.html$|index-v\d|index-hive-test|index-native-test|symbol-gallery)")

# A modal overlay opening tag: a <div ...> that is full-bleed AND carries a
# dialog token in its id/class. WIDENED (Grounded Sweep critique C12 / W2): the
# original check keyed ONLY on the Tailwind marker "fixed inset-0", so overlays
# built with an inline style="position:fixed;inset:0" (pm-scheduler #pm-edit-modal)
# or a CSS overlay class (dayplanner .modal-overlay, pm-scheduler .sheet-overlay)
# evaded the ratchet entirely. Now all three full-bleed forms are detected, and
# the dialog token set includes "sheet"/"drawer"/"dialog" so bottom-sheets count.
_DIV_OPEN = re.compile(r"<div\b[^>]*>", re.IGNORECASE)

# CSS classes whose rule is a full-screen overlay (position:fixed; inset:0).
# 2026-07-06 (deep-walk dim 8): added "modal-bg" — project-manager's 8 modals are
# <div class="modal-bg"> whose full-bleed comes from a CSS `.modal-bg` rule (not inline
# nor a *-overlay class), so they evaded this ratchet entirely (scope gap the sweep found).
_OVERLAY_CLASS_TOKENS = ("modal-overlay", "sheet-overlay", "drawer-overlay", "dialog-overlay", "modal-bg")
# id/class substrings that mark an element as a dialog/sheet (needs a name + a11y bar).
_DIALOG_TOKENS = ("modal", "sheet", "dialog", "drawer")


def _is_full_bleed(tag: str) -> bool:
    """True if the tag renders as a full-screen overlay by any of the 3 means."""
    if "fixed inset-0" in tag:                       # Tailwind utility
        return True
    m_cls = re.search(r'class="([^"]*)"', tag)
    if m_cls and any(t in m_cls.group(1).lower() for t in _OVERLAY_CLASS_TOKENS):
        return True
    m_style = re.search(r'style="([^"]*)"', tag)     # inline position:fixed + inset:0
    if m_style:
        s = m_style.group(1).lower().replace(" ", "")
        if "position:fixed" in s and ("inset:0" in s or ("top:0" in s and "left:0" in s)):
            return True
    return False


def _is_modal_overlay(tag: str) -> bool:
    if not _is_full_bleed(tag):
        return False
    m_id = re.search(r'id="([^"]*)"', tag)
    m_cls = re.search(r'class="([^"]*)"', tag)
    idv  = m_id.group(1).lower() if m_id else ""
    clsv = m_cls.group(1).lower() if m_cls else ""
    return any(t in idv or t in clsv for t in _DIALOG_TOKENS)


def _is_a11y_compliant(tag: str) -> bool:
    return ('role="dialog"' in tag) and ("aria-modal" in tag)


def _js_covered_classes(text: str) -> set:
    """Classes on which the page programmatically sets role="dialog" (a valid, DRY a11y
    pattern: `querySelectorAll('.cls').forEach(el => el.setAttribute('role','dialog'))` +
    aria-modal). project-manager sets the dialog contract on ALL `.modal-bg` this way rather
    than repeating it inline on 8 divs. Only counts a class if BOTH role=dialog AND aria-modal
    are set via setAttribute somewhere on the page."""
    if not (re.search(r"setAttribute\(\s*['\"]role['\"]\s*,\s*['\"]dialog['\"]", text)
            and re.search(r"setAttribute\(\s*['\"]aria-modal['\"]\s*,\s*['\"]true['\"]", text)):
        return set()
    return {m.group(1).lower() for m in re.finditer(r"querySelectorAll\(\s*['\"]\.([a-z0-9_-]+)['\"]\s*\)", text)}


def scan_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    js_covered = _js_covered_classes(text)
    overlays, noncompliant = 0, []
    for tag in _DIV_OPEN.findall(text):
        if not _is_modal_overlay(tag):
            continue
        overlays += 1
        if _is_a11y_compliant(tag):
            continue
        m_cls = re.search(r'class="([^"]*)"', tag)
        clsv = m_cls.group(1).lower().split() if m_cls else []
        if any(c in js_covered for c in clsv):   # role/aria set on this class via JS
            continue
        mid = re.search(r'id="([^"]*)"', tag)
        noncompliant.append(mid.group(1) if mid else "(class-only modal)")
    return {"overlays": overlays, "noncompliant": noncompliant}


def scan_all() -> dict:
    pages: dict = {}
    for fp in sorted(glob.glob(str(ROOT / "*.html"))):
        name = os.path.basename(fp)
        if SKIP_RE.search(name):
            continue
        res = scan_page(Path(fp))
        if res["overlays"] == 0:
            continue
        pages[name] = res
    total = sum(len(v["noncompliant"]) for v in pages.values())
    return {"pages": pages, "total_noncompliant": total}


def _per_page_debt(scan: dict) -> dict:
    return {p: len(v["noncompliant"]) for p, v in scan["pages"].items()}


def main() -> int:
    scan = scan_all()
    debt = _per_page_debt(scan)
    total = scan["total_noncompliant"]

    if "--update-baseline" in sys.argv:
        BASELINE.write_text(json.dumps({
            "_README": "Forward-only DEBT CEILING for hand-rolled modal a11y (role=dialog+aria-modal). "
                       "Lower these as Grounded Sweep critique C7 retrofits land; never raise. "
                       "Regenerate with: python validate_modal_a11y.py --update-baseline",
            "total_noncompliant": total,
            "per_page": debt,
        }, indent=2), encoding="utf-8")
        print(f"\033[92mBASELINE WRITTEN\033[0m  modal_a11y_baseline.json — total debt {total} across {len(debt)} page(s).")
        return 0

    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"\033[91mFAIL\033[0m  cannot parse modal_a11y_baseline.json: {e}")
            return 1
    base_per = base.get("per_page", {})
    base_total = base.get("total_noncompliant", 0)

    grown = [(p, base_per.get(p, 0), debt[p]) for p in debt if debt[p] > base_per.get(p, 0)]

    bar = "=" * 70
    print(bar)
    if grown or total > base_total:
        print(f"\033[91mFAIL\033[0m  Modal a11y debt GREW (new hand-rolled modal without role=dialog+aria-modal)")
        print(f"  total debt {total} > baseline ceiling {base_total}")
        for p, was, now in grown:
            new_ids = [m for m in scan["pages"][p]["noncompliant"]]
            print(f"  - {p:<26s}  {was} -> {now}   modals: {', '.join(new_ids)}")
        print(bar)
        print("  Fix the new modal (add role=\"dialog\" aria-modal=\"true\" + ESC/focus-trap, see")
        print("  utils.js whConfirm/whPrompt), OR if intentional, run --update-baseline to re-freeze.")
        return 1

    improved = base_total - total
    print(f"\033[92mOK\033[0m  Modal a11y debt within ceiling: {total} <= {base_total}"
          + (f"  (improved by {improved} — consider --update-baseline to lock it)" if improved > 0 else ""))
    print(f"  {len(debt)} page(s) with hand-rolled modals tracked. Critique C7 retrofits ratchet this down.")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
