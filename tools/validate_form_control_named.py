#!/usr/bin/env python3
"""form-control-named - T180: every form control says what it is (2026-08-26).

A control with no accessible name is a box a screen-reader user is asked to fill in
without being told what goes in it. On this platform that is not a theoretical harm:
the unnamed ones were a PM frequency selector, a CMMS column mapper, a scope-item
include checkbox and its estimated-hours field - each sitting in a LIST of near-identical
rows, where "combo box" announced twelve times in a row is indistinguishable from noise.

FIXED SIX, and each label names the ROW rather than the field, because these are heard
out of visual context: "Frequency for <task text>", "Source column for <field label>",
"Include scope item <title>", "Estimated hours for <title>", plus the two
validator-catalog filters that sat beside a search box which already had one.

★THE CENSUS WAS WRONG THREE TIMES AND THE CORRECTIONS ARE THE REAL CONTENT HERE.
41 -> 18 -> 8 -> 6, and every step removed FALSE accusations, not real defects:
  1. Checking only `label[for=id]` missed the WRAPPING form -
     `<label>Safety-critical <input type=checkbox></label>` - which needs no `for` and
     is how every checkbox and radio on the platform is labelled. That alone was 23
     wrong accusations, including all six of hive.html's intent radios.
  2. Reading raw source matched `<input>` and `<select>` written inside HTML, CSS and JS
     COMMENTS - prose DESCRIBING controls, e.g. logbook's "A filter <select> may not be
     squeezed narrower than the option it is showing" and voice-journal's "the only
     <input> in the whole document". Sixty-two of the 311 "controls" were sentences.
  3. Two survivors were labelled by TEMPLATE INTERPOLATION: resume.html builds
     `const _alab = \\`aria-label="${escHtml(fld.label)}"\\`` and injects `${_alab}` into
     the tag. The attribute is real at runtime and invisible to a static reader.
So this gate SKIPS any control whose tag carries an unresolved `${...}` in place of
attributes, and says so, rather than reporting a name it cannot see. A static oracle
must decline what it cannot know instead of guessing.

★PLACEHOLDER IS NOT A LABEL and is not accepted as one: it vanishes the moment the
field is focused, which is exactly when the reminder is needed, and it is not an
accessible name.

Usage: python tools/validate_form_control_named.py
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
CTRL = re.compile(r"<(input|select|textarea)\b([^>]*)>", re.I)
LBL = re.compile(r"<label\b[^>]*>(.*?)</label>", re.I | re.S)
NO_NAME_NEEDED = {"hidden", "submit", "button", "reset", "image"}


# ★THE NEGATIVE LOOKAHEAD IS LOAD-BEARING. `accept="image/*"` contains a literal /* , and a
# naive block-comment strip treated it as a comment OPENER - on logbook.html that swallowed 58,551
# characters up to the next real */, blanking an entire modal including an onclick. A census built
# on that reported a live, recently-hardened Save handler as dead code. A real comment opener is
# never immediately followed by a quote; a MIME wildcard in an attribute always is.
def strip_comments(s: str) -> str:
    """Blank comments while PRESERVING offsets, so the wrapping-label spans stay valid."""
    def blank(m):
        return " " * (m.end() - m.start())
    s = re.sub(r"<!--.*?-->", blank, s, flags=re.S)
    # (?!quote) below: accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html")))
             if not SKIP_FILE.search(Path(f).name)]
    if not files:
        print("SKIP form-control-named - no pages found")
        return 0

    total, skipped_dynamic, hidden_skipped, unnamed = 0, 0, 0, []
    for f in files:
        name = Path(f).name
        raw = io.open(f, encoding="utf-8", errors="replace").read()
        src = strip_comments(raw)
        forlabels = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', src, re.I))
        wraps = [(m.start(), m.end()) for m in LBL.finditer(src)
                 if re.sub(r"<[^>]+>", "", m.group(1)).strip()]
        for m in CTRL.finditer(src):
            tag, attrs = m.group(1).lower(), m.group(2)
            ty = (re.search(r'type="([^"]+)"', attrs, re.I) or [None, ""])[1].lower()
            if ty in NO_NAME_NEEDED:
                continue
            total += 1
            if re.search(r"aria-label=|aria-labelledby=", attrs, re.I):
                continue
            eid = (re.search(r'id="([^"]+)"', attrs, re.I) or [None, None])[1]
            if eid and eid in forlabels:
                continue
            if any(a <= m.start() < b for a, b in wraps):
                continue
            if "${" in attrs:          # attributes assembled at runtime — cannot be read statically
                skipped_dynamic += 1
                continue
            # ★A display:none CONTROL IS OUTSIDE THE ACCESSIBILITY TREE, so it has no name to give and
            # needs none: what a screen-reader user meets is the visible button that triggers it (the
            # nameplate scanner's hidden <input type=file> sits behind a labelled "Scan nameplate").
            # Demanding a name here would be noise, and noise is how a gate gets ignored. Labelling
            # them anyway is still good practice - the file-picker dialog can surface the input's own
            # name - which is why the platform's hidden pickers do carry one; it is just not a defect.
            if re.search(r'class="[^"]*\bhidden\b|style="[^"]*display\s*:\s*none', attrs, re.I):
                hidden_skipped += 1
                continue
            line = raw[:m.start()].count("\n") + 1
            unnamed.append(f"{name}:{line} <{tag}{' ' + ty if ty else ''}> has no accessible name")

    print(f"  form controls: {total} | unnamed: {len(unnamed)}"
          + (f" | skipped (attributes built at runtime): {skipped_dynamic}" if skipped_dynamic else "")
          + (f" | hidden (outside the a11y tree): {hidden_skipped}" if hidden_skipped else ""))
    if unnamed:
        print(f"FAIL form-control-named - {len(unnamed)} control(s) a screen reader cannot describe:")
        for x in unnamed[:12]:
            print("    - " + x)
        if len(unnamed) > 12:
            print(f"    ... and {len(unnamed) - 12} more")
        print("    Name the ROW, not just the field: these sit in lists of near-identical controls, and")
        print("    'combo box' announced twelve times is indistinguishable from noise. A placeholder is")
        print("    not a name - it disappears exactly when the reminder is needed.")
        return 1
    print(f"PASS form-control-named - all {total} form controls carry an accessible name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
