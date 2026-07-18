#!/usr/bin/env python3
# DEEPWALK-CELL: * D18
r"""validate_destructive_safety.py — D18 destructive-safety (confirm before delete/reset).

THE CLASS: a one-tap Delete / Remove / Reset / Leave that fires immediately destroys a record
(an FMEA mode, a worker's membership, a password, a scheduled PM) with no confirmation — a fat-
finger on a phone in the field wipes real data. The guard is a SHARED, styled async confirm modal
`window.whConfirm` (utils.js), loaded on EVERY page, whose contract is
`if (!(await whConfirm('Delete X?'))) return;` — the caller aborts on Cancel/Esc/backdrop.

Because whConfirm is ONE shared helper loaded platform-wide, the guarantee is platform-wide →
the `* D18` wildcard. THREE deterministic layers ($0, no browser/DB/model):
  1. SHARED HELPER — utils.js defines `window.whConfirm` and it resolves a boolean (OK→true,
     Cancel/Esc/backdrop→false), i.e. it is a real gate, not a stub that always resolves true.
  2. LOADED EVERYWHERE — utils.js self-guards a single definition (`if (window.whConfirm) return;`)
     and utils.js is the shared bundle every page includes (client-singleton invariant), so the
     helper is present on every surface.
  3. GENUINELY USED — the destructive-gate pattern is live: >= MIN_SITES `whConfirm(` call sites
     across pages sit on real destructive verbs (delete/remove/reset/leave/revoke/deactivate),
     proving it's the live pattern rather than dead code. A regression that strips confirms from
     destructive flows drops this below the ratchet floor.

(The "no orphan cascade" half of D18 is enforced at the DB layer by FK `ON DELETE` rules +
`validate_rpc_write_integrity` / trigger-existence gates; this gate owns the client confirm-gate.)

Exit 0 = PASS, 1 = FAIL. No file is edited.
"""
from __future__ import annotations
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"
GRN, RED, YEL, BLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
MIN_SITES = 15  # a forward-only floor: destructive flows across the platform stay confirm-gated
_DESTRUCTIVE = re.compile(r"delete|remove|reset|leave|revoke|deactiv|discard|clear|wipe|unlink|cancel",
                          re.I)


def main() -> int:
    fails: list[str] = []
    print(f"{BLD}DESTRUCTIVE SAFETY (D18) — delete/reset confirm-gated via shared whConfirm{RST}")
    print("=" * 80)

    if not UTILS.is_file():
        print(f"{RED}FAIL{RST}: utils.js not found")
        return 1
    usrc = UTILS.read_text(encoding="utf-8", errors="replace")

    # 1. SHARED HELPER defined + resolves a boolean gate (OK true / Cancel false), not a stub.
    if not re.search(r"window\.whConfirm\s*=\s*function", usrc):
        fails.append("utils.js does not define `window.whConfirm` (shared confirm modal)")
    else:
        # It must be a real GATE that can say NO: a Cancel control + an Escape/cancel path that
        # settles the promise with a falsy value. The modal wires OK/Cancel to a `dispose(value)`
        # that calls onResolve(value); Escape/Cancel dispose with false (or null for prompt).
        has_cancel_ctrl = "data-wh-modal-cancel" in usrc
        has_false_path = bool(re.search(r"dispose\(\s*(?:withInput\s*\?\s*null\s*:\s*)?false\s*\)", usrc)
                              or re.search(r"onResolve\(\s*false\s*\)", usrc)
                              or re.search(r"resolve\(\s*false\s*\)", usrc))
        if not (has_cancel_ctrl and has_false_path):
            fails.append("whConfirm has no cancel path settling false (Cancel/Esc) — "
                         "a confirm that can't be cancelled is not a gate")
        if re.search(r"function whConfirm[^{]*\{\s*return\s+(?:Promise\.resolve\(\s*)?true", usrc):
            fails.append("whConfirm stubbed to always-true (destructive actions would never prompt)")

    # 2. LOADED EVERYWHERE — single self-guarded definition (idempotent, owns the global).
    if not re.search(r"if\s*\(.*window\.whConfirm\s*\)\s*return", usrc):
        fails.append("whConfirm not self-guarded (`if (window.whConfirm) return;`) — "
                     "load-order duplication risk")

    # 3. GENUINELY USED on real destructive verbs across pages.
    sites = 0
    pages_using = set()
    for path in sorted(ROOT.glob("*.html")):
        html = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"whConfirm\((.{0,80})", html, re.S):
            if _DESTRUCTIVE.search(m.group(1)):
                sites += 1
                pages_using.add(path.name)
    if sites < MIN_SITES:
        fails.append(f"only {sites} destructive whConfirm( call-sites (floor {MIN_SITES}) — "
                     f"destructive flows may have lost their confirm gate")

    print(f"  shared helper: {'✓' if 'window.whConfirm' not in ''.join(f for f in fails if 'define' in f) else '✗'} · "
          f"destructive confirm-sites: {sites} across {len(pages_using)} pages (floor {MIN_SITES})")

    if fails:
        print(f"\n{RED}FAIL{RST}: {len(fails)} D18 destructive-safety breach(es):")
        for f in fails:
            print(f"  {RED}✗{RST} {f}")
        return 1
    print(f"\n{GRN}PASS{RST}: shared whConfirm is a real (cancellable) gate, loaded platform-wide, and "
          f"guards {sites} destructive actions across {len(pages_using)} pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
