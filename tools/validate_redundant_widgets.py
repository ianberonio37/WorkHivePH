#!/usr/bin/env python3
"""validate_redundant_widgets.py — LOCK for the redundant status-chrome + duplicate-action-widget classes.

Two forward-only ratchets from the 2026-07-22 redundant-widget consolidation. Ian: "there are still
redundant displays on every page … those are online and live pill … there is a bottom like updated x
minute ago … we will just remove it … in pm scheduler there is a + widget but there are already a
function of that … check everything platform-wide user facing pages."

CHECK A — freshness-footer STAYS retired (deterministic).
  The bottom-right "Updated X ago" footer (whFreshnessFooter → #wh-fresh-footer) DUPLICATED every
  adopting page's own source chip (renderSourceChip → `.wh-source-chip`, e.g. "Live · refreshed on
  load · Batay sa iyong logbook…"), which already states freshness at the TOP near the data — a G4
  "single freshness source" violation the family-wide adoption itself created. It was neutered to a
  no-op at its utils.js SSOT (removes the display on all ~18 adopters in one edit; the ~25 guarded
  call-sites became harmless). This asserts whFreshnessFooter STAYS a no-op — it must NOT stamp a
  footer again (no `whFreshnessChip(` call inside its body). Re-adoption = the duplicate freshness
  returns platform-wide. The source chip is the single freshness SSOT.

CHECK B — no NEW duplicate create-action widget (forward ratchet).
  A create / primary action wired to 2+ STATIC buttons on one page (e.g. pm-scheduler's Add-asset
  "+" FAB + the "Add Asset" bottom-nav tab, both `goAddAsset()`, both visible at every width) is a
  redundant widget. This counts create-action handlers wired to >=2 static (empty-arg) onclick
  buttons and ratchets on a baseline. State-branch pairs that are never simultaneously visible
  (empty-state vs populated-list "+ Add scope item"; a modal's close-X + Cancel) stay in the
  baseline; a genuinely NEW duplicate entry raises the count and fails. Companion of the FAB-
  consolidation discipline (4 shared FABs -> one nav-hub).

  python tools/validate_redundant_widgets.py                 # check (both ratchets)
  python tools/validate_redundant_widgets.py --update-baseline
  python tools/validate_redundant_widgets.py --self-test     # no repo
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "redundant_widgets_baseline.json"

# ── CHECK A: the freshness footer must stay a no-op ──────────────────────────────
# (brace-agnostic: slice from the fn declaration to its `window.` export, which immediately follows)

# ── CHECK B: create-action handlers on 2+ static buttons ─────────────────────────
# A "create/primary action" fn name — an ADD/NEW/CREATE/POST/COMPOSE verb — but NOT a
# close/cancel/back/next/dismiss (those legitimately repeat: close-X + Cancel on one modal).
CREATE_VERB = re.compile(r"(add|new|create|post|compose|open.*wizard|goadd)", re.I)
NEG_VERB = re.compile(r"(close|cancel|back|next|dismiss|hide|remove|delete|toggle|expand|collapse)", re.I)
BTN_RE = re.compile(r'<(?:button|a)\b[^>]*\bonclick\s*=\s*"([^"]+)"', re.I)
CALL_RE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(([^)]*)\)")


def _is_static_noarg(args: str) -> bool:
    """A static top-level action button call takes no dynamic per-row arg."""
    a = args.strip()
    if a == "":
        return True
    # a string LITERAL arg (e.g. closeModal('modal-x')) still = a distinct static button, but
    # dynamic per-row handlers (uuid / ${} / this / bare var) are list repeats — not widgets.
    if "${" in a or "this" in a:
        return False
    if re.search(r"['\"][0-9a-f]{6,}", a):
        return False
    if re.match(r"^[a-z_]\w*$", a):     # bare variable => per-row
        return False
    return True


def scan_footer(repo: Path) -> dict:
    """{'neutered': bool, 'reason': str} — is whFreshnessFooter a no-op in utils.js?"""
    u = repo / "utils.js"
    if not u.exists():
        return {"neutered": True, "reason": "utils.js absent (nothing to enforce)"}
    txt = u.read_text(encoding="utf-8", errors="ignore")
    i = txt.find("function whFreshnessFooter")
    if i == -1:
        return {"neutered": False, "reason": "whFreshnessFooter() not found in utils.js"}
    # body = fn declaration up to its `window.whFreshnessFooter =` export (immediately follows),
    # or a generous window if the export is absent (self-test snippets). Brace-agnostic.
    j = txt.find("window.whFreshnessFooter", i)
    body = txt[i: j if j != -1 else i + 800]
    # It re-renders the footer iff it stamps via whFreshnessChip on an appended element.
    stamps = "whFreshnessChip(" in body
    return {"neutered": not stamps,
            "reason": "stamps a footer via whFreshnessChip() again" if stamps else "no-op (no footer stamp)"}


def scan_dupes(repo: Path) -> list[dict]:
    """[{file, fn, count}] create-action handlers wired to >=2 static buttons, sorted."""
    out = []
    for f in sorted(repo.glob("*.html")):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        handlers: dict[str, int] = {}
        for m in BTN_RE.finditer(txt):
            cm = CALL_RE.search(m.group(1))
            if not cm:
                continue
            fn, args = cm.group(1), cm.group(2)
            if NEG_VERB.search(fn) or not CREATE_VERB.search(fn):
                continue
            if not _is_static_noarg(args):
                continue
            handlers[fn] = handlers.get(fn, 0) + 1
        for fn, n in handlers.items():
            if n >= 2:
                out.append({"file": f.name, "fn": fn, "count": n})
    return sorted(out, key=lambda x: (x["file"], x["fn"]))


def self_test() -> int:
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # neutered footer -> pass; stamping footer -> fail
        (repo / "utils.js").write_text(
            "function whFreshnessFooter(_o){ var el=document.getElementById('wh-fresh-footer');"
            " if(el&&el.parentNode)el.parentNode.removeChild(el); return; }\n", encoding="utf-8")
        if not scan_footer(repo)["neutered"]:
            fails.append("neutered footer must pass Check A")
        (repo / "utils.js").write_text(
            "function whFreshnessFooter(o){ var el=document.createElement('div');"
            " whFreshnessChip(el, Date.now(), o); }\n", encoding="utf-8")
        if scan_footer(repo)["neutered"]:
            fails.append("a footer that stamps via whFreshnessChip must FAIL Check A")
        # dup create-action: goAddAsset x2 static -> flagged; per-row + close x2 -> not
        (repo / "p.html").write_text(
            '<button onclick="goAddAsset()">+</button>\n'
            '<button onclick="goAddAsset()">Add Asset</button>\n'          # dup create x2 -> flag
            '<button onclick="closeModal()">x</button>\n'
            '<button onclick="closeModal()">Cancel</button>\n'            # close x2 -> NOT a create verb
            '<button onclick="togglePin(\'0f78abcd12\')">pin</button>\n'  # per-row dynamic -> skip
            '<button onclick="openComposer()">only once</button>\n',      # x1 -> not a dup
            encoding="utf-8")
        d = scan_dupes(repo)
        if not any(x["fn"] == "goAddAsset" and x["count"] == 2 for x in d):
            fails.append(f"goAddAsset x2 static must flag: {d}")
        if any(x["fn"] == "closeModal" for x in d):
            fails.append("closeModal (a close verb) must NOT count as a create-action dup")
        if any(x["fn"] == "openComposer" for x in d):
            fails.append("openComposer x1 must NOT flag")
    if fails:
        print("FAIL validate_redundant_widgets self-test:")
        for x in fails:
            print("  - " + x)
        return 1
    print("PASS validate_redundant_widgets self-test (footer-neutered · footer-stamp-fails · dup-create · close-skip · perrow-skip · single-skip)")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()

    footer = scan_footer(ROOT)
    dupes = scan_dupes(ROOT)
    dup_count = sum(x["count"] for x in dupes)  # total redundant create-action call-sites
    print(f"redundant-widgets: footer {'RETIRED' if footer['neutered'] else 'RE-ADOPTED'} ({footer['reason']}) · "
          f"{len(dupes)} page(s) with a create-action on 2+ static buttons ({dup_count} sites)")
    for x in dupes:
        print(f"    · {x['file']}: {x['fn']}() x{x['count']}")

    if "--update-baseline" in argv:
        BASELINE.write_text(json.dumps({"footer_neutered": footer["neutered"], "dup_sites": dup_count,
                                        "dupes": dupes}, indent=2), encoding="utf-8")
        print(f"baseline banked: footer_neutered={footer['neutered']} dup_sites={dup_count}")
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"footer_neutered": True, "dup_sites": 0}
    rc = 0
    if footer["neutered"] is False and base.get("footer_neutered", True) is True:
        print("FAIL redundant-widgets Check A: whFreshnessFooter re-adopted — the 'Updated X ago' footer "
              "DUPLICATES the source chip. Keep it a no-op; freshness lives in .wh-source-chip.")
        rc = 1
    if dup_count > base.get("dup_sites", 0):
        print(f"FAIL redundant-widgets Check B: {dup_count} duplicate create-action sites > baseline "
              f"{base.get('dup_sites', 0)} — a create action is wired to 2+ static buttons. Route it to ONE "
              f"labeled entry (a nav-tab / header button), not a second floating FAB.")
        rc = 1
    if rc == 0:
        print(f"PASS redundant-widgets: footer retired · dup create-action sites {dup_count} <= baseline {base.get('dup_sites', 0)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
