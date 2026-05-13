"""
One-shot codemod: add `for="<input-id>"` to every <label class="wh-label">
that precedes a labelled input (<input|select|textarea id="X">).

Why this exists: WorkHive forms already render visible labels as
<label class="wh-label">Field Name</label> followed by the input. Sighted
users see them; screen readers don't get the programmatic association
because no for-attribute ties them together. The UX Contract A2 check
flags every input where this association is missing. This script adds
the for-attribute in a single pass per file, without touching layout.

Pattern matched (per file):
  <label class="wh-label" ...>...</label>
  ...any whitespace / inline icons / required-tag spans...
  <input|select|textarea id="X"...>

Adds `for="X"` to the label tag's class block if not already present.

Usage:
  python tools/add_label_for.py logbook.html pm-scheduler.html dayplanner.html
  python tools/add_label_for.py --dry-run logbook.html

The dry-run mode prints would-be changes without writing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Match any <label> tag, then everything up to the next labelled input.
# The label may already have a `for=` attribute (skip those).
# We require the label and input to be within ~400 chars of each other
# so we don't grab a label from a different form section.
LABEL_RE = re.compile(
    r"""(?P<label_open><label\b[^>]*>)
        # label content may contain nested tags (<span>, <em>, etc.) so
        # match up to </label> non-greedily, allowing inner markup.
        (?P<label_text>(?:(?!</label>).)*?)
        (?P<label_close></label>)
        # Allow nested element subtrees (chip-bars, helper text) between
        # the label and its input. The safety check below ensures we don't
        # cross another labelled input.
        (?P<between>.*?)
        (?P<input_open><(?:input|select|textarea)\b[^>]*\bid\s*=\s*["'](?P<input_id>[^"']+)["'][^>]*>)""",
    re.VERBOSE | re.DOTALL | re.IGNORECASE,
)


def transform(src: str) -> tuple[str, int]:
    """Return (new_src, num_changes)."""
    changes = 0

    def repl(m: re.Match) -> str:
        nonlocal changes
        label_open = m.group("label_open")
        # Already has a for= attribute? Leave alone.
        if re.search(r"\bfor\s*=\s*['\"]", label_open, re.IGNORECASE):
            return m.group(0)
        input_id = m.group("input_id")
        # Templated/generated IDs (containing ${...}) — skip; the validator
        # also skips these because they aren't static.
        if "${" in input_id or "{" in input_id:
            return m.group(0)
        # Safety: if there's a LOT between </label> and <input>, the pairing
        # is probably wrong (e.g. label belongs to a different sibling input).
        # 400 chars is conservative; typical label-to-input gap is <100.
        if len(m.group("between")) > 400:
            return m.group(0)
        # Safety: if the in-between contains another <input|select|textarea>
        # (without us pairing to it), we're skipping over an input — abort.
        if re.search(r"<(?:input|select|textarea)\b", m.group("between"), re.IGNORECASE):
            return m.group(0)
        # Insert for="<id>" right after the opening <label
        new_label_open = re.sub(
            r"<label\b",
            f'<label for="{input_id}"',
            label_open,
            count=1,
        )
        changes += 1
        return (
            new_label_open
            + m.group("label_text")
            + m.group("label_close")
            + m.group("between")
            + m.group("input_open")
        )

    new_src = LABEL_RE.sub(repl, src)
    return new_src, changes


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
            print(f"  {n:>4}  {arg}  (dry-run, no write)")
        elif n:
            path.write_text(new_src, encoding="utf-8")
            print(f"  {n:>4}  {arg}  updated")
        else:
            print(f"  {n:>4}  {arg}  no changes")
    print(f"\n  Total: {total} labels gained for=")


if __name__ == "__main__":
    main()
