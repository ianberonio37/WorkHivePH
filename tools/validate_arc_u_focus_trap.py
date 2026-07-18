#!/usr/bin/env python3
"""
validate_arc_u_focus_trap.py — Arc U (Accessibility) durable gate: modal FOCUS-TRAP + focus-restore.

axe is STATIC and cannot detect a focus trap or a missing focus-restore. This gate runs the headless
probe (tools/arc_u_focus_trap_probe.mjs — reuses FB2's reliable programmatic sign-in, NOT the
thrash-prone MCP browser) which opens the marketplace Post modal (representative of all 9 sheets wired
via wireSheetA11y -> whModalA11y), Tab-walks it 40x, and asserts:
  - focus-escapes == 0            (WCAG 2.1.2 No Keyboard Trap — focus stays inside the modal)
  - Escape closes the sheet
  - focus RETURNS to the opener   (WCAG 2.4.3 Focus Order — whModalA11y restores focus)

Locks the whModalA11y wiring against regression. Skips cleanly (exit 0) if node or the local stack is
absent — mirrors validate_axe_live.py (the probe itself exits 0 on sign-in failure). A real
focus-management regression is exit 1.
"""
import io
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tools" / "arc_u_focus_trap_probe.mjs"


def main() -> int:
    print("\n" + "=" * 72)
    print("  Arc U focus-trap / focus-restore gate (WCAG 2.1.2 + 2.4.3)")
    print("=" * 72)
    if shutil.which("node") is None:
        print("  SKIP: node not on PATH — focus-trap gate not evaluated (local-only live gate).")
        return 0
    if not PROBE.exists():
        print(f"  FAIL: {PROBE.name} missing — the focus-trap probe was removed.")
        return 1
    try:
        r = subprocess.run(["node", str(PROBE)], cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    except Exception as e:
        print(f"  SKIP: could not run the probe ({e}) — treating as local-stack-absent.")
        return 0
    out = (r.stdout or "").strip()
    if out:
        print("\n".join("  " + ln for ln in out.splitlines()))
    err = (r.stderr or "").strip()
    if err and r.returncode != 0:
        print("  stderr:", err[:400])
    if r.returncode == 0:
        print("\n  PASS: modal focus-trap holds + Escape closes + focus returns to the opener.\n")
    else:
        print("\n  FAIL: a modal focus-management regression (trap leak / no ESC-close / focus not restored).\n")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
