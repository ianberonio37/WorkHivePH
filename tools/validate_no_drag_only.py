#!/usr/bin/env python3
"""no-drag-only - T117 + T75 / WCAG 2.5.7: nothing may require a drag (2026-08-26).

A worker in gloves, a person with a tremor, anyone on a trackpad, a phone held
one-handed on a ladder - they share one need: no function should require a dragging
movement. WCAG 2.5.7 asks that anything operated by dragging also work with a single
pointer.

★THIS FILE WAS REBUILT AFTER I OVERWROTE IT. T117 established this gate; driving T75 I
wrote a second version straight over it, having read "updated successfully" as
"created" - and only the registry's own duplicate-id guard caught it, because the file
was untracked so git had no copy to restore. The original's findings are recovered
below from its registry label and merged with T75's refinement. Two trajectories, one
assertion, one gate: a duplicate id was the signal to MERGE, not to register twice.

THE CENSUS, clean on both passes, and every gesture the platform has is harmless:
  integrations.html   a CSV/Excel DROP ZONE done properly - guarded by
                      `if (dropZone && fileInput)`, the zone carries onclick ->
                      file-input.click(), role="button", tabindex="0" and an aria-label,
                      a real labelled <input type=file> is wired to the SAME handleFile
                      on change, and the visible copy reads "Drop file here or click to
                      browse". Drag-and-drop OVER a working file picker is exactly what
                      2.5.7 asks for.
  nav-hub.js,         `touchmove` that REPOSITIONS the floating button while opening it
  companion-launcher  stays a TAP.
  session-timeout.js  listens for touchstart as an activity SIGNAL, not a gesture
                      requirement.
  wh-persona          sets draggable=false - disabling dragging rather than requiring it.
  dayplanner.html     no drag machinery at all. T75's walk had flagged its reorder as an
                      SC 2.5.7 risk; there is no drag to provide an alternative for.

The one genuine keyboard trap in this family was already closed centrally: .wh-scroll-x
regions scrolled by swipe were unreachable from a keyboard (axe
scrollable-region-focusable, eight on project-report), fixed where the shared class
lives rather than per call site.

EXCLUDED, and scoped to product surfaces: maplibre-gl.js (a vendor bundle, not our
interaction design) and survey_ufai_rubric.js - the measurement tooling whose JOB is to
find drag handlers, since a lens that greps for dragstart would otherwise fail a gate
about dragstart.

THE ASSERTION is guard-the-absence: a NEW gesture fails here - not because dragging is
forbidden, but because "is there a tap that does the same thing?" is a question somebody
must answer out loud before it ships.

Usage: python tools/validate_no_drag_only.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP_FILE = re.compile(r"backup|test|^index-", re.I)
# third-party and internal-tooling scripts: not this platform's interaction design
EXCLUDED = {"maplibre-gl.js", "survey_ufai_rubric.js"}

DRAG = re.compile(r"""addEventListener\(\s*['"](dragstart|drop|touchmove|pointermove)['"]"""
                  r"""|draggable\s*=\s*['"]?true|ondragstart\s*=|ondrop\s*=""")
# a single-pointer path near the drag: a click/keyboard route to the same capability
ALT = re.compile(r"""addEventListener\(\s*['"](click|keydown|change)['"]|onclick\s*=|role\s*=\s*['"]button"""
                 r"""|tabindex\s*=\s*['"]0|\.click\(\)""")
# the handler writes only placement -> it MOVES a control rather than operating anything
POSITION_ONLY = re.compile(r"style\.(left|right|top|bottom|transform)\s*=")
# ...unless it also mutates data or state, which would make the drag load-bearing
FUNCTIONAL_DRAG = re.compile(r"\.(insert|update|upsert|delete)\s*\(|splice\s*\(|reorder|sort_order|"
                             r"position_index|\.value\s*=", re.I)


# ★THE NEGATIVE LOOKAHEAD IS LOAD-BEARING. `accept="image/*"` contains a literal /* , and a
# naive block-comment strip treated it as a comment OPENER - on logbook.html that swallowed 58,551
# characters up to the next real */, blanking an entire modal including an onclick. A census built
# on that reported a live, recently-hardened Save handler as dead code. A real comment opener is
# never immediately followed by a quote; a MIME wildcard in an attribute always is.
def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote) below: accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in (sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js"))))
             if not SKIP_FILE.search(Path(f).name) and Path(f).name not in EXCLUDED]
    if not files:
        print("SKIP no-drag-only - no surfaces found")
        return 0

    hooks, bare = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in DRAG.finditer(src):
            hooks += 1
            # the surrounding block: a single-pointer path must live with the drag, not on
            # some other screen
            window = src[max(0, m.start() - 1500):m.end() + 1500]
            # ★A DRAG THAT ONLY MOVES A CONTROL IS NOT DRAG-ONLY FUNCTIONALITY, and this is decided
            # by what the handler WRITES, not by which file it lives in - a name-based exemption
            # would be a licence. nav-hub's and companion-launcher's touchmove handlers assign only
            # style.left/right/top/bottom, i.e. they reposition the FAB and confer no capability:
            # opening the hub is a tap, and `didDrag` exists precisely so a drag does NOT fire it.
            # The need a reposition serves - a fixed control covering content - is already met for
            # everyone structurally, by the reserve and lift rules in that same file. If such a
            # handler ever starts doing something other than moving its element, it stops matching
            # this and the gate speaks up.
            if POSITION_ONLY.search(window) and not FUNCTIONAL_DRAG.search(window):
                continue
            if not ALT.search(window):
                line = src[:m.start()].count("\n") + 1
                bare.append(f"{name}:{line} wires {m.group(0)[:34]} with no click, keyboard or button "
                            f"path to the same capability")

    print(f"  drag hooks on production surfaces: {hooks} | drag-only: {len(bare)} "
          f"| excluded (third-party / internal tooling): {len(EXCLUDED)}")
    if bare:
        print(f"FAIL no-drag-only - {len(bare)} interaction(s) that need a drag to operate:")
        for x in bare[:10]:
            print("    - " + x)
        print("    WCAG 2.5.7: dragging excludes gloved hands, one-handed phone use on a ladder, and")
        print("    anyone whose grip is unreliable. Give the same capability a tap - integrations'")
        print("    drop zone shows the shape: role=button, tabindex=0, onclick to the file input, and")
        print("    copy that says 'Drop file here or click to browse'.")
        return 1
    print(f"PASS no-drag-only - all {hooks} drag hooks sit beside a single-pointer path to the same "
          f"capability.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
