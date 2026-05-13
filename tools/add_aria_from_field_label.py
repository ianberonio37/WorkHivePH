"""
Phase-3 codemod: lift text from <div class="field-label">...</div> onto
the next sibling <input|select|textarea> as aria-label.

Pattern in engineering-design.html and similar dense calc layouts:

    <div class="field-label">Outdoor Temp</div>
    <div class="input-group">
      <input id="f-outdoor-temp" class="wh-input" type="number" value="35" />
      <span class="input-unit">°C</span>
    </div>

The "Outdoor Temp" text is the visible label but is a <div> not a <label>,
so neither <label for> nor aria-label exists. This codemod extracts the
field-label div's text content and adds it as aria-label on the next input.

Visual: unchanged. Programmatic association: gained.
Screen-reader: now hears "Outdoor Temp, edit text, 35 degrees Celsius."

Usage:
  python tools/add_aria_from_field_label.py --dry-run engineering-design.html
  python tools/add_aria_from_field_label.py engineering-design.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Approach: scan input-side. For each <input|select|textarea>, walk
# backward through the source to find the nearest preceding
# <div class="field-label">...</div> within ~500 chars and use its text.
# This handles the nested-field-label-divs case cleanly (a section heading
# styled as field-label doesn't trap the inner field-label).

INPUT_RE = re.compile(
    r"""<(?P<tag>input|select|textarea)\b(?P<attrs>[^>]*)>""",
    re.IGNORECASE,
)
NEAREST_FIELD_LABEL_RE = re.compile(
    r"""<div\b[^>]*\bclass\s*=\s*["'][^"']*\bfield-label\b[^"']*["'][^>]*>
        (?P<text>(?:(?!</div>).)*?)
        </div>""",
    re.VERBOSE | re.DOTALL | re.IGNORECASE,
)


def _strip_tags(html: str) -> str:
    """Return plain text by dropping inline tags + collapsing whitespace.
    Used to lift the visible label out of the div text content."""
    text = re.sub(r"<[^>]*>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    # Strip trailing parenthetical hint (e.g. "(Philippine defaults pre-filled)")
    text = re.sub(r"\s*\([^)]{0,80}\)\s*$", "", text)
    return text


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
    return m.group(1) if m else None


def transform(src: str) -> tuple[str, int]:
    """Walk each input, find the nearest preceding field-label div within
    a 500-char window, lift its text as aria-label. Skip if the input
    already has aria-label or if no usable field-label is in range."""
    changes = 0
    out_parts: list[str] = []
    pos = 0

    for m in INPUT_RE.finditer(src):
        attrs = m.group("attrs")
        tag = m.group("tag").lower()
        # Skip hidden / submit / button
        input_type = (_attr(attrs, "type") or "").lower()
        if input_type in {"hidden", "submit", "button"}:
            continue
        # Skip if already has aria-label or aria-labelledby
        if _attr(attrs, "aria-label") or _attr(attrs, "aria-labelledby"):
            continue
        # Skip if a static label is already paired
        input_id = _attr(attrs, "id")
        if input_id and not ("${" in input_id or "{" in input_id):
            if re.search(rf'<label[^>]*\bfor\s*=\s*["\']{re.escape(input_id)}["\']', src, re.IGNORECASE):
                continue
        # Walk backward to find nearest field-label div within 500 chars
        win_start = max(0, m.start() - 500)
        window = src[win_start: m.start()]
        # Find ALL field-label matches in the window, take the LAST one
        last = None
        for fm in NEAREST_FIELD_LABEL_RE.finditer(window):
            last = fm
        if not last:
            continue
        label_text = _strip_tags(last.group("text"))
        if not label_text or len(label_text) > 100:
            continue
        # Inject aria-label into the input tag
        safe = label_text.replace('"', "&quot;")
        new_attrs = f' aria-label="{safe}"' + attrs
        new_full = f"<{tag}{new_attrs}>"
        out_parts.append(src[pos: m.start()])
        out_parts.append(new_full)
        pos = m.end()
        changes += 1

    out_parts.append(src[pos:])
    return "".join(out_parts), changes


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    total = 0
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"  SKIP  {arg} — not found")
            continue
        src = path.read_text(encoding="utf-8")
        new_src, n = transform(src)
        total += n
        if dry_run:
            print(f"  {n:>4}  {arg}  (dry-run)")
        elif n:
            path.write_text(new_src, encoding="utf-8")
            print(f"  {n:>4}  {arg}  updated")
        else:
            print(f"  {n:>4}  {arg}  no changes")
    print(f"\n  Total: {total} aria-labels added from field-label divs")


if __name__ == "__main__":
    main()
